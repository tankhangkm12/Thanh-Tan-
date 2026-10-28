"""The branch a task starts from is the project's to choose.

- ``git.base.default``, ``git.base.<type>``, ``git.main_branch`` and ``git.develop_branch`` (``agentflow config set``, a
  person's command) and ``agentflow task new --base <branch>`` choose it; ``--base`` beats the type, the type beats
  the default, and the built-in choice (develop; main for a hotfix) is what is left.
- The task keeps its base: a later change of a setting does not move it, and ``scope``, ``review-map`` and the summary
  compare the work with that base, not with develop.
- The guard keeps agents off the base branches the project named, and off the base of an open task.
"""

import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import git
from sdd_helpers import init_workspace, run, sample_workflow, say

from agentflow import gitconfig
from agentflow.constants import ExitCode, GuardDecision, GuardRule
from agentflow.guard import evaluate
from agentflow.hook import protected_branches
from agentflow.models import StepStatus, Task, TaskStatus
from agentflow.seal import base_branch
from agentflow.workspace import find_workspace


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    """develop checked out, plus a branch ``feature/login`` with one commit that develop does not have."""
    git(gitflow_repo, "switch", "-q", "-c", "feature/login")
    (gitflow_repo / "login.txt").write_text("login\n", encoding="utf-8")
    git(gitflow_repo, "add", "login.txt")
    git(gitflow_repo, "commit", "-q", "-m", "login screen")
    git(gitflow_repo, "switch", "-q", "develop")
    return init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)


def state_task(repo: Path) -> dict:
    import json

    return json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][-1]


def config(capsys, key: str, value: str) -> tuple[int, str, str]:
    return run(capsys, "config", "set", key, value)


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repo).returncode == 0


# ------------------------------------------------------------------ branch names


@pytest.mark.parametrize("name", ["develop", "feature/login", "release/1.2", "dev-2", "team_a/x.y"])
def test_ordinary_branch_names_are_accepted(name):
    assert gitconfig.name_problem(name) is None


@pytest.mark.parametrize("name", ["", " ", "a b", "a..b", "a//b", "-x", "/x", "x/", "x.", "x.lock", "a~1", "a^", "a:b", "a?", "a*", "a[b", "a\\b", "a@{b", "@", " x"])
def test_names_git_would_refuse_are_refused(name):
    assert gitconfig.name_problem(name) is not None


def test_a_name_that_is_not_text_is_refused():
    assert gitconfig.name_problem(None) is not None and gitconfig.name_problem(3) is not None


# ------------------------------------------------------------------ the settings


def test_the_built_in_choice_is_develop_and_main_for_a_hotfix():
    names = gitconfig.GitNames()
    assert [names.base_for(kind) for kind in ("feature", "bugfix", "refactor", "chore")] == ["develop"] * 4
    assert names.base_for("hotfix") == "main"


def test_a_renamed_main_and_develop_are_the_built_in_choice():
    names = gitconfig.names_from({"git": {"main_branch": "master", "develop_branch": "dev"}})
    assert (names.base_for("feature"), names.base_for("hotfix")) == ("dev", "master")


def test_the_default_applies_to_every_type_and_a_type_beats_it():
    names = gitconfig.names_from({"git": {"base": {"default": "feature/login", "hotfix": "release/1"}}})
    assert [names.base_for(kind) for kind in ("feature", "refactor")] == ["feature/login"] * 2
    assert names.base_for("hotfix") == "release/1"


def test_the_explicit_base_beats_the_settings():
    names = gitconfig.names_from({"git": {"base": {"default": "feature/login", "feature": "x"}}})
    assert names.base_for("feature", "mine") == "mine"


def test_a_setting_with_a_bad_value_is_ignored_when_read_and_reported_by_the_check():
    settings = {"git": {"develop_branch": "a b", "base": {"default": "ok", "bugfix": "x..y", "nope": "z"}, "other": 1}}
    names = gitconfig.names_from(settings)
    assert names.develop == "develop" and names.base_default == "ok" and "bugfix" not in names.base_by_type
    found = gitconfig.settings_problems(settings)
    assert len(found) == 4 and any("git.other" in p for p in found) and any("git.base.nope" in p for p in found)
    assert gitconfig.settings_problems(None) == [] and gitconfig.settings_problems({"x": 1}) == []


def test_protected_branches_hold_the_built_in_names_the_configured_ones_and_the_open_bases():
    names = gitconfig.names_from({"git": {"develop_branch": "dev", "base": {"default": "feature/login", "hotfix": "release/1"}}})
    assert names.protected(["feature/payment", None]) == {"main", "develop", "dev", "feature/login", "release/1", "feature/payment"}


