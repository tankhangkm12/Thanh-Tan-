"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import check_links as cl  # noqa: E402
import check_trace as ct  # noqa: E402
import idlist  # noqa: E402

SCRIPT = Path(__file__).parent / "check_trace.py"
CORE = Path(__file__).parent.parent
TODAY = "2026-10-12"
CONFIG, _ = ct.load_config(ct.DEFAULT_CONFIG)
IDS = idlist.load()

GOOD = {
    "00-context/requirements-trace.md": "# Yêu cầu\n\n## FR-001 Đặt hàng\n\n## FR-002 Xem đơn\n",
    "04-flows/flow-index.md": "# Luồng\n\n| Luồng | FR |\n| --- | --- |\n| [FL-001](FL-001-dat-hang.md) | FR-001, FR-002 |\n",
    "04-flows/FL-001-dat-hang.md": (
        "# FL-001 Đặt hàng\n\nThực hiện FR-001 và FR-002. Gọi SVC-order qua API-create-order, ghi TBL-orders, phát EVT-order-created, lưu BKT-invoices.\n\n"
        "```mermaid\nsequenceDiagram\n  web->>SVC-order: API-create-order\n  SVC-order->>TBL-orders: insert\n```\n"
    ),
    "05-frontend/web/overview.md": "# Web\n\nGọi API-create-order khi bấm đặt hàng.\n",
    "06-backend/services/order/api.md": "# SVC-order\n\n## API-create-order\n\nTạo đơn.\n",
    "07-data/databases/orders/tables.md": "# Bảng\n\n## TBL-orders\n\nCột.\n",
    "07-data/messaging.md": "# Sự kiện\n\n## EVT-order-created\n\nPhát khi có đơn.\n",
    "07-data/object-storage.md": "# Bucket\n\n## BKT-invoices\n\nHóa đơn.\n",
}


def tree(root: Path, files: dict[str, str | None]) -> Path:
    for name, text in files.items():
        path = root / name
        if text is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return root


def design(tmp_path: Path, **changes) -> Path:
    files = dict(GOOD)
    files.update({k.replace("__", "/").replace("_md", ".md"): v for k, v in changes.items()})
    return tree(tmp_path / "drafts", files)


def run(root: Path, gate: int, workspace: Path | None = None):
    docs = cl.load(root)
    return ct.check(docs, CONFIG, gate, workspace)


def codes(root: Path, gate: int, workspace: Path | None = None) -> list[str]:
    return sorted(f.code for f in run(root, gate, workspace).errors)


# --- a clean design ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("gate", [6, 7, 8, 9, 10])
def test_a_traced_design_is_clean(tmp_path, gate):
    assert run(design(tmp_path), gate).errors == []


# --- FR without a flow (from G6) ---------------------------------------------------------------------------------------------

