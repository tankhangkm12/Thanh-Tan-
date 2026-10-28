"""What agentflow does when a CLI fires a hook.

Hooks must never get in the way: a project without ``.agentflow/``, unreadable input or an unreadable
state all end in "no output", which every CLI treats as "carry on".
"""

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from agentflow.constants import (
    ANTIGRAVITY_FIRST_INVOCATION,
    CliKind,
    IN_FLIGHT_TASK_STATUSES,
    HistoryEvent,
    HookEvent,
    ReplyKind,
    StepStatus,
    TaskStatus,
)
from agentflow import audit, gitconfig
from agentflow.engine import next_action
from agentflow.gates import plan_report_path
from agentflow.errors import AgentflowError
from agentflow.guard import evaluate, writes_into_workspace
from agentflow.hook_adapters import ADAPTERS
from agentflow.interfaces import BranchLookup, WorkspaceLookup
from agentflow.projectlocator import remember_project
from agentflow.models import HookInput, HookReply, State, Task, Workflow
from agentflow.render import NONE_TEXT, describe_action, describe_step
from agentflow.state import JsonStateStore
from agentflow.workspace import GitWorkspaceLookup, WorkspacePaths, find_workspace, load_config, load_workspace_workflow

RULES_TEXT = (
    "Rules: change task state only through `agentflow task ...`; save step reports with "
    "the `report_write` tool (or `agentflow report --step <id>`); commit with `agentflow commit`; never edit files under .agentflow/ "
    "by hand (the file tools are blocked there too); never push."
)
NO_TASK_TEXT = "No active task. To begin, use the start skill (it runs `agentflow task new`)."
STOP_REMINDER = (
    "agentflow: task {task} is still at step '{step}'. If that step is finished, record it with "
    "`agentflow task advance --result pass|fail` (and `agentflow report --step {step}`); "
    "if it is waiting for you, use `agentflow task approve`."
)


def handle_hook(
    event: HookEvent, cli: CliKind, stdin_text: str, branches: BranchLookup, workspaces: WorkspaceLookup | None = None
) -> str:
    """Return the text to print on stdout (possibly empty)."""
    adapter = ADAPTERS[cli]
    payload = _parse(stdin_text)
    if payload is None:
        return ""
    hook_input = adapter.read(event, payload)
    paths = _workspace(hook_input.cwd)
    if paths is None:
        return ""
    if cli is CliKind.ANTIGRAVITY:
        # Its MCP servers start in the plugin directory and cannot see the project; leave them a pointer.
        remember_project(paths.root)
    reply = _reply(event, cli, hook_input, paths, branches, workspaces or GitWorkspaceLookup())
    return adapter.render(event, reply)