# ------------------------------------------------------------------ config set and check


def test_a_person_sets_and_reads_the_base(repo, capsys):
    assert config(capsys, "git.base.default", "feature/login")[0] == ExitCode.OK
    code, out, _err = run(capsys, "config", "get", "git.base.default")
    assert code == ExitCode.OK and out.strip() == "feature/login"
    assert run(capsys, "config", "check")[0] == ExitCode.OK


@pytest.mark.parametrize(
    ("key", "value"),
    [("git.base.default", "bad name"), ("git.base.spike", "x"), ("git.nope", "x"), ("git.develop_branch", ""), ("git", "x"), ("git.base", "x")],
)
def test_a_bad_git_setting_is_refused_and_nothing_is_written(repo, capsys, key, value):
    code, _out, err = config(capsys, key, value)
    assert code == ExitCode.SETTINGS_INVALID and key in err
    assert run(capsys, "config", "get", key)[0] != ExitCode.OK


def test_the_check_reports_a_git_section_written_by_hand(repo, capsys):
    path = repo / ".ThanhTan" / "config.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["settings"] = {"git": {"base": {"default": "a b"}}}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    code, out, err = run(capsys, "config", "check")
    assert code == ExitCode.SETTINGS_INVALID and "git.base.default" in out


# ------------------------------------------------------------------ task new


def test_a_task_starts_from_the_branch_the_person_names(repo, monkeypatch, capsys):
    code, out, _err = run(capsys, "task", "new", "Login OTP", "--base", "feature/login")
    assert code == ExitCode.OK and "from feature/login" in out
    task = state_task(repo)
    assert task["base"] == "feature/login" and task["branch"].startswith("feature/T-001-")
    assert (repo / "login.txt").is_file(), "the new branch holds what feature/login holds"
    assert is_ancestor(repo, "feature/login", task["branch"])


def test_without_any_setting_the_task_starts_from_develop(repo, capsys):
    code, out, _err = run(capsys, "task", "new", "Plain")
    assert code == ExitCode.OK and "from develop" in out and state_task(repo)["base"] == "develop"
    assert not (repo / "login.txt").exists()


def test_the_project_default_and_the_type_setting_choose_the_base(repo, monkeypatch, capsys):
    assert config(capsys, "git.base.default", "feature/login")[0] == ExitCode.OK
    assert run(capsys, "task", "new", "One")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "feature/login"
    assert say(monkeypatch, "task", "cancel") == ExitCode.OK
    git(repo, "switch", "-q", "develop")
    assert config(capsys, "git.base.bugfix", "develop")[0] == ExitCode.OK
    assert run(capsys, "task", "new", "Two", "--type", "bugfix")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "develop"


def test_the_flag_beats_the_settings(repo, monkeypatch, capsys):
    git(repo, "branch", "release/2")
    assert config(capsys, "git.base.default", "feature/login")[0] == ExitCode.OK
    assert run(capsys, "task", "new", "Three", "--base", "release/2")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "release/2"


def test_a_hotfix_starts_from_main_and_a_renamed_main_is_followed(repo, monkeypatch, capsys):
    assert run(capsys, "task", "new", "Urgent", "--type", "hotfix")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "main"
    assert say(monkeypatch, "task", "cancel") == ExitCode.OK
    git(repo, "switch", "-q", "develop")
    git(repo, "branch", "master", "main")
    assert config(capsys, "git.main_branch", "master")[0] == ExitCode.OK
    assert run(capsys, "task", "new", "Urgent again", "--type", "hotfix")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "master"


def test_a_renamed_develop_is_followed(repo, capsys):
    git(repo, "branch", "-m", "develop", "dev")
    assert config(capsys, "git.develop_branch", "dev")[0] == ExitCode.OK
    assert run(capsys, "task", "new", "On dev")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "dev"


def test_a_base_that_does_not_exist_is_refused_with_the_way_out(repo, capsys):
    code, _out, err = run(capsys, "task", "new", "Nowhere", "--base", "feature/none")
    assert code == ExitCode.BRANCH_PROBLEM
    assert "feature/none" in err and "--base" in err and "git.base.default" in err
    import json

    assert json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"] == []


def test_a_bad_flag_value_is_refused_before_anything_is_created(repo, capsys):
    code, _out, err = run(capsys, "task", "new", "Bad", "--base", "a b")
    assert code == ExitCode.INVALID_INPUT and "--base" in err
    assert git(repo, "branch", "--list", "feature/T-001*") == ""


