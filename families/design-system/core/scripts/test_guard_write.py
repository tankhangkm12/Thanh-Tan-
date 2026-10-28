"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import guard_write as gw  # noqa: E402

SCRIPTS = Path(__file__).parent
CORE = SCRIPTS.parent
AGENTS = CORE / "claude" / "agents"

TASK = """# T-001: thử

- **Gate:** G1
- **Giao cho:** Designer
- **Trạng thái:** mở
- **Phụ thuộc:** không có

## Mô tả

Làm gì đó.
"""
DECISION = """# D-001

<!-- BEGIN:council (tally_votes.py sinh, không sửa tay) -->
Đề xuất: A
<!-- END:council -->

## Quyết định của người dùng

<!-- BEGIN:user (Orchestrator ghi, chỉ khi người dùng nói rõ theo ID) -->
chưa có
<!-- END:user -->
"""
TABLES = """# tables

Cột và lý do do Designer viết.

<!-- BEGIN:calc:orders -->
| cột | byte |
| --- | --- |
| id | 8 |
<!-- END:calc:orders -->

Ghi chú của Designer.
"""


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "proj" / ".agent-workspace"
    files = {
        "plan/tasks/T-001-thu.md": TASK,
        "plan/plan.md": "plan\n",
        "decisions/D-001-x/decision.md": DECISION,
        "drafts/07-data/databases/orders/tables.md": TABLES,
        "reviews/R-001-old.md": "báo cáo cũ\n",
        "state.md": "state\n",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return root


def call(ws: Path, agent: str, tool: str, rel: str | None = None, *, outside: str | None = None, **tool_input) -> str:
    path = outside if outside is not None else str(ws / rel)
    if tool != "Bash":
        tool_input["file_path"] = path
    data = {"agent_type": agent, "tool_name": tool, "tool_input": tool_input, "cwd": str(ws.parent)}
    try:
        gw.decide(data)
    except gw.Denied as reason:
        return f"deny: {reason}"
    return "allow"


def allowed(*args, **kwargs) -> bool:
    return call(*args, **kwargs) == "allow"


def shell_for(agent_type, tool: str, command: str, cwd: str = "") -> str:
    try:
        gw.decide({"agent_type": agent_type, "tool_name": tool, "tool_input": {"command": command}, "cwd": cwd})
    except gw.Denied as reason:
        return f"deny: {reason}"
    return "allow"


def shell(role: str, tool: str, command: str, cwd: str = "") -> str:
    return shell_for(f"design-core:{role}", tool, command, cwd)


def bash(role: str, command: str, cwd: str = "") -> str:
    return shell(role, "Bash", command, cwd)


def powershell(role: str, command: str, cwd: str = "") -> str:
    return shell(role, "PowerShell", command, cwd)


def agent(role: str) -> str:
    return f"design-core:{role}"


# --- who is checked -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("agent_type", ["", None, "Explore", "general-purpose", "reviewer", "other-plugin:reviewer", "design-core:unknown", "design-core:", "design-system:planner"])
def test_calls_without_a_design_core_agent_are_never_touched(ws, agent_type):
    assert allowed(ws, agent_type, "Write", "architecture/x.md", content="x", outside=str(ws.parent / "architecture" / "x.md"))
    assert allowed(ws, agent_type, "Write", "drafts/x.md", content="x")
    assert shell_for(agent_type, "Bash", "rm -rf /") == "allow"


def test_other_tools_are_not_checked(ws):
    assert allowed(ws, agent("reviewer"), "Read", "drafts/x.md")


# --- nobody writes outside .agent-workspace/ ------------------------------------------------------------------------------

@pytest.mark.parametrize("role", gw.ROLES)
def test_no_agent_writes_architecture_or_project_files(ws, role):
    for outside in (ws.parent / "architecture" / "README.md", ws.parent / "src" / "app.py", ws.parent / "CLAUDE.md"):
        assert "deny" in call(ws, agent(role), "Write", outside=str(outside), content="x")
        assert "deny" in call(ws, agent(role), "Edit", outside=str(outside), old_string="a", new_string="b")


def test_dotdot_cannot_climb_out_of_a_zone(ws):
    sneaky = str(ws / "inputs" / ".." / "drafts" / "x.md")
    assert "deny" in call(ws, agent("orchestrator"), "Write", outside=sneaky, content="x")
    assert "deny" in call(ws, agent("planner"), "Write", outside=str(ws / "plan" / ".." / "stack" / "x.md"), content="x")


def test_windows_paths_and_case(ws):
    win = str(ws / "state.md").replace("/", "\\").replace(".agent-workspace", ".AGENT-WORKSPACE")
    assert allowed(ws, agent("orchestrator"), "Write", outside=win, content="x")
    assert "deny" in call(ws, agent("orchestrator"), "Write", outside=win.replace("state.md", "drafts\\x.md"), content="x")


# --- Orchestrator -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["state.md", "models.md", "questions.md", "inputs/ba/brief.md", "decisions/decision-log.md", "risks/acceptance.md"])
def test_orchestrator_writes_its_files(ws, rel):
    assert allowed(ws, agent("orchestrator"), "Write", rel, content="x")


@pytest.mark.parametrize("rel", ["plan/plan.md", "stack/x.md", "capacity/assumptions.yaml", "drafts/00-context/glossary.md", "reviews/R-002-a.md",
                                 "checks/links.md", "decisions/D-001-x/tally.md", "decisions/D-001-x/brief.md", "decisions/D-001-x/votes/r1-fit-a.md"])
def test_orchestrator_cannot_write_other_zones(ws, rel):
    assert "deny" in call(ws, agent("orchestrator"), "Write", rel, content="x")


def test_orchestrator_may_change_only_the_status_line_of_a_task(ws):
    task = "plan/tasks/T-001-thu.md"
    assert allowed(ws, agent("orchestrator"), "Edit", task, old_string="**Trạng thái:** mở", new_string="**Trạng thái:** đang làm")
    assert allowed(ws, agent("orchestrator"), "Write", task, content=TASK.replace("Trạng thái:** mở", "Trạng thái:** đóng"))
    # any other line
    assert "deny" in call(ws, agent("orchestrator"), "Edit", task, old_string="Làm gì đó.", new_string="Làm việc khác.")
    assert "deny" in call(ws, agent("orchestrator"), "Edit", task, old_string="**Giao cho:** Designer", new_string="**Giao cho:** Reviewer")
    # status AND another line in one go
    assert "deny" in call(ws, agent("orchestrator"), "Write", task, content=TASK.replace("mở", "đóng").replace("Làm gì đó.", "Khác."))
    # extra line, fewer lines, status moved to a new line
    assert "deny" in call(ws, agent("orchestrator"), "Write", task, content=TASK + "\n- thêm\n")
    assert "deny" in call(ws, agent("orchestrator"), "Write", task, content=TASK.replace("- **Phụ thuộc:** không có\n", ""))
    assert "deny" in call(ws, agent("orchestrator"), "Edit", task, old_string="- **Gate:** G1", new_string="- **Trạng thái:** x")
    # cannot make a task file
    assert "deny" in call(ws, agent("orchestrator"), "Write", "plan/tasks/T-009-new.md", content=TASK)


def test_status_line_rule_survives_unicode_normalisation(ws):
    import unicodedata

    task = "plan/tasks/T-001-thu.md"
    decomposed = unicodedata.normalize("NFD", "**Trạng thái:** đóng")
    assert allowed(ws, agent("orchestrator"), "Edit", task, old_string="**Trạng thái:** mở", new_string=decomposed)


def test_orchestrator_may_write_only_the_user_block_of_decision_md(ws):
    decision = "decisions/D-001-x/decision.md"
    assert allowed(ws, agent("orchestrator"), "Edit", decision, old_string="chưa có", new_string="D-001: chọn A (2026-10-12)")
    assert "deny" in call(ws, agent("orchestrator"), "Edit", decision, old_string="Đề xuất: A", new_string="Đề xuất: B")
    assert "deny" in call(ws, agent("orchestrator"), "Edit", decision, old_string="<!-- END:user -->", new_string="")
    assert "deny" in call(ws, agent("orchestrator"), "Write", decision, content="# viết lại hết\n")
    assert "deny" in call(ws, agent("orchestrator"), "Write", "decisions/D-002-y/decision.md", content=DECISION)


# --- Planner, Researcher, Designer -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role,rel,ok", [
    ("planner", "plan/plan.md", True), ("planner", "plan/tasks/T-002-x.md", True), ("planner", "questions.md", True),
    ("planner", "drafts/00-context/project-profile.md", True),
    ("planner", "drafts/00-context/glossary.md", False), ("planner", "state.md", False), ("planner", "models.md", False),
    ("planner", "stack/x.md", False), ("planner", "inputs/ba/x.md", False), ("planner", "capacity/assumptions.yaml", False),
    ("researcher", "stack/layers/db/longlist.md", True), ("researcher", "stack/cross-check.md", True),
    ("researcher", "capacity/db-constants/postgresql-16.yaml", True), ("researcher", "capacity/db-constants/sub/x.yaml", False),
    ("researcher", "capacity/assumptions.yaml", False), ("researcher", "capacity/pricing.yaml", False), ("researcher", "capacity/db-constants/readme.md", False),
    ("designer", "capacity/db-constants/postgresql-16.yaml", False), ("designer", "capacity/tables.yaml", True),
    ("planner", "capacity/db-constants/postgresql-16.yaml", False), ("orchestrator", "capacity/db-constants/postgresql-16.yaml", False),
    ("reviewer", "capacity/db-constants/postgresql-16.yaml", False),
    ("researcher", "drafts/x.md", False), ("researcher", "decisions/D-001-x/brief.md", False), ("researcher", "state.md", False),
    ("researcher", "plan/plan.md", False), ("researcher", "reviews/R-005-x.md", False),
    ("designer", "decisions/D-001-x/brief.md", True), ("designer", "drafts/05-frontend/overview.md", True),
    ("designer", "capacity/assumptions.yaml", True), ("designer", "questions.md", True), ("designer", "stack/criteria-draft.md", False), ("designer", "drafts/02-tech-stack/selection-criteria.md", True),
    ("designer", "stack/layers/db/longlist.md", False), ("designer", "stack/cross-check.md", False),
    ("designer", "reviews/R-005-x.md", False), ("designer", "decisions/D-001-x/votes/r1-fit-a.md", False),
    ("designer", "decisions/D-001-x/tally.md", False), ("designer", "decisions/D-001-x/decision.md", False),
    ("designer", "plan/plan.md", False), ("designer", "state.md", False), ("designer", "models.md", False),
    ("designer", "inputs/ba/x.md", False), ("designer", "risks/acceptance.md", False), ("designer", "checks/x.md", False),
    ("designer", "drafts/00-context/assumptions.md", False), ("designer", "drafts/03-capacity/data-sizing.md", False),
])
def test_zone_table(ws, role, rel, ok):
    assert allowed(ws, agent(role), "Write", rel, content="x") is ok, rel


