"""The templates, checklists and profiles.md of design-architecture, and the sample draft built from them, stay in line with the scripts.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import check_profile as cp  # noqa: E402
import idlist  # noqa: E402

ARCH = HERE.parent.parent / "design-architecture"
TEMPLATES = ARCH / "templates"
CHECKLISTS = ARCH / "checklists"
SAMPLE = ARCH / "examples" / "cafe-order"
STAGES = (HERE.parent / "workflow" / "stages.md").read_text(encoding="utf-8")
IDS = idlist.load()
TODAY = "2026-10-13"  # the sample's end-of-support dates are checked against a fixed day, not the day the test runs

TEMPLATE_FILES = sorted(p for p in TEMPLATES.rglob("*.md"))
RELS = [p.relative_to(TEMPLATES).as_posix() for p in TEMPLATE_FILES]
# Written by a script (calc_capacity.py; archive_release.py for CHANGELOG.md): the template only describes the file, so it has no `<!-- required -->` section.
GENERATED = {"CHANGELOG.md", "00-context/assumptions.md", "03-capacity/workload-model.md", "03-capacity/data-sizing.md", "03-capacity/storage-sizing.md",
             "03-capacity/compute-sizing.md", "03-capacity/cost-model.md"}
# The 13 parts and the two root files of architecture/, and the checklist file for each.
CHECKLISTS_OF = {"00-context": "00-context.md", "01-system": "01-system.md", "02-tech-stack": "02-tech-stack.md", "03-capacity": "03-capacity.md",
                 "04-flows": "04-flows.md", "05-frontend": "05-frontend.md", "06-backend": "06-backend.md", "07-data": "07-data.md",
                 "08-security": "08-security.md", "09-infrastructure": "09-infrastructure.md", "10-process": "10-process.md", "11-risks": "11-risks.md",
                 "12-roadmap": "12-roadmap.md", "README.md": "readme.md", "CHANGELOG.md": "changelog.md"}
# Templates whose file must have a required "Tối ưu" section (Q2: a number-valued target per tier).
OPTIMISE = [
    "01-system/integrations.md", "05-frontend/device-matrix.md", "05-frontend/performance-budget.md", "05-frontend/{app}/routing-navigation.md",
    "05-frontend/{app}/state-data.md", "05-frontend/{app}/networking-offline.md", "05-frontend/{app}/build-delivery.md",
    "06-backend/overview.md", "06-backend/communication.md", "06-backend/cross-cutting.md",
    "07-data/overview.md", "07-data/object-storage.md", "07-data/cache.md", "07-data/messaging.md", "07-data/consistency.md", "07-data/backup-recovery.md",
    "08-security/authz-matrix.md", "08-security/secrets-compliance.md",
    "09-infrastructure/topology.md", "09-infrastructure/environments.md", "09-infrastructure/scaling-ha.md", "09-infrastructure/observability.md",
    "09-infrastructure/ci-cd.md", "10-process/delivery.md", "10-process/data-change.md", "10-process/maintenance.md", "10-process/operations.md",
]
# What the frontend (Q7) must not decide: no heading of a 05-frontend template names it.
VISUAL_WORDS = ("màu", "font", "bố cục", "khoảng cách", "icon", "hiệu ứng", "animation", "chuyển động", "minh họa")


def lines_of(path: Path) -> list[str]:
    return cp.read_lines(path)


# --- the templates ------------------------------------------------------------------------------------------------------------

def test_there_are_templates():
    assert TEMPLATE_FILES, "design-architecture/templates is empty"
    assert {rel.split("/")[0] for rel in RELS} == set(CHECKLISTS_OF)  # the 13 part folders, README.md and CHANGELOG.md


@pytest.mark.parametrize("rel", RELS)
def test_template_path_has_no_angle_brackets(rel):
    assert "<" not in rel and ">" not in rel, "< and > cannot be used in a file name on Windows: use {name} or xxx"


@pytest.mark.parametrize("rel", RELS)
def test_template_has_a_required_section_unless_a_script_writes_the_file(rel):
    required = cp.required_headings(lines_of(TEMPLATES / rel))
    if rel in GENERATED:
        assert required == [], "a file written by calc_capacity.py has nothing the Designer must fill"
    else:
        assert required, "a template that the Designer fills needs at least one <!-- required --> section"


@pytest.mark.parametrize("rel", RELS)
def test_required_mark_comes_straight_after_a_heading_and_every_mark_counts(rel):
    lines = lines_of(TEMPLATES / rel)
    masked = cp.mask_fences(lines)
    marks = [i for i, line in enumerate(masked) if cp.REQUIRED_MARK.fullmatch(line.strip())]  # a note may quote the mark inside backticks
    for i in marks:
        assert i > 0 and cp.HEADING_RE.match(masked[i - 1]), f"{rel}:{i + 1} the mark must be on the line right after a heading"
    assert len(marks) == len(cp.required_headings(lines)), "a stray mark that required_headings does not read"


@pytest.mark.parametrize("rel", RELS)
def test_template_names_no_real_id(rel):
    """A real ID in a template would become a second definition of that ID in every draft made from it."""
    text = "\n".join(lines_of(TEMPLATES / rel))
    real = sorted({m.group(1) for m in IDS.id_re().finditer(text) if not IDS.is_placeholder(m.group(1))})
    assert real == []


def test_project_profile_template_has_a_level_and_all_thirteen_parts():
    path = TEMPLATES / "00-context" / "project-profile.md"
    rows, findings = cp.parse_profile(path, "00-context/project-profile.md")
    assert [f.render() for f in findings] == []
    assert list(rows) == list(cp.PARTS)


def test_tables_template_has_exactly_one_pending_calc_pair_and_no_marker_text_elsewhere():
    import calc_capacity as cc

    text = (TEMPLATES / "07-data" / "databases" / "{db}" / "tables.md").read_text(encoding="utf-8")
    pairs = list(cc.CALC_BLOCK.finditer(text))
    assert len(pairs) == 1 and pairs[0].group(3).strip() == cc.PENDING
    assert text.count("<!-- BEGIN:calc") == 1 and text.count("<!-- END:calc") == 1  # the note at the top must not quote a whole marker


def test_a_template_with_a_placeholder_folder_matches_an_object_folder():
    assert cp.match_template("06-backend/services/order-service/scaling.md", RELS) == "06-backend/services/{service}/scaling.md"
    assert cp.match_template("07-data/databases/order-db/tables.md", RELS) == "07-data/databases/{db}/tables.md"
    assert cp.match_template("04-flows/FL-001-dat-don.md", RELS) == "04-flows/FL-xxx-{tên}.md"
    assert cp.match_template("02-tech-stack/layers/data.md", RELS) == "02-tech-stack/layers/{layer}.md"


@pytest.mark.parametrize("rel", RELS)
def test_a_template_with_a_basis_column_says_what_counts_as_a_basis(rel):
    text = (TEMPLATES / rel).read_text(encoding="utf-8")
    if re.search(r"^\|.*Cơ sở", text, re.MULTILINE):
        assert "Mỗi tham số thiết kế" in text.split("\n## ", 1)[0], "the note at the top must say a Cơ sở cell needs an ID or a link"


def test_an_app_folder_matches_the_frontend_templates():
    assert cp.match_template("05-frontend/web/state-data.md", RELS) == "05-frontend/{app}/state-data.md"
    app_files = sorted(r.rsplit("/", 1)[1] for r in RELS if r.startswith("05-frontend/{app}/"))
    assert app_files == sorted(["architecture.md", "routing-navigation.md", "state-data.md", "networking-offline.md", "auth-session.md",
                                "build-delivery.md", "folder-structure.md"])


@pytest.mark.parametrize("rel", [r for r in RELS if r.startswith("05-frontend/")])
def test_frontend_headings_decide_nothing_visible(rel):
    headings = [m.group(2).casefold() for line in lines_of(TEMPLATES / rel) if (m := cp.HEADING_RE.match(line))]
    assert [h for h in headings if any(w in h for w in VISUAL_WORDS)] == []


@pytest.mark.parametrize("rel", OPTIMISE)
def test_these_templates_have_a_required_optimise_section(rel):
    keys = cp.required_headings(lines_of(TEMPLATES / rel))
    assert any(k.startswith("tối ưu") for k in keys), rel


def test_optimise_list_names_real_templates():
    assert set(OPTIMISE) <= set(RELS)


@pytest.mark.parametrize("rel", RELS)
def test_a_template_that_defines_a_backlink_id_has_a_required_backlink_section(rel):
    """A heading `### API-xxx`, `# SVC-xxx` ... defines the ID, so the file needs "Được dùng bởi" (check_links.py: missing-backlink)."""
    lines = lines_of(TEMPLATES / rel)
    defines = any((m := cp.HEADING_RE.match(line)) and re.match(rf"(?:{'|'.join(IDS.backlink_kinds)})-", m.group(2)) for line in cp.mask_fences(lines))
    if defines:
        assert any(k.startswith("được dùng bởi") for k in cp.required_headings(lines))


def test_ids_are_defined_in_their_home_templates_only():
    """EVT in 07-data/messaging.md, BKT in 07-data/object-storage.md, API in api.md, SVC in responsibility.md, TBL in tables.md."""
    homes = {"EVT": "07-data/messaging.md", "BKT": "07-data/object-storage.md", "API": "06-backend/services/{service}/api.md",
             "SVC": "06-backend/services/{service}/responsibility.md", "TBL": "07-data/databases/{db}/tables.md"}
    for kind, home in homes.items():
        owners = [rel for rel in RELS if any((m := cp.HEADING_RE.match(line)) and m.group(2).startswith(f"{kind}-") for line in cp.mask_fences(lines_of(TEMPLATES / rel)))]
        assert owners == [home], f"{kind}: {owners}"


def test_risk_register_template_is_one_table_the_scripts_can_read():
    import check_workspace as cw

    text = (TEMPLATES / "11-risks" / "risk-register.md").read_text(encoding="utf-8")
    assert sum(1 for line in text.splitlines() if line.startswith("|")) == 3, "check_links.py wants every table here to have the components column"
    header, rows = cw.table(text)
    assert None not in (cw.column(header, "ID"), cw.column(header, "Khả năng", "Điểm"), cw.column(header, "Trạng thái"))
    assert cw.column(header, "Thành phần liên quan") is not None
    assert len(rows) == 1 and cw.clean(rows[0][1][0]).startswith("R-xxx")  # the placeholder row, which check_workspace.py skips


@pytest.mark.parametrize("part,name", [(p, n) for p, n in CHECKLISTS_OF.items() if p[0].isdigit()])
def test_checklist_names_the_gate_that_reaches_its_part(part, name):
    gate = next(g for g, entries in cp.GATE_ENTRIES.items() if part in entries)
    first = next(line for line in (CHECKLISTS / name).read_text(encoding="utf-8").splitlines() if line.startswith("Gate:"))
    assert f"G{gate}" in re.findall(r"G\d+", first), f"{name}: {first[:80]}"


def test_the_sample_has_no_object_storage_and_says_so():
    assert not (SAMPLE / "capacity" / "storage.yaml").exists() and not (SAMPLE / "drafts" / "07-data" / "object-storage.md").exists()
    assert "Không có object storage" in (SAMPLE / "drafts" / "03-capacity" / "storage-sizing.md").read_text(encoding="utf-8")


# --- the checklists and profiles.md --------------------------------------------------------------------------------------------

def test_every_templated_part_has_a_checklist_and_there_is_no_other():
    assert sorted(p.name for p in CHECKLISTS.glob("*.md")) == sorted(CHECKLISTS_OF.values())
    for name in CHECKLISTS_OF.values():
        assert re.search(r"^- \[ \] ", (CHECKLISTS / name).read_text(encoding="utf-8"), re.MULTILINE)


def table_rows(text: str, first_header: str) -> list[list[str]]:
    rows, inside = [], False
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            inside = False
            continue
        cells = cp.split_cells(line)
        if cp.heading_key(cells[0]) == first_header.casefold():
            inside = True
            continue
        if inside and not re.fullmatch(r"[:\-\s|]*", line):
            rows.append(cells)
    return rows


def stages_level_values() -> dict[str, list[str]]:
    """{part: [S, M, L, XL]} from the table "Phần của architecture/ theo mức áp dụng" of stages.md."""
    def value(cell: str) -> str:
        cell = cp.heading_key(cell)
        return "có" if cell.startswith(("có", "thêm")) else "bỏ" if cell.startswith("bỏ") else "rút gọn"

    section = STAGES.split("## Phần của `architecture/` theo mức áp dụng", 1)[1].split("\n## ", 1)[0]
    out: dict[str, list[str]] = {}
    for cells in table_rows(section, "Phần"):
        for part in re.findall(r"\d\d-[a-z-]+", cells[0]):
            out[part] = [value(c) for c in cells[1:5]]
    return out


def test_profiles_md_part_table_equals_the_table_of_stages_md():
    text = (ARCH / "profiles.md").read_text(encoding="utf-8")
    section = text.split("## Dòng cấp phần", 1)[1].split("\n## ", 1)[0]
    ours = {cells[0]: [cp.heading_key(c) for c in cells[1:5]] for cells in table_rows(section, "Phần")}
    assert list(ours) == list(cp.PARTS)
    assert ours == stages_level_values()
    assert all(v in cp.VALUES for values in ours.values() for v in values)


def test_profiles_md_file_rows_name_files_of_a_part_that_is_cut_down_at_level_s():
    text = (ARCH / "profiles.md").read_text(encoding="utf-8")
    section = text.split("## Dòng cấp file", 1)[1].split("\n## ", 1)[0]
    rows = table_rows(section, "File")
    assert rows
    for cells in rows:
        part = cells[0].split("/")[0]
        assert part in cp.PARTS and stages_level_values()[part][0] == "rút gọn", cells[0]
        assert cells[2:5] == ["có", "có", "có"]


# --- the sample draft ----------------------------------------------------------------------------------------------------------

@pytest.fixture()
def sample(tmp_path):
    workspace = tmp_path / "cafe-order"
    shutil.copytree(SAMPLE, workspace)
    return workspace


def run(script: str, workspace: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(HERE / script), "--workspace", str(workspace), *args, "--date", TODAY],
                          capture_output=True, text=True, encoding="utf-8")


def test_the_sample_has_no_check_reports_and_no_generated_file_is_stale(sample):
    assert not (SAMPLE / "checks").exists()
    result = run("calc_capacity.py", sample, "--check")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("script,args", [
    ("check_profile.py", ("--gate", "G10", "--templates", str(TEMPLATES))),
    ("check_trace.py", ("--gate", "G10")),
    ("check_links.py", ()),
    ("check_versions.py", ()),
    ("check_numbers.py", ()),
])
def test_scripts_run_clean_on_the_sample(sample, script, args):
    result = run(script, sample, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_sample_has_all_13_parts_and_the_root_readme(sample):
    """Phase 5B widened the sample to every part; G10 wants each of them plus README.md (CHANGELOG.md is written by archive_release.py)."""
    for part in cp.PARTS:
        assert any((sample / "drafts" / part).rglob("*.md")), part
    assert (sample / "drafts" / "README.md").is_file()
    assert not (sample / "drafts" / "CHANGELOG.md").exists()


def test_the_sample_at_gate_g10_has_no_check_report_left_in_the_repo(sample):
    run("check_profile.py", sample, "--gate", "G10", "--templates", str(TEMPLATES))
    assert (sample / "checks").exists() and not (SAMPLE / "checks").exists()


@pytest.mark.parametrize("rel", RELS)
def test_a_required_section_has_something_to_fill_in(rel):
    """check_profile calls a required section still the template's when every line is the template's own: static text (like the dev rules of
    implementation-plan.md) must not be marked required. A section to fill in carries a placeholder (<…>, {…}, xx, …, an empty table row)."""
    lines = cp.read_lines(TEMPLATES / rel)
    sections = {key: body for key, _, _, body in cp.sections(lines)}
    static = [key for key in cp.required_headings(lines) if not re.search(r"[<{…]|xx|\.\.\.|\|\s*\|", "\n".join(cp.content_lines(sections.get(key, []))))]
    assert static == [], f"{rel}: mục bắt buộc chỉ có chữ cố định, người viết giữ nguyên sẽ bị báo 'còn nguyên mẫu': {static}"
