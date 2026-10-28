"""Tests for approvals.py: gate approvals in state.md read the way rule 2 writes them.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import approvals as ap  # noqa: E402

CORE = Path(__file__).resolve().parent.parent
HEAD = "| Gate | Giai đoạn | Trạng thái | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- | --- |\n"


def state(rows: list[tuple[str, str, str, str]], before="", after="") -> str:
    body = "".join(f"| {g} | giai đoạn | {s} | {q} | {d} |\n" for g, s, q, d in rows)
    return f"# Trạng thái\n\n{before}## Gate\n\nmô tả\n\n{HEAD}{body}\n{after}## Task đang mở\n\n| ID | Tên |\n| --- | --- |\n| T-001 | x |\n"


def approved(upto: int, status="đã duyệt") -> list[tuple[str, str, str, str]]:
    return [(f"G{n}", status, f'"G{n}: duyệt"', "2026-10-12") for n in range(upto + 1)]


def test_every_gate_up_to_n_approved_is_fine():
    assert ap.problems_up_to(state(approved(4)), 4) == []
    assert ap.problems_up_to(state(approved(10)), 3) == []                 # later gates do not matter


def test_the_shipped_template_has_nothing_approved():
    text = (CORE / "templates" / "workspace" / "state.md").read_text(encoding="utf-8")
    problems = ap.problems_up_to(text, 0)
    assert len(problems) == 1 and "G0" in problems[0]


@pytest.mark.parametrize("status", ["đang làm", "chờ duyệt", "chưa làm", "", "duyệt"])
def test_only_the_status_da_duyet_counts(status):
    problems = ap.problems_up_to(state(approved(2, status)), 2)
    assert len(problems) == 3 and all("đã duyệt" in p for p in problems)


def test_an_earlier_gate_that_was_never_approved_blocks_a_later_one():
    rows = approved(4)
    rows[2] = ("G2", "chờ duyệt", "", "")
    problems = ap.problems_up_to(state(rows), 4)
    assert len(problems) == 1 and problems[0].startswith("G2")


@pytest.mark.parametrize("quote", ["ok", "được", "duyệt đi", "G4 duyệt", "G4: không duyệt", "G4: chưa duyệt", "G5: duyệt", "G14: duyệt", "XG4: duyệt", "G4-1: duyệt", "G4:duyệtt", ""])
def test_the_words_must_be_this_gates_id_colon_duyet(quote):
    rows = approved(4)
    rows[4] = ("G4", "đã duyệt", quote, "2026-10-12")
    problems = ap.problems_up_to(state(rows), 4)
    assert len(problems) == 1 and "G4: duyệt" in problems[0]


@pytest.mark.parametrize("quote", ['"G4: duyệt"', "G4: duyệt", "`G4: duyệt`", "“G4: duyệt”", "tôi nói G4: duyệt nhé", "G4 : duyệt", "g4: duyệt", "*G4: duyệt*"])
def test_the_ways_a_quote_may_be_written(quote):
    rows = approved(4)
    rows[4] = ("G4", "đã duyệt", quote, "2026-10-12")
    assert ap.problems_up_to(state(rows), 4) == []


def test_g1_is_not_approved_by_a_quote_for_g10():
    rows = approved(10)
    rows[1] = ("G1", "đã duyệt", '"G10: duyệt"', "2026-10-12")
    problems = ap.problems_up_to(state(rows), 1)
    assert len(problems) == 1 and problems[0].startswith("G1:")


@pytest.mark.parametrize("date", ["", "hôm nay", "2026-13-01", "12/10/2026", "2026-10-32", "<YYYY-MM-DD>"])
def test_the_date_must_be_real(date):
    rows = approved(2)
    rows[1] = ("G1", "đã duyệt", '"G1: duyệt"', date)
    problems = ap.problems_up_to(state(rows), 2)
    assert len(problems) == 1 and "ngày" in problems[0]


def test_a_gate_with_no_row_is_a_problem():
    rows = [r for r in approved(4) if r[0] != "G3"]
    problems = ap.problems_up_to(state(rows), 4)
    assert len(problems) == 1 and "G3" in problems[0] and "không có dòng" in problems[0]


def test_no_gate_table_is_one_clear_problem():
    assert len(ap.problems_up_to("# Trạng thái\n\nkhông có bảng\n", 3)) == 1
    assert len(ap.problems_up_to("## Gate\n\nchỉ chữ\n", 3)) == 1


def test_a_table_under_another_heading_is_not_the_gate_table():
    text = "## Việc khác\n\n" + HEAD + "".join(f"| G{n} | x | đã duyệt | \"G{n}: duyệt\" | 2026-10-12 |\n" for n in range(3))
    assert len(ap.problems_up_to(text, 2)) == 1


def test_the_first_row_of_a_gate_wins_a_later_copy_cannot_approve_it():
    rows = approved(2)
    rows[1] = ("G1", "chờ duyệt", "", "")
    rows.append(("G1", "đã duyệt", '"G1: duyệt"', "2026-10-12"))
    problems = ap.problems_up_to(state(rows), 2)
    assert len(problems) == 1 and problems[0].startswith("G1")


def test_a_table_in_a_later_section_does_not_leak_in():
    text = state(approved(0)[:0] + [("G0", "chưa làm", "", "")], after="")
    text += "\n## Gate khác\n\n" + HEAD + '| G0 | x | đã duyệt | "G0: duyệt" | 2026-10-12 |\n'
    assert len(ap.problems_up_to(text, 0)) == 1


def test_a_gate_missing_from_the_table_is_not_taken_from_a_table_of_a_later_section():
    rows = [r for r in approved(2) if r[0] != "G1"]
    text = state(rows, after="## Gate khác\n\n" + HEAD + '| G1 | x | đã duyệt | "G1: duyệt" | 2026-10-12 |\n\n')
    problems = ap.problems_up_to(text, 2)
    assert len(problems) == 1 and "G1" in problems[0] and "không có dòng" in problems[0]


def test_columns_may_come_in_another_order():
    text = ("## Gate\n\n| Ngày | Gate | Người dùng nói (nguyên văn) | Trạng thái |\n| --- | --- | --- | --- |\n"
            "| 2026-10-12 | G0 | \"G0: duyệt\" | đã duyệt |\n")
    assert ap.problems_up_to(text, 0) == []


def test_crlf_files_are_read_the_same():
    assert ap.problems_up_to(state(approved(3)).replace("\n", "\r\n"), 3) == []
