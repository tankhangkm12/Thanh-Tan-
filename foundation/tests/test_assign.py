import io

import pytest
from conftest import SAMPLE_WORKFLOW, write_workflow

from agentflow.assign import WorkflowAgentNames, assignment_lines
from agentflow.cli import main
from agentflow.constants import ExitCode
from agentflow.interfaces import AgentNames
from agentflow.plan import parse_plan
from agentflow.workflow import parse_workflow


def test_names_implement_the_protocol():
    assert isinstance(WorkflowAgentNames(()), AgentNames)


def test_a_tiered_role_has_an_agent_per_tier_and_others_have_one():
    names = WorkflowAgentNames(["builder"])
    assert names.agent_for("builder", "fast") == "builder-fast"
    assert names.agent_for("builder", "deep") == "builder-deep"
    assert names.agent_for("db-engineer", "fast") == "db-engineer"


def test_lines_name_the_agent_of_each_item_and_a_missing_tier_is_deep():
    plan = parse_plan(
        "### C1 - a\n- role: builder\n- tier: fast\n- done-when: ok\n- docs: không có — x\n"
        "### C2 - b\n- role: builder\n- done-when: ok\n- docs: không có — x\n"
        "### C3 - c\n- role: db-engineer\n- tier: fast\n- done-when: ok\n- docs: không có — x\n"
    )
    assert assignment_lines(plan.items, WorkflowAgentNames(["builder"])) == [
        "C1 builder fast builder-fast",
        "C2 builder deep builder-deep",
        "C3 db-engineer fast db-engineer",
    ]


def test_the_workflow_may_name_tiered_roles_and_they_must_be_step_roles():
    data = {**SAMPLE_WORKFLOW, "tiered_roles": ["builder"]}
    assert parse_workflow(data, "w").tiered_roles == ("builder",)
    with pytest.raises(Exception, match="tiered role 'ghost'"):
        parse_workflow({**SAMPLE_WORKFLOW, "tiered_roles": ["ghost"]}, "w")


PLAN = """### C1 - Quick
- role: builder
- tier: fast
- done-when: `pytest`
- docs: không có — internal

### C2 - Hard
- role: builder
- done-when: `pytest`
- docs: không có — internal
"""


def test_plan_assign_prints_one_line_per_item(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "tiered_roles": ["builder"], "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]  # "build" plays the plan step
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    assert main(["plan", "assign"]) != ExitCode.OK  # no task yet
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])
    monkeypatch.setattr("sys.stdin", io.StringIO(PLAN))
    main(["report", "--step", "build"])
    capsys.readouterr()
    assert main(["plan", "assign"]) == ExitCode.OK
    assert capsys.readouterr().out.splitlines() == ["C1 builder fast builder-fast", "C2 builder deep builder-deep"]
