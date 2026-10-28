"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import calc_capacity as cc  # noqa: E402
import check_numbers as cn  # noqa: E402

HERE = Path(__file__).parent
SCRIPT = HERE / "check_numbers.py"
DATA = HERE / "test_data"

CFG, ERRORS = cn.load_config(cn.DEFAULT_CONFIG)
assert CFG is not None, ERRORS


def check(text: str, defined: set[str] | None = None, cfg: cn.Config = CFG, blocks: dict[str, str] | None = None, known: set[str] | None = None) -> list[cn.Finding]:
    return cn.check_text("a.md", text, cfg, defined, cn.Stats(), blocks, known)


def codes(text: str, defined: set[str] | None = None, cfg: cn.Config = CFG, known: set[str] | None = None) -> list[str]:
    return [f.code for f in check(text, defined, cfg, known=known)]


# --- the data file ---------------------------------------------------------------------------------------------------------------------

def test_the_shipped_data_file_has_the_words_of_the_plan():
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for word in ("nhanh", "lớn", "đủ dùng", "scale tốt"):
        assert word in data["vague_words"]
    for unit in ("MB", "GB", "ms", "%", "req/s", "người dùng"):
        assert unit in data["units"]
    assert "nguồn" in data["evidence_columns"] and "giả định" in data["evidence_columns"]


def write_config(tmp_path: Path, **override) -> Path:
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data.update(override)
    path = tmp_path / "numbers.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_the_word_lists_come_from_the_data_file_not_from_the_code(tmp_path):
    cfg, errors = cn.load_config(write_config(tmp_path, vague_words=["siêu việt"], units=["con vẹt"]))
    assert cfg is not None and not errors
    assert codes("Hệ thống nhanh và lớn.", cfg=cfg) == []  # no longer on the list
    assert codes("Hệ thống siêu việt.", cfg=cfg) == ["vague-word"]
    assert codes("Có 5 con vẹt.", cfg=cfg) == ["number-without-evidence"]
    assert codes("Cần 5 MB.", cfg=cfg) == []  # MB is no longer a unit


@pytest.mark.parametrize("override,expected", [
    ({"vague_words": []}, "vague_words"), ({"vague_words": "nhanh"}, "vague_words"), ({"units": [1]}, "units"), ({"evidence_columns": []}, "evidence_columns"),
    ({"vague_words": ["", "nhanh"]}, "phần tử rỗng"),
])
def test_a_bad_data_file_is_reported(tmp_path, override, expected):
    cfg, errors = cn.load_config(write_config(tmp_path, **override))
    assert cfg is None and any(expected in e for e in errors)


def test_missing_and_broken_data_file(tmp_path):
    assert cn.load_config(tmp_path / "none.yaml")[0] is None
    broken = tmp_path / "b.yaml"
    broken.write_text("vague_words: [unclosed\n", encoding="utf-8")
    assert cn.load_config(broken)[0] is None
    broken.write_text("- a\n", encoding="utf-8")
    assert cn.load_config(broken)[0] is None


# --- numbers with a unit -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Dữ liệu tăng 292 MB mỗi năm.", "p95 dưới 300 ms.", "CPU trên 70% trong 15 phút.", "Có 10.000 người dùng.", "Tải đỉnh 450 req/s.",
    "Cần 3 instance.", "Chi phí $100.", "Chi phí USD 100.", "Dung lượng 1,5 TB.", "Giữ 5 năm.", "Có 3,65 triệu dòng.", "Cần 8 GiB RAM.", "Giữ 2 tuần.",
    "Độ trễ 12 ms.", "Độ trễ 12ms.", "Lưu 90 ngày.", "Đạt 1000 rps.", "Mất 2 s.", "Tối đa 5 GB.", "Khoảng 40 byte mỗi dòng.", "Kích thước ~20 KB.",
])
def test_a_number_with_a_unit_and_nothing_else_is_flagged(text):
    assert codes(text) == ["number-without-evidence"], text


@pytest.mark.parametrize("text", [
    "Phiên bản PostgreSQL 16 được chọn.", "Xem FR-001 và NFR-12.", "Task T-003 đóng.", "Ngày 2026-10-12.", "Mục 3.2 nói về tải.", "Có 5 lớp.", "Hai ba bốn.",
    "Xem [tài liệu](https://example.com/docs/16/limits-300ms).", "Mốc TC-03 và R-04.", "# 3. Tổng quan", "Chương 2 giới thiệu.",
])
def test_numbers_without_a_unit_ids_dates_and_link_targets_are_not_checked(text):
    assert codes(text) == [], text


@pytest.mark.parametrize("text", [
    "Dữ liệu 292 MB/năm = 3.650.000 dòng × 80 byte.", "Dữ liệu 292 MB (công thức: dòng × byte).", "p95 dưới 300 ms, tính ⌈x⌉.", "Tải 450 req/s ÷ 150 req/s = 3 instance.",
    "Tải 450 req/s theo A-peak.", "Tải 450 req/s ([BA](inputs/ba/prd.md)).", "Tải 450 req/s, nguồn https://example.com/limits.", "Tải 450 req/s, theo inputs/ba/prd.md mục 3.",
])
def test_formula_assumption_or_source_in_the_same_sentence_makes_it_pass(text):
    assert codes(text, defined={"A-peak"}) == [], text


def test_an_assumption_counts_only_if_it_is_declared():
    assert codes("Tải 450 req/s theo A-peak.", defined={"A-other"}) == ["number-without-evidence"]
    assert codes("Tải 450 req/s theo A-peak.", defined=set()) == ["number-without-evidence"]
    assert codes("Tải 450 req/s theo A-peak.", defined={"A-peak"}) == []
    assert codes("Tải 450 req/s theo A-peak.", defined=None) == []  # yaml unreadable: reported elsewhere, do not pile up


def test_paragraphs_are_checked_sentence_by_sentence():
    text = "Hệ thống chịu 450 req/s. Con số này tính từ [BA](inputs/x.md). Dữ liệu đạt 292 MB."
    found = check(text)
    assert [f.code for f in found] == ["number-without-evidence", "number-without-evidence"]
    assert "450 req/s" in found[0].message and "292 MB" in found[1].message


