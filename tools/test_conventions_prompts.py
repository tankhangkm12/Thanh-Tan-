"""Run with: uv run --with pyyaml --with pytest pytest tools

Roles and skills that work to conventions must say how: where to read them and what to write back.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

CORE = Path(__file__).resolve().parents[1] / build.DEFAULT_PLUGIN
ROLES = CORE / build.ROLES_DIR


def role(name: str) -> str:
    return (ROLES / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["planner", "implementer", "reviewer"])
def test_these_roles_read_the_conventions_first(name):
    body = role(name)
    assert "`conventions` tool" in body and "thanhtan conventions" in body
    assert "enforced" in body


def test_the_planner_sets_the_kind_of_every_item():
    body = role(name := "planner")
    for needle in ("- kind:", "interface", "implement", "other", "item-order"):
        assert needle in body, (name, needle)


def test_the_planner_asks_instead_of_guessing():
    body = role("planner")
    assert "## Chưa có quy ước" in body and "### Q1 - " in body and "- ask:" in body
    assert "do not guess" in body.lower()
    assert "thanhtan decide --answer Q1" in body and "never answer" in body.lower()


def test_the_reviewer_answers_for_every_review_convention():
    body = role("reviewer")
    assert "PC-01: đạt" in body and "vi phạm PC-01 ở file:line" in body
    assert "every" in body.lower() and "check: review" in body
    assert "## Bài học đề xuất" in body and "### L1 - " in body and "a person decides" in body


def test_the_continue_skill_stops_on_unanswered_questions():
    text = (CORE / "skills" / "continue" / "SKILL.md").read_text(encoding="utf-8")
    assert "unanswered" in text and "thanhtan decide --answer" in text
    assert "conventions" in text


def test_the_planner_proposes_a_tier_and_a_layer_for_every_item():
    body = role("planner")
    for needle in ("- tier: fast", "- layer: domain", "`fast`", "`deep`", "layer-order", "`scope`", "counts as `deep`"):
        assert needle in body, needle


def test_the_continue_skill_hands_each_item_to_the_agent_plan_assign_names():
    text = (CORE / "skills" / "continue" / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("thanhtan plan assign --cli claude", "--cli antigravity", "project-", "thanhtan role grant", "implementer-fast", "implementer-deep", "no tier", "plugins add roles of their own"):
        assert needle in text, needle


def test_the_size_comes_from_the_command_and_the_planner_keeps_a_small_plan_small():
    start = (CORE / "skills" / "start" / "SKILL.md").read_text(encoding="utf-8")
    assert "--size small" in start and "at most 3 plan items" in start and "never guess a size" in start
    for command in ("start-small", "hotfix", "refactor", "chore"):
        assert f"`/dev-core:{command}`" in start, command
    small = (CORE / "skills" / "start-small" / "SKILL.md").read_text(encoding="utf-8")
    assert "`--size small`" in small and "skills/start/SKILL.md" in small
    planner = role("planner")
    assert "size: small" in planner and "at most 3 items" in planner
    continue_skill = (CORE / "skills" / "continue" / "SKILL.md").read_text(encoding="utf-8")
    assert "size: small" in continue_skill and "needs no approval" in continue_skill
