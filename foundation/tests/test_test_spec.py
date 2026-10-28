"""Chặng E-spec: the step where tests are written first, and the gate `test-spec-valid` that thanhtan runs itself.

See ``spec_helpers`` for the report format. At `task advance --result pass` the gate checks the report against the
plan, checks the test files are committed, then RUNS every command itself and needs each to fail; what the tester wrote
under `output:` is only for the person to read. The result is kept in `tasks/<task>/verify-red.json`.
`thanhtan tests verify-red` does the same on demand.
"""

import json
import re

import pytest
from checklist_helpers import checklist_path, codes, items, tick
from conftest import git
from sdd_helpers import run, say
from spec_helpers import (
    EXE,
    GATE_FAILED,
    GREEN,
    RED,
    INVALID_INPUT,
    PLAN2,
    FLIP,
    advance,
    at_spec_step,
    block,
    both_red,
    no_test_block,
    spec_report,
    start,
    step_now,
    task_dir,
    verify_red_record,
    write_spec,
)

from thanhtan.constants import ExitCode, GateKind
from thanhtan.errors import ThanhTanError
from thanhtan.workflow import parse_workflow


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    at_spec_step(gitflow_repo, monkeypatch, capsys)
    return gitflow_repo


def refused(capsys) -> str:
    code, _out, err = advance(capsys)
    assert code == GATE_FAILED, err
    return err


# ------------------------------------------------------------------ the workflow knows the gates


def workflow_with(**step):
    data = {
        "schema_version": 1,
        "family": "f",
        "max_rounds": 2,
        "steps": [{"id": "s", "name": "S", "role": "r", "requires_approval": True, **step}],
    }
    return parse_workflow(data, "t")


def test_the_two_new_gates_are_known_kinds():
    assert {str(GateKind.TEST_SPEC_VALID), str(GateKind.TESTS_PASS)} == {"test-spec-valid", "tests-pass"}
    step = workflow_with(gates=["test-spec-valid", "tests-pass"]).steps[0]
    assert [str(g) for g in step.gates] == ["test-spec-valid", "tests-pass"]


def test_spec_items_is_a_known_source_of_checklist_lines():
    step = workflow_with(approval_items=["spec-items"]).steps[0]
    assert [str(i) for i in step.approval_items] == ["spec-items"]


def test_an_unknown_gate_is_still_rejected():
    with pytest.raises(ThanhTanError):
        workflow_with(gates=["test-spec-valids"])


# ------------------------------------------------------------------ the report against the plan


