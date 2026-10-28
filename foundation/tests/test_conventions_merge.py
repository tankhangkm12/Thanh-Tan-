import pytest

from thanhtan.constants import CheckKind, ConventionSource, ConventionStatus
from thanhtan.convention_sources import (
    answer_file_name,
    load_decision_conventions,
    load_effective_conventions,
    next_code,
    write_answer,
)
from thanhtan.conventions import Convention

PROJECT = """### PC-01 - Constants
- check: review
- status: confirmed
- source: src/constants.py
- description: Fixed values live in constants.

### PC-02 - Docstrings
- check: review
- status: unconfirmed
- source: src/app
- description: Public functions have docstrings.

### PC-03 - Interface first
- check: plan
- rule: item-order
- status: confirmed
- source: docs/CONTRIBUTING.md:3
- description: Interfaces come first.
"""

PERSONAL = """### KC-01 - Small commits
- check: review
- source: my notes
- description: Commit small.

### KC-02 - Prefer enums
- check: review
- source: my notes
- description: Enums over strings.
- overrides: PC-01
"""


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / ".ThanhTan"
    (root / "decisions").mkdir(parents=True)
    (root / "project").mkdir()
    (root / "knowledge").mkdir()
    return root


def put(root, relative, text):
    (root / relative).write_text(text, encoding="utf-8")


def codes(effective):
    return [item.convention.code for item in effective.items]


def test_nothing_anywhere_is_an_empty_list(workspace):
    effective = load_effective_conventions(workspace)
    assert effective.items == () and effective.problems == ()


def test_project_and_personal_conventions_are_listed_with_their_source(workspace):
    put(workspace, "project/conventions.md", PROJECT)
    put(workspace, "knowledge/conventions.md", PERSONAL.replace("- overrides: PC-01\n", ""))
    effective = load_effective_conventions(workspace)
    assert codes(effective) == ["PC-01", "PC-02", "PC-03", "KC-01", "KC-02"]
    assert {item.convention.code: item.source for item in effective.items}["KC-01"] is ConventionSource.PERSONAL


def test_a_person_made_convention_is_enforced_at_once_but_a_project_one_needs_confirming(workspace):
    put(workspace, "project/conventions.md", PROJECT)
    put(workspace, "knowledge/conventions.md", PERSONAL)
    effective = load_effective_conventions(workspace)
    enforced = {item.convention.code for item in effective.enforced}
    assert enforced == {"PC-01", "PC-03", "KC-01", "KC-02"}  # PC-02 is unconfirmed
    by_code = {item.convention.code: item for item in effective.items}
    assert by_code["KC-01"].convention.status is ConventionStatus.CONFIRMED


def test_the_personal_store_cannot_override_the_project(workspace):
    put(workspace, "project/conventions.md", PROJECT)
    put(workspace, "knowledge/conventions.md", PERSONAL)
    effective = load_effective_conventions(workspace)
    assert "PC-01" in codes(effective)
    assert any("KC-02" in problem and "PC-01" in problem for problem in effective.problems)


def test_a_decision_overrides_the_project_and_the_store(workspace):
    put(workspace, "project/conventions.md", PROJECT)
    put(workspace, "knowledge/conventions.md", PERSONAL)
    write_answer(
        workspace, scope="project", question="S1", code="DC-01", text="Use unittest.", check=CheckKind.REVIEW,
        rule=None, overrides="PC-02", at="2026-10-10T10:00:00Z",
    )  # fmt: skip
    effective = load_effective_conventions(workspace)
    assert codes(effective)[0] == "DC-01" and "PC-02" not in codes(effective)
    first = effective.items[0]
    assert first.source is ConventionSource.DECISION and first.convention.status is ConventionStatus.CONFIRMED
    assert first.convention.description == "Use unittest."


def test_decisions_come_first_then_project_then_personal(workspace):
    put(workspace, "project/conventions.md", PROJECT)
    put(workspace, "knowledge/conventions.md", PERSONAL.replace("- overrides: PC-01\n", ""))
    write_answer(workspace, "T-001", "Q1", "DC-01", "Singular table names.", CheckKind.REVIEW, None, None, "2026-10-10T10:00:00Z")
    assert codes(load_effective_conventions(workspace)) == ["DC-01", "PC-01", "PC-02", "PC-03", "KC-01", "KC-02"]


def test_answer_files_have_a_stable_name_and_round_trip(workspace):
    path = write_answer(workspace, "T-004", "Q2", "DC-07", "Line one.", CheckKind.PLAN, "item-order", None, "2026-10-10T10:00:00Z")
    assert path.name == answer_file_name("T-004", "Q2") == "T-004-answer-Q2.md"
    [item] = load_decision_conventions(workspace)
    assert item == Convention(
        code="DC-07", title="Q2 (T-004)", check=CheckKind.PLAN, rule="item-order", status=ConventionStatus.CONFIRMED,
        source="decision T-004-answer-Q2.md", description="Line one.",
    )  # fmt: skip


def test_next_code_continues_after_the_highest_in_use(workspace):
    assert next_code(workspace) == "DC-01"
    write_answer(workspace, "T-001", "Q1", "DC-01", "x", CheckKind.REVIEW, None, None, "2026-10-10T10:00:00Z")
    write_answer(workspace, "T-001", "Q2", "DC-09", "x", CheckKind.REVIEW, None, None, "2026-10-10T10:00:00Z")
    assert next_code(workspace) == "DC-10"


def test_a_broken_file_is_reported_not_fatal(workspace):
    put(workspace, "project/conventions.md", PROJECT.replace("- check: review\n- status: confirmed", "- check: lint\n- status: confirmed", 1))
    (workspace / "decisions" / "T-001-answer-Q1.md").write_text("no frontmatter at all", encoding="utf-8")
    effective = load_effective_conventions(workspace)
    assert effective.problems and "PC-03" in codes(effective)


def test_answering_the_same_question_twice_is_refused(workspace):
    write_answer(workspace, "T-001", "Q1", "DC-01", "x", CheckKind.REVIEW, None, None, "2026-10-10T10:00:00Z")
    with pytest.raises(Exception) as exc:
        write_answer(workspace, "T-001", "Q1", "DC-02", "y", CheckKind.REVIEW, None, None, "2026-10-10T10:00:00Z")
    assert "already" in str(exc.value)
