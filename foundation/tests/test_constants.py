from enum import Enum

import pytest

from agentflow import constants as c

ENUMS = [
    c.ExitCode,
    c.TaskStatus,
    c.StepStatus,
    c.HistoryEvent,
    c.ActionKind,
    c.DriftStatus,
    c.SyncOutcome,
    c.Tool,
    c.ToolStatus,
    c.Command,
    c.WorkflowCommand,
    c.WorkflowKey,
    c.StateKey,
    c.ConfigKey,
    c.TaskType,
    c.TaskEvent,
    c.TaskCommand,
    c.GuardDecision,
    c.GuardRule,
    c.GuardKey,
]


@pytest.mark.parametrize("enum_cls", ENUMS)
def test_enum_values_are_unique_and_non_empty(enum_cls: type[Enum]):
    values = [member.value for member in enum_cls]
    assert len(values) == len(set(values))
    assert all(value != "" for value in values)


def test_exit_code_ok_is_zero_and_others_are_not():
    assert c.ExitCode.OK == 0
    assert all(code != 0 for code in c.ExitCode if code is not c.ExitCode.OK)


def test_every_tool_has_an_https_install_url():
    assert set(c.INSTALL_URLS) == set(c.Tool)
    assert all(url.startswith("https://") for url in c.INSTALL_URLS.values())


def test_required_and_container_tools_cover_all_tools_once():
    assert set(c.REQUIRED_TOOLS).isdisjoint(c.CONTAINER_TOOLS)
    assert set(c.REQUIRED_TOOLS) | set(c.CONTAINER_TOOLS) == set(c.Tool)


def test_workspace_layout_names():
    assert c.EXCLUDE_ENTRY == c.WORKSPACE_DIR + "/"
    names = [c.STATE_FILE, c.STATE_MD_FILE, c.CONFIG_FILE, c.WORKFLOW_COPY_FILE, *c.WORKSPACE_SUBDIRS]
    assert len(names) == len(set(names))


def test_every_task_type_has_a_protected_base_branch():
    assert set(c.TASK_BASE_BRANCH) == set(c.TaskType)
    assert set(c.TASK_BASE_BRANCH.values()) == c.PROTECTED_BRANCHES
    assert c.TASK_BASE_BRANCH[c.TaskType.HOTFIX] == c.MAIN_BRANCH


def test_step_results_are_task_events():
    assert set(c.STEP_RESULTS) <= set(c.TaskEvent)
    assert c.TaskEvent.APPROVE not in c.STEP_RESULTS


def test_gitleaks_image_is_pinned():
    name, _, tag = c.GITLEAKS_IMAGE.rpartition(":")
    assert name and tag and tag != "latest"


def test_leaks_exit_code_differs_from_success_and_gitleaks_errors():
    assert c.GITLEAKS_LEAKS_EXIT_CODE not in (0, 1)


def test_in_flight_statuses_are_task_statuses():
    assert c.IN_FLIGHT_TASK_STATUSES <= set(c.TaskStatus)
    assert c.TaskStatus.DONE not in c.IN_FLIGHT_TASK_STATUSES