def test_designer_keeps_out_of_the_calc_blocks_of_tables_md(ws):
    tables = "drafts/07-data/databases/orders/tables.md"
    assert allowed(ws, agent("designer"), "Edit", tables, old_string="Ghi chú của Designer.", new_string="Ghi chú mới.")
    assert allowed(ws, agent("designer"), "Write", tables, content=TABLES.replace("Cột và lý do do Designer viết.", "Khác."))
    assert "deny" in call(ws, agent("designer"), "Edit", tables, old_string="| id | 8 |", new_string="| id | 4 |")
    assert "deny" in call(ws, agent("designer"), "Write", tables, content="# tables\n")  # block gone
    assert "deny" in call(ws, agent("designer"), "Edit", tables, old_string="<!-- END:calc:orders -->", new_string="")
    assert "deny" in call(ws, agent("designer"), "Write", "drafts/07-data/databases/new/tables.md",
                          content="<!-- BEGIN:calc:t -->\nx\n<!-- END:calc:t -->\n")  # cannot forge a block
    assert allowed(ws, agent("designer"), "Write", "drafts/07-data/databases/new/tables.md", content="# mới\n")


PENDING_TABLES = "# tables\n\nGhi chú.\n\n<!-- BEGIN:calc:items -->\nchờ script\n<!-- END:calc:items -->\n"


