"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import check_links as cl  # noqa: E402

SCRIPT = Path(__file__).parent / "check_links.py"


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return root


def codes(root: Path):
    errors, warnings, _ = cl.run(root)
    return sorted(f.code for f in errors), sorted(f.code for f in warnings)


GOOD = {
    "06-backend/services/order/responsibility.md": """# SVC-order: dịch vụ đơn hàng

Ghi đơn vào [TBL-orders](../../../07-data/orders.md#tbl-orders). Cần FR-001 và NFR-001.

## Được dùng bởi

- [Luồng đặt hàng](../../../04-flows/FL-001-dat-hang.md)
- [Bảng orders](../../../07-data/orders.md)
""",
    "07-data/orders.md": """# Dữ liệu đơn hàng

| Bảng | Mô tả |
| --- | --- |
| orders | đơn hàng của SVC-order |

## TBL-orders

Cột và kiểu.

## Được dùng bởi

- [Dịch vụ đơn hàng](../06-backend/services/order/responsibility.md)
- [Luồng đặt hàng](../04-flows/FL-001-dat-hang.md)
""",
    "04-flows/FL-001-dat-hang.md": """# FL-001 Đặt hàng

Khách gọi SVC-order, ghi TBL-orders. Thực hiện FR-001.
""",
    "00-context/requirements.md": """# Yêu cầu

## FR-001 Đặt hàng

Xem [luồng](../04-flows/FL-001-dat-hang.md).

## NFR-001 Độ trễ

p95 dưới 300 ms. Liên quan FR-001.
""",
}


@pytest.fixture
def good(tmp_path: Path) -> Path:
    return tree(tmp_path / "drafts", GOOD)


def test_clean_tree_passes(good):
    errors, warnings, count = cl.run(good)
    assert [f.render() for f in errors] == []
    assert count == 4
    # FL-001 is named in no other file (its file name in a link target does not count)
    assert [(f.code, f.message.split()[0]) for f in warnings] == [("orphan-id", "FL-001")]


# --- broken links and anchors -------------------------------------------------------------------------------------------

def test_broken_file_link(good):
    (good / "04-flows" / "FL-001-dat-hang.md").write_text("# FL-001\n\nSVC-order TBL-orders FR-001 xem [đâu đó](./khong-co.md)\n", encoding="utf-8")
    errors, _, _ = cl.run(good)
    assert [(f.path, f.line, f.code) for f in errors if f.code == "broken-link"] == [("04-flows/FL-001-dat-hang.md", 3, "broken-link")]


def test_broken_anchor_and_good_anchor(good):
    path = good / "00-context" / "requirements.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n[tốt](../07-data/orders.md#tbl-orders) [xấu](../07-data/orders.md#tbl-khac) [cùng file](#nfr-001-độ-trễ) [hỏng](#không-có)\n", encoding="utf-8")
    errors, _, _ = cl.run(good)
    broken = sorted(f.message for f in errors if f.code == "broken-anchor")
    assert len(broken) == 2 and any("tbl-khac" in m for m in broken) and any("#không-có" in m for m in broken)


