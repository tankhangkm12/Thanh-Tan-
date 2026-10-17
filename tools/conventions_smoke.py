"""Steps of the conventions flow that both smoke tests run: setup, confirming, questions, custom Semgrep rules.

The scout's part is played through the real MCP server (`agentflow mcp serve` over stdio), so the tool a model would
call is the one under test. A person's part (confirming, answering, copying a rule file) uses the real commands.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from smoke_support import AGENTFLOW, Session, expect

ENCODING = "utf-8"
RULE_FILE = "no-literal-status.yaml"
RULE = """rules:
  - id: no-literal-status
    languages: [python]
    severity: ERROR
    message: Use a constant for a status, not a string literal
    pattern: status = "..."
"""
PROJECT_DOCS = {
    "profile": "# Profile\n\nA sample service. Test: `python tests/check_items.py` (source: README.md:1).\n",
    "architecture": "# Architecture\n\nOne HTTP service, one database (source: app/server.py:1).\n",
    "sources": "# Sources\n\n- docs/contributing.md: conventions\n- app/server.py: code read\n",
}
CONVENTIONS = """# Quy ước

### PC-01 - No literal strings for fixed values
- check: semgrep
- rule: no-literal-status.yaml
- status: unconfirmed
- source: docs/contributing.md:2
- description: Statuses are constants, not string literals.

### PC-02 - Interface before implementation
- check: plan
- rule: item-order
- status: unconfirmed
- source: docs/contributing.md:3
- description: An interface item comes before the implementation items that touch the same file.

### PC-03 - Public functions have a docstring
- check: review
- status: unconfirmed
- source: app (inferred from code)
- description: Every public function has a one-line docstring.

## Câu hỏi mở

### S1 - Tests: pytest or plain scripts?
- docs: docs/contributing.md:4
- code: tests/check_items.py:1
"""
REVIEW_REPORT = """# Review

The change matches the plan.

PC-03: đạt
DC-01: đạt
DC-02: đạt

## Đề xuất cập nhật hồ sơ
không có

## Bài học đề xuất

