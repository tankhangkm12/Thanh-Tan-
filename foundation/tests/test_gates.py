import pytest
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode

GOOD_PLAN = """### C1 - Build it
- role: builder
- done-when: `pytest`
- docs: không có — internal change
"""


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]  # the "build" step plays the plan step
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])  # now at "build"
    capsys.readouterr()
    return gitflow_repo


def report(monkeypatch, text, step="build"):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert main(["report", "--step", step]) == ExitCode.OK


def test_pass_is_refused_without_a_plan_report(ws, capsys):
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    assert "no plan report" in capsys.readouterr().err


def test_pass_is_refused_for_an_invalid_plan_and_accepted_when_fixed(ws, capsys, monkeypatch):
    report(monkeypatch, "### C1 - x\n- role: wizard\n")
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    err = capsys.readouterr().err
    assert "unknown role 'wizard'" in err and "[plan-valid]" in err
    report(monkeypatch, GOOD_PLAN)
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK


def test_fail_result_ignores_gates(ws, capsys):
    assert main(["task", "advance", "--result", "fail"]) == ExitCode.OK


def test_plan_check_command(ws, capsys, monkeypatch, tmp_path):
    assert main(["plan", "check"]) == ExitCode.PLAN_INVALID  # no report yet
    report(monkeypatch, GOOD_PLAN)
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.OK
    assert "plan ok" in capsys.readouterr().out
    bad = tmp_path / "bad.md"
    bad.write_text("### C1 - x\n- role: builder\n", encoding="utf-8")
    assert main(["plan", "check", "--file", str(bad)]) == ExitCode.PLAN_INVALID
    out = capsys.readouterr().out
    assert "C1: missing 'done-when'" in out and "C1: missing 'docs'" in out


def test_workflow_schema_accepts_known_gates_only(workflow_data):
    from agentflow.constants import GateKind
    from agentflow.workflow import parse_workflow

    workflow_data["steps"][1]["gates"] = ["plan-valid", "scans-clean"]
    assert parse_workflow(workflow_data, "x").steps[1].gates == (GateKind.PLAN_VALID, GateKind.SCANS_CLEAN)
    workflow_data["steps"][1]["gates"] = ["made-up"]
    with pytest.raises(Exception, match="gates"):
        parse_workflow(workflow_data, "x")
