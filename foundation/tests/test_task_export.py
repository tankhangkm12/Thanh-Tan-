"""``thanhtan task export``: one commit with the task's whole change, on a new branch, without touching the checkout."""

import pytest
from conftest import git

from thanhtan.constants import ExitCode, StepStatus, TaskStatus
from thanhtan.errors import ThanhTanError
from thanhtan.models import Task
from thanhtan.taskexport import default_branch, default_message, export


def task(**changes) -> Task:
    values = {
        "id": "T-002", "title": "Thêm Dockerfile", "status": TaskStatus.DONE, "current_step": "review",
        "step_status": StepStatus.PASSED, "branch": "chore/T-002-them-dockerfile", "type": "chore", "base": "develop",
    }  # fmt: skip
    values.update(changes)
    return Task(**values)


@pytest.fixture
def repo(gitflow_repo):
    git(gitflow_repo, "switch", "-q", "-c", "chore/T-002-them-dockerfile")
    for name in ("Dockerfile", ".dockerignore"):
        (gitflow_repo / name).write_text(f"{name}\n", encoding="utf-8")
        git(gitflow_repo, "add", name)
        git(gitflow_repo, "commit", "-q", "-m", f"C1: {name}")
    git(gitflow_repo, "switch", "-q", "develop")
    return gitflow_repo


def test_names_and_message_leave_out_the_task_number():
    assert default_branch(task()) == "chore/them-dockerfile"
    assert default_message(task()) == "chore: Thêm Dockerfile"
    assert default_message(task(type=None, branch="feature/T-001-x")) == "feature: Thêm Dockerfile"


def test_the_export_is_one_commit_with_the_whole_change(repo):
    before = git(repo, "rev-parse", "HEAD")
    result = export(repo, task())
    assert result.branch == "chore/them-dockerfile" and result.files == 2
    assert git(repo, "rev-list", "--count", "develop..chore/them-dockerfile") == "1"
    assert git(repo, "log", "-1", "--format=%s", "chore/them-dockerfile") == "chore: Thêm Dockerfile"
    assert git(repo, "rev-parse", "chore/them-dockerfile^{tree}") == git(repo, "rev-parse", "chore/T-002-them-dockerfile^{tree}")
    assert git(repo, "rev-parse", "HEAD") == before and git(repo, "branch", "--show-current") == "develop"
    assert "git push -u origin chore/them-dockerfile" in result.lines[-1]
    assert result.warnings == []


def test_a_chosen_branch_and_message(repo):
    result = export(repo, task(), branch="feature/INV-12-dockerfile", message="INV-12 add a Dockerfile")
    assert git(repo, "log", "-1", "--format=%s", result.branch) == "INV-12 add a Dockerfile"


def test_an_existing_branch_is_not_overwritten(repo):
    export(repo, task())
    with pytest.raises(ThanhTanError) as refused:
        export(repo, task())
    assert refused.value.code == ExitCode.EXPORT_FAILED and "already exists" in str(refused.value)


def test_an_unfinished_task_or_a_moved_base_is_warned_about(repo):
    (repo / "later.txt").write_text("later\n", encoding="utf-8")
    git(repo, "add", "later.txt")
    git(repo, "commit", "-q", "-m", "later on develop")
    result = export(repo, task(status=TaskStatus.OPEN))
    assert any("not finished" in warning for warning in result.warnings)
    assert any("git rebase develop" in warning for warning in result.warnings)
    assert "later.txt" not in git(repo, "diff", "--name-only", f"{result.branch}~1", result.branch)


def test_a_task_without_changes_or_branch_is_refused(gitflow_repo):
    git(gitflow_repo, "branch", "chore/T-003-nothing")
    with pytest.raises(ThanhTanError, match="changes nothing"):
        export(gitflow_repo, task(id="T-003", branch="chore/T-003-nothing"))
    with pytest.raises(ThanhTanError, match="not on this machine"):
        export(gitflow_repo, task(branch="chore/T-009-gone"))
