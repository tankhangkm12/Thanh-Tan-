# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3", "pyyaml>=6.0.3"]
# ///
"""End-to-end smoke test of tiers, layer order, per-project role grants and small tasks, on a throw-away repository.

    uv run tools/smoke_modes.py

Uses the installed `agentflow` and the real dev-core workflow. A fake MCP server (fake_mcp_server.py) stands in for a
project's own MCP server. Needs git and a running Docker or Podman engine (the small task runs real scans).
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from fake_mcp_server import READ_TOOL, SERVER_NAME, TOOL_NAMES, WRITE_TOOL
from smoke_support import AGENTFLOW, ENCODING, Failure, Session, _make_writable_and_retry, expect

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "families" / "software-dev" / "core" / "workflow.yaml"
MAIN, DEVELOP = "main", "develop"
SERVER_PREFIX = f"mcp__{SERVER_NAME}__"
EXIT_ROLE_GRANT_REFUSED = 34
EXIT_PLAN_INVALID = 24
EXIT_GATE_FAILED = 25
PROJECT_AGENTS = Path(".claude") / "agents"
LAYERS = "interface, api, domain"


def item(code: str, title: str, layer: str, files: str, tier: str | None = None) -> str:
    tier_line = f"- tier: {tier}\n" if tier else ""
    return (
        f"### {code} - {title}\n- role: implementer\n{tier_line}- layer: {layer}\n- files: {files}\n"
        f"- done-when: `test -f {files}`\n- docs: không có — a plain file\n\n"
    )


QUESTION = "## Chưa có quy ước\n\n### Q1 - Thứ tự lớp?\n- ask: Dự án chưa nói thứ tự các lớp.\n- options: interface, api, domain\n"
WRONG_ORDER = item("C1", "Domain rule", "domain", "domain.txt", "fast") + item("C2", "Interface", "interface", "interface.txt", "fast") + QUESTION
RIGHT_ORDER = (
    item("C1", "Interface", "interface", "interface.txt", "fast")
    + item("C2", "Api", "api", "api.txt", "fast")
    + item("C3", "Domain rule", "domain", "domain.txt")
    + QUESTION
)


def fake_server_tools() -> set[str]:
    """The tools the fake MCP server really offers, listed over MCP."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run() -> set[str]:
        params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("fake_mcp_server.py"))])
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            return {tool.name for tool in (await session.list_tools()).tools}

    return asyncio.run(run())


def front(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding=ENCODING).split("---")[1])


def to_plan_step(s: Session, title: str, size: str | None = None) -> None:
    args = ["task", "new", title] + (["--size", size] if size else [])
    s.af(*args)
    s.af("report", "--step", "confirm", stdin="# Confirmed\n")
    s.af("task", "advance", "--result", "pass")
    s.af("task", "approve")


def tiers_and_layers(s: Session) -> None:
    to_plan_step(s, "Tiered work")
    s.af("report", "--step", "plan", stdin=WRONG_ORDER)
    unanswered = s.af("plan", "check", ok=False)
    expect("no answer yet" in unanswered.stdout, "an unanswered question blocks the plan", unanswered.stdout)
    s.af("decide", "--answer", "Q1", "--text", "Layers are built in order.", "--check", "plan", "--rule", "layer-order", "--layers", LAYERS)
    refused = s.af("plan", "check", ok=False)
    expect(refused.returncode == EXIT_PLAN_INVALID and "C2" in refused.stdout and "layer 'interface' comes after C1" in refused.stdout, "a later layer before an earlier one is refused", refused.stdout)
    s.af("report", "--step", "plan", stdin=RIGHT_ORDER.replace("- tier: fast", "- tier: turbo", 1))
    bad = s.af("plan", "check", ok=False)
    expect("unknown tier 'turbo'" in bad.stdout, "an unknown tier is refused", bad.stdout)
    s.af("report", "--step", "plan", stdin=RIGHT_ORDER)
    s.af("plan", "check")
    assigned = s.af("plan", "assign", "--cli", "claude").stdout.splitlines()
    expect(
        assigned == ["C1 implementer fast implementer-fast", "C2 implementer fast implementer-fast", "C3 implementer deep implementer-deep"],
        "fast items go to implementer-fast, deep and untiered items to implementer-deep",
        "\n".join(assigned),
    )
    s.af("task", "cancel")
    s.git("switch", "-q", DEVELOP)


