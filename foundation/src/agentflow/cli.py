"""Command-line entry point for agentflow."""

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path

from agentflow.assign import ProjectAgentNames, WorkflowAgentNames, assignment_lines
from agentflow.convention_sources import load_effective_conventions
from agentflow.services import WorkspaceServices
from agentflow.constants import ConfirmState, KnowledgeCommand, KnowledgePlace, McpCommand, ProjectCommand, RoadmapCommand, RoadmapStatus, RoleCommand
from agentflow.interfaces import AgentNames
from agentflow.roles import RoleGrants
from agentflow.constants import ANSWER_OPTION, DECISION_SCOPE_PROJECT, CheckKind
from agentflow.convention_sources import next_code, write_answer
from agentflow.knowledge import add_personal_convention, init_store, pull_files, push_file
from agentflow.project import load_conventions
from agentflow.userconfig import knowledge_dir, save_knowledge_dir
from agentflow.confirmations import Confirmations
from agentflow.project import confirm_project, mission_state, roadmap_state, status_lines, unconfirmed_conventions
from agentflow.roadmap import find_item, is_code, items_of, read_roadmap, require_linkable, set_status
from agentflow.constants import (
    CONTAINER_TOOLS,
    ENCODING,
    HOOK_LOG_ENV,
    EXCLUDE_ENTRY,
    IN_FLIGHT_TASK_STATUSES,
    PACKAGE_NAME,
    SEMGREP_DEFAULT_RULESETS,
    STEP_RESULTS,
    VERSION_FLAG,
    WORKSPACE_DIR,
    CliKind,
    Command,
    ConfigCommand,
    DriftStatus,
    ExtCommand,
    GateKind,
    PlanCommand,
    ExitCode,
    HookEvent,
    SyncOutcome,
    TaskCommand,
    TaskEvent,
    TaskStatus,
    TaskType,
    ToolStatus,
    WorkflowCommand,
)
from agentflow.commit import commit_staged
from agentflow.doctor import SystemToolProbe, run_doctor
from agentflow.engine import next_action
from agentflow.errors import AgentflowError
from agentflow.gates import GateContext, WorkspaceGates, plan_problems, plan_report_path
from agentflow.git import GitBranchLookup, SubprocessGit
from agentflow.guard import evaluate, parse_request, verdict_to_dict
from agentflow.hook import handle_hook
from agentflow.models import State, ToolCheck, Workflow
from agentflow.plan import PlanItem, parse_plan
from agentflow.projectcontext import load_project_context
from agentflow.render import NONE_TEXT, describe_action, describe_step
from agentflow.extension import Extension
from agentflow.extensions import add_extension, copy_path, drift, load_registered, sync_extensions
from agentflow.models import Task
from agentflow.settings import coerce, get_value, set_value, settings_problems
from agentflow.scan import ScanService, all_tools, summary_lines, tools_for_step, unsuppressed_blocking
from agentflow.scan_store import ScanStore, suppressed_ids, write_suppression
from agentflow.scan_tools import VAR_RANGE
from agentflow.scan_types import ScanContext
from agentflow.seal import NOT_SCANNED, TaskSealer, base_branch
from agentflow.semgrep_rules import HttpRuleFetcher, default_cache_dir
from agentflow.runner import SubprocessRunner
from agentflow.scanner import ContainerGitleaksScanner
from agentflow.state import JsonStateStore, utc_now
from agentflow.sync import sync_workflow, workflow_drift
from agentflow.tasks import (
    advance_task,
    approve_task,
    cancel_task,
    seal_finished_task,
    new_task,
    require_active_task,
    write_report,
)
from agentflow.workspace import (
    WorkspacePaths,
    find_workspace,
    init_workspace,
    load_config,
    load_workspace_workflow,
    GitWorkspaceLookup,
    save_config,
)

CLI_OPTION = "--cli"
TYPE_OPTION = "--type"
SIZE_OPTION = "--size"
ROADMAP_OPTION = "--roadmap"
RESULT_OPTION = "--result"
REASON_OPTION = "--reason"
STEP_OPTION = "--step"
SHORT_SHA_LENGTH = 9
WORKFLOW_OPTION = "--workflow"
FILE_OPTION = "--file"
ALL_OPTION = "--all"
SUPPRESS_OPTION = "--suppress"
COMMIT_OPTION = "--commit"
ITEM_OPTION = "--item"
FORCE_OPTION = "--force"
ERROR_PREFIX = "error: "
WARNING_PREFIX = "warning: "
SEMGREP_RULESETS_KEY = "scan.semgrep.rulesets"
SYNC_HINT = "run `agentflow workflow sync` to use the new version"

