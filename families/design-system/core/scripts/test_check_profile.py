"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import check_profile as cp  # noqa: E402

SCRIPT = Path(__file__).parent / "check_profile.py"
STAGES = Path(__file__).parent.parent / "workflow" / "stages.md"


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return root


def profile(level: str = "M", **overrides: str) -> str:
    """A profile with every part `có` except the overrides ({path with / replaced by __}: value)."""
    rows = {part: "có" for part in cp.PARTS}
    rows.update({key.replace("__", "/"): value for key, value in overrides.items()})
    body = "\n".join(f"| {key} | {value} |" for key, value in rows.items())
    return f"# Hồ sơ dự án\n\n- **Mức:** {level}\n\n| Phần | Áp dụng |\n| --- | --- |\n{body}\n"


CONTEXT = {f"00-context/{n}.md": "# x\n" for n in ("requirements-trace", "quality-attributes", "constraints", "assumptions", "glossary")}


def codes(root: Path, gate: int = 1, templates: Path | None = None) -> list[str]:
    findings, _ = cp.run(root, gate, templates)
    return sorted(f.code for f in findings)


def base(tmp_path: Path, level: str = "M", extra: dict | None = None, **overrides: str) -> Path:
    return tree(tmp_path / "drafts", {cp.PROFILE: profile(level, **overrides), **CONTEXT, **(extra or {})})


# --- the profile ------------------------------------------------------------------------------------------------------------

def test_good_profile_passes_at_g1(tmp_path):
    assert codes(base(tmp_path)) == []


def test_profile_missing(tmp_path):
    root = tree(tmp_path / "drafts", {"00-context/glossary.md": "# g\n"})
    assert codes(root) == ["profile-missing"]


def test_profile_without_level(tmp_path):
    root = base(tmp_path)
    (root / cp.PROFILE).write_text(profile().replace("- **Mức:** M\n", "Mức: rất lớn\n"), encoding="utf-8")
    assert codes(root) == ["profile-no-level"]


@pytest.mark.parametrize("line", ["Mức: S", "- **Mức:** XL", "**Mức:** L", "Mức: **M**", "* Mức: S (MVP nội bộ)"])
def test_level_line_forms(line):
    assert cp.LEVEL_RE.match(line)


def test_profile_without_table(tmp_path):
    root = base(tmp_path)
    (root / cp.PROFILE).write_text("# Hồ sơ\n\nMức: M\n\nKhông có bảng.\n", encoding="utf-8")
    assert codes(root) == ["profile-no-table"]


def test_bad_value_repeated_unknown_and_missing_rows(tmp_path):
    root = base(tmp_path)
    text = profile().replace("| 03-capacity | có |", "| 03-capacity | tùy |").replace("| 04-flows | có |", "| 04-flows | có |\n| 04-flows | bỏ |")
    text = text.replace("| 12-roadmap | có |", "| 13-extra | có |")
    (root / cp.PROFILE).write_text(text, encoding="utf-8")
    findings, _ = cp.run(root, 1, None)
    assert sorted((f.code) for f in findings) == ["profile-bad-value", "profile-missing-part-row", "profile-repeated-row", "profile-unknown-row"]
    missing = next(f for f in findings if f.code == "profile-missing-part-row")
    assert "12-roadmap" in missing.message


def test_value_forms_are_accepted(tmp_path):
    root = base(tmp_path, **{"03-capacity": "Rút gọn", "08-security": "**bỏ**", "05-frontend": "`bỏ`"})
    assert codes(root) == []


def test_only_the_phan_ap_dung_table_counts(tmp_path):
    root = base(tmp_path)
    (root / cp.PROFILE).write_text(profile() + "\n| Khác | Giá trị |\n| --- | --- |\n| ngân sách | 1000 |\n", encoding="utf-8")
    assert codes(root) == []


# --- omitted parts must stay out --------------------------------------------------------------------------------------------

