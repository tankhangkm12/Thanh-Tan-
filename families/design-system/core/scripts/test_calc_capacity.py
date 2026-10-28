"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import calc_capacity as cc  # noqa: E402
import check_links as cl  # noqa: E402

HERE = Path(__file__).parent
DATA = HERE / "test_data"
SCRIPT = HERE / "calc_capacity.py"
TABLES_MD = "# tables\n\nGhi chú Designer.\n\n<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n\nHết.\n"
FILES = ("assumptions", "tables", "storage", "compute", "pricing")
OUTPUTS = ("00-context/assumptions.md", "03-capacity/workload-model.md", "03-capacity/data-sizing.md", "03-capacity/storage-sizing.md",
           "03-capacity/compute-sizing.md", "03-capacity/cost-model.md")


def sample(name: str) -> dict:
    return yaml.safe_load((DATA / "capacity" / f"{name}.yaml").read_text(encoding="utf-8"))


def make(tmp_path: Path, level: str | None = "M", tables_md: str | None = TABLES_MD, mutate=None, constants=None) -> Path:
    """A workspace with the sample capacity files; mutate(files) may change the parsed yaml dicts, constants(dict) the constants."""
    workspace = tmp_path / ".agent-workspace"
    files = {n: sample(n) for n in FILES}
    consts = yaml.safe_load((DATA / "db-constants" / "postgresql-16.yaml").read_text(encoding="utf-8"))
    if mutate:
        mutate(files)
    if constants:
        constants(consts)
    (workspace / "capacity" / "db-constants").mkdir(parents=True)
    for n, data in files.items():
        (workspace / "capacity" / f"{n}.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (workspace / "capacity" / "db-constants" / "postgresql-16.yaml").write_text(yaml.safe_dump(consts, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if level:
        (workspace / "drafts" / "00-context").mkdir(parents=True)
        (workspace / "drafts" / "00-context" / "project-profile.md").write_text(f"# Hồ sơ\n\n- **Mức:** {level}\n", encoding="utf-8")
    if tables_md is not None:
        path = workspace / "drafts" / "07-data" / "databases" / "order-db" / "tables.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(tables_md.encode("utf-8"))
    return workspace


def run(workspace: Path, *args: str) -> int:
    return cc.main(["--workspace", str(workspace), "--date", "2026-10-12", *args])


def draft(workspace: Path, rel: str) -> str:
    return (workspace / "drafts" / rel).read_text(encoding="utf-8")


def report(workspace: Path) -> str:
    return (workspace / "checks" / "capacity-2026-10-12.md").read_text(encoding="utf-8")


def snapshot(workspace: Path) -> dict[str, bytes]:
    return {p.relative_to(workspace).as_posix(): p.read_bytes() for p in sorted(workspace.rglob("*")) if p.is_file() and "checks" not in p.parts}


# --- the numbers, by hand ----------------------------------------------------------------------------------------------------

def test_a_complete_run_writes_every_document(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    for rel in OUTPUTS:
        assert (workspace / "drafts" / rel).is_file(), rel
    assert "0 lỗi chặn" in report(workspace)


def test_row_layout_matches_a_hand_calculation(tmp_path):
    """id integer 4 @0; user_id uuid 16 (align 1) @4; status smallint 2 @20; total_cents bigint 8 padded 22->24; created_at 8; note text 1+40 (short, no padding).
    data = 81; header 23 + null bitmap 1 = 24; tuple = ceil8(24 + 81) = 112; + line pointer 4 = 116; rows/page = floor(8168 / 116) = 70."""
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "= **116 byte/dòng**" in text and "= **70**" in text
    assert "| 4 | total_cents | `bigint` | 8 | 8 | 2 |" in text  # 2 bytes of padding before the bigint
    assert "Dữ liệu các cột (kể cả đệm căn lề): 81 byte; đệm cuối dòng 7 byte" in text


def test_table_and_index_sizes_match_a_hand_calculation(tmp_path):
    """1 year: 10,000 x 365 = 3,650,000 rows; heap pages = ceil(3,650,000 / 70) = 52,143 x 8192 = 427,155,456 byte.
    pkey entry = ceil8(8 + 4) + 4 = 20; per page floor((8192 - 24 - 16) x 0.9 / 20) = 366 -> ceil(3,650,000 / 366) = 9,973 pages = 81,698,816 byte.
    user+created entry = ceil8(8 + 24) + 4 = 36; floor(7336.8 / 36) = 203 -> ceil(3,650,000 / 203) = 17,981 pages = 147,300,352 byte."""
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "| orders_pkey | id | 20 | 366 |" in text and "| orders_user_created_idx | user_id, created_at | 36 | 203 |" in text
    heap, pkey, user = 52_143 * 8192, 9_973 * 8192, 17_981 * 8192
    assert f"| 1 năm | 10,000 | 3,650,000 | 3,650,000 | 52,143 | {cc.size(heap)} |" in text
    assert f"({heap + pkey + user:,} byte)" in text


def test_the_plan_example_ten_thousand_orders_a_day_is_3_65_million_rows_a_year(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    assert "| 1 năm | 10,000 | 3,650,000 | 3,650,000 |" in draft(workspace, "03-capacity/data-sizing.md")


def test_column_order_changes_the_padding():
    consts = cc.Constants("postgresql", 16, "2026-10-12", {k: {"value": v} for k, v in {
        "varlena_short_max_bytes": 126, "varlena_short_header_bytes": 1, "varlena_long_header_bytes": 4, "maxalign_bytes": 8}.items()},
        {"smallint": {"bytes": 2, "align": 2}, "bigint": {"bytes": 8, "align": 8}})
    bad, end_bad = cc.place([("a", "smallint", None, "", ""), ("b", "bigint", None, "", ""), ("c", "smallint", None, "", ""), ("d", "bigint", None, "", "")], consts)
    good, end_good = cc.place([("b", "bigint", None, "", ""), ("d", "bigint", None, "", ""), ("a", "smallint", None, "", ""), ("c", "smallint", None, "", "")], consts)
    assert [p.pad for p in bad] == [0, 6, 0, 6] and end_bad == 32
    assert [p.pad for p in good] == [0, 0, 0, 0] and end_good == 20


def test_long_variable_columns_use_the_four_byte_header_and_int_alignment():
    consts = cc.Constants("postgresql", 16, "2026-10-12", {k: {"value": v} for k, v in {
        "varlena_short_max_bytes": 126, "varlena_short_header_bytes": 1, "varlena_long_header_bytes": 4, "maxalign_bytes": 8}.items()},
        {"smallint": {"bytes": 2, "align": 2}, "text": {"variable": True, "align": 4}})
    placed, end = cc.place([("a", "smallint", None, "", ""), ("t", "text", 126, "", "")], consts)
    assert (placed[1].size, placed[1].align, placed[1].pad, end) == (127, 1, 0, 129)  # 126 is still short
    placed, end = cc.place([("a", "smallint", None, "", ""), ("t", "text", 127, "", "")], consts)
    assert (placed[1].size, placed[1].align, placed[1].pad, end) == (131, 4, 2, 135)  # 4 + 127, aligned to 4 after the smallint


def layout_of(consts: cc.Constants, columns: list[tuple[str, str, bool]], maxalign: int = 8) -> cc.RowLayout:
    table = cc.Table("t", "TBL-t", "A-r", 0, None, [cc.Column(n, ty, nullable, None, "r", False) for n, ty, nullable in columns], [])
    return cc.row_layout(table, {}, consts, maxalign)


@pytest.fixture
def pg16() -> cc.Constants:
    problems = cc.Problems()
    consts = cc.parse_constants(DATA / "db-constants" / "postgresql-16.yaml", "postgresql", 16, problems)
    assert consts is not None and not problems
    return consts


def test_null_bitmap_grows_the_header_in_steps_of_maxalign(pg16):
    """Nine nullable smallint columns: bitmap ceil(9 / 8) = 2 byte -> 23 + 2 = 25 -> t_hoff 32. Without any nullable column there is no bitmap: 23 -> 24."""
    nine = [(f"c{i}", "smallint", True) for i in range(9)]
    with_nulls = layout_of(pg16, nine)
    assert (with_nulls.bitmap_bytes, with_nulls.t_hoff) == (2, 32)
    without = layout_of(pg16, [(n, t, False) for n, t, _ in nine])
    assert (without.bitmap_bytes, without.t_hoff) == (0, 24)
    one = layout_of(pg16, [("a", "smallint", True)])
    assert (one.bitmap_bytes, one.t_hoff) == (1, 24)
    eight = layout_of(pg16, [(f"c{i}", "smallint", True) for i in range(8)])
    assert eight.bitmap_bytes == 1


def test_heap_fill_factor_comes_from_the_constants_file(tmp_path):
    workspace = make(tmp_path, constants=lambda d: d["constants"]["heap_fillfactor"].update(value=0.5))
    assert run(workspace) == 0
    assert "fillfactor 0.5 ÷ 116⌋ = **35**" in draft(workspace, "03-capacity/data-sizing.md")  # floor(8168 x 0.5 / 116)


def test_row_bytes_of_a_single_bigint_table(pg16):
    layout = layout_of(pg16, [("id", "bigint", False)])
    # t_hoff 24, data 8, tuple 32, + 4 line pointer
    assert (layout.t_hoff, layout.data_bytes, layout.tuple_bytes, layout.row_bytes, layout.rows_per_page) == (24, 8, 32, 36, 8168 // 36)


def test_peak_row_and_egress_per_month_are_exact(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    assert "| req/s đỉnh | req/s trung bình × hệ số đỉnh | 6.94 | 69.44 | 347.22 |" in draft(workspace, "03-capacity/workload-model.md")
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]] for line in draft(workspace, "03-capacity/storage-sizing.md").splitlines() if line.startswith("| 1 năm") or line.startswith("| 3 năm")}
    assert rows["1 năm"][-1].endswith("(91,250,000,000 byte)")  # 6,000 x 500,000 x 365/12
    assert rows["3 năm"][-1].endswith("(365,000,000,000 byte)")  # 24,000 x 500,000 x 365/12


def test_the_key_counter_counts_every_row_ever_inserted_not_only_the_rows_kept(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"].update(retention_days=100))
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "đã chèn 18,250,000 × (1 + biên an toàn 0.3)" in text
    assert "| 3 năm | 20,000 | 18,250,000 | 2,000,000 |" in text  # kept: 20,000 x 100


def test_workload_instances_and_cost_match_a_hand_calculation(tmp_path):
    """3y: DAU 50,000 x 120 = 6,000,000/day; / 86,400 = 69.444 req/s; x 5 = 347.22; x 1.3 = 451.39.
    order-service 0.6 x 451.39 = 270.83; capacity 150 x 0.7 = 105 -> ceil(2.579) = 3; catalog 0.4 -> 180.56 / 280 -> 1 -> min 2. Compute = (3 + 2) x 70 = 350."""
    workspace = make(tmp_path)
    assert run(workspace) == 0
    assert "| req/s đỉnh có biên an toàn | req/s đỉnh × (1 + biên an toàn) | 9.03 | 90.28 | 451.39 |" in draft(workspace, "03-capacity/workload-model.md")
    compute = draft(workspace, "03-capacity/compute-sizing.md")
    assert "| 3 năm | 270.83 | 105.00 | 3 | **3** |" in compute and "| 3 năm | 180.56 | 280.00 | 1 | **2** |" in compute
    cost = draft(workspace, "03-capacity/cost-model.md")
    assert "| Compute (instance × đơn giá) | 280.00 | 280.00 | 350.00 |" in cost


def test_storage_retention_and_egress(tmp_path):
    """1y: 2,000 x 365 = 730,000 files, kept (retention 365 d: min(730,000, 2,000 x 365)); 500,000 byte each = 365,000,000,000 byte.
    3y: uploaded 730,000 + 8,000 x 730 = 6,570,000; kept min(6,570,000, 8,000 x 365 = 2,920,000); egress/month = 24,000 x 500,000 x 365/12."""
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/storage-sizing.md")
    assert "| 1 năm | 2,000 | 730,000 | 730,000 |" in text and "(365,000,000,000 byte)" in text
    assert "| 3 năm | 8,000 | 6,570,000 | 2,920,000 |" in text and "(1,460,000,000,000 byte)" in text
    assert f"({24_000 * 500_000 * 365 / 12:,.0f} byte)" in text


def no_object_storage(files):
    files["storage"]["buckets"] = {}
    for item in ("object-storage", "egress"):  # no bucket, so no object storage price is needed either
        files["pricing"]["items"].pop(item)


def test_a_project_with_no_object_storage_runs_and_says_so(tmp_path):
    workspace = make(tmp_path, mutate=no_object_storage)
    assert run(workspace) == 0
    storage = draft(workspace, "03-capacity/storage-sizing.md")
    assert "Không có object storage" in storage and "##" not in storage.replace("# Dung lượng object storage", "")
    cost = draft(workspace, "03-capacity/cost-model.md")
    assert "| Object storage (GB × đơn giá) | 0.00 | 0.00 | 0.00 |" in cost and "| Băng thông ra (GB × đơn giá) | 0.00 | 0.00 | 0.00 |" in cost
    assert "Không có object storage: khoản object storage và băng thông ra bằng 0." in cost
    assert run(workspace, "--check") == 0


def test_no_storage_yaml_is_the_same_as_empty_buckets(tmp_path):
    empty = make(tmp_path / "a", mutate=no_object_storage)
    missing = make(tmp_path / "b", mutate=no_object_storage)
    (missing / "capacity" / "storage.yaml").unlink()
    assert run(empty) == 0 and run(missing) == 0
    for rel in OUTPUTS:
        assert draft(empty, rel) == draft(missing, rel), rel


def test_the_total_without_object_storage_is_compute_plus_database(tmp_path):
    with_bucket = make(tmp_path / "a")
    without = make(tmp_path / "b", mutate=no_object_storage)
    assert run(with_bucket) == 0 and run(without) == 0
    def row(workspace, label):
        line = next(l for l in draft(workspace, "03-capacity/cost-model.md").splitlines() if l.startswith(f"| {label}"))
        return [c.strip() for c in line.split("|")[2:-1]]
    for label in ("Compute", "Lưu trữ database"):
        assert row(with_bucket, label) == row(without, label)
    total = [float(c.strip("*").replace(",", "")) for c in row(without, "**Tổng**")[1:]]
    parts = [float(a.replace(",", "")) + float(b.replace(",", "")) for a, b in zip(row(without, "Compute")[1:], row(without, "Lưu trữ database")[1:])]
    assert total == parts


@pytest.mark.parametrize("storage,message", [
    ({}, "thiếu khóa buckets"),
    ({"buckets": ["uploads"]}, "buckets phải là mapping"),
    ({"buckets": "uploads"}, "buckets phải là mapping"),
])
def test_storage_yaml_that_is_neither_buckets_nor_empty_is_an_error(tmp_path, storage, message):
    workspace = make(tmp_path, mutate=lambda f: f.update(storage=storage))
    assert run(workspace) == 1
    assert message in report(workspace)


def test_the_database_cost_uses_the_storage_to_provision_not_the_logical_size(tmp_path):
    """1 year, from the hand calculation above: heap 427,155,456 + index 228,999,168 byte (logical 656,154,624).
    data after bloat = 427,155,456 x 1.2 + 228,999,168 x 1.3 = 810,285,465.6; + WAL 1,073,741,824 = 1,884,027,289.6; x (1 + 1 replica) = 3,768,054,579.2;
    + 2 backups x 810,285,465.6 = 1,620,570,931.2 -> 5,388,625,510.4 byte to provision; / 1 GB (1,073,741,824) x 0.115."""
    workspace = make(tmp_path)
    assert run(workspace) == 0
    heap, index = 427_155_456, 228_999_168
    data = heap * 1.2 + index * 1.3
    total = (data + 1_073_741_824) * 2 + 2 * data
    assert round(total, 1) == 5_388_625_510.4
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert f"**{cc.with_bytes(total)}**" in text and f"({total:,.0f} byte)" in text
    assert f"{total / 1_073_741_824 * 0.115:,.2f}" in draft(workspace, "03-capacity/cost-model.md")
    assert f"{656_154_624 / 1_073_741_824 * 0.115:,.2f}" != f"{total / 1_073_741_824 * 0.115:,.2f}"


def test_the_plan_example_integer_runs_out_after_about_5_9_years_at_a_million_rows_a_day(tmp_path):
    def mutate(files):
        files["assumptions"]["milestones"] = ["launch", "1y"]
        for a in files["assumptions"]["assumptions"]:
            if a["id"] == "A-orders-per-day":
                a["by_milestone"] = {"launch": 0, "1y": 1_000_000}
        files["tables"]["databases"]["order-db"]["tables"]["orders"].pop("retention_days")
        for a in files["assumptions"]["assumptions"]:
            if a["id"] in ("A-dau", "A-uploads-per-day", "A-views-per-day"):
                a["by_milestone"] = {k: v for k, v in a["by_milestone"].items() if k != "3y"}

    workspace = make(tmp_path, level="S", mutate=mutate)
    assert run(workspace) == 0  # still enough at the 1-year milestone: 365,000,000 x 1.3 < 2,147,483,647
    text = draft(workspace, "03-capacity/data-sizing.md")
    years_in_total = 1 + (2_147_483_647 - 365_000_000) / (1_000_000 * 365)
    assert round(years_in_total, 1) == 5.9
    assert f"còn đủ khoảng {(2_147_483_647 - 365_000_000) / (1_000_000 * 365):,.1f} năm sau mốc 1y" in text


def test_too_small_a_key_type_is_a_blocking_error_but_the_documents_still_show_it(tmp_path):
    def mutate(files):
        files["assumptions"]["milestones"] = ["launch", "1y", "3y", "5y"]
        for a in files["assumptions"]["assumptions"]:
            if "by_milestone" in a:
                a["by_milestone"]["5y"] = a["by_milestone"]["3y"]
            if a["id"] == "A-orders-per-day":
                a["by_milestone"] = {"launch": 0, "1y": 1_000_000, "3y": 1_000_000, "5y": 1_000_000}
        files["tables"]["databases"]["order-db"]["tables"]["orders"].pop("retention_days")

    workspace = make(tmp_path, level="L", mutate=mutate)
    assert run(workspace) == 1
    assert "kiểu integer" in report(workspace) and "kiểu nhỏ nhất đủ là bigint" in report(workspace)
    assert "**KHÔNG ĐỦ**" in draft(workspace, "03-capacity/data-sizing.md")


# --- constants and sources: nothing is hard-coded, nothing without a source ----------------------------------------------------------

@pytest.mark.parametrize("constant", cc.REQUIRED_CONSTANTS)
def test_every_constant_must_have_a_source_link(tmp_path, constant):
    def constants(data):
        data["constants"][constant].pop("source")

    workspace = make(tmp_path, constants=constants)
    assert run(workspace) == 1
    assert constant in report(workspace) and "link nguồn" in report(workspace)
    assert not (workspace / "drafts" / "03-capacity").exists()  # nothing is computed from an unsourced constant


@pytest.mark.parametrize("constant", cc.REQUIRED_CONSTANTS)
def test_a_missing_constant_is_an_error(tmp_path, constant):
    workspace = make(tmp_path, constants=lambda data: data["constants"].pop(constant))
    assert run(workspace) == 1 and f"thiếu hằng số {constant}" in report(workspace)


def test_the_constants_file_needs_the_date_it_was_looked_up(tmp_path):
    workspace = make(tmp_path, constants=lambda d: d.pop("looked_up"))
    assert run(workspace) == 1 and "looked_up" in report(workspace)
    workspace2 = make(tmp_path / "b", constants=lambda d: d.update(looked_up="hôm qua"))
    assert run(workspace2) == 1 and "looked_up" in report(workspace2)


def test_a_constant_that_is_not_a_url_is_not_a_source(tmp_path):
    workspace = make(tmp_path, constants=lambda d: d["constants"]["tuple_header_bytes"].update(source="đọc trong sách"))
    assert run(workspace) == 1 and "tuple_header_bytes" in report(workspace)


@pytest.mark.parametrize("key", ["source", "align_source", "align"])
def test_a_type_needs_both_sources_and_an_alignment(tmp_path, key):
    workspace = make(tmp_path, constants=lambda d: d["types"]["bigint"].pop(key))
    assert run(workspace) == 1 and "types.bigint" in report(workspace)


def test_the_constants_come_from_the_file_not_from_the_code(tmp_path):
    """Change the file, the numbers change: a 15-byte tuple header and a 4 KiB page give another row size and page count."""
    def constants(d):
        d["constants"]["tuple_header_bytes"]["value"] = 15
        d["constants"]["page_size_bytes"]["value"] = 4096

    workspace = make(tmp_path, constants=constants)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "= **" in text and "= **116 byte/dòng**" not in text
    assert "| `page_size_bytes` | 4,096 |" in text and "| `tuple_header_bytes` | 15 |" in text


def test_the_generated_docs_cite_the_constants_and_their_links(tmp_path):
    workspace = make(tmp_path)
    run(workspace)
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "https://www.postgresql.org/docs/16/storage-page-layout.html" in text and "tra cứu 2026-10-12" in text


def test_missing_constants_file_and_wrong_header(tmp_path):
    workspace = make(tmp_path)
    (workspace / "capacity" / "db-constants" / "postgresql-16.yaml").unlink()
    assert run(workspace) == 1 and "không có file" in report(workspace)
    assert run(workspace, "--constants-dir", str(tmp_path / "elsewhere")) == 1
    workspace2 = make(tmp_path / "b", constants=lambda d: d.update(major=15))
    assert run(workspace2) == 1 and "không khớp postgresql/16" in report(workspace2)
    workspace3 = make(tmp_path / "c", constants=lambda d: d.update(model="mysql-innodb"))
    assert run(workspace3) == 1 and "chưa được hỗ trợ" in report(workspace3)


def test_constants_dir_option(tmp_path):
    workspace = make(tmp_path)
    moved = tmp_path / "knowledge" / "postgresql"
    moved.mkdir(parents=True)
    shutil.move(str(workspace / "capacity" / "db-constants" / "postgresql-16.yaml"), str(moved / "postgresql-16.yaml"))
    assert run(workspace) == 1
    assert run(workspace, "--constants-dir", str(moved)) == 0


# --- source-code links name a tag, never a branch ------------------------------------------------------------------------------------

@pytest.mark.parametrize("url,ref", [
    ("https://github.com/postgres/postgres/blob/REL_16_4/src/include/access/itup.h", "REL_16_4"),
    ("https://github.com/postgres/postgres/blob/REL_16_STABLE/src/include/access/itup.h", "REL_16_STABLE"),
    ("https://github.com/postgres/postgres/tree/master/src", "master"),
    ("https://github.com/o/r/raw/main/x.h", "main"),
    ("https://raw.githubusercontent.com/postgres/postgres/REL_16_4/src/include/catalog/pg_type.dat", "REL_16_4"),
    ("https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/include/catalog/pg_type.dat", "REL_16_STABLE"),
    ("https://gitlab.com/g/p/-/blob/v1.2.3/a.c", "v1.2.3"),
    ("https://gitlab.com/g/p/-/blob/develop/a.c", "develop"),
    ("https://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/include/access/itup.h;hb=REL_16_STABLE", "REL_16_STABLE"),
    ("https://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/include/access/itup.h;hb=REL_16_4", "REL_16_4"),
    ("https://git.postgresql.org/cgit/postgresql.git/tree/src/include/access/itup.h?h=REL_16_STABLE", "REL_16_STABLE"),
    ("https://www.postgresql.org/docs/16/storage-page-layout.html", None),
    ("https://example.com/blob/master/x", None),
])
def test_source_ref_is_read_from_repository_links_only(url, ref):
    assert cc.source_ref(url) == ref


@pytest.mark.parametrize("ref,pinned", [
    ("REL_16_4", True), ("REL_17_0", True), ("REL_9_6_24", True), ("v1.2.3", True), ("1.2", True), ("release-1.2.3", True),
    ("a" * 40, True), ("0123456789abcdef0123456789abcdef01234567", True),
    ("REL_16_STABLE", False), ("master", False), ("main", False), ("HEAD", False), ("develop", False), ("stable-2.4", False), ("REL_16", False), ("v1", False), ("release-branch.go1.22", False),
])
def test_only_release_tags_and_commits_are_pinned(ref, pinned):
    assert cc.is_pinned_ref(ref) is pinned


@pytest.mark.parametrize("where", ["constant", "type_source", "type_align_source"])
def test_a_source_link_that_points_at_a_branch_is_an_error(tmp_path, where):
    branch = "https://github.com/postgres/postgres/blob/REL_16_STABLE/src/include/access/itup.h"

    def constants(d):
        if where == "constant":
            d["constants"]["index_tuple_header_bytes"]["source"] = branch
        elif where == "type_source":
            d["types"]["bigint"]["source"] = branch
        else:
            d["types"]["bigint"]["align_source"] = branch

    workspace = make(tmp_path, constants=constants)
    assert run(workspace) == 1
    assert "REL_16_STABLE" in report(workspace) and "tag phát hành" in report(workspace)
    assert not (workspace / "drafts" / "03-capacity").exists()


def test_documentation_links_are_not_source_links_and_tags_pass(tmp_path):
    def constants(d):
        d["constants"]["page_size_bytes"]["source"] = "https://www.postgresql.org/docs/current/storage-page-layout.html"
        d["constants"]["btree_page_special_bytes"]["source"] = "https://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/include/access/nbtree.h;hb=REL_16_4"

    assert run(make(tmp_path, constants=constants)) == 0


def test_the_sample_constants_point_only_at_tags():
    text = (DATA / "db-constants" / "postgresql-16.yaml").read_text(encoding="utf-8")
    refs = {cc.source_ref(url) for url in __import__("re").findall(r"https?://[^\s\"',}]+", text)} - {None}
    assert refs == {"REL_16_4"}


# --- MAXALIGN is a platform assumption, not a constant of the database -------------------------------------------------------------------

def test_maxalign_in_the_constants_file_is_an_error_pointing_to_the_assumption(tmp_path):
    workspace = make(tmp_path, constants=lambda d: d["constants"].update(maxalign_bytes={"value": 8, "source": "https://www.postgresql.org/docs/16/catalog-pg-type.html"}))
    assert run(workspace) == 1 and "maxalign_bytes không là hằng số" in report(workspace) and "database_assumptions" in report(workspace)


def test_maxalign_comes_from_the_assumption_with_its_platform(tmp_path):
    """MAXALIGN 4: t_hoff = ceil4(23 + 1) = 24; data 81; tuple = ceil4(24 + 81) = 108; + 4 = 112; rows/page = floor(8168 / 112) = 72."""
    def mutate(files):
        for a in files["assumptions"]["assumptions"]:
            if a["id"] == "A-maxalign":
                a["value"], a["platform"] = 4, "arm64"

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "= **112 byte/dòng**" in text and "= **72**" in text
    assert "MAXALIGN 4 (giả định A-maxalign, nền tảng arm64)" in text
    assert "MAXALIGN 4 (giả định A-maxalign, nền tảng arm64)" in draft(workspace, "07-data/databases/order-db/tables.md")
    assert "(nền tảng: arm64)" in draft(workspace, "00-context/assumptions.md")


def test_a_larger_maxalign_pads_more(tmp_path):
    def mutate(files):
        for a in files["assumptions"]["assumptions"]:
            if a["id"] == "A-maxalign":
                a["value"] = 16

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 0
    assert "= **132 byte/dòng**" in draft(workspace, "03-capacity/data-sizing.md")  # t_hoff 32, data 81 -> ceil16(113) = 128, + 4


def test_maxalign_row_layout_unit(pg16):
    four = layout_of(pg16, [("a", "smallint", False)], maxalign=4)
    sixteen = layout_of(pg16, [("a", "smallint", False)], maxalign=16)
    assert (four.t_hoff, four.tuple_bytes) == (24, 28) and (sixteen.t_hoff, sixteen.tuple_bytes) == (32, 48)


# --- the assumptions every database must declare ---------------------------------------------------------------------------------------

DB_KEYS = ("maxalign", "heap_bloat_factor", "index_bloat_factor", "wal_bytes", "replicas", "backups", "toast_column_ratio")


def edit_db(files, **changes):
    block = files["assumptions"]["database_assumptions"]["order-db"]
    for key, value in changes.items():
        if value is None:
            block.pop(key)
        else:
            block[key] = value


def edit_assumption(files, ident, **changes):
    for a in files["assumptions"]["assumptions"]:
        if a["id"] == ident:
            for key, value in changes.items():
                if value is None:
                    a.pop(key, None)
                else:
                    a[key] = value
            return a
    raise KeyError(ident)


@pytest.mark.parametrize("key", DB_KEYS)
def test_every_database_assumption_is_required(tmp_path, key):
    workspace = make(tmp_path, mutate=lambda f: edit_db(f, **{key: None}))
    assert run(workspace) == 1 and f"database_assumptions.order-db.{key}: thiếu" in report(workspace)
    assert not (workspace / "drafts" / "03-capacity").exists()


def test_the_whole_block_is_required_and_must_match_tables_yaml(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: f["assumptions"].pop("database_assumptions"))
    assert run(workspace) == 1 and "thiếu database_assumptions" in report(workspace)
    workspace2 = make(tmp_path / "b", mutate=lambda f: f["assumptions"]["database_assumptions"].pop("order-db"))
    assert run(workspace2) == 1 and "database_assumptions.order-db: thiếu" in report(workspace2)
    workspace3 = make(tmp_path / "c", mutate=lambda f: f["assumptions"]["database_assumptions"].update({"other-db": {}}))
    assert run(workspace3) == 1 and "database_assumptions.other-db không có trong tables.yaml" in report(workspace3)


def test_a_key_must_point_at_a_declared_assumption(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: edit_db(f, replicas="A-nope"))
    assert run(workspace) == 1 and "database_assumptions.order-db.replicas" in report(workspace) and "A-nope" in report(workspace)


@pytest.mark.parametrize("ident,key", [("A-replicas", "replicas"), ("A-backups", "backups"), ("A-wal-bytes", "wal_bytes"), ("A-toast-ratio", "toast_column_ratio"),
                                       ("A-heap-bloat", "heap_bloat_factor"), ("A-index-bloat", "index_bloat_factor")])
def test_a_zero_or_no_bloat_assumption_needs_a_reason(tmp_path, ident, key):
    zero = 1 if "bloat" in ident else 0
    workspace = make(tmp_path, mutate=lambda f: edit_assumption(f, ident, value=zero, reason=None))
    assert run(workspace) == 1 and ident in report(workspace) and "reason" in report(workspace)
    workspace2 = make(tmp_path / "b", mutate=lambda f: edit_assumption(f, ident, value=zero, reason="không dùng: dự án S, một node"))
    assert run(workspace2) == 0, report(workspace2)


def test_a_reason_alone_is_not_enough_a_source_is_still_required(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: edit_assumption(f, "A-replicas", value=0, reason="một node", source=""))
    assert run(workspace) == 1 and "A-replicas" in report(workspace) and "nguồn của giả định" in report(workspace)


def test_non_zero_values_need_no_reason(tmp_path):
    assert run(make(tmp_path, mutate=lambda f: edit_assumption(f, "A-replicas", value=3, reason=None))) == 0


@pytest.mark.parametrize("ident,changes,expected", [
    ("A-heap-bloat", {"value": 0.9}, "từ 1 trở lên"),
    ("A-index-bloat", {"value": 0.5, "reason": "x"}, "từ 1 trở lên"),
    ("A-wal-bytes", {"by_milestone": {"launch": 1, "1y": 2, "3y": 3}, "value": None}, None),
    ("A-replicas", {"value": 1.5}, "số nguyên"),
    ("A-backups", {"value": 2.5}, "số nguyên"),
    ("A-toast-ratio", {"value": 1.5}, "từ 0 đến 1"),
    ("A-maxalign", {"value": 6}, "lũy thừa của 2"),
    ("A-maxalign", {"value": 128}, "lũy thừa của 2"),
    ("A-maxalign", {"platform": None}, "thiếu platform"),
    ("A-maxalign", {"platform": "riscv"}, "platform phải là"),
    ("A-maxalign", {"by_milestone": {"launch": 8, "1y": 8, "3y": 8}, "value": None}, "giả định hằng"),
    ("A-toast-ratio", {"by_milestone": {"launch": 0, "1y": 0, "3y": 0}, "value": None}, "giả định hằng"),
])
def test_database_assumption_ranges(tmp_path, ident, changes, expected):
    workspace = make(tmp_path, mutate=lambda f: edit_assumption(f, ident, **changes))
    if expected is None:
        assert run(workspace) == 0, report(workspace)  # these may change by milestone
        return
    assert run(workspace) == 1 and expected in report(workspace), report(workspace)


def test_database_assumptions_may_change_by_milestone(tmp_path):
    def mutate(files):
        edit_assumption(files, "A-replicas", value=None, by_milestone={"launch": 0, "1y": 1, "3y": 2}, reason="launch: một node")

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]] for line in text.splitlines() if line.startswith(("| Ra mắt", "| 1 năm", "| 3 năm")) and "Primary" not in line and len(line.split("|")) > 10}
    assert [rows[m][4] for m in ("Ra mắt", "1 năm", "3 năm")] == ["0", "1", "2"]


