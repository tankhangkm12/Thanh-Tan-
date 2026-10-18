"""Typed data shared by every agentflow module.

The ``*_from_dict`` helpers expect data that already passed schema validation;
they only map plain JSON/YAML values onto the dataclasses.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agentflow.constants import (
    INSTALL_URLS,
    SCHEMA_VERSION,
    ActionKind,
    ApprovalItem,
    ConfigKey,
    GateKind,
    GuardDecision,
    GuardRule,
    SizeKey,
    HistoryEvent,
    ReplyKind,
    StateKey,
    StepStatus,
    TaskStatus,
    Tool,
    ToolStatus,
    WorkflowKey,
)

# ---------------------------------------------------------------- workflow


@dataclass(frozen=True)
class Step:
    id: str
    name: str
    role: str
    requires_approval: bool = False
    # An earlier step to go back to when this step fails.
    on_fail: str | None = None
    gates: tuple[GateKind, ...] = ()
    # What a person ticks before approving this step: fixed questions, and where the dynamic lines come from.
    approval_checklist: tuple[str, ...] = ()
    approval_items: tuple[ApprovalItem, ...] = ()

    @property
    def has_checklist(self) -> bool:
        return bool(self.approval_checklist or self.approval_items)


@dataclass(frozen=True)
class SizeProfile:
    """A task size: how a task of this size differs from the full workflow."""

    id: str
    # Steps that need no approval for this size.
    skip_approval: tuple[str, ...] = ()
    max_plan_items: int | None = None
    # Step id -> ids of the scan tools that step runs; a step not listed runs them all.
    scans: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Workflow:
    schema_version: int
    family: str
    # How many times one task may go back through ``on_fail`` before it is blocked.
    max_rounds: int
    steps: tuple[Step, ...]
    # Roles with one agent per plan-item tier; every other role has a single agent.
    tiered_roles: tuple[str, ...] = ()
    sizes: tuple[SizeProfile, ...] = ()
    default_size: str | None = None
    # Roles that only read: a project may grant them read-only tools and nothing else.
    read_only_roles: tuple[str, ...] = ()
    # CLI -> folder (relative to the workflow file) holding that CLI's generated agent files.
    agent_dirs: Mapping[str, str] = field(default_factory=dict)

    def size_profile(self, size: str | None) -> SizeProfile | None:
        return next((profile for profile in self.sizes if profile.id == size), None) if size else None

    def get_step(self, step_id: str) -> Step | None:
        return next((step for step in self.steps if step.id == step_id), None)

    def first_step(self) -> Step:
        return self.steps[0]

    def step_after(self, step_id: str) -> Step | None:
        """The step that follows ``step_id``, or ``None`` when it is the last one."""
        ids = [step.id for step in self.steps]
        position = ids.index(step_id)
        return self.steps[position + 1] if position + 1 < len(self.steps) else None


def workflow_from_dict(data: Mapping[str, Any]) -> Workflow:
    return Workflow(
        schema_version=data[WorkflowKey.SCHEMA_VERSION],
        family=data[WorkflowKey.FAMILY],
        max_rounds=data[WorkflowKey.MAX_ROUNDS],
        steps=tuple(_step_from_dict(item) for item in data[WorkflowKey.STEPS]),
        tiered_roles=tuple(data.get(WorkflowKey.TIERED_ROLES, ())),
        sizes=tuple(_size_from_dict(name, item) for name, item in data.get(WorkflowKey.SIZES, {}).get(SizeKey.PROFILES, {}).items()),
        default_size=data.get(WorkflowKey.SIZES, {}).get(SizeKey.DEFAULT),
        read_only_roles=tuple(data.get(WorkflowKey.READ_ONLY_ROLES, ())),
        agent_dirs=dict(data.get(WorkflowKey.AGENT_DIRS, {})),
    )


def _size_from_dict(name: str, data: Mapping[str, Any]) -> SizeProfile:
    return SizeProfile(
        id=name,
        skip_approval=tuple(data.get(SizeKey.SKIP_APPROVAL, ())),
        max_plan_items=data.get(SizeKey.MAX_PLAN_ITEMS),
        scans={step: tuple(tools) for step, tools in data.get(SizeKey.SCANS, {}).items()},
    )


def _step_from_dict(data: Mapping[str, Any]) -> Step:
    return Step(
        id=data[WorkflowKey.ID],
        name=data[WorkflowKey.NAME],
        role=data[WorkflowKey.ROLE],
        requires_approval=data.get(WorkflowKey.REQUIRES_APPROVAL, False),
        on_fail=data.get(WorkflowKey.ON_FAIL),
        gates=tuple(GateKind(item) for item in data.get(WorkflowKey.GATES, ())),
        approval_checklist=tuple(data.get(WorkflowKey.APPROVAL_CHECKLIST, ())),
        approval_items=tuple(ApprovalItem(item) for item in data.get(WorkflowKey.APPROVAL_ITEMS, ())),
    )


# ------------------------------------------------------------------- state


@dataclass(frozen=True)
class HistoryEntry:
    at: str
    step: str
    event: HistoryEvent


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: TaskStatus
    current_step: str
    step_status: StepStatus
    loop_round: int = 0
    branch: str | None = None
    history: tuple[HistoryEntry, ...] = ()
    # The workflow size the task was started with; ``None`` when the workflow has no sizes.
    size: str | None = None
    # The roadmap item (R3) the task serves; ``None`` when it is not tied to one.
    roadmap: str | None = None
    # When a person confirmed the replan of this finished task (``agentflow replan done``); ``None`` until then.
    replanned_at: str | None = None


@dataclass(frozen=True)
class FileChange:
    """One file a task changed, as git reports it: ``status`` is A (added), M (modified), D (deleted) or R (renamed)."""

    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True)
class State:
    schema_version: int = SCHEMA_VERSION
    updated_at: str | None = None
    active_task_id: str | None = None
    tasks: tuple[Task, ...] = ()

    def active_task(self) -> Task | None:
        if self.active_task_id is None:
            return None
        return next((task for task in self.tasks if task.id == self.active_task_id), None)

    def stamped(self, updated_at: str) -> "State":
        return replace(self, updated_at=updated_at)


def state_from_dict(data: Mapping[str, Any]) -> State:
    return State(
        schema_version=data[StateKey.SCHEMA_VERSION],
        updated_at=data[StateKey.UPDATED_AT],
        active_task_id=data[StateKey.ACTIVE_TASK_ID],
        tasks=tuple(_task_from_dict(item) for item in data[StateKey.TASKS]),
    )


def _task_from_dict(data: Mapping[str, Any]) -> Task:
    return Task(
        id=data[StateKey.ID],
        title=data[StateKey.TITLE],
        status=TaskStatus(data[StateKey.STATUS]),
        current_step=data[StateKey.CURRENT_STEP],
        step_status=StepStatus(data[StateKey.STEP_STATUS]),
        loop_round=data[StateKey.LOOP_ROUND],
        branch=data[StateKey.BRANCH],
        size=data.get(StateKey.SIZE),
        roadmap=data.get(StateKey.ROADMAP),
        replanned_at=data.get(StateKey.REPLANNED_AT),
        history=tuple(
            HistoryEntry(
                at=entry[StateKey.AT],
                step=entry[StateKey.STEP],
                event=HistoryEvent(entry[StateKey.EVENT]),
            )
            for entry in data[StateKey.HISTORY]
        ),
    )


def state_to_dict(state: State) -> dict[str, Any]:
    return {
        StateKey.SCHEMA_VERSION: state.schema_version,
        StateKey.UPDATED_AT: state.updated_at,
        StateKey.ACTIVE_TASK_ID: state.active_task_id,
        StateKey.TASKS: [_task_to_dict(task) for task in state.tasks],
    }


def _task_to_dict(task: Task) -> dict[str, Any]:
    data = {
        StateKey.ID: task.id,
        StateKey.TITLE: task.title,
        StateKey.STATUS: task.status,
        StateKey.CURRENT_STEP: task.current_step,
        StateKey.STEP_STATUS: task.step_status,
        StateKey.LOOP_ROUND: task.loop_round,
        StateKey.BRANCH: task.branch,
        StateKey.HISTORY: [
            {StateKey.AT: entry.at, StateKey.STEP: entry.step, StateKey.EVENT: entry.event}
            for entry in task.history
        ],
    }
    if task.size is not None:
        data[StateKey.SIZE] = task.size
    if task.roadmap is not None:
        data[StateKey.ROADMAP] = task.roadmap
    if task.replanned_at is not None:
        data[StateKey.REPLANNED_AT] = task.replanned_at
    return data


# ------------------------------------------------------------------ config


@dataclass(frozen=True)
class WorkflowRef:
    """Where the workspace's workflow copy came from, and the sha256 it had when copied."""

    family: str
    source_path: str
    sha256: str


