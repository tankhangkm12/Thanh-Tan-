"""Task lifecycle on a real workspace: state.json through a ``StateStore``, branches through a ``GitClient``."""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from agentflow.checklist import ChecklistWriter
from agentflow.constants import (
    BRANCH_SEPARATOR,
    DECISIONS_DIR,
    IN_FLIGHT_TASK_STATUSES,
    MARKDOWN_SUFFIX,
    REPORTS_DIR,
    SLUG_FALLBACK,
    SLUG_MAX_LENGTH,
    TASK_BASE_BRANCH,
    TASK_ID_DIGITS,
    TASK_ID_PREFIX,
    TASKS_DIR,
    ExitCode,
    StepStatus,
    TaskEvent,
    TaskStatus,
    TaskType,
)
from agentflow.engine import resume_target, start_task, transition
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.interfaces import GateRunner, GitClient, StateStore
from agentflow.models import State, Task, Workflow
from agentflow.render import NONE_TEXT, describe_step
from agentflow.seal import TaskSealer, require_sealed

Clock = Callable[[], str]

_SLUG_SEPARATOR = "-"
_NOT_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
# NFKD does not decompose the Vietnamese letter đ, so map it by hand.
_UNDECOMPOSABLE = str.maketrans({"đ": "d", "Đ": "D"})
_TIMESTAMP_UNSAFE = re.compile(r"[^0-9A-Za-z]")
_CRLF = "\r\n"
_LF = "\n"
OVERRIDE_FILE_SUFFIX = "-override"
NO_REASON_TEXT = "not given"


@dataclass(frozen=True)
class ApproveResult:
    task: Task
    # Written when the approval overrode a blocked task.
    decision_file: Path | None = None


# ------------------------------------------------------------------ naming


def slugify(title: str) -> str:
    """ASCII, lower-case, dash-separated, at most ``SLUG_MAX_LENGTH`` characters, cut at a word boundary."""
    decomposed = unicodedata.normalize("NFKD", title.translate(_UNDECOMPOSABLE))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
    slug = _NOT_SLUG_CHARS.sub(_SLUG_SEPARATOR, ascii_text).strip(_SLUG_SEPARATOR)
    if len(slug) > SLUG_MAX_LENGTH:
        cut = slug[:SLUG_MAX_LENGTH]
        if slug[SLUG_MAX_LENGTH] != _SLUG_SEPARATOR and _SLUG_SEPARATOR in cut:
            cut = cut.rsplit(_SLUG_SEPARATOR, 1)[0]
        slug = cut.strip(_SLUG_SEPARATOR)
    return slug or SLUG_FALLBACK


def next_task_id(state: State) -> str:
    numbers = [int(task.id.removeprefix(TASK_ID_PREFIX)) for task in state.tasks]
    return f"{TASK_ID_PREFIX}{max(numbers, default=0) + 1:0{TASK_ID_DIGITS}d}"


def branch_name(task_type: TaskType, task_id: str, title: str) -> str:
    return f"{task_type}{BRANCH_SEPARATOR}{task_id}{_SLUG_SEPARATOR}{slugify(title)}"


# --------------------------------------------------------------- lifecycle


def new_task(
    store: StateStore,
    workflow: Workflow,
    git: GitClient,
    title: str,
    task_type: TaskType,
    clock: Clock,
    size: str | None = None,
    roadmap: str | None = None,
) -> Task:
    """Create the task's gitflow branch from its base, switch to it, and record the task as active."""
    title = title.strip()
    if not title:
        raise AgentflowError("the task title is empty", ExitCode.INVALID_INPUT)
    size = resolve_size(workflow, size)
    state = store.load()
    in_flight = [task for task in state.tasks if task.status in IN_FLIGHT_TASK_STATUSES]
    if in_flight:
        listing = ", ".join(f"{task.id} ({task.status})" for task in in_flight)
        raise AgentflowError(
            f"finish or cancel the current task first: {listing}", ExitCode.TASK_CONFLICT
        )
    require_sealed(state, git)
    if not git.is_clean():
        raise AgentflowError(
            "the working tree has uncommitted or untracked changes; commit, stash or remove them first",
            ExitCode.DIRTY_WORKING_TREE,
        )
    base = TASK_BASE_BRANCH[task_type]
    if not git.branch_exists(base):
        raise AgentflowError(
            f"base branch '{base}' for a {task_type} task does not exist locally", ExitCode.BRANCH_PROBLEM
        )
    task_id = next_task_id(state)
    branch = branch_name(task_type, task_id, title)
    if git.branch_exists(branch):
        raise AgentflowError(f"branch '{branch}' already exists", ExitCode.BRANCH_PROBLEM)

    git.create_branch(branch, base)
    task = start_task(workflow, task_id, title, branch, clock(), size, roadmap, str(task_type))
    store.save(replace(state, active_task_id=task.id, tasks=(*state.tasks, task)))
    return task


