"""Chặng E-spec (workflow, prompts, skills, documents): tests come first, and the documents say how.

The real `core/workflow.yaml` gets the step `test-spec` between `plan` and `implement` (role tester, needs a person, even
for a small task, gate `test-spec-valid`, back to `plan` when it fails) and the gate `tests-pass` on `test`. The tester,
planner and implementer prompts, the skills, USAGE, README, architecture, CHANGELOG and the dev-backend README describe it.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / build.DEFAULT_PLUGIN
USAGE = REPO / "families" / "software-dev" / "USAGE.md"
ARCHITECTURE = REPO / "docs" / "architecture.md"
README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"
BACKEND_README = REPO / "families" / "software-dev" / "backend" / "README.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def workflow() -> dict:
    return yaml.safe_load(read(CORE / "workflow.yaml"))


def step(name: str) -> dict:
    return next(s for s in workflow()["steps"] if s["id"] == name)


def role(name: str) -> str:
    return read(CORE / build.ROLES_DIR / f"{name}.md")


def skill(name: str) -> str:
    return read(CORE / "skills" / name / "SKILL.md")


def section(text: str, heading: str) -> str:
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    assert found, f"no '## {heading}' section"
    return found.group(1)


# ------------------------------------------------------------------ the workflow


def test_test_spec_sits_between_plan_and_implement():
    ids = [s["id"] for s in workflow()["steps"]]
    assert ids.index("plan") + 1 == ids.index("test-spec") and ids.index("test-spec") + 1 == ids.index("implement")


def test_test_spec_is_done_by_the_tester_and_needs_a_person():
    spec = step("test-spec")
    assert spec["role"] == "tester" and spec["requires_approval"] is True
    assert "test-spec-valid" in spec["gates"] and spec["on_fail"] == "plan"


def test_test_spec_has_a_checklist_with_the_lines_agentflow_adds():
    spec = step("test-spec")
    assert len(spec["approval_checklist"]) >= 4
    assert "spec-items" in spec["approval_items"]
    joined = " ".join(spec["approval_checklist"]).lower()
    for needle in ("done-when", "không có", "lý do"):
        assert needle in joined, needle


def test_a_small_task_does_not_skip_the_approval_of_test_spec():
    profiles = workflow()["sizes"]["profiles"]
    assert all("test-spec" not in p.get("skip_approval", []) for p in profiles.values())


def test_the_test_step_has_the_tests_pass_gate_and_goes_back_to_implement():
    test = step("test")
    assert "tests-pass" in test["gates"] and test["on_fail"] == "implement"


def test_the_generated_checklist_block_of_usage_includes_test_spec():
    assert "`test-spec`" in build.checklists_block(CORE)
    assert build.check(CORE) == []


# ------------------------------------------------------------------ the tester


@pytest.mark.parametrize(
    "needle",
    [
        "test-spec",
        "- tests:",
        "- command:",
        "- red: fail",
        "- reason:",
        "- output:",
        "không có —",
        "agentflow tests verify-red",
        "agentflow commit",
    ],
)
def test_the_tester_writes_the_test_spec_report_in_the_agreed_form(needle):
    assert needle in role("tester")


def test_the_tester_proves_the_tests_fail_for_the_right_reason():
    text = role("tester")
    assert re.search(r"not (a )?(syntax|import|typo)|feature (is )?(missing|not there)|reason", text, flags=re.I)
    assert re.search(r"runs? (the )?commands? (again|itself)|agentflow runs", text, flags=re.I)


def test_the_tester_never_writes_application_code_in_either_step():
    text = role("tester")
    assert "test directories" in text and re.search(r"never (edit|change|write).{0,40}application code", text, flags=re.I)


def test_the_tester_does_not_report_the_test_step_as_passed_on_its_own_word():
    text = role("tester")
    assert re.search(r"agentflow runs the (project's )?test command", text, flags=re.I)
    assert "tests-pass" in text


def test_the_tester_makes_every_command_name_a_test_file_of_its_item():
    text = role("tester")
    assert re.search(r"command.{0,120}(name|mention).{0,60}(test file|file)", text, flags=re.I | re.S)
    assert re.search(r"(not|never|no).{0,40}(false|exit 1)", text, flags=re.I) or "`false`" in text


def test_the_tester_knows_the_commands_run_again_at_the_test_step_and_must_pass():
    text = role("tester")
    assert re.search(r"(run|runs) again.{0,200}(green|pass|exit 0)|green after|red before", text, flags=re.I | re.S)


def test_the_tester_does_not_force_a_test_where_none_can_be_written():
    text = role("tester")
    assert re.search(r"do not (force|invent|write).{0,60}test", text, flags=re.I) or "không có —" in text


# ------------------------------------------------------------------ planner, implementer, scout


def test_the_planner_writes_done_when_that_a_test_can_check_or_says_how_to_check_by_hand():
    text = role("planner")
    assert "test-spec" in text
    assert re.search(r"kind: other", text) and re.search(r"how (it is|to) check", text, flags=re.I)


def test_the_implementer_does_not_edit_the_tests_of_the_test_spec_report():
    text = role("implementer")
    assert "test-spec" in text
    assert re.search(r"(never|do not|must not) (edit|change|modify).{0,80}test", text, flags=re.I)
    assert re.search(r"stop|tell the person|report it", text, flags=re.I)


def test_the_scout_writes_the_test_command_line_of_the_profile():
    text = role("scout")
    assert "- test-command:" in text and "agentflow config set test_command" in text


# ------------------------------------------------------------------ skills


def test_the_continue_skill_runs_the_test_spec_step_with_the_tester_and_stops_for_the_person():
    text = skill("continue")
    assert "test-spec" in text and "tester" in text
    assert re.search(r"test-spec.{0,400}(approve|checklist|person)", text, flags=re.S)


def test_the_start_skill_mentions_the_new_step_in_the_cycle():
    assert "test-spec" in skill("start")


def test_the_approve_skill_tells_the_person_what_to_read_for_test_spec():
    text = skill("approve")
    assert "test-spec" in text and "verify-red.json" in text


# ------------------------------------------------------------------ documents


def test_usage_has_a_section_on_tests_first_with_the_report_form_and_the_commands():
    body = section(read(USAGE), "Test trước (test-spec)")
    for needle in ("- tests:", "- command:", "- red: fail", "không có —", "agentflow tests verify-red", "verify-red.json", "tests-pass", "test_command", "test_timeout_minutes", "test-command", "15 phút", "kind: other", "spec_results", "đỏ trước", "xanh sau"):
        assert needle in body, needle


def test_usage_says_the_command_must_name_a_test_file_of_its_item_and_that_the_person_reads_it():
    body = section(read(USAGE), "Test trước (test-spec)")
    assert re.search(r"lệnh.{0,120}(nhắc|ghi tên|chứa).{0,80}file test", body, flags=re.S | re.I)
    assert re.search(r"bạn (đọc|kiểm).{0,80}lệnh|lệnh.{0,80}bạn (đọc|kiểm)", body, flags=re.S | re.I)


def test_usage_names_the_loop_with_test_spec_in_it():
    assert re.search(r"plan\s*(→|->)\s*test-spec\s*(→|->)\s*implement", read(USAGE))


def test_usage_troubleshooting_covers_the_two_new_refusals():
    body = section(read(USAGE), "Xử lý tình huống")
    for needle in ("test-spec", "chạy lại", "tests-pass", "agentflow config set test_command", "project confirm profile"):
        assert needle in body, needle


def test_usage_says_the_report_is_not_what_agentflow_trusts():
    body = section(read(USAGE), "Test trước (test-spec)")
    assert re.search(r"agentflow (tự )?chạy lại", body) and re.search(r"output.{0,80}(chỉ|để bạn đọc)", body, flags=re.S)


def test_readme_names_test_spec_and_the_test_command_setting():
    text = read(README)
    assert "test-spec" in text and "test_command" in text


def test_architecture_lists_both_gates_and_the_files_they_write():
    text = read(ARCHITECTURE)
    for needle in ("test-spec-valid", "tests-pass", "verify-red.json", "tests-pass.json", "testrun", "spec_results"):
        assert needle in text, needle


def test_architecture_states_what_the_gates_cannot_know():
    text = read(ARCHITECTURE)
    assert re.search(r"(lý do|reason).{0,120}(người|person).{0,80}(kiểm|đọc|check)|(người|person).{0,80}(kiểm|đọc).{0,120}(lý do|reason)", text, flags=re.S | re.I)
    assert re.search(r"exit code|mã thoát", text)


def unreleased() -> str:
    found = re.search(r"^## \[?Unreleased\]?.*?$(.*)", read(CHANGELOG), flags=re.M | re.S | re.I)
    assert found
    return found.group(1)


@pytest.mark.parametrize(
    "needle", ["test-spec", "test-spec-valid", "tests-pass", "verify-red", "test_command", "test_timeout_minutes", "tests verify-red", "spec_results"]
)
def test_the_changelog_records_the_new_behaviour(needle):
    assert needle in unreleased()


def test_the_backend_readme_explains_how_migration_items_pass_test_spec():
    text = read(BACKEND_README)
    assert "test-spec" in text
    assert re.search(r"không có — chạy lên/xuống/lên|không có — .{0,40}up.{0,10}down", text)
    assert re.search(r"Squawk|Schemathesis", text) and re.search(r"bước `test`", text)
