import asyncio
import sys

import pytest
from conftest import SAMPLE_WORKFLOW, write_workflow
from mcp import Client

from agentflow.cli import main
from agentflow.constants import MCP_SERVER_NAME, READ_ONLY_TOOLS, ExitCode, ToolName
from agentflow.mcp_server import CurrentProjectServices, build_server
from agentflow.projectlocator import EnvironmentProjectLocator
from agentflow.services import WorkspaceServices
from agentflow.workspace import find_workspace

GOOD_PLAN = "### C1 - Build it\n- role: builder\n- done-when: `pytest`\n- docs: không có — internal change\n"
# What only a person may do: none of it may be reachable through a tool.
PERSON_WORDS = {"approve", "cancel", "seal", "decide", "suppress", "ext", "extension", "config", "settings", "push", "pull", "confirm", "commit", "merge", "init"}


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def call(server, name, **arguments):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def tool_list(server):
    async def run():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())


@pytest.fixture
def server(repo):
    return build_server(WorkspaceServices(find_workspace(repo)))


def test_the_tool_list_is_exactly_the_agreed_one(server):
    names = {tool.name for tool in tool_list(server)}
    assert names == {str(name) for name in ToolName}
    assert names == {
        "status", "next_step", "plan_check", "report_write", "project_write", "replan_write", "scan_summary", "conventions", "knowledge_search", "knowledge_read", "diagnosis_write",
    }  # fmt: skip
    assert not [name for name in names if PERSON_WORDS & set(name.split("_"))]


def test_tools_say_whether_they_only_read(server):
    for tool in tool_list(server):
        assert tool.annotations.read_only_hint is (ToolName(tool.name) in READ_ONLY_TOOLS)


def test_status_and_next_step(server, repo):
    first = call(server, "status")
    assert not first.is_error and first.structured_content["active_task"] is None
    main(["task", "new", "t"])
    task = call(server, "status").structured_content["active_task"]
    assert task["id"] == "T-001" and task["current_step"] == "confirm"
    assert call(server, "next_step").structured_content["kind"] == "continue"


def test_report_write_and_its_rules_come_back_as_tool_errors(server, repo):
    refused = call(server, "report_write", step="confirm", content="x")
    assert refused.is_error and "no active task" in refused.content[0].text
    main(["task", "new", "t"])
    ok = call(server, "report_write", step="confirm", content="# Confirmed")
    assert not ok.is_error and ok.structured_content["path"].endswith("confirm.md")
    other = call(server, "report_write", step="build", content="x")
    assert other.is_error and "current step 'confirm'" in other.content[0].text
    main(["task", "advance", "--result", "pass"])
    final = call(server, "report_write", step="confirm", content="again")
    assert final.is_error and "final" in final.content[0].text


def test_plan_check_returns_problems_as_data(server, repo):
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])
    call(server, "report_write", step="build", content="### C1 - x\n- role: nobody\n")
    bad = call(server, "plan_check")
    assert not bad.is_error and bad.structured_content["ok"] is False and bad.structured_content["problems"]
    call(server, "report_write", step="build", content=GOOD_PLAN)
    assert call(server, "plan_check").structured_content == {"ok": True, "problems": []}


def test_project_write_takes_only_the_known_sections(server, repo):
    ok = call(server, "project_write", section="profile", content="# Profile")
    assert not ok.is_error and (repo / ".agentflow" / "project" / "profile.md").is_file()
    assert call(server, "project_write", section="secrets", content="x").is_error
    assert call(server, "project_write", section="profile", content=" ").is_error
    main(["task", "new", "t"])
    busy = call(server, "project_write", section="profile", content="# changed")
    assert busy.is_error and "still open" in busy.content[0].text


def test_knowledge_tools(server, repo):
    folder = repo / ".agentflow" / "knowledge"
    folder.mkdir(exist_ok=True)
    (folder / "tips.md").write_text("Use constants.\nNo magic strings.\n", encoding="utf-8")
    hits = call(server, "knowledge_search", query="magic").structured_content["result"]
    assert hits == [{"file": "tips.md", "line": 2, "text": "No magic strings."}]
    assert call(server, "knowledge_read", file="tips.md").structured_content["content"].startswith("Use constants")
    assert call(server, "knowledge_read", file="../state.json").is_error


def test_scan_summary_without_results(server, repo):
    assert call(server, "scan_summary").structured_content["task"] is None
    main(["task", "new", "t"])
    assert call(server, "scan_summary").structured_content["task"] == "T-001"


def test_the_server_finds_the_workspace_afresh_on_every_call(repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # outside any workspace
    server = build_server(CurrentProjectServices(EnvironmentProjectLocator(environ={"AGENTFLOW_HOME": str(tmp_path / "home")})))
    assert call(server, "status").is_error
    monkeypatch.chdir(repo)
    assert not call(server, "status").is_error


def test_a_real_stdio_server_answers_and_refuses(repo):
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "agentflow", "mcp", "serve"], cwd=str(repo))

    async def run():
        from mcp import ClientSession

        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            status = await session.call_tool("status", {})
            report = await session.call_tool("report_write", {"step": "confirm", "content": "x"})
            return names, status, report

    names, status, report = asyncio.run(run())
    assert names == {str(name) for name in ToolName}
    assert not status.is_error and report.is_error and "no active task" in report.content[0].text
    assert MCP_SERVER_NAME == "agentflow"