def resolve_size(workflow: Workflow, size: str | None) -> str | None:
    """The size a new task gets: the one asked for, else the workflow's default; ``None`` when the workflow has no sizes."""
    if not workflow.sizes:
        if size is not None:
            raise AgentflowError(f"this workflow has no task sizes, so --size {size} cannot be used", ExitCode.INVALID_INPUT)
        return None
    chosen = size or workflow.default_size
    if workflow.size_profile(chosen) is None:
        known = ", ".join(profile.id for profile in workflow.sizes)
        raise AgentflowError(f"unknown size '{chosen}' (this workflow has: {known})", ExitCode.INVALID_INPUT)
    return chosen


def advance_task(
    store: StateStore,
    workflow: Workflow,
    result: TaskEvent,
    clock: Clock,
    gates: GateRunner | None = None,
    sealer: TaskSealer | None = None,
    checklists: ChecklistWriter | None = None,
) -> Task:
    """Record that the active task's current step passed or failed; a pass must clear the step's gates.

    A pass into ``awaiting_approval`` writes the step's approval checklist first; if that fails the state is not changed.

    A pass of a last step that needs no approval finishes the task, so it seals it like an approval would.
    """
    return _apply(store, workflow, result, clock, gates, _sealing(sealer), _checklist_writing(workflow, checklists))[1]


def cancel_task(store: StateStore, workflow: Workflow, clock: Clock) -> Task:
    return _apply(store, workflow, TaskEvent.CANCEL, clock)[1]


def approve_task(
    store: StateStore,
    workflow: Workflow,
    workspace_dir: Path,
    clock: Clock,
    reason: str | None = None,
    sealer: TaskSealer | None = None,
) -> ApproveResult:
    """Approve the step awaiting approval, or override a blocked task (recorded in ``decisions/``).

    Approving the last step seals the task first (summary and approval tag); if that fails nothing changes.
    """
    before, after = _apply(store, workflow, TaskEvent.APPROVE, clock, before_save=_sealing(sealer))
    if before.status is not TaskStatus.BLOCKED:
        return ApproveResult(after)
    return ApproveResult(after, write_override_decision(workspace_dir, workflow, before, after, reason))