def role_grants(s: Session, repo: Path) -> None:
    offered = fake_server_tools()
    expect(offered == set(TOOL_NAMES), "the fake MCP server offers a read tool and a write tool", str(offered))
    agents = repo / PROJECT_AGENTS
    s.af("role", "grant", "implementer", f"{SERVER_PREFIX}*")
    for name in ("implementer-fast", "implementer-deep"):
        header = front(agents / f"project-{name}.md")
        expect(f"{SERVER_PREFIX}*" in header["tools"].split(", ") and header["name"] == f"project-{name}", f"project-{name} carries the granted server")
    fast, plugin_fast = front(agents / "project-implementer-fast.md"), front(ROOT / "families/software-dev/core/claude/agents/implementer-fast.md")
    expect((fast["model"], fast["effort"]) == (plugin_fast["model"], plugin_fast["effort"]) == ("sonnet", "low"), "the project copy keeps the tier's model and effort")
    expect(s.git("status", "--porcelain") == "", "the project agents stay out of git")
    expect(".claude/agents/project-*.md" in (repo / ".git/info/exclude").read_text(encoding=ENCODING), "they are listed in .git/info/exclude")

    refused = s.af("role", "grant", "reviewer", f"{SERVER_PREFIX}{WRITE_TOOL}", ok=False)
    expect(refused.returncode == EXIT_ROLE_GRANT_REFUSED and "only reads" in refused.stderr, "reviewer is refused a tool that writes", refused.stderr)
    expect(s.af("role", "grant", "planner", f"{SERVER_PREFIX}*", ok=False).returncode == EXIT_ROLE_GRANT_REFUSED, "a read-only role is refused a whole server")
    s.af("role", "grant", "reviewer", f"{SERVER_PREFIX}{READ_TOOL}")
    expect(f"{SERVER_PREFIX}{READ_TOOL}" in front(agents / "project-reviewer.md")["tools"], "reviewer gets the tool that reads")
    expect(not (agents / "project-planner.md").exists(), "nothing was made for the refused grant")

    listing = s.af("role", "list").stdout
    expect("project-implementer-fast (current)" in listing and "Antigravity" in listing, "role list shows the agents and the Antigravity note", listing)

    verdict = json.loads(s.af("guard", stdin=json.dumps({"command": f"agentflow role grant reviewer {SERVER_PREFIX}*", "cwd": str(repo)})).stdout)
    expect(verdict["rule"] == "person-only", "an agent cannot run role grant", str(verdict))
    write = json.loads(
        s.af("hook", "pre-tool", "--cli", "claude", stdin=json.dumps({"cwd": str(repo), "tool_name": "Write", "tool_input": {"file_path": str(agents / "project-implementer-fast.md")}})).stdout
    )
    expect(write["hookSpecificOutput"]["permissionDecision"] == "deny", "the hook stops an agent writing a project agent")

    to_plan_step(s, "Granted work")
    s.af("report", "--step", "plan", stdin=item("C1", "Quick", "api", "api.txt", "fast") + item("C2", "Hard", "domain", "domain.txt"))
    claude = s.af("plan", "assign", "--cli", "claude").stdout.splitlines()
    expect(claude == ["C1 implementer fast project-implementer-fast", "C2 implementer deep project-implementer-deep"], "Claude Code items go to the project agents", "\n".join(claude))
    antigravity = s.af("plan", "assign", "--cli", "antigravity").stdout.splitlines()
    expect(antigravity[0] == "C1 implementer fast implementer-fast", "Antigravity keeps the plugin agents (it sees every installed MCP)", "\n".join(antigravity))
    s.af("task", "cancel")
    s.git("switch", "-q", DEVELOP)

    s.af("role", "revoke", "implementer", f"{SERVER_PREFIX}*")
    s.af("role", "revoke", "reviewer", f"{SERVER_PREFIX}{READ_TOOL}")
    expect(not list(agents.glob("project-*.md")), "revoking the last grants removes the project agents")