def test_omitted_part_reappearing_is_an_error(tmp_path):
    root = base(tmp_path, "S", {"05-frontend/overview.md": "# f\n", "05-frontend/web/state-data.md": "# s\n"}, **{"05-frontend": "bỏ"})
    findings, _ = cp.run(root, 1, None)
    assert sorted((f.path, f.code) for f in findings) == [("05-frontend/overview.md", "omitted-part-present"), ("05-frontend/web/state-data.md", "omitted-part-present")]


def test_a_part_that_is_omitted_and_absent_is_fine(tmp_path):
    assert codes(base(tmp_path, "S", **{"05-frontend": "bỏ", "08-security": "bỏ"})) == []


def test_file_level_rows_override_the_part(tmp_path):
    files = {"01-system/containers.md": "# c\n", "01-system/system-context.md": "# s\n"}
    root = base(tmp_path, "S", files, **{"01-system__system-context.md": "bỏ"})
    findings, _ = cp.run(root, 1, None)
    assert [(f.path, f.code) for f in findings] == [("01-system/system-context.md", "omitted-part-present")]
    # the other way: a file kept inside an omitted part
    root2 = base(tmp_path / "x", "S", {"12-roadmap/implementation-plan.md": "# i\n", "12-roadmap/scaling-stages.md": "# s\n"},
                 **{"12-roadmap": "bỏ", "12-roadmap__implementation-plan.md": "có"})
    findings, _ = cp.run(root2, 1, None)
    assert [(f.path, f.code) for f in findings] == [("12-roadmap/scaling-stages.md", "omitted-part-present")]


def test_status_of_picks_the_longest_row():
    rows = {"01-system": "có", "01-system/a.md": "bỏ", "01-system/sub": "rút gọn", "01-system/sub/b.md": "bỏ"}
    assert [cp.status_of(p, rows) for p in ("01-system/x.md", "01-system/a.md", "01-system/sub/c.md", "01-system/sub/b.md", "01-system/a.md.bak", "02-tech-stack/x.md")] == \
        ["có", "bỏ", "rút gọn", "bỏ", "có", None]


# --- required parts by gate --------------------------------------------------------------------------------------------------

def test_a_part_the_gate_has_not_reached_may_be_absent(tmp_path):
    assert codes(base(tmp_path), gate=1) == []
    assert codes(base(tmp_path), gate=2) == ["required-file-missing"]  # 02-tech-stack/selection-criteria.md
    assert codes(base(tmp_path), gate=3) == ["required-file-missing", "required-part-missing"]


def test_gates_are_cumulative_and_omitted_parts_are_skipped(tmp_path):
    root = base(tmp_path, "S", **{"05-frontend": "bỏ", "08-security": "bỏ", "09-infrastructure": "bỏ", "10-process": "bỏ"})
    findings, _ = cp.run(root, 9, None)
    assert sorted(f.path for f in findings if f.code == "required-part-missing") == [
        "01-system", "02-tech-stack", "03-capacity", "04-flows", "06-backend", "07-data", "11-risks", "12-roadmap"]


def test_g2_needs_only_the_criteria_file_not_the_whole_stack_folder(tmp_path):
    root = base(tmp_path, extra={"01-system/containers.md": "# c\n", "02-tech-stack/selection-criteria.md": "# TC\n"})
    assert codes(root, gate=2) == []
    assert codes(root, gate=3) == []
    assert codes(root, gate=4) == []  # without templates a folder only needs one markdown file


def test_rut_gon_is_still_required(tmp_path):
    root = base(tmp_path, **{"03-capacity": "rút gọn"})
    assert sorted(f.path for f in cp.run(root, 5, None)[0]) == ["01-system", "02-tech-stack", "02-tech-stack/selection-criteria.md", "03-capacity"]


def test_omitted_file_is_not_required(tmp_path):
    root = base(tmp_path, **{"02-tech-stack__selection-criteria.md": "bỏ"})
    assert codes(root, gate=2) == []


def test_gate_zero_needs_only_the_profile(tmp_path):
    root = tree(tmp_path / "drafts", {cp.PROFILE: profile()})
    assert codes(root, gate=0) == []
    assert codes(tree(tmp_path / "x" / "drafts", {"00-context/glossary.md": "# g\n"}), gate=0) == ["profile-missing"]