def test_the_evidence_must_be_in_the_same_sentence():
    assert codes("Tải 450 req/s. Nguồn: [BA](inputs/ba.md).") == ["number-without-evidence"]
    assert codes("Tải 450 req/s, nguồn: [BA](inputs/ba.md).") == []


def test_numbers_in_a_decimal_or_thousands_form_do_not_split_sentences():
    assert codes("Cỡ 3.65 triệu dòng mỗi năm, tức 292 MB = 3.65 triệu × 80 byte.") == []
    assert len(check("Cỡ 3.65 triệu dòng mỗi năm.")) == 1


def test_one_finding_per_context_listing_the_numbers():
    found = check("Cần 3 instance và 8 GB RAM, độ trễ 12 ms.")
    assert len(found) == 1 and all(x in found[0].message for x in ("3 instance", "8 GB", "12 ms"))


def test_line_numbers_point_into_the_paragraph():
    found = check("Dòng một không có số.\nDòng hai cũng thế.\nTải 450 req/s ở dòng ba.\n")
    assert [f.line for f in found] == [3]
    found = check("Câu một.\nCâu hai bắt đầu\nvà kéo qua dòng 4 với 300 ms.\n")
    assert found[0].line == 2  # the sentence starts on line 2


def test_list_items_and_headings_are_checked_as_a_whole():
    assert codes("- Tải 450 req/s, nguồn [BA](inputs/ba.md).\n- Tải 10 MB.\n") == ["number-without-evidence"]
    assert codes("- Tải 450 req/s.\n  Nguồn: [BA](inputs/ba.md).\n") == []  # a continuation line belongs to the item
    assert codes("1. Tải 450 req/s (A-x).\n2. Tải 10 MB.\n", defined={"A-x"}) == ["number-without-evidence"]
    assert codes("## Giữ 5 năm\n") == ["number-without-evidence"]
    assert codes("## Giữ 5 năm (A-giu)\n", defined={"A-giu"}) == []


def test_two_items_do_not_borrow_each_others_evidence():
    found = check("- Tải 450 req/s.\n- Nguồn [BA](inputs/ba.md).\n")
    assert [f.line for f in found] == [1]


# --- tables -----------------------------------------------------------------------------------------------------------------------------

TABLE = "| Chỉ số | Giá trị | {col} |\n| --- | --- | --- |\n| tải | 450 req/s | {cell} |\n"


@pytest.mark.parametrize("col", ["Nguồn", "Giả định", "Công thức", "nguồn dữ liệu", "**Nguồn**", "Source", "Assumption", "Formula"])
def test_a_filled_evidence_column_makes_the_row_pass(col):
    assert codes(TABLE.format(col=col, cell="BA mục 3")) == []


@pytest.mark.parametrize("cell", ["", " ", "-", "—", "–", "n/a", "N/A", "TBD", "chưa có", "`—`", "**-**"])
def test_an_empty_evidence_cell_does_not(cell):
    assert codes(TABLE.format(col="Nguồn", cell=cell)) == ["number-without-evidence"]


def test_a_table_without_an_evidence_column_needs_evidence_in_the_row():
    plain = "| Chỉ số | Giá trị |\n| --- | --- |\n| tải | 450 req/s |\n| tải 2 | 10 MB = 5 × 2 |\n| tải 3 | 10 MB, A-x |\n"
    found = check(plain, defined={"A-x"})
    assert [f.line for f in found] == [3]


def test_the_header_row_and_separator_are_not_checked():
    assert codes("| Dung lượng (MB) | Độ trễ (ms) | 70% |\n| --- | --- | --- |\n| a | b | c |\n") == []


def test_evidence_in_one_row_is_not_shared_with_the_next():
    text = "| Chỉ số | Nguồn |\n| --- | --- |\n| tải 450 req/s | BA |\n| tải 10 MB | |\n"
    assert [f.line for f in check(text)] == [4]


def test_a_cell_in_another_column_filled_does_not_count():
    text = "| Chỉ số | Ghi chú | Nguồn |\n| --- | --- | --- |\n| tải 450 req/s | có ghi chú | |\n"
    assert codes(text) == ["number-without-evidence"]


def test_short_rows_and_tables_without_a_separator():
    assert [(f.code, f.line) for f in check("| a | b |\n| tải 450 req/s |\n")] == [("number-without-evidence", 2)]  # no separator: every line is a row
    assert codes("| Chỉ số | Nguồn |\n| --- | --- |\n| tải 450 req/s |\n") == ["number-without-evidence"]


# --- exact phrases that contain a vague word ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Đơn có ít nhất một dòng món.", "Ít nhất 2 món mỗi đơn.", "Dùng kiểu nhỏ nhất đủ cho mốc xa nhất.", "Chọn bảng lớn nhất trước.", "Nhiều nhất một lần thử lại.",
    "- Cần ít  nhất một FR.", "## Ít nhất một luồng",
])
def test_an_exact_phrase_with_a_vague_word_is_not_vague(text):
    assert codes(text) == [], text


@pytest.mark.parametrize("text", ["Có ít món.", "Bảng lớn hơn.", "Hệ thống nhanh nhất.", "Ít nhất một món nhưng hệ thống nhanh.", "Nhiều khách."])
def test_the_bare_word_and_other_superlatives_stay_vague(text):
    assert codes(text) == ["vague-word"], text


def test_the_exempt_phrases_come_from_the_data_file(tmp_path):
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert {"ít nhất", "nhiều nhất", "lớn nhất", "nhỏ nhất"} <= set(data["exempt_phrases"])
    cfg, _ = cn.load_config(write_config(tmp_path, exempt_phrases=[]))
    assert codes("Đơn có ít nhất một dòng món.", cfg=cfg) == ["vague-word"]
    cfg, _ = cn.load_config(write_config(tmp_path, exempt_phrases=["nhanh nhất"]))
    assert codes("Hệ thống nhanh nhất.", cfg=cfg) == []


