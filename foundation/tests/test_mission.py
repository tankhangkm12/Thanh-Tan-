"""Phase B1: the mission of a project, written by the scout into profile.md and confirmed by a person.

The mission is the `## Mission` section of `.ThanhTan/project/profile.md`: why, for whom, scope, out of scope and
the source it came from. Confirmation is not a flag inside the file: agentflow keeps the sha256 of what a person
confirmed, so a document that an agent rewrites is unconfirmed again without anyone remembering to say so.
`agentflow project status` shows `mission:`, `profile:`, `architecture:` and `roadmap:` as missing, unconfirmed or confirmed.
"""

import json

import pytest
from mcp_helpers import call
from sdd_helpers import CONVENTIONS, PROFILE, init_workspace, project_dir, run, sample_workflow

from agentflow.constants import CliKind, ExitCode, HookEvent, ProjectSection
from agentflow.errors import AgentflowError
from agentflow.git import GitBranchLookup
from agentflow.hook import handle_hook
from agentflow.services import WorkspaceServices
from agentflow.workspace import find_workspace

INVALID_INPUT = 22


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    return init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)


@pytest.fixture
def service(ws):
    return WorkspaceServices(find_workspace(ws))


def state_line(capsys, name: str) -> str:
    """The value after `<name>: ` in the output of `agentflow project status`."""
    code, out, _ = run(capsys, "project", "status")
    assert code == ExitCode.OK
    lines = [line for line in out.splitlines() if line.startswith(f"{name}: ")]
    assert len(lines) == 1, out
    return lines[0].split(": ", 1)[1]


def write_profile(service, text=PROFILE):
    return service.write_project(ProjectSection.PROFILE, text)


# ------------------------------------------------------------------ the form


def test_a_profile_with_a_complete_mission_is_written_without_warnings(service):
    assert write_profile(service).warnings == ()


def test_a_profile_without_a_mission_is_still_written_but_warns(service, ws):
    info = write_profile(service, "# Profile\n\nA web shop.\n")
    assert (project_dir(ws) / "profile.md").is_file()
    assert len(info.warnings) == 1 and "Mission" in info.warnings[0]


@pytest.mark.parametrize("field", ["why", "for", "scope", "out-of-scope", "source"])
def test_a_missing_mission_field_is_named_in_the_warning(service, field):
    text = "\n".join(line for line in PROFILE.splitlines() if not line.startswith(f"- {field}:")) + "\n"
    info = write_profile(service, text)
    assert any(field in warning for warning in info.warnings), info.warnings


@pytest.mark.parametrize("field", ["why", "for", "scope", "out-of-scope", "source"])
def test_an_empty_mission_field_is_named_in_the_warning(service, field):
    lines = [f"- {field}:" if line.startswith(f"- {field}:") else line for line in PROFILE.splitlines()]
    info = write_profile(service, "\n".join(lines) + "\n")
    assert any(field in warning and "empty" in warning for warning in info.warnings), info.warnings


def test_a_mission_that_exists_only_inside_a_code_fence_does_not_count(service):
    fenced = "# Profile\n\nExample of the section:\n\n```\n" + PROFILE.split("## Build")[0].split("# Profile\n")[1] + "```\n"
    assert any("Mission" in warning for warning in write_profile(service, fenced).warnings)


def test_a_second_mission_section_is_reported(service):
    twice = PROFILE + "\n## Mission\n- why: khác\n"
    assert any("twice" in warning for warning in write_profile(service, twice).warnings)


def test_a_profile_is_still_stored_exactly_as_written(service, ws):
    """Regression: green before phase B; the mission checks may warn but must never rewrite the profile."""
    write_profile(service)
    assert (project_dir(ws) / "profile.md").read_text(encoding="utf-8") == PROFILE


# ---------------------------------------------------------------- the status


def test_the_status_of_an_empty_project_is_missing_everywhere(ws, capsys):
    for name in ("mission", "profile", "architecture", "roadmap"):
        assert state_line(capsys, name) == "missing", name


def test_a_written_mission_is_unconfirmed_until_a_person_confirms_it(service, ws, capsys):
    write_profile(service)
    assert state_line(capsys, "mission") == "unconfirmed"
    code, out, _ = run(capsys, "project", "confirm", "mission")
    assert code == ExitCode.OK and "confirmed: mission" in out
    assert state_line(capsys, "mission") == "confirmed"


