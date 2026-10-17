"""Sealing a finished task: summary.md plus an annotated tag on the task branch's last commit."""

from collections.abc import Callable
from pathlib import Path

from agentflow.constants import (
    APPROVAL_TAG_PREFIX,
    APPROVAL_TAG_SUFFIX,
    BRANCH_SEPARATOR,
    DEVELOP_BRANCH,
    ENCODING,
    SUMMARY_FILE,
    TASK_BASE_BRANCH,
    TASKS_DIR,
    ExitCode,
    GateKind,
    TaskStatus,
    TaskType,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.gates import plan_report_path
from agentflow.interfaces import GitClient
from agentflow.lessons import read_lessons, write_lessons
from agentflow.models import State, Task, Workflow
from agentflow.plan import PlanItem, parse_plan
from agentflow.roadmap import find_item, items_of
from agentflow.summary import build_summary

ScanLines = Callable[[Task], list[str]]
NOT_SCANNED = ["scans were not run for this task"]


def approval_tag(task_id: str) -> str:
    return f"{APPROVAL_TAG_PREFIX}{task_id}/{APPROVAL_TAG_SUFFIX}"


def base_branch(task: Task) -> str:
    """Branch the task started from, read off its branch name (``feature/T-001-x`` -> develop)."""
    prefix = (task.branch or "").split(BRANCH_SEPARATOR, 1)[0]
    try:
        return TASK_BASE_BRANCH[TaskType(prefix)]
    except ValueError:
        return DEVELOP_BRANCH


def require_sealed(state: State, git: GitClient) -> None:
    """The most recent finished task must carry its approval tag before another one starts."""
    done = [task for task in state.tasks if task.status is TaskStatus.DONE]
    if not done:
        return
    last = max(done, key=lambda task: task.id)
    if not git.tag_exists(approval_tag(last.id)):
        raise AgentflowError(
            f"task {last.id} is done but has no approval tag '{approval_tag(last.id)}'; "
            f"a person runs `agentflow task seal {last.id}` first",
            ExitCode.TASK_NOT_SEALED,
        )


class TaskSealer:
    def __init__(
        self,
        git: GitClient,
        workspace_dir: Path,
        workflow: Workflow,
        clock: Callable[[], str],
        scan_lines: ScanLines = lambda task: NOT_SCANNED,
    ) -> None:
        self.git = git
        self.workspace_dir = workspace_dir
        self.workflow = workflow
        self.clock = clock
        self.scan_lines = scan_lines

    def plan_items(self, task: Task) -> tuple[PlanItem, ...]:
        step = next((s for s in self.workflow.steps if GateKind.PLAN_VALID in s.gates), None)
        if step is None:
            return ()
        path = plan_report_path(self.workspace_dir, task.id, step.id)
        return parse_plan(path.read_text(encoding=ENCODING)).items if path.is_file() else ()

    def _roadmap_label(self, task: Task) -> str | None:
        if not task.roadmap:
            return None
        item = find_item(items_of(self.workspace_dir), task.roadmap)
        return item.label if item is not None else task.roadmap

    def seal(self, task: Task, commit: str | None = None) -> Path:
        """Write summary.md and tag the task's last commit; raises (changing no state) when that is not possible."""
        if task.branch is None:
            raise AgentflowError(f"task {task.id} has no branch recorded", ExitCode.BRANCH_PROBLEM)
        try:
            tip = self.git.rev_parse(commit or task.branch)
        except AgentflowError as exc:
            raise AgentflowError(f"cannot find the last commit of task {task.id}: {exc}", ExitCode.BRANCH_PROBLEM) from exc
        tag = approval_tag(task.id)
        if self.git.tag_exists(tag):
            raise AgentflowError(f"tag '{tag}' already exists", ExitCode.TASK_CONFLICT)
        approver, at = self.git.identity(), self.clock()
        base = base_branch(task)
        commits = self.git.commits_between(base, tip) if self.git.branch_exists(base) else []
        lessons = read_lessons(plan_report_path(self.workspace_dir, task.id, self.workflow.steps[-1].id))
        write_lessons(self.workspace_dir, task.id, lessons)
        text = build_summary(task, self.plan_items(task), commits, self.scan_lines(task), approver, at, lessons, self._roadmap_label(task))
        path = self.workspace_dir / TASKS_DIR / task.id / SUMMARY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, text)
        message = f"agentflow approved {task.id}: {task.title}\nApproved by: {approver}\nApproved at: {at}"
        self.git.create_tag(tag, tip, message)
        return path
