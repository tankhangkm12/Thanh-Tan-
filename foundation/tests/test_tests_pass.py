"""Chặng E-spec: the gate `tests-pass`. agentflow runs the project's test command itself; the agent cannot say "pass".

The command: setting `test_command` (`agentflow config set test_command "..."`) wins; else the line
`- test-command: <command>` of `project/profile.md`, but only while a person has confirmed the profile. Timeout:
setting `test_timeout_minutes`, default 15. No command: the step is blocked with instructions, except for a task whose
plan items are all `kind: other` (then a warning). The result goes to `tasks/<task>/tests-pass.json`.
"""

import json
import re

import pytest
from conftest import git
from sdd_helpers import run, say
from spec_helpers import (
    EXE,
    FLIP,
    GATE_FAILED,
    GREEN,
    PLAN2,
    PLAN_MIXED,
    PLAN_OTHER,
    RED,
    at_test_step,
    block,
    no_test_block,
    profile_with,
    set_config,
    start,
    step_now,
    task_dir,
    tests_pass_record,
    write_profile,
)

from agentflow.constants import ExitCode


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    return gitflow_repo


def passing(capsys) -> tuple[int, str, str]:
    return run(capsys, "task", "advance", "--result", "pass")


# ------------------------------------------------------------------ where the command comes from


def test_the_test_command_setting_is_run_and_a_pass_is_kept(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    code, _out, err = passing(capsys)
    assert code == ExitCode.OK, err
    record = tests_pass_record(repo)
    assert record["status"] == "pass" and record["exit_code"] == 0 and record["source"] == "config"
    assert record["command"] == GREEN and "2 passed" in record["output"]
    assert re.fullmatch(r"[0-9a-f]{40}", record["head"])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["at"])
    assert isinstance(record["duration_seconds"], (int, float))


def test_a_failing_command_blocks_the_step_and_shows_why(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", RED)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED
    assert "tests-pass" in err and "exit 1" in err and "feature missing" in err
    assert step_now(repo) == ("check", "in_progress")
    record = tests_pass_record(repo)
    assert record["status"] == "fail" and record["exit_code"] == 1


def test_the_profile_line_is_used_when_the_profile_is_confirmed(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, profile_with(GREEN), capsys=capsys)
    assert passing(capsys)[0] == ExitCode.OK
    assert tests_pass_record(repo)["source"] == "profile"


def test_a_profile_nobody_confirmed_gives_no_command(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, profile_with(GREEN), confirm=False)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED
    assert "agentflow project confirm profile" in err


def test_a_profile_changed_after_it_was_confirmed_gives_no_command(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, profile_with(GREEN), capsys=capsys)
    write_profile(repo, profile_with(f"{EXE} tests/mark_ok.py"), confirm=False)
    assert passing(capsys)[0] == GATE_FAILED
    assert not (repo / "ran.marker").exists()


def test_the_setting_wins_over_the_profile(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, profile_with(RED), capsys=capsys)
    set_config(capsys, "test_command", GREEN)
    assert passing(capsys)[0] == ExitCode.OK
    assert tests_pass_record(repo)["source"] == "config"


@pytest.mark.parametrize(
    "line,expected",
    [
        ("- test-command: `{cmd}`", True),
        ("- test-command: {cmd}", True),
        ("  - test-command:   `{cmd}`  ", True),
    ],
)
def test_the_profile_line_may_or_may_not_use_backticks(repo, monkeypatch, capsys, line, expected):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, "# Profile\n\n" + line.format(cmd=GREEN) + "\n", capsys=capsys)
    assert (passing(capsys)[0] == ExitCode.OK) is expected
    assert tests_pass_record(repo)["source"] == "profile" and tests_pass_record(repo)["command"] == GREEN


def test_a_line_inside_a_code_block_of_the_profile_is_not_the_command(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, f"# Profile\n\n```\n- test-command: {GREEN}\n```\n", capsys=capsys)
    assert passing(capsys)[0] == GATE_FAILED