def test_a_missing_milestone_in_a_database_assumption_is_an_error(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: edit_assumption(f, "A-replicas", value=None, by_milestone={"launch": 1, "1y": 1}))
    assert run(workspace) == 1 and "A-replicas không có giá trị cho mốc 3y" in report(workspace)


# --- logical size and storage to provision ----------------------------------------------------------------------------------------------

def provisioned_row(workspace: Path, milestone: str) -> list[str]:
    lines = draft(workspace, "03-capacity/data-sizing.md").split("## order-db · dung lượng cần cấp")[1].splitlines()
    row = next(line for line in lines if line.startswith(f"| {milestone} |"))
    return [c.strip() for c in row.split("|")[2:-1]]


def test_the_provisioned_table_shows_logical_size_and_every_term(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    cells = provisioned_row(workspace, "1 năm")
    heap, index = 427_155_456, 228_999_168
    data = heap * 1.2 + index * 1.3
    assert cells[0] == cc.with_bytes(heap + index)  # the logical size, as before
    assert cells[1] == "1.2 / 1.3" and cells[2] == cc.with_bytes(data) and cells[3] == cc.with_bytes(1_073_741_824)
    assert cells[4] == "1" and cells[5] == cc.with_bytes((data + 1_073_741_824) * 2) and cells[6] == "2" and cells[7] == cc.with_bytes(2 * data)
    assert cells[8] == f"**{cc.with_bytes((data + 1_073_741_824) * 2 + 2 * data)}**"


def test_zero_everything_gives_the_logical_size_times_bloat_only(tmp_path):
    def mutate(files):
        for ident in ("A-wal-bytes", "A-replicas", "A-backups"):
            edit_assumption(files, ident, value=0, reason="mẫu: không dùng")
        for ident in ("A-heap-bloat", "A-index-bloat"):
            edit_assumption(files, ident, value=1, reason="mẫu: không phình")

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 0
    cells = provisioned_row(workspace, "1 năm")
    assert cells[0] == cells[2] == cells[5] and cells[8] == f"**{cells[0]}**"
    assert cells[1] == "1 / 1"


@pytest.mark.parametrize("ident,value,more", [("A-replicas", 3, True), ("A-backups", 4, True), ("A-wal-bytes", 5 * 1024**3, True), ("A-heap-bloat", 2.0, True), ("A-index-bloat", 2.0, True)])
def test_each_assumption_raises_the_storage_to_provision(tmp_path, ident, value, more):
    base = make(tmp_path / "a")
    assert run(base) == 0
    changed = make(tmp_path / "b", mutate=lambda f: edit_assumption(f, ident, value=value))
    assert run(changed) == 0
    total = lambda w: float(provisioned_row(w, "3 năm")[8].strip("*").split("(")[1].split(" byte")[0].replace(",", ""))  # noqa: E731
    assert total(changed) > total(base)
    # and the logical size does not move
    assert provisioned_row(changed, "3 năm")[0] == provisioned_row(base, "3 năm")[0]


def test_the_logical_size_is_still_reported_in_the_table_blocks_with_the_figure_after_bloat(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    block = draft(workspace, "07-data/databases/order-db/tables.md")
    assert "Tổng logic (heap + index)" in block and "Sau phình (bloat)" in block
    heap, index = 427_155_456, 228_999_168
    assert f"{cc.with_bytes(heap + index)} | {cc.with_bytes(heap * 1.2 + index * 1.3)} |" in block


def test_the_cost_of_database_storage_follows_the_replica_count(tmp_path):
    def cost(w):
        line = next(l for l in draft(w, "03-capacity/cost-model.md").splitlines() if l.startswith("| Lưu trữ database"))
        return float(line.split("|")[-2].strip())

    a = make(tmp_path / "a")
    b = make(tmp_path / "b", mutate=lambda f: edit_assumption(f, "A-replicas", value=4))
    assert run(a) == 0 and run(b) == 0
    assert cost(b) > cost(a)


# --- TOAST: declared, not modelled ------------------------------------------------------------------------------------------------------

def test_toast_is_stated_as_not_modelled_and_the_declared_ratio_is_shown(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "TOAST (chưa mô hình)" in text and "Tỉ lệ cột độ dài thay đổi vượt ngưỡng TOAST đã khai: 0 (A-toast-ratio" in text
    assert "Đã khai không có cột vượt ngưỡng" in text and "Chưa mô hình: TOAST" in text


def test_a_non_zero_toast_ratio_warns_in_the_document(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: edit_assumption(f, "A-toast-ratio", value=0.25, reason=None))
    assert run(workspace) == 0
    text = draft(workspace, "03-capacity/data-sizing.md")
    assert "đã khai: 0.25" in text and "Script chưa mô hình TOAST" in text and "đo bằng dữ liệu thật" in text


def test_the_assumptions_md_shows_reasons_and_platforms(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "00-context/assumptions.md")
    assert "ghi chú đơn hàng tối đa vài chục byte" in text and "lý do:" in text and "(nền tảng: x86_64)" in text
    assert "| A-replicas |" in text and "| A-backups |" in text and "| A-wal-bytes |" in text and "| A-heap-bloat |" in text and "| A-index-bloat |" in text


# --- prices, benchmarks, assumptions -----------------------------------------------------------------------------------------------

def price_without(item: str, key: str):
    def mutate(files):
        files["pricing"]["items"][item].pop(key)
    return mutate


@pytest.mark.parametrize("item", ["compute-instance", "db-storage", "object-storage", "egress"])
@pytest.mark.parametrize("key", ["source", "looked_up", "unit_price"])
def test_a_price_needs_source_date_and_value(tmp_path, item, key):
    workspace = make(tmp_path, mutate=price_without(item, key))
    assert run(workspace) == 1 and f"items.{item}" in report(workspace)
    assert not (workspace / "drafts" / "03-capacity").exists()


def test_gb_definition_needs_a_source(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: f["pricing"]["gb_bytes"].pop("source"))
    assert run(workspace) == 1 and "gb_bytes" in report(workspace)


def test_a_benchmark_needs_a_source(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: f["compute"]["services"]["order-service"]["requests_per_second_per_instance"].pop("source"))
    assert run(workspace) == 1 and "thiếu source" in report(workspace)


def test_an_assumption_needs_a_source(tmp_path):
    def mutate(files):
        files["assumptions"]["assumptions"][0]["source"] = " "

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1 and "A-dau" in report(workspace) and "nguồn của giả định" in report(workspace)


def test_price_item_must_exist_and_have_the_right_unit(tmp_path):
    def missing(files):
        files["compute"]["services"]["order-service"]["price_item"] = "gpu-instance"

    def wrong_unit(files):
        files["pricing"]["items"]["egress"]["unit"] = "GB-month"

    assert run(make(tmp_path / "a", mutate=missing)) == 1
    workspace = make(tmp_path / "b", mutate=wrong_unit)
    assert run(workspace) == 1 and "cần 'GB'" in report(workspace)


@pytest.mark.parametrize("name,mutate,expected", [
    ("unknown type", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][2].update(type="int128"), "không có trong db-constants"),
    ("unknown assumption", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"].update(rows_per_day="A-nope"), "không phải giả định đã khai"),
    ("missing reason", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][2].pop("reason"), "thiếu reason"),
    ("variable without avg", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][5].pop("avg_bytes"), "cần avg_bytes"),
    ("avg on a fixed type", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][2].update(avg_bytes="A-note-bytes"), "chỉ dùng cho kiểu độ dài thay đổi"),
    ("duplicate column", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][2].update(name="id"), "trùng"),
    ("index on unknown column", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["indexes"][0].update(columns=["nope"]), "cột không có trong bảng"),
    ("bad table id", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"].update(id="orders"), "TBL-"),
    ("counter on a type without max", lambda f: f["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][1].update(counter=True), "counter: true"),
    ("bad bucket id", lambda f: f["storage"]["buckets"]["uploads"].update(id="uploads"), "BKT-"),
    ("bad service id", lambda f: f["compute"]["services"]["order-service"].update(id="order"), "SVC-"),
    ("share out of range", lambda f: f["compute"]["services"]["order-service"].update(traffic_share=1.5), "traffic_share"),
    ("shares above 1", lambda f: f["compute"]["services"]["catalog-service"].update(traffic_share=0.9), "vượt 1"),
    ("utilization zero", lambda f: f["compute"]["services"]["order-service"].update(target_utilization=0), "target_utilization"),
    ("min instances zero", lambda f: f["compute"]["services"]["order-service"].update(min_instances=0), "min_instances"),
    ("views without egress price", lambda f: f["storage"]["buckets"]["uploads"].pop("egress_price_item"), "egress_price_item"),
])
def test_input_validation(tmp_path, name, mutate, expected):
    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1 and expected in report(workspace), name
    assert not (workspace / "drafts" / "03-capacity").exists()


def test_avg_bytes_must_be_a_constant_assumption(tmp_path):
    def mutate(files):
        for a in files["assumptions"]["assumptions"]:
            if a["id"] == "A-note-bytes":
                a.pop("value")
                a["by_milestone"] = {"launch": 40, "1y": 50, "3y": 60}

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1 and "giả định hằng" in report(workspace)


@pytest.mark.parametrize("name,mutate,expected", [
    ("bad id", lambda a: a["assumptions"][0].update(id="dau"), "dạng A-"),
    ("duplicate id", lambda a: a["assumptions"][1].update(id="A-dau"), "id trùng"),
    ("value and by_milestone", lambda a: a["assumptions"][0].update(value=5), "đúng một trong"),
    ("neither", lambda a: a["assumptions"][1].pop("value"), "đúng một trong"),
    ("negative", lambda a: a["assumptions"][1].update(value=-1), "số không âm"),
    ("boolean", lambda a: a["assumptions"][1].update(value=True), "số không âm"),
    ("text value", lambda a: a["assumptions"][1].update(value="120"), "số không âm"),
    ("unit missing", lambda a: a["assumptions"][1].pop("unit"), "thiếu unit"),
    ("unknown milestone key", lambda a: a["assumptions"][0]["by_milestone"].update({"9y": 1}), "không nằm trong milestones"),
    ("bad milestone", lambda a: a.update(milestones=["launch", "2y"]), "milestones phải là danh sách"),
    ("no launch", lambda a: a.update(milestones=["1y", "3y"]), "phải có launch"),
    ("duplicate milestone", lambda a: a.update(milestones=["launch", "1y", "1y"]), "không trùng"),
    ("no workload", lambda a: a.pop("workload"), "workload phải có"),
    ("workload points nowhere", lambda a: a["workload"].update(dau="A-nope"), "không phải giả định đã khai"),
    ("assumption missing a milestone", lambda a: a["assumptions"][0]["by_milestone"].pop("3y"), "không có giá trị cho mốc 3y"),
])
def test_assumptions_validation(tmp_path, name, mutate, expected):
    workspace = make(tmp_path, mutate=lambda files: mutate(files["assumptions"]))
    assert run(workspace) == 1 and expected in report(workspace), name
    assert not (workspace / "drafts" / "03-capacity").exists()


def test_missing_input_file_is_an_error(tmp_path):
    for name in FILES:
        if name == "storage":
            continue  # optional: no storage.yaml means no object storage (test_no_storage_yaml_is_the_same_as_empty_buckets)
        workspace = make(tmp_path / name)
        (workspace / "capacity" / f"{name}.yaml").unlink()
        assert run(workspace) == 1 and f"{name}.yaml" in report(workspace), name


def test_broken_yaml_is_an_error(tmp_path):
    workspace = make(tmp_path)
    (workspace / "capacity" / "tables.yaml").write_text("databases: [unclosed\n", encoding="utf-8")
    assert run(workspace) == 1 and "YAML hỏng" in report(workspace)
    (workspace / "capacity" / "tables.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    assert run(workspace) == 1 and "mapping" in report(workspace)


def test_all_problems_are_listed_together(tmp_path):
    def mutate(files):
        files["pricing"]["items"]["egress"].pop("source")
        files["compute"]["services"]["order-service"]["traffic_share"] = 7
        files["tables"]["databases"]["order-db"]["tables"]["orders"]["columns"][2]["type"] = "int128"

    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1
    text = report(workspace)
    assert "items.egress" in text and "traffic_share" in text and "int128" in text


# --- milestones by project level ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("level,milestones,ok", [
    ("S", ["launch", "1y"], True), ("S", ["launch"], False), ("S", ["launch", "1y", "3y"], True),
    ("M", ["launch", "1y", "3y"], True), ("M", ["launch", "1y"], False),
    ("L", ["launch", "1y", "3y", "5y"], True), ("L", ["launch", "1y", "3y"], False),
    ("XL", ["launch", "1y", "3y", "5y", "peak"], True), ("XL", ["launch", "1y", "3y", "5y"], False),
])
def test_milestones_must_cover_the_level(tmp_path, level, milestones, ok):
    def mutate(files):
        files["assumptions"]["milestones"] = milestones
        for a in files["assumptions"]["assumptions"]:
            if "by_milestone" in a:
                a["by_milestone"] = {m: a["by_milestone"].get(m, a["by_milestone"]["3y"]) for m in milestones}

    workspace = make(tmp_path, level=level, mutate=mutate)
    code = run(workspace)
    assert (code == 0) is ok, report(workspace)
    if not ok:
        assert f"mức {level} cần các mốc" in report(workspace)


def test_without_a_profile_the_level_is_unchecked_and_noted(tmp_path):
    workspace = make(tmp_path, level=None)
    assert run(workspace) == 0 and "chưa kiểm các mốc theo mức" in report(workspace)


def test_peak_milestone_gets_workload_and_compute_only(tmp_path):
    def mutate(files):
        files["assumptions"]["milestones"] = ["launch", "1y", "3y", "5y", "peak"]
        for a in files["assumptions"]["assumptions"]:
            if "by_milestone" in a:
                v = a["by_milestone"]
                a["by_milestone"] = {**v, "5y": v["3y"]}
                if a["id"] == "A-dau":
                    a["by_milestone"]["peak"] = 100_000

    workspace = make(tmp_path, level="XL", mutate=mutate)
    assert run(workspace) == 0
    assert "100,000" in draft(workspace, "03-capacity/workload-model.md")
    assert "Đỉnh tải" in draft(workspace, "03-capacity/compute-sizing.md")
    cost = draft(workspace, "03-capacity/cost-model.md")
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]] for line in cost.splitlines() if line.startswith("| ") and "GB cần cấp × đơn giá" in line or line.startswith("| Compute") or line.startswith("| **Tổng**")}
    db_row = rows["Lưu trữ database (GB cần cấp × đơn giá)"]
    assert db_row[0] != "0.00" and float(db_row[2]) > float(db_row[1]) and float(db_row[3]) > float(db_row[2]) and db_row[4] == "—"
    assert rows["Compute (instance × đơn giá)"][-1] != "—" and rows["**Tổng**"][-1] == rows["Compute (instance × đơn giá)"][-1]