def test_confirming_writes_no_flag_into_the_document(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    assert (project_dir(ws) / "profile.md").read_text(encoding="utf-8") == PROFILE
    assert (project_dir(ws) / "confirmations.json").is_file()


def test_the_same_text_written_again_stays_confirmed(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    write_profile(service)
    assert state_line(capsys, "mission") == "confirmed"


def test_line_endings_and_trailing_spaces_do_not_unconfirm(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    write_profile(service, PROFILE.replace("\n", "  \r\n"))
    assert state_line(capsys, "mission") == "confirmed"


def test_a_changed_mission_field_makes_the_mission_unconfirmed_again(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    write_profile(service, PROFILE.replace("báo bếp", "báo bếp, giao hàng"))
    assert state_line(capsys, "mission") == "unconfirmed"


def test_changing_another_part_of_the_profile_keeps_the_mission_but_not_the_profile(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission", "profile")
    write_profile(service, PROFILE.replace("make build", "make all"))
    assert state_line(capsys, "mission") == "confirmed"
    assert state_line(capsys, "profile") == "unconfirmed"


def test_an_agent_cannot_confirm_by_writing_a_status_line(service, ws, capsys):
    forged = PROFILE.replace("- source: docs/vision.md:3", "- source: docs/vision.md:3\n- status: confirmed")
    write_profile(service, forged)
    assert state_line(capsys, "mission") == "unconfirmed"


# --------------------------------------------------------------- confirming


def test_confirming_the_mission_needs_a_profile(ws, capsys):
    code, _, err = run(capsys, "project", "confirm", "mission")
    assert code == INVALID_INPUT and "profile" in err


def test_confirming_the_mission_needs_a_mission_section(service, ws, capsys):
    write_profile(service, "# Profile\n\nA web shop.\n")
    code, _, err = run(capsys, "project", "confirm", "mission")
    assert code == INVALID_INPUT and "Mission" in err
    assert state_line(capsys, "mission") == "missing"


def test_confirming_the_architecture_needs_the_document(ws, capsys):
    code, _, err = run(capsys, "project", "confirm", "architecture")
    assert code == INVALID_INPUT and "architecture" in err


def test_architecture_and_profile_can_be_confirmed_as_whole_documents(service, ws, capsys):
    write_profile(service)
    service.write_project(ProjectSection.ARCHITECTURE, "# Architecture\n\nOne service.\n")
    assert state_line(capsys, "architecture") == "unconfirmed"
    code, out, _ = run(capsys, "project", "confirm", "profile", "architecture")
    assert code == ExitCode.OK and "confirmed: profile, architecture" in out
    service.write_project(ProjectSection.ARCHITECTURE, "# Architecture\n\nTwo services.\n")
    assert state_line(capsys, "architecture") == "unconfirmed" and state_line(capsys, "profile") == "confirmed"


def test_confirming_again_says_it_was_already_confirmed(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    code, out, _ = run(capsys, "project", "confirm", "mission")
    assert code == ExitCode.OK and "already confirmed: mission" in out


def test_one_bad_code_confirms_nothing(service, ws, capsys):
    write_profile(service)
    code, _, err = run(capsys, "project", "confirm", "mission", "banana")
    assert code == INVALID_INPUT and "banana" in err
    assert state_line(capsys, "mission") == "unconfirmed"


def test_conventions_and_the_mission_can_be_confirmed_together(service, ws, capsys):
    write_profile(service)
    (project_dir(ws) / "conventions.md").write_text(CONVENTIONS, encoding="utf-8")
    code, out, _ = run(capsys, "project", "confirm", "PC-01", "mission")
    assert code == ExitCode.OK and "PC-01" in out and "mission" in out
    assert state_line(capsys, "mission") == "confirmed"


def test_all_still_means_every_convention_and_nothing_else(service, ws, capsys):
    write_profile(service)
    (project_dir(ws) / "conventions.md").write_text(CONVENTIONS, encoding="utf-8")
    code, out, _ = run(capsys, "project", "confirm", "--all")
    assert code == ExitCode.OK and "confirmed: PC-01" in out
    assert state_line(capsys, "mission") == "unconfirmed"


def test_a_workspace_without_a_confirmation_store_reads_as_unconfirmed(service, ws, capsys):
    write_profile(service)
    assert not (project_dir(ws) / "confirmations.json").exists()
    assert state_line(capsys, "mission") == "unconfirmed"


# -------------------------------------------------------- warnings on a task


def warning_lines(err: str, word: str) -> list[str]:
    return [line for line in err.splitlines() if word in line.lower()]


def test_a_new_task_warns_when_the_project_has_no_mission_yet(ws, capsys):
    code, _, err = run(capsys, "task", "new", "t")
    assert code == ExitCode.OK and warning_lines(err, "mission")


def test_a_new_task_warns_while_the_mission_is_unconfirmed(service, ws, capsys):
    write_profile(service)
    code, _, err = run(capsys, "task", "new", "t")
    assert code == ExitCode.OK and warning_lines(err, "mission")


def test_a_new_task_does_not_warn_about_a_confirmed_mission(service, ws, capsys):
    write_profile(service)
    assert run(capsys, "project", "confirm", "mission")[0] == ExitCode.OK
    code, _, err = run(capsys, "task", "new", "t")
    assert code == ExitCode.OK and not warning_lines(err, "mission")


# --------------------------------------------------------- the MCP tool


def test_the_project_write_tool_reports_the_warnings(ws):
    from agentflow.mcp_server import build_server

    server = build_server(WorkspaceServices(find_workspace(ws)))
    result = call(server, "project_write", section="profile", content="# Profile\n\nA web shop.\n")
    assert not result.is_error and result.structured_content["warnings"]


# ----------------------------------------------------- hand edits are blocked


def hook_payload(repo, tool, **tool_input):
    return json.dumps({"cwd": str(repo), "tool_name": tool, "tool_input": tool_input})


@pytest.mark.parametrize("name", ["confirmations.json", "profile.md"])
def test_regression_the_file_tools_cannot_write_the_mission_files(ws, name):
    """Green before phase B (the whole workspace is already protected); it must stay so for the new files."""
    target = str(project_dir(ws) / name)
    for tool, args in (("Write", {"file_path": target, "content": "x"}), ("Edit", {"file_path": target, "old_string": "a", "new_string": "b"})):
        out = json.loads(handle_hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, hook_payload(ws, tool, **args), GitBranchLookup()))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny", (tool, name)


def test_regression_a_shell_redirect_into_the_confirmation_store_is_blocked(ws):
    command = "echo {} > .ThanhTan/project/confirmations.json"
    out = json.loads(handle_hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, hook_payload(ws, "Bash", command=command), GitBranchLookup()))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


FILES = ["confirmations.json", "roadmap.md", "profile.md"]
SHELL_WRITES = [
    "echo {{}} > .ThanhTan/project/{name}",
    "echo {{}} >> .ThanhTan/project/{name}",
    "echo {{}}>.ThanhTan/project/{name}",
    "cat forged.json | tee .ThanhTan/project/{name}",
    "cp forged.json .ThanhTan/project/{name}",
    "mv forged.json .ThanhTan/project/{name}",
    "sed -i s/a/b/ .ThanhTan/project/{name}",
    "rm .ThanhTan/project/{name}",
    "truncate -s 0 .ThanhTan/project/{name}",
    "cd .ThanhTan/project && echo {{}} > {name}",
    "bash -c 'echo {{}} > .ThanhTan/project/{name}'",
]


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("command", SHELL_WRITES)
def test_a_shell_command_cannot_write_delete_or_replace_the_mission_roadmap_or_confirmation_files(ws, name, command):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    out = hook_reply(ws, "Bash", command=command.format(name=name))
    assert out and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny", command


POWERSHELL_WRITES = [
    "Set-Content -Path .ThanhTan\\project\\{name} -Value x",
    "Add-Content .ThanhTan/project/{name} x",
    "'x' | Out-File .ThanhTan/project/{name}",
    "Remove-Item .ThanhTan\\project\\{name}",
    "Copy-Item forged.json .ThanhTan\\project\\{name}",
    "New-Item .ThanhTan/project/{name} -Force",
]


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("command", POWERSHELL_WRITES)
def test_a_powershell_command_cannot_write_delete_or_replace_them_either(ws, name, command):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    out = hook_reply(ws, "PowerShell", command=command.format(name=name))
    assert out and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny", command


FILE_TOOLS = {
    "Write": lambda path: {"file_path": path, "content": "{}"},
    "Edit": lambda path: {"file_path": path, "old_string": "a", "new_string": "b"},
    "MultiEdit": lambda path: {"file_path": path, "edits": []},
    "NotebookEdit": lambda path: {"notebook_path": path, "new_source": "x"},
}


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("tool", FILE_TOOLS)
def test_no_file_tool_of_claude_code_can_write_them(ws, tool, name):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    out = hook_reply(ws, tool, **FILE_TOOLS[tool](str(project_dir(ws) / name)))
    assert out and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("name", FILES)
def test_no_file_tool_of_antigravity_can_write_them(ws, name):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    target = str(project_dir(ws) / name)
    for tool, args in (("write_to_file", {"TargetFile": target}), ("replace_file_content", {"TargetFile": target}), ("multi_replace_file_content", {"TargetFile": target})):
        payload = json.dumps({"workspacePaths": [str(ws)], "toolCall": {"name": tool, "args": args}})
        out = json.loads(handle_hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, payload, GitBranchLookup()))
        assert out["decision"] == "deny", (tool, name)


def test_a_path_with_dots_and_mixed_case_does_not_get_round_the_block(ws):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    sneaky = str(project_dir(ws) / ".." / "project" / "Confirmations.JSON")
    out = hook_reply(ws, "Write", file_path=sneaky, content="{}")
    assert out and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def hook_reply(repo, tool, **tool_input) -> str:
    return handle_hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, hook_payload(repo, tool, **tool_input), GitBranchLookup())


# ------------------------------------------- the project_write tool cannot reach the store


@pytest.fixture
def server(ws):
    from agentflow.mcp_server import build_server

    return build_server(WorkspaceServices(find_workspace(ws)))


@pytest.mark.parametrize("section", ["confirmations", "confirmations.json", "../confirmations", "project/confirmations", "history", "roadmap/../confirmations", "mission"])
def test_the_project_write_tool_has_no_section_that_reaches_the_confirmation_store(server, ws, section):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    result = call(server, "project_write", section=section, content='{"mission": "x"}')
    assert result.is_error
    assert not (project_dir(ws) / "confirmations.json").exists()


def test_the_mcp_server_offers_no_tool_that_confirms_anything(server):
    """Regression (evasion cases): the whole workspace is already protected, so this is green before phase B and must stay green once the new files exist."""
    from mcp_helpers import tool_list

    names = {tool.name for tool in tool_list(server)}
    assert not any("confirm" in name for name in names)


def test_a_profile_that_looks_like_a_confirmation_store_confirms_nothing(service, ws, capsys, server):
    write_profile(service)
    run(capsys, "project", "confirm", "mission")
    before = (project_dir(ws) / "confirmations.json").read_bytes()
    forged = json.dumps({"mission": "0" * 64, "profile": "0" * 64})
    result = call(server, "project_write", section="profile", content=forged)
    assert not result.is_error
    assert (project_dir(ws) / "confirmations.json").read_bytes() == before
    assert state_line(capsys, "profile") == "unconfirmed" and state_line(capsys, "mission") == "missing"


def test_writing_a_document_through_the_tool_never_confirms_it(service, ws, capsys, server):
    for section, text in (("profile", PROFILE), ("architecture", "# Architecture\n\nOne service.\n")):
        assert not call(server, "project_write", section=section, content=text).is_error
    assert state_line(capsys, "profile") == "unconfirmed" and state_line(capsys, "mission") == "unconfirmed"
    assert state_line(capsys, "architecture") == "unconfirmed"


def test_what_a_person_confirmed_is_confirmed_again_only_by_the_very_same_text(service, ws, capsys):
    write_profile(service)
    run(capsys, "project", "confirm", "mission", "profile")
    write_profile(service, PROFILE.replace("Đặt món", "Đặt món nhanh"))
    assert state_line(capsys, "mission") == "unconfirmed" and state_line(capsys, "profile") == "unconfirmed"
    write_profile(service)
    assert state_line(capsys, "mission") == "confirmed" and state_line(capsys, "profile") == "confirmed"


def test_a_task_in_progress_blocks_a_rewrite_of_the_profile(service, ws, capsys):
    """Regression: green before phase B (project documents are written between tasks)."""
    run(capsys, "task", "new", "t")
    with pytest.raises(AgentflowError) as exc:
        write_profile(service)
    assert exc.value.code == 31
