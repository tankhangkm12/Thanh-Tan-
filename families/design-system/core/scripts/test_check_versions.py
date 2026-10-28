"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import datetime
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import check_versions as cv  # noqa: E402

SCRIPT = Path(__file__).parent / "check_versions.py"
TODAY = datetime.date(2026, 10, 12)
CFG, ERRORS = cv.load_config(cv.DEFAULT_CONFIG)
assert CFG is not None, ERRORS

PG_LINK = "[vòng đời](https://www.postgresql.org/support/versioning/)"
README = """# Tech stack

| Lớp | Công nghệ | Phiên bản | TC đáp ứng |
| --- | --- | --- | --- |
| data | PostgreSQL | 16.4 | TC-01 |
| backend | NestJS | 10.4 | TC-02 |
"""
HEADER = "| Công nghệ | Phiên bản chốt | Ngày phát hành, ngày hết hỗ trợ | Tính năng dự án dựa vào | Rủi ro |\n| --- | --- | --- | --- | --- |\n"
VERSIONS = HEADER + (
    f"| PostgreSQL — database quan hệ cho order-db | 16.4 (nhận bản vá 16.x) | 2024-09-12; 2028-11-09 {PG_LINK} | jsonb | R-01 |\n"
    "| NestJS | 10.4 | phát hành 2024-06-01, hết hỗ trợ 2027-12-31 [nguồn](https://docs.nestjs.com/releases) | modules | R-02 |\n"
)


def tree(root: Path, readme: str | None = README, versions: str | None = VERSIONS) -> Path:
    folder = root / "02-tech-stack"
    folder.mkdir(parents=True)
    if readme is not None:
        (folder / "README.md").write_text(readme, encoding="utf-8")
    if versions is not None:
        (folder / "versions-features.md").write_text(versions, encoding="utf-8")
    return root


def run(root: Path, cfg: cv.Config = CFG, today: datetime.date = TODAY):
    return cv.run(root, cfg, today)


def codes(root: Path, **kwargs) -> list[str]:
    return sorted(f.code for f in run(root, **kwargs)[0])


def errors(root: Path, **kwargs) -> list[str]:
    return sorted(f.code for f in run(root, **kwargs)[0] if f.blocking)


def with_row(row: str, readme: str = README) -> str:
    return readme  # placeholder to keep call sites readable


RISK = "[R-01](../11-risks/risk-register.md#r-01)"


def versions_with(cell: str, version: str = "16.4", risk: str = RISK) -> str:
    return HEADER + f"| PostgreSQL | {version} | {cell} | x | {risk} |\n| NestJS | 10.4 | 2024-06-01; 2027-12-31 [n](https://a.b/c) | x | [R-02](../11-risks/risk-register.md#r-02) |\n"


# --- the matrix ------------------------------------------------------------------------------------------------------------------------

def test_a_complete_matrix_is_clean(tmp_path):
    findings, stats = run(tree(tmp_path))
    assert findings == [] and stats == {"readme": 2, "versions": 2}


def test_every_technology_of_the_readme_needs_a_row(tmp_path):
    readme = README + "| cache | Redis | 7.2 | TC-03 |\n"
    found, _ = run(tree(tmp_path, readme))
    assert [(f.code, f.path, f.line) for f in found] == [("tech-missing-from-versions", "02-tech-stack/README.md", 7)]
    assert "Redis" in found[0].message


def test_names_match_without_role_case_markup_or_spacing(tmp_path):
    readme = ("| Lớp | Công nghệ | Phiên bản |\n| --- | --- | --- |\n| data | **PostgreSQL** (order-db) | 16.4 |\n| backend | [NestJS](https://nestjs.com)  | 10.4 |\n")
    versions = HEADER + (f"| postgresql: database quan hệ | 16.4 | 2024-09-12; 2028-11-09 {PG_LINK} | x | R |\n"
                         "| `NestJS`   — framework | 10.4 | 2024-06-01; 2027-12-31 [n](https://a.b/c) | x | R |\n")
    assert codes(tree(tmp_path, readme, versions)) == []


@pytest.mark.parametrize("cell", ["PostgreSQL — database quan hệ cho order-db", "PostgreSQL – vai trò", "PostgreSQL - vai trò", "PostgreSQL (order-db)", "PostgreSQL: order-db"])
def test_a_role_after_the_name_is_ignored(tmp_path, cell):
    versions = HEADER + f"| {cell} | 16.4 | 2024-09-12; 2028-11-09 {PG_LINK} | x | R |\n| NestJS | 10.4 | 2024-06-01; 2027-12-31 [n](https://a.b/c) | x | R |\n"
    assert codes(tree(tmp_path, README, versions)) == []