def small_task(s: Session, repo: Path) -> None:
    to_plan_step(s, "Tiny change", "small")
    expect("size: small" in s.af("status").stdout, "status shows the size")
    four = "".join(item(f"C{n}", f"Item {n}", "api", f"f{n}.txt") for n in range(1, 5))
    s.af("report", "--step", "plan", stdin=four)
    refused = s.af("task", "advance", "--result", "pass", ok=False)
    expect(refused.returncode == EXIT_GATE_FAILED and "at most 3" in refused.stdout + refused.stderr, "a small plan over 3 items is refused", refused.stdout + refused.stderr)
    s.af("report", "--step", "plan", stdin=item("C1", "Only item", "api", "tiny.txt"))
    passed = s.af("task", "advance", "--result", "pass")
    expect("step 'implement'" in passed.stdout and "wait for a person" not in passed.stdout, "the plan needs no approval in a small task", passed.stdout)
    (repo / "tiny.txt").write_text("tiny\n", encoding=ENCODING)
    s.git("add", "tiny.txt")
    s.af("commit", "add tiny file", "--item", "C1")
    s.af("task", "advance", "--result", "pass")  # implement
    s.af("task", "advance", "--result", "pass")  # test
    scan = s.af("scan")
    expect("semgrep: " in scan.stdout and "gitleaks: " in scan.stdout, "a small task still runs Gitleaks and Semgrep", scan.stdout)
    expect("trivy" not in scan.stdout, "a small task does not run Trivy", scan.stdout)
    s.af("task", "advance", "--result", "pass")  # security
    s.af("report", "--step", "review", stdin="# Review\nNo findings.\n\n## Đề xuất cập nhật hồ sơ\nkhông có\n")
    waiting = s.af("task", "advance", "--result", "pass")  # review
    expect("awaiting_approval" in waiting.stdout, "review of a small task still waits for a person", waiting.stdout)
    s.af("task", "approve")
    latest = sorted((repo / ".agentflow" / "tasks").glob("T-*/summary.md"))[-1].read_text(encoding=ENCODING)
    expect("- Size: small" in latest, "summary.md records the size", latest[:200])
    state = json.loads((repo / ".agentflow" / "state.json").read_text(encoding=ENCODING))
    expect(state["tasks"][-1]["size"] == "small" and state["tasks"][-1]["status"] == "done", "state.json records the size")


def main() -> int:
    if shutil.which(AGENTFLOW) is None or shutil.which("git") is None:
        print("git must be on PATH", file=sys.stderr)
        return 2
    base = Path(tempfile.mkdtemp(prefix="agentflow-modes-"))
    repo = base / "sample"
    repo.mkdir()
    os.environ["GIT_CEILING_DIRECTORIES"] = str(base)
    os.environ["AGENTFLOW_HOME"] = str(base / "user-home")  # nothing here may touch the real ~/.agentflow
    try:
        s = Session(repo)
        s.git("init", "-q", "-b", MAIN)
        for key, value in {"user.name": "Smoke", "user.email": "smoke@example.invalid", "commit.gpgsign": "false"}.items():
            s.git("config", key, value)
        (repo / "README.md").write_text("sample\n", encoding=ENCODING)
        s.git("add", "README.md")
        s.git("commit", "-q", "-m", "initial")
        s.git("switch", "-q", "-c", DEVELOP)
        s.af("init", "--workflow", str(WORKFLOW))
        tiers_and_layers(s)
        role_grants(s, repo)
        small_task(s, repo)
        print("\nmodes smoke test passed")
        return 0
    except Failure as exc:
        print(f"\nmodes smoke test FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(base, onerror=_make_writable_and_retry)


if __name__ == "__main__":
    sys.exit(main())