# --- templates: files and required sections ---------------------------------------------------------------------------------

SCALING_TEMPLATE = """# Dịch vụ <tên>

## Tối ưu <!-- required -->

<Chỉ số mục tiêu bằng số và đơn vị>

## Scale
<!-- required -->

<Ngưỡng và đường scale>

## Nâng cấp

<!-- required -->

<Phiên bản, ngày EOL>

## Bảo trì
<!-- required -->
<Công việc định kỳ>

## Ghi chú

Tùy chọn.
"""
FILLED = """# Dịch vụ order

## Tối ưu

p95 dưới 200 ms (NFR-001).

## Scale

Thêm instance khi CPU trên 70% trong 15 phút.

## Nâng cấp

PostgreSQL 16, EOL 2028-11-09.

## Bảo trì

Vá bản vá mỗi tháng.
"""


@pytest.fixture
def templates(tmp_path: Path) -> Path:
    return tree(tmp_path / "templates", {
        "06-backend/services/{service}/scaling.md": SCALING_TEMPLATE,
        "06-backend/overview.md": "# Tổng quan\n\n## Bản đồ service\n<!-- required -->\n<bảng service>\n",
        "04-flows/FL-xxx-{tên}.md": "# FL-xxx\n\n## Lỗi <!-- required -->\n\n<các lỗi>\n",
        "03-capacity/data-sizing.md": "# Dung lượng\n\n## Bảng số\n<!-- required -->\n\n<bảng>\n",
        "03-capacity/workload-model.md": "# Tải\n",
    })


def scaling_files(text: str) -> dict:
    return {"06-backend/services/order/scaling.md": text}


def test_required_sections_present_and_filled_pass(tmp_path, templates):
    root = base(tmp_path, extra=scaling_files(FILLED))
    assert codes(root, templates=templates) == []


@pytest.mark.parametrize("heading,missing", [("Tối ưu", "tối ưu"), ("Scale", "scale"), ("Nâng cấp", "nâng cấp"), ("Bảo trì", "bảo trì")])
def test_each_required_section_is_enforced(tmp_path, templates, heading, missing):
    removed = re.sub(rf"## {heading}\n\n.*?\n\n", "", FILLED + "\n", flags=re.S).rstrip() + "\n"
    root = base(tmp_path, extra=scaling_files(removed))
    findings, _ = cp.run(root, 1, templates)
    assert [(f.code, missing in f.message) for f in findings] == [("missing-required-section", True)]


def test_optional_sections_may_be_absent(tmp_path, templates):
    assert "Ghi chú" not in FILLED
    assert codes(base(tmp_path, extra=scaling_files(FILLED)), templates=templates) == []


def test_empty_and_unfilled_required_sections(tmp_path, templates):
    empty = FILLED.replace("p95 dưới 200 ms (NFR-001).", "<!-- chưa viết -->")
    unfilled = FILLED.replace("Thêm instance khi CPU trên 70% trong 15 phút.", "<Ngưỡng và đường scale>")
    findings, _ = cp.run(base(tmp_path / "a", extra=scaling_files(empty)), 1, templates)
    assert [(f.code, f.line) for f in findings] == [("empty-required-section", 3)]
    findings, _ = cp.run(base(tmp_path / "b", extra=scaling_files(unfilled)), 1, templates)
    assert [f.code for f in findings] == ["unfilled-required-section"]


def test_text_under_a_subheading_counts_as_content(tmp_path, templates):
    nested = FILLED.replace("p95 dưới 200 ms (NFR-001).", "### Chỉ số\n\np95 dưới 200 ms.")
    assert codes(base(tmp_path, extra=scaling_files(nested)), templates=templates) == []
    only_empty_sub = FILLED.replace("p95 dưới 200 ms (NFR-001).", "### Chỉ số\n")
    assert codes(base(tmp_path / "y", extra=scaling_files(only_empty_sub)), templates=templates) == ["empty-required-section"]