def test_designer_may_add_and_remove_an_empty_calc_block_marked_cho_script(ws):
    tables = "drafts/07-data/databases/orders/tables.md"
    new = "drafts/07-data/databases/billing/tables.md"
    for pending in ("chờ script", "<!-- chờ script -->", "  Chờ Script  "):
        content = f"# t\n\n<!-- BEGIN:calc:items -->\n{pending}\n<!-- END:calc:items -->\n"
        assert allowed(ws, agent("designer"), "Write", new, content=content), pending
    # next to a filled block, a second (pending) pair may be added
    assert allowed(ws, agent("designer"), "Edit", tables, old_string="Ghi chú của Designer.", new_string="Ghi chú.\n\n<!-- BEGIN:calc:items -->\nchờ script\n<!-- END:calc:items -->")
    # and a pending pair that is already in the file may be removed
    path = ws / "drafts/07-data/databases/billing/tables.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PENDING_TABLES, encoding="utf-8")
    assert allowed(ws, agent("designer"), "Write", new, content="# tables\n\nGhi chú.\n")
    # never a filled block: add, change or remove
    assert "deny" in call(ws, agent("designer"), "Write", new, content=PENDING_TABLES.replace("chờ script", "| a | 1 |"))
    assert "deny" in call(ws, agent("designer"), "Edit", new, old_string="chờ script", new_string="| a | 1 |")
    assert "deny" in call(ws, agent("designer"), "Edit", tables, old_string="| id | 8 |", new_string="chờ script")
    assert "deny" in call(ws, agent("designer"), "Write", tables, content="# tables\n")  # a filled block removed
    # a pending block renamed is still only an empty pair; a duplicate name or a lone marker is not allowed
    assert "deny" in call(ws, agent("designer"), "Write", new, content=PENDING_TABLES + PENDING_TABLES)
    assert "deny" in call(ws, agent("designer"), "Write", new, content=PENDING_TABLES.replace("<!-- END:calc:items -->", ""))


# --- Reviewer ------------------------------------------------------------------------------------------------------------------