def test_one_technology_per_row(tmp_path):
    readme = README.replace("| NestJS | 10.4 |", "| NestJS + TypeORM | 10.4 |")
    assert errors(tree(tmp_path, readme)) == ["tech-missing-from-versions"]


def test_a_name_that_only_contains_another_is_not_a_match(tmp_path):
    versions = VERSIONS.replace("| NestJS |", "| NestJS Core |")
    assert errors(tree(tmp_path, README, versions)) == ["tech-missing-from-versions"]


def test_version_in_the_readme_must_equal_the_one_in_the_matrix(tmp_path):
    readme = README.replace("16.4", "16.3")
    found, _ = run(tree(tmp_path, readme))
    assert [f.code for f in found if f.blocking] == ["version-mismatch"] and "16.3" in found[0].message and "16.4" in found[0].message


def test_patch_text_in_the_version_cell_does_not_confuse_the_comparison(tmp_path):
    readme = README.replace("| 16.4 |", "| 16.4 (bản vá 16.x) |")
    assert errors(tree(tmp_path, readme)) == []
    assert errors(tree(tmp_path / "b", README.replace("| 16.4 |", "| v16.4 |"))) == []


@pytest.mark.parametrize("cell", ["", "16", "mới nhất", "latest", "chưa chọn"])
def test_the_readme_version_must_be_a_number(tmp_path, cell):
    readme = README.replace("| 16.4 |", f"| {cell} |")
    assert errors(tree(tmp_path, readme)) == ["version-not-pinned"]


def test_the_same_technology_in_two_roles(tmp_path):
    readme = README + "| data | PostgreSQL | 15.8 | TC-01 |\n"
    versions = VERSIONS + f"| PostgreSQL — user-db | 15.8 | 2023-10-05; 2027-11-11 {PG_LINK} | x | R |\n"
    assert codes(tree(tmp_path, readme, versions)) == []
    assert errors(tree(tmp_path / "b", readme.replace("15.8", "14.1"), versions)) == ["version-mismatch"]


def test_a_row_the_readme_does_not_list_is_only_a_warning(tmp_path):
    versions = VERSIONS + f"| Redis | 7.2 | 2023-08-15; 2030-08-15 {PG_LINK} | x | R |\n"
    found, _ = run(tree(tmp_path, README, versions))
    assert [(f.code, f.blocking) for f in found] == [("versions-row-not-in-readme", False)]


def test_the_same_technology_and_version_twice_is_an_error(tmp_path):
    versions = VERSIONS + f"| PostgreSQL — user-db | 16.4 | 2024-09-12; 2028-11-09 {PG_LINK} | x | R |\n"
    found, _ = run(tree(tmp_path, README, versions))
    assert [(f.code, f.blocking, f.line) for f in found] == [("duplicate-row", True, 5)] and "dòng 3" in found[0].message


def test_several_tables_in_the_readme_are_all_read(tmp_path):
    readme = ("## Data\n\n| Công nghệ | Phiên bản |\n| --- | --- |\n| PostgreSQL | 16.4 |\n\n## Backend\n\n| Công nghệ | Phiên bản |\n| --- | --- |\n| NestJS | 10.4 |\n")
    findings, stats = run(tree(tmp_path, readme))
    assert findings == [] and stats["readme"] == 2


def test_other_tables_and_fenced_code_are_ignored(tmp_path):
    readme = README + "\n| Bước | Mô tả |\n| --- | --- |\n| 1 | làm gì đó |\n\n```\n| Công nghệ | Phiên bản |\n| --- | --- |\n| Ghost | 1.0 |\n```\n"
    assert codes(tree(tmp_path, readme)) == []


# --- the version cell ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("version", ["16", "16.x", "latest", "mới nhất", "LATEST", "", "nightly", "main", "lts"])
def test_a_version_that_is_not_major_dot_minor_is_an_error(tmp_path, version):
    readme = README.replace("| 16.4 |", "| 16.4 |")  # README fine; the matrix cell is what is wrong
    result = errors(tree(tmp_path, readme, versions_with(f"2024-09-12; 2028-11-09 {PG_LINK}", version)))
    assert "version-not-pinned" in result, version