def test_heading_match_ignores_level_case_markup_and_a_heading_in_a_code_block(tmp_path, templates):
    changed = FILLED.replace("## Tối ưu", "### **TỐI ƯU**")
    assert codes(base(tmp_path / "a", extra=scaling_files(changed)), templates=templates) == []
    faked = FILLED.replace("## Scale", "```\n## Scale\n```\n\n## Khác")
    findings, _ = cp.run(base(tmp_path / "b", extra=scaling_files(faked)), 1, templates)
    assert [f.code for f in findings] == ["missing-required-section"]


def test_marker_forms_in_the_template():
    lines = SCALING_TEMPLATE.splitlines()
    assert cp.required_headings(lines) == ["tối ưu", "scale", "nâng cấp", "bảo trì"]
    assert cp.required_headings(["## A", "", "text", "<!-- required -->", "## B <!-- required --> ", "<!-- REQUIRED -->"]) == ["b"]
    assert cp.required_headings(["```", "## A <!-- required -->", "```"]) == []


def test_placeholder_template_paths(tmp_path, templates):
    assert cp.match_template("06-backend/services/order/scaling.md", ["06-backend/services/<service>/scaling.md"]) == "06-backend/services/<service>/scaling.md"
    assert cp.match_template("04-flows/FL-001-dat-hang.md", ["04-flows/FL-xxx-<tên>.md"]) == "04-flows/FL-xxx-<tên>.md"
    assert cp.match_template("06-backend/services/order/scaling.md", ["06-backend/services/{service}/scaling.md"]) == "06-backend/services/{service}/scaling.md"
    assert cp.match_template("04-flows/FL-001-dat-hang.md", ["04-flows/FL-xxx-{tên}.md"]) == "04-flows/FL-xxx-{tên}.md"
    assert cp.match_template("06-backend/services/order/extra/scaling.md", ["06-backend/services/<service>/scaling.md"]) is None
    assert cp.match_template("06-backend/overview.md", ["06-backend/overview.md", "06-backend/<x>.md"]) == "06-backend/overview.md"
    root = base(tmp_path, extra={"04-flows/FL-001-dat-hang.md": "# FL-001\n\nluồng\n"})
    findings, _ = cp.run(root, 1, templates)
    assert [(f.path, f.code) for f in findings] == [("04-flows/FL-001-dat-hang.md", "missing-required-section")]


def test_required_files_come_from_the_templates_but_placeholder_ones_are_per_instance(tmp_path, templates):
    root = base(tmp_path, extra={"03-capacity/workload-model.md": "# t\n"})
    findings, _ = cp.run(root, 5, templates)
    assert sorted((f.path, f.code) for f in findings) == [
        ("01-system", "required-part-missing"), ("02-tech-stack", "required-part-missing"), ("02-tech-stack/selection-criteria.md", "required-file-missing"),
        ("03-capacity/data-sizing.md", "required-file-missing")]
    # 06-backend/services/{service}/scaling.md is never listed as a missing file
    assert not any("{service}" in f.path for f in cp.run(root, 7, templates)[0])


def test_a_template_file_of_an_omitted_part_is_not_required(tmp_path, templates):
    root = base(tmp_path, extra={"03-capacity/workload-model.md": "# t\n"}, **{"03-capacity__data-sizing.md": "bỏ"})
    findings, _ = cp.run(root, 5, templates)
    assert "03-capacity/data-sizing.md" not in [f.path for f in findings]


def test_run_without_templates_says_the_template_checks_were_not_done(tmp_path):
    root = base(tmp_path)
    findings, notes = cp.run(root, 1, None)
    assert findings == [] and notes == [cp.NOT_CHECKED] and "Chưa kiểm mục bắt buộc" in notes[0]
    assert cp.run(root, 1, Path(tmp_path))[1] == []


# --- object folders: every template with {service} / {db} / {app} must have its file ---------------------------------------------

