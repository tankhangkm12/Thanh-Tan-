import copy
import io

import pytest
from conftest import SAMPLE_WORKFLOW, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode, StepStatus, TaskEvent, TaskStatus
from agentflow.engine import needs_approval, start_task, transition
from agentflow.models import state_from_dict, state_to_dict, workflow_from_dict
from agentflow.plan import check_plan, parse_plan
from agentflow.plan_rules import MaxPlanItemsRule
from agentflow.projectcontext import ProjectContext, RoleSet
from agentflow.scan import all_tools, tools_for_step
from agentflow.workflow import parse_workflow

SIZES = {
    "default": "normal",
    "profiles": {
        "normal": {},
        "small": {"skip_approval": ["confirm2"], "max_plan_items": 3, "scans": {"check": ["gitleaks", "semgrep"]}},
    },
}


def workflow_data(**changes):
    data = copy.deepcopy(SAMPLE_WORKFLOW)
    data["steps"] = [
        {"id": "confirm", "name": "Confirm", "role": "lead", "requires_approval": True},
        {"id": "confirm2", "name": "Plan", "role": "lead", "requires_approval": True, "gates": ["plan-valid"]},
        {"id": "build", "name": "Build", "role": "builder"},
        {"id": "check", "name": "Check", "role": "checker", "on_fail": "build", "gates": ["scans-clean"]},
    ]
    data["sizes"] = copy.deepcopy(SIZES)
    data.update(changes)
    return data


# ------------------------------------------------------------------ the workflow


def test_a_workflow_may_define_sizes():
    workflow = parse_workflow(workflow_data(), "w")
    assert workflow.default_size == "normal" and [p.id for p in workflow.sizes] == ["normal", "small"]
    small = workflow.size_profile("small")
    assert small.skip_approval == ("confirm2",) and small.max_plan_items == 3 and small.scans == {"check": ("gitleaks", "semgrep")}
    assert workflow.size_profile("normal") is not None and workflow.size_profile("huge") is None and workflow.size_profile(None) is None


def test_a_workflow_without_sizes_has_none():
    workflow = parse_workflow(copy.deepcopy(SAMPLE_WORKFLOW), "w")
    assert workflow.sizes == () and workflow.default_size is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.update(default="huge"), "default 'huge'"),
        (lambda s: s["profiles"]["small"].update(skip_approval=["build"]), "skip_approval 'build'"),
        (lambda s: s["profiles"]["small"].update(scans={"ghost": ["x"]}), "step 'ghost'"),
        (lambda s: s["profiles"]["small"].update(max_plan_items=0), "invalid workflow"),
        (lambda s: s["profiles"]["small"].update(colour="red"), "invalid workflow"),
    ],
)
def test_sizes_are_checked(change, message):
    data = workflow_data()
    change(data["sizes"])
    with pytest.raises(Exception, match=message):
        parse_workflow(data, "w")


# ------------------------------------------------------------------ the task


def test_a_task_keeps_its_size_in_the_state():
    workflow = workflow_from_dict(workflow_data())
    task = start_task(workflow, "T-001", "t", "feature/t", "2026-01-01T00:00:00Z", "small")
    assert task.size == "small"
    state = state_to_dict(state_from_dict({"schema_version": 1, "updated_at": None, "active_task_id": "T-001", "tasks": [state_to_dict_task(task)]}))
    assert state["tasks"][0]["size"] == "small"


def state_to_dict_task(task):
    from agentflow.models import State

    return state_to_dict(State(tasks=(task,)))["tasks"][0]


def test_a_task_without_a_size_writes_no_size_and_old_state_still_loads():
    workflow = workflow_from_dict(workflow_data())
    task = start_task(workflow, "T-001", "t", None, "2026-01-01T00:00:00Z")
    assert "size" not in state_to_dict_task(task)


def test_small_skips_the_approval_of_the_listed_steps_only():
    workflow = workflow_from_dict(workflow_data())
    for size, plan_waits in (("normal", True), ("small", False)):
        task = start_task(workflow, "T-001", "t", None, "2026-01-01T00:00:00Z", size)
        task = transition(workflow, task, TaskEvent.PASS, "t")  # confirm
        assert task.step_status is StepStatus.AWAITING_APPROVAL, size  # confirm always needs a person
        task = transition(workflow, task, TaskEvent.APPROVE, "t")
        task = transition(workflow, task, TaskEvent.PASS, "t")  # the plan step
        assert (task.step_status is StepStatus.AWAITING_APPROVAL) is plan_waits, size
        assert task.current_step == ("confirm2" if plan_waits else "build"), size
        assert task.status is TaskStatus.OPEN


def test_needs_approval_follows_the_size():
    workflow = workflow_from_dict(workflow_data())
    step = workflow.get_step("confirm2")
    assert needs_approval(workflow, start_task(workflow, "T-001", "t", None, "t", "normal"), step)
    assert not needs_approval(workflow, start_task(workflow, "T-001", "t", None, "t", "small"), step)
    assert not needs_approval(workflow, start_task(workflow, "T-001", "t", None, "t", "small"), workflow.get_step("build"))