@pytest.mark.parametrize("version", ["16.4", "16.4.1", "v16.4", "16.4 (nhận bản vá 16.x)", "5.4.2-lts", "1.0"])
def test_pinned_forms(tmp_path, version):
    readme = README.replace("| 16.4 |", f"| {version} |")
    assert not [f for f in run(tree(tmp_path, readme, versions_with(f"2024-09-12; 2028-11-09 {PG_LINK}", version)))[0] if f.code == "version-not-pinned"]


# --- end of support and source link ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cell", [
    f"2024-09-12; 2028-11-09 {PG_LINK}", f"2024-09-12 → 2028-11-09 {PG_LINK}", f"phát hành 2024-09-12, hết hỗ trợ 2028-11-09 {PG_LINK}", f"hết hỗ trợ 2028-11-09 {PG_LINK}",
    f"EOL: 2028-11-09 {PG_LINK}", f"End of life 2028-11-09, https://www.postgresql.org/support/versioning/", f"2024-09 / 2028-11 {PG_LINK}",
    f"2024-09-12; hết hỗ trợ 2028-11 {PG_LINK}", f"2028-11-09 (hết hỗ trợ), phát hành 2024-09-12. {PG_LINK}", f"2024-09-12; chưa công bố {PG_LINK}", f"không có ngày EOL, https://example.com/policy",
])
def test_accepted_lifecycle_cells(tmp_path, cell):
    assert not [f for f in run(tree(tmp_path, README, versions_with(cell)))[0] if f.blocking], cell


@pytest.mark.parametrize("cell,code", [
    (f"2024-09-12 {PG_LINK}", "eol-missing"), (PG_LINK, "eol-missing"), ("", "source-link-missing"), ("2024-09-12; 2028-11-09", "source-link-missing"),
    (f"2024-09-12; 2024-09-12 {PG_LINK}", "eol-before-release"), (f"2028-11-09; 2024-09-12 {PG_LINK}", "eol-before-release"), (f"phát hành 2028-01-01, hết hỗ trợ 2027-01-01 {PG_LINK}", "eol-before-release"),
    (f"2024-13-01; 2028-11-09 {PG_LINK}", "date-invalid"), (f"2024-09-12; 2028-02-30 {PG_LINK}", "date-invalid"), (f"hết hỗ trợ 2028-00-10 {PG_LINK}", "date-invalid"),
    ("chưa công bố", "source-link-missing"), ("2024-09-12; 2028-11-09 https://", "source-link-missing"),
])
def test_rejected_lifecycle_cells(tmp_path, cell, code):
    assert code in errors(tree(tmp_path, README, versions_with(cell))), cell


def test_a_date_inside_a_link_is_not_an_end_date(tmp_path):
    cell = "[trang](https://example.com/releases/2028-11-09/lifecycle)"
    assert "eol-missing" in errors(tree(tmp_path, README, versions_with(cell)))


def test_a_date_inside_a_bare_url_is_not_an_end_date(tmp_path):
    cell = "2024-09-12 https://example.com/releases/2028-11-09/lifecycle"
    assert "eol-missing" in errors(tree(tmp_path, README, versions_with(cell)))


def test_a_date_followed_by_a_link_labelled_end_of_support_is_the_end_date(tmp_path):
    cell = "2028-11-09 [hết hỗ trợ](https://example.com/eol)"
    assert not [f for f in run(tree(tmp_path, README, versions_with(cell)))[0] if f.blocking]


def test_labels_decide_which_of_two_dates_is_the_end(tmp_path):
    """The label sits next to the end date, whichever order the dates are written in."""
    for cell in ("2028-11-09 (hết hỗ trợ), phát hành 2024-09-12", "phát hành 2024-09-12, hết hỗ trợ 2028-11-09", "2024-09-12 (phát hành), 2028-11-09 (hết hỗ trợ)"):
        _, end, _, _, _ = cv.lifecycle(f"{cell} https://a.b/c", CFG)
        release = cv.lifecycle(f"{cell} https://a.b/c", CFG)[0]
        assert (release, end) == (datetime.date(2024, 9, 12), datetime.date(2028, 11, 9)), cell


def test_the_end_date_of_a_month_is_its_last_day_the_release_its_first(tmp_path):
    cell = f"2028-11; 2028-11 {PG_LINK}"
    assert "eol-before-release" not in errors(tree(tmp_path, README, versions_with(cell)))  # 2028-11-01 < 2028-11-30
    assert cv.make_date("2028", "02", None, True) == datetime.date(2028, 2, 29) and cv.make_date("2028", "02", None, False) == datetime.date(2028, 2, 1)
    assert cv.make_date("2027", "02", "29", False) is None and cv.make_date("2027", "13", None, False) is None


