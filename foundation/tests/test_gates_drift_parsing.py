"""The `drift-reviewed` gate: continuation lines and code fences (added after the first set of tests was locked).

Same harness as test_gates_drift.py (imported, not copied). Fence rules follow CommonMark: a fence closes only
with the same character and at least as many of them, and an unclosed fence runs to the end of the report.
"""

import pytest
from test_gates_drift import HEADING, at_review, review_with, save_review, try_pass  # noqa: F401 (at_review is a fixture)

from agentflow.constants import ExitCode

SECTION_OK = HEADING + "\n\nkhông có\n"


def passes(at_review, capsys, text: str) -> tuple[int, str]:
    save_review(at_review, review_with(text))
    return try_pass(capsys)


# ------------------------------------------------------- continuation lines


def test_an_indented_line_under_a_bullet_continues_that_proposal(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\n- architecture: thêm module thanh toán\n  gọi dịch vụ ngoài qua hàng đợi\n- roadmap: R2 xong\n")
    assert code == ExitCode.OK, err


def test_an_indented_line_with_no_bullet_before_it_is_refused(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\n  nằm lửng lơ, không thuộc đề xuất nào\n")
    assert code == ExitCode.GATE_FAILED and "neither" in err


def test_an_indented_line_after_none_is_refused(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\nkhông có\n  thêm một dòng\n")
    assert code == ExitCode.GATE_FAILED


def test_a_continuation_does_not_rescue_a_bullet_that_names_no_document(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\n- readme: sửa lại\n  vì mô tả sai\n")
    assert code == ExitCode.GATE_FAILED and "readme" in err


# ---------------------------------------------------------------- code fences

HIDDEN_BEHIND = {
    "backtick fence": "```\n" + SECTION_OK + "```\n",
    "backtick fence with a language": "```markdown\n" + SECTION_OK + "```\n",
    "tilde fence": "~~~\n" + SECTION_OK + "~~~\n",
    "tilde fence with a language": "~~~md\n" + SECTION_OK + "~~~\n",
    "indented fence marker": "   ```\n" + SECTION_OK + "   ```\n",
    "backticks inside a tilde fence": "~~~\n```\n" + SECTION_OK + "```\n~~~\n",
    "tildes inside a backtick fence": "```\n~~~\n" + SECTION_OK + "~~~\n```\n",
    "longer outer fence around a shorter one": "````\n```\n" + SECTION_OK + "```\n````\n",
    "a fence that is never closed": "```\n" + SECTION_OK,
}


@pytest.mark.parametrize("text", HIDDEN_BEHIND.values(), ids=HIDDEN_BEHIND.keys())
def test_a_section_that_is_only_inside_a_code_fence_does_not_count(at_review, capsys, text):
    code, err = passes(at_review, capsys, text)
    assert code == ExitCode.GATE_FAILED and "has no" in err


def test_a_closed_tilde_fence_inside_the_section_is_not_part_of_the_proposals(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\nkhông có\n\n~~~\nsome shell output\n~~~\n")
    assert code == ExitCode.OK, err


def test_a_closed_backtick_fence_inside_the_section_is_not_part_of_the_proposals(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\n- profile: lệnh build mới\n\n```\nuv run build\n```\n")
    assert code == ExitCode.OK, err


def test_text_after_a_closed_fence_is_report_content_again(at_review, capsys):
    code, err = passes(at_review, capsys, "```\nexample\n```\n\n" + SECTION_OK)
    assert code == ExitCode.OK, err


def test_the_section_that_follows_an_unclosed_fence_is_lost(at_review, capsys):
    code, _ = passes(at_review, capsys, "```\nexample that was never closed\n\n" + SECTION_OK)
    assert code == ExitCode.GATE_FAILED


def test_a_shorter_closing_marker_does_not_close_a_longer_fence(at_review, capsys):
    code, _ = passes(at_review, capsys, "````\nexample\n```\n" + SECTION_OK + "````\n")
    assert code == ExitCode.GATE_FAILED


# ------------------------------------------- indentation (CommonMark: up to 3 spaces is still markup, 4 is code)


@pytest.mark.parametrize("indent", [" ", "  ", "   "], ids=["1 space", "2 spaces", "3 spaces"])
def test_a_heading_indented_by_up_to_three_spaces_is_still_a_heading(at_review, capsys, indent):
    code, err = passes(at_review, capsys, f"{indent}## Đề xuất cập nhật hồ sơ\n\nkhông có\n")
    assert code == ExitCode.OK, err


INDENTED_CODE = {
    "four spaces": "    ",
    "five spaces": "     ",
    "a tab": "\t",
    "a space and a tab": " \t",
}


@pytest.mark.parametrize("indent", INDENTED_CODE.values(), ids=INDENTED_CODE.keys())
def test_a_heading_indented_four_columns_or_more_is_code_not_a_heading(at_review, capsys, indent):
    """Regression for the 4-column edge: green before the fix, and the fix for 1–3 spaces must not break it."""
    code, err = passes(at_review, capsys, f"{indent}## Đề xuất cập nhật hồ sơ\n{indent}không có\n")
    assert code == ExitCode.GATE_FAILED and "has no" in err


def test_a_section_shown_as_an_indented_code_block_after_a_paragraph_does_not_count(at_review, capsys):
    """Regression: the usual way a report quotes an example section."""
    code, err = passes(at_review, capsys, "Ví dụ mục này:\n\n    " + HEADING + "\n\n    không có\n")
    assert code == ExitCode.GATE_FAILED and "has no" in err


def test_the_real_section_after_an_indented_code_block_still_counts(at_review, capsys):
    code, err = passes(at_review, capsys, "Ví dụ:\n\n    " + HEADING + "\n    không có\n\n" + SECTION_OK)
    assert code == ExitCode.OK, err


def test_a_heading_indented_by_up_to_three_spaces_still_ends_the_section(at_review, capsys):
    code, err = passes(at_review, capsys, HEADING + "\n\nkhông có\n\n  ## Bài học đề xuất\n\n### L1 - x\ntext\n")
    assert code == ExitCode.OK, err


def test_a_heading_indented_four_spaces_does_not_end_the_section(at_review, capsys):
    """Regression: an indented 'heading' is code, so it is a stray line of the section and the gate says so."""
    code, err = passes(at_review, capsys, HEADING + "\n\nkhông có\n\n    ## Bài học đề xuất\n")
    assert code == ExitCode.GATE_FAILED and "neither" in err


def test_a_fence_marker_indented_four_spaces_opens_no_fence(at_review, capsys):
    code, err = passes(at_review, capsys, "    ```\n" + SECTION_OK)
    assert code == ExitCode.OK, err


def test_a_closing_marker_followed_by_text_does_not_close_the_fence(at_review, capsys):
    code, err = passes(at_review, capsys, "```\nexample\n``` this is not a closing fence\n" + SECTION_OK + "```\n")
    assert code == ExitCode.GATE_FAILED and "has no" in err


def test_a_closing_marker_followed_only_by_spaces_closes_the_fence(at_review, capsys):
    code, err = passes(at_review, capsys, "```\nexample\n```   \n" + SECTION_OK)
    assert code == ExitCode.OK, err