OBJECT_TEMPLATES = {
    "06-backend/services/{service}/responsibility.md": "# Trách nhiệm\n",
    "06-backend/services/{service}/scaling.md": SCALING_TEMPLATE,
    "06-backend/services/{service}/modules/{module}/design.md": "# Module\n",
    "07-data/databases/{db}/tables.md": "# Bảng\n",
    "05-frontend/{app}/architecture.md": "# Kiến trúc\n",
    "04-flows/FL-xxx-{tên}.md": "# FL\n",
}


@pytest.fixture
def object_templates(tmp_path: Path) -> Path:
    return tree(tmp_path / "object-templates", OBJECT_TEMPLATES)


def object_files(root: Path, gate: int, templates: Path | None):
    findings, _ = cp.run(root, gate, templates)
    return sorted((f.path, f.code) for f in findings if f.code == "instance-file-missing")


def test_a_complete_service_passes_and_one_without_scaling_md_fails(tmp_path, object_templates):
    root = base(tmp_path, extra={
        "06-backend/services/order-service/responsibility.md": "# r\n", "06-backend/services/order-service/scaling.md": FILLED,
        "06-backend/services/billing-service/responsibility.md": "# r\n",
    })
    assert object_files(root, 7, object_templates) == [("06-backend/services/billing-service/scaling.md", "instance-file-missing")]
    findings, _ = cp.run(root, 7, object_templates)
    message = next(f.message for f in findings if f.code == "instance-file-missing")
    assert "billing-service" in message and "scaling.md" in message


def test_every_kind_of_object_folder(tmp_path, object_templates):
    root = base(tmp_path, extra={"07-data/databases/order-db/erd.md": "# e\n", "05-frontend/web/state-data.md": "# s\n"})
    (root / "05-frontend" / "admin").mkdir(parents=True)  # an empty folder is an object folder too
    assert object_files(root, 7, object_templates) == [
        ("05-frontend/admin/architecture.md", "instance-file-missing"), ("05-frontend/web/architecture.md", "instance-file-missing"),
        ("07-data/databases/order-db/tables.md", "instance-file-missing")]


def test_object_files_are_not_required_before_the_gate_reaches_the_part(tmp_path, object_templates):
    root = base(tmp_path, extra={"06-backend/services/order-service/responsibility.md": "# r\n"})
    assert object_files(root, 6, object_templates) == []
    assert object_files(root, 7, object_templates) == [("06-backend/services/order-service/scaling.md", "instance-file-missing")]


def test_object_files_are_not_required_in_an_omitted_part_or_for_an_omitted_file(tmp_path, object_templates):
    extra = {"06-backend/services/order-service/responsibility.md": "# r\n", "05-frontend/web/state-data.md": "# s\n"}
    omitted_part = base(tmp_path / "a", extra=extra, **{"05-frontend": "bỏ"})
    assert object_files(omitted_part, 7, object_templates) == [("06-backend/services/order-service/scaling.md", "instance-file-missing")]
    omitted_file = base(tmp_path / "b", extra=extra, **{"06-backend__services__order-service__scaling.md": "bỏ", "05-frontend": "bỏ"})
    assert object_files(omitted_file, 7, object_templates) == []
    kept = base(tmp_path / "c", extra=extra, **{"06-backend": "rút gọn", "05-frontend": "bỏ"})
    assert object_files(kept, 7, object_templates) == [("06-backend/services/order-service/scaling.md", "instance-file-missing")]


def test_placeholders_deeper_in_the_path_or_only_in_the_file_name_are_not_object_folders(tmp_path, object_templates):
    root = base(tmp_path, extra={
        "06-backend/services/order-service/responsibility.md": "# r\n", "06-backend/services/order-service/scaling.md": FILLED,
        "06-backend/services/order-service/modules/payment/other.md": "# m\n", "04-flows/FL-001-dat-hang.md": "# FL\n",
    })
    assert object_files(root, 7, object_templates) == []


def test_a_folder_next_to_name_only_templates_is_not_an_object(tmp_path, object_templates):
    root = base(tmp_path, extra={"04-flows/flow-index.md": "# i\n"})
    (root / "04-flows" / "FL-001-dat-hang.md").mkdir()  # a folder whose name fits the file template
    assert object_files(root, 7, object_templates) == []


