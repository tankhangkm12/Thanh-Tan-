"""Phase C (prompts, skills and documents): the replan and the spec delta are described where people and agents read.

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
MCP_PREFIX = "mcp__plugin_dev-core_thanhtan__"
DONE_HEADING = "## Mục roadmap đã hoàn thành"
PROCESS_HEADING = "## Đề xuất cải tiến quy trình"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def role(name: str) -> str:
    return read(CORE / build.ROLES_DIR / f"{name}.md")


def skill(name: str) -> str:
    return read(CORE / "skills" / name / "SKILL.md")


def section(text: str, heading: str) -> str:
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    assert found, f"no '## {heading}' section"
    return found.group(1)


def frontmatter(path: Path) -> dict:
    import yaml

    return yaml.safe_load(read(path).split("---", 2)[1])


# --------------------------------------------------------------------- scout


@pytest.mark.parametrize("needle", ["replan", "summary.md", "spec-delta.md", "replan_write", DONE_HEADING, PROCESS_HEADING])
def test_the_scout_knows_how_to_replan(needle):
    assert needle in role("scout")


def test_the_scout_reads_what_the_task_did_before_it_rewrites_a_document():
    body = role("scout")
    replan = body[body.index("replan") :]
    assert replan.index("spec-delta.md") < replan.index("project_write")


def test_the_scout_only_proposes_which_roadmap_items_are_done():
    body = role("scout").lower()
    assert "roadmap set" in body and "person" in body
    assert "never" in body and "done" in body


def test_the_scout_asks_for_nothing_to_be_applied_to_the_workflow_itself():
    assert "proposals only" in role("scout").lower()


def test_the_scout_agent_is_the_only_one_with_the_replan_tool():
    for path in sorted((CORE / "claude" / "agents").glob("*.md")):
        tools = frontmatter(path)["tools"].split(", ")
        assert (MCP_PREFIX + "replan_write" in tools) is (path.stem == "scout"), path


# -------------------------------------------------------------------- skills


def test_there_is_a_replan_skill_with_the_usual_frontmatter():
    path = CORE / "skills" / "replan" / "SKILL.md"
    assert path.is_file()
    data = frontmatter(path)
    assert data["name"] == "replan" and len(data["description"]) > 40


def test_the_replan_skill_checks_the_state_first_and_only_goes_on_when_it_is_pending():
    text = skill("replan")
    assert "thanhtan replan status" in text
    assert text.index("thanhtan replan status") < text.index("scout")
    for state in ("pending", "proposed", "task-open", "not-sealed", "done", "skipped", "no-finished-task"):
        assert state in text, state


def test_the_replan_skill_hands_the_work_to_the_scout_and_names_the_report():
    text = skill("replan")
    assert "scout" in text and "replan.md" in text and "spec-delta.md" in text


def test_the_replan_skill_leaves_confirming_and_closing_items_to_the_person():
    text = skill("replan")
    for needle in ("thanhtan project confirm", "thanhtan roadmap set", "thanhtan replan done", "thanhtan replan skip"):
        assert needle in text, needle
    assert "never run" in text.lower()


def test_the_replan_skill_stops_at_proposed_and_asks_the_person_to_read_replan_md_first():
    text = skill("replan")
    assert "proposed" in text and "replan.md" in text
    assert text.index("replan.md") < text.index("thanhtan replan done")


def test_the_replan_skill_follows_the_rules_of_every_skill():
    text = skill("replan")
    assert "single command line" in text and "Never join commands" in text
    assert "You never push" in text


def test_the_replan_skill_says_a_blocked_task_stops_it():
    text = skill("replan").lower()
    assert "blocked" in text and "open" in text


def test_the_continue_skill_suggests_the_replan_when_a_task_is_done():
    assert "replan" in skill("continue")


def test_the_status_skill_reports_the_replan_state():
    assert "thanhtan replan status" in skill("status")


def test_the_start_skill_mentions_the_replan_warning():
    text = skill("start")
    assert "replan" in text and "warn" in text.lower()


def test_the_approve_skill_points_at_the_replan_after_the_last_approval():
    assert "replan" in skill("approve")


# ----------------------------------------------------------------------- USAGE


def test_usage_has_a_section_on_the_replan():
    text = section(read(USAGE), "Replan sau mỗi task")
    for needle in ("/dev-core:replan", "spec-delta.md", "replan.md", "thanhtan replan status", "thanhtan replan skip", "thanhtan replan done", "proposed", "thanhtan roadmap set", DONE_HEADING.removeprefix("## ")):
        assert needle in text, needle


def test_usage_lists_the_replan_commands_of_a_person_among_the_persons_commands():
    text = section(read(USAGE), "Lệnh của người")
    assert "thanhtan replan skip" in text and "thanhtan replan done" in text


def test_usage_explains_the_replan_warning_and_the_blocked_task_limit():
    text = section(read(USAGE), "Xử lý tình huống").lower()
    assert "replan" in text and "blocked" in text and "cảnh báo" in text


def test_usage_says_the_antigravity_way_to_run_the_replan():
    text = section(read(USAGE), "Replan sau mỗi task")
    assert "Antigravity" in text and "skill" in text


def test_the_work_cycle_in_usage_ends_with_the_replan():
    assert re.search(r"review\s*→\s*replan|review\s*->\s*replan|review.{0,40}replan", read(USAGE), flags=re.S)


# --------------------------------------------------------------- the rest


def test_the_architecture_document_describes_the_new_files_commands_and_tool():
    text = read(ARCHITECTURE)
    for needle in ("spec-delta.md", "replan.md", "replanned_at", "proposed", "thanhtan replan status", "thanhtan replan write", "thanhtan replan done", "thanhtan replan skip", "replan_write"):
        assert needle in text, needle


def test_the_architecture_document_maps_the_flow_to_openspec_without_depending_on_it():
    text = read(ARCHITECTURE)
    assert "https://github.com/Fission-AI/OpenSpec" in text
    openspec = text[text.index("OpenSpec") - 600 : text.index("OpenSpec") + 1500]
    for needle in ("propose", "apply", "archive", "spec-delta.md", "project confirm"):
        assert needle in openspec, needle
    assert "not a dependency" in text.lower()


def test_the_architecture_document_lists_the_replan_commands_among_the_persons_commands():
    lines = [line for line in read(ARCHITECTURE).splitlines() if "knowledge init" in line and "task seal" in line]
    assert lines and all("replan skip" in line and "replan done" in line for line in lines)


def test_the_readme_mentions_the_replan():
    assert "replan" in read(README).lower()


def test_the_changelog_announces_the_replan_and_the_spec_delta_under_unreleased():
    unreleased = read(CHANGELOG).split("## [Unreleased]", 1)[1].lower()
    for needle in ("replan", "spec-delta", "replan_write", "replan skip", "replan done"):
        assert needle in unreleased, needle
