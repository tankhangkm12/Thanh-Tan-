"""The real dev-backend extension.yaml, registered in a throw-away workspace."""

from pathlib import Path

import pytest
from conftest import git

from agentflow import cli
from agentflow.cli import main
from agentflow.constants import ExitCode, GateKind, NetworkMode, ResultKind
from agentflow.extension import load_extension_file

REPO = Path(__file__).resolve().parents[2]
EXTENSION = REPO / "families" / "software-dev" / "backend" / "extension.yaml"
WORKFLOW = REPO / "families" / "software-dev" / "core" / "workflow.yaml"

SETTINGS = {
    "db.engine": "postgresql",
    "migrations_dir": "db/migrations",
    "migrations_lint_glob": "db/migrations/*.up.sql",
    "migrate_up_command": "docker compose exec -T db psql -f /m/up.sql",
    "migrate_down_command": "docker compose exec -T db psql -f /m/down.sql",
    "test_command": "make test",
    "openapi.spec": "openapi.yaml",
    "openapi.url": "http://localhost:8000",
}


def test_the_extension_is_valid_and_pins_its_images():
    extension = load_extension_file(EXTENSION)
    assert extension.name == "dev-backend" and extension.role_ids == ("db-engineer",)
    squawk, schemathesis = extension.scan_tools
    assert squawk.image == "ghcr.io/sbdchd/squawk:2.68.0" and squawk.network is NetworkMode.NONE
    assert squawk.result.kind is ResultKind.JSON_FINDINGS and squawk.when.config_equals == ("backend.db.engine", "postgresql")
    assert schemathesis.image == "schemathesis/schemathesis:4.30.1" and schemathesis.network is NetworkMode.HOST_GATEWAY
    assert schemathesis.result.kind is ResultKind.EXIT_CODE and schemathesis.result.fail_exit_codes == (1,)
    assert extension.gates == (("test", GateKind.SCANS_CLEAN),)


@pytest.fixture
def ws(gitflow_repo, monkeypatch, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(WORKFLOW)]) == ExitCode.OK
    assert main(["ext", "add", str(EXTENSION)]) == ExitCode.OK
    for key, value in SETTINGS.items():
        assert main(["config", "set", f"backend.{key}", value]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


PLAN = """### C1 - Add the items table
- role: {migration_role}
- files: db/migrations/0001_items.up.sql, db/migrations/0001_items.down.sql
- done-when: `{up}` then `{down}` then `{up}` again
- docs: https://www.postgresql.org/docs/current/sql-createtable.html

### C2 - List endpoint
- role: implementer
- files: app/items.py
- done-when: `make test`
- docs: không có — internal endpoint
"""


def check(tmp_path, migration_role="db-engineer", down=SETTINGS["migrate_down_command"]):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN.format(migration_role=migration_role, up=SETTINGS["migrate_up_command"], down=down), encoding="utf-8")
    return main(["plan", "check", "--file", str(plan)])


def test_config_check_passes_with_the_documented_settings(ws, capsys):
    assert main(["config", "check"]) == ExitCode.OK


def test_a_migration_item_for_db_engineer_with_up_and_down_passes(ws, tmp_path, capsys):
    assert check(tmp_path) == ExitCode.OK


def test_an_implementer_cannot_own_a_migration_item(ws, tmp_path, capsys):
    assert check(tmp_path, migration_role="implementer") == ExitCode.PLAN_INVALID
    assert "only db-engineer may" in capsys.readouterr().out


def test_a_migration_without_the_down_command_is_refused(ws, tmp_path, capsys):
    assert check(tmp_path, down="we will roll back by hand") == ExitCode.PLAN_INVALID
    assert f"done-when must contain `{SETTINGS['migrate_down_command']}`" in capsys.readouterr().out


def test_an_unknown_role_is_refused(ws, tmp_path):
    assert check(tmp_path, migration_role="dba") == ExitCode.PLAN_INVALID


def test_the_extension_adds_tools_to_the_test_step(ws, capsys):
    from agentflow.projectcontext import load_project_context
    from agentflow.scan import tools_for_step
    from agentflow.workspace import find_workspace, load_workspace_workflow

    paths = find_workspace(Path.cwd())
    workflow, project = load_workspace_workflow(paths), None
    project = load_project_context(paths.dir, workflow)
    assert [tool.id for tool in tools_for_step("test", workflow, project)] == ["squawk", "schemathesis"]
    assert [tool.id for tool in tools_for_step("security", workflow, project)] == ["semgrep", "trivy", "gitleaks"]
    assert ("test", GateKind.SCANS_CLEAN) in project.extra_gates
