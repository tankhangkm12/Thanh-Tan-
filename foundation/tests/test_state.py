import json

import pytest

from agentflow.constants import ExitCode, StepStatus, TaskStatus
from agentflow.errors import AgentflowError
from agentflow.interfaces import StateStore
from agentflow.models import State, Task, state_from_dict, workflow_from_dict
from agentflow.state import GENERATED_NOTE, JsonStateStore, render_state_md

FIXED_TIME = "2026-10-10T09:00:00Z"


@pytest.fixture
def workflow(workflow_data):
    return workflow_from_dict(workflow_data)


@pytest.fixture
def store(tmp_path, workflow):
    return JsonStateStore(tmp_path, workflow, clock=lambda: FIXED_TIME)


def test_store_implements_protocol(store):
    assert isinstance(store, StateStore)


def test_save_then_load_round_trip(store, state_data, tmp_path):
    written = store.save(state_from_dict(state_data))
    assert written.updated_at == FIXED_TIME
    assert store.load() == written
    on_disk = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert on_disk["tasks"][0]["branch"] == "feature/thing"


def test_save_regenerates_state_md(store, state_data, tmp_path):
    store.save(state_from_dict(state_data))
    md_path = tmp_path / "STATE.md"
    md_path.write_text("edited by hand", encoding="utf-8")
    store.save(store.load())
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith(GENERATED_NOTE)
    assert "edited by hand" not in text


def test_load_missing_file_means_no_workspace(store):
    with pytest.raises(AgentflowError) as exc:
        store.load()
    assert exc.value.code is ExitCode.NO_WORKSPACE


def test_load_rejects_broken_json(store, tmp_path):
    (tmp_path / "state.json").write_text("{", encoding="utf-8")
    with pytest.raises(AgentflowError) as exc:
        store.load()
    assert exc.value.code is ExitCode.INVALID_STATE


def test_load_rejects_schema_violation(store, state_data, tmp_path):
    del state_data["tasks"][0]["branch"]
    (tmp_path / "state.json").write_text(json.dumps(state_data), encoding="utf-8")
    with pytest.raises(AgentflowError) as exc:
        store.load()
    assert exc.value.code is ExitCode.INVALID_STATE


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d["tasks"].append(dict(d["tasks"][0])), "duplicate task id 'T-001'"),
        (lambda d: d.update(active_task_id="T-999"), "matches no task"),
        (lambda d: d["tasks"][0].update(current_step="ghost"), "step 'ghost' is not in workflow"),
        (lambda d: d["tasks"][0].update(status="done"), "active task T-001 is done"),
        (lambda d: d["tasks"][0].update(step_status="failed"), "'failed' does not fit task status 'open'"),
        (lambda d: d["tasks"][0].update(status="blocked"), "'in_progress' does not fit task status 'blocked'"),
    ],
)
def test_save_refuses_invalid_state_and_writes_nothing(store, state_data, tmp_path, mutate, expected):
    mutate(state_data)
    with pytest.raises(AgentflowError) as exc:
        store.save(state_from_dict(state_data))
    assert exc.value.code is ExitCode.INVALID_STATE
    assert expected in str(exc.value)
    assert not (tmp_path / "state.json").exists()


def test_finished_task_may_sit_on_a_dropped_step(store, state_data):
    state_data["tasks"][0].update(current_step="gone", status="done", step_status="passed")
    state_data["active_task_id"] = None
    store.save(state_from_dict(state_data))
    assert store.load().tasks[0].current_step == "gone"


def test_render_empty_state(workflow):
    text = render_state_md(State(), workflow)
    assert "- Active task: none" in text
    assert "- Next: start a new task at step 'confirm'" in text
    assert "No tasks yet." in text


def test_render_active_task(workflow, state_data):
    text = render_state_md(state_from_dict(state_data), workflow)
    assert "- Active task: T-001 Do the thing" in text
    assert "- Branch: feature/thing" in text
    assert "- Rework rounds: 1/2" in text
    assert "- Next: work on step 'build' (Build; role builder), rework round 1/2" in text
    assert "| T-001 | Do the thing | open | build | in_progress | feature/thing |" in text


def test_render_escapes_pipes_in_titles(workflow):
    task = Task("T-002", "a | b", TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS)
    text = render_state_md(State(active_task_id="T-002", tasks=(task,)), workflow)
    assert "a \\| b" in text