def test_changing_a_setting_later_does_not_move_a_running_task(repo, capsys):
    assert run(capsys, "task", "new", "Stays", "--base", "feature/login")[0] == ExitCode.OK
    assert config(capsys, "git.base.default", "develop")[0] == ExitCode.OK
    assert state_task(repo)["base"] == "feature/login"
    _code, out, _err = run(capsys, "status")
    assert "base: feature/login" in out
    assert "- Base: feature/login" in (repo / ".ThanhTan" / "STATE.md").read_text(encoding="utf-8")


def test_a_base_that_is_behind_origin_is_warned_about(repo, tmp_path, capsys):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "origin", "develop")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "develop", str(bare), str(other)], check=True)
    ident = ["-c", "user.name=T", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    (other / "colleague.txt").write_text("c\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(other), "add", "colleague.txt"], check=True)
    subprocess.run(["git", "-C", str(other), *ident, "commit", "-q", "-m", "colleague"], check=True)
    subprocess.run(["git", "-C", str(other), "push", "-q", "origin", "develop"], check=True)
    git(repo, "fetch", "-q", "origin")
    code, _out, err = run(capsys, "task", "new", "Late")
    assert code == ExitCode.OK
    assert "'develop' is 1 commit(s) behind origin/develop" in err and "git pull" in err


def test_a_base_that_is_up_to_date_gives_no_warning(repo, capsys):
    code, _out, err = run(capsys, "task", "new", "Fresh")
    assert code == ExitCode.OK and "behind" not in err


# ------------------------------------------------------------------ the work is compared with the base


def test_scope_compares_with_the_base_not_with_develop(repo, monkeypatch, capsys):
    assert run(capsys, "task", "new", "Login OTP", "--base", "feature/login")[0] == ExitCode.OK
    (repo / "otp.txt").write_text("otp\n", encoding="utf-8")
    git(repo, "add", "otp.txt")
    git(repo, "commit", "-q", "-m", "T-001: otp")
    code, out, _err = run(capsys, "scope")
    assert code == ExitCode.OK
    assert "git diff feature/login.." in out
    assert "T-001: otp" in out and "login screen" not in out


def test_a_task_recorded_before_the_base_was_kept_reads_it_off_its_branch():
    old = Task("T-001", "Old", TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, branch="hotfix/T-001-x")
    assert base_branch(old) == "main"
    assert base_branch(Task("T-002", "Old", TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, branch="feature/T-002-x")) == "develop"
    assert base_branch(Task("T-003", "New", TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, branch="feature/T-003-x", base="feature/login")) == "feature/login"


# ------------------------------------------------------------------ the guard


class _On:
    def __init__(self, branch):
        self.branch = branch

    def current_branch(self, directory):
        return self.branch

    def branch_exists(self, directory, name):
        return True


def test_an_agent_may_not_commit_on_a_branch_the_project_named(tmp_path):
    here = tmp_path
    on_login = _On("feature/login")
    assert evaluate("git merge topic", here, on_login).decision is GuardDecision.ALLOW
    verdict = evaluate("git merge topic", here, on_login, protected_branches={"feature/login"})
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PROTECTED_BRANCH
    assert evaluate("git merge topic", here, _On("develop")).decision is GuardDecision.DENY, "the built-in two stay protected"


def test_the_protected_branches_come_from_the_settings_and_the_open_task(repo, capsys):
    paths = find_workspace(repo)
    assert protected_branches(paths) == {"main", "develop"}
    assert config(capsys, "git.develop_branch", "dev")[0] == ExitCode.OK
    git(repo, "branch", "dev")
    assert run(capsys, "task", "new", "Login OTP", "--base", "feature/login")[0] == ExitCode.OK
    assert protected_branches(paths) == {"main", "develop", "dev", "feature/login"}


def test_the_guard_command_reads_the_project_too(repo, monkeypatch, capsys):
    import io
    import json

    assert config(capsys, "git.base.default", "feature/login")[0] == ExitCode.OK
    git(repo, "switch", "-q", "feature/login")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"command": "git merge topic", "cwd": str(repo)})))
    code, out, _err = run(capsys, "guard")
    assert code == ExitCode.OK and json.loads(out)["decision"] == "deny"


def test_a_workspace_that_cannot_be_read_keeps_the_two_built_in_protected_branches(repo):
    paths = find_workspace(repo)
    (repo / ".ThanhTan" / "config.yaml").write_text("{ not: [valid", encoding="utf-8")
    assert protected_branches(paths) == {"main", "develop"}
