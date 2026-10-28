from dataclasses import replace

import pytest

from agentflow.constants import ActionKind, ExitCode, HistoryEvent, StepStatus, TaskEvent, TaskStatus
from agentflow.engine import next_action, resume_target, start_task, transition
from agentflow.errors import AgentflowError
from agentflow.models import Task, workflow_from_dict

AT = "2026-10-10T10:00:00Z"


@pytest.fixture
def workflow(workflow_data):
    # confirm (approval) -> build -> check (on_fail build) -> accept (approval, on_fail build); max 2 rounds.
    workflow_data["steps"].append(
        {"id": "accept", "name": "Accept", "role": "lead", "requires_approval": True, "on_fail": "build"}
    )
    return workflow_from_dict(workflow_data)


def task(step="build", step_status=StepStatus.IN_PROGRESS, status=TaskStatus.OPEN, loop_round=0):
    return Task(
        id="T-001",
        title="t",
        status=status,
        current_step=step,
        step_status=step_status,
        loop_round=loop_round,
    )


def shape(t: Task):
    return t.status, t.current_step, t.step_status, t.loop_round


def events(t: Task):
    return [(entry.step, entry.event) for entry in t.history]


def ids(action):
    return action.kind, (action.step.id if action.step else None), action.loop_round


# ------------------------------------------------------------- next_action


def test_no_task_starts_at_first_step(workflow):
    assert ids(next_action(workflow, None)) == (ActionKind.START_TASK, "confirm", None)


@pytest.mark.parametrize(
    ("status", "step_status"), [(TaskStatus.DONE, StepStatus.PASSED), (TaskStatus.CANCELLED, StepStatus.IN_PROGRESS)]
)
def test_finished_task_means_start_a_new_one(workflow, status, step_status):
    assert next_action(workflow, task(status=status, step_status=step_status)).kind is ActionKind.START_TASK


def test_in_progress_continues_with_round(workflow):
    assert ids(next_action(workflow, task())) == (ActionKind.CONTINUE, "build", 0)
    action = next_action(workflow, task(loop_round=1))
    assert ids(action) == (ActionKind.CONTINUE, "build", 1)
    assert action.max_rounds == 2


def test_awaiting_approval(workflow):
    action = next_action(workflow, task("confirm", StepStatus.AWAITING_APPROVAL))
    assert ids(action) == (ActionKind.AWAIT_APPROVAL, "confirm", None)


def test_blocked(workflow):
    action = next_action(workflow, task("check", StepStatus.FAILED, TaskStatus.BLOCKED, 2))
    assert ids(action) == (ActionKind.BLOCKED, "check", 2)


@pytest.mark.parametrize("step_status", [StepStatus.PASSED, StepStatus.FAILED])
def test_open_task_with_finished_step_status_is_invalid(workflow, step_status):
    with pytest.raises(AgentflowError) as exc:
        next_action(workflow, task(step_status=step_status))
    assert exc.value.code is ExitCode.INVALID_STATE


def test_unknown_step_is_invalid_state(workflow):
    with pytest.raises(AgentflowError) as exc:
        next_action(workflow, task("ghost"))
    assert exc.value.code is ExitCode.INVALID_STATE


# -------------------------------------------------------------- transition


def test_start_task(workflow):
    t = start_task(workflow, "T-007", "New", "feature/T-007-new", AT)
    assert shape(t) == (TaskStatus.OPEN, "confirm", StepStatus.IN_PROGRESS, 0)
    assert t.branch == "feature/T-007-new"
    assert events(t) == [("confirm", HistoryEvent.STARTED)]


def test_pass_on_approval_step_waits_for_approval(workflow):
    t = transition(workflow, task("confirm"), TaskEvent.PASS, AT)
    assert shape(t) == (TaskStatus.OPEN, "confirm", StepStatus.AWAITING_APPROVAL, 0)
    assert events(t) == [("confirm", HistoryEvent.PASSED)]


def test_approve_moves_to_next_step(workflow):
    t = transition(workflow, task("confirm", StepStatus.AWAITING_APPROVAL), TaskEvent.APPROVE, AT)
    assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, 0)
    assert events(t) == [("confirm", HistoryEvent.APPROVED), ("build", HistoryEvent.STARTED)]


def test_pass_without_approval_moves_on(workflow):
    t = transition(workflow, task("build"), TaskEvent.PASS, AT)
    assert shape(t) == (TaskStatus.OPEN, "check", StepStatus.IN_PROGRESS, 0)
    assert events(t) == [("build", HistoryEvent.PASSED), ("check", HistoryEvent.STARTED)]


def test_approving_last_step_finishes_the_task(workflow):
    t = transition(workflow, task("accept", StepStatus.AWAITING_APPROVAL), TaskEvent.APPROVE, AT)
    assert shape(t) == (TaskStatus.DONE, "accept", StepStatus.PASSED, 0)
    assert events(t)[-1] == ("accept", HistoryEvent.DONE)