# ------------------------------------------------------------------ the plan


def items(count):
    return "".join(f"### C{n} - item {n}\n- role: builder\n- done-when: ok\n- docs: không có — x\n\n" for n in range(1, count + 1))


class Roles:
    def roles(self):
        return {"builder"}


def test_a_small_plan_has_at_most_the_allowed_number_of_items():
    rule = MaxPlanItemsRule(3, "small")
    assert check_plan(parse_plan(items(3)), Roles(), wide_rules=[rule]) == []
    found = [str(p) for p in check_plan(parse_plan(items(4)), Roles(), wide_rules=[rule])]
    assert len(found) == 1 and "4 items" in found[0] and "small" in found[0] and "at most 3" in found[0]


# ------------------------------------------------------------------ the scans


class Tool:
    def __init__(self, id, step=None):
        self.id, self.step = id, step


def test_a_size_limits_the_scan_tools_of_a_step(monkeypatch):
    from agentflow import scan

    workflow = workflow_from_dict(workflow_data())
    tools = [Tool("semgrep"), Tool("trivy"), Tool("gitleaks"), Tool("semgrep-conventions")]
    monkeypatch.setattr(scan, "BUILTIN_TOOLS", tools)
    normal = ProjectContext(RoleSet(frozenset()))
    small = ProjectContext(RoleSet(frozenset()), scan_filter={"check": ("gitleaks", "semgrep")})
    assert [t.id for t in tools_for_step("check", workflow, normal)] == ["semgrep", "trivy", "gitleaks", "semgrep-conventions"]
    assert [t.id for t in tools_for_step("check", workflow, small)] == ["semgrep", "gitleaks"]
    assert [t.id for t in all_tools(workflow, small)] == ["semgrep", "gitleaks"]
    assert [t.id for t in tools_for_step("build", workflow, small)] == []  # not a scan step


def test_extension_tools_of_another_step_are_not_limited_by_a_filter_for_this_step(monkeypatch):
    from agentflow import scan

    workflow = workflow_from_dict(workflow_data())
    monkeypatch.setattr(scan, "BUILTIN_TOOLS", [Tool("semgrep")])
    project = ProjectContext(RoleSet(frozenset()), scan_tools=(Tool("squawk", "build"),), scan_filter={"check": ("semgrep",)})
    assert [t.id for t in tools_for_step("build", workflow, project)] == ["squawk"]


# ------------------------------------------------------------------ the commands


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", workflow_data())
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def test_task_new_takes_a_size_and_says_which(ws, capsys):
    assert main(["task", "new", "tiny fix", "--size", "small"]) == ExitCode.OK
    assert "(size small)" in capsys.readouterr().out
    main(["status"])
    assert "size: small" in capsys.readouterr().out
    assert "- Size: small" in (ws / ".ThanhTan" / "STATE.md").read_text(encoding="utf-8")


def test_the_default_size_is_the_workflows(ws, capsys):
    assert main(["task", "new", "usual"]) == ExitCode.OK
    assert "(size normal)" in capsys.readouterr().out


def test_an_unknown_size_is_refused_and_no_task_is_made(ws, capsys):
    assert main(["task", "new", "x", "--size", "huge"]) == ExitCode.INVALID_INPUT
    assert "unknown size 'huge'" in capsys.readouterr().err
    main(["status"])
    assert "active task: none" in capsys.readouterr().out


def test_a_workflow_without_sizes_refuses_a_size(gitflow_repo, tmp_path, monkeypatch, capsys):
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", copy.deepcopy(SAMPLE_WORKFLOW))
    monkeypatch.chdir(gitflow_repo)
    main(["init", "--workflow", str(path)])
    assert main(["task", "new", "x", "--size", "small"]) == ExitCode.INVALID_INPUT
    assert main(["task", "new", "x"]) == ExitCode.OK


def test_a_small_task_skips_plan_approval_but_the_plan_check_still_runs(ws, monkeypatch, capsys):
    main(["task", "new", "tiny", "--size", "small"])
    main(["task", "advance", "--result", "pass"])  # confirm
    main(["task", "approve"])
    monkeypatch.setattr("sys.stdin", io.StringIO(items(4)))
    main(["report", "--step", "confirm2"])
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.PLAN_INVALID
    assert "at most 3" in capsys.readouterr().out
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED  # the gate refuses the long plan
    monkeypatch.setattr("sys.stdin", io.StringIO(items(2)))
    main(["report", "--step", "confirm2"])
    capsys.readouterr()
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "step 'build'" in out and "wait for a person" not in out


def test_a_normal_task_still_waits_for_plan_approval(ws, monkeypatch, capsys):
    main(["task", "new", "usual", "--size", "normal"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])
    monkeypatch.setattr("sys.stdin", io.StringIO(items(5)))
    main(["report", "--step", "confirm2"])
    capsys.readouterr()
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK
    assert "awaiting_approval" in capsys.readouterr().out