def test_a_report_with_a_block_for_every_plan_item_passes(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    code, out, err = advance(capsys)
    assert code == ExitCode.OK, err
    assert step_now(repo) == ("test-spec", "awaiting_approval")
    assert set(verify_red_record(repo)["results"]) == {"C1", "C2"}


def test_the_gate_names_the_plan_item_that_has_no_block(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it"))
    err = refused(capsys)
    assert "C2" in err
    assert step_now(repo) == ("test-spec", "in_progress")


def test_the_gate_refuses_a_block_for_an_item_that_is_not_in_the_plan(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red(), block("C9", "Ghost"))
    assert "C9" in refused(capsys)


def test_the_gate_refuses_two_blocks_for_the_same_item(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red(), block("C1", "Again"))
    err = refused(capsys)
    assert "C1" in err and "more than once" in err


def test_the_gate_asks_for_the_report_when_there_is_none(repo, capsys):
    err = refused(capsys)
    assert "report" in err and "test-spec" in err


@pytest.mark.parametrize(
    "broken,field",
    [
        (block("C1", "Build it", command=None), "command"),
        (block("C1", "Build it", red=None), "red"),
        (block("C1", "Build it", red="pass"), "red"),
        (block("C1", "Build it", reason=None), "reason"),
        (block("C1", "Build it", reason="   "), "reason"),
        (block("C1", "Build it", output=None), "output"),
    ],
)
def test_a_block_with_tests_must_have_command_red_fail_reason_and_output(repo, monkeypatch, capsys, broken, field):
    write_spec(monkeypatch, broken, block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err and field in err


def test_a_block_may_say_there_is_no_automatic_test_if_it_says_how_the_item_is_checked(repo, monkeypatch, capsys):
    write_spec(monkeypatch, no_test_block("C1", "Build it"), block("C2", "Test it"))
    code, _out, err = advance(capsys)
    assert code == ExitCode.OK, err
    assert verify_red_record(repo)["results"]["C1"]["status"] == "none"


@pytest.mark.parametrize("how", [None, "", "   "])
def test_no_automatic_test_without_a_way_to_check_is_refused(repo, monkeypatch, capsys, how):
    write_spec(monkeypatch, no_test_block("C1", "Build it", how), block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err


def test_an_item_with_no_test_is_not_forced_to_have_one(repo, monkeypatch, capsys):
    write_spec(monkeypatch, no_test_block("C1", "Build it"), no_test_block("C2", "Test it", "open the page"))
    assert advance(capsys)[0] == ExitCode.OK
    record = verify_red_record(repo)
    assert record["results"]["C1"]["status"] == "none"
    assert "run it by hand" in record["results"]["C1"]["reason"]


# ------------------------------------------------------------------ the command must run the tests it names


@pytest.mark.parametrize("command", ["false", "exit 1", "echo nothing", f"{EXE} tests/green.py", f"{EXE} -c \"raise SystemExit(1)\""])
def test_a_command_that_does_not_mention_a_test_file_of_its_item_is_refused(repo, monkeypatch, capsys, command):
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/red.py::test_x", command=command), block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err and "mention" in err
    assert not (task_dir(repo) / "verify-red.json").exists(), "nothing is run for a report that is not in order"


def test_a_command_that_runs_another_test_file_than_the_one_it_declares_is_refused(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/test_a.py::test_x", command=RED), block("C2", "Test it"))
    assert "mention" in refused(capsys)


def test_one_declared_file_is_enough_when_an_item_has_several(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/test_a.py::test_x, tests/flip.py::test_y", command=FLIP), block("C2", "Test it"))
    code, _out, err = advance(capsys)
    assert code == ExitCode.OK, err
    assert verify_red_record(repo)["results"]["C1"]["status"] == "red"


def test_the_path_may_be_written_with_either_kind_of_slash_in_the_command(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/flip.py::test_x", command=FLIP.replace("tests/flip.py", "tests\\flip.py")), block("C2", "Test it"))
    code, _out, err = advance(capsys)
    assert code == ExitCode.OK, err
    assert verify_red_record(repo)["results"]["C1"]["status"] == "red"


def test_the_command_is_shown_to_the_person_because_naming_a_file_is_all_the_gate_can_check(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    advance(capsys)
    assert FLIP in checklist_path(repo, "test-spec").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the test files must exist and be committed


def test_a_test_file_that_does_not_exist_is_refused(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/test_missing.py::test_x"), block("C2", "Test it"))
    err = refused(capsys)
    assert "tests/test_missing.py" in err and "exist" in err


def test_a_test_file_that_is_not_committed_is_refused(repo, monkeypatch, capsys):
    (repo / "tests" / "test_new.py").write_text("def test_n():\n    assert False\n", encoding="utf-8")
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/test_new.py::test_n"), block("C2", "Test it"))
    err = refused(capsys)
    assert "tests/test_new.py" in err and "commit" in err


def test_a_test_file_changed_after_its_commit_is_refused(repo, monkeypatch, capsys):
    (repo / "tests" / "flip.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    write_spec(monkeypatch, *both_red())
    err = refused(capsys)
    assert "tests/flip.py" in err and "commit" in err


def test_a_staged_but_not_committed_test_file_is_refused(repo, monkeypatch, capsys):
    (repo / "tests" / "test_new.py").write_text("def test_n():\n    assert False\n", encoding="utf-8")
    git(repo, "add", "tests/test_new.py")
    write_spec(monkeypatch, block("C1", "Build it", tests="tests/test_new.py::test_n"), block("C2", "Test it"))
    assert "tests/test_new.py" in refused(capsys)


def test_several_tests_of_one_item_are_each_checked(repo, monkeypatch, capsys):
    write_spec(
        monkeypatch,
        block("C1", "Build it", tests="tests/test_a.py::test_x, tests/test_gone.py::test_y"),
        block("C2", "Test it"),
    )
    assert "tests/test_gone.py" in refused(capsys)


@pytest.mark.parametrize("path", ["../outside.py::test_x", "/etc/passwd::test_x", "C:/Windows/win.ini::test_x"])
def test_a_test_path_outside_the_project_is_refused(repo, monkeypatch, capsys, path):
    write_spec(monkeypatch, block("C1", "Build it", tests=path), block("C2", "Test it"))
    assert "C1" in refused(capsys)


# ------------------------------------------------------------------ thanhtan runs the commands itself


def test_a_command_that_passes_is_refused_whatever_the_report_claims(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", command=GREEN, red="fail", output="FAILED tests/test_a.py::test_x"), block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err and "did not fail" in err
    assert step_now(repo) == ("test-spec", "in_progress")


def test_the_refusal_shows_what_the_command_printed(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", command=GREEN), block("C2", "Test it"))
    assert "2 passed" in refused(capsys)


def test_a_command_that_fails_passes_the_gate_and_the_result_is_kept(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    assert advance(capsys)[0] == ExitCode.OK
    record = verify_red_record(repo)
    assert re.fullmatch(r"[0-9a-f]{40}", record["head"])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["at"])
    first = record["results"]["C1"]
    assert first["status"] == "red" and first["exit_code"] == 1 and first["command"] == FLIP
    assert "feature missing" in first["output"]
    assert isinstance(first["duration_seconds"], (int, float))
    assert set(record["results"]) == {"C1", "C2"}


def test_a_report_that_lies_about_the_output_does_not_matter_the_record_is_thanhtans(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", output="everything is fine"), block("C2", "Test it"))
    assert advance(capsys)[0] == ExitCode.OK
    assert "everything is fine" not in verify_red_record(repo)["results"]["C1"]["output"]


def test_a_record_written_by_hand_is_ignored_the_gate_runs_again(repo, monkeypatch, capsys):
    (task_dir(repo)).mkdir(parents=True, exist_ok=True)
    (task_dir(repo) / "verify-red.json").write_text(json.dumps({"head": "0" * 40, "at": "2026-01-01T00:00:00Z", "results": {"C1": {"status": "red", "exit_code": 1}}}), encoding="utf-8")
    write_spec(monkeypatch, block("C1", "Build it", command=GREEN), block("C2", "Test it"))
    assert "did not fail" in refused(capsys)


def test_the_gate_runs_the_commands_at_the_project_root(repo, monkeypatch, capsys):
    where = f'{EXE} tests/where.py'
    write_spec(monkeypatch, block("C1", "Build it", command=where), block("C2", "Test it"))
    assert advance(capsys)[0] == ExitCode.OK
    assert f"CWD={repo}" in verify_red_record(repo)["results"]["C1"]["output"].replace("\\\\", "\\")


def test_a_long_output_is_cut_to_its_tail(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", command=f"{EXE} tests/loud.py"), block("C2", "Test it"))
    assert advance(capsys)[0] == ExitCode.OK
    output = verify_red_record(repo)["results"]["C1"]["output"]
    assert len(output) <= 5000 and output.rstrip().endswith("THE-END")


def test_a_command_that_does_not_exist_is_not_a_red_test(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", command="definitely-not-a-command-xyz tests/red.py"), block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err and ("not found" in err or "cannot run" in err)


def test_a_command_that_runs_too_long_is_refused_with_the_timeout(repo, monkeypatch, capsys):
    run(capsys, "config", "set", "test_timeout_minutes", "0.02")
    write_spec(monkeypatch, block("C1", "Build it", command=f"{EXE} tests/slow.py"), block("C2", "Test it"))
    err = refused(capsys)
    assert "C1" in err and "timed out" in err


def test_the_same_command_for_two_items_is_run_once(repo, monkeypatch, capsys):
    calls = []
    from thanhtan import testrun

    real = testrun.run_command

    def counting(command, *args, **kwargs):
        calls.append(command)
        return real(command, *args, **kwargs)

    monkeypatch.setattr("thanhtan.testrun.run_command", counting)
    write_spec(monkeypatch, *both_red())
    assert advance(capsys)[0] == ExitCode.OK
    assert calls == [FLIP]


def test_the_gate_does_not_run_anything_when_the_step_is_failed_not_passed(repo, monkeypatch, capsys):
    (repo / "tests" / "mark_zero.py").write_text("open('ran.marker', 'a').write('x')\n", encoding="utf-8")
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "marker")
    write_spec(monkeypatch, block("C1", "Build it", command=f"{EXE} tests/mark_zero.py"), block("C2", "Test it"))
    assert run(capsys, "task", "advance", "--result", "fail")[0] == ExitCode.OK
    assert not (repo / "ran.marker").exists()


# ------------------------------------------------------------------ `thanhtan tests verify-red`


def test_verify_red_runs_the_commands_and_keeps_the_same_record(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    code, out, err = run(capsys, "tests", "verify-red")
    assert code == ExitCode.OK, err
    assert "C1" in out and "C2" in out and "red" in out
    assert verify_red_record(repo)["results"]["C1"]["status"] == "red"
    assert step_now(repo) == ("test-spec", "in_progress"), "it never moves the task"


def test_verify_red_fails_with_the_gate_exit_code_when_a_command_passes(repo, monkeypatch, capsys):
    write_spec(monkeypatch, block("C1", "Build it", command=GREEN), block("C2", "Test it"))
    code, out, _err = run(capsys, "tests", "verify-red")
    assert code == GATE_FAILED
    assert "C1" in out and "green" in out


def test_verify_red_outside_the_test_spec_step_is_refused(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    say(monkeypatch, "task", "new", "Do it")
    assert run(capsys, "tests", "verify-red")[0] == INVALID_INPUT


def test_verify_red_without_a_task_is_refused(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    assert run(capsys, "tests", "verify-red")[0] == ExitCode.NO_ACTIVE_TASK


# ------------------------------------------------------------------ the person's checklist for the step


def test_the_checklist_has_a_line_per_plan_item_with_the_command_and_what_thanhtan_saw(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    assert advance(capsys)[0] == ExitCode.OK
    text = checklist_path(repo, "test-spec").read_text(encoding="utf-8")
    assert codes(text) == ["K1", "C1", "C2"]
    lines = {code: line for _b, _o, code, line in items(text)}
    assert "tests/flip.py::test_x" in lines["C1"] and "exit 1" in lines["C1"] and "red" in lines["C1"]
    assert FLIP in lines["C1"]


def test_an_item_with_no_test_shows_up_in_the_checklist_with_its_way_of_checking(repo, monkeypatch, capsys):
    write_spec(monkeypatch, no_test_block("C1", "Build it", "open the page and look"), block("C2", "Test it"))
    assert advance(capsys)[0] == ExitCode.OK
    lines = {code: line for _b, _o, code, line in items(checklist_path(repo, "test-spec").read_text(encoding="utf-8"))}
    assert "không có" in lines["C1"] and "open the page and look" in lines["C1"]


def test_the_step_waits_for_a_person_and_approval_needs_the_ticks(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    advance(capsys)
    assert run(capsys, "task", "approve")[0] == 36
    tick(checklist_path(repo, "test-spec"))
    assert run(capsys, "task", "approve")[0] == ExitCode.OK
    assert step_now(repo) == ("build", "in_progress")


def test_a_small_task_still_waits_for_a_person_at_this_step(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    at_spec_step(gitflow_repo, monkeypatch, capsys, PLAN2, "--size", "small")
    write_spec(monkeypatch, *both_red())
    assert advance(capsys)[0] == ExitCode.OK
    assert step_now(gitflow_repo) == ("test-spec", "awaiting_approval")
    assert checklist_path(gitflow_repo, "test-spec").is_file()


def test_failing_the_step_sends_the_task_back_to_the_plan(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    advance(capsys)
    assert run(capsys, "task", "advance", "--result", "fail")[0] == ExitCode.OK
    assert step_now(repo) == ("plan", "in_progress")


def test_the_report_cannot_be_rewritten_once_the_step_waits_for_approval(repo, monkeypatch, capsys):
    write_spec(monkeypatch, *both_red())
    advance(capsys)
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_report(block("C1", "Changed"))) != ExitCode.OK


# ------------------------------------------------------------------ nothing changes for a workflow without the step


def test_a_workflow_without_the_new_gates_runs_as_before(gitflow_repo, tmp_path, monkeypatch, capsys):
    from sdd_helpers import init_workspace, sample_workflow

    init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)
    say(monkeypatch, "task", "new", "Do it")
    say(monkeypatch, "task", "advance", "--result", "pass")
    assert run(capsys, "task", "approve")[0] == ExitCode.OK
    assert not list(task_dir(gitflow_repo).glob("verify-red.json"))