def test_duplicate_headings_get_numbered_anchors(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## Ghi chú\n\n## Ghi chú\n\n[1](#ghi-chú) [2](#ghi-chú-1) [3](#ghi-chú-2)\n"})
    errors, _, _ = cl.run(root)
    assert [f.message for f in errors if f.code == "broken-anchor"] == ["link tới mục không có: #ghi-chú-2"]


def test_external_links_images_code_and_links_to_folders_are_handled(tmp_path):
    root = tree(tmp_path, {
        "a.md": "# A\n\n[web](https://example.com/x) [mail](mailto:a@b.c) ![hình](missing.png)\n\n`[trong code](khong-co.md)`\n\n```\n[trong khối](khong-co.md)\n```\n\n[thư mục](sub/)\n",
        "sub/b.md": "# B\n",
    })
    errors, _, _ = cl.run(root)
    assert [(f.code, f.line) for f in errors] == [("broken-link", 3)]  # only the image


def test_links_with_titles_angle_brackets_percent_and_reference_definitions(tmp_path):
    root = tree(tmp_path, {
        "a.md": '# A\n\n[t](b%20c.md "tiêu đề") [u](<b c.md>) [v][ref] [w][gone]\n\n[ref]: b%20c.md\n[gone]: nope.md\n',
        "b c.md": "# B\n",
    })
    errors, _, _ = cl.run(root)
    assert [(f.code, f.line, "nope.md" in f.message) for f in errors] == [("broken-link", 6, True)]


def test_link_to_a_file_outside_the_root_is_checked_on_disk(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "ba.md").write_text("# BA\n\n## Mục tiêu\n", encoding="utf-8")
    root = tree(tmp_path / "drafts", {"a.md": "# A\n\n[ok](../inputs/ba.md#mục-tiêu) [xấu](../inputs/ba.md#khong) [mất](../inputs/mat.md)\n"})
    errors, _, _ = cl.run(root)
    assert sorted(f.code for f in errors) == ["broken-anchor", "broken-link"]


# --- IDs ----------------------------------------------------------------------------------------------------------------------

def test_id_syntax_numbers_and_names(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## SVC-order\n\n## TBL-order-items\n\n## R-04\n\n## NFR-12\n\n## Chapter-1\n\n## XYZ-1\n\n## R-\n"})
    defined = [i for i, _ in cl.definitions(cl.load(root)[0])]
    assert defined == ["SVC-order", "TBL-order-items", "R-04", "NFR-12"]


def test_prefix_inside_longer_id_is_not_an_id():
    assert cl.ID_RE.findall("NFR-01 và FR-02, ABC-FR-1 xNFR-1 R-01. SVC-order,") == ["NFR-01", "FR-02", "R-01", "SVC-order"]


def test_definition_in_heading_markup_and_first_table_cell_only(tmp_path):
    root = tree(tmp_path, {"a.md": """# A

## `SVC-one` mô tả

## **FL-2**: luồng

## Mô tả về SVC-three

| Mã | Mô tả |
| --- | --- |
| [TBL-a](x.md) | cột 1 chứa TBL-b |
| `BKT-c` | |
| nói về TBL-d | |

```
## SVC-in-fence
| SVC-fenced | x |
```
"""})
    defined = [i for i, _ in cl.definitions(cl.load(root)[0])]
    assert defined == ["SVC-one", "FL-2", "TBL-a", "BKT-c"]


def test_header_row_and_later_cells_do_not_define(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n| FR-9 | Mô tả |\n| --- | --- |\n| ghi chú | TBL-z |\n| FR-1 | x |\n"})
    assert [i for i, _ in cl.definitions(cl.load(root)[0])] == ["FR-1"]


def test_duplicate_id_across_and_inside_files(tmp_path):
    root = tree(tmp_path, {
        "a.md": "# A\n\n## FR-001 một\n\n## FR-001 hai\n\n| Mã |\n| --- |\n| TC-1 |\n",
        "b.md": "# B\n\n## FR-001\n\n| Mã |\n| --- |\n| TC-1 |\n",
    })
    errors, _, _ = cl.run(root)
    dup = [f for f in errors if f.code == "duplicate-id"]
    assert sorted((f.path, f.line) for f in dup) == [("a.md", 5), ("b.md", 3), ("b.md", 7)]
    assert all("a.md:3" in f.message or "a.md:9" in f.message for f in dup)


OVERVIEW = {
    "06-backend/overview.md": "# Tổng quan\n\n| Service | Mô tả |\n| --- | --- |\n| SVC-order | [chi tiết](services/order/responsibility.md) |\n| SVC-pay | thanh toán |\n",
    "06-backend/services/order/responsibility.md": "# SVC-order\n\n## Được dùng bởi\n\n- [Tổng quan](../../overview.md)\n",
    "06-backend/services/pay/responsibility.md": "# SVC-pay\n\n## Được dùng bởi\n\n- [Tổng quan](../../overview.md)\n",
}


def test_index_table_in_an_overview_does_not_clash_with_the_detailed_files(tmp_path):
    root = tree(tmp_path, OVERVIEW)
    errors, warnings, _ = cl.run(root)
    assert [f.render() for f in errors] == [] and [f.render() for f in warnings] == []
    defined = cl.effective_definitions(cl.load(root))
    assert sorted((i, places[0][0].rel) for i, places in defined.items()) == [
        ("SVC-order", "06-backend/services/order/responsibility.md"), ("SVC-pay", "06-backend/services/pay/responsibility.md")]


def test_the_overview_mentions_the_id_so_the_detailed_file_must_link_it_back(tmp_path):
    files = dict(OVERVIEW)
    files["06-backend/services/pay/responsibility.md"] = "# SVC-pay\n\n## Được dùng bởi\n\n- không ai\n"
    errors, _, _ = cl.run(tree(tmp_path, files))
    assert [(f.path, f.code) for f in errors] == [("06-backend/services/pay/responsibility.md", "missing-backlink")]
    assert "06-backend/overview.md" in errors[0].message and "SVC-pay" in errors[0].message


def test_the_overview_itself_needs_no_backlink_section_when_it_only_indexes(tmp_path):
    assert codes(tree(tmp_path, OVERVIEW)) == ([], [])


def test_heading_wins_over_cells_even_when_there_are_several_cells(tmp_path):
    root = tree(tmp_path, {
        "a.md": "# A\n\n| Mã |\n| --- |\n| FR-1 |\n\n| Mã |\n| --- |\n| FR-1 |\n",
        "b.md": "# B\n\n## FR-1 chi tiết\n",
    })
    assert codes(root) == ([], [])
    assert [(d.rel, n) for d, n in cl.effective_definitions(cl.load(root))["FR-1"]] == [("b.md", 3)]


def test_without_any_heading_two_cells_are_a_duplicate_and_one_cell_defines(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n| Mã |\n| --- |\n| FR-1 |\n| FR-2 |\n", "b.md": "# B\n\n| Mã |\n| --- |\n| FR-1 |\n"})
    errors, _, _ = cl.run(root)
    assert [(f.path, f.line, f.code) for f in errors] == [("b.md", 5, "duplicate-id")]


def test_two_headings_are_a_duplicate_even_if_a_cell_exists_too(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## FR-1\n\n| Mã |\n| --- |\n| FR-1 |\n", "b.md": "# B\n\n## FR-1\n"})
    errors, _, _ = cl.run(root)
    assert [(f.path, f.line, f.code) for f in errors] == [("b.md", 3, "duplicate-id")]


def test_a_duplicated_id_is_reported_once_and_asks_for_no_backlink_section(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## SVC-x\n\n## SVC-x\n", "b.md": "# B\n\nSVC-x\n"})
    assert codes(root)[0] == ["duplicate-id"]


def test_an_id_defined_only_by_a_table_cell_still_needs_the_backlink_section(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n| Bảng |\n| --- |\n| TBL-x |\n", "b.md": "# B\n\nTBL-x\n"})
    assert codes(root)[0] == ["missing-backlink-section"]


def test_orphan_is_only_a_warning_and_not_blocking(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## FR-001 alone\n", "b.md": "# B\n\nnothing\n"})
    assert codes(root) == ([], ["orphan-id"])
    root2 = tree(tmp_path / "x", {"a.md": "# A\n\n## FR-001 alone\n", "b.md": "# B\n\nsee FR-001\n"})
    assert codes(root2) == ([], [])


def test_mention_in_own_file_or_in_a_link_target_does_not_count(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## FR-001\n\nFR-001 again. [x](D-001-FR-001.md)\n", "D-001-FR-001.md": "# D\n"})
    assert codes(root) == ([], ["orphan-id"])


def test_an_id_in_a_link_target_alone_is_not_a_mention(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## FR-001\n", "b.md": "# B\n\n[luồng](FR-001.md)\n", "FR-001.md": "# f\n"})
    assert codes(root) == ([], ["orphan-id"])


# --- back links ---------------------------------------------------------------------------------------------------------------

def test_missing_backlink_section(good):
    path = good / "06-backend/services/order/responsibility.md"
    path.write_text(path.read_text(encoding="utf-8").split("## Được dùng bởi")[0], encoding="utf-8")
    errors, _, _ = cl.run(good)
    assert [(f.path, f.code) for f in errors] == [("06-backend/services/order/responsibility.md", "missing-backlink-section")]


def test_a_file_that_mentions_the_id_but_is_not_linked_in_the_section(good):
    path = good / "04-flows/FL-002-huy.md"
    path.write_text("# FL-002 Hủy\n\nHủy qua SVC-order.\n", encoding="utf-8")
    errors, _, _ = cl.run(good)
    missing = [f for f in errors if f.code == "missing-backlink"]
    assert [(f.path, "FL-002-huy.md" in f.message and "SVC-order" in f.message) for f in missing] == [("06-backend/services/order/responsibility.md", True)]
    # fixing the section fixes the error
    section = good / "06-backend/services/order/responsibility.md"
    section.write_text(section.read_text(encoding="utf-8") + "- [Luồng hủy](../../../04-flows/FL-002-huy.md)\n", encoding="utf-8")
    assert cl.run(good)[0] == []


def test_a_link_in_the_section_to_another_file_does_not_count(good):
    path = good / "06-backend/services/order/responsibility.md"
    path.write_text(path.read_text(encoding="utf-8").replace("[Luồng đặt hàng](../../../04-flows/FL-001-dat-hang.md)", "[nhầm](../../../00-context/requirements.md)"), encoding="utf-8")
    errors, _, _ = cl.run(good)
    assert [f.code for f in errors] == ["missing-backlink"] and "FL-001-dat-hang.md" in errors[0].message


def test_link_outside_the_section_does_not_count(good):
    path = good / "06-backend/services/order/responsibility.md"
    text = path.read_text(encoding="utf-8").replace("- [Luồng đặt hàng](../../../04-flows/FL-001-dat-hang.md)\n", "")
    path.write_text(text.replace("Ghi đơn", "Xem [luồng](../../../04-flows/FL-001-dat-hang.md). Ghi đơn"), encoding="utf-8")
    assert [f.code for f in cl.run(good)[0]] == ["missing-backlink"]


def test_section_ends_at_the_next_heading_of_same_or_higher_level(good):
    path = good / "06-backend/services/order/responsibility.md"
    path.write_text(path.read_text(encoding="utf-8").replace("- [Luồng đặt hàng](../../../04-flows/FL-001-dat-hang.md)\n", "") + "\n## Khác\n\n- [Luồng đặt hàng](../../../04-flows/FL-001-dat-hang.md)\n", encoding="utf-8")
    assert [f.code for f in cl.run(good)[0]] == ["missing-backlink"]
    path.write_text(path.read_text(encoding="utf-8").replace("## Khác", "### Chi tiết"), encoding="utf-8")  # a sub-heading stays inside the section? no: it is below "Được dùng bởi" only if after it
    assert cl.run(good)[0] == []


def test_fr_nfr_tc_r_need_no_backlinks(tmp_path):
    root = tree(tmp_path, {
        "a.md": "# A\n\n## FR-001\n\n## NFR-001\n\n## TC-01\n\n## R-01\n\n## FL-001\n\n## SCR-01\n",
        "b.md": "# B\n\nFR-001 NFR-001 TC-01 R-01 FL-001 SCR-01\n",
    })
    assert codes(root) == ([], [])


@pytest.mark.parametrize("kind", ["SVC", "TBL", "BKT", "EVT", "API"])
def test_every_backlink_kind_needs_the_section(tmp_path, kind):
    root = tree(tmp_path, {"a.md": f"# A\n\n## {kind}-x\n", "b.md": f"# B\n\n{kind}-x\n"})
    assert codes(root)[0] == ["missing-backlink-section"]


def test_backlink_heading_may_have_any_level_and_case(tmp_path):
    root = tree(tmp_path, {"a.md": "# A\n\n## SVC-x\n\n#### được dùng bởi\n\n- [b](b.md)\n", "b.md": "# B\n\nSVC-x\n"})
    assert codes(root) == ([], [])


# --- stack layers (Q5) and risk register (Q6) -------------------------------------------------------------------------------

def test_stack_layers_must_trace_to_a_defined_tc(tmp_path):
    root = tree(tmp_path, {
        "02-tech-stack/selection-criteria.md": "# TC\n\n| Mã | Nội dung |\n| --- | --- |\n| TC-01 | giá |\n",
        "02-tech-stack/layers/data.md": "# Data\n\nChọn theo TC-01.\n",
        "02-tech-stack/layers/backend.md": "# Backend\n\nkhông truy về đâu.\n",
        "02-tech-stack/layers/frontend.md": "# Frontend\n\nTheo TC-09.\n",
    })
    errors, _, _ = cl.run(root)
    assert sorted((f.path, f.code) for f in errors) == [
        ("02-tech-stack/layers/backend.md", "layer-without-tc"),
        ("02-tech-stack/layers/frontend.md", "layer-unknown-tc"),
    ]


RISKS = """# Rủi ro

| ID | Mô tả | Thành phần liên quan | Điểm |
| --- | --- | --- | --- |
| R-01 | a | [SVC-order](../x.md) | 9 |
| R-02 | b | TBL-orders | 8 |
| R-03 | c |  | 4 |
| R-04 | d | PostgreSQL | 4 |
| R-05 | e | [PostgreSQL](../02-tech-stack/versions-features.md#postgresql) | 4 |
| R-06 | f | [lớp data](../02-tech-stack/layers/data.md), TBL-orders | 4 |
| R-07 | g | [PostgreSQL](../x.md) | 4 |
| R-08 | h | [PostgreSQL](https://www.postgresql.org/) | 4 |
| R-09 | i | [PostgreSQL](../02-tech-stack-old/a.md) | 4 |
| R-10 | j | [PostgreSQL](./02-tech-stack/a.md) | 4 |
| R-11 | k | FR-001, NFR-002, TC-3 | 4 |
"""


def test_each_risk_row_names_its_components(tmp_path):
    root = tree(tmp_path, {
        "11-risks/risk-register.md": RISKS, "x.md": "# x\n", "02-tech-stack/versions-features.md": "# V\n\n## PostgreSQL\n",
        "02-tech-stack/layers/data.md": "# D\n\nTC-1\n", "02-tech-stack-old/a.md": "# o\n", "11-risks/02-tech-stack/a.md": "# nested\n",
    })
    errors, _, _ = cl.run(root)
    flagged = sorted((f.line, f.message.split(":")[0]) for f in errors if f.code.startswith("risk"))
    # R-03 empty, R-04 bare name, R-07 link outside the stack, R-08 external link, R-09 look-alike folder,
    # R-10 stack folder under 11-risks/, R-11 IDs that are not components (FR, NFR, TC)
    assert flagged == [(7, "R-03"), (8, "R-04"), (11, "R-07"), (12, "R-08"), (13, "R-09"), (14, "R-10"), (15, "R-11")]


def test_risk_rows_are_not_checked_before_the_stack_layers_exist(tmp_path):
    early = "# R\n\n| ID | Mô tả | Thành phần liên quan |\n| --- | --- | --- |\n| R-01 | a |  |\n| R-02 | b | PostgreSQL |\n"
    # G1: no 02-tech-stack/ at all
    assert codes(tree(tmp_path / "g1", {"11-risks/risk-register.md": early}))[0] == []
    # G2/G3: 02-tech-stack/ holds only the selection criteria, no layers/
    g2 = {"11-risks/risk-register.md": early, "02-tech-stack/selection-criteria.md": "# TC\n\n## TC-1\n"}
    assert [c for c in codes(tree(tmp_path / "g2", g2))[0] if c.startswith("risk")] == []
    # an empty layers/ folder or a non-markdown file in it is no layer
    g3 = dict(g2, **{"02-tech-stack/layers/notes.txt": "x"})
    assert [c for c in codes(tree(tmp_path / "g3", g3))[0] if c.startswith("risk")] == []
    # G4: the first layer file turns the rule on
    g4 = dict(g2, **{"02-tech-stack/layers/data.md": "# D\n\nTC-1\n"})
    assert sorted(c for c in codes(tree(tmp_path / "g4", g4))[0] if c.startswith("risk")) == ["risk-without-components"] * 2


def test_risk_table_without_the_column(tmp_path):
    root = tree(tmp_path, {"11-risks/risk-register.md": "# R\n\n| ID | Mô tả |\n| --- | --- |\n| R-01 | a |\n"})
    assert "risk-without-components-column" in codes(root)[0]


def test_layer_and_risk_rules_only_apply_when_those_files_exist(tmp_path):
    assert codes(tree(tmp_path, {"a.md": "# A\n"})) == ([], [])


# --- the script ----------------------------------------------------------------------------------------------------------------

def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_cli_exit_codes_and_report_file(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {"a.md": "# A\n\n[x](nope.md)\n"})
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 1
    assert "broken-link" in result.stdout and "1 lỗi chặn" in result.stdout
    report = (workspace / "checks" / "links-2026-10-12.md").read_text(encoding="utf-8")
    assert "a.md:3" in report and "## Lỗi chặn" in report

    (workspace / "drafts" / "a.md").write_text("# A\n", encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 0
    assert "không có" in (workspace / "checks" / "links-2026-10-12.md").read_text(encoding="utf-8")


def test_cli_warnings_do_not_block(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {"a.md": "# A\n\n## FR-001\n"})
    result = run_cli("--workspace", str(workspace))
    assert result.returncode == 0 and "orphan-id" in result.stdout


def test_cli_root_option_and_missing_folder(tmp_path):
    root = tree(tmp_path / "architecture", {"a.md": "# A\n\n[x](nope.md)\n"})
    assert run_cli("--workspace", str(tmp_path / "ws"), "--root", str(root)).returncode == 1
    assert run_cli("--workspace", str(tmp_path / "ws"), "--root", str(tmp_path / "none")).returncode == 2
    assert not (tmp_path / "ws").exists()  # no workspace, no report file made


def test_cli_lists_at_most_25_errors_but_the_report_has_all(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {"a.md": "# A\n\n" + "".join(f"[x](n{i}.md)\n" for i in range(40))})
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.stdout.count("error: `") == 25 and "15 lỗi nữa" in result.stdout
    assert (workspace / "checks" / "links-2026-10-12.md").read_text(encoding="utf-8").count("[broken-link]") == 40


# --- C and A have a home file (data/ids.yaml) ----------------------------------------------------------------------------

HOMES = {
    "00-context/constraints.md": "# Ràng buộc\n\n## C-01 Ngân sách\n\nTối đa 500 USD.\n",
    "00-context/assumptions.md": "# Giả định\n\n| ID | Mô tả |\n| --- | --- |\n| A-dau | DAU |\n",
}


def test_c_and_a_defined_in_their_home_files_are_fine(tmp_path):
    root = tree(tmp_path, {**HOMES, "00-context/other.md": "Theo C-01 và A-dau.\n"})
    assert codes(root)[0] == []


@pytest.mark.parametrize("where, text, expected", [
    ("06-backend/x.md", "# Dịch vụ\n\n## C-02 Giới hạn\n", ["id-outside-home"]),
    ("00-context/requirements.md", "# Yêu cầu\n\n| ID | Nội dung |\n| --- | --- |\n| C-02 | giới hạn |\n", ["id-outside-home"]),
    ("00-context/constraints.md", "# Ràng buộc\n\n## A-07 Giả định đặt nhầm chỗ\n", ["id-outside-home"]),
    ("00-context/other.md", "# Khác\n\n## A-dau Định nghĩa lại\n", ["id-outside-home"]),   # a heading beats the table cell of the home file
    ("00-context/other.md", "# Khác\n\n## C-01 Định nghĩa lại\n", ["duplicate-id", "id-outside-home"]),
])
def test_c_or_a_defined_outside_its_home_is_an_error(tmp_path, where, text, expected):
    files = {**HOMES}
    files[where] = files.get(where, "") + text if where in files else text
    root = tree(tmp_path, files)
    assert sorted(codes(root)[0]) == sorted(expected)


def test_prefixes_without_a_home_may_be_defined_anywhere(tmp_path):
    root = tree(tmp_path, {**HOMES, "06-backend/x.md": "# FR-09 Một yêu cầu\n\n## TC-04 tiêu chí\n"})
    assert codes(root)[0] == []


def test_tc_and_nfr_are_not_read_as_c_and_r(tmp_path):
    root = tree(tmp_path, {**HOMES, "02-tech-stack/selection-criteria.md": "# Tiêu chí\n\n## TC-01 Chi phí\n\n## NFR-01 Độ trễ\n"})
    assert codes(root)[0] == []
