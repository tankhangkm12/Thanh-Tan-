"""Phase A1: the Claude Code `deep` tier is Sonnet at high effort, and every document says so.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "families" / "software-dev" / "core"
BACKEND = REPO / "families" / "software-dev" / "backend"
README = REPO / "README.md"
USAGE = REPO / "families" / "software-dev" / "USAGE.md"
CORE_README = CORE / "README.md"
BACKEND_README = BACKEND / "README.md"
CONTINUE_SKILL = CORE / "skills" / "continue" / "SKILL.md"
CHANGELOG = REPO / "CHANGELOG.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(read(path).split("---")[1])


def role_source(path: Path) -> dict:
    return frontmatter(path)


# ------------------------------------------------------------ generated agents


def test_claude_deep_implementer_is_sonnet_at_high_effort():
    agent = frontmatter(CORE / "claude" / "agents" / "implementer-deep.md")
    assert (agent["model"], agent["effort"]) == ("sonnet", "high")


def test_claude_fast_implementer_stays_sonnet_at_low_effort():
    """Regression: already green before the change; it must stay so."""
    agent = frontmatter(CORE / "claude" / "agents" / "implementer-fast.md")
    assert (agent["model"], agent["effort"]) == ("sonnet", "low")


def test_antigravity_implementer_tiers_do_not_change():
    """Regression: already green before the change; it must stay so."""
    fast = frontmatter(CORE / "agents" / "implementer-fast.md")
    deep = frontmatter(CORE / "agents" / "implementer-deep.md")
    assert (fast["model"], deep["model"]) == ("flash", "pro")
    assert "effort" not in fast and "effort" not in deep


def test_the_implementer_role_source_declares_the_same_tiers():
    variants = role_source(CORE / "src" / "roles" / "implementer.md")["variants"]
    assert variants["deep"]["claude"] == {"model": "sonnet", "effort": "high"}
    assert variants["fast"]["claude"] == {"model": "sonnet", "effort": "low"}
    assert variants["deep"]["antigravity"] == {"model": "pro"}


def test_claude_db_engineer_is_sonnet_at_high_effort_and_antigravity_keeps_pro():
    agent = frontmatter(BACKEND / "claude" / "agents" / "db-engineer.md")
    assert (agent["model"], agent["effort"]) == ("sonnet", "high")
    assert frontmatter(BACKEND / "agents" / "db-engineer.md")["model"] == "pro"
    assert role_source(BACKEND / "src" / "roles" / "db-engineer.md")["settings"]["claude"] == {"model": "sonnet", "effort": "high"}


def test_both_plugins_still_build_cleanly_after_the_change():
    """Regression: generated agents stay in step with their sources."""
    assert build.check(CORE) == []
    assert build.check(BACKEND) == []


# --------------------------------------------------------- the tier tables


def tier_table(text: str) -> dict[str, tuple[dict, dict]]:
    """Rows of the first table whose header is `| | fast | deep |`: label -> (fast settings, deep settings)."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells == ["", "fast", "deep"]:
            rows = {}
            for row in lines[number + 2 :]:
                if not row.strip().startswith("|"):
                    break
                parts = [c.strip() for c in row.strip().strip("|").split("|")]
                rows[parts[0]] = tuple(dict(re.findall(r"`(model|effort): (\w+)`", cell)) for cell in parts[1:3])
            return rows
    raise AssertionError("no `| | fast | deep |` table found")


def expected_table() -> dict[str, tuple[dict, dict]]:
    variants = role_source(CORE / "src" / "roles" / "implementer.md")["variants"]
    claude = tuple({k: v for k, v in variants[tier]["claude"].items()} for tier in ("fast", "deep"))
    agy = tuple({"model": variants[tier]["antigravity"]["model"]} for tier in ("fast", "deep"))
    return {"Claude Code": claude, "Antigravity": agy}


@pytest.mark.parametrize("document", [README, USAGE], ids=["README.md", "USAGE.md"])
def test_the_tier_table_matches_the_implementer_role_source(document):
    """Regression: green today (docs and source agree on Opus); it keeps the two in step through the change."""
    assert tier_table(read(document)) == expected_table()