def test_reviewer_only_creates_new_report_files(ws):
    assert allowed(ws, agent("reviewer"), "Write", "reviews/R-002-context.md", content="x")
    assert "deny" in call(ws, agent("reviewer"), "Write", "reviews/R-001-old.md", content="x")  # exists
    assert "deny" in call(ws, agent("reviewer"), "Edit", "reviews/R-001-old.md", old_string="cũ", new_string="mới")
    assert "deny" in call(ws, agent("reviewer"), "Edit", "reviews/R-009-new.md", old_string="a", new_string="b")
    for rel in ("reviews/notes.md", "reviews/sub/R-003-x.md", "reviews/R-xxx-x.md", "drafts/00-context/glossary.md", "state.md", "checks/x.md"):
        assert "deny" in call(ws, agent("reviewer"), "Write", rel, content="x"), rel


# --- Council -------------------------------------------------------------------------------------------------------------------

def test_council_member_writes_only_its_own_vote(ws):
    fit = agent("council-fit")
    assert allowed(ws, fit, "Write", "decisions/D-001-x/votes/r1-fit-sonnet.md", content="x")
    assert allowed(ws, fit, "Write", "decisions/D-002-y/votes/r2-fit-haiku.md", content="x")
    for rel in ("decisions/D-001-x/votes/r1-cost-ops-sonnet.md", "decisions/D-001-x/votes/r1-summary.md", "decisions/D-001-x/votes/r3-fit-a.md",
                "decisions/D-001-x/brief.md", "decisions/D-001-x/tally.md", "drafts/x.md", "state.md", "decisions/D-001-x/votes/sub/r1-fit-a.md"):
        assert "deny" in call(ws, fit, "Write", rel, content="x"), rel
    assert allowed(ws, agent("council-cost-ops"), "Write", "decisions/D-001-x/votes/r1-cost-ops-a.md", content="x")
    assert "deny" in call(ws, agent("council-cost-ops"), "Write", "decisions/D-001-x/votes/r1-fit-a.md", content="x")


# --- Bash ----------------------------------------------------------------------------------------------------------------------

THIS = str(SCRIPTS)


@pytest.mark.parametrize("command", [
    'uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py" --workspace .agent-workspace',
    "uv run $CLAUDE_PLUGIN_ROOT/scripts/check_numbers.py",
    "uv run --with pyyaml ${CLAUDE_PLUGIN_ROOT}/scripts/check_profile.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_trace.py",
    'uv run "${CLAUDE_PLUGIN_ROOT}/scripts/calc_capacity.py" --check',
    f'uv run "{THIS}/check_versions.py"',
    'uv run "' + THIS.replace("/", "\\") + '\\check_workspace.py" --workspace x',
    "cat drafts/x.md", "head -20 drafts/x.md | grep -n foo", "ls -la && pwd", "grep -rn 'a > b' drafts", "rg TODO drafts",
    "git status", "git diff HEAD~1", "cd .agent-workspace && uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py",
    'uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py 2>&1',
    "find . -name '*.md'", "wc -l a.md; wc -l b.md",
])
def test_reviewer_bash_allowed(command):
    assert bash("reviewer", command) == "allow", command


@pytest.mark.parametrize("command", [
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/promote_drafts.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/archive_release.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/tally_votes.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/init_workspace.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/detect_models.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/calc_capacity.py",  # writes drafts/ without --check
    "uv run /tmp/evil/scripts/check_links.py",
    "uv run ./check_links.py",
    "uv run check_links.py",  # not under the plugin's scripts/
    "uv run python -c 'open(1)'", "uv run --with pytest pytest", "uv run", "uv run --with",
    "python check_links.py", "bash -c 'rm x'", "sh x.sh", "node x.js", "curl http://x", "pip install x",
    "rm -rf drafts", "rm a.md", "mv a b", "cp a b", "touch a", "mkdir x", "tee a", "sed -i s/a/b/ a.md", "awk '{print}' a", "sort -o a b",
    "cat a > b", "cat a >> b", "echo x > drafts/a.md", "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py > out.txt",
    "cat < a", "echo $(rm a)", "echo `rm a`", 'echo "$(rm a)"', "ls & rm a", "ls; rm a", "ls && rm a", "ls || rm a", "ls | tee a", "ls\nrm a",
    "find . -delete", "find . -exec rm {} ;", "find . -fprint out", "git commit -m x", "git add .", "git checkout .", "git diff --output=x",
    "git reset --hard", "git", "git push", "dd if=a of=b", "powershell -c x", "Remove-Item a",
])
def test_reviewer_bash_blocked(command):
    assert bash("reviewer", command).startswith("deny"), command


def test_reviewer_bash_accepts_the_expanded_plugin_root_as_claude_code_sends_it():
    # Observed with claude -p: the hook sees ${CLAUDE_PLUGIN_ROOT} already expanded, with forward slashes, even on Windows.
    assert bash("reviewer", f'uv run "{Path(THIS).as_posix()}/check_links.py" --workspace x') == "allow"
    assert bash("reviewer", f'uv run "{Path(THIS).as_posix()}/../scripts/check_links.py"') == "allow"
    assert bash("reviewer", f'uv run "{Path(THIS).as_posix()}/../promote_drafts.py"').startswith("deny")


