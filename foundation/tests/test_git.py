import pytest
from conftest import git

from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.git import GitBranchLookup, SubprocessGit
from thanhtan.interfaces import BranchLookup, GitClient


@pytest.fixture
def client(gitflow_repo):
    return SubprocessGit(gitflow_repo)


def test_implements_protocols(client):
    assert isinstance(client, GitClient)
    assert isinstance(GitBranchLookup(), BranchLookup)


def test_current_branch_and_detached_head(client, gitflow_repo):
    assert client.current_branch() == "develop"
    git(gitflow_repo, "switch", "-q", "--detach")
    assert client.current_branch() is None


def test_is_clean_counts_untracked_modified_and_staged(client, gitflow_repo):
    assert client.is_clean()
    (gitflow_repo / "new.txt").write_text("x", encoding="utf-8")
    assert not client.is_clean()
    git(gitflow_repo, "add", "new.txt")
    assert not client.is_clean()


def test_ignored_files_do_not_make_the_tree_dirty(client, gitflow_repo):
    (gitflow_repo / ".git" / "info" / "exclude").write_text(".ThanhTan/\n", encoding="utf-8")
    (gitflow_repo / ".ThanhTan").mkdir()
    (gitflow_repo / ".ThanhTan" / "state.json").write_text("{}", encoding="utf-8")
    assert client.is_clean()


def test_branch_exists_and_create(client):
    assert client.branch_exists("main")
    assert not client.branch_exists("feature/x")
    client.create_branch("feature/x", "main")
    assert client.current_branch() == "feature/x"
    assert client.branch_exists("feature/x")


def test_create_branch_from_missing_base_fails(client):
    with pytest.raises(ThanhTanError) as exc:
        client.create_branch("feature/x", "nope")
    assert exc.value.code is ExitCode.GIT_FAILED


def test_staged_changes_and_commit(client, gitflow_repo):
    assert not client.has_staged_changes()
    (gitflow_repo / "a.txt").write_text("a", encoding="utf-8")
    assert not client.has_staged_changes()  # untracked is not staged
    git(gitflow_repo, "add", "a.txt")
    assert client.has_staged_changes()
    sha = client.commit("T-001: add a")
    assert sha == git(gitflow_repo, "rev-parse", "HEAD")
    assert git(gitflow_repo, "log", "-1", "--format=%s") == "T-001: add a"
    assert not client.has_staged_changes()


def test_commit_with_nothing_staged_fails(client):
    with pytest.raises(ThanhTanError) as exc:
        client.commit("empty")
    assert exc.value.code is ExitCode.GIT_FAILED


def test_branch_lookup_outside_a_repository_is_unknown(tmp_path):
    lookup = GitBranchLookup()
    assert lookup.current_branch(tmp_path / "missing") is None
    assert lookup.current_branch(tmp_path) is None
    assert not lookup.branch_exists(tmp_path, "main")


def test_branch_lookup_in_a_repository(gitflow_repo):
    lookup = GitBranchLookup()
    assert lookup.current_branch(gitflow_repo) == "develop"
    assert lookup.branch_exists(gitflow_repo, "main")
    assert not lookup.branch_exists(gitflow_repo, "ghost")