def test_passing_last_step_without_approval_finishes(workflow_data):
    simple = workflow_from_dict(workflow_data)  # check is last and needs no approval
    t = transition(simple, task("check"), TaskEvent.PASS, AT)
    assert shape(t) == (TaskStatus.DONE, "check", StepStatus.PASSED, 0)


def test_fail_goes_back_to_on_fail_and_counts_rounds(workflow):
    t = transition(workflow, task("check"), TaskEvent.FAIL, AT)
    assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, 1)
    assert events(t) == [("check", HistoryEvent.FAILED), ("build", HistoryEvent.STARTED)]
    t = transition(workflow, task("accept", StepStatus.AWAITING_APPROVAL, loop_round=1), TaskEvent.FAIL, AT)
    assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, 2)


def test_fail_after_max_rounds_blocks(workflow):
    t = transition(workflow, task("check", loop_round=2), TaskEvent.FAIL, AT)
    assert shape(t) == (TaskStatus.BLOCKED, "check", StepStatus.FAILED, 2)
    assert events(t) == [("check", HistoryEvent.FAILED), ("check", HistoryEvent.BLOCKED)]


def test_fail_without_on_fail_blocks_at_once(workflow):
    t = transition(workflow, task("build"), TaskEvent.FAIL, AT)
    assert shape(t) == (TaskStatus.BLOCKED, "build", StepStatus.FAILED, 0)


def test_full_run_with_rework_until_blocked(workflow):
    t = start_task(workflow, "T-001", "t", None, AT)
    for event in (TaskEvent.PASS, TaskEvent.APPROVE, TaskEvent.PASS):  # confirm, approve, build
        t = transition(workflow, t, event, AT)
    for expected_round in (1, 2):
        t = transition(workflow, t, TaskEvent.FAIL, AT)  # check fails
        assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, expected_round)
        t = transition(workflow, t, TaskEvent.PASS, AT)  # build again
    t = transition(workflow, t, TaskEvent.FAIL, AT)
    assert shape(t) == (TaskStatus.BLOCKED, "check", StepStatus.FAILED, 2)


def test_approve_on_blocked_resumes_at_on_fail_with_rounds_reset(workflow):
    blocked = task("check", StepStatus.FAILED, TaskStatus.BLOCKED, 2)
    t = transition(workflow, blocked, TaskEvent.APPROVE, AT)
    assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, 0)
    assert events(t) == [("check", HistoryEvent.RESUMED), ("build", HistoryEvent.STARTED)]


def test_approve_on_blocked_step_without_on_fail_retries_that_step(workflow):
    blocked = task("build", StepStatus.FAILED, TaskStatus.BLOCKED)
    t = transition(workflow, blocked, TaskEvent.APPROVE, AT)
    assert shape(t) == (TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, 0)
    assert resume_target(workflow.get_step("build")) == "build"
    assert resume_target(workflow.get_step("check")) == "build"


@pytest.mark.parametrize(
    "start",
    [task(), task("check", StepStatus.FAILED, TaskStatus.BLOCKED, 2), task("confirm", StepStatus.AWAITING_APPROVAL)],
)
def test_cancel_in_flight_task(workflow, start):
    t = transition(workflow, start, TaskEvent.CANCEL, AT)
    assert t.status is TaskStatus.CANCELLED
    assert events(t)[-1] == (start.current_step, HistoryEvent.CANCELLED)


@pytest.mark.parametrize(
    ("start", "event", "message"),
    [
        (task("confirm", StepStatus.AWAITING_APPROVAL), TaskEvent.PASS, "waiting for a person to approve"),
        (task(), TaskEvent.APPROVE, "has to pass before it can be approved"),
        (task("check", StepStatus.FAILED, TaskStatus.BLOCKED, 2), TaskEvent.PASS, "is blocked"),
        (task("check", StepStatus.FAILED, TaskStatus.BLOCKED, 2), TaskEvent.FAIL, "is blocked"),
        (task("accept", StepStatus.PASSED, TaskStatus.DONE), TaskEvent.PASS, "already done"),
        (task(status=TaskStatus.CANCELLED), TaskEvent.CANCEL, "already cancelled"),
    ],
)
def test_invalid_transitions(workflow, start, event, message):
    with pytest.raises(AgentflowError) as exc:
        transition(workflow, start, event, AT)
    assert exc.value.code is ExitCode.INVALID_TRANSITION
    assert message in str(exc.value)


def test_transition_keeps_identity_fields(workflow):
    start = replace(task(), title="Keep me", branch="feature/T-001-keep")
    t = transition(workflow, start, TaskEvent.PASS, AT)
    assert (t.id, t.title, t.branch) == ("T-001", "Keep me", "feature/T-001-keep")