def test_a_workload_assumption_without_a_peak_value_is_an_error_for_xl(tmp_path):
    def mutate(files):
        files["assumptions"]["milestones"] = ["launch", "1y", "3y", "5y", "peak"]
        for a in files["assumptions"]["assumptions"]:
            if "by_milestone" in a:
                a["by_milestone"]["5y"] = a["by_milestone"]["3y"]

    workspace = make(tmp_path, level="XL", mutate=mutate)
    assert run(workspace) == 1 and "A-dau không có giá trị cho mốc peak" in report(workspace)


# --- assumptions.md ----------------------------------------------------------------------------------------------------------------

def test_assumptions_md_lists_every_assumption_with_its_source(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    text = draft(workspace, "00-context/assumptions.md")
    assert "| A-dau | Người dùng hoạt động mỗi ngày | người dùng | 1,000 | 10,000 | 50,000 | inputs/ba/prd.md mục 3.1 |" in text
    assert "| A-safety-margin | Biên an toàn cộng thêm lên tải đỉnh | tỉ lệ | 0.3 | 0.3 | 0.3 | người dùng duyệt ở G1 |" in text
    assert text.count("\n| A-") == len(sample("assumptions")["assumptions"])
    assert "Sinh bởi calc_capacity.py" in text


def test_assumptions_only_needs_just_assumptions_yaml(tmp_path):
    workspace = make(tmp_path, tables_md=None)
    for name in ("tables", "storage", "compute", "pricing"):
        (workspace / "capacity" / f"{name}.yaml").unlink()
    assert run(workspace, "--assumptions-only") == 0
    assert (workspace / "drafts" / "00-context" / "assumptions.md").is_file()
    assert not (workspace / "drafts" / "03-capacity").exists()
    assert run(workspace) == 1  # the full run still wants the other files


def test_assumptions_only_still_validates(tmp_path):
    workspace = make(tmp_path, mutate=lambda f: f["assumptions"]["assumptions"][0].update(source=""))
    assert run(workspace, "--assumptions-only") == 1
    assert not (workspace / "drafts" / "00-context" / "assumptions.md").exists()


# --- tables.md: only between the markers --------------------------------------------------------------------------------------------

def tables_md(workspace: Path) -> Path:
    return workspace / "drafts" / "07-data" / "databases" / "order-db" / "tables.md"


def test_only_the_text_between_the_markers_changes(tmp_path):
    workspace = make(tmp_path)
    before = tables_md(workspace).read_bytes()
    assert run(workspace) == 0
    after = tables_md(workspace).read_bytes()
    begin, end = b"<!-- BEGIN:calc:orders -->", b"<!-- END:calc:orders -->"
    assert after[: after.index(begin) + len(begin)] == before[: before.index(begin) + len(begin)]
    assert after[after.index(end) :] == before[before.index(end) :]
    assert "chờ script".encode() not in after and "116 byte/dòng".encode() in after


def test_a_second_run_changes_nothing(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    first = snapshot(workspace)
    assert run(workspace) == 0
    assert snapshot(workspace) == first
    assert "- không có" in report(workspace).split("## Đã ghi")[1].split("##")[0]


def test_crlf_files_keep_their_line_endings_outside_and_inside_the_block(tmp_path):
    workspace = make(tmp_path, tables_md=TABLES_MD.replace("\n", "\r\n"))
    assert run(workspace) == 0
    data = tables_md(workspace).read_bytes()
    assert b"\r\n" in data and data.replace(b"\r\n", b"").count(b"\n") == 0
    before = TABLES_MD.replace("\n", "\r\n").encode("utf-8")
    assert data.startswith(before[: before.index(b"<!-- BEGIN")]) and data.endswith(before[before.index(b"<!-- END") :])
    first = data
    assert run(workspace) == 0 and tables_md(workspace).read_bytes() == first


def test_text_outside_the_block_is_never_touched_even_if_it_looks_like_a_table(tmp_path):
    custom = "# tables\r\n\r\n| a | b |\r\n| --- | --- |\r\n| 1 | 2 |\r\n\r\n<!-- BEGIN:calc:orders -->\r\nchờ script\r\n<!-- END:calc:orders -->\r\n\r\nCuối.  \r\n\r\n\r\n"
    workspace = make(tmp_path, tables_md=custom)
    assert run(workspace) == 0
    data = tables_md(workspace).read_bytes()
    assert data.startswith(custom[: custom.index("<!-- BEGIN")].encode())
    assert data.endswith(custom[custom.index("<!-- END") :].encode())


def test_a_table_without_its_marker_pair_is_an_error_and_the_file_is_left_alone(tmp_path):
    workspace = make(tmp_path, tables_md="# tables\n\nKhông có cặp dấu nào.\n")
    before = tables_md(workspace).read_bytes()
    assert run(workspace) == 1
    assert "cần đúng một cặp dấu" in report(workspace) and "calc:orders" in report(workspace)
    assert tables_md(workspace).read_bytes() == before


def test_a_marker_pair_for_another_name_does_not_count_and_a_stale_block_is_noted(tmp_path):
    workspace = make(tmp_path, tables_md=TABLES_MD.replace("calc:orders", "calc:order_items"))
    assert run(workspace) == 1 and "calc:orders" in report(workspace)
    workspace2 = make(tmp_path / "b", tables_md=TABLES_MD + "\n<!-- BEGIN:calc:old -->\nchờ script\n<!-- END:calc:old -->\n")
    assert run(workspace2) == 0 and "calc:old không có trong tables.yaml" in report(workspace2)


def test_one_missing_pair_leaves_the_whole_file_alone_even_if_another_table_has_its_pair(tmp_path):
    def mutate(files):
        orders = files["tables"]["databases"]["order-db"]["tables"]["orders"]
        files["tables"]["databases"]["order-db"]["tables"]["order_items"] = {**copy.deepcopy(orders), "id": "TBL-order-items"}

    workspace = make(tmp_path, mutate=mutate)  # tables.md has the pair for orders only
    before = tables_md(workspace).read_bytes()
    assert run(workspace) == 1
    assert "calc:order_items" in report(workspace) and tables_md(workspace).read_bytes() == before


def test_a_duplicated_pair_is_an_error(tmp_path):
    workspace = make(tmp_path, tables_md=TABLES_MD + TABLES_MD.split("\n\n", 2)[2])
    assert run(workspace) == 1


def test_two_pairs_for_one_table_refuse_to_write_any_pair_of_that_file(tmp_path):
    two_pairs = TABLES_MD + "\n<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n"
    workspace = make(tmp_path, tables_md=two_pairs)
    before = tables_md(workspace).read_bytes()
    assert run(workspace) == 1
    assert tables_md(workspace).read_bytes() == before  # neither pair was filled
    text = report(workspace)
    assert "cần đúng một cặp dấu" in text and "calc:orders" in text and "thấy 2" in text


def test_no_tables_md_yet_is_a_note_not_an_error(tmp_path):
    workspace = make(tmp_path, tables_md=None)
    assert run(workspace) == 0
    assert "tables.md chưa có" in report(workspace)
    assert not tables_md(workspace).exists()  # the script never creates the Designer's file


def test_the_script_does_not_write_anywhere_else(tmp_path):
    workspace = make(tmp_path)
    before = set(snapshot(workspace))
    assert run(workspace) == 0
    new = set(snapshot(workspace)) - before
    assert new == {f"drafts/{rel}" for rel in OUTPUTS if rel != "00-context/assumptions.md"} | {"drafts/00-context/assumptions.md"}


def test_generated_documents_define_only_the_a_ids_of_assumptions_md_so_they_never_clash_with_the_designers_files(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    docs = [d for d in cl.load(workspace / "drafts") if d.rel.startswith(("03-capacity/", "00-context/assumptions"))]
    assert docs
    for doc in docs:
        ids = [ident for ident, _ in cl.definitions(doc)]
        if doc.rel == "00-context/assumptions.md":
            assert ids and all(ident.startswith("A-") for ident in ids), ids  # A-xx is defined here, its home file (data/ids.yaml)
        else:
            assert ids == [], doc.rel
    errors, _, _ = cl.run(workspace / "drafts")
    assert [e.render() for e in errors if e.code in ("broken-link", "broken-anchor", "duplicate-id", "id-outside-home")] == []


# --- --check ------------------------------------------------------------------------------------------------------------------------

def test_check_writes_nothing_but_the_report(tmp_path):
    workspace = make(tmp_path)
    before = snapshot(workspace)
    assert run(workspace, "--check") == 1  # nothing generated yet
    assert snapshot(workspace) == before
    assert "chưa có file" in report(workspace)


def test_check_passes_after_a_run_and_catches_every_kind_of_difference(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    assert run(workspace, "--check") == 0 and "Chế độ: --check" in report(workspace)
    for rel in OUTPUTS:
        path = workspace / "drafts" / rel
        original = path.read_bytes()
        path.write_bytes(original.replace(b"1", b"2", 1))
        assert run(workspace, "--check") == 1, rel
        assert rel in report(workspace)
        path.write_bytes(original)
        assert run(workspace, "--check") == 0
        path.unlink()
        assert run(workspace, "--check") == 1, rel
        path.write_bytes(original)


def test_check_catches_a_hand_edited_block_and_a_changed_yaml(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    path = tables_md(workspace)
    original = path.read_bytes()
    path.write_bytes(original.replace(b"orders_pkey | id | 20 | 366", b"orders_pkey | id | 20 | 999"))
    assert run(workspace, "--check") == 1 and "khối calc" in report(workspace)
    path.write_bytes(original)
    capacity = workspace / "capacity" / "assumptions.yaml"
    data = yaml.safe_load(capacity.read_text(encoding="utf-8"))
    data["assumptions"][0]["by_milestone"]["1y"] = 11_000
    capacity.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert run(workspace, "--check") == 1  # the drafts no longer match the assumptions
    assert run(workspace) == 0 and run(workspace, "--check") == 0


def test_check_with_invalid_input_fails_without_comparing(tmp_path):
    workspace = make(tmp_path, constants=lambda d: d["constants"]["page_size_bytes"].pop("source"))
    assert run(workspace, "--check") == 1


def test_check_tolerates_crlf_in_generated_documents(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    for rel in OUTPUTS:
        path = workspace / "drafts" / rel
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert run(workspace, "--check") == 0


# --- the script ----------------------------------------------------------------------------------------------------------------------

def test_workspace_must_exist(tmp_path):
    assert cc.main(["--workspace", str(tmp_path / "none")]) == 2


def test_helpers():
    assert cc.align_up(24, 8) == 24 and cc.align_up(25, 8) == 32 and cc.align_up(0, 8) == 0
    assert cc.size(0) == "0.00 B" and cc.size(1024) == "1.00 KiB" and cc.size(1536) == "1.50 KiB" and cc.size(1024**3) == "1.00 GiB" and cc.size(5 * 1024**4) == "5.00 TiB"
    assert cc.num(1000) == "1,000" and cc.num(1000.0) == "1,000" and cc.num(2.5) == "2.50" and cc.num(3.14159, 3) == "3.142" and cc.num(0) == "0"
    assert cc.plain(1000.0) == "1,000" and cc.plain(0.115) == "0.115" and cc.plain(5) == "5"
    assert cc.is_url("https://a.b/c") and not cc.is_url("a.b/c") and not cc.is_url("") and not cc.is_url(None) and not cc.is_url("https://a b")
    assert cc.is_date("2026-10-12") and not cc.is_date("12/10/2026") and not cc.is_date(None)
    import datetime
    assert cc.is_date(datetime.date(2026, 10, 12))
    assert not cc.is_number(True) and not cc.is_number(float("nan")) and not cc.is_number("1") and cc.is_number(0) and cc.is_number(2.5)


def test_series_with_and_without_retention():
    a = cc.Assumptions(["launch", "1y", "3y"], {"A-r": cc.Assumption("A-r", "", "", "s", None, {"launch": 0, "1y": 100, "3y": 200})}, {})
    forever = cc.series(a, "A-r", 50, None, ["launch", "1y", "3y"])
    assert [forever[m]["inserted"] for m in ("launch", "1y", "3y")] == [50, 50 + 100 * 365, 50 + 100 * 365 + 200 * 730]
    kept = cc.series(a, "A-r", 50, 30, ["launch", "1y", "3y"])
    assert [kept[m]["live"] for m in ("launch", "1y", "3y")] == [50, 50 + 100 * 30, 50 + 200 * 30]
    long_keep = cc.series(a, "A-r", 0, 10_000, ["launch", "1y", "3y"])
    assert long_keep["3y"]["live"] == long_keep["3y"]["inserted"]


def test_days_follow_the_365_day_year():
    assert [cc.days_of(m) for m in ("launch", "1y", "3y", "5y")] == [0, 365, 1095, 1825]


def test_runs_under_uv_with_its_own_dependencies(tmp_path):
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv not installed")
    workspace = make(tmp_path)
    result = subprocess.run([uv, "run", "--quiet", "--no-project", str(SCRIPT), "--workspace", str(workspace), "--date", "2026-10-12"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "0 lỗi chặn" in result.stdout and (workspace / "drafts" / "03-capacity" / "data-sizing.md").is_file()


# --- derived assumptions (derived: {product: [A-xx, ...]}) ---------------------------------------------------------------------------

def base_item(ident, **kw):
    return {"id": ident, "description": ident, "unit": "x", "source": "test", **kw}


def with_derived(*extra, workload_dau=None):
    def mutate(files):
        files["assumptions"]["assumptions"] += list(extra)
        if workload_dau:
            files["assumptions"]["workload"]["dau"] = workload_dau
    return mutate


def parse(files_mutate):
    problems = cc.Problems()
    data = sample("assumptions")
    files = {"assumptions": data}
    files_mutate(files)
    return cc.parse_assumptions(data, "M", problems), problems.items


def test_derived_by_milestone_is_the_unrounded_product_of_its_factors():
    parsed, problems = parse(with_derived(
        base_item("A-users", by_milestone={"launch": 1000, "1y": 10000, "3y": 50000}),
        base_item("A-ratio", value=0.2),
        {"id": "A-dau2", "description": "d", "unit": "người", "derived": {"product": ["A-users", "A-ratio"]}}))
    assert problems == []
    item = parsed.items["A-dau2"]
    assert item.factors == ("A-users", "A-ratio") and item.value is None
    assert item.by_milestone == {"launch": 1000 * 0.2, "1y": 10000 * 0.2, "3y": 50000 * 0.2}


def test_derived_of_constants_is_a_constant_and_derived_may_nest():
    parsed, problems = parse(with_derived(
        {"id": "A-top", "description": "d", "unit": "x", "derived": {"product": ["A-mid", "A-b"]}},  # declared before its factors
        {"id": "A-mid", "description": "d", "unit": "x", "derived": {"product": ["A-a", "A-b"]}},
        base_item("A-a", value=0.2), base_item("A-b", value=3)))
    assert problems == []
    assert parsed.items["A-mid"].value == 0.2 * 3 and parsed.items["A-top"].value == 0.2 * 3 * 3


def test_derived_covers_only_the_milestones_all_factors_cover():
    parsed, problems = parse(with_derived(
        base_item("A-r", by_milestone={"1y": 10, "3y": 20}), base_item("A-c", value=2),
        {"id": "A-d", "description": "d", "unit": "x", "derived": {"product": ["A-r", "A-c"]}}))
    assert problems == [] and parsed.items["A-d"].by_milestone == {"1y": 20, "3y": 40}


@pytest.mark.parametrize("derived, message", [
    ({"product": ["A-a", 2]}, "chỉ nhận ID giả định"),
    ({"product": ["A-a", "0.5"]}, "chỉ nhận ID giả định"),
    ({"product": ["A-a"]}, "từ 2"),
    ({"product": "A-a"}, "từ 2"),
    ({"sum": ["A-a", "A-b"]}, "chỉ có product"),
    ({"product": ["A-a", "A-b"], "extra": 1}, "chỉ có product"),
    ("A-a * A-b", "chỉ có product"),
    ({"product": ["A-a", "A-missing"]}, "không phải giả định đã khai"),
    ({"product": ["A-a", "A-d"]}, "chính nó"),
])
def test_bad_derived_forms_are_blocking(derived, message):
    _, problems = parse(with_derived(base_item("A-a", value=1), base_item("A-b", value=2),
                                     {"id": "A-d", "description": "d", "unit": "x", "derived": derived}))
    assert any(message in p for p in problems), problems


def test_a_reference_cycle_is_blocking_and_names_the_cycle():
    _, problems = parse(with_derived(
        base_item("A-a", value=1),
        {"id": "A-x", "description": "d", "unit": "x", "derived": {"product": ["A-a", "A-y"]}},
        {"id": "A-y", "description": "d", "unit": "x", "derived": {"product": ["A-a", "A-x"]}}))
    assert any("vòng tham chiếu" in p and "A-x" in p and "A-y" in p for p in problems), problems


def test_derived_cannot_be_combined_with_value_or_by_milestone():
    _, problems = parse(with_derived(base_item("A-a", value=1), base_item("A-b", value=2),
                                     {"id": "A-d", "description": "d", "unit": "x", "value": 2, "derived": {"product": ["A-a", "A-b"]}}))
    assert any("đúng một trong value, by_milestone hoặc derived" in p for p in problems), problems


def test_a_derived_assumption_needs_no_source_and_a_source_is_only_a_note():
    parsed, problems = parse(with_derived(
        base_item("A-a", value=2), base_item("A-b", value=3),
        {"id": "A-d", "description": "d", "unit": "x", "derived": {"product": ["A-a", "A-b"]}},
        {"id": "A-e", "description": "d", "unit": "x", "derived": {"product": ["A-a", "A-b"]}, "source": "ghi chú"}))
    assert problems == [] and parsed.items["A-d"].source == "" and parsed.items["A-e"].source == "ghi chú"


def test_database_assumptions_may_not_be_derived(tmp_path):
    def mutate(files):
        files["assumptions"]["assumptions"] += [base_item("A-one", value=1), base_item("A-two", value=1),
                                                {"id": "A-heap2", "description": "d", "unit": "x", "derived": {"product": ["A-one", "A-two"]}}]
        files["assumptions"]["database_assumptions"]["order-db"]["heap_bloat_factor"] = "A-heap2"
    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1
    assert "dẫn xuất" in report(workspace)


def test_workload_may_use_a_derived_assumption_and_the_documents_show_the_formula(tmp_path):
    def mutate(files):
        a = files["assumptions"]
        users = next(i for i in a["assumptions"] if i["id"] == a["workload"]["dau"])
        a["assumptions"] += [dict(users, id="A-users"), base_item("A-active-ratio", value=0.2),
                             {"id": "A-dau-derived", "description": "Người dùng hoạt động mỗi ngày", "unit": "người", "derived": {"product": ["A-users", "A-active-ratio"]}}]
        a["workload"]["dau"] = "A-dau-derived"
    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 0
    text = draft(workspace, "00-context/assumptions.md")
    assert "| Công thức |" in text and "A-users × A-active-ratio" in text
    assert "0 lỗi chặn" in report(workspace)


def test_without_derived_the_assumptions_md_has_no_formula_column(tmp_path):
    workspace = make(tmp_path)
    assert run(workspace) == 0
    assert "Công thức" not in draft(workspace, "00-context/assumptions.md")


def test_a_derived_assumption_missing_a_milestone_the_workload_needs_is_a_blocking_error(tmp_path):
    def mutate(files):
        a = files["assumptions"]
        a["assumptions"] += [base_item("A-users", by_milestone={"1y": 10000, "3y": 50000}), base_item("A-ratio", value=0.2),
                             {"id": "A-dau-d", "description": "d", "unit": "người", "derived": {"product": ["A-users", "A-ratio"]}}]
        a["workload"]["dau"] = "A-dau-d"
    workspace = make(tmp_path, mutate=mutate)
    before = snapshot(workspace)
    assert run(workspace) == 1
    text = report(workspace)
    assert "workload.dau" in text and "A-dau-d" in text and "launch" in text
    assert not (workspace / "drafts" / "03-capacity" / "workload-model.md").exists()
    assert {k: v for k, v in snapshot(workspace).items() if k in before} == before


def test_a_derived_rate_missing_a_milestone_a_table_needs_is_a_blocking_error(tmp_path):
    def mutate(files):
        files["assumptions"]["assumptions"] += [base_item("A-users", by_milestone={"3y": 50000}), base_item("A-per-user", value=2),
                                                {"id": "A-rows-d", "description": "d", "unit": "dòng/ngày", "derived": {"product": ["A-users", "A-per-user"]}}]
        files["tables"]["databases"]["order-db"]["tables"]["orders"]["rows_per_day"] = "A-rows-d"
    workspace = make(tmp_path, mutate=mutate)
    assert run(workspace) == 1
    assert "A-rows-d" in report(workspace) and "không có giá trị cho mốc" in report(workspace)


# --- TBL heading against tables.yaml id ----------------------------------------------------------------------------------------------

HEADED = "# tables\n\n### TBL-orders: orders\n\nGhi chú.\n\n<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n\nHết.\n"


def test_a_heading_with_the_yaml_id_and_the_pair_under_it_passes(tmp_path):
    assert run(make(tmp_path, tables_md=HEADED)) == 0


def test_a_heading_id_different_from_the_yaml_id_is_a_blocking_error_and_the_file_is_left_alone(tmp_path):
    workspace = make(tmp_path, tables_md=HEADED.replace("TBL-orders", "TBL-order"))
    before = tables_md(workspace).read_bytes()
    assert run(workspace) == 1
    assert "TBL-orders" in report(workspace) and "heading" in report(workspace)
    assert tables_md(workspace).read_bytes() == before


def test_a_pair_under_the_heading_of_another_table_is_a_blocking_error(tmp_path):
    text = "# tables\n\n### TBL-orders: orders\n\nGhi chú.\n\n### TBL-other: other\n\n<!-- BEGIN:calc:orders -->\nchờ script\n<!-- END:calc:orders -->\n"
    workspace = make(tmp_path, tables_md=text)
    assert run(workspace) == 1 and "không nằm dưới heading" in report(workspace)


def test_a_duplicated_heading_is_a_blocking_error(tmp_path):
    workspace = make(tmp_path, tables_md=HEADED + "\n### TBL-orders: orders lần hai\n")
    assert run(workspace) == 1 and "có 2 heading" in report(workspace)