def write_override_decision(
    workspace_dir: Path, workflow: Workflow, blocked: Task, resumed: Task, reason: str | None
) -> Path:
    at = resumed.history[-1].at
    path = (
        workspace_dir
        / DECISIONS_DIR
        / f"{blocked.id}{_SLUG_SEPARATOR}{_TIMESTAMP_UNSAFE.sub('', at)}{OVERRIDE_FILE_SUFFIX}{MARKDOWN_SUFFIX}"
    )
    blocked_step = workflow.get_step(blocked.current_step)
    assert blocked_step is not None
    lines = [
        f"# {blocked.id}: blocked task resumed by a person",
        "",
        f"- Task: {blocked.id} {blocked.title}",
        f"- Branch: {blocked.branch or NONE_TEXT}",
        f"- Blocked at: {describe_step(blocked_step)}, after {blocked.loop_round}/{workflow.max_rounds} rework rounds",
        f"- Resumed at: step '{resume_target(blocked_step)}', rework rounds reset to 0",
        f"- Time: {at}",
        f"- Reason: {reason.strip() if reason and reason.strip() else NO_REASON_TEXT}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, "\n".join(lines) + "\n")
    return path


def write_report(workspace_dir: Path, workflow: Workflow, task: Task, step_id: str, content: str) -> Path:
    """Store a step's report at ``tasks/<task id>/reports/<step id>.md``, replacing an earlier one.

    Only the current step of an open task can be reported on, and only while it is in progress: once a step
    has passed (or waits for approval) its report is what the person approved and stays as it is.
    """
    if workflow.get_step(step_id) is None:
        known = ", ".join(step.id for step in workflow.steps)
        raise AgentflowError(f"unknown step '{step_id}' (steps: {known})", ExitCode.UNKNOWN_STEP)
    if task.status is not TaskStatus.OPEN:
        raise AgentflowError(f"{task.id} is {task.status}: no report can be written", ExitCode.REPORT_REFUSED)
    if step_id != task.current_step:
        raise AgentflowError(
            f"a report can only be written for the current step '{task.current_step}', not '{step_id}'",
            ExitCode.REPORT_REFUSED,
        )
    if task.step_status is not StepStatus.IN_PROGRESS:
        raise AgentflowError(
            f"step '{step_id}' is {task.step_status}: its report is final and cannot be overwritten",
            ExitCode.REPORT_REFUSED,
        )
    if not content.strip():
        raise AgentflowError("the report is empty", ExitCode.INVALID_INPUT)
    path = workspace_dir / TASKS_DIR / task.id / REPORTS_DIR / f"{step_id}{MARKDOWN_SUFFIX}"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content.replace(_CRLF, _LF)
    write_text_atomic(path, text if text.endswith(_LF) else text + _LF)
    return path


def require_active_task(state: State) -> Task:
    task = state.active_task()
    if task is None:
        raise AgentflowError(
            "no active task (start one with `agentflow task new`)", ExitCode.NO_ACTIVE_TASK
        )
    return task


# ----------------------------------------------------------------- helpers


def seal_finished_task(
    store: StateStore, sealer: TaskSealer, task_id: str, commit: str | None = None
) -> Path:
    """For a person: write the summary and approval tag of a finished task that has none."""
    task = next((t for t in store.load().tasks if t.id == task_id), None)
    if task is None or task.status is not TaskStatus.DONE:
        raise AgentflowError(f"{task_id} is not a finished task", ExitCode.INVALID_INPUT)
    return sealer.seal(task, commit)


def _sealing(sealer: TaskSealer | None) -> Callable[[Task, Task], None] | None:
    if sealer is None:
        return None

    def seal(_before: Task, after: Task) -> None:
        sealer.seal(after)

    return seal


def _checklist_writing(workflow: Workflow, writer: ChecklistWriter | None) -> Callable[[Task, Task], None] | None:
    if writer is None:
        return None

    def write(before: Task, after: Task) -> None:
        if after.status is TaskStatus.OPEN and after.step_status is StepStatus.AWAITING_APPROVAL:
            writer.write(workflow, after)

    return write


def _apply(
    store: StateStore,
    workflow: Workflow,
    event: TaskEvent,
    clock: Clock,
    gates: GateRunner | None = None,
    before_save: Callable[[Task, Task], None] | None = None,
    after_transition: Callable[[Task, Task], None] | None = None,
) -> tuple[Task, Task]:
    state = store.load()
    before = require_active_task(state)
    if event is TaskEvent.PASS and gates is not None:
        _require_gates(workflow, before, gates)
    after = transition(workflow, before, event, clock())
    if after_transition is not None:
        after_transition(before, after)
    if before_save is not None and after.status is TaskStatus.DONE:
        before_save(before, after)
    tasks = tuple(after if task.id == before.id else task for task in state.tasks)
    active = after.id if after.status in IN_FLIGHT_TASK_STATUSES else None
    store.save(replace(state, active_task_id=active, tasks=tasks))
    return before, after


def _require_gates(workflow: Workflow, task: Task, gates: GateRunner) -> None:
    step = workflow.get_step(task.current_step)
    if step is None or task.step_status is not StepStatus.IN_PROGRESS:
        return  # `transition` reports these
    problems = gates.problems(task, step)
    if problems:
        listing = "\n  - ".join(problems)
        raise AgentflowError(f"step '{step.id}' cannot pass yet:\n  - {listing}", ExitCode.GATE_FAILED)