def test_no_object_folder_no_requirement_and_plain_files_are_not_objects(tmp_path, object_templates):
    root = base(tmp_path, extra={"06-backend/services/README.md": "# services\n", "06-backend/overview.md": "# o\n"})
    assert object_files(root, 7, object_templates) == []


def test_object_check_needs_the_templates(tmp_path):
    root = base(tmp_path, extra={"06-backend/services/order-service/responsibility.md": "# r\n"})
    assert object_files(root, 7, None) == []


def test_default_templates_are_found_beside_design_core(tmp_path):
    scripts = tmp_path / "design-system" / "core" / "scripts"
    scripts.mkdir(parents=True)
    assert cp.default_templates(scripts) is None
    (tmp_path / "design-system" / "design-architecture" / "templates").mkdir(parents=True)
    assert cp.default_templates(scripts) == tmp_path / "design-system" / "design-architecture" / "templates"


def test_g0_needs_only_the_profile_even_with_templates_for_the_rest_of_00_context(tmp_path, templates):
    (templates / "00-context").mkdir()
    (templates / "00-context" / "glossary.md").write_text("# g\n", encoding="utf-8")
    root = tree(tmp_path / "drafts", {cp.PROFILE: profile()})
    assert codes(root, gate=0, templates=templates) == []
    assert [f.path for f in cp.run(root, 1, templates)[0]] == ["00-context/glossary.md"]


