"""Run with: uv run --with pyyaml --with pytest pytest tools

The scout role and the setup skill of dev-core: what they must say, and what they must not allow.
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

CORE = Path(__file__).resolve().parents[1] / build.DEFAULT_PLUGIN
SCOUT = CORE / build.ROLES_DIR / "scout.md"
SETUP = CORE / "skills" / "setup" / "SKILL.md"
SECTIONS = ("profile", "architecture", "sources", "conventions")
COMMANDS_THAT_ARE_A_PERSONS = ("agentflow project confirm", "agentflow decide")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scout_may_write_project_documents_and_nothing_else():
    roles = {role.name: role for role in build.load_roles(CORE)}
    scout = roles["scout"]
    assert set(scout.capabilities) == {build.Capability.READ, build.Capability.RUN, build.Capability.WORKSPACE, build.Capability.PROJECT}
    claude = (CORE / "claude" / "agents" / "scout.md").read_text(encoding="utf-8")
    tools = yaml.safe_load(claude.split("---")[1])["tools"]
    assert build.MCP_SERVER_PREFIX + "project_write" in tools and "Edit" not in tools and "Write" not in tools.split(", ")
    antigravity = yaml.safe_load((CORE / "agents" / "scout.md").read_text(encoding="utf-8").split("---")[1])["tools"]
    assert not set(antigravity) & build.ANTIGRAVITY_EDIT_TOOLS


def test_scout_is_a_read_only_role_for_the_builder_checks():
    assert "scout" in build.READ_ONLY_ROLES


@pytest.mark.parametrize(
    "needle",
    [
        "project_write",
        "unconfirmed",
        "## Câu hỏi mở",
        "Do not choose",
        "never confirm",
        "file:line",
        "knowledge/semgrep",
        "agentflow config get",
    ],
)
def test_the_scout_prompt_covers(needle):
    assert needle.lower() in text(SCOUT).lower()


def test_the_scout_names_every_section_and_the_convention_format():
    body = text(SCOUT)
    for section in SECTIONS:
        assert f"`{section}`" in body
    assert "### PC-01 - " in body and "- check:" in body and "- source:" in body and "- description:" in body


def test_the_setup_skill_asks_for_the_paths_and_does_not_look_for_them():
    skill = text(SETUP)
    data = yaml.safe_load(skill.split("---")[1])
    assert set(data) == {"name", "description"} and data["name"] == "setup"
    assert re.search(r"ask the person", skill, re.I) and "do not look for documents yourself" in skill.lower()
    assert "never search" in skill.lower() or "do not search" in skill.lower()
    assert len(skill.splitlines()) < 500


def test_the_setup_skill_runs_the_scout_and_leaves_confirming_to_the_person():
    skill = text(SETUP)
    assert "scout" in skill and "`status`" in skill
    for section in SECTIONS:
        assert section in skill
    assert "agentflow project confirm" in skill and "you never run" in skill.lower()
    assert "no task is open" in skill.lower() or "no open task" in skill.lower()


@pytest.mark.parametrize("path", [SCOUT, SETUP], ids=lambda p: p.parent.name + "/" + p.name)
def test_they_do_not_let_an_agent_push_merge_or_confirm(path):
    body = text(path).lower()
    assert "never push" in body or "you never push" in body
    assert "merge" in body and "pull request" in body
