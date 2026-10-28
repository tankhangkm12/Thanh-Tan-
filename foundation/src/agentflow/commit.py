"""`agentflow commit`: commit staged changes on the task's own branch, after a clean secret scan."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from agentflow.constants import COMMIT_PREFIX_SEPARATOR, PLAN_ITEM_TRAILER, ExitCode
from agentflow.errors import AgentflowError
from agentflow.ext_rules import file_listed
from agentflow.interfaces import GitClient, SecretScanner, StateStore
from agentflow.models import CommitResult
from agentflow.plan import PlanItem
from agentflow.tasks import require_active_task

class CommitRules(Protocol):
    def commit_problems(self, item: PlanItem | None, staged: Sequence[str]) -> list[str]: ...


LEAKS_HINT = "secrets were found in the staged changes; nothing was committed. Remove them, restage and retry"


def commit_staged(
    store: StateStore,
    git: GitClient,
    scanner: SecretScanner,
    message: str,
    item: str | None = None,
    plan_items: Mapping[str, PlanItem] | None = None,
    rules: CommitRules | None = None,
) -> CommitResult:
    """Commit what is staged. ``item`` ties the commit to a plan item; ``plan_items`` (when known) must contain it.

    ``rules`` (from extensions) may refuse the commit: for example a path only one role may change.
    """
    message = message.strip()
    if not message:
        raise AgentflowError("the commit message is empty", ExitCode.INVALID_INPUT)
    if item is not None and plan_items is not None and item not in plan_items:
        known = ", ".join(sorted(plan_items)) or "none"
        raise AgentflowError(f"the plan has no item '{item}' (items: {known})", ExitCode.INVALID_INPUT)
    task = require_active_task(store.load())
    if task.branch is None:
        raise AgentflowError(f"task {task.id} has no branch recorded", ExitCode.BRANCH_PROBLEM)
    current = git.current_branch()
    if current != task.branch:
        raise AgentflowError(
            f"task {task.id} lives on branch '{task.branch}' but the checked-out branch is "
            f"'{current or 'none (detached HEAD)'}'; switch to the task branch first",
            ExitCode.BRANCH_PROBLEM,
        )
    if not git.has_staged_changes():
        raise AgentflowError("nothing is staged; `git add` the files to commit first", ExitCode.NOTHING_STAGED)

    staged = git.staged_files()
    if rules is not None:
        problems = rules.commit_problems(plan_items.get(item) if item and plan_items else None, staged)
        if problems:
            raise AgentflowError("the commit is refused:\n  - " + "\n  - ".join(problems), ExitCode.PLAN_INVALID)
    scan = scanner.scan_staged(git.root)
    if not scan.clean:
        raise AgentflowError(f"{LEAKS_HINT}:\n{scan.output}", ExitCode.SECRETS_FOUND)

    full_message = f"{task.id}{COMMIT_PREFIX_SEPARATOR}{message}"
    body = f"{full_message}\n\n{PLAN_ITEM_TRAILER}: {item}" if item else full_message
    listed = plan_items[item].files if item and plan_items and item in plan_items else None
    outside = tuple(path for path in staged if not file_listed(path, listed)) if listed else ()
    return CommitResult(git.commit(body), full_message, outside)
