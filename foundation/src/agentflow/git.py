"""Git through its command line: the ``GitClient`` for one repository and the guard's ``BranchLookup``."""

import subprocess
from pathlib import Path

from agentflow.constants import ENCODING, GIT_EXECUTABLE, PLAN_ITEM_TRAILER, ExitCode
from agentflow.errors import AgentflowError
from agentflow.models import CommitInfo, FileChange

CURRENT_BRANCH_ARGS = ("symbolic-ref", "--quiet", "--short", "HEAD")
STATUS_ARGS = ("status", "--porcelain")
VERIFY_ARGS = ("rev-parse", "--verify", "--quiet")
HEAD_SHA_ARGS = ("rev-parse", "HEAD")
SWITCH_CREATE_ARGS = ("switch", "--quiet", "--create")
STAGED_QUIET_ARGS = ("diff", "--cached", "--quiet")
COMMIT_ARGS = ("commit", "--quiet", "--message")
HEADS_REF_PREFIX = "refs/heads/"
TAGS_REF_PREFIX = "refs/tags/"
CONFIG_GET_ARGS = ("config", "--get")
FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1e"
LOG_FORMAT = (
    f"--format=%H{FIELD_SEPARATOR}%s{FIELD_SEPARATOR}"
    f"%(trailers:key={PLAN_ITEM_TRAILER},valueonly,unfold){RECORD_SEPARATOR}"
)
# Return code reported for a directory that does not exist (git itself uses 128 for fatal errors).
NO_DIRECTORY = 128
# `git diff --quiet` exits 1 when there are differences.
DIFF_HAS_CHANGES = 1


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if not cwd.is_dir():
        return subprocess.CompletedProcess([GIT_EXECUTABLE, *args], NO_DIRECTORY, "", f"not a directory: {cwd}")
    try:
        return subprocess.run(
            [GIT_EXECUTABLE, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding=ENCODING,
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise AgentflowError("git is not installed or not on PATH", ExitCode.MISSING_REQUIREMENT) from exc


def _checked(cwd: Path, *args: str) -> str:
    result = run_git(cwd, *args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentflowError(f"git {' '.join(args)} failed: {detail}", ExitCode.GIT_FAILED)
    return result.stdout.strip()


class SubprocessGit:
    """``GitClient`` for the repository at ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def current_branch(self) -> str | None:
        result = run_git(self.root, *CURRENT_BRANCH_ARGS)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def is_clean(self) -> bool:
        return _checked(self.root, *STATUS_ARGS) == ""

    def branch_exists(self, name: str) -> bool:
        return run_git(self.root, *VERIFY_ARGS, HEADS_REF_PREFIX + name).returncode == 0

    def create_branch(self, name: str, base: str) -> None:
        _checked(self.root, *SWITCH_CREATE_ARGS, name, base)

    def has_staged_changes(self) -> bool:
        result = run_git(self.root, *STAGED_QUIET_ARGS)
        if result.returncode not in (0, DIFF_HAS_CHANGES):
            raise AgentflowError(f"cannot read staged changes: {result.stderr.strip()}", ExitCode.GIT_FAILED)
        return result.returncode == DIFF_HAS_CHANGES

    def staged_files(self) -> list[str]:
        output = _checked(self.root, "diff", "--cached", "--name-only")
        return [line for line in output.splitlines() if line]

    def commit(self, message: str) -> str:
        _checked(self.root, *COMMIT_ARGS, message)
        return _checked(self.root, *HEAD_SHA_ARGS)

    def head_or_empty(self) -> str:
        """The current commit, or an empty string when there is none."""
        result = run_git(self.root, *HEAD_SHA_ARGS)
        return result.stdout.strip() if result.returncode == 0 else ""

    def rev_parse(self, ref: str) -> str:
        return _checked(self.root, "rev-parse", "--verify", f"{ref}^{{commit}}")

    def tag_exists(self, name: str) -> bool:
        return run_git(self.root, *VERIFY_ARGS, TAGS_REF_PREFIX + name).returncode == 0

    def create_tag(self, name: str, target: str, message: str) -> None:
        _checked(self.root, "tag", "--annotate", "--message", message, name, target)

    def commits_between(self, base: str, head: str) -> list[CommitInfo]:
        # Not `_checked`: it strips the output, and Python treats the separator characters as whitespace.
        done = run_git(self.root, "log", "--reverse", LOG_FORMAT, f"{base}..{head}")
        if done.returncode != 0:
            raise AgentflowError(f"git log failed: {(done.stderr or done.stdout).strip()}", ExitCode.GIT_FAILED)
        output = done.stdout
        commits = []
        for record in output.split(RECORD_SEPARATOR):
            record = record.strip("\r\n")
            if not record:
                continue
            sha, subject, item = record.split(FIELD_SEPARATOR)
            commits.append(CommitInfo(sha, subject, item.strip() or None))
        return commits

    def changed_files(self, base: str, head: str) -> list[str]:
        output = _checked(self.root, "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}")
        return [line for line in output.splitlines() if line]

    def changed_entries(self, base: str, head: str) -> list[FileChange]:
        # NUL-separated so that a name with unusual characters comes out as it is, not quoted.
        done = run_git(self.root, "diff", "--name-status", "-z", "-M", f"{base}...{head}")
        if done.returncode != 0:
            raise AgentflowError(f"git diff failed: {(done.stderr or done.stdout).strip()}", ExitCode.GIT_FAILED)
        fields = done.stdout.split("\0")
        changes: list[FileChange] = []
        position = 0
        while position < len(fields) and fields[position]:
            code = fields[position][0]
            if code in {"R", "C"} and position + 2 < len(fields):
                old, new = fields[position + 1], fields[position + 2]
                changes.append(FileChange("R" if code == "R" else "A", new, old if code == "R" else None))
                position += 3
            elif position + 1 < len(fields):
                changes.append(FileChange({"A": "A", "D": "D"}.get(code, "M"), fields[position + 1]))
                position += 2
            else:
                break
        return changes

    def identity(self) -> str:
        name = run_git(self.root, *CONFIG_GET_ARGS, "user.name").stdout.strip()
        email = run_git(self.root, *CONFIG_GET_ARGS, "user.email").stdout.strip()
        return f"{name or 'unknown'} <{email or 'unknown'}>"


class GitBranchLookup:
    """``BranchLookup`` that asks git; any failure (no repository, missing directory) reads as unknown."""

    def current_branch(self, directory: Path) -> str | None:
        if not directory.is_dir():
            return None
        result = run_git(directory, *CURRENT_BRANCH_ARGS)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def branch_exists(self, directory: Path, name: str) -> bool:
        if not directory.is_dir():
            return False
        return run_git(directory, *VERIFY_ARGS, HEADS_REF_PREFIX + name).returncode == 0
