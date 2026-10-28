"""Run with: uv run --with pytest pytest tools"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import docs_standard as ds  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

CORE_NAME = "xx-core"
FAMILY = "xx"
USAGE = f"# Usage\n\n{ds.TEMPLATE_HEADING}\n\n```\nBrief: <what>\n```\n"
CHILD_README = f"# xx-child\n\n{ds.CHILD_HEADING_PREFIX}{CORE_NAME}\n\nNothing extra yet.\n"
ROOT_README = "# Root\n\n| Family | Link |\n|---|---|\n| xx | [xx](families/xx/README.md) ([usage](families/xx/USAGE.md)) |\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_plugin(directory: Path, name: str) -> None:
    write(directory / ds.CLAUDE_MANIFEST, json.dumps({"name": name}))
    write(directory / ds.ANTIGRAVITY_MANIFEST, json.dumps({"name": name}))


@pytest.fixture
def repo(tmp_path) -> Path:
    """A valid repository: one family with a core and a child, one family without a core."""
    write(tmp_path / ds.ROOT_README, ROOT_README)
    family = tmp_path / ds.FAMILIES_DIR / FAMILY
    write(family / ds.README_FILE, "# xx\n")
    write(family / ds.USAGE_FILE, USAGE)
    make_plugin(family / ds.CORE_DIR, CORE_NAME)
    write(family / ds.CORE_DIR / ds.WORKFLOW_FILE, "family: xx\n")
    make_plugin(family / "xx-child", "xx-child")
    write(family / "xx-child" / ds.README_FILE, CHILD_README)
    write(tmp_path / ds.FAMILIES_DIR / "later" / ds.README_FILE, "# later, no core yet\n")
    return tmp_path


def rules(findings) -> list[ds.Rule]:
    return [finding.rule for finding in findings]


def test_a_valid_repository_has_no_findings(repo):
    assert ds.check(repo) == []


def test_a_family_without_a_core_is_not_checked(repo):
    assert not (repo / ds.FAMILIES_DIR / "later" / ds.USAGE_FILE).exists()
    assert ds.check(repo) == []


def test_missing_usage_names_the_file(repo):
    (repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE).unlink()
    findings = ds.check(repo)
    # the root README's link to the missing file is broken too
    assert rules(findings) == [ds.Rule.MISSING_USAGE, ds.Rule.BROKEN_LINK]
    assert str(findings[0]).startswith("families/xx/USAGE.md")


def test_missing_template_heading_names_the_file(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE, "# Usage\n\n## Something else\n\n```\nx\n```\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.MISSING_TEMPLATE]
    assert "families/xx/USAGE.md" in str(findings[0])


def test_template_heading_without_a_code_block_is_a_finding(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE, f"# Usage\n\n{ds.TEMPLATE_HEADING}\n\nJust prose.\n\n## Next\n\n```\nx\n```\n")
    assert rules(ds.check(repo)) == [ds.Rule.MISSING_TEMPLATE]


def test_the_template_is_not_checked_by_its_labels(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE, f"{ds.TEMPLATE_HEADING}\n\nWhy this family needs it.\n\n```\nAudience: <who>\n```\n")
    assert ds.check(repo) == []


def test_missing_child_section_names_the_readme(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / "xx-child" / ds.README_FILE, "# xx-child\n\nNo usage section.\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.MISSING_CHILD_SECTION]
    assert "families/xx/xx-child/README.md" in str(findings[0])
    assert f"{ds.CHILD_HEADING_PREFIX}{CORE_NAME}" in str(findings[0])


def test_a_child_without_a_readme_is_a_finding(repo):
    (repo / ds.FAMILIES_DIR / FAMILY / "xx-child" / ds.README_FILE).unlink()
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.MISSING_CHILD_SECTION]
    assert "families/xx/xx-child/README.md" in str(findings[0])


def test_the_child_section_must_name_the_families_core(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / "xx-child" / ds.README_FILE, f"{ds.CHILD_HEADING_PREFIX}other-core\n")
    assert rules(ds.check(repo)) == [ds.Rule.MISSING_CHILD_SECTION]


def test_the_core_itself_needs_no_child_section(repo):
    assert not (repo / ds.FAMILIES_DIR / FAMILY / ds.CORE_DIR / ds.README_FILE).exists()
    assert ds.check(repo) == []


def test_root_readme_without_the_link_names_the_file(repo):
    write(repo / ds.ROOT_README, "# Root\n\nNo links.\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.MISSING_ROOT_LINK]
    assert str(findings[0]).startswith("README.md")
    assert "families/xx/USAGE.md" in str(findings[0])


def test_root_readme_may_link_with_an_anchor(repo):
    write(repo / ds.ROOT_README, "[usage](families/xx/USAGE.md#top)\n")
    assert ds.check(repo) == []


def test_broken_link_names_the_file_and_the_target(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.README_FILE, "[gone](nowhere.md)\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.BROKEN_LINK]
    assert "families/xx/README.md" in str(findings[0]) and "nowhere.md" in str(findings[0])


def test_links_to_files_and_folders_pass_and_anchors_and_urls_are_not_checked(repo):
    write(
        repo / ds.FAMILIES_DIR / FAMILY / ds.README_FILE,
        "[a](USAGE.md#no-such-anchor) [b](xx-child) [c](https://example.com/x) [d](#local) [e](mailto:a@b.c)\n",
    )
    assert ds.check(repo) == []


def test_links_inside_code_are_ignored(repo):
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.README_FILE, "```\n[x](nowhere.md)\n```\n`[y](nowhere.md)`\n")
    assert ds.check(repo) == []


def test_only_the_files_of_the_standard_are_scanned_for_links(repo):
    write(repo / "docs" / "other.md", "[gone](nowhere.md)\n")
    write(repo / ds.FAMILIES_DIR / FAMILY / "xx-child" / "NOTES.md", "[gone](nowhere.md)\n")
    assert ds.check(repo) == []


def test_a_plugin_readme_of_a_family_without_core_is_scanned_for_links(repo):
    write(repo / ds.FAMILIES_DIR / "later" / "later-child" / ds.README_FILE, "[gone](nowhere.md)\n")
    write(repo / ds.FAMILIES_DIR / "later" / "later-child" / ds.ANTIGRAVITY_MANIFEST, "{}")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.BROKEN_LINK]
    assert "families/later/later-child/README.md" in str(findings[0])


def test_every_kind_of_gap_is_reported_together(repo):
    (repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE).unlink()
    write(repo / ds.ROOT_README, "# Root\n")
    write(repo / ds.FAMILIES_DIR / FAMILY / "xx-child" / ds.README_FILE, "# x\n")
    assert set(rules(ds.check(repo))) == {ds.Rule.MISSING_USAGE, ds.Rule.MISSING_ROOT_LINK, ds.Rule.MISSING_CHILD_SECTION}


def test_main_exit_codes(repo, capsys):
    assert ds.main(["--repo", str(repo)]) == 0
    (repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE).unlink()
    assert ds.main(["--repo", str(repo)]) == 1
    assert "families/xx/USAGE.md" in capsys.readouterr().out


def move_usage_to_core(repo: Path) -> None:
    family = repo / ds.FAMILIES_DIR / FAMILY
    write(family / ds.CORE_DIR / ds.USAGE_FILE, USAGE)
    (family / ds.USAGE_FILE).unlink()
    root = repo / ds.ROOT_README
    root.write_text(root.read_text(encoding="utf-8").replace("xx/USAGE.md", "xx/core/USAGE.md"), encoding="utf-8")


def test_a_family_is_recognised_by_a_usage_in_its_core_without_a_workflow_file(repo):
    move_usage_to_core(repo)
    (repo / ds.FAMILIES_DIR / FAMILY / ds.CORE_DIR / ds.WORKFLOW_FILE).unlink()
    assert ds.core_families(repo) == {FAMILY: CORE_NAME}
    assert ds.check(repo) == []


def test_a_usage_in_the_core_needs_the_template_section(repo):
    move_usage_to_core(repo)
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.CORE_DIR / ds.USAGE_FILE, "# Usage\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.MISSING_TEMPLATE]
    assert "families/xx/core/USAGE.md" in str(findings[0])


def test_a_usage_in_the_core_must_be_linked_from_the_root_readme_by_that_path(repo):
    move_usage_to_core(repo)
    root = repo / ds.ROOT_README
    root.write_text(root.read_text(encoding="utf-8").replace("xx/core/USAGE.md", "xx/USAGE.md"), encoding="utf-8")
    assert set(rules(ds.check(repo))) == {ds.Rule.MISSING_ROOT_LINK, ds.Rule.BROKEN_LINK}


def test_links_in_a_core_usage_are_checked(repo):
    move_usage_to_core(repo)
    write(repo / ds.FAMILIES_DIR / FAMILY / ds.CORE_DIR / ds.USAGE_FILE, USAGE + "\n[gone](nowhere.md)\n")
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.BROKEN_LINK]
    assert "families/xx/core/USAGE.md" in str(findings[0])


def test_a_family_with_both_usage_files_is_a_finding(repo):
    family = repo / ds.FAMILIES_DIR / FAMILY
    write(family / ds.CORE_DIR / ds.USAGE_FILE, USAGE)
    findings = ds.check(repo)
    assert rules(findings) == [ds.Rule.DUPLICATE_USAGE]
    assert "families/xx/USAGE.md and families/xx/core/USAGE.md" in str(findings[0])


def test_a_workflow_file_without_any_usage_is_still_missing_usage(repo):
    (repo / ds.FAMILIES_DIR / FAMILY / ds.USAGE_FILE).unlink()
    assert ds.Rule.MISSING_USAGE in rules(ds.check(repo))


def test_the_real_repository_follows_the_standard():
    assert ds.check(REPO) == []


def test_the_real_software_dev_family_is_checked():
    assert ds.core_families(REPO) == {"software-dev": "dev-core", "design-system": "design-core"}