def test_reviewer_bash_relative_script_path_is_blocked_even_from_inside_the_scripts_folder(monkeypatch):
    monkeypatch.chdir(SCRIPTS)
    for command in ("uv run ./check_links.py", "uv run check_links.py", "uv run scripts/check_links.py"):
        assert bash("reviewer", command).startswith("deny"), command


def test_reviewer_bash_script_from_a_foreign_folder_is_blocked_even_with_the_right_name(tmp_path):
    assert bash("reviewer", f'uv run "{tmp_path}/check_links.py"').startswith("deny")
    assert bash("reviewer", f'uv run "{THIS}/check_links.py"') == "allow"


@pytest.mark.parametrize("role", ["planner", "researcher", "designer"] + ["council-" + p for p in gw.COUNCIL])
def test_agents_without_bash_are_blocked_from_it(role):
    assert bash(role, "ls").startswith("deny")


def test_every_agent_with_a_shell_tool_has_a_shell_policy_and_the_rest_are_blocked():
    """Agent files and the guard agree: Bash only for the Orchestrator and the Reviewer; nobody has PowerShell."""
    for path in sorted(AGENTS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        tools = [t.strip() for t in next(line for line in text.splitlines() if line.startswith("tools:")).split(":", 1)[1].split(",")]
        role = next(line for line in text.splitlines() if line.startswith("name:")).split(":", 1)[1].strip()
        assert role in gw.ROLES
        assert ("Bash" in tools) is (role in ("orchestrator", "reviewer")), role
        assert "PowerShell" not in tools, role  # no agent has it; the PowerShell rules are a back-up layer
        assert (role in gw.SHELL_POLICY) is bool({"Bash", "PowerShell"} & set(tools)), role
        for tool in gw.SHELLS:
            if role not in gw.SHELL_POLICY:
                assert shell(role, tool, "ls").startswith("deny"), (role, tool)
            assert shell(role, tool, "rm -rf x" if tool == "Bash" else "Remove-Item x").startswith("deny"), (role, tool)


ORCH_SCRIPT_NAMES = ["promote_drafts.py", "archive_release.py", "tally_votes.py", "init_workspace.py", "detect_models.py", "call_council_cli.py",
                     "calc_capacity.py", "check_links.py", "check_workspace.py"]


@pytest.mark.parametrize("name", ORCH_SCRIPT_NAMES)
def test_orchestrator_may_uv_run_every_script_of_the_family(name):
    assert bash("orchestrator", f"uv run ${{CLAUDE_PLUGIN_ROOT}}/scripts/{name} --workspace .agent-workspace") == "allow"
    assert bash("orchestrator", f'uv run --with pyyaml "{Path(THIS).as_posix()}/{name}"') == "allow"
    assert powershell("orchestrator", f'uv run "{Path(THIS).as_posix()}/{name}" --workspace .agent-workspace') == "allow"
    assert powershell("orchestrator", f'uv run "{THIS}\\{name}"') == "allow"


@pytest.mark.parametrize("command", [
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/guard_write.py", "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/test_guard_write.py",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/evil.py", "uv run /tmp/scripts/promote_drafts.py", "uv run promote_drafts.py",
    "uv run python -c 'print(1)'", "uv run --with pytest pytest", "uv run",
    "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py && rm -rf drafts", "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/promote_drafts.py > log.txt",
])
def test_orchestrator_uv_run_is_limited_to_the_family_scripts(command):
    assert bash("orchestrator", command).startswith("deny"), command


@pytest.mark.parametrize("command", [
    "date", "date +%F", "date -I", "date -u +%Y-%m-%d", "date --iso-8601=seconds", "date -R",
    "cat state.md", "ls -la .agent-workspace", "grep -rn TODO .agent-workspace/drafts", "git status", "git log", "pwd",
    "cp notes.md .agent-workspace/inputs/ba/", "cp -r docs .agent-workspace/inputs/ba/docs", "cp -rv a b .agent-workspace/inputs/ba",
    "cp a.md .agent-workspace/inputs/ui-design/a.md", "cp a.md inputs/ba/../ba/a.md".replace("inputs", ".agent-workspace/inputs"),
    "cd .agent-workspace && cp /tmp/a.md inputs/ba/", "cd .agent-workspace/inputs && cp /tmp/a.md ba/",
    "date; cp a .agent-workspace/inputs/ba/", "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py 2>&1",
])
def test_orchestrator_bash_allowed(command, ws):
    assert shell("orchestrator", "Bash", command, cwd=str(ws.parent)) == "allow", command


@pytest.mark.parametrize("command", [
    "rm -rf drafts", "rm a", "mv a b", "touch a", "mkdir x", "tee a", "sed -i s/a/b/ a.md", "python x.py", "bash -c ls", "curl http://x",
    "echo x > state.md", "echo x >> .agent-workspace/state.md", "cat a > b", "cat < a", "echo $(date)", "echo `date`", "ls & rm a", "ls; rm a",
    "git commit -m x", "git add .", "git push", "git checkout .", "git reset --hard", "git diff --output=x",
    "date -s 12:00", "date --set=2026-01-01", "date 101200002026", "date -d tomorrow",
    "cp a .agent-workspace/state.md", "cp a .agent-workspace/drafts/x.md", "cp a .agent-workspace/", "cp a .agent-workspace", "cp a .",
    "cp a ../x/", "cp a /tmp/", "cp a .agent-workspace/inputs/../drafts/x.md", "cp a .agent-workspace/plan/", "cp a .agent-workspace/stack/layers/",
    "cp -t .agent-workspace/inputs a", "cp --target-directory=.agent-workspace/inputs a", "cp a", "cp", "cp -l a .agent-workspace/inputs/b",
    "cp a ~/x", "cp a $HOME/x", "cp a .agent-workspace/inputs/*", "cp a .agent-workspace/inputs/ba/ && rm a",
    "cd /tmp && cp a x/", "cd - && cp a .agent-workspace/inputs/ba/", "cd $HOME && cp a .agent-workspace/inputs/", "cd .. && cp a .agent-workspace/inputs/",
    "ln -s a .agent-workspace/inputs/b", "install a .agent-workspace/inputs/b", "rsync a .agent-workspace/inputs/", "dd if=a of=.agent-workspace/inputs/b",
    "xcopy a .agent-workspace\\inputs\\", "powershell -c x", "cmd /c copy a b",
])
def test_orchestrator_bash_blocked(command, ws):
    assert shell("orchestrator", "Bash", command, cwd=str(ws.parent)).startswith("deny"), command


def test_orchestrator_copy_needs_a_known_current_folder_for_a_relative_target():
    assert shell("orchestrator", "Bash", "cp a .agent-workspace/inputs/ba/").startswith("deny")  # no cwd in the hook data
    assert shell("orchestrator", "Bash", "cp a /p/.agent-workspace/inputs/ba/") == "allow"
    assert shell("orchestrator", "Bash", "cp a C:/p/.agent-workspace/inputs/ba/") == "allow"
    assert shell("orchestrator", "Bash", "cp a C:/p/.agent-workspace/drafts/x") .startswith("deny")


def test_other_roles_cannot_use_date_or_copy():
    for role in ("reviewer",):
        assert bash(role, "date").startswith("deny")
        assert shell(role, "Bash", "cp a .agent-workspace/inputs/ba/", cwd="/p").startswith("deny")
        assert powershell(role, "Get-Date").startswith("deny")
        assert powershell(role, "Copy-Item a .agent-workspace/inputs/ba/", cwd="/p").startswith("deny")


# --- PowerShell tool (tool_name "PowerShell", tool_input.command: observed with claude -p) -------------------------------------

@pytest.mark.parametrize("command", [
    "Get-Date", "Get-Date -Format yyyy-MM-dd", "Get-Date -UFormat %F",
    "Get-Content drafts/x.md", "Get-Content drafts/x.md | Select-String foo", "gc drafts\\x.md | select -First 3",
    "Get-ChildItem -Recurse .agent-workspace | Select-Object -First 5", "ls .agent-workspace", "dir", "Test-Path state.md",
    "Get-ChildItem .agent-workspace | Measure-Object", "Select-String -Path 'drafts/*.md' -Pattern foo", "Get-Location", "Set-Location .agent-workspace",
    "git status", "git log", "rg TODO drafts", "Get-Content a 2>&1",
    "Copy-Item a.md .agent-workspace/inputs/ba/", "Copy-Item -Path a.md -Destination .agent-workspace\\inputs\\ba\\ -Recurse -Force",
    "copy a.md .agent-workspace\\inputs\\ba\\a.md", "cp a.md .agent-workspace/inputs/ba/", "Copy-Item -Recurse docs .agent-workspace/inputs/ba/docs",
    'Copy-Item "a b.md" ".agent-workspace\\inputs\\ba\\"', "Set-Location .agent-workspace; Copy-Item /tmp/a.md inputs/ba/",
    "Get-Date; Copy-Item a.md .agent-workspace/inputs/ba/",
    f'uv run "{Path(THIS).as_posix()}/check_links.py"',
])
def test_orchestrator_powershell_allowed(command, ws):
    assert powershell("orchestrator", command, cwd=str(ws.parent)) == "allow", command


@pytest.mark.parametrize("command", [
    "Set-Content x.md 'a'", "Set-Content -Path .agent-workspace/state.md -Value a", "sc x a", "Add-Content x.md a", "ac x a",
    "Out-File x.md", "Get-Date | Out-File x", "Get-Content a | Set-Content b", "Get-Content a | Out-File b", "Get-Content a | Tee-Object b", "Tee-Object x",
    "Remove-Item x", "rm x", "del x", "ri x", "rd x", "Remove-Item -Recurse .agent-workspace", "Get-ChildItem | Remove-Item",
    "Move-Item a b", "mv a b", "move a b", "mi a b", "Rename-Item a b", "ren a b", "New-Item x.md", "ni x", "mkdir x", "md x", "New-Item -ItemType Directory x",
    "Clear-Content x", "Set-Item x 1", "Export-Csv x", "Set-Date 2026-01-01", "Out-File -FilePath .agent-workspace/state.md",
    "echo x > state.md", "echo x >> state.md", "Get-Content a > b", "Get-Content < a", "Get-Date -Format x > f", "Write-Output a 1> f",
    "Copy-Item a .agent-workspace/state.md", "Copy-Item a .agent-workspace/drafts/", "Copy-Item a .agent-workspace", "Copy-Item a ..\\x", "Copy-Item a /tmp",
    "Copy-Item -Path a -Destination .agent-workspace/drafts/x", "Copy-Item a .agent-workspace/inputs/../drafts/", "Copy-Item a", "Copy-Item",
    "Copy-Item a b c", "Copy-Item -Path a", "Copy-Item a b -Exclude *.md", "Copy-Item a b -Filter x", "Copy-Item a b -Confirm:$false",
    "Copy-Item a .agent-workspace/inputs/*", "Copy-Item a $env:TEMP", "Copy-Item a ~\\x", "Copy-Item a b -ToSession x",
    "Set-Location /tmp; Copy-Item a .agent-workspace/inputs/", "Set-Location $env:TEMP; Copy-Item a .agent-workspace/inputs/ba/",
    "[IO.File]::WriteAllText('x','y')", "[System.IO.File]::Delete('x')", "Invoke-Expression 'ls'", "iex ls", "Start-Process x", "start x",
    "Invoke-WebRequest http://x", "iwr http://x", "Get-Process", "Stop-Process -Id 1", "python x.py", "pwsh -c ls", "powershell -c ls", "cmd /c dir",
    "& uv run x", "& 'C:\\x.exe'", "$x = 1", "Get-Content $env:APPDATA", 'Get-Content "$env:APPDATA"', "Get-Content `a",
    "Get-Content (Get-Content a)", "Get-ChildItem | ForEach-Object { Remove-Item $_ }", "@('a') | Set-Content b", "Get-Content a; Remove-Item a",
    "Get-Content a | Remove-Item", "Get-Content a && Remove-Item a", "ls\nRemove-Item a", "ls\r\nrm a", "ls 'a",
    "git commit -m x", "git add .", "git push", "uv run python -c 1", "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/evil.py", "uv run /tmp/promote_drafts.py",
    "xcopy a .agent-workspace\\inputs\\", "robocopy a .agent-workspace\\inputs\\", "Compress-Archive a b", "Expand-Archive a b",
])
def test_orchestrator_powershell_blocked(command, ws):
    assert powershell("orchestrator", command, cwd=str(ws.parent)).startswith("deny"), command


@pytest.mark.parametrize("command", [
    "Get-Content drafts/x.md", "Get-ChildItem drafts | Select-String foo", "git status",
    f'uv run "{Path(THIS).as_posix()}/check_trace.py"',
])
def test_reviewer_powershell_read_only_and_check_scripts(command):
    assert powershell("reviewer", command) == "allow", command


@pytest.mark.parametrize("command", [
    "Set-Content x a", "Out-File x", "Remove-Item x", "Copy-Item a b", "Get-Content a > b", "Get-Date",
    f'uv run "{Path(THIS).as_posix()}/promote_drafts.py"', f'uv run "{Path(THIS).as_posix()}/calc_capacity.py"', "Invoke-Expression ls",
])
def test_reviewer_powershell_blocked(command):
    assert powershell("reviewer", command).startswith("deny"), command


@pytest.mark.parametrize("role", ["planner", "researcher", "designer"] + ["council-" + p for p in gw.COUNCIL])
def test_agents_without_a_shell_are_blocked_from_powershell_too(role):
    assert powershell(role, "Get-Date").startswith("deny")
    assert powershell(role, "Get-Content x").startswith("deny")


def test_non_design_core_agents_may_use_powershell():
    for agent_type in ("", "Explore", "other-plugin:reviewer"):
        assert shell_for(agent_type, "PowerShell", "Remove-Item x") == "allow"


# --- the hook as Claude Code runs it ---------------------------------------------------------------------------------------------

def run_hook(payload) -> subprocess.CompletedProcess:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(SCRIPTS / "guard_write.py")], input=text, capture_output=True, text=True, encoding="utf-8")