# --- an NFR or a constraint in the same sentence, item or row is evidence ---------------------------------------------------------------

KNOWN = {"NFR-001", "C-001", "TC-001", "R-01"}


@pytest.mark.parametrize("text", [
    "p95 dưới 300 ms (NFR-001).", "Ngân sách 300 USD theo C-001.", "- Mục tiêu 300 ms, truy về NFR-001.", "## p95 dưới 300 ms, NFR-001",
    "| Chỉ số | Mục tiêu | NFR |\n| --- | --- | --- |\n| p95 | dưới 300 ms | NFR-001 |\n",
])
def test_a_defined_nfr_or_constraint_is_evidence_for_a_number(text):
    assert codes(text, known=KNOWN) == [], text


@pytest.mark.parametrize("text", [
    "p95 dưới 300 ms (NFR-009).", "p95 dưới 300 ms. Xem NFR-001.", "p95 dưới 300 ms theo TC-001.", "p95 dưới 300 ms theo R-01.", "p95 dưới 300 ms theo D-001.",
    "| Chỉ số | Mục tiêu |\n| --- | --- |\n| p95 | dưới 300 ms |\n| p99 | NFR-001 |\n",
])
def test_an_undefined_or_other_id_or_one_in_another_sentence_or_row_is_not(text):
    assert codes(text, known=KNOWN) == ["number-without-evidence"], text


def test_without_the_set_of_defined_ids_any_nfr_counts():
    assert codes("p95 dưới 300 ms (NFR-009).", known=None) == []


def test_the_kinds_that_count_come_from_the_data_file(tmp_path):
    cfg, _ = cn.load_config(write_config(tmp_path, evidence_id_kinds=[]))
    assert codes("p95 dưới 300 ms (NFR-001).", cfg=cfg, known=KNOWN) == ["number-without-evidence"]
    cfg, _ = cn.load_config(write_config(tmp_path, evidence_id_kinds=["TC"]))
    assert codes("p95 dưới 300 ms (TC-001).", cfg=cfg, known=KNOWN) == []


# --- the basis ("cơ sở") column: only an ID or a link counts -----------------------------------------------------------------------------

BASIS = "| Mục | Giá trị | {col} |\n| --- | --- | --- |\n| chờ | 2 giây | {cell} |\n"


@pytest.mark.parametrize("col", ["Cơ sở", "Cơ sở ước tính", "**Cơ sở**", "cơ sở thiết kế"])
@pytest.mark.parametrize("cell", ["NFR-001", "C-001", "TC-001", "R-01", "D-001", "A-peak", "NFR-001, kinh nghiệm team", "[tài liệu](https://example.com/docs)",
                                  "https://example.com/docs", "`C-001`"])
def test_a_basis_cell_with_an_id_or_a_link_makes_the_row_pass(col, cell):
    assert codes(BASIS.format(col=col, cell=cell), defined={"A-peak"}, known=KNOWN) == [], (col, cell)


@pytest.mark.parametrize("cell", ["kinh nghiệm team", "ước tính của BA", "theo tài liệu", "", "-", "—", "chưa có", "FR-001", "T-003", "NFR-009", "C-009", "A-other"])
def test_a_basis_cell_with_words_only_or_an_undefined_id_does_not(cell):
    assert codes(BASIS.format(col="Cơ sở", cell=cell), defined={"A-peak"}, known=KNOWN) == ["number-without-evidence"], cell
    assert codes(BASIS.format(col="Cơ sở ước tính", cell=cell), defined={"A-peak"}, known=KNOWN) == ["number-without-evidence"], cell


def test_a_free_text_evidence_column_still_takes_words_and_the_basis_column_is_not_one_of_them():
    both = "| Mục | Giá trị | Nguồn | Cơ sở |\n| --- | --- | --- | --- |\n| chờ | 2 giây | BA mục 3 | kinh nghiệm team |\n"
    assert codes(both, known=KNOWN) == []
    assert codes(TABLE.format(col="Nguồn", cell="BA mục 3"), known=KNOWN) == []


def test_a_basis_cell_is_not_shared_with_the_next_row():
    text = "| Mục | Giá trị | Cơ sở |\n| --- | --- | --- |\n| a | 2 giây | NFR-001 |\n| b | 3 giây | |\n"
    assert [f.line for f in check(text, known=KNOWN)] == [4]


def test_the_basis_columns_and_kinds_come_from_the_data_file(tmp_path):
    cfg, _ = cn.load_config(write_config(tmp_path, basis_columns=["lý do"], basis_id_kinds=["NFR"], evidence_id_kinds=[]))
    assert codes(BASIS.format(col="Lý do", cell="NFR-001"), cfg=cfg, known=KNOWN) == []
    assert codes(BASIS.format(col="Lý do", cell="C-001"), cfg=cfg, known=KNOWN) == ["number-without-evidence"]
    assert codes(BASIS.format(col="Lý do", cell="kinh nghiệm"), cfg=cfg, known=KNOWN) == ["number-without-evidence"]
    assert codes(BASIS.format(col="Cơ sở", cell="kinh nghiệm"), cfg=cfg, known=KNOWN) == ["number-without-evidence"]


def test_an_old_data_file_without_the_new_keys_still_loads(tmp_path):
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for key in ("exempt_phrases", "evidence_id_kinds", "basis_columns", "basis_id_kinds"):
        data.pop(key)
    path = tmp_path / "old.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    cfg, errors = cn.load_config(path)
    assert cfg is not None and not errors
    assert codes("Đơn có ít nhất một món.", cfg=cfg) == ["vague-word"]
    assert codes("p95 dưới 300 ms (NFR-001).", cfg=cfg) == ["number-without-evidence"]


@pytest.mark.parametrize("override", [{"evidence_id_kinds": ["XYZ"]}, {"basis_id_kinds": ["NFR", "XYZ"]}, {"exempt_phrases": "ít nhất"}, {"basis_columns": [1]}])
def test_a_bad_new_key_is_reported(tmp_path, override):
    cfg, errors = cn.load_config(write_config(tmp_path, **override))
    assert cfg is None and errors


