"""Compare the workspace's workflow copy with its source, and replace the copy on request."""

from dataclasses import dataclass, replace
from pathlib import Path

from thanhtan.constants import IN_FLIGHT_TASK_STATUSES, DriftStatus, ExitCode, SyncOutcome
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import file_sha256
from thanhtan.models import WorkspaceConfig
from thanhtan.state import JsonStateStore, unknown_step_tasks
from thanhtan.workflow import load_workflow
from thanhtan.workspace import (
    WorkspacePaths,
    copy_workflow,
    find_workspace,
    load_config,
    load_workspace_workflow,
    save_config,
)


@dataclass(frozen=True)
class SyncResult:
    outcome: SyncOutcome
    forced_task_ids: tuple[str, ...] = ()


def workflow_drift(config: WorkspaceConfig) -> DriftStatus:
    source = Path(config.workflow.source_path)
    if not source.is_file():
        return DriftStatus.SOURCE_MISSING
    if file_sha256(source) != config.workflow.sha256:
        return DriftStatus.SOURCE_CHANGED
    return DriftStatus.IN_SYNC


def sync_workflow(cwd: Path, force: bool = False) -> SyncResult:
    """Replace the workflow copy with its source, after checking the source and the tasks."""
    paths = find_workspace(cwd)
    config = load_config(paths)
    source = Path(config.workflow.source_path)
    if not source.is_file():
        raise ThanhTanError(
            f"workflow source no longer exists: {source}; the workspace keeps using its copy "
            "(run `thanhtan init --workflow <file>` to point at a new source)",
            ExitCode.WORKFLOW_NOT_FOUND,
        )
    new_workflow = load_workflow(source)  # schema and reference checks before anything changes
    if new_workflow.family != config.workflow.family:
        raise ThanhTanError(
            f"workspace uses family '{config.workflow.family}', {source} is family '{new_workflow.family}'",
            ExitCode.WORKFLOW_MISMATCH,
        )
    if file_sha256(source) == config.workflow.sha256 == file_sha256(paths.workflow_copy):
        return SyncResult(SyncOutcome.UNCHANGED)

    state = JsonStateStore(paths.dir, load_workspace_workflow(paths)).load()
    in_flight = [task for task in state.tasks if task.status in IN_FLIGHT_TASK_STATUSES]
    if in_flight and not force:
        listing = ", ".join(f"{task.id} at '{task.current_step}'" for task in in_flight)
        raise ThanhTanError(
            f"tasks are in the middle of the workflow ({listing}); finish them or rerun with --force",
            ExitCode.SYNC_BLOCKED,
        )
    stranded = unknown_step_tasks(state, new_workflow)
    if stranded:
        listing = ", ".join(f"{task.id} at '{task.current_step}'" for task in stranded)
        raise ThanhTanError(
            f"the new workflow drops steps that tasks are on ({listing}); not syncing, even with --force",
            ExitCode.SYNC_BLOCKED,
        )

    _replace_copy(paths, config, source)
    JsonStateStore(paths.dir, new_workflow).write_state_md(state)
    return SyncResult(SyncOutcome.UPDATED, tuple(task.id for task in in_flight))


def _replace_copy(paths: WorkspacePaths, config: WorkspaceConfig, source: Path) -> None:
    sha = copy_workflow(source, paths)
    save_config(paths, replace(config, workflow=replace(config.workflow, sha256=sha)))
