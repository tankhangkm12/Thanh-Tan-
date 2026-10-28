"""The task lifecycle as pure functions of the workflow and the task: no I/O, no clock.

A task is always in one of these shapes, and only ``transition`` moves it between them:

- open, step in progress: the step's role is working on it;
- open, step awaiting approval: the step passed and a person has to approve it;
- blocked, step failed: out of rounds, or failed where the workflow has no way back;
- done (last step passed) or cancelled.
"""

from dataclasses import replace

from thanhtan.constants import (
    IN_FLIGHT_TASK_STATUSES,
    ActionKind,
    ExitCode,
    HistoryEvent,
    StepStatus,
    TaskEvent,
    TaskStatus,
)
from thanhtan.errors import ThanhTanError
from thanhtan.models import HistoryEntry, NextAction, Step, Task, Workflow

_FINISHED = frozenset({TaskStatus.DONE, TaskStatus.CANCELLED})


def next_action(workflow: Workflow, task: Task | None) -> NextAction:
    if task is None or task.status in _FINISHED:
        return NextAction(ActionKind.START_TASK, workflow.first_step())
    step = _current_step(workflow, task)
    if task.status is TaskStatus.BLOCKED:
        return NextAction(ActionKind.BLOCKED, step, task.loop_round, workflow.max_rounds)
    match task.step_status:
        case StepStatus.IN_PROGRESS:
            return NextAction(ActionKind.CONTINUE, step, task.loop_round, workflow.max_rounds)
        case StepStatus.AWAITING_APPROVAL:
            return NextAction(ActionKind.AWAIT_APPROVAL, step)
    raise ThanhTanError(
        f"task {task.id} is {task.status} with step status {task.step_status}, which thanhtan never writes",
        ExitCode.INVALID_STATE,
    )


def start_task(
    workflow: Workflow,
    task_id: str,
    title: str,
    branch: str | None,
    at: str,
    size: str | None = None,
    roadmap: str | None = None,
    task_type: str | None = None,
    base: str | None = None,
) -> Task:
    first = workflow.first_step()
    return Task(
        id=task_id,
        title=title,
        status=TaskStatus.OPEN,
        current_step=first.id,
        step_status=StepStatus.IN_PROGRESS,
        branch=branch,
        history=(HistoryEntry(at, first.id, HistoryEvent.STARTED),),
        size=size,
        roadmap=roadmap,
        type=task_type,
        base=base,
    )


def transition(workflow: Workflow, task: Task, event: TaskEvent, at: str) -> Task:
    """Apply ``event`` to ``task``; raise ``INVALID_TRANSITION`` when the task is not in a shape that allows it."""
    step = _current_step(workflow, task)
    if task.status in _FINISHED:
        raise _invalid(f"task {task.id} is already {task.status}")
    match event:
        case TaskEvent.PASS:
            _require_working(task, step, {StepStatus.IN_PROGRESS})
            passed = _log(task, at, step.id, HistoryEvent.PASSED)
            if needs_approval(workflow, task, step):
                return replace(passed, step_status=StepStatus.AWAITING_APPROVAL)
            return _move_on(workflow, passed, step, at)
        case TaskEvent.APPROVE:
            if task.status is TaskStatus.BLOCKED:
                return _resume(task, step, at)
            _require_working(task, step, {StepStatus.AWAITING_APPROVAL})
            return _move_on(workflow, _log(task, at, step.id, HistoryEvent.APPROVED), step, at)
        case TaskEvent.FAIL:
            _require_working(task, step, {StepStatus.IN_PROGRESS, StepStatus.AWAITING_APPROVAL})
            return _fail(workflow, _log(task, at, step.id, HistoryEvent.FAILED), step, at)
        case TaskEvent.CANCEL:
            assert task.status in IN_FLIGHT_TASK_STATUSES
            return replace(_log(task, at, step.id, HistoryEvent.CANCELLED), status=TaskStatus.CANCELLED)
    raise AssertionError(event)  # unreachable: TaskEvent is exhaustive


def needs_approval(workflow: Workflow, task: Task, step: Step) -> bool:
    """Whether a person has to approve ``step``: the workflow says so, unless the task's size drops that approval."""
    profile = workflow.size_profile(task.size)
    return step.requires_approval and not (profile is not None and step.id in profile.skip_approval)


def resume_target(step: Step) -> str:
    """Where a blocked task restarts when a person overrides the block."""
    return step.on_fail or step.id


# ----------------------------------------------------------------- helpers


def _current_step(workflow: Workflow, task: Task) -> Step:
    step = workflow.get_step(task.current_step)
    if step is None:
        raise ThanhTanError(
            f"task {task.id} is at step '{task.current_step}', which the workflow does not define",
            ExitCode.INVALID_STATE,
        )
    return step


def _require_working(task: Task, step: Step, allowed: set[StepStatus]) -> None:
    if task.status is TaskStatus.BLOCKED:
        raise _invalid(
            f"task {task.id} is blocked at step '{step.id}': a person has to approve it to resume, or cancel it"
        )
    if task.step_status in allowed:
        return
    if task.step_status is StepStatus.AWAITING_APPROVAL:
        raise _invalid(f"step '{step.id}' is waiting for a person to approve it (or to fail it)")
    raise _invalid(f"step '{step.id}' is {task.step_status}; it has to pass before it can be approved")


def _move_on(workflow: Workflow, task: Task, step: Step, at: str) -> Task:
    following = workflow.step_after(step.id)
    if following is None:
        done = _log(task, at, step.id, HistoryEvent.DONE)
        return replace(done, status=TaskStatus.DONE, step_status=StepStatus.PASSED)
    return _enter(task, following.id, at)


def _fail(workflow: Workflow, task: Task, step: Step, at: str) -> Task:
    if step.on_fail is not None and task.loop_round < workflow.max_rounds:
        return replace(_enter(task, step.on_fail, at), loop_round=task.loop_round + 1)
    blocked = _log(task, at, step.id, HistoryEvent.BLOCKED)
    return replace(blocked, status=TaskStatus.BLOCKED, step_status=StepStatus.FAILED)


def _resume(task: Task, step: Step, at: str) -> Task:
    resumed = _log(task, at, step.id, HistoryEvent.RESUMED)
    return replace(_enter(resumed, resume_target(step), at), status=TaskStatus.OPEN, loop_round=0)


def _enter(task: Task, step_id: str, at: str) -> Task:
    started = _log(task, at, step_id, HistoryEvent.STARTED)
    return replace(started, current_step=step_id, step_status=StepStatus.IN_PROGRESS)


def _log(task: Task, at: str, step_id: str, event: HistoryEvent) -> Task:
    return replace(task, history=(*task.history, HistoryEntry(at, step_id, event)))


def _invalid(message: str) -> ThanhTanError:
    return ThanhTanError(message, ExitCode.INVALID_TRANSITION)
