"""The workspace is called ``.ThanhTan/`` (``~/.ThanhTan/`` for the user folder); before 0.8.0 it was ``.agentflow/``.

- The first command that finds a project with only ``.agentflow/`` moves it to ``.ThanhTan/``, keeps every task, says so on
  stderr and adds ``.ThanhTan/`` to ``.git/info/exclude``.
- A project with both folders is refused (exit 38) until a person keeps one.
- Until it is moved, the old folder is protected like the new one: the hook keeps agents out of it.
- ``~/.agentflow`` is moved to ``~/.ThanhTan`` the same way; ``AGENTFLOW_HOME`` still wins.
"""

from pathlib import Path

from checklist_helpers import checklist_workflow, open_workspace
from sdd_helpers import run, say

from thanhtan.constants import (
    CONFIG_FILE,
    LEGACY_WORKSPACE_DIR,
    WORKSPACE_DIR,
    ExitCode,
)
from thanhtan.lockguard import _workspace_of
from thanhtan.pathguard import WorkspaceWritePolicy
from thanhtan.projectlocator import user_dir


def test_the_names():
    assert WORKSPACE_DIR == ".ThanhTan"
    assert LEGACY_WORKSPACE_DIR == ".agentflow"


def legacy_project(repo: Path, tmp_path: Path, monkeypatch, capsys) -> Path:
    """A project as agentflow 0.7.0 left it: a workspace with a task, in ``.agentflow/``."""
    open_workspace(repo, tmp_path, monkeypatch, capsys, checklist_workflow(tmp_path))
    assert say(monkeypatch, "task", "new", "Orders") == ExitCode.OK
    capsys.readouterr()
    (repo / WORKSPACE_DIR).rename(repo / LEGACY_WORKSPACE_DIR)
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(exclude.read_text(encoding="utf-8").replace(f"{WORKSPACE_DIR}/", f"{LEGACY_WORKSPACE_DIR}/"), encoding="utf-8")
    return repo


def test_an_old_workspace_is_moved_on_the_first_command_and_keeps_its_tasks(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = legacy_project(gitflow_repo, tmp_path, monkeypatch, capsys)
    code, out, err = run(capsys, "status")
    assert code == ExitCode.OK
    assert f"moved {LEGACY_WORKSPACE_DIR}/ to {WORKSPACE_DIR}/" in err
    assert "T-001" in out
    assert not (repo / LEGACY_WORKSPACE_DIR).exists()
    assert (repo / WORKSPACE_DIR / CONFIG_FILE).is_file()
    assert f"{WORKSPACE_DIR}/" in (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    code, _out, err = run(capsys, "status")
    assert code == ExitCode.OK and "moved" not in err


def test_a_project_with_both_folders_is_refused(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = legacy_project(gitflow_repo, tmp_path, monkeypatch, capsys)
    (repo / WORKSPACE_DIR).mkdir()
    code, _out, err = run(capsys, "status")
    assert code == ExitCode.WORKSPACE_CONFLICT == 38
    assert "keep one" in err
    assert (repo / LEGACY_WORKSPACE_DIR / CONFIG_FILE).is_file()


def test_a_folder_named_agentflow_without_a_config_is_left_alone(gitflow_repo, tmp_path, monkeypatch, capsys):
    open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, checklist_workflow(tmp_path))
    (gitflow_repo / LEGACY_WORKSPACE_DIR).mkdir()
    code, _out, err = run(capsys, "status")
    assert code == ExitCode.OK and "moved" not in err
    assert (gitflow_repo / LEGACY_WORKSPACE_DIR).is_dir()


def test_init_moves_an_old_workspace_instead_of_making_a_second_one(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = legacy_project(gitflow_repo, tmp_path, monkeypatch, capsys)
    code, _out, err = run(capsys, "init", "--workflow", str(checklist_workflow(tmp_path)))
    assert code == ExitCode.OK and "moved" in err
    assert not (repo / LEGACY_WORKSPACE_DIR).exists()


def test_the_old_folder_is_protected_until_it_is_moved(tmp_path):
    repo = tmp_path / "repo"
    (repo / LEGACY_WORKSPACE_DIR).mkdir(parents=True)
    (repo / LEGACY_WORKSPACE_DIR / CONFIG_FILE).write_text("x", encoding="utf-8")
    policy = WorkspaceWritePolicy()
    assert policy.is_protected(f"{LEGACY_WORKSPACE_DIR}/state.json", repo)
    assert policy.is_protected(".claude/agents/project-builder.md", repo)
    assert not policy.is_protected("src/app.py", repo)
    assert _workspace_of(str(repo / "src" / "app.py")) == repo / LEGACY_WORKSPACE_DIR


def test_the_user_folder_is_moved_to_the_new_name(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".agentflow").mkdir()
    (tmp_path / ".agentflow" / "user.yaml").write_text("knowledge_dir: k\n", encoding="utf-8")
    assert user_dir({}) == tmp_path / ".ThanhTan"
    assert (tmp_path / ".ThanhTan" / "user.yaml").is_file()
    assert not (tmp_path / ".agentflow").exists()


def test_the_user_folder_keeps_the_new_one_when_both_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".agentflow").mkdir()
    (tmp_path / ".ThanhTan").mkdir()
    assert user_dir({}) == tmp_path / ".ThanhTan"
    assert (tmp_path / ".agentflow").is_dir()


def test_agentflow_home_still_wins(tmp_path):
    assert user_dir({"AGENTFLOW_HOME": str(tmp_path / "elsewhere")}) == tmp_path / "elsewhere"
