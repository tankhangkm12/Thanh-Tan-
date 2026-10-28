import pytest

from agentflow.constants import PlanItemKind
from agentflow.interfaces import PlanWideRule
from agentflow.plan import PlanQuestion, check_plan, parse_plan
from agentflow.plan_rules import ItemOrderRule


class Roles:
    def roles(self):
        return {"implementer", "tester"}


def item(code, kind, files, role="implementer"):
    kind_line = f"- kind: {kind}\n" if kind else ""
    return f"### {code} - {code} title\n- role: {role}\n{kind_line}- files: {files}\n- done-when: ok\n- docs: không có — internal\n\n"


def problems(text, rules=(ItemOrderRule("PC-03"),), answered=None):
    return [str(p) for p in check_plan(parse_plan(text), Roles(), wide_rules=rules, answered_questions=answered)]


def test_the_rule_implements_the_protocol():
    assert isinstance(ItemOrderRule("PC-03"), PlanWideRule)


def test_items_carry_their_kind():
    plan = parse_plan(item("C1", "interface", "src/api.py") + item("C2", "IMPLEMENT", "src/impl.py"))
    assert [i.kind for i in plan.items] == ["interface", "implement"]
    assert [i.kind for i in parse_plan(item("C1", None, "a.py")).items] == [None]


def test_interface_before_implementation_of_the_same_file_is_fine():
    text = item("C1", "interface", "src/api.py") + item("C2", "implement", "src/api.py, src/impl.py")
    assert problems(text) == []


def test_an_implementation_before_its_interface_is_refused():
    text = item("C1", "implement", "src/api.py") + item("C2", "interface", "src/api.py")
    found = problems(text)
    assert len(found) == 1 and "C1" in found[0] and "C2" in found[0] and "src/api.py" in found[0] and "PC-03" in found[0]


def test_items_about_different_files_may_come_in_any_order():
    assert problems(item("C1", "implement", "src/a.py") + item("C2", "interface", "src/b.py")) == []


def test_other_kinds_are_never_ordered():
    assert problems(item("C1", "other", "src/a.py") + item("C2", "interface", "src/a.py")) == []


def test_with_the_rule_on_every_item_needs_a_known_kind():
    text = item("C1", None, "a.py") + item("C2", "banana", "a.py")
    found = problems(text)
    assert any("C1" in p and "missing 'kind'" in p for p in found)
    assert any("C2" in p and "banana" in p for p in found)


def test_interface_and_implement_items_must_list_their_files():
    text = "### C1 - x\n- role: implementer\n- kind: implement\n- done-when: ok\n- docs: không có — internal\n"
    assert any("C1" in p and "files" in p for p in problems(text))


def test_without_the_rule_kind_is_optional_but_must_be_valid_when_given():
    assert problems(item("C1", None, "a.py"), rules=()) == []
    assert any("banana" in p for p in problems(item("C1", "banana", "a.py"), rules=()))


def test_every_kind_is_known():
    assert {kind.value for kind in PlanItemKind} == {"interface", "implement", "other"}


# --------------------------------------------------------- "Chưa có quy ước"

QUESTIONS = """
## Chưa có quy ước

### Q1 - Tên bảng số ít hay số nhiều?
- ask: Dự án chưa có quy ước đặt tên bảng; cần chọn trước khi viết migration.
- options: số ít (item), số nhiều (items)
- needed-by: C2

### Q2 - Có dùng soft delete không?
- ask: Chưa rõ xóa mềm hay xóa cứng.
"""


def test_questions_are_read_from_their_section():
    plan = parse_plan(item("C1", None, "a.py") + QUESTIONS)
    assert [q.code for q in plan.questions] == ["Q1", "Q2"]
    first = plan.questions[0]
    assert first == PlanQuestion("Q1", "Tên bảng số ít hay số nhiều?", "Dự án chưa có quy ước đặt tên bảng; cần chọn trước khi viết migration.", "số ít (item), số nhiều (items)", "C2")
    assert plan.bad_headings == () and [i.code for i in plan.items] == ["C1"]


def test_unanswered_questions_block_the_plan():
    found = problems(item("C1", None, "a.py") + QUESTIONS, rules=(), answered={"Q2"})
    assert len(found) == 1 and "Q1" in found[0] and "decide --answer Q1" in found[0]


def test_answered_questions_do_not_block():
    assert problems(item("C1", None, "a.py") + QUESTIONS, rules=(), answered={"Q1", "Q2"}) == []


def test_without_a_task_the_answers_are_not_checked():
    assert problems(item("C1", None, "a.py") + QUESTIONS, rules=(), answered=None) == []


def test_a_question_must_say_what_it_asks_and_have_a_unique_code():
    text = item("C1", None, "a.py") + "\n## Chưa có quy ước\n\n### Q1 - a\n\n### Q1 - b\n- ask: x\n"
    found = problems(text, rules=(), answered={"Q1"})
    assert any("Q1" in p and "ask" in p for p in found) and any("duplicate" in p for p in found)


def test_another_heading_ends_the_questions_section():
    text = QUESTIONS + "\n## Rủi ro\n\n### C9 - late item\n- role: tester\n- done-when: x\n- docs: không có — x\n"
    plan = parse_plan(item("C1", None, "a.py") + text)
    assert [q.code for q in plan.questions] == ["Q1", "Q2"] and [i.code for i in plan.items] == ["C1", "C9"]


@pytest.mark.parametrize("heading", ["## Chưa có quy ước", "## chưa có quy ước", "##  Chưa có quy ước  "])
def test_the_section_heading_is_found_whatever_its_case_and_spacing(heading):
    plan = parse_plan(item("C1", None, "a.py") + f"\n{heading}\n\n### Q1 - t\n- ask: x\n")
    assert [q.code for q in plan.questions] == ["Q1"]