def _parse(text: str) -> Mapping[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _workspace(cwd: Path | None) -> WorkspacePaths | None:
    if cwd is None:
        return None
    try:
        return find_workspace(cwd)
    except AgentflowError:  # not a git repository, or no .agentflow/ in it
        return None


def _reply(
    event: HookEvent,
    cli: CliKind,
    hook_input: HookInput,
    paths: WorkspacePaths,
    branches: BranchLookup,
    workspaces: WorkspaceLookup,
) -> HookReply:
    match event:
        case HookEvent.PRE_TOOL:
            return _audited(paths, cli, hook_input, _guard_reply(hook_input, branches, workspaces, protected_branches(paths)))
        case HookEvent.SESSION_START:
            if cli is CliKind.ANTIGRAVITY and hook_input.invocation_num != ANTIGRAVITY_FIRST_INVOCATION:
                return HookReply()
            return _loaded(paths, _summary)
        case HookEvent.STOP:
            if hook_input.stop_hook_active:
                return HookReply()
            return _loaded(paths, lambda workflow, state: _reminder(paths, state), kind=ReplyKind.REMINDER)
    return HookReply()


def _audited(paths: WorkspacePaths, cli: CliKind, hook_input: HookInput, reply: HookReply) -> HookReply:
    """Log the call when it names a protected file; the reply is returned as it was."""
    if hook_input.write_target is not None:
        kind, target = audit.WRITE_KIND, str(hook_input.write_target)
    elif hook_input.command:
        kind, target = audit.SHELL_KIND, hook_input.command
    else:
        return reply
    decision = {ReplyKind.DENY: "deny", ReplyKind.ASK: "ask"}.get(reply.kind, audit.ALLOW)
    audit.record(paths.dir, str(cli), hook_input.tool, kind, target, decision)
    return reply


def protected_branches(paths: WorkspacePaths) -> frozenset[str]:
    """The branches an agent must not commit on: main and develop, the ones the project named (``git.*`` settings) and the
    base of every open task. A workspace that cannot be read gives the built-in two (the hook must never get in the way)."""
    try:
        names = gitconfig.names_from(load_config(paths).settings)
        state = JsonStateStore(paths.dir, load_workspace_workflow(paths)).load()
        bases = [task.base for task in state.tasks if task.status in IN_FLIGHT_TASK_STATUSES]
    except AgentflowError:
        return gitconfig.GitNames().protected()
    return names.protected(bases)


def _guard_reply(
    hook_input: HookInput, branches: BranchLookup, workspaces: WorkspaceLookup, protected: frozenset[str] | None = None
) -> HookReply:
    if hook_input.cwd is None:
        return HookReply()
    if hook_input.write_target is not None:
        verdict = writes_into_workspace(hook_input.write_target, hook_input.cwd)
    elif hook_input.command:
        verdict = evaluate(hook_input.command, hook_input.cwd, branches, workspaces, protected_branches=protected)
    else:
        return HookReply()
    if verdict.denied:
        return HookReply(ReplyKind.DENY, verdict.reason or "")
    if verdict.asks:
        return HookReply(ReplyKind.ASK, verdict.reason or "")
    return HookReply()


def _loaded(paths: WorkspacePaths, build, kind: ReplyKind = ReplyKind.CONTEXT) -> HookReply:
    """Load workflow and state, then let ``build`` write the text; any agentflow error means no reply."""
    try:
        workflow = load_workspace_workflow(paths)
        state = JsonStateStore(paths.dir, workflow).load()
    except AgentflowError:
        return HookReply()
    text = build(workflow, state)
    return HookReply(kind, text) if text else HookReply()


def _summary(workflow: Workflow, state: State) -> str:
    task = state.active_task()
    lines = [f"agentflow workspace found (workflow: {workflow.family})."]
    if task is None:
        lines.append(NO_TASK_TEXT)
    else:
        step = workflow.get_step(task.current_step)
        lines += [
            f"Active task: {task.id} {task.title} (branch {task.branch or NONE_TEXT}, status {task.status}).",
            f"Current step: {describe_step(step) if step else task.current_step}, {task.step_status}.",
            f"Next: {describe_action(next_action(workflow, task))}.",
        ]
    lines.append(RULES_TEXT)
    return "\n".join(lines)


def _reminder(paths: WorkspacePaths, state: State) -> str:
    """Only while a step is in progress and its report was saved after the step began (it looks finished)."""
    task = state.active_task()
    if task is None or task.status is not TaskStatus.OPEN or task.step_status is not StepStatus.IN_PROGRESS:
        return ""
    if not _report_saved_since_step_began(paths, task):
        return ""
    return STOP_REMINDER.format(task=task.id, step=task.current_step)


def _report_saved_since_step_began(paths: WorkspacePaths, task: Task) -> bool:
    report = plan_report_path(paths.dir, task.id, task.current_step)
    started = [e for e in task.history if e.step == task.current_step and e.event is HistoryEvent.STARTED]
    if not report.is_file() or not started:
        return False
    began = datetime.fromisoformat(started[-1].at.replace("Z", "+00:00"))
    return report.stat().st_mtime >= began.timestamp()
