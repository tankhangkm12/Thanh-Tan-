import ntpath
import os
import posixpath

import pytest

from thanhtan.constants import CONFIG_FILE, WORKSPACE_DIR
from thanhtan.interfaces import WriteTargetPolicy
from thanhtan.pathguard import WorkspaceWritePolicy


@pytest.fixture
def repo(tmp_path):
    workspace = tmp_path / "repo" / WORKSPACE_DIR
    (workspace / "decisions").mkdir(parents=True)
    (workspace / CONFIG_FILE).write_text("x", encoding="utf-8")
    (tmp_path / "repo" / "src").mkdir()
    return tmp_path / "repo"


def test_policy_implements_protocol():
    assert isinstance(WorkspaceWritePolicy(), WriteTargetPolicy)


@pytest.mark.parametrize(
    "target",
    [
        ".ThanhTan/decisions/x.md",
        "./.ThanhTan/decisions/x.md",
        ".ThanhTan",
        "src/../.ThanhTan/decisions/x.md",
        ".ThanhTan/decisions/../../.ThanhTan/state.json",
        ".ThanhTan//decisions///x.md",
        ".ThanhTan/not-yet/created/dir/file.md",
    ],
)
def test_relative_targets_inside_the_workspace_are_protected(repo, target):
    assert WorkspaceWritePolicy().is_protected(target, repo)


def test_absolute_targets_and_other_working_directories(repo):
    policy = WorkspaceWritePolicy()
    assert policy.is_protected(str(repo / WORKSPACE_DIR / "decisions" / "x.md"), repo / "src")
    assert policy.is_protected("../.ThanhTan/x.md", repo / "src")
    assert policy.is_protected(str(repo / WORKSPACE_DIR / "decisions" / "x.md"), repo.parent)


@pytest.mark.parametrize("target", ["src/app.py", ".ThanhTan-notes/x.md", "thanhtan/x.md", "x/.ThanhTany/y", "README.md"])
def test_other_paths_are_not_protected(repo, target):
    assert not WorkspaceWritePolicy().is_protected(target, repo)


def test_a_directory_named_like_the_workspace_without_config_is_not_a_workspace(tmp_path):
    (tmp_path / WORKSPACE_DIR).mkdir()
    assert not WorkspaceWritePolicy().is_protected(f"{WORKSPACE_DIR}/x.md", tmp_path)


def test_windows_compares_without_regard_to_case(repo):
    policy = WorkspaceWritePolicy(normcase=ntpath.normcase)
    # ntpath.normcase also turns '/' into '\\' and lower-cases, as on a Windows file system.
    assert policy.is_protected(".thanhtan/Decisions/X.md", repo)
    assert policy.is_protected(".THANHTAN\\decisions\\x.md", repo)


def test_posix_keeps_case_significant(repo):
    if os.path.normcase("A") != "A":  # a case-insensitive host cannot show the difference
        pytest.skip("host file system folds case")
    policy = WorkspaceWritePolicy(normcase=posixpath.normcase)
    assert not policy.is_protected(".thanhtan/decisions/x.md", repo)


def test_symlinks_into_the_workspace_are_followed(repo, tmp_path):
    link = tmp_path / "elsewhere"
    try:
        link.symlink_to(repo / WORKSPACE_DIR, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    assert WorkspaceWritePolicy().is_protected(str(link / "decisions" / "x.md"), tmp_path)