@dataclass(frozen=True)
class ExtensionRef:
    """An extension registered in the workspace: where its copy came from and the sha256 it had."""

    name: str
    source_path: str
    sha256: str


@dataclass(frozen=True)
class WorkspaceConfig:
    workflow: WorkflowRef
    schema_version: int = SCHEMA_VERSION
    extensions: tuple[ExtensionRef, ...] = ()
    # Project settings that extensions read (``agentflow config get/set``), keyed by each extension's settings key.
    settings: Mapping[str, Any] = field(default_factory=dict)
    # Tools a person granted a role for this project: role -> MCP tool names or patterns.
    role_grants: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def config_from_dict(data: Mapping[str, Any]) -> WorkspaceConfig:
    ref = data[ConfigKey.WORKFLOW]
    return WorkspaceConfig(
        schema_version=data[ConfigKey.SCHEMA_VERSION],
        workflow=WorkflowRef(
            family=ref[ConfigKey.FAMILY],
            source_path=ref[ConfigKey.SOURCE_PATH],
            sha256=ref[ConfigKey.SHA256],
        ),
        extensions=tuple(
            ExtensionRef(item[ConfigKey.NAME], item[ConfigKey.SOURCE_PATH], item[ConfigKey.SHA256])
            for item in data.get(ConfigKey.EXTENSIONS, ())
        ),
        settings=data.get(ConfigKey.SETTINGS, {}),
        role_grants={role: tuple(tools) for role, tools in data.get(ConfigKey.ROLE_GRANTS, {}).items()},
    )


