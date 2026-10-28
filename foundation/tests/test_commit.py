import pytest
from conftest import git

from thanhtan.commit import commit_staged
from thanhtan.constants import ExitCode, TaskType
from thanhtan.errors import ThanhTanError
from thanhtan.git import SubprocessGit
from thanhtan.models import ScanResult
from thanhtan.state import JsonStateStore
from thanhtan.tasks import new_task
from thanhtan.workspace import init_workspace, load_workspace_workflow


class FakeScanner:
    def __init__(self, clean=True, error=None):
        self.clean, self.error, self.calls = clean, error, 0

    def scan_staged(self, repo):
        self.calls += 1
        if self.error:
            raise self.error
        return ScanResult(self.clean, "Finding: REDACTED" if not self.clean else "")


@pytest.fixture
def env(gitflow_repo, workflow_file):
    paths = init_workspace(gitflow_repo, workflow_file).paths
    workflow = load_workspace_workflow(paths)
    store = JsonStateStore(paths.dir, workflow)
    client = SubprocessGit(gitflow_repo)
    new_task(store, workflow, client, "Add thing", TaskType.FEATURE, lambda: "2026-10-10T10:00:00Z")
    (gitflow_repo / "a.txt").write_text("a", encoding="utf-8")
    git(gitflow_repo, "add", "a.txt")
    return store, client, gitflow_repo


def test_commits_with_task_prefix_after_scan(env):
    store, client, repo = env
    scanner = FakeScanner()
    result = commit_staged(store, client, scanner, "  add a  ")
    assert result.message == "T-001: add a"
    assert git(repo, "log", "-1", "--format=%s") == "T-001: add a"
    assert result.sha == git(repo, "rev-parse", "HEAD")
    assert scanner.calls == 1


def test_leaks_block_the_commit(env):
    store, client, repo = env
    head = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, client, FakeScanner(clean=False), "add a")
    assert exc.value.code is ExitCode.SECRETS_FOUND
    assert "REDACTED" in str(exc.value)
    assert git(repo, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("code", [ExitCode.ENGINE_NOT_RUNNING, ExitCode.SCAN_FAILED, ExitCode.MISSING_REQUIREMENT])
def test_scanner_errors_block_the_commit(env, code):
    store, client, repo = env
    head = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, client, FakeScanner(error=ThanhTanError("down", code)), "add a")
    assert exc.value.code is code
    assert git(repo, "rev-parse", "HEAD") == head


def test_wrong_branch_is_refused_before_scanning(env):
    store, client, repo = env
    git(repo, "stash", "-q")
    git(repo, "switch", "-q", "develop")
    git(repo, "stash", "pop", "-q")
    scanner = FakeScanner()
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, client, scanner, "add a")
    assert exc.value.code is ExitCode.BRANCH_PROBLEM
    assert "feature/T-001-add-thing" in str(exc.value)
    assert scanner.calls == 0


def test_nothing_staged(env):
    store, client, repo = env
    git(repo, "reset", "-q")
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, client, FakeScanner(), "x")
    assert exc.value.code is ExitCode.NOTHING_STAGED


def test_empty_message(env):
    store, client, _ = env
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, client, FakeScanner(), "  ")
    assert exc.value.code is ExitCode.INVALID_INPUT


def test_no_active_task(gitflow_repo, workflow_file):
    paths = init_workspace(gitflow_repo, workflow_file).paths
    store = JsonStateStore(paths.dir, load_workspace_workflow(paths))
    with pytest.raises(ThanhTanError) as exc:
        commit_staged(store, SubprocessGit(gitflow_repo), FakeScanner(), "x")
    assert exc.value.code is ExitCode.NO_ACTIVE_TASK


# ------------------------------------------------------------------ files outside the plan item (a warning, never a refusal)


def _item(*files):
    from thanhtan.plan import PlanItem

    return {"C1": PlanItem(code="C1", title="t", files=tuple(files))}


def test_a_staged_file_outside_the_files_of_the_item_is_reported(env):
    store, client, repo = env
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", "b.txt")
    result = commit_staged(store, client, FakeScanner(), "add", "C1", _item("a.txt"))
    assert result.outside == ("b.txt",)


def test_files_listed_by_name_folder_or_glob_are_not_reported(env):
    store, client, repo = env
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("x", encoding="utf-8")
    git(repo, "add", "src/x.py")
    result = commit_staged(store, client, FakeScanner(), "add", "C1", _item("a.txt", "src/"))
    assert result.outside == ()


def test_nothing_is_reported_without_an_item_or_when_the_item_lists_no_files(env):
    store, client, repo = env
    assert commit_staged(store, client, FakeScanner(), "no item").outside == ()
    (repo / "c.txt").write_text("c", encoding="utf-8")
    git(repo, "add", "c.txt")
    assert commit_staged(store, client, FakeScanner(), "empty list", "C1", _item()).outside == ()
