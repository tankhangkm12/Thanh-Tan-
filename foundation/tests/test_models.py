import json

from agentflow.constants import StepStatus, TaskStatus, Tool, ToolStatus
from agentflow.models import (
    State,
    ToolCheck,
    config_from_dict,
    config_to_dict,
    state_from_dict,
    state_to_dict,
    workflow_from_dict,
)


def test_workflow_from_dict_applies_defaults(workflow_data):
    workflow = workflow_from_dict(workflow_data)
    assert workflow.max_rounds == 2
    build = workflow.get_step("build")
    assert build is not None
    assert build.requires_approval is False
    assert build.on_fail is None
    check = workflow.get_step("check")
    assert check is not None and check.on_fail == "build"


def test_workflow_steps_run_in_list_order(workflow_data):
    workflow = workflow_from_dict(workflow_data)
    assert workflow.first_step().id == "confirm"
    assert workflow.step_after("confirm").id == "build"
    assert workflow.step_after("check") is None
    assert workflow.get_step("missing") is None


def test_state_round_trip(state_data):
    state = state_from_dict(state_data)
    task = state.active_task()
    assert task is not None
    assert task.status is TaskStatus.OPEN
    assert task.step_status is StepStatus.IN_PROGRESS
    assert task.branch == "feature/thing"
    # Through JSON text, exactly like the file on disk.
    assert json.loads(json.dumps(state_to_dict(state))) == state_data


def test_state_branch_may_be_null(state_data):
    state_data["tasks"][0]["branch"] = None
    task = state_from_dict(state_data).tasks[0]
    assert task.branch is None


def test_empty_state_has_no_active_task():
    state = State()
    assert state.active_task() is None
    assert state.stamped("2026-01-01T00:00:00Z").updated_at == "2026-01-01T00:00:00Z"


def test_config_round_trip(config_data):
    assert config_to_dict(config_from_dict(config_data)) == config_data


def test_tool_check_install_url():
    check = ToolCheck(tool=Tool.UV, status=ToolStatus.MISSING, required=True)
    assert check.install_url.startswith("https://")
