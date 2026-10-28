"""stages.md, the script table of PLAN.md and the scripts/ folder must tell the same story.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
CORE = HERE.parent
STAGES = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")
PLAN = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")

# Scripts named in the plan that have no file yet (none left: phases 3A and 3B are written). Add a name here while its script is pending.
PENDING: set[str] = set()
NOT_A_GATE_STEP = {"guard_write.py"}  # the PreToolUse hook runs on every call, it is not a step of a gate
MODULES = {"idlist.py", "checkreport.py", "approvals.py"}  # imported by the scripts, never run on its own: neither a gate step nor a row of the script table
SCRIPT_NAME = re.compile(r"`([a-z_]+\.py)")


def existing() -> set[str]:
    return {p.name for p in HERE.glob("*.py") if not p.name.startswith("test_") and p.name not in MODULES}


def gate_script_lines() -> list[tuple[int, str]]:
    gate, found = None, []
    for line in STAGES.splitlines():
        match = re.match(r"## G(\d+)\.", line)
        if match:
            gate = int(match.group(1))
        if line.startswith("- **Script:**"):
            found.append((gate, line))
    return found


def test_every_script_named_in_stages_exists_or_is_a_known_pending_one():
    named = {name for _, line in gate_script_lines() for name in SCRIPT_NAME.findall(line)}
    assert named - existing() - PENDING == set(), "stages.md names a script that is neither written nor listed as pending"


def test_pending_scripts_do_not_exist_yet_and_the_list_is_current():
    assert existing() & PENDING == set(), "a pending script now exists: move it out of PENDING"


def test_every_written_script_is_used_by_a_gate_or_is_the_hook():
    named = {name for _, line in gate_script_lines() for name in SCRIPT_NAME.findall(line)}
    assert existing() - named - NOT_A_GATE_STEP == set()


def test_there_are_eleven_gates_each_with_a_script_line():
    assert [gate for gate, _ in gate_script_lines()] == list(range(11))


def test_check_scripts_run_from_the_gate_the_rules_section_says():
    first = {}
    for gate, line in gate_script_lines():
        for name in SCRIPT_NAME.findall(line):
            first.setdefault(name, gate)
    assert first["check_links.py"] == first["check_numbers.py"] == first["check_profile.py"] == 1
    assert first["check_versions.py"] == 4 and first["check_trace.py"] == 6 and first["calc_capacity.py"] == 1
    assert first["detect_models.py"] == 0 and first["init_workspace.py"] == 0


def test_every_gate_from_g4_runs_check_versions_and_the_reviewer_may_run_it():
    for gate, line in gate_script_lines():
        assert ("check_versions.py" in line) == (gate >= 4), (gate, line)
    permissions = (CORE / "workflow" / "permissions.md").read_text(encoding="utf-8")
    assert "check_versions" in permissions


def test_the_plan_table_lists_every_written_script():
    table = [line for line in PLAN.splitlines() if line.startswith("| `") and ".py" in line.split("|")[1]]
    in_table = {name for line in table for name in SCRIPT_NAME.findall(line.split("|")[1])}
    assert existing() - in_table == set()
    assert PENDING - in_table == set(), "the table must still list the scripts of phase 3B"
    # the script table has one row per script, none of them twice
    names = [SCRIPT_NAME.findall(line.split("|")[1])[0] for line in table]
    assert len(names) == len(set(names))


def test_the_plan_states_which_scripts_are_written_and_which_are_pending():
    status = next(line for line in PLAN.splitlines() if line.startswith("**Trạng thái dựng"))
    done, _, pending = status.partition("Chưa làm")
    for name in existing():
        assert f"`{name.removesuffix('.py')}" in done, name
    for name in PENDING:
        assert f"`{name}`" in pending, name