def test_exit_2_and_message_when_blocked(ws):
    result = run_hook({"agent_type": "design-core:designer", "tool_name": "Write", "cwd": str(ws.parent),
                       "tool_input": {"file_path": str(ws / "state.md"), "content": "x"}})
    assert result.returncode == 2
    assert "state.md" in result.stderr and "design-core:designer" in result.stderr and result.stdout == ""


def test_exit_0_when_allowed_or_not_ours(ws):
    ok = {"agent_type": "design-core:designer", "tool_name": "Write", "tool_input": {"file_path": str(ws / "drafts" / "a.md"), "content": "x"}}
    assert run_hook(ok).returncode == 0
    assert run_hook({"tool_name": "Write", "tool_input": {"file_path": "C:/anywhere/x", "content": "x"}}).returncode == 0
    assert run_hook({"session_id": "s", "hook_event_name": "PreToolUse"}).returncode == 0


def test_unreadable_input_is_a_visible_non_blocking_error():
    for bad in ("", "not json", "[1, 2]"):
        result = run_hook(bad)
        assert result.returncode == 1 and "guard_write" in result.stderr, bad


def test_relative_file_path_is_resolved_against_cwd(ws):
    result = run_hook({"agent_type": "design-core:designer", "tool_name": "Write", "cwd": str(ws.parent),
                       "tool_input": {"file_path": ".agent-workspace/state.md", "content": "x"}})
    assert result.returncode == 2