def test_an_fr_that_no_flow_mentions_is_an_error(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"].replace("FR-001 và FR-002", "FR-001")})
    result = run(root, 6)
    assert [f.code for f in result.errors] == ["fr-without-flow"] and "FR-002" in result.errors[0].message
    assert result.errors[0].path == "00-context/requirements-trace.md" and result.errors[0].line == 5


def test_only_single_flow_files_trace_a_requirement(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": "# FL-001\n\nKhông nhắc yêu cầu nào.\n", "04-flows/notes.md": "FR-001 FR-002 ở đây\n"})
    # flow-index.md and notes.md mention both, but neither is a FL-*.md file
    assert codes(root, 6) == ["fr-without-flow", "fr-without-flow"]


def test_a_flow_file_in_another_folder_does_not_count(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": "# FL-001\n", "06-backend/FL-009-x.md": "FR-001 FR-002\n"})
    assert codes(root, 6) == ["fr-without-flow", "fr-without-flow"]


def test_an_fr_defined_in_a_table_needs_a_flow_too(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/requirements-trace.md": "# Yêu cầu\n\n| ID | Nội dung |\n| --- | --- |\n| FR-001 | a |\n| FR-002 | b |\n| FR-003 | c |\n"})
    result = run(root, 6)
    assert [f.code for f in result.errors] == ["fr-without-flow"] and "FR-003" in result.errors[0].message


def test_an_fr_mentioned_but_not_defined_is_not_asked_for_a_flow_but_is_undefined(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"] + "\nCũng FR-099.\n"})
    assert codes(root, 6) == ["id-undefined"]


def test_no_requirement_at_all_is_an_error(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/requirements-trace.md": "# Yêu cầu\n\nChưa có.\n"})
    assert "no-requirements" in codes(root, 6)


def test_placeholder_ids_are_nobodys_requirement(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/requirements-trace.md": GOOD["00-context/requirements-trace.md"] + "\n## FR-xx Mẫu\n\nMỗi FR-xxx cần luồng.\n"})
    assert run(root, 6).errors == []


def test_the_requirement_check_does_not_run_before_g6(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": "# FL-001\n"})
    assert codes(root, 5) == []
    assert codes(root, 6) == ["fr-without-flow", "fr-without-flow"]


# --- the frontend calls an API the backend does not have (from G7) -------------------------------------------------------------

def test_a_frontend_call_without_a_backend_api_is_an_error(tmp_path):
    root = design(tmp_path)
    tree(root, {"05-frontend/web/overview.md": "# Web\n\nGọi API-create-order và API-cancel-order.\n"})
    result = run(root, 7)
    errors = [f for f in result.errors if f.code == "api-not-in-backend"]
    assert len(errors) == 1 and "API-cancel-order" in errors[0].message and errors[0].path == "05-frontend/web/overview.md" and errors[0].line == 3
    assert {f.code for f in result.errors} == {"api-not-in-backend"}  # nobody defines it at all, still one error for the ID


def test_an_api_defined_only_by_the_frontend_is_not_a_backend_api(tmp_path):
    root = design(tmp_path)
    tree(root, {"05-frontend/web/overview.md": "# Web\n\n## API-mock-only\n\nGọi API-mock-only.\n"})
    result = run(root, 7)
    errors = [f for f in result.errors if f.code == "api-not-in-backend"]
    assert len(errors) == 1 and "chỉ định nghĩa ở 05-frontend/web/overview.md" in errors[0].message


def test_backend_apis_may_sit_in_contracts_or_any_backend_file(tmp_path):
    root = design(tmp_path)
    tree(root, {"05-frontend/web/overview.md": "# Web\n\nGọi API-create-order và API-list-orders.\n", "06-backend/contracts/orders.md": "# Hợp đồng\n\n## API-list-orders\n"})
    assert run(root, 7).errors == []


def test_an_api_mentioned_by_the_backend_alone_is_fine(tmp_path):
    root = design(tmp_path)
    tree(root, {"06-backend/services/order/api.md": GOOD["06-backend/services/order/api.md"] + "\n## API-internal\n"})
    assert run(root, 7).errors == []


def test_no_frontend_folder_skips_the_api_check(tmp_path):
    root = design(tmp_path, **{"05-frontend__web__overview_md": None})
    result = run(root, 7)
    assert result.errors == [] and any("bỏ qua kiểm API" in n for n in result.notes)


def test_the_api_check_does_not_run_at_g6(tmp_path):
    root = design(tmp_path)
    tree(root, {"05-frontend/web/overview.md": "# Web\n\nGọi API-ghost.\n"})
    assert codes(root, 6) == []
    assert "api-not-in-backend" in codes(root, 7)


# --- the flows name tables, buckets, events the data part does not have (from G7) -----------------------------------------------

@pytest.mark.parametrize("ident", ["TBL-ghost", "BKT-ghost", "EVT-ghost"])
def test_a_flow_that_names_a_missing_data_object_is_an_error(tmp_path, ident):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"] + f"\nGhi {ident}.\n"})
    result = run(root, 7)
    errors = [f for f in result.errors if f.code == "data-ref-missing"]
    assert len(errors) == 1 and ident in errors[0].message and errors[0].path == "04-flows/FL-001-dat-hang.md"


def test_a_diagram_in_a_code_fence_counts(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"] + "\n```mermaid\nsequenceDiagram\n  SVC-order->>TBL-ghost: insert\n```\n"})
    errors = [f for f in run(root, 7).errors if f.code == "data-ref-missing"]
    line = (root / "04-flows/FL-001-dat-hang.md").read_text(encoding="utf-8").splitlines().index("  SVC-order->>TBL-ghost: insert") + 1
    assert len(errors) == 1 and "TBL-ghost" in errors[0].message and errors[0].line == line


def test_a_data_object_defined_outside_the_data_part_is_not_enough(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"] + "\nGhi TBL-audit.\n", "06-backend/services/order/audit.md": "# Audit\n\n## TBL-audit\n"})
    errors = [f for f in run(root, 7).errors if f.code == "data-ref-missing"]
    assert len(errors) == 1 and "chỉ định nghĩa ở 06-backend/services/order/audit.md" in errors[0].message


def test_data_defined_by_a_table_row_of_the_data_part_counts(tmp_path):
    root = design(tmp_path)
    tree(root, {"04-flows/FL-001-dat-hang.md": GOOD["04-flows/FL-001-dat-hang.md"] + "\nĐọc TBL-users.\n",
                "07-data/databases/users/tables.md": "# Bảng\n\n| Bảng | Mô tả |\n| --- | --- |\n| TBL-users | người dùng |\n"})
    assert run(root, 7).errors == []


def test_the_data_check_does_not_run_at_g6(tmp_path):
    root = design(tmp_path)
    tree(root, {"07-data/databases/orders/tables.md": None, "07-data/messaging.md": None, "07-data/object-storage.md": None})
    assert codes(root, 6) == []   # the flows name TBL/EVT/BKT but the data is only designed at G7
    assert codes(root, 7) == ["data-ref-missing"] * 3


def test_a_missing_data_folder_means_the_flows_name_things_it_does_not_have(tmp_path):
    root = design(tmp_path)
    for name in [k for k in GOOD if k.startswith("07-data/")]:
        (root / name).unlink()
    assert codes(root, 7) == ["data-ref-missing"] * 3


def test_only_flows_are_checked_against_the_data_part(tmp_path):
    root = design(tmp_path)
    tree(root, {"06-backend/services/order/api.md": GOOD["06-backend/services/order/api.md"] + "\nTBL-in-backend-only dùng.\n"})
    assert codes(root, 7) == ["id-undefined"]    # not a flow, so no data-ref-missing, but nobody defines it


# --- an ID that is mentioned but defined nowhere -------------------------------------------------------------------------------

def test_a_mentioned_id_that_nobody_defines_is_an_error(tmp_path):
    root = design(tmp_path)
    tree(root, {"02-tech-stack/README.md": "# Stack\n\nTheo TC-07, NFR-12 và R-03.\n"})
    result = run(root, 7)
    assert sorted(f.message.split()[0] for f in result.errors) == ["NFR-12", "R-03", "TC-07"]
    assert all(f.code == "id-undefined" and f.path == "02-tech-stack/README.md" and f.line == 3 for f in result.errors)


def test_one_error_per_id_with_the_other_files_counted(tmp_path):
    root = design(tmp_path)
    tree(root, {"a.md": "TC-07\n", "b.md": "x\nTC-07\n", "c.md": "TC-07\n"})
    errors = run(root, 7).errors
    assert len(errors) == 1 and "và 2 file khác" in errors[0].message and errors[0].path == "a.md"


@pytest.mark.parametrize("definition", ["## TC-07 Chi phí\n", "| TC-07 | Chi phí |\n| --- | --- |\n"])
def test_defined_anywhere_in_the_drafts_is_defined(tmp_path, definition):
    root = design(tmp_path)
    body = "# Tiêu chí\n\n" + (definition if definition.startswith("##") else "| ID | Tên |\n| --- | --- |\n" + definition.split("\n")[0] + "\n")
    tree(root, {"02-tech-stack/selection-criteria.md": body, "02-tech-stack/README.md": "# Stack\n\nTheo TC-07.\n"})
    assert run(root, 7).errors == []


def test_link_targets_and_file_names_are_not_mentions(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/overview.md": "# Tổng quan\n\nXem [luồng đặt hàng](../04-flows/FL-001-dat-hang.md) và [bảng](../07-data/TBL-orders-notes.md#x).\n"})
    assert run(root, 7).errors == []   # FL-001-dat-hang and TBL-orders-notes are file names, not IDs


def test_link_text_is_a_mention(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/overview.md": "# Tổng quan\n\nXem [TC-55](x.md).\n"})
    assert [f.message.split()[0] for f in run(root, 7).errors] == ["TC-55"]


def test_placeholder_ids_are_not_mentions(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/guide.md": "# Hướng dẫn\n\nMỗi FR-xx, TC-xxx, SVC-xx và R-XX cần ID thật; file `04-flows/FL-xxx-<tên>.md`.\n"})
    assert run(root, 7).errors == []


def test_ids_inside_code_fences_count_but_not_ones_in_file_names(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/diagram.md": "# Sơ đồ\n\n```mermaid\ngraph TD\n  A-->TC-88\n```\n"})
    assert [f.message.split()[0] for f in run(root, 7).errors] == ["TC-88"]
    tree(root, {"00-context/diagram.md": None, "00-context/TC-99-notes.md": "# ghi chú\n"})
    assert run(root, 7).errors == []


@pytest.mark.parametrize("kind", ["SVC", "API", "EVT", "TBL", "BKT"])
def test_ids_of_the_detailed_design_are_not_missing_before_g7(tmp_path, kind):
    root = design(tmp_path)
    tree(root, {"04-flows/flow-index.md": GOOD["04-flows/flow-index.md"] + f"\nVà {kind}-future.\n"})
    assert codes(root, 6) == []
    # SVC and API are only undefined; a flow naming a TBL, BKT or EVT gets the more specific error: one error per ID either way
    assert codes(root, 7) == (["data-ref-missing"] if kind in ("TBL", "BKT", "EVT") else ["id-undefined"])


@pytest.mark.parametrize("kind", ["FR", "NFR", "C", "A", "TC", "FL", "SCR", "R", "D", "CH"])
def test_the_other_ids_are_checked_from_g6(tmp_path, kind):
    root = design(tmp_path)
    tree(root, {"04-flows/flow-index.md": GOOD["04-flows/flow-index.md"] + f"\nVà {kind}-future.\n"})
    assert codes(root, 6) == ["id-undefined"]
    assert codes(root, 5) == []


def test_ids_defined_outside_the_drafts_by_their_sources(tmp_path):
    root = design(tmp_path)
    ws = tmp_path
    tree(root, {"00-context/links.md": "# Liên kết\n\nQuyết định D-001, câu hỏi CH-002, màn hình SCR-03.\n"})
    assert sorted(f.message.split()[0] for f in run(root, 7, ws).errors) == ["CH-002", "D-001", "SCR-03"]
    tree(ws, {"decisions/decision-log.md": "| ID | Câu hỏi |\n| --- | --- |\n| D-001 | x |\n", "questions.md": "### CH-002\n",
              "inputs/ui-design/screens.md": "- SCR-03 Trang chủ\n", "inputs/ui-design/more/list.txt": "SCR-04\n"})
    assert run(root, 7, ws).errors == []


def test_a_source_defines_only_its_own_kinds(tmp_path):
    root = design(tmp_path)
    ws = tmp_path
    tree(ws, {"decisions/decision-log.md": "| D-001 | nhắc TC-77 và CH-005 |\n", "questions.md": "CH-002 nhắc D-009 và R-05\n"})
    tree(root, {"00-context/links.md": "# Liên kết\n\nD-001 CH-002 TC-77 CH-005 D-009 R-05\n"})
    assert sorted(f.message.split()[0] for f in run(root, 7, ws).errors) == ["CH-005", "D-009", "R-05", "TC-77"]


def test_without_a_workspace_the_sources_are_skipped(tmp_path):
    root = design(tmp_path)
    tree(root, {"00-context/links.md": "# Liên kết\n\nD-001\n"})
    assert [f.message.split()[0] for f in run(root, 7, None).errors] == ["D-001"]


# --- the script ------------------------------------------------------------------------------------------------------------------

def cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--date", TODAY, *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd)


def workspace(tmp_path: Path, **changes) -> Path:
    ws = tmp_path / ".agent-workspace"
    ws.mkdir()
    tree(ws / "drafts", {**GOOD, **{k.replace("__", "/").replace("_md", ".md"): v for k, v in changes.items()}})
    return ws


def test_clean_run_exits_zero_and_writes_the_report(tmp_path):
    ws = workspace(tmp_path)
    proc = cli("--workspace", str(ws), "--gate", "G7")
    assert proc.returncode == 0, proc.stdout
    report = (ws / "checks" / f"trace-{TODAY}.md").read_text(encoding="utf-8")
    assert "0 lỗi chặn" in report and "FR: 2 định nghĩa, 2 có luồng" in report and "G7" in report and "- không có" in report


def test_errors_exit_one_and_are_listed_in_the_report(tmp_path):
    ws = workspace(tmp_path, **{"04-flows__FL-001-dat-hang_md": "# FL-001\n\nGhi TBL-ghost.\n"})
    proc = cli("--workspace", str(ws), "--gate", "G7")
    assert proc.returncode == 1 and "fr-without-flow" in proc.stdout and "data-ref-missing" in proc.stdout
    report = (ws / "checks" / f"trace-{TODAY}.md").read_text(encoding="utf-8")
    assert "[fr-without-flow]" in report and "[data-ref-missing]" in report and "TBL-ghost" in report


def test_many_errors_are_cut_on_screen_but_all_are_in_the_report(tmp_path):
    ids = " ".join(f"TC-{n:03d}" for n in range(40))
    ws = workspace(tmp_path, **{"00-context__x_md": f"# x\n\n{ids}\n"})
    proc = cli("--workspace", str(ws), "--gate", "G7")
    assert proc.returncode == 1 and "và 15 lỗi nữa" in proc.stdout
    assert (ws / "checks" / f"trace-{TODAY}.md").read_text(encoding="utf-8").count("[id-undefined]") == 40


def test_the_gate_is_required_and_must_be_g0_to_g10(tmp_path):
    ws = workspace(tmp_path)
    assert cli("--workspace", str(ws)).returncode == 2
    for gate in ("7", "G11", "G", "g7", "G-1", "banana"):
        assert cli("--workspace", str(ws), "--gate", gate).returncode == 2, gate
    assert cli("--workspace", str(ws), "--gate", "G10").returncode == 0


def test_a_missing_root_or_config_is_a_usage_error(tmp_path):
    assert cli("--workspace", str(tmp_path / "nope"), "--gate", "G7").returncode == 2
    ws = workspace(tmp_path)
    assert cli("--workspace", str(ws), "--gate", "G7", "--config", str(tmp_path / "none.yaml")).returncode == 2
    assert cli("--workspace", str(ws), "--gate", "G7", "--root", str(tmp_path / "elsewhere")).returncode == 2


def test_root_can_point_anywhere_and_no_workspace_means_no_report(tmp_path):
    root = design(tmp_path)
    proc = cli("--workspace", str(tmp_path / "missing-ws"), "--root", str(root), "--gate", "G7")
    assert proc.returncode == 0 and "báo cáo" not in proc.stdout
    assert not (tmp_path / "missing-ws").exists()


def test_the_default_root_is_the_drafts_of_the_workspace(tmp_path):
    ws = workspace(tmp_path)
    tree(ws, {"drafts/00-context/x.md": "TC-123\n"})
    assert "TC-123" in cli("--workspace", str(ws), "--gate", "G7").stdout


# --- data and documents ----------------------------------------------------------------------------------------------------------

def test_the_data_file_is_valid_and_names_prefixes_of_the_shared_list():
    config, errors = ct.load_config(ct.DEFAULT_CONFIG)
    assert not errors and config is not None
    assert config.requirement_kind == "FR" and config.api_kind == "API" and config.data_kinds == ["TBL", "BKT", "EVT"]
    assert (config.requirement_from_gate, config.cross_from_gate) == (6, 7)
    assert all(config.undefined_from_gate[k] == 7 for k in ("SVC", "API", "EVT", "TBL", "BKT")) and config.undefined_from_gate["default"] == 6
    assert {kind for _, kinds in config.sources for kind in kinds} == {"D", "CH", "SCR"}


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(requirement_kind="ZZZ"), lambda d: d.update(api_kind="nope"), lambda d: d.update(data_kinds=["TBL", "ZZ"]), lambda d: d.update(data_kinds=[]),
    lambda d: d.update(cross_from_gate=11), lambda d: d.update(requirement_from_gate="6"), lambda d: d["undefined_from_gate"].pop("default"),
    lambda d: d["undefined_from_gate"].update(ZZZ=7), lambda d: d.update(sources=[{"path": "/abs", "kinds": ["D"]}]), lambda d: d.update(sources=[{"path": "q.md", "kinds": ["ZZ"]}]),
    lambda d: d.update(sources="questions.md"), lambda d: d.update(flows_dir="../up"), lambda d: d.update(flow_files=""),
])
def test_a_bad_data_file_is_refused(tmp_path, mutate):
    data = yaml.safe_load(ct.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "trace.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    config, errors = ct.load_config(path)
    assert config is None and errors


def test_the_script_reads_the_id_prefixes_through_idlist():
    assert ct.IDS.kinds == IDS.kinds and ct.ID_RE.pattern == IDS.id_re().pattern


def test_placeholder_names_come_from_the_shared_list():
    for ident in ("FR-xx", "SVC-xxx", "TBL-XXX", "R-x"):
        assert IDS.is_placeholder(ident), ident
    for ident in ("FR-001", "SVC-order", "TBL-xorders", "R-x1", "A-dau"):
        assert not IDS.is_placeholder(ident), ident


def test_the_documents_describe_the_checks():
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    row = next(line for line in plan.splitlines() if line.startswith("| `check_trace.py"))
    for needle in ("--gate", "G6", "G7", "FL-*.md", "trace.yaml", "chưa định nghĩa"):
        assert needle in row, needle
    stages = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")
    assert "check_trace.py --gate" in stages and "data/trace.yaml" in stages
    g6 = stages.split("## G6.")[1].split("## G7.")[0]
    assert "FL-*.md" in g6 or "FL-xxx" in g6


def test_a_frontend_file_may_mention_ids_that_are_not_apis(tmp_path):
    root = design(tmp_path)
    tree(root, {"05-frontend/web/overview.md": "# Web\n\nThực hiện FR-001, theo FL-001, dùng SVC-order qua API-create-order, đọc EVT-order-created.\n"})
    assert run(root, 7).errors == []   # only API-xx is a call the backend must define