@pytest.mark.parametrize("eol,codes_expected", [
    ("2026-10-11", ["eol-passed"]), ("2026-10-12", ["eol-passed"]), ("2025-01-01", ["eol-passed"]),
    ("2026-10-13", ["eol-soon"]), ("2027-03-01", ["eol-soon"]), ("2027-10-12", ["eol-soon"]),
    ("2027-10-20", []), ("2030-01-01", []),
])
def test_end_of_support_past_blocks_close_warns_far_is_silent(tmp_path, eol, codes_expected):
    found, _ = run(tree(tmp_path, README, versions_with(f"2020-01-01; {eol} {PG_LINK}")))
    eol_codes = [(f.code, f.blocking) for f in found if f.code.startswith("eol-")]
    assert eol_codes == [(code, code == "eol-passed") for code in codes_expected]


NO_RISK = ["", " ", "R-01", "chưa có", "[nguồn](https://a.b/c)", "[rủi ro](../11-risks/risk-register.md)", "[R](x.md)", "R-01 (không link)"]


@pytest.mark.parametrize("risk", NO_RISK)
def test_a_version_that_ends_within_12_months_needs_an_r_link_in_the_risk_column(tmp_path, risk):
    found, _ = run(tree(tmp_path, README, versions_with(f"2020-01-01; 2027-03-01 {PG_LINK}", risk=risk)))
    assert [(f.code, f.blocking) for f in found] == [("eol-soon", False), ("eol-soon-without-risk", True)], risk
    assert "R-xx" in found[1].message


@pytest.mark.parametrize("risk", [RISK, "[R-05](risk-register.md)", "[rủi ro](../11-risks/risk-register.md#r-05)", "[R-05](x.md), [R-06](y.md)", "[`R-05`](x.md) công nghệ hết hạn",
                                  "[bản vá](https://a.b/c) và [R-12](../11-risks/risk-register.md#r-12)", "[r-05](x.md)"])
def test_an_r_link_in_the_risk_cell_satisfies_it(tmp_path, risk):
    found, _ = run(tree(tmp_path, README, versions_with(f"2020-01-01; 2027-03-01 {PG_LINK}", risk=risk)))
    assert [(f.code, f.blocking) for f in found] == [("eol-soon", False)], risk


def test_without_a_risk_column_the_close_end_of_support_is_an_error_naming_the_column(tmp_path):
    versions = ("| Công nghệ | Phiên bản chốt | Ngày phát hành, ngày hết hỗ trợ |\n| --- | --- | --- |\n"
                f"| PostgreSQL | 16.4 | 2020-01-01; 2027-03-01 {PG_LINK} |\n| NestJS | 10.4 | 2024-06-01; 2027-12-31 [n](https://a.b/c) |\n")
    found, _ = run(tree(tmp_path, README, versions))
    assert sorted(f.code for f in found) == ["eol-soon", "eol-soon-without-risk"] and any("không có cột Rủi ro" in f.message for f in found)
    # a far end of support needs no column at all
    ok = versions.replace("2027-03-01", "2030-03-01")
    assert run(tree(tmp_path / "b", README, ok))[0] == []


def test_a_passed_end_of_support_is_one_error_not_two(tmp_path):
    found, _ = run(tree(tmp_path, README, versions_with(f"2020-01-01; 2026-06-01 {PG_LINK}", risk="")))
    assert [f.code for f in found] == ["eol-passed"]


def test_the_risk_rule_is_per_row(tmp_path):
    versions = HEADER + (f"| PostgreSQL | 16.4 | 2020-01-01; 2027-03-01 {PG_LINK} | x | {RISK} |\n"
                         f"| NestJS | 10.4 | 2020-01-01; 2027-06-01 [n](https://a.b/c) | x | |\n")
    found, _ = run(tree(tmp_path, README, versions))
    assert [(f.code, f.line) for f in found if f.blocking] == [("eol-soon-without-risk", 4)]


