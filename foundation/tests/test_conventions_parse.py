import pytest

from agentflow.constants import CheckKind, ConventionStatus, PlanRuleKind
from agentflow.conventions import (
    Convention,
    parse_conventions,
    render_conventions,
    validate_conventions,
)

SAMPLE = """# Quy ước dự án

Ghi chú mở đầu.

### PC-01 - Giá trị cố định dùng constant hoặc Enum
- check: semgrep
- rule: no-literal-status.yaml
- status: unconfirmed
- source: src/constants.py (suy ra từ code)
- description: Không viết trực tiếp chuỗi cho trạng thái, khóa, tên lệnh.

### PC-02 - Interface trước khi implement
- check: plan
- rule: item-order
- status: confirmed
- source: docs/CONTRIBUTING.md:12
- description: Mục khai báo interface đứng trước mục cài đặt cùng file.
- overrides: KC-03

### PC-03 - Hàm công khai có docstring
- check: review
- status: unconfirmed
- source: src/app (suy ra từ code)
- description: Mỗi hàm công khai có docstring một dòng.

## Câu hỏi mở

### S1 - Tài liệu ghi dùng pytest, Makefile gọi unittest. Dùng cái nào?
- docs: docs/testing.md:5
- code: Makefile:14
"""


def parsed(text=SAMPLE, prefix="PC"):
    return parse_conventions(text, prefix)


def test_parse_reads_every_field():
    doc = parsed()
    assert [c.code for c in doc.conventions] == ["PC-01", "PC-02", "PC-03"]
    first, second, third = doc.conventions
    assert first == Convention(
        code="PC-01",
        title="Giá trị cố định dùng constant hoặc Enum",
        check=CheckKind.SEMGREP,
        rule="no-literal-status.yaml",
        status=ConventionStatus.UNCONFIRMED,
        source="src/constants.py (suy ra từ code)",
        description="Không viết trực tiếp chuỗi cho trạng thái, khóa, tên lệnh.",
    )
    assert second.check is CheckKind.PLAN and second.rule == PlanRuleKind.ITEM_ORDER and second.status is ConventionStatus.CONFIRMED
    assert second.overrides == "KC-03"
    assert third.rule is None and third.check is CheckKind.REVIEW
    assert [(q.code, q.docs, q.code_ref) for q in doc.questions] == [("S1", "docs/testing.md:5", "Makefile:14")]
    assert doc.questions[0].title.startswith("Tài liệu ghi dùng pytest")
    assert "Ghi chú mở đầu." in doc.preamble


def test_a_valid_document_has_no_problems():
    assert validate_conventions(parsed()) == []


def test_render_is_stable_and_parses_back_to_the_same_document():
    doc = parsed()
    again = parse_conventions(render_conventions(doc), "PC")
    assert again.conventions == doc.conventions and again.questions == doc.questions
    assert render_conventions(again) == render_conventions(doc)


@pytest.mark.parametrize(
    ("edit", "needle"),
    [
        (lambda t: t.replace("- check: review", "- check: lint"), "check"),
        (lambda t: t.replace("- check: review\n", ""), "check"),
        (lambda t: t.replace("- source: src/app (suy ra từ code)\n", ""), "source"),
        (lambda t: t.replace("- description: Mỗi hàm công khai có docstring một dòng.\n", ""), "description"),
        (lambda t: t.replace("- status: unconfirmed\n- source: src/app", "- status: maybe\n- source: src/app"), "status"),
        (lambda t: t.replace("- rule: item-order", "- rule: sort-things"), "item-order"),
        (lambda t: t.replace("- rule: no-literal-status.yaml\n", ""), "rule"),
        (lambda t: t.replace("- rule: no-literal-status.yaml", "- rule: ../../etc/x.yaml"), "file name"),
        (lambda t: t.replace("- check: review\n", "- check: review\n- rule: whatever\n"), "rule"),
        (lambda t: t.replace("### PC-03 -", "### PC-02 -"), "duplicate"),
        (lambda t: t.replace("### PC-03 -", "### XX-03 -"), "XX-03"),
        (lambda t: t.replace("- overrides: KC-03", "- overrides: banana"), "overrides"),
        (lambda t: t.replace("### S1 -", "### Q1 -"), "Q1"),
    ],
)
def test_validation_names_each_problem(edit, needle):
    problems = validate_conventions(parsed(edit(SAMPLE)))
    assert problems and any(needle in problem for problem in problems), problems


def test_all_problems_are_listed_at_once():
    broken = SAMPLE.replace("- check: review", "- check: lint").replace("- source: src/constants.py (suy ra từ code)\n", "")
    assert len(validate_conventions(parsed(broken))) >= 2


def test_other_prefixes_belong_to_other_sources():
    text = "### DC-01 - From a decision\n- check: review\n- source: decision\n- description: x\n"
    assert validate_conventions(parse_conventions(text, "DC")) == []
    assert validate_conventions(parse_conventions(text, "PC"))  # a DC code in the project file is wrong


def test_an_empty_document_is_valid_but_has_nothing_in_it():
    doc = parse_conventions("# Nothing yet\n", "PC")
    assert doc.conventions == () and doc.questions == () and validate_conventions(doc) == []


def test_headings_inside_code_fences_are_ignored():
    text = "```\n### PC-09 - not real\n- check: review\n```\n" + SAMPLE
    assert [c.code for c in parse_conventions(text, "PC").conventions] == ["PC-01", "PC-02", "PC-03"]
