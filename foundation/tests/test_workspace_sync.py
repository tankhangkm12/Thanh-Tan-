"""``thanhtan workspace remote|save|load|status``: the workspace travels between machines through the person's private repo.

Two machines are two home folders (``THANHTAN_HOME``) and two clones of the project; the private repository and the
company repository are bare repositories in the test folder.
"""

from pathlib import Path

import pytest
from checklist_helpers import checklist_workflow
from conftest import git
from sdd_helpers import init_workspace, say

from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.workspace import WorkspacePaths, load_config
from thanhtan.workspacesync import MARKER_FILE, SAVE_FILE, load, project_name, save, set_remote, status

AT = "2026-10-29T10:00:00+07:00"


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    for key, value in {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid"}.items():
        monkeypatch.setenv(key, value)


def bare(path: Path) -> str:
    path.mkdir(parents=True)
    git(path, "init", "-q", "--bare", "-b", "main")
    return str(path)


@pytest.fixture
def world(gitflow_repo, tmp_path, monkeypatch, capsys):
    """Machine A: the project with a workspace, a task branch and an approval tag; the company remote; the private repo."""
    company = bare(tmp_path / "company.git")
    private = bare(tmp_path / "private.git")
    git(gitflow_repo, "remote", "add", "origin", company)
    git(gitflow_repo, "push", "-q", "origin", "main", "develop")
    workflow = checklist_workflow(tmp_path)
    init_workspace(gitflow_repo, workflow, monkeypatch, capsys)
    assert say(monkeypatch, "task", "new", "Orders") == ExitCode.OK
    (gitflow_repo / "orders.txt").write_text("orders\n", encoding="utf-8")
    git(gitflow_repo, "add", "orders.txt")
    git(gitflow_repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "C1: orders")
    branch = git(gitflow_repo, "branch", "--show-current")
    git(gitflow_repo, "tag", "-a", "thanhtan/T-000/approved", "-m", "approved", "develop")
    capsys.readouterr()
    return {"a": gitflow_repo, "company": company, "private": private, "branch": branch, "workflow": workflow, "tmp": tmp_path}


def home(world, machine: str) -> dict[str, str]:
    return {"THANHTAN_HOME": str(world["tmp"] / f"home-{machine}")}


def machine_b(world) -> Path:
    clone = world["tmp"] / "machine-b" / "project"
    clone.parent.mkdir()
    git(clone.parent, "clone", "-q", world["company"], str(clone))
    git(clone, "switch", "-q", "develop")
    return clone


def save_a(world, **kwargs):
    paths = WorkspacePaths(world["a"])
    return save(paths, [world["branch"]], at=AT, machine="A", environ=home(world, "a"), **kwargs)


def test_project_names_come_from_origin(tmp_path):
    repo = tmp_path / "inventory-service"
    repo.mkdir()
    git(repo, "init", "-q")
    assert project_name(repo) == "inventory-service"
    git(repo, "remote", "add", "origin", "git@github.com:ecommerce-taca/inventory-service.git")
    assert project_name(repo) == "ecommerce-taca/inventory-service"
    git(repo, "remote", "set-url", "origin", "https://github.com/ecommerce-taca/inventory-service")
    assert project_name(repo) == "ecommerce-taca/inventory-service"
    assert project_name(repo, "mine/inv") == "mine/inv"
    for bad in ("../x", "a/../b", "a b", ""):
        if bad:
            with pytest.raises(ThanhTanError):
                project_name(repo, bad)


def test_save_needs_a_store_first(world):
    with pytest.raises(ThanhTanError) as refused:
        save_a(world)
    assert refused.value.code == ExitCode.WORKSPACE_SYNC and "workspace remote" in str(refused.value)


def test_a_workspace_moves_to_another_machine_with_its_branches_and_tags(world):
    set_remote(world["private"], home(world, "a"))
    report = save_a(world)
    assert "saved" in report.lines[0]
    b = machine_b(world)
    assert git(b, "branch", "--list", world["branch"]) == ""
    set_remote(world["private"], home(world, "b"))
    report = load(b, workflow=world["workflow"], at=AT, machine="B", environ=home(world, "b"))
    assert (b / ".ThanhTan" / "state.json").is_file()
    assert not (b / ".ThanhTan" / SAVE_FILE).exists() and (b / ".ThanhTan" / MARKER_FILE).is_file()
    assert git(b, "rev-parse", world["branch"]) == git(world["a"], "rev-parse", world["branch"])
    assert git(b, "tag", "--list", "thanhtan/*") == "thanhtan/T-000/approved"
    assert any("restored" in line for line in report.lines)
    assert load_config(WorkspacePaths(b)).workflow.source_path == str(world["workflow"].resolve())
    assert ".ThanhTan/" in (b / ".git" / "info" / "exclude").read_text(encoding="utf-8")


def test_load_refuses_to_drop_work_that_was_never_saved(world):
    set_remote(world["private"], home(world, "a"))
    save_a(world)
    b = machine_b(world)
    set_remote(world["private"], home(world, "b"))
    load(b, workflow=world["workflow"], at=AT, machine="B", environ=home(world, "b"))
    (b / ".ThanhTan" / "decisions" / "note.md").write_text("new\n", encoding="utf-8")
    with pytest.raises(ThanhTanError) as refused:
        load(b, at=AT, machine="B", environ=home(world, "b"))
    assert "never saved" in str(refused.value)
    assert "changed since" in status(b, environ=home(world, "b"))[-1]
    load(b, force=True, at=AT, machine="B", environ=home(world, "b"))
    assert not (b / ".ThanhTan" / "decisions" / "note.md").exists()


def test_save_refuses_when_another_machine_saved_since(world):
    set_remote(world["private"], home(world, "a"))
    save_a(world)
    b = machine_b(world)
    set_remote(world["private"], home(world, "b"))
    load(b, workflow=world["workflow"], at=AT, machine="B", environ=home(world, "b"))
    (b / ".ThanhTan" / "decisions" / "from-b.md").write_text("b\n", encoding="utf-8")
    save(WorkspacePaths(b), [], at=AT, machine="B", environ=home(world, "b"))
    with pytest.raises(ThanhTanError) as refused:
        save_a(world)
    assert "saved from B" in str(refused.value) and "workspace load" in str(refused.value)
    load(world["a"], at=AT, machine="A", environ=home(world, "a"))  # A was unchanged since its save, so it may load
    assert (world["a"] / ".ThanhTan" / "decisions" / "from-b.md").is_file()
    save_a(world)


def test_a_workspace_that_was_never_saved_is_not_replaced(world):
    set_remote(world["private"], home(world, "a"))
    save_a(world)
    b = machine_b(world)
    (b / ".ThanhTan").mkdir()
    set_remote(world["private"], home(world, "b"))
    with pytest.raises(ThanhTanError) as refused:
        load(b, at=AT, environ=home(world, "b"))
    assert "never saved" in str(refused.value)


def test_a_branch_with_other_commits_is_left_alone(world):
    set_remote(world["private"], home(world, "a"))
    save_a(world)
    b = machine_b(world)
    git(b, "switch", "-q", "-c", world["branch"])
    (b / "other.txt").write_text("other\n", encoding="utf-8")
    git(b, "add", "other.txt")
    git(b, "commit", "-q", "-m", "other")
    git(b, "switch", "-q", "develop")
    mine = git(b, "rev-parse", world["branch"])
    set_remote(world["private"], home(world, "b"))
    report = load(b, workflow=world["workflow"], at=AT, environ=home(world, "b"))
    assert git(b, "rev-parse", world["branch"]) == mine
    assert any(world["branch"] in warning and "other commits" in warning for warning in report.warnings)


def test_saving_twice_without_changes_pushes_nothing_new(world):
    set_remote(world["private"], home(world, "a"))
    save_a(world)
    commits = git(Path(world["private"]), "rev-list", "--count", "main")
    assert "already saved" in save_a(world).lines[0]
    assert git(Path(world["private"]), "rev-list", "--count", "main") == commits


def test_uncommitted_code_is_warned_about(world):
    set_remote(world["private"], home(world, "a"))
    (world["a"] / "README.md").write_text("changed\n", encoding="utf-8")
    assert any("uncommitted" in warning for warning in save_a(world).warnings)


def test_status_before_any_store():
    assert status(Path("/nowhere"), environ={"THANHTAN_HOME": "/nonexistent-home"})[0].startswith("store: not set up")
