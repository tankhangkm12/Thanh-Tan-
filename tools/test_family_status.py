"""Phase A2: the design-system README says what the family really is, and agrees with PLAN.md and the root README.

Both the family README and its PLAN.md carry one machine-readable line, `**Trạng thái:** Giai đoạn N xong; …`,
so the two cannot drift apart unnoticed.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FAMILY = REPO / "families" / "design-system"
FAMILY_README = FAMILY / "README.md"
PLAN = FAMILY / "PLAN.md"
ROOT_README = REPO / "README.md"

STATUS_LINE = re.compile(r"^\*\*Trạng thái:\*\*\s*(.+)$", re.M)
STAGE = re.compile(r"Giai đoạn (\d+) xong")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def status_of(path: Path) -> str:
    found = STATUS_LINE.search(read(path))
    assert found, f"{path.name} has no `**Trạng thái:** …` line"
    return found.group(1)


def stage_of(path: Path) -> int:
    found = STAGE.search(status_of(path))
    assert found, f"the status line of {path.name} names no `Giai đoạn N xong`"
    return int(found.group(1))


def test_the_family_readme_no_longer_claims_to_be_a_skeleton():
    text = read(FAMILY_README)
    assert "Bản nháp (khung)" not in text
    assert "chưa có workflow, agent hay script" not in text


def test_the_family_readme_and_the_plan_name_the_same_finished_stage():
    assert stage_of(FAMILY_README) == stage_of(PLAN) == 6


def test_the_plan_does_not_keep_an_older_build_state_paragraph():
    found = re.search(r"Trạng thái dựng \(Giai đoạn (\d+)", read(PLAN))
    assert found is None or int(found.group(1)) == stage_of(PLAN)


def test_neither_status_line_says_the_work_is_unpushed_when_it_is_merged_into_develop():
    assert "chưa push" not in status_of(FAMILY_README)
    assert "chưa push" not in status_of(PLAN)


def test_what_the_readme_says_exists_does_exist():
    assert stage_of(FAMILY_README) >= 3
    core = FAMILY / "core"
    for name in ("USAGE.md", "plugin.json", "scripts", "agents", "hooks", "workflow"):
        assert (core / name).exists(), f"the README claims stage {stage_of(FAMILY_README)} but core/{name} is missing"
    assert any((core / "scripts").glob("*.py"))


def test_the_family_readme_reports_a_real_project_trial_of_g0_to_g2_and_no_further():
    """Values only: the trial ranges named in the status line, not its wording."""
    status = status_of(FAMILY_README)
    ranges = re.findall(r"G(\d+)–G(\d+)", status)
    assert ranges, "the status line names no trial range such as G0–G2"
    assert (min(int(a) for a, _ in ranges), max(int(b) for _, b in ranges)) == (0, 2)


def test_the_root_readme_agrees_with_the_family_readme_about_the_trial_runs():
    row = [line for line in read(ROOT_README).splitlines() if line.startswith("| [design-system]")]
    assert row, "the root README has no design-system row"
    assert "G0–G2" in row[0] and "G0–G2" in status_of(FAMILY_README)


@pytest.mark.parametrize("name", ["PLAN.md", "core/USAGE.md"])
def test_the_family_readme_links_to_the_documents_that_are_in_git(name):
    """The PLAN.md case is a regression guard (green today); core/USAGE.md is the new link."""
    assert f"]({name})" in read(FAMILY_README)


def test_the_family_readme_does_not_link_to_the_local_only_build_notes():
    """Regression: green today; BUILD-PROGRESS.md is git-ignored, so no tracked document may point at it."""
    assert "BUILD-PROGRESS" not in read(FAMILY_README)