def fenced_blocks(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)


def test_the_variants_example_in_the_core_readme_matches_the_role_source():
    """Regression: green today; it keeps the README example in step with the source through the change."""
    blocks = [b for b in fenced_blocks(read(CORE_README)) if b.lstrip().startswith("variants:")]
    assert blocks, "the core README shows no `variants:` example"
    assert yaml.safe_load(blocks[0])["variants"] == role_source(CORE / "src" / "roles" / "implementer.md")["variants"]


# ---------------------------------------------- statements about the defaults
# Only sentences that state what a role or tier uses BY DEFAULT are checked. Advice such as "to use Opus,
# change `deep` to ..." is allowed to name Opus.

DEEP_DEFAULT_IS_OPUS = re.compile(r"`deep`\s*(?:dùng|uses|is|là|chạy)\s+(?:Opus|`opus`)", re.I)
DB_ENGINEER_DEFAULT_IS_OPUS = re.compile(r"db-engineer`?[^|.\n]{0,80}(?:dùng|uses|is|là|chạy)\s+(?:Opus|`opus`)", re.I)


@pytest.mark.parametrize("document", [README, USAGE, CORE_README, CONTINUE_SKILL], ids=lambda p: p.relative_to(REPO).as_posix())
def test_no_document_states_that_the_deep_tier_uses_opus_by_default(document):
    """Documents without such a claim today (the continue skill) are regression guards; the rest are red until fixed."""
    assert DEEP_DEFAULT_IS_OPUS.findall(read(document)) == []


@pytest.mark.parametrize("document", [README, USAGE, BACKEND_README], ids=lambda p: p.relative_to(REPO).as_posix())
def test_no_document_states_that_db_engineer_uses_opus_by_default(document):
    """The backend README case is a regression guard (its claim is caught by the Model-row test below)."""
    assert DB_ENGINEER_DEFAULT_IS_OPUS.findall(read(document)) == []


def test_advice_on_how_to_use_opus_is_still_allowed_by_these_checks():
    """Regression guard for the checks above: a how-to sentence is not a default claim."""
    advice = "Muốn dùng Opus thì đổi `deep` của Claude Code thành `{model: opus, effort: medium}` rồi chạy build."
    assert not DEEP_DEFAULT_IS_OPUS.search(advice) and not DB_ENGINEER_DEFAULT_IS_OPUS.search(advice)
    assert DEEP_DEFAULT_IS_OPUS.search("`deep` dùng Opus nên tốn giới hạn hơn.")
    assert DB_ENGINEER_DEFAULT_IS_OPUS.search("Role `db-engineer` cũng dùng Opus.")


def test_the_backend_readme_states_the_db_engineer_settings_that_the_role_source_has():
    row = [line for line in read(BACKEND_README).splitlines() if line.startswith("| Model |")]
    assert row, "the backend README has no model row for db-engineer"
    assert "sonnet" in row[0] and "high" in row[0]
    assert "mạnh nhất" not in row[0]


def test_the_continue_skill_gives_each_implementer_agent_its_real_effort():
    text = read(CONTINUE_SKILL)
    variants = role_source(CORE / "src" / "roles" / "implementer.md")["variants"]
    for tier in ("fast", "deep"):
        found = re.search(rf"`implementer-{tier}`\s*\(([^)]*)\)", text)
        assert found, f"the continue skill does not describe implementer-{tier}"
        assert f"{variants[tier]['claude']['effort']} effort" in found.group(1)
        assert "strongest" not in found.group(1)


def test_the_changelog_records_the_tier_change_under_unreleased():
    """Checks that the entry exists and carries the values; the wording is free."""
    text = read(CHANGELOG)
    unreleased = text.split("## [Unreleased]", 1)[1]
    changed = unreleased.split("### Changed", 1)[1]
    assert "implementer-deep" in changed and "sonnet" in changed.lower() and "high" in changed
    assert "db-engineer" in changed