def test_cli_uses_the_default_templates_when_none_are_given(tmp_path, monkeypatch):
    templates = tree(tmp_path / "tpl", {"03-capacity/data-sizing.md": "# D\n\n## Bảng số\n<!-- required -->\n<bảng>\n"})
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {cp.PROFILE: profile(), "03-capacity/data-sizing.md": "# D\n"})
    monkeypatch.setattr(cp, "default_templates", lambda: templates)
    assert cp.main(["--gate", "G0", "--workspace", str(workspace)]) == 1
    (report,) = (workspace / "checks").glob("profile-*.md")
    assert "missing-required-section" in report.read_text(encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A clean G0 project, with no default templates to be found."""
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {cp.PROFILE: profile()})
    monkeypatch.setattr(cp, "default_templates", lambda: None)
    return workspace


def last_report(workspace: Path) -> str:
    (path,) = (workspace / "checks").glob("profile-*.md")
    return path.read_text(encoding="utf-8")


def test_no_templates_found_is_an_error_not_a_pass(project, capsys):
    assert cp.main(["--gate", "G0", "--workspace", str(project)]) == 1
    out = capsys.readouterr().out
    assert "templates-not-found" in out and "--no-templates" in out
    report = last_report(project)
    assert "templates-not-found" in report and report.splitlines()[2].startswith("**Chưa kiểm mục bắt buộc")


def test_no_templates_flag_skips_the_template_checks_and_says_so_first(project, capsys):
    assert cp.main(["--gate", "G0", "--workspace", str(project), "--no-templates"]) == 0
    assert "Chưa kiểm mục bắt buộc" in capsys.readouterr().out
    lines = last_report(project).splitlines()
    assert lines[0].startswith("# check_profile") and lines[2].startswith("**Chưa kiểm mục bắt buộc")


def test_no_templates_flag_does_not_hide_other_errors(project):
    (project / "drafts" / cp.PROFILE).write_text(profile(**{"05-frontend": "bỏ"}), encoding="utf-8")
    (project / "drafts" / "05-frontend").mkdir()
    (project / "drafts" / "05-frontend" / "overview.md").write_text("# f\n", encoding="utf-8")
    assert cp.main(["--gate", "G0", "--workspace", str(project), "--no-templates"]) == 1


def test_templates_and_no_templates_together_are_an_argument_error(project, tmp_path):
    with pytest.raises(SystemExit) as stop:
        cp.main(["--gate", "G0", "--workspace", str(project), "--templates", str(tmp_path), "--no-templates"])
    assert stop.value.code == 2


def test_an_empty_templates_folder_is_an_error(project, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cp.main(["--gate", "G0", "--workspace", str(project), "--templates", str(empty)]) == 1
    assert "templates-empty" in capsys.readouterr().out


def test_given_templates_with_nothing_to_report_pass_and_carry_no_not_checked_note(project, tmp_path, capsys):
    templates = tree(tmp_path / "tpl", {"00-context/glossary.md": "# G\n"})
    assert cp.main(["--gate", "G0", "--workspace", str(project), "--templates", str(templates)]) == 0
    assert "Chưa kiểm" not in capsys.readouterr().out and "Chưa kiểm" not in last_report(project)


def test_cli_without_templates_flags_exits_1_in_a_subprocess(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {cp.PROFILE: profile()})
    result = run_cli("--gate", "G0", "--workspace", str(workspace))
    # the repository has no design-architecture/templates yet; once it has, the run uses them instead
    if cp.default_templates() is None:
        assert result.returncode == 1 and "templates-not-found" in result.stdout
    assert run_cli("--gate", "G0", "--workspace", str(workspace), "--no-templates").returncode == 0


# --- the gate map matches stages.md ----------------------------------------------------------------------------------------

def test_gate_entries_match_the_files_each_gate_creates_in_stages_md():
    text = STAGES.read_text(encoding="utf-8")
    for number in range(0, 11):
        section = re.search(rf"^## G{number}\. .*?(?=^## G|\Z)", text, re.S | re.M).group(0)
        created = next(line for line in section.splitlines() if line.startswith("- **File tạo ra:**"))
        created = created.split(".agent-workspace")[0]
        in_text = set(re.findall(r"\b(\d\d-[a-z-]+)/", created))
        in_map = {entry.split("/")[0] for entry in cp.GATE_ENTRIES[number] if re.match(r"\d\d-", entry)}
        assert in_text == in_map, f"G{number}: stages.md {sorted(in_text)} vs GATE_ENTRIES {sorted(in_map)}"
    assert {e.split("/")[0] for g in cp.GATE_ENTRIES.values() for e in g} == set(cp.PARTS)


# --- the script ----------------------------------------------------------------------------------------------------------------

def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_cli_exit_codes_and_report(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    base_dir = workspace / "drafts"
    tree(base_dir, {cp.PROFILE: profile("S", **{"05-frontend": "bỏ"}), **CONTEXT, "05-frontend/overview.md": "# f\n"})
    result = run_cli("--gate", "G1", "--workspace", str(workspace), "--date", "2026-10-12", "--no-templates")
    assert result.returncode == 1 and "omitted-part-present" in result.stdout
    assert "05-frontend/overview.md" in (workspace / "checks" / "profile-2026-10-12.md").read_text(encoding="utf-8")
    (base_dir / "05-frontend" / "overview.md").unlink()
    result = run_cli("--gate", "g1", "--workspace", str(workspace), "--no-templates")
    assert result.returncode == 0 and "0 lỗi chặn" in result.stdout


def test_cli_argument_errors(tmp_path):
    assert run_cli("--workspace", str(tmp_path)).returncode == 2  # --gate is required
    for bad in ("G11", "X", "4", "G"):
        assert run_cli("--gate", bad, "--workspace", str(tmp_path)).returncode == 2, bad
    assert run_cli("--gate", "G1", "--root", str(tmp_path / "nope")).returncode == 2
    assert run_cli("--gate", "G1", "--root", str(tmp_path), "--templates", str(tmp_path / "nope")).returncode == 2


def test_cli_lists_at_most_25_errors(tmp_path):
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", {cp.PROFILE: profile("S", **{"05-frontend": "bỏ"}), **{f"05-frontend/f{i}.md": "# f\n" for i in range(30)}})
    result = run_cli("--gate", "G0", "--workspace", str(workspace), "--date", "2026-10-12", "--no-templates")
    assert result.stdout.count("error: `") == 25 and "5 lỗi nữa" in result.stdout
    assert (workspace / "checks" / "profile-2026-10-12.md").read_text(encoding="utf-8").count("[omitted-part-present]") == 30
