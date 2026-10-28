"""Sealing a finished task: summary.md plus an annotated tag on the task branch's last commit."""

from collections.abc import Callable
from pathlib import Path

from thanhtan.constants import (
    APPROVAL_TAG_PREFIX,
    LEGACY_APPROVAL_TAG_PREFIX,
    APPROVAL_TAG_SUFFIX,
    BRANCH_SEPARATOR,
    DEVELOP_BRANCH,
    ENCODING,
    SPEC_DELTA_FILE,
    SUMMARY_FILE,
    TASK_BASE_BRANCH,
    TASKS_DIR,
    ConfirmUnit,
    ExitCode,
    GateKind,
    ProjectSection,
    ReplanState,
    TaskStatus,
    TaskType,
)
from thanhtan.confirmations import Confirmations
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic
from thanhtan.gates import plan_report_path
from thanhtan.interfaces import GitClient, SealingGit
from thanhtan.lessons import read_lessons, write_lessons
from thanhtan.models import State, Task, Workflow
from thanhtan.plan import PlanItem, parse_plan
from thanhtan.project import document_state, mission_state
from thanhtan.roadmap import find_item, items_of
from thanhtan.specdelta import build_spec_delta
from thanhtan.summary import build_summary

ScanLines = Callable[[Task], list[str]]
NOT_SCANNED = ["scans were not run for this task"]


def approval_tag(task_id: str) -> str:
    return f"{APPROVAL_TAG_PREFIX}{task_id}/{APPROVAL_TAG_SUFFIX}"


def is_approved(git: GitClient, task_id: str) -> bool:
    """The task carries its approval tag: ``thanhtan/<id>/approved``, or ``agentflow/<id>/approved`` from before 1.0.0."""
    return git.tag_exists(approval_tag(task_id)) or git.tag_exists(f"{LEGACY_APPROVAL_TAG_PREFIX}{task_id}/{APPROVAL_TAG_SUFFIX}")


def base_branch(task: Task) -> str:
    """Branch the task started from: the one kept in the task, or for a task recorded before that, read off its branch name
    (``feature/T-001-x`` -> develop)."""
    if task.base:
        return task.base
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
    if not is_approved(git, last.id):
        raise ThanhTanError(
            f"task {last.id} is done but has no approval tag '{approval_tag(last.id)}'; "
            f"a person runs `thanhtan task seal {last.id}` first",
            ExitCode.TASK_NOT_SEALED,
        )


class TaskSealer:
    def __init__(
        self,
        git: SealingGit,
        workspace_dir: Path,
        workflow: Workflow,
        clock: Callable[[], str],
        scan_lines: ScanLines = lambda task: NOT_SCANNED,
        develop_branch: str = DEVELOP_BRANCH,
    ) -> None:
        self.develop_branch = develop_branch
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

    def _review_report(self, task: Task) -> str | None:
        """The review report: the step that checks the reviewer's proposals, else the last step; ``None`` when there is none."""
        step = next((s for s in self.workflow.steps if GateKind.DRIFT_REVIEWED in s.gates), self.workflow.steps[-1])
        path = plan_report_path(self.workspace_dir, task.id, step.id)
        return path.read_text(encoding=ENCODING) if path.is_file() else None

    def _document_states(self) -> dict[str, str]:
        confirmations = Confirmations.load(self.workspace_dir)
        return {
            ConfirmUnit.MISSION: str(mission_state(self.workspace_dir, confirmations)),
            ConfirmUnit.PROFILE: str(document_state(self.workspace_dir, ProjectSection.PROFILE, confirmations)),
            ConfirmUnit.ARCHITECTURE: str(document_state(self.workspace_dir, ProjectSection.ARCHITECTURE, confirmations)),
        }

    def seal(self, task: Task, commit: str | None = None) -> Path:
        """Write summary.md and tag the task's last commit; raises (changing no state) when that is not possible."""
        if task.branch is None:
            raise ThanhTanError(f"task {task.id} has no branch recorded", ExitCode.BRANCH_PROBLEM)
        try:
            tip = self.git.rev_parse(commit or task.branch)
        except ThanhTanError as exc:
            raise ThanhTanError(f"cannot find the last commit of task {task.id}: {exc}", ExitCode.BRANCH_PROBLEM) from exc
        tag = approval_tag(task.id)
        if is_approved(self.git, task.id):
            raise ThanhTanError(f"task {task.id} already has its approval tag", ExitCode.TASK_CONFLICT)
        approver, at = self.git.identity(), self.clock()
        base = base_branch(task)
        has_base = self.git.branch_exists(base)
        commits = self.git.commits_between(base, tip) if has_base else []
        files = list(self.git.changed_entries(base, tip)) if has_base else []
        lessons = read_lessons(plan_report_path(self.workspace_dir, task.id, self.workflow.steps[-1].id))
        items, roadmap = self.plan_items(task), self._roadmap_label(task)
        # Everything is worked out before anything is written: a seal that fails leaves no half-written file behind.
        delta = build_spec_delta(task, self._review_report(task), items, commits, files, roadmap, self._document_states())
        task_dir = self.workspace_dir / TASKS_DIR / task.id
        text = build_summary(
            task, items, commits, self.scan_lines(task), approver, at, lessons, roadmap,
            f"{TASKS_DIR}/{task.id}/{SPEC_DELTA_FILE}", str(ReplanState.PENDING), develop_branch=self.develop_branch,
        )  # fmt: skip
        write_lessons(self.workspace_dir, task.id, lessons)
        path = task_dir / SUMMARY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, text)
        write_text_atomic(task_dir / SPEC_DELTA_FILE, delta)
        message = f"thanhtan approved {task.id}: {task.title}\nApproved by: {approver}\nApproved at: {at}"
        self.git.create_tag(tag, tip, message)
        return path
