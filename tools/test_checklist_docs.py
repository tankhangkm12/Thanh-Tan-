"""Chặng D-checklist (prompts, skills, documents, build): the checklists have one source and the documents describe them.

The fixed questions of each approval live only in `core/workflow.yaml` (`approval_checklist`, `approval_items`).
`tools/build.py` writes the block between `<!-- BEGIN:checklists -->` and `<!-- END:checklists -->` in
`families/software-dev/USAGE.md` from them, and `build.py --check` reports a block that is out of date.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
import shutil
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
BEGIN = "<!-- BEGIN:checklists -->"
END = "<!-- END:checklists -->"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def workflow() -> dict:
    return yaml.safe_load(read(CORE / "workflow.yaml"))


def steps_with_checklist() -> list[dict]:
    return [s for s in workflow()["steps"] if s.get("approval_checklist") or s.get("approval_items")]


def section(text: str, heading: str) -> str:
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    assert found, f"no '## {heading}' section"
    return found.group(1)


def block_of(text: str) -> str:
    assert text.count(BEGIN) == 1 and text.count(END) == 1, "exactly one generated block"
    assert text.index(BEGIN) < text.index(END)
    return text.split(BEGIN, 1)[1].split(END, 1)[0]


@pytest.fixture
def copy_of_family(tmp_path) -> Path:
    """The software-dev family in a temporary folder: ``core`` next to ``USAGE.md``."""
    family = tmp_path / "software-dev"
    shutil.copytree(CORE, family / "core")
    shutil.copy(USAGE, family / "USAGE.md")
    return family


# ------------------------------------------------------------------ the workflow is the source


def test_the_three_approvals_declare_their_fixed_questions_in_the_workflow():
    declared = {s["id"]: s for s in workflow()["steps"]}
    for name in ("confirm", "plan", "review"):
        questions = declared[name].get("approval_checklist") or []
        assert len(questions) >= 3, name
        assert all(isinstance(q, str) and q.strip() for q in questions)
    every = [q for s in steps_with_checklist() for q in s.get("approval_checklist", [])]
    assert len(every) == len(set(every)), "a question is written once"


def test_the_dynamic_sources_are_declared_where_the_report_that_feeds_them_is_approved():
    declared = {s["id"]: s for s in workflow()["steps"]}
    assert "plan-items" in declared["plan"].get("approval_items", [])
    assert {"review-conventions", "drift-proposals"} <= set(declared["review"].get("approval_items", []))


def test_only_steps_that_need_a_person_declare_a_checklist():
    for step in steps_with_checklist():
        assert step.get("requires_approval") is True, step["id"]


def test_the_roadmap_box_is_made_by_agentflow_not_written_in_the_workflow():
    questions = [q for s in steps_with_checklist() for q in s.get("approval_checklist", [])]
    assert not [q for q in questions if "Mục R" in q]


# ------------------------------------------------------------------ USAGE carries a generated block


def test_usage_has_one_generated_block_inside_the_checklist_section():
    body = section(read(USAGE), "Checklist khi duyệt")
    assert BEGIN in body and END in body
    block_of(read(USAGE))


def test_the_block_in_usage_is_exactly_what_the_build_writes():
    assert block_of(read(USAGE)) == build.checklists_block(CORE)


def test_every_question_of_the_workflow_is_in_the_block_as_an_open_box():
    block = block_of(read(USAGE))
    for step in steps_with_checklist():
        assert step["id"] in block
        for question in step.get("approval_checklist", []):
            assert f"- [ ] {question}" in block, question
        for source in step.get("approval_items", []):
            assert f"`{source}`" in block, source


def test_no_checklist_line_is_written_by_hand_outside_the_block():
    body = section(read(USAGE), "Checklist khi duyệt")
    outside = body.replace(block_of(read(USAGE)), "")
    assert "- [ ]" not in outside, "one source: the questions are not typed a second time"


def test_the_section_explains_the_file_the_boxes_the_notes_and_the_optional_roadmap_box():
    body = section(read(USAGE), "Checklist khi duyệt")
    for needle in ("approve-", "tasks/<task>", "[x]", "Ghi chú của bạn", "decisions/", "(tùy chọn)", "roadmap"):
        assert needle in body, needle


# ------------------------------------------------------------------ build.py keeps it honest


def test_a_clean_copy_of_the_family_passes_the_check(copy_of_family):
    assert build.check(copy_of_family / "core") == []


def test_a_hand_edit_inside_the_block_is_reported_and_the_build_repairs_it(copy_of_family):
    usage = copy_of_family / "USAGE.md"
    text = read(usage)
    usage.write_text(text.replace("- [ ]", "- [x]", 1), encoding="utf-8")
    problems = build.check(copy_of_family / "core")
    assert any("USAGE.md" in p for p in problems)
    build.build(copy_of_family / "core")
    assert build.check(copy_of_family / "core") == []
    assert read(usage) == text


def test_a_change_of_a_question_in_the_workflow_makes_the_block_out_of_date(copy_of_family):
    path = copy_of_family / "core" / "workflow.yaml"
    data = yaml.safe_load(read(path))
    first = next(s for s in data["steps"] if s.get("approval_checklist"))
    first["approval_checklist"][0] += " (đã đổi)"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert any("USAGE.md" in p for p in build.check(copy_of_family / "core"))


def test_text_outside_the_block_is_not_the_builds_business(copy_of_family):
    usage = copy_of_family / "USAGE.md"
    usage.write_text(read(usage) + "\nMột dòng ghi thêm.\n", encoding="utf-8")
    assert build.check(copy_of_family / "core") == []


def test_a_usage_without_the_markers_is_reported(copy_of_family):
    usage = copy_of_family / "USAGE.md"
    usage.write_text(read(usage).replace(BEGIN, "").replace(END, ""), encoding="utf-8")
    assert any("USAGE.md" in p for p in build.check(copy_of_family / "core"))


# ------------------------------------------------------------------ skills


def skill(name: str) -> str:
    return read(CORE / "skills" / name / "SKILL.md")


def test_the_approve_skill_sends_the_person_to_the_checklist_before_the_command():
    text = skill("approve")
    assert "approve-" in text and ".ThanhTan/tasks/<task>" in text
    assert re.search(r"\[x\]|tick", text)
    assert text.index("approve-") < text.index("agentflow task approve")


def test_the_approve_skill_forbids_the_agent_to_tick_or_edit_the_checklist():
    text = skill("approve")
    assert re.search(r"never (tick|edit|fill)", text, flags=re.I)
    assert "state accept" in text


def test_the_continue_skill_stops_at_the_checklist_and_names_the_file():
    text = skill("continue")
    assert "approve-" in text and re.search(r"checklist", text, flags=re.I)


# ------------------------------------------------------------------ USAGE, architecture, README, CHANGELOG


def test_usage_lists_state_accept_among_the_commands_of_the_person():
    body = section(read(USAGE), "Lệnh của người")
    assert "agentflow state accept" in body and "--reason" in body


def test_usage_troubleshooting_names_each_reason_an_approval_is_refused():
    body = section(read(USAGE), "Xử lý tình huống")
    for needle in ("chưa tick", "khung", "state.json", "integrity.json", "audit.jsonl", "state accept"):
        assert needle in body, needle


def protection_model() -> str:
    text = read(ARCHITECTURE)
    found = re.search(r"^(#{2,3}) [^\n]*Mô hình bảo vệ duyệt[^\n]*$(.*?)(?=^#{1,3} |\Z)", text, flags=re.M | re.S)
    assert found, "architecture.md has no 'Mô hình bảo vệ duyệt' section"
    return found.group(2)


@pytest.mark.parametrize(
    "layer",
    ["permissions", "hook", "ask", "approve-", "state.json", "integrity.json", "audit.jsonl", "agentflow commit", "sandbox"],
)
def test_architecture_describes_each_layer_of_the_approval_protection(layer):
    assert layer in protection_model()


def test_architecture_states_what_the_layers_cannot_do():
    body = protection_model()
    assert "python -c" in body, "a program that writes files by itself is not seen by the hook"
    assert re.search(r"Windows", body) and re.search(r"không có sandbox|không chạy.{0,40}sandbox|sandbox.{0,60}không", body, flags=re.S)
    assert re.search(r"tính lại|recompute|viết lại.{0,40}hash", body, flags=re.S), "an agent that recomputes every hash is not stopped by hashes"
    assert re.search(r"không ghi.{0,40}(Read|đọc)|(Read|đọc).{0,60}không (được )?ghi", body, flags=re.S | re.I)


def test_architecture_has_a_table_with_one_row_per_layer():
    rows = [line for line in protection_model().splitlines() if line.strip().startswith("|")]
    assert len(rows) >= 8


def test_readme_tells_the_person_to_run_doctor_after_updating_and_what_it_reports():
    text = read(README)
    assert re.search(r"agentflow doctor.{0,400}(lệch|khác).{0,40}phiên bản|(lệch|khác).{0,40}phiên bản.{0,400}agentflow doctor", text, flags=re.S)
    assert "uv tool install --force --reinstall ./foundation" in text


def unreleased() -> str:
    found = re.search(r"^## \[?Unreleased\]?.*?$(.*)", read(CHANGELOG), flags=re.M | re.S | re.I)
    assert found, "CHANGELOG has no Unreleased section"
    return found.group(1)


@pytest.mark.parametrize(
    "needle",
    ["approve-<", "approval_checklist", "integrity.json", "audit.jsonl", "state accept", "agentflow doctor", "(tùy chọn)"],
)
def test_the_changelog_records_the_new_behaviour(needle):
    assert needle in unreleased()