### L1 - Keep statuses in one module
A literal status slipped in and only the convention rule caught it. Start with the constants module.
"""
SKIPPING_REPORT = "# Review\n\nThe change matches the plan.\n"


def mcp_call(repo: Path, tool: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Call a tool of the real MCP server started in ``repo``; returns (is_error, text of the answer)."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run() -> tuple[bool, str]:
        params = StdioServerParameters(command=AGENTFLOW, args=["mcp", "serve"], cwd=str(repo))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            return bool(result.is_error), "".join(getattr(part, "text", "") for part in result.content)

    return asyncio.run(run())


def setup_through_mcp(repo: Path) -> None:
    """What the scout does: four documents through `project_write`."""
    for section, text in {**PROJECT_DOCS, "conventions": CONVENTIONS}.items():
        failed, answer = mcp_call(repo, "project_write", {"section": section, "content": text})
        expect(not failed, f"project_write {section} through MCP", answer)
    forged = CONVENTIONS.replace("status: unconfirmed", "status: confirmed", 1)
    failed, answer = mcp_call(repo, "project_write", {"section": "conventions", "content": forged})
    expect(not failed and "PC-01" in answer and "demoted" in answer, "an agent cannot confirm a convention (it is demoted)", answer)


def person_assets(s: Session, base: Path, repo: Path) -> Path:
    """What the person does: a rule file in their store, copied in; confirm; answer the setup question."""
    store = base / "my-knowledge"
    s.af("knowledge", "init", "--dir", str(store))
    (store / "semgrep" / RULE_FILE).write_text(RULE, encoding=ENCODING)
    s.af("knowledge", "pull", f"semgrep/{RULE_FILE}")
    expect((repo / ".agentflow" / "knowledge" / "semgrep" / RULE_FILE).is_file(), "the rule file is copied into the workspace")
    warned = s.af("task", "new", "probe")
    expect("unconfirmed" in warned.stderr, "task new warns while conventions are unconfirmed", warned.stderr)
    s.af("task", "cancel")
    s.git("switch", "-q", "develop")
    s.af("project", "confirm", "PC-01", "PC-02", "PC-03")
    s.af("decide", "--answer", "S1", "--text", "Plain scripts are fine for tests here.", "--check", "review")
    listing = s.af("conventions").stdout
    expect("PC-01" in listing and "DC-01" in listing and "unconfirmed" not in listing, "all conventions are in force", listing)
    return store


def agents_cannot_decide_or_write(s: Session, repo: Path) -> None:
    for command in ("agentflow project confirm --all", "agentflow decide --answer Q1 --text x --check review", "agentflow knowledge push x.md"):
        verdict = json.loads(s.af("guard", stdin=json.dumps({"command": command, "cwd": str(repo)})).stdout)
        expect(verdict["rule"] == "person-only", f"the guard refuses `{command}` from an agent", str(verdict))
    target = str(repo / ".agentflow" / "decisions" / "forged.md")
    claude = s.af("hook", "pre-tool", "--cli", "claude", stdin=json.dumps({"cwd": str(repo), "tool_name": "Write", "tool_input": {"file_path": target}}))
    expect(json.loads(claude.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny", "the Claude hook refuses a Write into .agentflow/")
    agy = s.af(
        "hook", "pre-tool", "--cli", "antigravity",
        stdin=json.dumps({"workspacePaths": [str(repo)], "toolCall": {"name": "write_to_file", "args": {"TargetFile": target}}}),
    )  # fmt: skip
    expect(json.loads(agy.stdout)["decision"] == "deny", "the Antigravity hook refuses write_to_file into .agentflow/")
    shell = json.loads(s.af("guard", stdin=json.dumps({"command": "echo x > .agentflow/decisions/forged.md", "cwd": str(repo)})).stdout)
    expect(shell["rule"] == "workspace-write", "the guard refuses a shell redirect into .agentflow/", str(shell))
    expect(not Path(target).exists(), "nothing was written into .agentflow/decisions/")


def plan(items: list[tuple[str, str, str, str]], question: bool = False) -> str:
    """A plan of (code, kind, files, title) items for the implementer; with a question when asked."""
    text = ""
    for code, kind, files, title in items:
        text += (
            f"### {code} - {title}\n- role: implementer\n- kind: {kind}\n- files: {files}\n"
            f"- done-when: `test -f {files.split(',')[0].strip()}`\n- docs: không có — a tiny sample file\n\n"
        )
    if question:
        text += "## Chưa có quy ước\n\n### Q1 - Which module holds the statuses?\n- ask: The plan adds statuses and no convention says where they live.\n- options: statuses.py, constants.py\n- needed-by: C1\n"
    return text


def active_task(repo: Path) -> str:
    state = json.loads((repo / ".agentflow" / "state.json").read_text(encoding=ENCODING))
    return state["active_task_id"]


def conventions_flow(s: Session, base: Path, repo: Path) -> None:
    """Setup -> confirm -> a wrong plan and an open question stop the plan -> a custom Semgrep rule stops the
    security step -> the review must answer each convention -> approved, tagged, lessons proposed."""
    print("\n-- conventions: setup, confirm, questions, a custom Semgrep rule, the review gate")
    s.git("switch", "-q", "develop")
    setup_through_mcp(repo)
    store = person_assets(s, base, repo)
    agents_cannot_decide_or_write(s, repo)

    s.af("task", "new", "Statuses as constants")
    task = active_task(repo)
    failed, answer = mcp_call(repo, "project_write", {"section": "profile", "content": "# changed during a task"})
    expect(failed and "still open" in answer, "project documents are not written while a task is open", answer)
    failed, answer = mcp_call(repo, "report_write", {"step": "plan", "content": "too early"})
    expect(failed and "current step 'confirm'" in answer, "report_write refuses a step that is not the current one", answer)
    failed, answer = mcp_call(repo, "report_write", {"step": "confirm", "content": "# Confirmed\nStatuses become constants."})
    expect(not failed, "report_write saves the confirm report", answer)
    s.af("task", "advance", "--result", "pass")
    s.af("task", "approve")

    wrong = plan([("C1", "implement", "service.py, statuses.py", "Use the statuses"), ("C2", "interface", "statuses.py", "Declare the statuses")], question=True)
    failed, answer = mcp_call(repo, "report_write", {"step": "plan", "content": wrong})
    expect(not failed, "the plan is saved through MCP", answer)
    bad = s.af("plan", "check", ok=False)
    expect("interface item C2" in bad.stdout and "PC-02" in bad.stdout, "an implementation before its interface is refused", bad.stdout)
    expect("Q1" in bad.stdout and "decide --answer Q1" in bad.stdout, "an unanswered question blocks the plan", bad.stdout)
    failed, answer = mcp_call(repo, "plan_check", {})
    expect(not failed and '"ok": false' in answer.replace('"ok":false', '"ok": false'), "the plan_check tool reports the same problems", answer)
    s.af("task", "advance", "--result", "pass", ok=False)  # the plan-valid gate refuses
    s.af("decide", "--answer", "Q1", "--text", "Statuses live in statuses.py.", "--check", "review")
    right = plan([("C1", "interface", "statuses.py", "Declare the statuses"), ("C2", "implement", "service.py, statuses.py", "Use the statuses")], question=True)
    s.af("report", "--step", "plan", stdin=right)
    s.af("plan", "check")
    s.af("task", "advance", "--result", "pass")
    s.af("task", "approve")

    (repo / "statuses.py").write_text('"""Statuses."""\n\nSTATUS_OPEN = "open"\n', encoding=ENCODING)
    s.git("add", "statuses.py")
    s.af("commit", "declare the statuses", "--item", "C1")
    (repo / "service.py").write_text('status = "open"\n', encoding=ENCODING)
    s.git("add", "service.py")
    s.af("commit", "use a status", "--item", "C2")
    s.af("task", "advance", "--result", "pass")  # implement
    s.af("task", "advance", "--result", "pass")  # test
    blocked = s.af("scan", ok=False)
    expect("semgrep-conventions: blocked" in blocked.stdout, "the convention's own Semgrep rule catches a literal string", blocked.stdout)
    (repo / "service.py").write_text('"""Service."""\n\nfrom statuses import STATUS_OPEN\n\nstatus = STATUS_OPEN\n', encoding=ENCODING)
    s.git("add", "service.py")
    s.af("commit", "use the constant", "--item", "C2")
    clean = s.af("scan")
    expect("semgrep-conventions: clean" in clean.stdout, "the rule passes once the literal is a constant", clean.stdout)
    s.af("task", "advance", "--result", "pass")  # security

    mcp_call(repo, "report_write", {"step": "review", "content": SKIPPING_REPORT})
    refused = s.af("task", "advance", "--result", "pass", ok=False)
    expect("PC-03" in refused.stderr + refused.stdout and "DC-01" in refused.stderr + refused.stdout, "a review that skips a convention cannot pass", refused.stderr)
    failed, answer = mcp_call(repo, "report_write", {"step": "review", "content": REVIEW_REPORT})
    expect(not failed, "the review report answers each convention", answer)
    s.af("task", "advance", "--result", "pass")
    s.af("task", "approve")

    tag = f"agentflow/{task}/approved"
    expect(s.git("tag", "-l", tag) == tag and s.git("cat-file", "-t", tag) == "tag", "the approval tag is annotated")
    lesson = repo / ".agentflow" / "tasks" / task / "lessons" / "L1.md"
    summary = (repo / ".agentflow" / "tasks" / task / "summary.md").read_text(encoding=ENCODING)
    expect(lesson.is_file() and "L1: Keep statuses in one module" in summary, "the summary proposes the lesson and it is a file", summary)
    s.af("knowledge", "push", str(lesson))
    expect((store / "lessons" / "L1.md").is_file(), "a person pushed the lesson into their own store")