def test_the_warning_window_comes_from_the_data_file(tmp_path):
    path = tmp_path / "v.yaml"
    data = yaml.safe_load(cv.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["eol_warning_months"] = 0
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    cfg, _ = cv.load_config(path)
    found, _ = run(tree(tmp_path / "t", README, versions_with(f"2020-01-01; 2026-12-01 {PG_LINK}", risk="")), cfg)
    assert [f.code for f in found] == []
    data["eol_warning_months"] = 24
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    wide, _ = cv.load_config(path)
    found, _ = run(tree(tmp_path / "u", README, versions_with(f"2020-01-01; 2028-06-01 {PG_LINK}", risk="")), wide)
    assert [f.code for f in found if f.line == 3] == ["eol-soon", "eol-soon-without-risk"]


# --- third-party layer: date versions and SaaS -------------------------------------------------------------------------------------------

README3 = """# Tech stack

| Lớp | Công nghệ | Phiên bản | TC đáp ứng |
| --- | --- | --- | --- |
| data | PostgreSQL | 16.4 | TC-01 |
| third-party | Stripe API | {stripe} | TC-04 |
| third-party | Acme Mail | {mail} | TC-05 |
"""
CHANGELOG = "[changelog](https://stripe.com/docs/upgrades)"


def matrix3(stripe_row: str, mail_row: str | None = None) -> str:
    mail_row = mail_row or "| Acme Mail | 3.2 | 2024-01-01; 2029-01-01 [n](https://a.b/c) | x | [R-04](r.md#r-04) |\n"
    return HEADER + (f"| PostgreSQL | 16.4 | 2024-09-12; 2028-11-09 {PG_LINK} | x | {RISK} |\n" + stripe_row + mail_row)


def stack3(tmp_path: Path, stripe_readme: str, stripe_row: str, mail_readme: str = "3.2", mail_row: str | None = None) -> Path:
    return tree(tmp_path, README3.format(stripe=stripe_readme, mail=mail_readme), matrix3(stripe_row, mail_row))


def test_third_party_may_use_a_date_version(tmp_path):
    root = stack3(tmp_path, "2025-03-01", f"| Stripe API | 2025-03-01 | 2025-03-01; chưa công bố {CHANGELOG} | x | R |\n")
    assert run(root)[0] == []


def test_third_party_may_use_saas_without_a_version_and_needs_no_end_date(tmp_path):
    saas = "SaaS, không phiên bản"
    root = stack3(tmp_path, saas, f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n")
    assert run(root)[0] == []


def test_a_saas_row_must_still_link_the_changelog_or_deprecation_policy(tmp_path):
    saas = "SaaS, không phiên bản"
    root = stack3(tmp_path, saas, f"| Stripe API | {saas} | không công bố | x | R |\n")
    found, _ = run(root)
    assert [f.code for f in found] == ["source-link-missing"] and "changelog" in found[0].message and "chính sách ngừng hỗ trợ" in found[0].message
    root2 = stack3(tmp_path / "b", saas, f"| Stripe API | {saas} |  | x | R |\n")
    assert [f.code for f in run(root2)[0]] == ["source-link-missing"]


def test_saas_in_the_matrix_must_equal_saas_in_the_readme(tmp_path):
    saas = "SaaS, không phiên bản"
    root = stack3(tmp_path, "2025-03-01", f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n")
    found, _ = run(root)
    assert [f.code for f in found] == ["version-mismatch"] and "saas" in found[0].message and "2025-03-01" in found[0].message


def test_date_versions_must_match_between_the_two_files(tmp_path):
    root = stack3(tmp_path, "2025-03-01", f"| Stripe API | 2025-04-01 | 2025-04-01; chưa công bố {CHANGELOG} | x | R |\n")
    found, _ = run(root)
    assert [f.code for f in found] == ["version-mismatch"] and "2025-03-01" in found[0].message and "2025-04-01" in found[0].message


def test_third_party_may_still_use_major_minor(tmp_path):
    assert run(stack3(tmp_path, "3.1", f"| Stripe API | 3.1 | 2024-01-01; 2029-01-01 {CHANGELOG} | x | R |\n"))[0] == []


def test_other_layers_cannot_use_date_versions_or_saas(tmp_path):
    readme = README.replace("| 16.4 |", "| 2025-03-01 |")
    versions = versions_with(f"2025-03-01; chưa công bố {PG_LINK}", version="2025-03-01")
    found = [f for f in run(tree(tmp_path, readme, versions))[0] if f.code == "version-not-pinned"]
    assert len(found) == 2 and all("third-party" in f.message for f in found)
    saas = "SaaS, không phiên bản"
    found = [f for f in run(tree(tmp_path / "b", README.replace("| 16.4 |", f"| {saas} |"), versions_with(f"{PG_LINK}", version=saas)))[0] if f.code == "version-not-pinned"]
    assert len(found) == 2 and all("third-party" in f.message for f in found)


def test_a_technology_the_readme_does_not_list_is_strict(tmp_path):
    saas = "SaaS, không phiên bản"
    versions = matrix3(f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n") + f"| Ghost | {saas} | {CHANGELOG} | x | R |\n"
    root = tree(tmp_path, README3.format(stripe=saas, mail="3.2"), versions)
    found, _ = run(root)
    assert [(f.code, f.line) for f in found if f.code in ("version-not-pinned", "versions-row-not-in-readme")] == [("version-not-pinned", 6), ("versions-row-not-in-readme", 6)]


def test_a_readme_without_a_layer_column_is_strict_everywhere(tmp_path):
    readme = "| Công nghệ | Phiên bản |\n| --- | --- |\n| PostgreSQL | 16.4 |\n| Stripe API | SaaS, không phiên bản |\n"
    versions = matrix3(f"| Stripe API | SaaS, không phiên bản | {CHANGELOG} | x | R |\n", "")
    found, _ = run(tree(tmp_path, readme, versions))
    assert "version-not-pinned" in {f.code for f in found if f.blocking}


def test_a_technology_in_two_layers_is_third_party_only_if_every_row_is(tmp_path):
    saas = "SaaS, không phiên bản"
    readme = README3.format(stripe=saas, mail="3.2") + f"| backend | Stripe API | {saas} | TC-06 |\n"
    root = tree(tmp_path, readme, matrix3(f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n"))
    assert "version-not-pinned" in {f.code for f in run(root)[0]}


def test_layer_cell_matching_is_by_containment_and_case(tmp_path):
    saas = "SaaS, không phiên bản"
    readme = README3.format(stripe=saas, mail="3.2").replace("| third-party | Stripe API", "| **Third-Party** (thanh toán) | Stripe API")
    root = tree(tmp_path, readme, matrix3(f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n"))
    assert run(root)[0] == []
    root2 = tree(tmp_path / "b", README3.format(stripe=saas, mail="3.2").replace("| third-party | Stripe API", "| bên thứ ba | Stripe API"), matrix3(f"| Stripe API | {saas} | {CHANGELOG} | x | R |\n"))
    assert run(root2)[0] == []


def test_an_impossible_date_version_is_rejected_even_for_third_party(tmp_path):
    root = stack3(tmp_path, "2025-13-40", f"| Stripe API | 2025-13-40 | {CHANGELOG} chưa công bố | x | R |\n")
    assert {f.code for f in run(root)[0] if f.blocking} >= {"version-not-pinned"}


def test_the_extra_forms_come_from_the_data_file(tmp_path):
    saas = "SaaS, không phiên bản"
    base = yaml.safe_load(cv.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    base.update(date_versions=False)
    path = tmp_path / "v.yaml"
    path.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    no_date, _ = cv.load_config(path)
    root = stack3(tmp_path / "a", "2025-03-01", f"| Stripe API | 2025-03-01 | 2025-03-01; chưa công bố {CHANGELOG} | x | R |\n")
    assert "version-not-pinned" in {f.code for f in run(root, no_date)[0] if f.blocking}
    base.update(date_versions=True, third_party_layers=["partner"], saas_phrases=["dịch vụ đám mây"])
    path.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    custom, _ = cv.load_config(path)
    readme = README3.format(stripe="dịch vụ đám mây", mail="3.2").replace("third-party", "partner")
    root2 = tree(tmp_path / "b", readme, matrix3(f"| Stripe API | dịch vụ đám mây | {CHANGELOG} | x | R |\n"))
    assert run(root2, custom)[0] == []
    assert "version-not-pinned" in {f.code for f in run(root2)[0] if f.blocking}  # the shipped words do not know them


# --- files and tables ----------------------------------------------------------------------------------------------------------------------

def test_missing_files(tmp_path):
    assert sorted(f.code for f in run(tree(tmp_path / "a", readme=None))[0]) == ["file-missing"]
    assert sorted(f.code for f in run(tree(tmp_path / "b", versions=None))[0]) == ["file-missing"]
    root = tmp_path / "c"
    root.mkdir()
    assert sorted(f.code for f in run(root)[0]) == ["file-missing", "file-missing"]


def test_no_table_in_either_file(tmp_path):
    found, _ = run(tree(tmp_path, "# Tech stack\n\nChưa có.\n", "# Phiên bản\n\nChưa có.\n"))
    assert sorted(f.code for f in found) == ["readme-no-table", "versions-no-table"]


def test_a_table_without_the_needed_column(tmp_path):
    readme = "| Công nghệ | TC |\n| --- | --- |\n| PostgreSQL | TC-01 |\n"
    assert "readme-column-missing" in errors(tree(tmp_path / "a", readme))
    versions = "| Công nghệ | Phiên bản chốt | Tính năng |\n| --- | --- | --- |\n| PostgreSQL | 16.4 | x |\n| NestJS | 10.4 | y |\n"
    found = errors(tree(tmp_path / "b", README, versions))
    assert "versions-column-missing" in found and found.count("tech-missing-from-versions") == 2


def test_header_words_are_found_by_containment(tmp_path):
    versions = ("| Công nghệ (tên và vai trò) | Phiên bản chốt (major.minor) | Ngày phát hành, ngày hết hỗ trợ (link vòng đời) |\n| --- | --- | --- |\n"
                f"| PostgreSQL | 16.4 | 2024-09-12; 2028-11-09 {PG_LINK} |\n| NestJS | 10.4 | 2024-06-01; 2027-12-31 [n](https://a.b/c) |\n")
    assert codes(tree(tmp_path, README, versions)) == []


def test_blank_rows_are_skipped(tmp_path):
    readme = README + "|  |  |  |  |\n"
    assert codes(tree(tmp_path, readme)) == []


def test_errors_are_attributed_to_the_right_file_and_line(tmp_path):
    found, _ = run(tree(tmp_path, README.replace("16.4", "16.3")))
    assert [(f.path, f.line) for f in found] == [("02-tech-stack/README.md", 5)]
    found, _ = run(tree(tmp_path / "b", README, versions_with("")))
    assert {(f.path, f.line) for f in found if f.code == "source-link-missing"} == {("02-tech-stack/versions-features.md", 3)}


# --- the data file -------------------------------------------------------------------------------------------------------------------------

def write_config(tmp_path: Path, **override) -> Path:
    data = yaml.safe_load(cv.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data.update(override)
    path = tmp_path / "versions.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_the_shipped_data_file(tmp_path):
    data = yaml.safe_load(cv.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert "công nghệ" in data["readme_columns"]["technology"] and "phiên bản chốt" in data["versions_columns"]["version"]
    assert "latest" in data["floating_versions"] and "hết hỗ trợ" in data["eol_labels"] and "chưa công bố" in data["no_eol_phrases"]


def test_the_words_come_from_the_data_file_not_from_the_code(tmp_path):
    cfg, errs = cv.load_config(write_config(tmp_path, floating_versions=["beta"], no_eol_phrases=["vĩnh viễn"], eol_labels=["tắt lúc"],
                                            versions_columns={"technology": ["tech"], "version": ["ver"], "lifecycle": ["life"], "risk": ["rr"]}))
    assert cfg is not None and not errs
    versions = "| Tech | Ver | Life |\n| --- | --- | --- |\n| PostgreSQL | 16.4 | tắt lúc 2028-11-09 https://a.b/c |\n| NestJS | 10.4 beta | vĩnh viễn https://a.b/c |\n"
    found = run(tree(tmp_path / "t", README, versions), cfg)[0]
    assert [(f.code, f.blocking) for f in found] == [("version-not-pinned", True), ("version-mismatch", True)]  # "beta" floats, so it matches nothing


@pytest.mark.parametrize("override,expected", [
    ({"readme_columns": {"technology": []}}, "readme_columns.technology"), ({"versions_columns": "x"}, "versions_columns"), ({"floating_versions": []}, "floating_versions"),
    ({"eol_labels": [""]}, "eol_labels"), ({"no_eol_phrases": "x"}, "no_eol_phrases"), ({"eol_warning_months": -1}, "eol_warning_months"), ({"eol_warning_months": True}, "eol_warning_months"),
    ({"third_party_layers": []}, "third_party_layers"), ({"saas_phrases": [""]}, "saas_phrases"), ({"date_versions": "yes"}, "date_versions"),
    ({"readme_columns": {"technology": ["a"], "version": ["b"]}}, "readme_columns.layer"),
    ({"versions_columns": {"technology": ["a"], "version": ["b"], "lifecycle": ["c"]}}, "versions_columns.risk"),
])
def test_a_bad_data_file_is_reported(tmp_path, override, expected):
    cfg, errs = cv.load_config(write_config(tmp_path, **override))
    assert cfg is None and any(expected in e for e in errs)


def test_missing_and_broken_data_file(tmp_path):
    assert cv.load_config(tmp_path / "none.yaml")[0] is None
    broken = tmp_path / "b.yaml"
    broken.write_text("a: [unclosed\n", encoding="utf-8")
    assert cv.load_config(broken)[0] is None
    broken.write_text("- a\n", encoding="utf-8")
    assert cv.load_config(broken)[0] is None


# --- the script ----------------------------------------------------------------------------------------------------------------------------

def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def make_workspace(tmp_path: Path, versions: str = VERSIONS) -> Path:
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", README, versions)
    return workspace


def test_cli_exit_codes_and_report(tmp_path):
    workspace = make_workspace(tmp_path, versions_with("2024-09-12; 2028-11-09"))
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 1 and "source-link-missing" in result.stdout and "1 lỗi chặn" in result.stdout
    report = (workspace / "checks" / "versions-2026-10-12.md").read_text(encoding="utf-8")
    assert "versions-features.md:3" in report and "## Lỗi chặn" in report
    (workspace / "drafts" / "02-tech-stack" / "versions-features.md").write_text(VERSIONS, encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 0 and "0 lỗi chặn" in result.stdout


def test_cli_a_passed_end_of_support_blocks(tmp_path):
    workspace = make_workspace(tmp_path, versions_with(f"2020-01-01; 2026-06-01 {PG_LINK}"))
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 1 and "eol-passed" in result.stdout and "1 lỗi chặn" in result.stdout


def test_cli_a_close_end_of_support_with_an_r_link_only_warns(tmp_path):
    workspace = make_workspace(tmp_path, versions_with(f"2020-01-01; 2027-03-01 {PG_LINK}"))
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.returncode == 0 and "eol-soon" in result.stdout and "1 cảnh báo" in result.stdout
    workspace2 = make_workspace(tmp_path / "b", versions_with(f"2020-01-01; 2027-03-01 {PG_LINK}", risk=""))
    result = run_cli("--workspace", str(workspace2), "--date", "2026-10-12")
    assert result.returncode == 1 and "eol-soon-without-risk" in result.stdout


def test_cli_date_option_changes_the_warning(tmp_path):
    workspace = make_workspace(tmp_path, versions_with(f"2020-01-01; 2027-01-01 {PG_LINK}"))
    assert "eol-soon" in run_cli("--workspace", str(workspace), "--date", "2026-10-12").stdout
    assert "eol-" not in run_cli("--workspace", str(workspace), "--date", "2025-01-01").stdout
    assert "eol-passed" in run_cli("--workspace", str(workspace), "--date", "2027-06-01").stdout


def test_cli_argument_errors(tmp_path):
    workspace = make_workspace(tmp_path)
    assert run_cli("--workspace", str(workspace), "--root", str(tmp_path / "none")).returncode == 2
    result = run_cli("--workspace", str(workspace), "--config", str(tmp_path / "none.yaml"))
    assert result.returncode == 2 and "config error" in result.stderr
    assert run_cli("--workspace", str(workspace), "--date", "12/10/2026").returncode == 2


def test_cli_root_option_and_no_report_without_a_workspace(tmp_path):
    root = tree(tmp_path / "architecture", README, versions_with(""))
    result = run_cli("--workspace", str(tmp_path / "ws"), "--root", str(root))
    assert result.returncode == 1 and not (tmp_path / "ws").exists()


def test_cli_lists_at_most_25_errors(tmp_path):
    readme = "| Công nghệ | Phiên bản |\n| --- | --- |\n" + "".join(f"| T{i} | 1.{i} |\n" for i in range(40))
    workspace = tmp_path / ".agent-workspace"
    tree(workspace / "drafts", readme, VERSIONS)
    result = run_cli("--workspace", str(workspace), "--date", "2026-10-12")
    assert result.stdout.count("error: `") == 25 and "15 lỗi nữa" in result.stdout
    assert (workspace / "checks" / "versions-2026-10-12.md").read_text(encoding="utf-8").count("[tech-missing-from-versions]") == 40


def test_runs_under_uv_with_its_own_dependencies(tmp_path):
    import shutil
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv not installed")
    workspace = make_workspace(tmp_path)
    result = subprocess.run([uv, "run", "--quiet", "--no-project", str(SCRIPT), "--workspace", str(workspace), "--date", "2026-10-12"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