def test_hooks_json_wires_the_script():
    config = json.loads((CORE / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    (entry,) = config["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Write|Edit|Bash|PowerShell"
    (hook,) = entry["hooks"]
    assert hook["type"] == "command" and hook["command"] == "uv"
    script = [a for a in hook["args"] if a.endswith("guard_write.py")]
    assert script and script[0].startswith("${CLAUDE_PLUGIN_ROOT}/scripts/")
    assert (CORE / script[0].removeprefix("${CLAUDE_PLUGIN_ROOT}/")).is_file()


# --- spikes: the spec is the Designer's, the result is only run_spike.py's --------------------------------------------------------

SPIKE_SPEC = "stack/layers/data/spikes/S-02-pg-version.md"
SPIKE_RESULT = "stack/layers/data/spikes/S-02-pg-version.result.md"


@pytest.mark.parametrize("role, rel, ok", [
    ("designer", SPIKE_SPEC, True), ("designer", "stack/layers/messaging/spikes/S-10-queue.md", True),
    ("designer", SPIKE_RESULT, False), ("designer", "stack/layers/data/spikes/S-02-pg-version.RESULT.MD", False),
    ("designer", "stack/layers/data/spikes/S-02.result.md", False),
    ("designer", "stack/layers/data/spikes/notes.md", False), ("designer", "stack/layers/data/spikes/sub/S-02-x.md", False),
    ("designer", "stack/layers/data/S-02-x.md", False), ("designer", "stack/layers/data/longlist.md", False), ("designer", "stack/S-02-x.md", False),
    ("researcher", SPIKE_RESULT, False), ("researcher", "stack/layers/messaging/spikes/S-10-queue.result.md", False),
    ("researcher", SPIKE_SPEC, True), ("researcher", "stack/layers/data/longlist.md", True),
    ("planner", SPIKE_SPEC, False), ("planner", SPIKE_RESULT, False), ("orchestrator", SPIKE_SPEC, False), ("orchestrator", SPIKE_RESULT, False),
    ("council-fit", SPIKE_SPEC, False), ("reviewer", SPIKE_RESULT, False),
])
def test_spike_zones(ws, role, rel, ok):
    assert allowed(ws, agent(role), "Write", rel, content="x") is ok, (role, rel)


def test_nobody_edits_a_spike_result_not_even_to_fix_a_typo(ws):
    put = ws / SPIKE_RESULT
    put.parent.mkdir(parents=True, exist_ok=True)
    put.write_text("---\nresult: đạt\n---\n", encoding="utf-8")
    for role in ("designer", "researcher"):
        assert "deny" in call(ws, agent(role), "Edit", SPIKE_RESULT, old_string="đạt", new_string="không đạt"), role
        assert "deny" in call(ws, agent(role), "Write", SPIKE_RESULT, content="---\nresult: đạt\n---\nx"), role
    (ws / SPIKE_SPEC).write_text("spec x\n", encoding="utf-8")
    assert allowed(ws, agent("designer"), "Edit", SPIKE_SPEC, old_string="x", new_string="y")  # the spec itself is the Designer's


def test_the_orchestrator_runs_run_spike_and_nobody_else_does():
    command = 'uv run "${CLAUDE_PLUGIN_ROOT}/scripts/run_spike.py" --spike S-02 --show'
    assert shell("orchestrator", "Bash", command) == "allow"
    assert shell("orchestrator", "Bash", 'uv run "${CLAUDE_PLUGIN_ROOT}/scripts/run_spike.py" --spike S-02') == "allow"
    assert shell("reviewer", "Bash", command).startswith("deny")      # it starts containers: never a check script
    assert shell("designer", "Bash", command).startswith("deny")
    assert shell("orchestrator", "Bash", 'uv run "${CLAUDE_PLUGIN_ROOT}/scripts/run_spike.py" --spike S-02 > state.md').startswith("deny")
    assert shell("orchestrator", "Bash", "docker run --rm alpine sh").startswith("deny")  # no container except through the script
    assert shell("orchestrator", "Bash", "podman run --rm alpine sh").startswith("deny")