def config_to_dict(config: WorkspaceConfig) -> dict[str, Any]:
    # Plain str keys/values so yaml.safe_dump can serialise them.
    data: dict[str, Any] = {
        str(ConfigKey.SCHEMA_VERSION): config.schema_version,
        str(ConfigKey.WORKFLOW): {
            str(ConfigKey.FAMILY): config.workflow.family,
            str(ConfigKey.SOURCE_PATH): config.workflow.source_path,
            str(ConfigKey.SHA256): config.workflow.sha256,
        },
    }
    if config.extensions:
        data[str(ConfigKey.EXTENSIONS)] = [
            {
                str(ConfigKey.NAME): ref.name,
                str(ConfigKey.SOURCE_PATH): ref.source_path,
                str(ConfigKey.SHA256): ref.sha256,
            }
            for ref in config.extensions
        ]
    if config.settings:
        data[str(ConfigKey.SETTINGS)] = config.settings
    if config.role_grants:
        data[str(ConfigKey.ROLE_GRANTS)] = {role: list(tools) for role, tools in config.role_grants.items()}
    return data


# ------------------------------------------------------------ engine/doctor


@dataclass(frozen=True)
class NextAction:
    kind: ActionKind
    step: Step | None = None
    loop_round: int | None = None
    max_rounds: int | None = None


@dataclass(frozen=True)
class ProbeResult:
    returncode: int
    stdout: str


@dataclass(frozen=True)
class ToolCheck:
    tool: Tool | str
    status: ToolStatus
    required: bool
    version: str | None = None
    detail: str | None = None

    @property
    def install_url(self) -> str:
        return INSTALL_URLS[self.tool]


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[ToolCheck, ...]
    ok: bool


# ------------------------------------------------------ commit/scan/guard


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ScanResult:
    """Outcome of a secret scan that actually ran; ``output`` is the scanner's redacted report."""

    clean: bool
    output: str


@dataclass(frozen=True)
class CommitInfo:
    """One commit of a task: its sha, subject line and the plan item it names (if any)."""

    sha: str
    subject: str
    item: str | None = None


@dataclass(frozen=True)
class CommitResult:
    sha: str
    message: str


@dataclass(frozen=True)
class HookInput:
    """What a hook needs from a CLI's payload, in one shape for every CLI."""

    cwd: Path | None = None
    command: str | None = None
    # The file a file-writing tool is about to change (as given, possibly relative).
    write_target: Path | None = None
    # The CLI's name for the tool being called (Bash, Write, run_command...), when its payload gives one.
    tool: str | None = None
    # Claude: this Stop hook already ran this turn. Antigravity: 0-based model invocation number.
    stop_hook_active: bool = False
    invocation_num: int | None = None


@dataclass(frozen=True)
class TaskInfo:
    id: str
    title: str
    branch: str | None
    status: str
    current_step: str
    step_status: str
    loop_round: int
    max_rounds: int
    size: str | None = None
    roadmap: str | None = None


@dataclass(frozen=True)
class StatusInfo:
    workspace: str
    workflow: str
    active_task: TaskInfo | None
    next: str
    # The roadmap item to take up next, as ``R2 - Title`` plus ``(unconfirmed)`` when nobody confirmed it.
    next_roadmap: str | None = None


@dataclass(frozen=True)
class NextInfo:
    kind: str
    description: str


@dataclass(frozen=True)
class PlanCheckInfo:
    ok: bool
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportInfo:
    path: str
    bytes: int


@dataclass(frozen=True)
class ProjectWriteInfo:
    path: str
    bytes: int
    conventions: int = 0
    open_questions: int = 0
    # Conventions that were confirmed (or written as confirmed) and are now unconfirmed, because an agent cannot confirm.
    demoted: tuple[str, ...] = ()
    # Things the writer should know: a mission that is incomplete, a status that was kept, a confirmed item that is gone.
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanToolInfo:
    tool: str
    status: str
    findings: int
    blocking: int


@dataclass(frozen=True)
class ScanSummaryInfo:
    task: str | None
    tools: tuple[ScanToolInfo, ...] = ()
    # Ids of blocking findings no person has suppressed.
    blocking: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConventionInfo:
    code: str
    title: str
    source: str
    check: str
    rule: str | None
    description: str
    # False for a project convention nobody confirmed yet: a suggestion, not checked.
    enforced: bool


@dataclass(frozen=True)
class KnowledgeHit:
    file: str
    line: int
    text: str


@dataclass(frozen=True)
class KnowledgeFile:
    file: str
    content: str


@dataclass(frozen=True)
class HookReply:
    kind: ReplyKind = ReplyKind.NONE
    text: str = ""


@dataclass(frozen=True)
class GuardVerdict:
    decision: GuardDecision
    rule: GuardRule | None = None
    reason: str | None = None

    @property
    def denied(self) -> bool:
        return self.decision is GuardDecision.DENY

    @property
    def asks(self) -> bool:
        return self.decision is GuardDecision.ASK
