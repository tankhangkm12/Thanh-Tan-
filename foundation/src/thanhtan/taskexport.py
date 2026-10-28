"""``thanhtan task export``: a clean branch for a pull request, with the whole task as one commit.

The task branch keeps every commit an agent made (``C1: ...``, ``C2: ...``). Many teams want one commit with a plain
message. Export builds it without touching the checkout: the tree of the task's last commit, on top of the commit the
task branched from (``git merge-base``), as a new branch (by default the task branch without its ``T-001-`` part).
Nothing is pushed; the person pushes it themselves.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from thanhtan.constants import BRANCH_SEPARATOR, ExitCode, TaskStatus
from thanhtan.errors import ThanhTanError
from thanhtan.git import run_git
from thanhtan.models import Task
from thanhtan.seal import base_branch

_TASK_PART = re.compile(r"^T-\d+-")


@dataclass
class Export:
    branch: str
    commit: str
    base: str
    files: int
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _fail(message: str) -> ThanhTanError:
    return ThanhTanError(message, ExitCode.EXPORT_FAILED)


def _git(root: Path, *args: str) -> str:
    done = run_git(root, *args)
    if done.returncode != 0:
        raise _fail(f"git {' '.join(args[:2])} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def default_branch(task: Task) -> str:
    """``chore/T-002-them-dockerfile`` -> ``chore/them-dockerfile``."""
    prefix, _, rest = (task.branch or "").partition(BRANCH_SEPARATOR)
    return f"{prefix}{BRANCH_SEPARATOR}{_TASK_PART.sub('', rest)}" if rest else f"export/{task.id}"


def default_message(task: Task) -> str:
    kind = str(task.type) if task.type else (task.branch or "").partition(BRANCH_SEPARATOR)[0] or "feat"
    return f"{kind}: {task.title}"


def export(root: Path, task: Task, *, branch: str | None = None, message: str | None = None) -> Export:
    if not task.branch:
        raise _fail(f"task {task.id} has no branch recorded")
    tip = run_git(root, "rev-parse", "--verify", "-q", f"refs/heads/{task.branch}")
    if tip.returncode != 0:
        raise _fail(f"the branch of task {task.id} ({task.branch}) is not on this machine")
    base = base_branch(task)
    if run_git(root, "rev-parse", "--verify", "-q", f"refs/heads/{base}").returncode != 0:
        raise _fail(f"the base branch of task {task.id} ({base}) is not on this machine")
    name = branch or default_branch(task)
    if run_git(root, "check-ref-format", "--branch", name).returncode != 0:
        raise _fail(f"'{name}' is not a valid branch name")
    if run_git(root, "rev-parse", "--verify", "-q", f"refs/heads/{name}").returncode == 0:
        raise _fail(f"branch {name} already exists: delete it (`git branch -D {name}`) or pass --branch <other name>")
    fork = _git(root, "merge-base", base, task.branch)
    tree = _git(root, "rev-parse", f"{task.branch}^{{tree}}")
    if tree == _git(root, "rev-parse", f"{fork}^{{tree}}"):
        raise _fail(f"task {task.id} changes nothing compared with {base}")
    commit = _git(root, "commit-tree", tree, "-p", fork, "-m", message or default_message(task))
    _git(root, "branch", name, commit)
    files = len([line for line in _git(root, "diff", "--name-only", fork, commit).splitlines() if line])
    result = Export(name, commit, base, files)
    result.lines.append(f"created branch {name}: one commit ({files} file(s)) on {base} at {fork[:7]}, from task {task.id}")
    result.lines.append(f"push it yourself: git push -u origin {name}")
    if task.status is not TaskStatus.DONE:
        result.warnings.append(f"task {task.id} is not finished yet ({task.status}); the export holds its work so far")
    if _git(root, "rev-parse", base) != fork:
        result.warnings.append(f"{base} has moved on since the task started: `git switch {name}` then `git rebase {base}` before pushing")
    return result
