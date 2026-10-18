"""Gates: checks a step has to satisfy before it can pass. Foundation knows the kinds, workflows choose where they apply."""

import re
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from agentflow.constants import DRIFT_HEADING, ENCODING, MARKDOWN_SUFFIX, REPORTS_DIR, TASKS_DIR, CheckKind, GateKind
from agentflow.convention_sources import answered_questions, load_effective_conventions
from agentflow import testspec
from agentflow.drift import drift_problems
from agentflow.scan import scan_problems, tools_for_step
from agentflow.scan_store import ScanStore
from agentflow.models import Step, Task, Workflow
from agentflow.plan import check_plan, parse_plan
from agentflow.projectcontext import ProjectContext


@dataclass(frozen=True)
class GateContext:
    workspace_dir: Path
    workflow: Workflow
    project: ProjectContext
    # Current commit of the project; scan results must be for it. ``None`` skips the freshness check.
    head: Callable[[], str] = field(default=lambda: "")


GateCheck = Callable[[GateContext, Task, Step], list[str]]


def plan_report_path(workspace_dir: Path, task_id: str, step_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / REPORTS_DIR / f"{step_id}{MARKDOWN_SUFFIX}"


def plan_problems(text: str, project: ProjectContext, answered: Collection[str] | None = None) -> list[str]:
    """Problems of a plan. ``answered`` are the questions a person answered; ``None`` skips that check (no task)."""
    plan = parse_plan(text)
    found = check_plan(plan, project.roles, project.plan_rules, project.require_files, project.plan_wide_rules, answered)
    return [str(p) for p in found]


def _plan_valid(context: GateContext, task: Task, step: Step) -> list[str]:
    path = plan_report_path(context.workspace_dir, task.id, step.id)
    if not path.is_file():
        return [f"no plan report for step '{step.id}' yet (save it with `agentflow report --step {step.id}`)"]
    answered = answered_questions(context.workspace_dir, task.id)
    return plan_problems(path.read_text(encoding=ENCODING), context.project, answered)


def _scans_clean(context: GateContext, task: Task, step: Step) -> list[str]:
    specs = tools_for_step(step.id, context.workflow, context.project)
    return scan_problems(
        ScanStore(context.workspace_dir), context.workspace_dir, task, specs, context.head(), context.project.lookup
    )


def _conventions_reviewed(context: GateContext, task: Task, step: Step) -> list[str]:
    """The review report must say, for each enforced ``check: review`` convention, that it is met or where it is not."""
    wanted = [item.convention for item in load_effective_conventions(context.workspace_dir).checked_by(CheckKind.REVIEW)]
    if not wanted:
        return []
    path = plan_report_path(context.workspace_dir, task.id, step.id)
    if not path.is_file():
        return [f"no report for step '{step.id}' yet: it must cover {', '.join(c.code for c in wanted)}"]
    text = path.read_text(encoding=ENCODING)
    problems: list[str] = []
    for convention in wanted:
        code = re.escape(convention.code)
        violation = re.search(rf"vi phạm\s+`?{code}`?(?![\w-])\s+ở\s+(\S+:\d+)", text, re.IGNORECASE)
        loose = re.search(rf"vi phạm\s+`?{code}`?(?![\w-])", text, re.IGNORECASE)
        met = re.search(rf"(?im)^[\s>*-]*`?{code}`?(?![\w-])\s*[:\-–—]\s*đạt\b", text)
        if violation:
            problems.append(
                f"{convention.code} is violated at {violation.group(1)}: a review that finds a violation fails "
                "(`agentflow task advance --result fail`) so the implementer can fix it"
            )
        elif loose:
            problems.append(f"{convention.code}: a violation must say where (`vi phạm {convention.code} ở file:line`)")
        elif not met:
            problems.append(
                f"{convention.code} ({convention.title}) is not covered: write `{convention.code}: đạt` or "
                f"`vi phạm {convention.code} ở file:line`"
            )
    return problems


def _drift_reviewed(context: GateContext, task: Task, step: Step) -> list[str]:
    """The review report must say, in its `## Đề xuất cập nhật hồ sơ` section, whether the project documents need to change."""
    path = plan_report_path(context.workspace_dir, task.id, step.id)
    if not path.is_file():
        return [f"no report for step '{step.id}' yet: it must have a '## {DRIFT_HEADING}' section"]
    return drift_problems(path.read_text(encoding=ENCODING))


def _test_spec_valid(context: GateContext, task: Task, step: Step) -> list[str]:
    """The test-spec report is in order and every command, run by agentflow itself, fails (tests come before the code)."""
    problems, _record = testspec.verify_red(
        context.workspace_dir, context.workflow, task, context.workspace_dir.parent, context.head(), context.project.lookup
    )
    return problems


def _tests_pass(context: GateContext, task: Task, step: Step) -> list[str]:
    """agentflow runs the project's test command and the commands of the test-spec again; all must pass."""
    problems, _warning = testspec.tests_pass(
        context.workspace_dir, context.workflow, task, context.workspace_dir.parent, context.head(), context.project.lookup
    )
    return problems


CHECKS: dict[GateKind, GateCheck] = {
    GateKind.TEST_SPEC_VALID: _test_spec_valid,
    GateKind.TESTS_PASS: _tests_pass,
    GateKind.PLAN_VALID: _plan_valid,
    GateKind.SCANS_CLEAN: _scans_clean,
    GateKind.CONVENTIONS_REVIEWED: _conventions_reviewed,
    GateKind.DRIFT_REVIEWED: _drift_reviewed,
}


class WorkspaceGates:
    """``GateRunner`` for a real workspace. Gate kinds without a registered check are skipped."""

    def __init__(
        self,
        context: GateContext,
        extra: Callable[[Step], Sequence[GateKind]] = lambda step: (),
        checks: dict[GateKind, GateCheck] | None = None,
    ) -> None:
        self.context = context
        self.extra = extra
        self.checks = CHECKS if checks is None else checks

    def problems(self, task: Task, step: Step) -> list[str]:
        kinds = dict.fromkeys((*step.gates, *self.extra(step)))
        found: list[str] = []
        for kind in kinds:
            check = self.checks.get(kind)
            if check is not None:
                found += [f"[{kind}] {message}" for message in check(self.context, task, step)]
        return found
