"""Human-readable text for steps and next actions, shared by STATE.md, the CLI and hooks."""

from agentflow.constants import ActionKind
from agentflow.models import NextAction, Step

NONE_TEXT = "none"
APPROVAL_NOTE = ", needs approval"
ROUND_TEXT = ", rework round {round}/{max_rounds}"

_ACTION_TEXT = {
    ActionKind.START_TASK: "start a new task at {step}",
    ActionKind.CONTINUE: "work on {step}{rounds}",
    ActionKind.AWAIT_APPROVAL: "wait for a person to approve {step}",
    ActionKind.BLOCKED: "blocked at {step} after {round}/{max_rounds} rework rounds: "
    "a person has to approve to resume, or cancel the task",
}


def describe_step(step: Step) -> str:
    approval = APPROVAL_NOTE if step.requires_approval else ""
    return f"step '{step.id}' ({step.name}; role {step.role}{approval})"


def describe_action(action: NextAction) -> str:
    rounds = ROUND_TEXT.format(round=action.loop_round, max_rounds=action.max_rounds) if action.loop_round else ""
    return _ACTION_TEXT[action.kind].format(
        step=describe_step(action.step) if action.step else NONE_TEXT,
        rounds=rounds,
        round=action.loop_round,
        max_rounds=action.max_rounds,
    )