def test_end_to_end_ids_are_checked_against_what_the_drafts_define(tmp_path):
    workspace = make_workspace(tmp_path)
    drafts = workspace / "drafts"
    (drafts / "00-context" / "quality-attributes.md").write_text("# NFR\n\n| ID | Chỉ tiêu | Nguồn |\n| --- | --- | --- |\n| NFR-001 | p95 dưới 300 ms | BA |\n", encoding="utf-8")
    (drafts / "x.md").write_text("Mục tiêu p95 dưới 300 ms (NFR-001).\n\n| Mục | Giá trị | Cơ sở |\n| --- | --- | --- |\n| chờ | 2 giây | NFR-001 |\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 0, result.stdout
    (drafts / "y.md").write_text("Mục tiêu p95 dưới 300 ms (NFR-777).\n\n| Mục | Giá trị | Cơ sở |\n| --- | --- | --- |\n| chờ | 2 giây | NFR-777 |\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 1 and result.stdout.count("y.md") == 2


# --- what is not checked -----------------------------------------------------------------------------------------------------------------

def test_fenced_code_comments_and_empty_calc_blocks_are_skipped():
    text = ("```\nCần 300 MB nhanh\n```\n\n~~~\nlớn 5 GB\n~~~\n\n<!-- Cần 300 MB, nhanh -->\n\n<!-- required -->\n\n"
            "<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n\nHết.\n")
    assert codes(text) == []


def test_text_after_a_block_still_counts_and_lines_stay_right():
    text = "<!-- BEGIN:calc:t -->\nchờ script\n<!-- END:calc:t -->\n\n\nSau khối: 300 MB.\n"
    found = check(text)
    assert [(f.code, f.line) for f in found] == [("number-without-evidence", 6)]
    found = check("<!-- ghi chú\nnhiều dòng -->\nTải 10 MB.\n")
    assert found[0].line == 3


def test_inline_code_is_still_checked():
    assert codes("Đặt `max_connections` là 200 connections.") == ["number-without-evidence"]


def test_blockquotes_are_text():
    assert codes("> Tải 450 req/s.\n") == ["number-without-evidence"]


# --- vague words -------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("word", ["nhanh", "chậm", "lớn", "nhỏ", "nhiều", "ít", "đủ dùng", "đủ nhanh", "đủ lớn", "scale tốt", "hiệu năng cao", "hiệu năng tốt", "mượt"])
def test_every_listed_word_without_a_number_is_flagged(word):
    assert codes(f"Hệ thống cần {word} khi vận hành.") == ["vague-word"], word


@pytest.mark.parametrize("text", [
    "Hệ thống phải nhanh: p95 dưới 300 ms.", "Dữ liệu lớn hơn 100 GB = 5 × 20 GB.", "Cần đủ dùng cho 10.000 người dùng (A-dau).", "Scale tốt tới 5 instance.",
    "Tải nhiều hơn 3 lần.",
])
def test_a_number_in_the_same_sentence_makes_a_vague_word_pass(text):
    assert [f.code for f in check(text, defined={"A-dau"}) if f.code == "vague-word"] == [], text


def test_digits_inside_ids_and_urls_are_not_numbers():
    assert codes("Hệ thống nhanh (NFR-001).") == ["vague-word"]
    assert codes("Hệ thống nhanh (TC-03, R-04, 2026-10-12).") == ["vague-word"]
    assert codes("Hệ thống nhanh, xem [docs](https://example.com/16/x).") == ["vague-word"]


def test_digits_in_a_relative_link_and_in_a_bare_url_are_not_numbers_either():
    assert codes("Hệ thống nhanh, xem [chi tiết](docs/16/limits.md).") == ["vague-word"]
    assert codes("Hệ thống nhanh, xem https://example.com/16/limits.") == ["vague-word"]
    assert codes("Hệ thống nhanh, xem <https://example.com/16/limits>.") == ["vague-word"]


def test_a_unit_must_be_a_whole_word():
    assert codes("Có 3 bảng và 5 server, 2 sessionx, 7 mbx.") == []
    assert codes("Có 5 s.") == ["number-without-evidence"]
    assert codes("Có 5 sessions, 3 GB.") == ["number-without-evidence"]


def test_vague_words_are_whole_words_and_case_insensitive():
    assert codes("Hệ thống NHANH và Lớn.") == ["vague-word"]
    assert codes("Nhanh") == ["vague-word"]
    assert codes("Đi nhanhhh qua.") == []  # not the word
    assert codes("Quá chậmchạp.") == []
    assert codes("Hệ thống scale  tốt.") == ["vague-word"]  # spacing inside a phrase


def test_the_words_are_matched_after_unicode_normalisation():
    import unicodedata
    assert codes(unicodedata.normalize("NFD", "Hệ thống đủ dùng.")) == ["vague-word"]


def test_a_number_in_another_sentence_or_row_does_not_help():
    assert codes("Hệ thống nhanh. Có 300 ms ở chỗ khác.") == ["vague-word", "number-without-evidence"]
    assert [f.code for f in check("| a | b |\n| --- | --- |\n| nhanh | |\n| ok | 300 |\n")] == ["vague-word"]


def test_a_vague_word_in_a_table_row_passes_with_a_number_in_the_row():
    text = "| Yêu cầu | Chỉ số |\n| --- | --- |\n| Phản hồi nhanh | 300 |\n| Phản hồi nhanh | |\n"
    assert [(f.code, f.line) for f in check(text)] == [("vague-word", 4)]


def test_vague_words_in_headings_and_items():
    assert codes("## Hiệu năng cao\n") == ["vague-word"]
    assert codes("- Tải lớn\n- Tải lớn 5 GB = 5 × 1 GB\n") == ["vague-word"]


def test_all_words_of_one_context_are_listed_in_one_finding():
    found = check("Cần nhanh, lớn và mượt.")
    assert len(found) == 1 and all(w in found[0].message for w in ("nhanh", "lớn", "mượt"))


def test_vague_words_in_code_and_comments_are_ignored():
    assert codes("```\nnhanh\n```\n<!-- nhanh -->\n") == []


# --- assumptions.md against assumptions.yaml --------------------------------------------------------------------------------------------

def make_workspace(tmp_path: Path, md: str | None = "generate", yaml_text: str | None = "sample", level: str | None = "M") -> Path:
    workspace = tmp_path / ".agent-workspace"
    (workspace / "capacity").mkdir(parents=True)
    drafts = workspace / "drafts"
    (drafts / "00-context").mkdir(parents=True)
    if level:
        (drafts / "00-context" / "project-profile.md").write_text(f"# Hồ sơ\n\n- **Mức:** {level}\n", encoding="utf-8")
    if yaml_text is not None:
        text = (DATA / "capacity" / "assumptions.yaml").read_text(encoding="utf-8") if yaml_text == "sample" else yaml_text
        (workspace / "capacity" / "assumptions.yaml").write_text(text, encoding="utf-8")
    if md == "generate":
        problems = cc.Problems()
        parsed = cc.parse_assumptions(yaml.safe_load((workspace / "capacity" / "assumptions.yaml").read_text(encoding="utf-8")), level, problems)
        assert parsed is not None, problems.items
        md = cc.render_assumptions(parsed, level)
    if md is not None:
        (drafts / "00-context" / "assumptions.md").write_text(md, encoding="utf-8", newline="")
    return workspace


def md_findings(found: list[cn.Finding]) -> list[cn.Finding]:
    """Only the findings about assumptions.md against assumptions.yaml (a file that does not match is also checked like any file)."""
    return [f for f in found if f.code.startswith("assumptions-")]


def run_all(workspace: Path) -> list[cn.Finding]:
    return cn.run(workspace / "drafts", workspace, CFG)[0]


def test_assumptions_md_in_step_with_yaml_is_clean(tmp_path):
    assert run_all(make_workspace(tmp_path)) == []


def test_generated_md_from_calc_capacity_matches(tmp_path):
    """The file calc_capacity.py itself writes is exactly what check_numbers expects."""
    workspace = tmp_path / ".agent-workspace"
    (workspace / "capacity" / "db-constants").mkdir(parents=True)
    for name in ("assumptions", "tables", "storage", "compute", "pricing"):
        (workspace / "capacity" / f"{name}.yaml").write_text((DATA / "capacity" / f"{name}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (workspace / "capacity" / "db-constants" / "postgresql-16.yaml").write_text((DATA / "db-constants" / "postgresql-16.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (workspace / "drafts" / "00-context").mkdir(parents=True)
    (workspace / "drafts" / "00-context" / "project-profile.md").write_text("# H\n\n- **Mức:** M\n", encoding="utf-8")
    assert cc.main(["--workspace", str(workspace), "--date", "2026-10-12"]) == 0
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    assert findings == [] and stats.generated_files == 6


def test_crlf_in_assumptions_md_is_tolerated(tmp_path):
    workspace = make_workspace(tmp_path)
    path = workspace / "drafts" / "00-context" / "assumptions.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert run_all(workspace) == []


@pytest.mark.parametrize("old,new", [("10,000", "11,000"), ("| A-dau |", "| A-dau2 |"), ("inputs/ba/prd.md mục 3.1", "ở đâu đó"), ("người dùng", "user"), ("| 120 |", "| 121 |")])
def test_a_changed_cell_is_a_mismatch_with_a_useful_message(tmp_path, old, new):
    workspace = make_workspace(tmp_path)
    path = workspace / "drafts" / "00-context" / "assumptions.md"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    found = md_findings(run_all(workspace))
    assert [f.code for f in found] == ["assumptions-md-mismatch"]
    assert new in found[0].message and "calc_capacity.py" in found[0].message and found[0].path == "00-context/assumptions.md"


def test_an_added_removed_or_reordered_row_is_a_mismatch(tmp_path):
    workspace = make_workspace(tmp_path)
    path = workspace / "drafts" / "00-context" / "assumptions.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [i for i, l in enumerate(lines) if l.startswith("| A-")]
    removed = lines[:rows[1]] + lines[rows[1] + 1:]
    path.write_text("\n".join(removed) + "\n", encoding="utf-8")
    assert [f.code for f in md_findings(run_all(workspace))] == ["assumptions-md-mismatch"]
    added = lines + ["| A-extra | thêm | lần | 1 | 1 | 1 | tay |"]
    path.write_text("\n".join(added) + "\n", encoding="utf-8")
    found = md_findings(run_all(workspace))
    assert [f.code for f in found] == ["assumptions-md-mismatch"] and "không có trong yaml" in found[0].message and "A-extra" in found[0].message
    swapped = list(lines)
    swapped[rows[0]], swapped[rows[1]] = swapped[rows[1]], swapped[rows[0]]
    path.write_text("\n".join(swapped) + "\n", encoding="utf-8")
    assert [f.code for f in md_findings(run_all(workspace))] == ["assumptions-md-mismatch"]


def test_the_yaml_changed_after_md_was_generated_is_a_mismatch(tmp_path):
    workspace = make_workspace(tmp_path)
    path = workspace / "capacity" / "assumptions.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("value: 120", "value: 150"), encoding="utf-8")
    assert [f.code for f in md_findings(run_all(workspace))] == ["assumptions-md-mismatch"]


def test_md_missing_and_yaml_missing_and_yaml_invalid(tmp_path):
    assert [f.code for f in run_all(make_workspace(tmp_path / "a", md=None))] == ["assumptions-md-missing"]
    workspace = make_workspace(tmp_path / "b", yaml_text=None, md="# Giả định\n")
    assert "assumptions-yaml-missing" in [f.code for f in run_all(workspace)]
    bad = make_workspace(tmp_path / "c", yaml_text="assumptions: []\nmilestones: [launch]\n", md="# Giả định\n")
    found = run_all(bad)
    assert found and all(f.code == "assumptions-yaml-invalid" for f in found)
    broken = make_workspace(tmp_path / "d", yaml_text="a: [unclosed\n", md="# Giả định\n")
    assert [f.code for f in run_all(broken)][0] == "assumptions-yaml-invalid"


def test_the_level_of_the_profile_is_part_of_what_is_generated(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "drafts" / "00-context" / "project-profile.md").write_text("# H\n\n- **Mức:** S\n", encoding="utf-8")
    assert [f.code for f in md_findings(run_all(workspace))] == ["assumptions-md-mismatch"]  # "Mức dự án: M" is in the file


def test_a_yaml_that_breaks_the_level_milestones_is_invalid(tmp_path):
    workspace = make_workspace(tmp_path, md=None, level="L")
    found = run_all(workspace)
    assert found and found[0].code == "assumptions-yaml-invalid" and "mức L" in found[0].message


# --- through the folder -------------------------------------------------------------------------------------------------------------------

def test_assumption_ids_of_the_yaml_are_evidence_in_drafts(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "drafts" / "ctx.md").write_text("Có 10.000 người dùng mỗi ngày (A-dau).\nCó 10.000 người dùng mỗi ngày (A-không-có).\n", encoding="utf-8")
    assert [(f.path, f.line) for f in run_all(workspace)] == [("ctx.md", 2)]


def test_when_the_yaml_is_unreadable_assumption_refs_are_not_judged(tmp_path):
    workspace = make_workspace(tmp_path, yaml_text="a: [unclosed\n", md="# x\n")
    (workspace / "drafts" / "ctx.md").write_text("Có 10.000 người dùng mỗi ngày (A-dau).\n", encoding="utf-8")
    assert [f.code for f in run_all(workspace)] == ["assumptions-yaml-invalid"]


# --- what calc_capacity.py wrote is exempt only when it is proven ---------------------------------------------------------------------------

TABLES_MD = "# tables\n\nGhi chú Designer.\n\n<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n\nHết.\n"
FIELD_MARK = "<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->"


def make_full(tmp_path: Path, tables_md: str | None = TABLES_MD) -> Path:
    """A workspace where calc_capacity.py has written its six documents (and the block of tables.md)."""
    workspace = tmp_path / ".agent-workspace"
    (workspace / "capacity" / "db-constants").mkdir(parents=True)
    for name in ("assumptions", "tables", "storage", "compute", "pricing"):
        (workspace / "capacity" / f"{name}.yaml").write_text((DATA / "capacity" / f"{name}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (workspace / "capacity" / "db-constants" / "postgresql-16.yaml").write_text((DATA / "db-constants" / "postgresql-16.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (workspace / "drafts" / "00-context").mkdir(parents=True)
    (workspace / "drafts" / "00-context" / "project-profile.md").write_text("# H\n\n- **Mức:** M\n", encoding="utf-8")
    if tables_md is not None:
        path = workspace / "drafts" / "07-data" / "databases" / "order-db" / "tables.md"
        path.parent.mkdir(parents=True)
        path.write_text(tables_md, encoding="utf-8", newline="")
    assert cc.main(["--workspace", str(workspace), "--date", "2026-10-12"]) == 0
    return workspace


def draft_path(workspace: Path, rel: str) -> Path:
    return workspace / "drafts" / rel


def by_code(found: list[cn.Finding]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for f in found:
        result.setdefault(f.code, []).append(f.path)
    return result


def test_the_six_files_and_the_block_are_exempt_when_they_match_the_recomputation(tmp_path):
    workspace = make_full(tmp_path)
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    assert findings == [] and stats.generated_files == 6
    assert cc.OUTPUT_FILES == tuple(sorted(cc.OUTPUT_FILES, key=lambda r: cc.OUTPUT_FILES.index(r))) and len(cc.OUTPUT_FILES) == 6
    text = draft_path(workspace, "07-data/databases/order-db/tables.md").read_text(encoding="utf-8")
    assert "MiB" in text  # the block holds numbers with units and nothing is reported


def test_output_files_are_exactly_what_render_all_produces(tmp_path):
    workspace = make_full(tmp_path)
    problems = cc.Problems()
    inputs = cc.load_inputs(workspace, workspace / "capacity" / "db-constants", problems)
    assert inputs is not None and set(cc.render_all(inputs, problems).files) == set(cc.OUTPUT_FILES)


def test_crlf_in_generated_files_and_blocks_is_still_proof(tmp_path):
    workspace = make_full(tmp_path)
    for rel in (*cc.OUTPUT_FILES, "07-data/databases/order-db/tables.md"):
        path = draft_path(workspace, rel)
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    assert findings == [] and stats.generated_files == 6


def test_the_marker_line_in_another_file_proves_nothing(tmp_path):
    workspace = make_full(tmp_path)
    (workspace / "drafts" / "x.md").write_text(f"# X\n\n{FIELD_MARK}\n\nCần 300 MB. Hệ thống nhanh.\n", encoding="utf-8")
    (workspace / "drafts" / "03-capacity" / "extra.md").write_text(f"# X\n\n{FIELD_MARK}\n\nCần 300 MB. Hệ thống nhanh.\n", encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found == {"number-without-evidence": ["03-capacity/extra.md", "x.md"], "vague-word": ["03-capacity/extra.md", "x.md"]}


def test_a_file_at_a_generated_path_that_only_copies_the_marker_is_edited(tmp_path):
    workspace = make_full(tmp_path)
    draft_path(workspace, "03-capacity/data-sizing.md").write_text(f"# Dung lượng\n\n{FIELD_MARK}\n\nCần 300 MB. Hệ thống nhanh.\n", encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found == {"generated-file-edited": ["03-capacity/data-sizing.md"], "number-without-evidence": ["03-capacity/data-sizing.md"], "vague-word": ["03-capacity/data-sizing.md"]}


def test_a_generated_file_edited_by_hand_is_reported_and_then_checked_like_any_file(tmp_path):
    workspace = make_full(tmp_path)
    path = draft_path(workspace, "03-capacity/cost-model.md")
    path.write_text(path.read_text(encoding="utf-8") + "\nThêm tay: cần 300 MB. Hệ thống nhanh.\n", encoding="utf-8")
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    found = by_code(findings)
    assert found["generated-file-edited"] == ["03-capacity/cost-model.md"]
    assert "number-without-evidence" in found and "vague-word" in found and stats.generated_files == 5
    edited = next(f for f in findings if f.code == "generated-file-edited")
    assert "file sinh bị sửa tay" in edited.message


def test_one_changed_digit_in_a_generated_table_is_enough(tmp_path):
    workspace = make_full(tmp_path)
    path = draft_path(workspace, "03-capacity/workload-model.md")
    text = path.read_text(encoding="utf-8")
    assert "| 120 | 120 | 120 |" in text
    path.write_text(text.replace("| 120 | 120 | 120 |", "| 120 | 120 | 121 |"), encoding="utf-8")
    assert "generated-file-edited" in by_code(cn.run(workspace / "drafts", workspace, CFG)[0])


def test_when_the_inputs_change_after_generation_the_old_files_are_no_longer_proven(tmp_path):
    workspace = make_full(tmp_path)
    path = workspace / "capacity" / "pricing.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("unit_price: 70", "unit_price: 75"), encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found["generated-file-edited"] == ["03-capacity/cost-model.md"]


def test_a_missing_generated_file_is_not_this_scripts_business(tmp_path):
    workspace = make_full(tmp_path)
    draft_path(workspace, "03-capacity/storage-sizing.md").unlink()
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    assert findings == [] and stats.generated_files == 5


def test_when_calc_capacity_cannot_recompute_its_files_cannot_be_proven(tmp_path):
    workspace = make_full(tmp_path)
    (workspace / "capacity" / "pricing.yaml").write_text("items: {}\n", encoding="utf-8")
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    found = by_code(findings)
    assert sorted(found["generated-file-unverified"]) == sorted(r for r in cc.OUTPUT_FILES if r != "00-context/assumptions.md")
    assert "generated-file-edited" not in found and "assumptions-md-mismatch" not in found
    assert stats.generated_files == 1  # assumptions.md still matches what assumptions.yaml alone produces
    assert found["calc-block-unverified"] == ["07-data/databases/order-db/tables.md"]  # the block is filled, so it cannot be proven either


def test_a_filled_block_that_cannot_be_recomputed_is_unverified(tmp_path):
    workspace = make_full(tmp_path)
    (workspace / "capacity" / "pricing.yaml").write_text("items: {}\n", encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found.get("calc-block-unverified") == ["07-data/databases/order-db/tables.md"]


def test_a_block_edited_by_hand_is_reported_and_its_text_is_checked(tmp_path):
    workspace = make_full(tmp_path)
    path = draft_path(workspace, "07-data/databases/order-db/tables.md")
    path.write_text(path.read_text(encoding="utf-8").replace("Hết.", "Hết.").replace("\n- Cột `id`", "\nThêm tay: cần 300 MB. Hệ thống nhanh.\n- Cột `id`"), encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found["calc-block-edited"] == ["07-data/databases/order-db/tables.md"]
    assert "number-without-evidence" in found and "vague-word" in found


def test_a_calc_block_pasted_into_another_file_proves_nothing(tmp_path):
    workspace = make_full(tmp_path)
    block = draft_path(workspace, "07-data/databases/order-db/tables.md").read_text(encoding="utf-8")
    block = block[block.index("<!-- BEGIN:calc:orders -->"): block.index("<!-- END:calc:orders -->") + len("<!-- END:calc:orders -->")]
    (workspace / "drafts" / "x.md").write_text(f"# X\n\n{block}\n", encoding="utf-8")
    other = workspace / "drafts" / "07-data" / "databases" / "other-db"
    other.mkdir()
    (other / "tables.md").write_text(f"# T\n\n{block}\n", encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert sorted(found["calc-block-edited"]) == ["07-data/databases/other-db/tables.md", "x.md"]


def test_an_invented_block_with_numbers_is_reported_and_checked(tmp_path):
    workspace = make_full(tmp_path)
    (workspace / "drafts" / "y.md").write_text("# Y\n\n<!-- BEGIN:calc:t -->\nDung lượng 300 MB.\n<!-- END:calc:t -->\n", encoding="utf-8")
    found = by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert found == {"calc-block-edited": ["y.md"], "number-without-evidence": ["y.md"]}


def test_pending_blocks_need_no_proof(tmp_path):
    workspace = make_full(tmp_path)
    (workspace / "drafts" / "y.md").write_text("# Y\n\n<!-- BEGIN:calc:t -->\nchờ script\n<!-- END:calc:t -->\n\n<!-- BEGIN:calc:u -->\n<!-- chờ script -->\n<!-- END:calc:u -->\n", encoding="utf-8")
    assert cn.run(workspace / "drafts", workspace, CFG)[0] == []


def test_an_empty_block_is_not_proof_of_anything(tmp_path):
    findings = check("<!-- BEGIN:calc:t -->\n<!-- END:calc:t -->\nTải 10 MB.\n", blocks={"t": ""})
    assert sorted(f.code for f in findings) == ["calc-block-edited", "number-without-evidence"]


def test_a_hand_edited_assumptions_md_is_a_mismatch_and_not_exempt(tmp_path):
    workspace = make_full(tmp_path)
    path = draft_path(workspace, "00-context/assumptions.md")
    path.write_text(path.read_text(encoding="utf-8").replace("| 120 | 120 | 120 |", "| 121 | 121 | 121 |"), encoding="utf-8")
    findings, stats = cn.run(workspace / "drafts", workspace, CFG)
    found = by_code(findings)
    assert found["assumptions-md-mismatch"] == ["00-context/assumptions.md"] and "generated-file-edited" not in found
    assert stats.generated_files == 5
    mismatch = next(f for f in findings if f.code == "assumptions-md-mismatch")
    assert "file sinh bị sửa tay" in mismatch.message


def test_constants_dir_option_lets_the_recomputation_find_the_constants(tmp_path):
    workspace = make_full(tmp_path)
    moved = tmp_path / "knowledge"
    moved.mkdir()
    (workspace / "capacity" / "db-constants" / "postgresql-16.yaml").replace(moved / "postgresql-16.yaml")
    assert "generated-file-unverified" in by_code(cn.run(workspace / "drafts", workspace, CFG)[0])
    assert cn.run(workspace / "drafts", workspace, CFG, moved)[0] == []
    assert run_cli("--workspace", str(workspace)).returncode == 1
    assert run_cli("--workspace", str(workspace), "--constants-dir", str(moved)).returncode == 0


def test_the_profile_level_of_the_scanned_root_is_used(tmp_path):
    """Scanning architecture/ (not drafts/): the Mức in architecture/00-context/project-profile.md is the one printed in the files."""
    workspace = make_full(tmp_path)
    arch = tmp_path / "architecture"
    import shutil
    shutil.copytree(workspace / "drafts", arch)
    shutil.rmtree(workspace / "drafts")
    (workspace / "drafts").mkdir()
    findings, stats = cn.run(arch, workspace, CFG)
    assert findings == [] and stats.generated_files == 6


# --- English vague words, and the word that must stay allowed ----------------------------------------------------------------------------------

@pytest.mark.parametrize("word", ["fast", "slow", "large", "small", "big", "huge", "quick", "quickly", "scalable", "scales well", "scale well",
                                  "high performance", "good performance", "enough", "sufficient", "adequate", "many", "few", "smooth"])
def test_english_vague_words_are_flagged(word):
    assert codes(f"The system must be {word} in use.") == ["vague-word"], word
    assert codes(f"The system must be {word.upper()} in use.") == ["vague-word"]
    assert codes(f"The system must be {word}: p95 = 300 ms.") == []  # a number (with its formula) in the sentence


def test_optimisation_words_are_not_vague_words_because_toi_uu_is_a_required_section():
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for word in data["vague_words"]:
        assert word.casefold() not in ("tối ưu", "optimal", "optimize", "optimise", "optimization", "optimisation", "optimized", "optimised", "tối ưu hóa")
    assert codes("## Tối ưu\n") == [] and codes("## Optimization\n") == [] and codes("Tối ưu hóa truy vấn.\n") == []


def test_the_vietnamese_list_is_kept():
    data = yaml.safe_load(cn.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for word in ("nhanh", "chậm", "lớn", "nhỏ", "nhiều", "ít", "đủ dùng", "đủ nhanh", "đủ lớn", "scale tốt", "hiệu năng cao", "hiệu năng tốt", "mượt"):
        assert word in data["vague_words"]


def test_english_words_are_whole_words():
    assert codes("A manyfold gain, a fewer-than-expected result, enoughness, smoothly done.") == []


# --- the script ----------------------------------------------------------------------------------------------------------------------------

def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_cli_exit_codes_and_report(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "drafts" / "x.md").write_text("Tải 450 req/s. Hệ thống nhanh.\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 1 and "number-without-evidence" in result.stdout and "vague-word" in result.stdout
    report = (workspace / "checks" / "numbers-2026-10-12.md").read_text(encoding="utf-8")
    assert "x.md:1" in report and "## Lỗi chặn" in report and "1 số có đơn vị" in report
    (workspace / "drafts" / "x.md").write_text("Tải 450 req/s, nguồn [BA](inputs/ba.md).\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 0 and "0 lỗi chặn" in result.stdout


def test_cli_config_option_and_errors(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "drafts" / "x.md").write_text("Hệ thống siêu việt.\n", encoding="utf-8")
    assert run_cli("--workspace", str(workspace)).returncode == 0
    custom = write_config(tmp_path, vague_words=["siêu việt"])
    assert run_cli("--workspace", str(workspace), "--config", str(custom)).returncode == 1
    result = run_cli("--workspace", str(workspace), "--config", str(tmp_path / "none.yaml"))
    assert result.returncode == 2 and "config error" in result.stderr
    assert run_cli("--workspace", str(workspace), "--root", str(tmp_path / "none")).returncode == 2


def test_cli_root_option_scans_another_folder(tmp_path):
    workspace = make_workspace(tmp_path)
    arch = tmp_path / "architecture" / "00-context"
    arch.mkdir(parents=True)
    (arch / "assumptions.md").write_text((workspace / "drafts" / "00-context" / "assumptions.md").read_text(encoding="utf-8"), encoding="utf-8")
    (arch / "project-profile.md").write_text("# H\n\n- **Mức:** M\n", encoding="utf-8")
    (tmp_path / "architecture" / "y.md").write_text("Cần 5 GB.\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--root", str(tmp_path / "architecture"))
    assert result.returncode == 1 and "y.md" in result.stdout


def test_cli_lists_at_most_25_findings(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "drafts" / "x.md").write_text("".join(f"- Cần {i} GB.\n" for i in range(1, 41)), encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.stdout.count("error: `") == 25 and "15 lỗi nữa" in result.stdout
    assert (workspace / "checks" / "numbers-2026-10-12.md").read_text(encoding="utf-8").count("[number-without-evidence]") == 40


def test_runs_under_uv_with_its_own_dependencies(tmp_path):
    import shutil
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv not installed")
    workspace = make_workspace(tmp_path)
    result = subprocess.run([uv, "run", "--quiet", "--no-project", str(SCRIPT), "--workspace", str(workspace)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_a_derived_assumption_is_sourced_by_its_formula_column(tmp_path):
    data = yaml.safe_load((DATA / "capacity" / "assumptions.yaml").read_text(encoding="utf-8"))
    data["assumptions"] += [{"id": "A-ratio", "description": "Tỉ lệ", "unit": "tỉ lệ", "value": 0.2, "source": "người dùng duyệt ở G1"},
                            {"id": "A-derived", "description": "Số người dùng hoạt động", "unit": "người dùng", "derived": {"product": ["A-orders-per-day", "A-ratio"]}}]
    workspace = make_workspace(tmp_path, yaml_text=yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    text = (workspace / "drafts" / "00-context" / "assumptions.md").read_text(encoding="utf-8")
    assert "A-orders-per-day × A-ratio" in text
    assert run_all(workspace) == []
