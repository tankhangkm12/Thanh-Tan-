"""Phase B (prompts, skills and documents): mission and roadmap are described where people and agents read about them.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / build.DEFAULT_PLUGIN
USAGE = REPO / "families" / "software-dev" / "USAGE.md"
ARCHITECTURE = REPO / "docs" / "architecture.md"
README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def role(name: str) -> str:
    return read(CORE / build.ROLES_DIR / f"{name}.md")


def skill(name: str) -> str:
    return read(CORE / "skills" / name / "SKILL.md")


def section(text: str, heading: str) -> str:
    """The body of a `## heading` section up to the next `## `."""
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    assert found, f"no '## {heading}' section"
    return found.group(1)


# --------------------------------------------------------------------- scout


@pytest.mark.parametrize("needle", ["## Mission", "- why:", "- for:", "- scope:", "- out-of-scope:", "chưa có tài liệu"])
def test_the_scout_writes_the_mission_in_the_agreed_form(needle):
    assert needle in role("scout")


def test_the_scout_gives_a_source_for_the_mission_not_only_for_conventions():
    body = role("scout")
    assert "## Mission" in body and "- source:" in body.split("## Mission", 1)[1]


def test_the_scout_takes_the_mission_from_the_documents_it_was_given_and_never_from_code():
    body = role("scout")
    assert "infer the mission" in body and "documents" in body
    assert "S1" in body  # an open question instead of a guess


@pytest.mark.parametrize("needle", ["roadmap", "### R1 - ", "- goal:", "`todo`", "TODO"])
def test_the_scout_proposes_a_roadmap_in_the_agreed_form(needle):
    assert needle in role("scout")


def test_the_scout_gives_roadmap_items_a_docs_line():
    body = role("scout")
    assert "### R1 - " in body and "- docs:" in body.split("### R1 - ", 1)[1]


def test_the_scout_is_told_that_it_confirms_nothing_and_cannot_change_a_status():
    body = role("scout").lower()
    assert "mission" in body and "roadmap" in body
    assert "agentflow project confirm" in body and "never confirm" in body
    assert "status" in body and "person" in body


# -------------------------------------------------------------------- skills


def test_the_setup_skill_asks_for_the_mission_and_roadmap_documents_and_tells_the_person_what_to_confirm():
    text = skill("setup")
    assert "mission" in text and "roadmap" in text
    assert "agentflow project confirm mission" in text and "R1" in text
    assert "agentflow project status" in text


def test_the_start_skill_ties_the_task_to_a_roadmap_item():
    text = skill("start")
    assert "--roadmap" in text and "agentflow roadmap list" in text
    assert "warn" in text.lower()


def test_the_status_skill_mentions_the_roadmap_suggestion():
    assert "roadmap" in skill("status")


# ----------------------------------------------------------------------- USAGE


def test_usage_tells_a_new_project_to_set_up_the_mission_and_the_roadmap():
    text = section(read(USAGE), "Chuẩn bị một lần cho mỗi dự án")
    for needle in ("Mission", "roadmap.md", "agentflow project confirm mission", "agentflow project status", "agentflow project confirm R1"):
        assert needle in text, needle


def test_the_task_template_has_a_roadmap_line():
    block = re.search(r"```\n(Loại:.*?)```", section(read(USAGE), "Khuôn yêu cầu task"), flags=re.S)
    assert block, "the template block was not found"
    assert re.search(r"^Roadmap: ", block.group(1), flags=re.M)


def test_usage_lists_the_new_commands_a_person_runs():
    text = section(read(USAGE), "Lệnh của người")
    for needle in ("agentflow roadmap set", "agentflow project confirm mission"):
        assert needle in text, needle


def test_usage_explains_that_an_item_is_never_closed_by_finishing_a_task():
    lines = [line for line in read(USAGE).splitlines() if "roadmap" in line.lower() and "done" in line]
    assert any("không tự" in line for line in lines), "USAGE does not say that an item does not become done by itself"


def test_usage_explains_unconfirmed_mission_and_roadmap_in_the_situations_section():
    text = section(read(USAGE), "Xử lý tình huống").lower()
    assert "mission" in text and "roadmap" in text


# --------------------------------------------------------------- the rest


def test_the_architecture_document_describes_the_new_files_and_commands():
    text = read(ARCHITECTURE)
    for needle in ("roadmap.md", "confirmations.json", "agentflow roadmap list", "agentflow roadmap set", "agentflow project status", "history/", "removed:"):
        assert needle in text, needle


def test_the_architecture_document_lists_the_roadmap_command_among_the_persons_commands():
    lines = [line for line in read(ARCHITECTURE).splitlines() if "knowledge init" in line and "task seal" in line]
    assert lines and all("roadmap set" in line for line in lines)


def test_usage_tells_the_person_what_a_warning_at_task_new_means_and_what_removed_means():
    text = read(USAGE).lower()
    assert "removed:" in text and "task new" in text and "cảnh báo" in text


def test_the_readme_shows_the_roadmap_option_in_the_usage_steps():
    assert "--roadmap" in read(README)


def test_the_changelog_announces_the_mission_and_the_roadmap_under_unreleased():
    unreleased = read(CHANGELOG).split("## [Unreleased]", 1)[1].split("\n## ", 1)[0]
    assert "mission" in unreleased.lower() and "roadmap" in unreleased.lower() and "--roadmap" in unreleased
