"""Running scans for a task and judging their results. Tools come from dev-core itself or from extensions."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agentflow.constants import ExitCode, GateKind, ResultKind, ScanStatus
from agentflow.container import run_tool, running_engine, select_files, tool_command
from agentflow.errors import AgentflowError
from agentflow.interfaces import CommandRunner
from agentflow.models import Task, Workflow
from agentflow.placeholders import expand_args, expand_text
from agentflow.projectcontext import ProjectContext
from agentflow.scan_read import read_result
from agentflow.scan_store import ScanStore, suppressed_ids
from agentflow.scan_tools import BUILTIN_TOOLS, custom_semgrep_spec
from agentflow.scan_types import Condition, MountSpec, ScanContext, ScanFinding, ScanOutcome, ScanToolSpec

JSON_OUTPUT_SUFFIX = ".json"
TEXT_OUTPUT_SUFFIX = ".txt"
MAX_LISTED_FINDINGS = 10
NO_FILES_NOTE = "no changed files match"


def condition_holds(condition: Condition | None, lookup: Callable[[str], Any]) -> bool:
    if condition is None:
        return True
    if condition.config_equals is not None:
        key, expected = condition.config_equals
        if str(lookup(key)) != expected:
            return False
    return all(lookup(key) not in (None, "") for key in condition.config_present)


def scan_gated_steps(workflow: Workflow, project: ProjectContext) -> set[str]:
    own = {step.id for step in workflow.steps if GateKind.SCANS_CLEAN in step.gates}
    return own | {step for step, kind in project.extra_gates if kind is GateKind.SCANS_CLEAN}


def tools_for_step(step_id: str, workflow: Workflow, project: ProjectContext) -> list[ScanToolSpec]:
    """Built-in tools belong to the step the workflow itself gates; extension tools name their own step."""
    own = any(step.id == step_id and GateKind.SCANS_CLEAN in step.gates for step in workflow.steps)
    tools = (list(BUILTIN_TOOLS) + _convention_tools(project)) if own else []
    return _limited(step_id, tools + [tool for tool in project.scan_tools if tool.step == step_id], project)


def all_tools(workflow: Workflow, project: ProjectContext) -> list[ScanToolSpec]:
    has_own = any(GateKind.SCANS_CLEAN in step.gates for step in workflow.steps)
    tools = ((list(BUILTIN_TOOLS) + _convention_tools(project)) if has_own else []) + list(project.scan_tools)
    return [tool for tool in tools if tool in _limited(tool.step or _own_step(workflow), [tool], project)]


def _own_step(workflow: Workflow) -> str | None:
    return next((step.id for step in workflow.steps if GateKind.SCANS_CLEAN in step.gates), None)


def _limited(step_id: str | None, tools: list[ScanToolSpec], project: ProjectContext) -> list[ScanToolSpec]:
    """The tools a task's size lets ``step_id`` run (all of them when its size says nothing about that step)."""
    allowed = project.scan_filter.get(step_id) if step_id else None
    return tools if allowed is None else [tool for tool in tools if tool.id in allowed]


def _convention_tools(project: ProjectContext) -> list[ScanToolSpec]:
    """Semgrep with the project's own rules, when enforced conventions ask for it (or their rule files are unusable)."""
    if not project.custom_semgrep and not project.custom_semgrep_problems:
        return []
    return [custom_semgrep_spec(project.custom_semgrep, project.custom_semgrep_problems)]


def output_name(spec: ScanToolSpec) -> str:
    suffix = JSON_OUTPUT_SUFFIX if spec.result.kind is ResultKind.JSON_FINDINGS else TEXT_OUTPUT_SUFFIX
    return f"{spec.id}{suffix}"


