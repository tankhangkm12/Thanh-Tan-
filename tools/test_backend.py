"""Run with: uv run --with pyyaml --with pytest pytest tools

Checks on the dev-backend plugin that do not need thanhtan itself (the extension contract is checked by
foundation/tests/test_backend_extension.py).
"""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / build.DEFAULT_PLUGIN
BACKEND = REPO / "families" / "software-dev" / "backend"
SKILLS = {"api-implementation", "business-logic", "db-migration", "query-review", "backend-testing", "contract-test"}
# Frameworks, ORMs, migration tools, languages and test runners: the skills must stay stack-agnostic.
STACK_WORDS = re.compile(
    r"\b(django|flask|fastapi|spring|express|rails|laravel|nestjs|sqlalchemy|hibernate|prisma|typeorm|sequelize|alembic|"
    r"flyway|liquibase|knex|gorm|pytest|jest|junit|mocha|python|java|javascript|typescript|golang|ruby|php|rust|kotlin|"
    r"npm|pip|maven|gradle)\b",
    re.I,
)
PROMPTS = sorted([*BACKEND.glob("skills/*/SKILL.md"), *(BACKEND / build.ROLES_DIR).glob("*.md")])


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def test_backend_has_the_db_engineer_role_and_its_six_skills():
    roles = {role.name: role for role in build.load_roles(BACKEND)}
    assert set(roles) == {"db-engineer"} and build.Capability.EDIT in roles["db-engineer"].capabilities
    skills = {path.parent.name: path for path in (BACKEND / "skills").glob("*/SKILL.md")}
    assert set(skills) == SKILLS
    for name, path in skills.items():
        data = frontmatter(path)
        assert set(data) == {"name", "description"} and data["name"] == name
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500


def test_generated_agents_are_up_to_date_and_declared_in_the_manifest():
    assert build.check(BACKEND) == []
    manifest = json.loads((BACKEND / build.CLAUDE_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["agents"] == ["./claude/agents/db-engineer.md"]
    assert manifest["dependencies"] == ["dev-core"] and manifest["version"] == "1.0.0"
    antigravity = json.loads((BACKEND / "plugin.json").read_text(encoding="utf-8"))
    assert antigravity["name"] == "dev-backend" and antigravity["version"] == manifest["version"]


@pytest.mark.parametrize("path", PROMPTS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_prompts_do_not_assume_a_stack(path):
    match = STACK_WORDS.search(path.read_text(encoding="utf-8"))
    assert match is None, match.group(0)


def test_the_migration_skill_reads_the_commands_from_the_project_settings():
    text = (BACKEND / "skills" / "db-migration" / "SKILL.md").read_text(encoding="utf-8")
    assert "thanhtan config get backend.migrate_up_command" in text
    assert "thanhtan config get backend.migrate_down_command" in text


def test_dev_core_knows_nothing_about_db_engineer():
    for path in [*(CORE / build.ROLES_DIR).glob("*.md"), *(CORE / "skills").glob("*/SKILL.md")]:
        assert "db-engineer" not in path.read_text(encoding="utf-8"), path
