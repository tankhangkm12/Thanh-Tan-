import hashlib

import pytest
import yaml

from agentflow.constants import ExitCode
from agentflow.errors import AgentflowError
from agentflow.interfaces import WorkflowSource
from agentflow.workflow import FileWorkflowSource, load_workflow, parse_workflow


def write_yaml(tmp_path, data, name="workflow.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_load_valid_workflow(tmp_path, workflow_data):
    workflow = load_workflow(write_yaml(tmp_path, workflow_data))
    assert workflow.family == "sample"
    assert [step.id for step in workflow.steps] == ["confirm", "build", "check"]


def test_missing_file(tmp_path):
    with pytest.raises(AgentflowError) as exc:
        load_workflow(tmp_path / "nope.yaml")
    assert exc.value.code is ExitCode.WORKFLOW_NOT_FOUND


def test_broken_yaml(tmp_path):
    path = tmp_path / "workflow.yaml"
    path.write_text("steps: [unclosed", encoding="utf-8")
    with pytest.raises(AgentflowError) as exc:
        load_workflow(path)
    assert exc.value.code is ExitCode.INVALID_WORKFLOW


def test_schema_violation_lists_location(workflow_data):
    del workflow_data["steps"][0]["role"]
    with pytest.raises(AgentflowError) as exc:
        parse_workflow(workflow_data, origin="w.yaml")
    assert exc.value.code is ExitCode.INVALID_WORKFLOW
    assert "steps/0" in str(exc.value)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d["steps"][1].update(id="confirm"), "duplicate step id 'confirm'"),
        (lambda d: d["steps"][2].update(on_fail="ghost"), "on_fail 'ghost' does not exist"),
        (lambda d: d["steps"][2].update(on_fail="check"), "on_fail 'check' must be an earlier step"),
        (lambda d: d["steps"][1].update(on_fail="check"), "on_fail 'check' must be an earlier step"),
    ],
)
def test_reference_problems(workflow_data, mutate, expected):
    mutate(workflow_data)
    with pytest.raises(AgentflowError) as exc:
        parse_workflow(workflow_data, origin="w.yaml")
    assert expected in str(exc.value)


def test_file_source_implements_protocol(tmp_path, workflow_data):
    path = write_yaml(tmp_path, workflow_data)
    source = FileWorkflowSource(path)
    assert isinstance(source, WorkflowSource)
    assert source.load().family == "sample"
    assert source.fingerprint() == hashlib.sha256(path.read_bytes()).hexdigest()