class ScanService:
    def __init__(self, runner: CommandRunner, store: ScanStore) -> None:
        self.runner = runner
        self.store = store

    def run(self, task_id: str, specs: Sequence[ScanToolSpec], context: ScanContext) -> list[ScanOutcome]:
        """Run ``specs`` in containers and store the results. Nothing is stored if any tool fails to run."""
        outcomes: list[ScanOutcome] = []
        outputs: dict[str, str] = {}
        engine: str | None = None
        for spec in specs:
            skip = self._skip_reason(spec, context)
            if skip is not None:
                outcomes.append(ScanOutcome(spec.id, ScanStatus.SKIPPED, context.head, note=skip, step=spec.step))
                continue
            engine = engine or running_engine(self.runner)
            files = self._files(spec, context)
            if spec.prepare is not None:
                spec.prepare(context)
            outcome, raw = self._run_one(engine, spec, context, files)
            outcomes.append(outcome)
            if raw is not None:
                outputs[output_name(spec)] = raw
        self.store.save(task_id, outcomes, outputs)
        return outcomes

    def _skip_reason(self, spec: ScanToolSpec, context: ScanContext) -> str | None:
        if not condition_holds(spec.when, context.lookup):
            return spec.skip_note or "not applicable to this project"
        if spec.files is not None and spec.files.skip_when_empty and not self._files(spec, context):
            return spec.skip_note or NO_FILES_NOTE
        return None

    def _files(self, spec: ScanToolSpec, context: ScanContext) -> list[str]:
        if spec.files is None:
            return []
        globs = tuple(expand_text(glob, context.lookup, context.extra) for glob in spec.files.globs)
        return select_files(context.changed_files, globs)

    def _run_one(
        self, engine: str, spec: ScanToolSpec, context: ScanContext, files: list[str]
    ) -> tuple[ScanOutcome, str | None]:
        args = expand_args(spec.args, context.lookup, files, context.extra)
        mounts = [
            MountSpec(expand_text(m.source, context.lookup, context.extra), m.target, m.readonly, m.volume)
            for m in spec.mounts
        ]
        command = tool_command(engine, spec, context.repo, args, mounts)
        result = run_tool(self.runner, command, context.repo)
        text = result.stdout if spec.result.kind is ResultKind.JSON_FINDINGS else f"{result.stdout}\n{result.stderr}".strip()
        status, findings = read_result(spec.id, spec.result, result.returncode, text)
        outcome = ScanOutcome(spec.id, status, context.head, findings, output_file=output_name(spec), step=spec.step)
        return outcome, text


def summary_lines(store: ScanStore, workspace_dir: Path, task_id: str) -> list[str]:
    """One line per tool for summary.md."""
    suppressed = suppressed_ids(workspace_dir, task_id)
    lines = []
    for outcome in store.load(task_id).values():
        accepted = len([f for f in outcome.blocking if f.id in suppressed])
        extra = f", {accepted} suppressed by a person" if accepted else ""
        note = f" ({outcome.note})" if outcome.note else ""
        lines.append(f"{outcome.tool}: {outcome.status}, {len(outcome.findings)} finding(s){extra}{note}")
    return lines


def unsuppressed_blocking(outcome: ScanOutcome, suppressed: set[str]) -> list[ScanFinding]:
    return [finding for finding in outcome.blocking if finding.id not in suppressed]


def scan_problems(
    store: ScanStore,
    workspace_dir: Path,
    task: Task,
    specs: Sequence[ScanToolSpec],
    head: str,
    lookup: Callable[[str], Any],
) -> list[str]:
    """Reasons the step's scans do not allow it to pass: missing, stale, or blocking findings left."""
    stored = store.load(task.id)
    suppressed = suppressed_ids(workspace_dir, task.id)
    problems: list[str] = []
    for spec in specs:
        if not condition_holds(spec.when, lookup):
            continue
        outcome = stored.get(spec.id)
        if outcome is None:
            problems.append(f"scan '{spec.id}' has not run (run `agentflow scan`)")
        elif outcome.commit != head:
            problems.append(f"scan '{spec.id}' is out of date: the branch moved since it ran (run `agentflow scan`)")
        else:
            left = unsuppressed_blocking(outcome, suppressed)
            if left:
                ids = ", ".join(finding.id for finding in left[:MAX_LISTED_FINDINGS])
                more = f" and {len(left) - MAX_LISTED_FINDINGS} more" if len(left) > MAX_LISTED_FINDINGS else ""
                problems.append(f"scan '{spec.id}' blocks with {len(left)} finding(s): {ids}{more}")
    return problems


def require_scans_ok(problems: list[str]) -> None:
    if problems:
        raise AgentflowError("\n".join(problems), ExitCode.SCAN_BLOCKED)
