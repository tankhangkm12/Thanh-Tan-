import pytest
from conftest import write_workflow

from agentflow.constants import DriftStatus, ExitCode, StepStatus, SyncOutcome, TaskStatus
from agentflow.errors import AgentflowError
from agentflow.models import State, Task
from agentflow.state import JsonStateStore
from agentflow.sync import sync_workflow, workflow_drift
from agentflow.workspace import init_workspace, load_config, load_workspace_workflow


@pytest.fixture
def paths(git_repo, workflow_file):
    return init_workspace(git_repo, workflow_file).paths


STEP_STATUS_FOR = {
    TaskStatus.OPEN: StepStatus.IN_PROGRESS,
    TaskStatus.BLOCKED: StepStatus.FAILED,
    TaskStatus.DONE: StepStatus.PASSED,
}


def put_task(paths, status=TaskStatus.OPEN, step="build"):
    store = JsonStateStore(paths.dir, load_workspace_workflow(paths))
    task = Task("T-001", "t", status, step, STEP_STATUS_FOR[status])
    active = "T-001" if status in (TaskStatus.OPEN, TaskStatus.BLOCKED) else None
    store.save(State(active_task_id=active, tasks=(task,)))


def change_source(workflow_file, workflow_data, name="Build v2"):
    workflow_data["steps"][1]["name"] = name
    write_workflow(workflow_file, workflow_data)


def test_drift_states(paths, workflow_file, workflow_data):
    assert workflow_drift(load_config(paths)) is DriftStatus.IN_SYNC
    change_source(workflow_file, workflow_data)
    assert workflow_drift(load_config(paths)) is DriftStatus.SOURCE_CHANGED
    workflow_file.unlink()
    assert workflow_drift(load_config(paths)) is DriftStatus.SOURCE_MISSING


def test_sync_unchanged(paths, git_repo):
    assert sync_workflow(git_repo).outcome is SyncOutcome.UNCHANGED


def test_sync_updates_copy_config_and_state_md(paths, git_repo, workflow_file, workflow_data):
    change_source(workflow_file, workflow_data)
    result = sync_workflow(git_repo)
    assert result.outcome is SyncOutcome.UPDATED
    assert paths.workflow_copy.read_bytes() == workflow_file.read_bytes()
    assert workflow_drift(load_config(paths)) is DriftStatus.IN_SYNC
    assert load_workspace_workflow(paths).get_step("build").name == "Build v2"


def test_sync_rejects_invalid_source_and_keeps_copy(paths, git_repo, workflow_file, workflow_data):
    before = paths.workflow_copy.read_bytes()
    workflow_data["steps"][2]["on_fail"] = "ghost"
    write_workflow(workflow_file, workflow_data)
    with pytest.raises(AgentflowError) as exc:
        sync_workflow(git_repo)
    assert exc.value.code is ExitCode.INVALID_WORKFLOW
    assert paths.workflow_copy.read_bytes() == before


def test_sync_rejects_other_family(paths, git_repo, workflow_file, workflow_data):
    workflow_data["family"] = "other"
    write_workflow(workflow_file, workflow_data)
    with pytest.raises(AgentflowError) as exc:
        sync_workflow(git_repo)
    assert exc.value.code is ExitCode.WORKFLOW_MISMATCH


def test_sync_missing_source(paths, git_repo, workflow_file):
    workflow_file.unlink()
    with pytest.raises(AgentflowError) as exc:
        sync_workflow(git_repo)
    assert exc.value.code is ExitCode.WORKFLOW_NOT_FOUND
    assert paths.workflow_copy.is_file()


@pytest.mark.parametrize("status", [TaskStatus.OPEN, TaskStatus.BLOCKED])
def test_sync_blocked_by_in_flight_task(paths, git_repo, workflow_file, workflow_data, status):
    put_task(paths, status)
    before = paths.workflow_copy.read_bytes()
    change_source(workflow_file, workflow_data)
    with pytest.raises(AgentflowError) as exc:
        sync_workflow(git_repo)
    assert exc.value.code is ExitCode.SYNC_BLOCKED
    assert "T-001 at 'build'" in str(exc.value)
    assert paths.workflow_copy.read_bytes() == before


def test_force_sync_with_in_flight_task(paths, git_repo, workflow_file, workflow_data):
    put_task(paths)
    change_source(workflow_file, workflow_data)
    result = sync_workflow(git_repo, force=True)
    assert result.outcome is SyncOutcome.UPDATED
    assert result.forced_task_ids == ("T-001",)


def test_force_cannot_strand_a_task(paths, git_repo, workflow_file, workflow_data):
    put_task(paths, step="build")
    workflow_data["steps"][1]["id"] = "compile"
    workflow_data["steps"][2]["on_fail"] = "compile"
    write_workflow(workflow_file, workflow_data)
    with pytest.raises(AgentflowError) as exc:
        sync_workflow(git_repo, force=True)
    assert exc.value.code is ExitCode.SYNC_BLOCKED
    assert "drops steps" in str(exc.value)


def test_finished_tasks_do_not_block_sync(paths, git_repo, workflow_file, workflow_data):
    put_task(paths, TaskStatus.DONE)
    change_source(workflow_file, workflow_data)
    assert sync_workflow(git_repo).outcome is SyncOutcome.UPDATED