Handler = Callable[[argparse.Namespace], ExitCode]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PACKAGE_NAME, description="Shared engine for plugin family workflows.")
    parser.add_argument(VERSION_FLAG, action="version", version=f"{PACKAGE_NAME} {version(PACKAGE_NAME)}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    commands.add_parser(Command.DOCTOR, help="check uv, git and a container runtime")

    init = commands.add_parser(Command.INIT, help=f"create or complete {EXCLUDE_ENTRY} in this git repository")
    init.add_argument(WORKFLOW_OPTION, required=True, type=Path, help="family workflow.yaml to copy in")

    commands.add_parser(Command.STATUS, help="show the open task, its current step and what comes next")
    commands.add_parser(Command.NEXT, help="show the next step for the workflow and current state")

    workflow = commands.add_parser(Command.WORKFLOW, help="manage the workspace's workflow copy")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", metavar="<workflow command>", required=True)
    sync = workflow_commands.add_parser(WorkflowCommand.SYNC, help="replace the copy with the checked source")
    sync.add_argument(FORCE_OPTION, action="store_true", help="sync even while tasks are mid-workflow")

    task = commands.add_parser(Command.TASK, help="start, advance, approve or cancel a task")
    task_commands = task.add_subparsers(dest="task_command", metavar="<task command>", required=True)
    new = task_commands.add_parser(TaskCommand.NEW, help="create the task's gitflow branch and record the task")
    new.add_argument("title", help="what the task is about")
    new.add_argument(TYPE_OPTION, type=TaskType, choices=list(TaskType), default=TaskType.FEATURE)
    new.add_argument(SIZE_OPTION, help="task size, one of the sizes the workflow defines (default: the workflow's default size)")
    new.add_argument(ROADMAP_OPTION, help="the roadmap item (R1, R2 ...) the task serves; moves it to doing")
    advance = task_commands.add_parser(TaskCommand.ADVANCE, help="record that the current step passed or failed")
    advance.add_argument(RESULT_OPTION, required=True, type=TaskEvent, choices=list(STEP_RESULTS))
    approve = task_commands.add_parser(TaskCommand.APPROVE, help="approve the step, or resume a blocked task")
    approve.add_argument(REASON_OPTION, help="why a blocked task is resumed (kept in decisions/)")
    task_commands.add_parser(TaskCommand.CANCEL, help="cancel the active task")
    seal = task_commands.add_parser(TaskCommand.SEAL, help="for a person: write summary.md and the approval tag of a finished task")
    seal.add_argument("task_id", help="id of a finished task, e.g. T-001")
    seal.add_argument(COMMIT_OPTION, help="tag this commit instead of the task branch's tip (e.g. after the branch was deleted)")

    ext = commands.add_parser(Command.EXT, help="extensions: what child plugins add (roles, rules, scan tools, gates)")
    ext_commands = ext.add_subparsers(dest="ext_command", metavar="<ext command>", required=True)
    ext_add = ext_commands.add_parser(ExtCommand.ADD, help="for a person: check an extension.yaml and register it in this workspace")
    ext_add.add_argument("path", type=Path, help="the plugin's extension.yaml")
    ext_commands.add_parser(ExtCommand.LIST, help="registered extensions and whether their source changed")
    ext_sync = ext_commands.add_parser(ExtCommand.SYNC, help="for a person: replace the copies with their checked sources")
    ext_sync.add_argument("name", nargs="?", help="only this extension")
    ext_sync.add_argument(FORCE_OPTION, action="store_true", help="sync even while tasks are in progress")

    config = commands.add_parser(Command.CONFIG, help="project settings that extensions read (.agentflow/config.yaml)")
    config_commands = config.add_subparsers(dest="config_command", metavar="<config command>", required=True)
    config_get = config_commands.add_parser(ConfigCommand.GET, help="print a setting (exit 29 when it is not set)")
    config_get.add_argument("key", help="dotted key, for example area.group.name")
    config_set = config_commands.add_parser(ConfigCommand.SET, help="for a person: set a setting")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_commands.add_parser(ConfigCommand.CHECK, help="check the settings against what the extensions declare")

    scan = commands.add_parser(Command.SCAN, help="run the scanners of the current step in containers (--all: every configured scan)")
    scan.add_argument(ALL_OPTION, action="store_true", help="run every configured scan, not only the current step's")

    decide = commands.add_parser(Command.DECIDE, help="for a person: record a decision (accept a scan finding, or answer a question)")
    what = decide.add_mutually_exclusive_group(required=True)
    what.add_argument(SUPPRESS_OPTION, metavar="FINDING_ID", help="accept this scan finding as a false positive")
    what.add_argument(ANSWER_OPTION, metavar="QUESTION", help="answer a question: Q1 of the plan, or S1 of the setup")
    decide.add_argument(REASON_OPTION, help="why it is acceptable (with --suppress)")
    decide.add_argument("--text", help="the convention the answer sets, in one line (with --answer)")
    decide.add_argument("--check", choices=[str(kind) for kind in CheckKind], help="how it is checked (with --answer)")
    decide.add_argument("--rule", help="item-order for plan, a rule file in knowledge/semgrep/ for semgrep (with --answer)")
    decide.add_argument("--layers", help="layer-order: the layers from first to last, comma separated (with --answer)")
    decide.add_argument("--scope", help="layer-order: path globs that limit the rule, comma separated; none means the whole plan (with --answer)")
    decide.add_argument("--overrides", help="the code of a lower-priority convention this one replaces (with --answer)")
    decide.add_argument("--global", dest="to_store", action="store_true", help="also add it to your personal knowledge store (with --answer)")

    plan = commands.add_parser(Command.PLAN, help="check the plan of the active task")
    plan_commands = plan.add_subparsers(dest="plan_command", metavar="<plan command>", required=True)
    check = plan_commands.add_parser(PlanCommand.CHECK, help="every item needs a code, a valid role, done-when and docs")
    check.add_argument(FILE_OPTION, type=Path, help="check this Markdown file instead of the task's plan report")
    assign = plan_commands.add_parser(PlanCommand.ASSIGN, help="which agent takes each plan item: its role, and its tier where the role has tiers")
    assign.add_argument(CLI_OPTION, type=CliKind, choices=list(CliKind), default=CliKind.CLAUDE, help="the CLI that will call the agents (default: claude)")

    role = commands.add_parser(Command.ROLE, help="tools a person grants a role for this project")
    role_commands = role.add_subparsers(dest="role_command", metavar="<role command>", required=True)
    grant = role_commands.add_parser(RoleCommand.GRANT, help="for a person: let a role use an MCP tool (or a pattern such as mcp__server__*) in this project")
    grant.add_argument("role")
    grant.add_argument("tool", help="mcp__<server>, mcp__<server>__* or mcp__<server>__<tool>")
    revoke = role_commands.add_parser(RoleCommand.REVOKE, help="for a person: take a granted tool away again")
    revoke.add_argument("role")
    revoke.add_argument("tool")
    role_commands.add_parser(RoleCommand.LIST, help="the grants of this project and the agents that carry them")
    role_commands.add_parser(RoleCommand.SYNC, help="for a person: write the project agents again from the grants and the installed plugins")

    report = commands.add_parser(Command.REPORT, help="store a step report read from stdin")
    report.add_argument(STEP_OPTION, required=True, help="step id the report belongs to")

    commit = commands.add_parser(Command.COMMIT, help="scan staged changes for secrets, then commit with the task prefix")
    commit.add_argument("message", help="commit message, without the task prefix")
    commit.add_argument(ITEM_OPTION, help="plan item (C1, ...) this commit belongs to")

    commands.add_parser(Command.GUARD, help='read {"command", "cwd"} JSON from stdin, print an allow/deny verdict')

    commands.add_parser(Command.CONVENTIONS, help="the conventions to work to: decisions, project and personal store, merged")

    project = commands.add_parser(Command.PROJECT, help="the project documents a scout wrote (.agentflow/project/)")
    project_commands = project.add_subparsers(dest="project_command", metavar="<project command>", required=True)
    confirm = project_commands.add_parser(
        ProjectCommand.CONFIRM, help="for a person: confirm conventions (PC-01 ...), the mission, profile, architecture or roadmap items (R1 ...)"
    )
    confirm.add_argument("codes", nargs="*", metavar="CODE")
    confirm.add_argument("--all", action="store_true", dest="everything", help="confirm every convention (not the mission, profile, architecture or roadmap)")
    project_commands.add_parser(ProjectCommand.STATUS, help="which project documents exist and which a person has confirmed")

    roadmap = commands.add_parser(Command.ROADMAP, help="the project's roadmap (.agentflow/project/roadmap.md)")
    roadmap_commands = roadmap.add_subparsers(dest="roadmap_command", metavar="<roadmap command>", required=True)
    roadmap_commands.add_parser(RoadmapCommand.LIST, help="the items with their status")
    roadmap_set = roadmap_commands.add_parser(RoadmapCommand.SET, help="for a person: move an item to todo, doing, done or dropped")
    roadmap_set.add_argument("code", help="roadmap item, e.g. R3")
    roadmap_set.add_argument("status", choices=[str(status) for status in RoadmapStatus])

    knowledge = commands.add_parser(Command.KNOWLEDGE, help="your personal knowledge store (outside every repository)")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", metavar="<knowledge command>", required=True)
    k_init = knowledge_commands.add_parser(KnowledgeCommand.INIT, help="for a person: create the store's folders and files")
    k_init.add_argument("--dir", type=Path, default=None, help="the store's folder (default: the one in the user config, else ~/knowledge)")
    k_pull = knowledge_commands.add_parser(KnowledgeCommand.PULL, help="for a person: copy files of the store into .agentflow/knowledge/")
    k_pull.add_argument("files", nargs="+", metavar="FILE", help="paths inside the store")
    k_push = knowledge_commands.add_parser(KnowledgeCommand.PUSH, help="for a person: copy a lesson from the workspace into the store")
    k_push.add_argument("file", type=Path)
    k_push.add_argument("--as", dest="place", default=str(KnowledgePlace.LESSONS), choices=[str(p) for p in KnowledgePlace])

    mcp = commands.add_parser(Command.MCP, help="the MCP server that gives agents the agentflow tools")
    mcp_commands = mcp.add_subparsers(dest="mcp_command", metavar="<mcp command>", required=True)
    mcp_commands.add_parser(McpCommand.SERVE, help="serve the tools over stdio (started by Claude Code or Antigravity)")

    hook = commands.add_parser(Command.HOOK, help="answer a Claude Code or Antigravity hook (JSON on stdin)")
    hook.add_argument("event", type=HookEvent, choices=list(HookEvent))
    hook.add_argument(CLI_OPTION, required=True, type=CliKind, choices=list(CliKind))
    return parser


def main(argv: list[str] | None = None) -> int:
    _utf8_when_redirected()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return ExitCode.USAGE
    try:
        return handler(args)
    except AgentflowError as exc:
        _err(f"{ERROR_PREFIX}{exc}")
        return exc.code


# ---------------------------------------------------------------- handlers


def cmd_doctor(args: argparse.Namespace) -> ExitCode:
    report = run_doctor(SystemToolProbe())
    width = max(len(check.tool) for check in report.checks)
    for check in report.checks:
        print(_doctor_line(check, width))
    if not any(c.status is not ToolStatus.MISSING for c in report.checks if c.tool in CONTAINER_TOOLS):
        print(f"container runtime: install at least one of {', '.join(CONTAINER_TOOLS)}")
    if report.ok:
        print("result: all required tools found")
        return ExitCode.OK
    print("result: required tools are missing")
    return ExitCode.MISSING_REQUIREMENT


def _doctor_line(check: ToolCheck, width: int) -> str:
    label = f"[{check.status}]".ljust(len(f"[{ToolStatus.WARNING}]"))
    parts = [part for part in (check.version, check.detail) if part]
    if check.status is ToolStatus.MISSING:
        parts.append(f"install: {check.install_url}")
    return f"{label} {check.tool.ljust(width)}  {'; '.join(parts)}"


def cmd_init(args: argparse.Namespace) -> ExitCode:
    result = init_workspace(Path.cwd(), args.workflow)
    paths = result.paths
    config = load_config(paths)
    print(f"workspace: {paths.dir}")
    print(f"created: {', '.join(result.created)}" if result.created else "created: nothing, workspace was complete")
    copy_note = "copied" if result.workflow_copied else "kept the existing copy"
    print(f"workflow: {config.workflow.family} ({copy_note}; source {config.workflow.source_path})")
    print(f"git exclude: added {EXCLUDE_ENTRY}" if result.exclude_added else "git exclude: already excluded")
    _warn_drift(workflow_drift(config))
    return ExitCode.OK


@dataclass(frozen=True)
class _Opened:
    paths: WorkspacePaths
    workflow: Workflow
    state: State


def _open_workspace() -> _Opened:
    """Workspace, workflow copy in use and validated state; warns when the source drifted."""
    paths = find_workspace(Path.cwd())
    config = load_config(paths)
    workflow = load_workspace_workflow(paths)
    state = JsonStateStore(paths.dir, workflow).load()
    _warn_drift(workflow_drift(config))
    return _Opened(paths, workflow, state)


def cmd_status(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    workflow, state = opened.workflow, opened.state
    task = state.active_task()
    print(f"workspace: {opened.paths.dir}")
    print(f"workflow: {workflow.family} ({len(workflow.steps)} steps)")
    print(f"active task: {NONE_TEXT if task is None else f'{task.id} {task.title}'}")
    if task is not None:
        step = workflow.get_step(task.current_step)
        step_text = describe_step(step) if step else task.current_step
        print(f"current step: {step_text}, {task.step_status}")
        rounds = f"{task.loop_round}/{workflow.max_rounds}"
        print(f"task status: {task.status}; rework rounds: {rounds}; branch: {task.branch or NONE_TEXT}")
        if task.size:
            print(f"size: {task.size}")
        if task.roadmap:
            item = find_item(items_of(opened.paths.dir), task.roadmap)
            print(f"roadmap: {item.label if item else task.roadmap}")
    others = [t for t in state.tasks if t.status in IN_FLIGHT_TASK_STATUSES and t is not task]
    if others:
        print("other open tasks: " + ", ".join(f"{t.id} ({t.current_step}, {t.status})" for t in others))
    suggestion = WorkspaceServices(opened.paths).next_roadmap(state)
    if suggestion is not None:
        print(f"next roadmap: {suggestion}")
    print(f"next: {describe_action(next_action(workflow, task))}")
    return ExitCode.OK


def cmd_next(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    action = next_action(opened.workflow, opened.state.active_task())
    print(f"{action.kind}: {describe_action(action)}")
    return ExitCode.OK


def cmd_workflow(args: argparse.Namespace) -> ExitCode:
    # argparse requires a workflow subcommand, and sync is the only one so far.
    result = sync_workflow(Path.cwd(), force=args.force)
    if result.outcome is SyncOutcome.UNCHANGED:
        print("workflow: already in sync with its source")
        return ExitCode.OK
    print("workflow: copy replaced with the source version")
    if result.forced_task_ids:
        _err(f"{WARNING_PREFIX}synced with --force while tasks were open: {', '.join(result.forced_task_ids)}")
    return ExitCode.OK


def _store(opened: _Opened) -> JsonStateStore:
    return JsonStateStore(opened.paths.dir, opened.workflow)


def cmd_task(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    store = _store(opened)
    match args.task_command:
        case TaskCommand.NEW:
            if args.roadmap is not None:
                require_linkable(opened.paths.dir, args.roadmap)
            task = new_task(store, opened.workflow, SubprocessGit(opened.paths.root), args.title, args.type, utc_now, args.size, args.roadmap)
            if task.roadmap:
                set_status(opened.paths.dir, task.roadmap, RoadmapStatus.DOING)
            size_note = f" (size {task.size})" if task.size else ""
            roadmap_note = f" (roadmap {task.roadmap})" if task.roadmap else ""
            print(f"{task.id} created on branch {task.branch}{size_note}{roadmap_note}")
            unconfirmed = unconfirmed_conventions(opened.paths.dir)
            if unconfirmed:
                _err(
                    f"{WARNING_PREFIX}{len(unconfirmed)} convention(s) are still unconfirmed ({', '.join(unconfirmed)}): "
                    "a person confirms them with `agentflow project confirm`"
                )
            _warn_project_documents(opened.paths.dir, task)
        case TaskCommand.ADVANCE:
            task = advance_task(store, opened.workflow, args.result, utc_now, _gates(opened), _sealer(opened))
            print(f"{task.id}: step '{task.current_step}' is now {task.step_status} (task {task.status})")
        case TaskCommand.APPROVE:
            result = approve_task(store, opened.workflow, opened.paths.dir, utc_now, args.reason, _sealer(opened))
            task = result.task
            print(f"{task.id}: step '{task.current_step}' is now {task.step_status} (task {task.status})")
            if result.decision_file is not None:
                print(f"decision recorded: {result.decision_file}")
        case TaskCommand.CANCEL:
            task = cancel_task(store, opened.workflow, utc_now)
            _release_roadmap_item(opened.paths.dir, store.load(), task)
            print(f"{task.id} cancelled")
        case TaskCommand.SEAL:
            path = seal_finished_task(store, _sealer(opened), args.task_id, args.commit)
            print(f"{args.task_id} sealed; summary: {path}")
    state = store.load()
    print(f"next: {describe_action(next_action(opened.workflow, state.active_task()))}")
    return ExitCode.OK


def _warn_project_documents(workspace_dir: Path, task: Task) -> None:
    """Warnings (never errors) about the mission and roadmap a new task rests on."""
    confirmations = Confirmations.load(workspace_dir)
    mission = mission_state(workspace_dir, confirmations)
    if mission is ConfirmState.MISSING:
        _err(f"{WARNING_PREFIX}the project has no mission yet: the scout writes it from your documents (setup skill), then a person confirms it with `agentflow project confirm mission`")
    elif mission is ConfirmState.UNCONFIRMED:
        _err(f"{WARNING_PREFIX}the mission is unconfirmed: a person confirms it with `agentflow project confirm mission`")
    state, unconfirmed = roadmap_state(workspace_dir, confirmations)
    if state is ConfirmState.MISSING:
        _err(f"{WARNING_PREFIX}the project has no roadmap (roadmap missing): the scout proposes one (setup skill), then a person confirms its items")
    elif unconfirmed:
        _err(f"{WARNING_PREFIX}the roadmap has unconfirmed items: {', '.join(unconfirmed)} (a person confirms them with `agentflow project confirm {unconfirmed[0]} ...`)")
    if task.roadmap is None:
        _err(f"{WARNING_PREFIX}this task is not tied to a roadmap item: start it with `{ROADMAP_OPTION} Rn` (see `agentflow roadmap list`)")
    elif task.roadmap in unconfirmed:
        _err(f"{WARNING_PREFIX}the roadmap item {task.roadmap} you linked is unconfirmed: a person confirms it with `agentflow project confirm {task.roadmap}`")


def _release_roadmap_item(workspace_dir: Path, state: State, cancelled: Task) -> None:
    """A cancelled task that was the only work on a roadmap item puts the item back to todo."""
    if not cancelled.roadmap:
        return
    item = find_item(items_of(workspace_dir), cancelled.roadmap)
    if item is None or item.status is not RoadmapStatus.DOING:
        return
    others = [t for t in state.tasks if t.id != cancelled.id and t.roadmap == cancelled.roadmap and t.status is not TaskStatus.CANCELLED]
    if not others:
        set_status(workspace_dir, cancelled.roadmap, RoadmapStatus.TODO)


def _sealer(opened: _Opened) -> TaskSealer:
    def scan_lines(task: Task) -> list[str]:
        return summary_lines(ScanStore(opened.paths.dir), opened.paths.dir, task.id) or NOT_SCANNED

    return TaskSealer(SubprocessGit(opened.paths.root), opened.paths.dir, opened.workflow, utc_now, scan_lines)


def _plan_items(opened: _Opened) -> dict[str, PlanItem] | None:
    """Items of the active task's plan by code, or ``None`` while there is no plan report."""
    task = opened.state.active_task()
    step = next((s for s in opened.workflow.steps if GateKind.PLAN_VALID in s.gates), None)
    if task is None or step is None:
        return None
    path = plan_report_path(opened.paths.dir, task.id, step.id)
    if not path.is_file():
        return None
    return {item.code: item for item in parse_plan(path.read_text(encoding=ENCODING)).items}


def _gates(opened: _Opened) -> WorkspaceGates:
    project = load_project_context(opened.paths.dir, opened.workflow, opened.state.active_task())
    git = SubprocessGit(opened.paths.root)
    context = GateContext(opened.paths.dir, opened.workflow, project, git.head_or_empty)
    return WorkspaceGates(context, lambda step: [kind for step_id, kind in project.extra_gates if step_id == step.id])


def _semgrep_rulesets(lookup) -> tuple[str, ...]:
    configured = lookup(SEMGREP_RULESETS_KEY)
    if isinstance(configured, str):
        return (configured,)
    return tuple(configured) if configured else SEMGREP_DEFAULT_RULESETS


def cmd_ext(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    match args.ext_command:
        case ExtCommand.ADD:
            extension = add_extension(opened.paths, opened.workflow, args.path)
            print(f"registered extension '{extension.name}' (copy: {copy_path(opened.paths, extension.name)})")
            _describe_extension(extension)
            missing = settings_problems([extension], load_config(opened.paths).settings)
            if missing:
                print("settings still to set (a person runs `agentflow config set <key> <value>`):")
                for problem in missing:
                    print(f"  - {problem}")
        case ExtCommand.LIST:
            registered = load_registered(opened.paths)
            if not registered:
                print("no extensions registered")
            for item in registered:
                print(f"{item.extension.name}: {drift(item.ref)}")
                _describe_extension(item.extension)
        case ExtCommand.SYNC:
            in_flight = [t.id for t in opened.state.tasks if t.status in IN_FLIGHT_TASK_STATUSES]
            for report in sync_extensions(opened.paths, opened.workflow, args.name, in_flight, args.force):
                print(f"{report.name}: {report.outcome}")
    return ExitCode.OK


def _describe_extension(extension: Extension) -> None:
    if extension.roles:
        print(f"  roles: {', '.join(extension.role_ids)}")
    for tool in extension.scan_tools:
        print(f"  scan tool: {tool.id} (image {tool.image}, step {tool.step}, network {tool.network})")
    if extension.gates:
        print("  gates: " + ", ".join(f"{kind} on {step}" for step, kind in extension.gates))
    for rule in extension.path_rules:
        print(f"  path rule {rule.id}: {', '.join(rule.paths)} -> {', '.join(rule.roles)}")


def cmd_config(args: argparse.Namespace) -> ExitCode:
    paths = find_workspace(Path.cwd())
    config = load_config(paths)
    extensions = [item.extension for item in load_registered(paths)]
    match args.config_command:
        case ConfigCommand.GET:
            value = get_value(config.settings, args.key)
            if value is None:
                raise AgentflowError(f"setting '{args.key}' is not set", ExitCode.SETTINGS_INVALID)
            print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
        case ConfigCommand.SET:
            value = coerce(extensions, args.key, args.value)
            save_config(paths, replace(config, settings=set_value(config.settings, args.key, value)))
            print(f"{args.key} set")
        case ConfigCommand.CHECK:
            problems = settings_problems(extensions, config.settings)
            for problem in problems:
                print(f"- {problem}")
            if problems:
                raise AgentflowError(f"{len(problems)} problem(s) in the project settings", ExitCode.SETTINGS_INVALID)
            print("settings ok")
    return ExitCode.OK


def cmd_scan(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    task = require_active_task(opened.state)
    project = load_project_context(opened.paths.dir, opened.workflow, task)
    specs = all_tools(opened.workflow, project) if args.all else tools_for_step(task.current_step, opened.workflow, project)
    if not specs:
        print(f"no scans are configured for step '{task.current_step}'")
        return ExitCode.OK
    git = SubprocessGit(opened.paths.root)
    if not git.is_clean():
        raise AgentflowError(
            "the working tree has uncommitted changes; scan results must describe the committed branch, so commit or stash first",
            ExitCode.DIRTY_WORKING_TREE,
        )
    base = base_branch(task)
    if not git.branch_exists(base):
        raise AgentflowError(f"base branch '{base}' does not exist locally", ExitCode.BRANCH_PROBLEM)
    head = git.rev_parse("HEAD")
    context = ScanContext(
        repo=opened.paths.root,
        base=base,
        head=head,
        changed_files=git.changed_files(base, head),
        lookup=project.lookup,
        cache_dir=default_cache_dir(),
        rulesets=_semgrep_rulesets(project.lookup),
        extra={VAR_RANGE: f"{base}..{head}"},
        fetcher=HttpRuleFetcher(),
        warn=lambda message: _err(f"{WARNING_PREFIX}{message}"),
    )
    store = ScanStore(opened.paths.dir)
    outcomes = ScanService(SubprocessRunner(), store).run(task.id, specs, context)
    suppressed = suppressed_ids(opened.paths.dir, task.id)
    blocked = 0
    for outcome in outcomes:
        left = unsuppressed_blocking(outcome, suppressed)
        blocked += len(left)
        note = f" ({outcome.note})" if outcome.note else ""
        print(f"{outcome.tool}: {outcome.status}, {len(outcome.findings)} finding(s), {len(left)} blocking{note}")
        for finding in left:
            print(f"  - {finding.id} [{finding.severity}] {finding.message}".rstrip())
    print(f"results: {store.scans_dir(task.id)}")
    if blocked:
        raise AgentflowError(f"{blocked} blocking finding(s); fix them, or a person suppresses a false positive with `agentflow decide`", ExitCode.SCAN_BLOCKED)
    return ExitCode.OK


def _question_scope(opened: _Opened, question: str) -> tuple[str, str]:
    """(scope, where it was asked): the active task when its plan asks it, ``project`` when the setup did."""
    task = opened.state.active_task()
    items = _plan_questions(opened)
    if task is not None and question in items:
        return task.id, f"the plan of {task.id}"
    project = load_conventions(opened.paths.dir)
    if project is not None and question in {q.code for q in project.questions}:
        return DECISION_SCOPE_PROJECT, "project/conventions.md"
    raise AgentflowError(
        f"no question '{question}' in the active task's plan or in the project's open questions", ExitCode.INVALID_INPUT
    )


def _plan_questions(opened: _Opened) -> set[str]:
    task = opened.state.active_task()
    step = next((s for s in opened.workflow.steps if GateKind.PLAN_VALID in s.gates), None)
    if task is None or step is None:
        return set()
    path = plan_report_path(opened.paths.dir, task.id, step.id)
    return {q.code for q in parse_plan(path.read_text(encoding=ENCODING)).questions} if path.is_file() else set()


def _decide_answer(opened: _Opened, args: argparse.Namespace) -> ExitCode:
    if not args.text or not args.text.strip():
        raise AgentflowError("an answer needs --text (the convention, in one line)", ExitCode.INVALID_INPUT)
    if not args.check:
        raise AgentflowError(f"an answer needs --check ({', '.join(CheckKind)})", ExitCode.INVALID_INPUT)
    scope, where = _question_scope(opened, args.answer)
    store = knowledge_dir()
    if args.to_store and not store.is_dir():
        raise AgentflowError(f"--global needs your knowledge store: run `agentflow knowledge init` first ({store})", ExitCode.INVALID_INPUT)
    code = next_code(opened.paths.dir)
    path = write_answer(
        opened.paths.dir, scope, args.answer, code, args.text, CheckKind(args.check), args.rule, args.overrides, utc_now(),
        args.layers, args.scope,
    )
    print(f"decision recorded: {path} ({code}, from {where})")
    if args.to_store:
        title = f"{args.answer} ({scope})"
        kept = add_personal_convention(store, title, args.check, args.rule, args.text.strip(), f"answer to {args.answer} of {scope}", args.layers, args.scope)
        print(f"added to your knowledge store: {kept}")
    return ExitCode.OK


def cmd_decide(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    if args.answer:
        return _decide_answer(opened, args)
    if not args.reason:
        raise AgentflowError("a suppression needs a reason (--reason)", ExitCode.INVALID_INPUT)
    task = require_active_task(opened.state)
    known = {f.id: f for outcome in ScanStore(opened.paths.dir).load(task.id).values() for f in outcome.findings}
    finding = known.get(args.suppress)
    if finding is None:
        raise AgentflowError(
            f"no finding '{args.suppress}' in the scan results of {task.id} (run `agentflow scan` and copy the id)",
            ExitCode.INVALID_INPUT,
        )
    path = write_suppression(opened.paths.dir, task.id, finding, args.reason, utc_now())
    print(f"decision recorded: {path}")
    return ExitCode.OK


def _plan_assign(opened: _Opened, args: argparse.Namespace) -> ExitCode:
    items = _plan_items(opened)
    if items is None:
        raise AgentflowError("no plan report yet: nothing to assign", ExitCode.PLAN_INVALID)
    names: AgentNames = WorkflowAgentNames(opened.workflow.tiered_roles)
    if args.cli is CliKind.CLAUDE:  # Antigravity agents already see every installed MCP server
        names = ProjectAgentNames(names, RoleGrants(opened.paths, opened.workflow).project_agent_for)
    for line in assignment_lines(list(items.values()), names):
        print(line)
    return ExitCode.OK


def cmd_plan(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    if args.plan_command == PlanCommand.ASSIGN:
        return _plan_assign(opened, args)
    project = load_project_context(opened.paths.dir, opened.workflow, opened.state.active_task())
    if args.file is not None:
        problems = plan_problems(args.file.read_text(encoding=ENCODING), project)
    else:
        problems = list(WorkspaceServices(opened.paths).plan_check().problems)
    if problems:
        for problem in problems:
            print(f"- {problem}")
        raise AgentflowError(f"the plan has {len(problems)} problem(s)", ExitCode.PLAN_INVALID)
    print("plan ok")
    return ExitCode.OK


def cmd_role(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    grants = RoleGrants(opened.paths, opened.workflow)
    match args.role_command:
        case RoleCommand.GRANT:
            lines = grants.grant(args.role, args.tool)
            lines.insert(0, f"{args.role} may use {args.tool} in this project")
        case RoleCommand.REVOKE:
            lines = grants.revoke(args.role, args.tool)
            lines.insert(0, f"{args.role} no longer has {args.tool}")
        case RoleCommand.SYNC:
            lines = grants.sync() or ["project agents are up to date"]
        case _:
            lines = grants.listing()
    print("\n".join(lines))
    return ExitCode.OK


def cmd_report(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    info = WorkspaceServices(opened.paths).write_report(args.step, sys.stdin.read())
    print(f"report saved: {info.path}")
    return ExitCode.OK


def cmd_commit(args: argparse.Namespace) -> ExitCode:
    opened = _open_workspace()
    scanner = ContainerGitleaksScanner(SubprocessRunner())
    project = load_project_context(opened.paths.dir, opened.workflow)
    result = commit_staged(
        _store(opened), SubprocessGit(opened.paths.root), scanner, args.message, args.item, _plan_items(opened), project.rules
    )
    print(f"committed {result.sha[:SHORT_SHA_LENGTH]}: {result.message}")
    return ExitCode.OK


def cmd_guard(args: argparse.Namespace) -> ExitCode:
    request = parse_request(sys.stdin.read())
    verdict = evaluate(request.command, request.cwd or Path.cwd(), GitBranchLookup(), GitWorkspaceLookup())
    print(json.dumps(verdict_to_dict(verdict), ensure_ascii=False))
    return ExitCode.OK


def cmd_knowledge(args: argparse.Namespace) -> ExitCode:
    match args.knowledge_command:
        case KnowledgeCommand.INIT:
            store = args.dir or knowledge_dir()
            created = init_store(store)
            save_knowledge_dir(store)
            print(f"knowledge store: {store}")
            print(f"created: {', '.join(created)}" if created else "created: nothing, the store was complete")
        case KnowledgeCommand.PULL:
            paths = find_workspace(Path.cwd())
            for path in pull_files(knowledge_dir(), paths.dir, args.files):
                print(f"pulled: {path}")
        case KnowledgeCommand.PUSH:
            paths = find_workspace(Path.cwd())
            print(f"pushed: {push_file(knowledge_dir(), paths.dir, args.file, args.place)}")
    return ExitCode.OK


def cmd_conventions(args: argparse.Namespace) -> ExitCode:
    paths = find_workspace(Path.cwd())
    items = WorkspaceServices(paths).conventions()
    if not items:
        print("no conventions yet (the setup skill writes the project's; a person may add their own)")
    for item in items:
        mark = "" if item.enforced else " [unconfirmed: a suggestion, not checked]"
        rule = f" rule={item.rule}" if item.rule else ""
        print(f"{item.code} ({item.source}, check={item.check}{rule}){mark}: {item.title}")
        print(f"    {item.description}")
    for problem in load_effective_conventions(paths.dir).problems:
        _err(f"{WARNING_PREFIX}{problem}")
    return ExitCode.OK


def cmd_project(args: argparse.Namespace) -> ExitCode:
    paths = find_workspace(Path.cwd())
    if args.project_command == ProjectCommand.STATUS:
        for line in status_lines(paths.dir):
            print(line)
        return ExitCode.OK
    result = confirm_project(paths.dir, args.codes, args.everything)
    if result.confirmed:
        print(f"confirmed: {', '.join(result.confirmed)}")
    if result.already:
        print(f"already confirmed: {', '.join(result.already)}")
    conventions = result.conventions
    if conventions is not None and conventions.unconfirmed:
        print(f"still unconfirmed: {', '.join(conventions.unconfirmed)}")
    if conventions is not None and conventions.open_questions:
        print(f"open questions: {', '.join(conventions.open_questions)} (see .agentflow/project/conventions.md)")
    return ExitCode.OK


def cmd_roadmap(args: argparse.Namespace) -> ExitCode:
    paths = find_workspace(Path.cwd())
    if args.roadmap_command == RoadmapCommand.LIST:
        found = read_roadmap(paths.dir)
        if found is None:
            print("no roadmap yet (the setup skill has the scout propose one)")
            return ExitCode.OK
        confirmations = Confirmations.load(paths.dir)
        for item in found[1]:
            note = "" if confirmations.is_confirmed(item.code, item.content) else " (unconfirmed)"
            print(f"{item.code} [{item.status}] {item.title}{note}")
        return ExitCode.OK
    if not is_code(args.code):
        raise AgentflowError(f"'{args.code}' is not a roadmap item code (R and digits, for example R3)", ExitCode.INVALID_INPUT)
    before = set_status(paths.dir, args.code, RoadmapStatus(args.status))
    print(f"{args.code}: {before} -> {args.status}")
    return ExitCode.OK


def cmd_mcp(args: argparse.Namespace) -> ExitCode:
    # argparse requires an mcp subcommand, and serve is the only one so far.
    from agentflow.mcp_server import serve  # imported here: hooks start often and must stay fast

    serve()
    return ExitCode.OK


def cmd_hook(args: argparse.Namespace) -> ExitCode:
    # Hooks must not break the agent: report problems on stderr but always exit 0.
    stdin_text = sys.stdin.read()
    try:
        output = handle_hook(args.event, args.cli, stdin_text, GitBranchLookup())
    except Exception as exc:  # noqa: BLE001 - a crashing hook would otherwise surface as a tool error
        _err(f"{WARNING_PREFIX}agentflow hook failed: {exc}")
        return ExitCode.OK
    _log_hook_call(args, stdin_text, output)
    if output:
        print(output)
    return ExitCode.OK


HANDLERS: dict[str, Handler] = {
    Command.HOOK: cmd_hook,
    Command.DOCTOR: cmd_doctor,
    Command.INIT: cmd_init,
    Command.STATUS: cmd_status,
    Command.NEXT: cmd_next,
    Command.WORKFLOW: cmd_workflow,
    Command.TASK: cmd_task,
    Command.EXT: cmd_ext,
    Command.CONFIG: cmd_config,
    Command.ROLE: cmd_role,
    Command.SCAN: cmd_scan,
    Command.DECIDE: cmd_decide,
    Command.PLAN: cmd_plan,
    Command.REPORT: cmd_report,
    Command.COMMIT: cmd_commit,
    Command.GUARD: cmd_guard,
    Command.MCP: cmd_mcp,
    Command.PROJECT: cmd_project,
    Command.ROADMAP: cmd_roadmap,
    Command.CONVENTIONS: cmd_conventions,
    Command.KNOWLEDGE: cmd_knowledge,
}


# ----------------------------------------------------------------- helpers


def _warn_drift(drift: DriftStatus) -> None:
    if drift is DriftStatus.SOURCE_CHANGED:
        _err(f"{WARNING_PREFIX}the workflow source changed since it was copied; {SYNC_HINT}")
    elif drift is DriftStatus.SOURCE_MISSING:
        _err(f"{WARNING_PREFIX}the workflow source no longer exists; using the copy in {WORKSPACE_DIR}/")


def _log_hook_call(args: argparse.Namespace, stdin_text: str, output: str) -> None:
    """Append the call to the file named by ``HOOK_LOG_ENV``, if set; a log that cannot be written is ignored."""
    target = os.environ.get(HOOK_LOG_ENV)
    if not target:
        return
    entry = {"event": args.event, "cli": args.cli, "stdin": stdin_text, "output": output}
    try:
        with open(target, "a", encoding=ENCODING) as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _utf8_when_redirected() -> None:
    # Workflow names are often non-ASCII; a redirected Windows stream defaults to a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding=ENCODING)