def test_two_test_command_lines_in_the_profile_are_ambiguous_and_give_no_command(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    write_profile(repo, f"# Profile\n\n- test-command: {GREEN}\n- test-command: {RED}\n", capsys=capsys)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "more than one" in err


# ------------------------------------------------------------------ no command


def test_without_any_command_the_step_is_blocked_with_the_two_ways_to_give_one(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED
    assert "agentflow config set test_command" in err
    assert "test-command" in err and "agentflow project confirm profile" in err
    assert step_now(repo) == ("check", "in_progress")


def test_a_task_whose_plan_items_are_all_other_only_gets_a_warning(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, PLAN_OTHER, blocks=(no_test_block("C1", "Write the guide"),))
    code, _out, err = passing(capsys)
    assert code == ExitCode.OK
    assert "no test command" in err.lower() and "warning" in err.lower()
    record = tests_pass_record(repo)
    assert record["status"] == "skipped" and record["source"] == "none"


def test_one_item_that_is_not_other_blocks_again(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, PLAN_MIXED, blocks=(no_test_block("C1", "Write the guide"), block("C2", "Code it")))
    assert passing(capsys)[0] == GATE_FAILED


def test_other_items_do_not_excuse_a_command_that_exists_and_fails(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, PLAN_OTHER, blocks=(no_test_block("C1", "Write the guide"),))
    set_config(capsys, "test_command", RED)
    assert passing(capsys)[0] == GATE_FAILED


# ------------------------------------------------------------------ the agent cannot say "pass"


def test_a_report_that_says_everything_passed_changes_nothing(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", RED)
    assert say(monkeypatch, "report", "--step", "check", text="# Check\n\nAll 120 tests passed.\n") == ExitCode.OK
    assert passing(capsys)[0] == GATE_FAILED


def test_a_result_file_written_by_hand_is_ignored_and_overwritten(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", RED)
    (task_dir(repo) / "tests-pass.json").write_text(json.dumps({"status": "pass", "exit_code": 0, "head": "0" * 40}), encoding="utf-8")
    assert passing(capsys)[0] == GATE_FAILED
    assert tests_pass_record(repo)["status"] == "fail"


def test_the_command_is_run_again_on_every_pass_attempt(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/mark.py")
    passing(capsys)
    passing(capsys)
    assert (repo / "ran.marker").read_text(encoding="utf-8") == "xx"


def test_failing_the_step_does_not_run_the_tests(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/mark.py")
    assert run(capsys, "task", "advance", "--result", "fail")[0] == ExitCode.OK
    assert not (repo / "ran.marker").exists()


# ------------------------------------------------------------------ red before, green after: the commands of the test-spec run again


def test_the_commands_of_the_test_spec_run_again_and_both_results_are_kept(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    code, _out, err = passing(capsys)
    assert code == ExitCode.OK, err
    record = tests_pass_record(repo)
    assert record["status"] == "pass" and record["command"] == GREEN
    for code_ in ("C1", "C2"):
        result = record["spec_results"][code_]
        assert result["command"] == FLIP and result["exit_code"] == 0 and result["status"] == "green"
    assert "2 passed" in record["spec_results"]["C1"]["output"]


def test_an_item_whose_own_command_is_still_red_blocks_the_step_even_when_the_project_suite_is_green(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, built=False)
    set_config(capsys, "test_command", GREEN)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED
    assert "C1" in err and "C2" in err and "still fails" in err
    record = tests_pass_record(repo)
    assert record["status"] == "fail"
    assert record["exit_code"] == 0, "the project command's own result is kept apart from the items'"
    assert record["spec_results"]["C1"]["exit_code"] == 1 and record["spec_results"]["C1"]["status"] == "red"


def test_one_item_still_red_among_green_ones_is_named_alone(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, blocks=(block("C1", "Build it"), block("C2", "Test it", command=f"{EXE} tests/red.py")))
    set_config(capsys, "test_command", GREEN)
    err = passing(capsys)[2]
    assert "C2" in err and "C1" not in err


def test_an_item_with_no_automatic_test_is_listed_but_not_run(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys, blocks=(no_test_block("C1", "Build it"), block("C2", "Test it")))
    set_config(capsys, "test_command", GREEN)
    assert passing(capsys)[0] == ExitCode.OK
    record = tests_pass_record(repo)
    assert record["spec_results"]["C1"]["status"] == "none" and "exit_code" not in record["spec_results"]["C1"]
    assert record["spec_results"]["C2"]["status"] == "green"


def test_a_verify_red_file_edited_to_hide_a_command_is_caught_against_the_approved_report(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    path = task_dir(repo) / "verify-red.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"]["C1"]["command"] = GREEN  # a command that always passes
    path.write_text(json.dumps(data), encoding="utf-8")
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "verify-red.json" in err and "C1" in err


def test_a_verify_red_file_that_lost_an_item_is_caught(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    path = task_dir(repo) / "verify-red.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["results"]["C2"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert passing(capsys)[0] == GATE_FAILED


def test_a_missing_verify_red_file_blocks_the_step_of_a_workflow_that_has_a_test_spec(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    (task_dir(repo) / "verify-red.json").unlink()
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "verify-red.json" in err


def test_a_workflow_without_a_test_spec_step_runs_the_project_command_only(tmp_path, gitflow_repo, monkeypatch, capsys):
    from conftest import write_workflow
    from sdd_helpers import init_workspace

    path = write_workflow(
        tmp_path / "plain" / "workflow.yaml",
        {"schema_version": 1, "family": "plain", "max_rounds": 2, "steps": [{"id": "check", "name": "Check", "role": "checker", "gates": ["tests-pass"]}]},
    )
    init_workspace(gitflow_repo, path, monkeypatch, capsys)
    (gitflow_repo / "tests").mkdir()
    (gitflow_repo / "tests" / "green.py").write_text("print('ok')" + chr(10), encoding="utf-8")
    git(gitflow_repo, "add", "tests")
    git(gitflow_repo, "commit", "-q", "-m", "t")
    say(monkeypatch, "task", "new", "Do it")
    set_config(capsys, "test_command", GREEN)
    assert passing(capsys)[0] == ExitCode.OK
    assert tests_pass_record(gitflow_repo)["spec_results"] == {}


def test_a_green_project_suite_is_not_enough_if_the_command_of_an_item_was_swapped_in_the_report(repo, monkeypatch, capsys):
    """The approved report is final: the commands to run again are the ones in it."""
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    report = task_dir(repo) / "reports" / "test-spec.md"
    report.write_text(report.read_text(encoding="utf-8").replace(FLIP, GREEN), encoding="utf-8")
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "verify-red.json" in err


# ------------------------------------------------------------------ timeout, directory, output


def test_the_default_timeout_is_fifteen_minutes():
    from agentflow import testrun

    assert testrun.DEFAULT_TIMEOUT_MINUTES == 15


def test_a_command_that_takes_too_long_blocks_the_step(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/slow.py")
    set_config(capsys, "test_timeout_minutes", "0.02")
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "timed out" in err
    assert tests_pass_record(repo)["status"] == "timeout"


@pytest.mark.parametrize("value", ["0", "-3", "soon"])
def test_a_timeout_setting_that_makes_no_sense_is_refused_not_ignored(repo, monkeypatch, capsys, value):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", GREEN)
    set_config(capsys, "test_timeout_minutes", value)
    code, _out, err = passing(capsys)
    assert code == GATE_FAILED and "test_timeout_minutes" in err


def test_the_command_runs_at_the_project_root(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/where.py")
    passing(capsys)
    assert f"CWD={repo}" in tests_pass_record(repo)["output"]


def test_only_the_tail_of_a_long_output_is_kept(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/loud.py")
    passing(capsys)
    output = tests_pass_record(repo)["output"]
    assert len(output) <= 5000 and output.rstrip().endswith("THE-END")


# ------------------------------------------------------------------ one runner for both gates


def test_the_two_gates_share_one_runner(repo, monkeypatch, capsys):
    from agentflow import testrun
    from spec_helpers import at_spec_step, block, write_spec

    calls = []
    real = testrun.run_command

    def spy(command, *args, **kwargs):
        calls.append(command)
        return real(command, *args, **kwargs)

    monkeypatch.setattr("agentflow.testrun.run_command", spy)
    at_spec_step(repo, monkeypatch, capsys)
    write_spec(monkeypatch, block("C1", "Build it"), block("C2", "Test it"))
    assert passing(capsys)[0] == ExitCode.OK  # test-spec: verify-red
    from checklist_helpers import checklist_path, tick

    tick(checklist_path(repo, "test-spec"))
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "task", "advance", "--result", "pass")  # build
    (repo / "built.marker").write_text("x" + chr(10), encoding="utf-8")
    set_config(capsys, "test_command", GREEN)
    assert passing(capsys)[0] == ExitCode.OK  # check: tests-pass
    assert calls == [FLIP, GREEN, FLIP]


def test_the_runner_reports_exit_code_output_timeout_and_a_missing_program():
    from agentflow import testrun

    done = testrun.run_command(f'{EXE} -c "print(5); raise SystemExit(3)"', ".", 30)
    assert done.exit_code == 3 and "5" in done.output and not done.timed_out
    slow = testrun.run_command(f'{EXE} -c "import time; time.sleep(5)"', ".", 0.5)
    assert slow.timed_out
    gone = testrun.run_command("definitely-not-a-command-xyz", ".", 30)
    assert gone.exit_code in {126, 127, 1} and gone.not_found


# ------------------------------------------------------------------ the person sees it


def test_status_does_not_run_the_tests(repo, monkeypatch, capsys):
    at_test_step(repo, monkeypatch, capsys)
    set_config(capsys, "test_command", f"{EXE} tests/mark.py")
    assert run(capsys, "status")[0] == ExitCode.OK
    assert not (repo / "ran.marker").exists()
