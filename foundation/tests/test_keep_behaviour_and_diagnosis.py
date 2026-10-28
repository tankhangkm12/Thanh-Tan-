"""Tasks that keep the behaviour (refactor, chore) and the diagnoses of the debugger.

- ``task new --type refactor|chore`` branches from develop, keeps the type in ``state.json`` and shows it in ``status``.
- A workflow's ``types`` section gives a type ``test_spec: green``: at the test-spec step every block says
  ``- green: pass`` and thanhtan wants each command to PASS on the code as it is; the approval locks the tests and
  ``tests-pass`` wants them to pass again. An amended locked test must still pass on the old code.
- ``thanhtan diagnosis write|list|show`` and the MCP tool ``diagnosis_write`` keep a diagnosis: in the open task
  (``diagnoses/round-<n>.md``), or with none open as ``diagnoses/D-001.md``.
"""

import json
from pathlib import Path

import pytest
import yaml
from checklist_helpers import checklist_path, tick
from conftest import git
from lock_helpers import EXTRA_SCRIPTS, clean_scanner, commit_files, lock_record, lock_workflow, spec_text, stage_and_commit
from sdd_helpers import PLAN, init_workspace, run, say
from spec_helpers import EXE, GREEN, PLAN2, SCRIPTS, at_spec_step, block

from thanhtan import diagnosis
from thanhtan.constants import ExitCode, TestSpecMode
from thanhtan.errors import ThanhTanError
from thanhtan.models import State, StepStatus, Task, TaskStatus
from thanhtan.workflow import load_workflow

REAL_WORKFLOW = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core" / "workflow.yaml"
KEEP = "tests/keep.py"  # passes until broken.marker exists: the behaviour the refactor must keep
KEEP2 = "tests/keep2.py"
KEEP_SCRIPT = "import os, sys\nif os.path.exists('broken.marker'):\n    print('FAILED behaviour changed')\n    sys.exit(1)\nprint('2 passed')\n"
KEEP_CMD = f"{EXE} {KEEP}"
KEEP2_CMD = f"{EXE} {KEEP2}"
GREEN_FAILING = "import sys\nprint('FAILED')\nsys.exit(1)\n"

DIAGNOSIS = """# Chẩn đoán

## Tái hiện
`uv run pytest tests/test_stock.py::test_reserve` fails every time.

## Nguyên nhân
src/stock.py:42 subtracts before it checks the quantity.
"""


def green_block(code: str, title: str, command: str = KEEP_CMD, *, verdict: str | None = "pass", red: str | None = None) -> str:
    test = command.split()[-1]
    lines = [f"### {code} - {title}", f"- tests: {test}::test_x", f"- command: `{command}`"]
    if verdict is not None:
        lines.append(f"- green: {verdict}")
    if red is not None:
        lines.append(f"- red: {red}")
    lines += ["- reason: the totals and the rounding the split must keep", "- output: |", "    2 passed"]
    return "\n".join(lines) + "\n"


def keep_workflow(tmp_path: Path) -> Path:
    path = lock_workflow(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["types"] = {"refactor": {"test_spec": "green"}, "chore": {"test_spec": "green"}}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def keep_repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    """A workspace on a workflow where refactor and chore keep the behaviour, with keep.py and keep2.py committed."""
    init_workspace(gitflow_repo, keep_workflow(tmp_path), monkeypatch, capsys)
    clean_scanner(monkeypatch)
    files = {f"tests/{name}": body for name, body in {**SCRIPTS, **EXTRA_SCRIPTS}.items()}
    files.update({KEEP: KEEP_SCRIPT, KEEP2: KEEP_SCRIPT, "tests/test_a.py": "def test_x():\n    assert False\n"})
    commit_files(gitflow_repo, files, "add test scripts")
    assert run(capsys, "config", "set", "test_command", GREEN)[0] == ExitCode.OK
    return gitflow_repo


def state(repo: Path) -> dict:
    return json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))


def verify_record(repo: Path) -> dict:
    return json.loads((repo / ".ThanhTan" / "tasks" / "T-001" / "verify-red.json").read_text(encoding="utf-8"))


def spec_advance(repo, monkeypatch, capsys, *blocks: str) -> tuple[int, str, str]:
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_text(*blocks, infra=[])) == ExitCode.OK
    capsys.readouterr()
    return run(capsys, "task", "advance", "--result", "pass")


def locked_green(repo, monkeypatch, capsys) -> None:
    """A refactor task whose green tests are approved and locked; the build step is in progress."""
    at_spec_step(repo, monkeypatch, capsys, PLAN2, "--type", "refactor")
    code, _out, err = spec_advance(repo, monkeypatch, capsys, green_block("C1", "Split it"), green_block("C2", "Rename it", KEEP2_CMD))
    assert code == ExitCode.OK, err
    tick(checklist_path(repo, "test-spec"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    capsys.readouterr()


# ------------------------------------------------------------------ the workflow and the task


def test_the_workflow_gives_a_type_its_test_spec_mode(keep_repo, tmp_path):
    workflow = load_workflow(keep_workflow(tmp_path))
    assert workflow.test_spec_modes == {"refactor": TestSpecMode.GREEN, "chore": TestSpecMode.GREEN}
    assert workflow.test_spec_mode(None) is TestSpecMode.RED


@pytest.mark.parametrize("types", [{"refactor": {"test_spec": "blue"}}, {"spike": {"test_spec": "green"}}, {"refactor": {"other": 1}}])
def test_the_schema_refuses_a_bad_types_section(tmp_path, types):
    path = lock_workflow(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["types"] = types
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ThanhTanError):
        load_workflow(path)


def test_the_software_dev_workflow_keeps_the_behaviour_for_refactor_and_chore():
    workflow = load_workflow(REAL_WORKFLOW)
    assert workflow.test_spec_modes == {"refactor": TestSpecMode.GREEN, "chore": TestSpecMode.GREEN}
    assert "debugger" in workflow.read_only_roles


@pytest.mark.parametrize("kind", ["refactor", "chore"])
def test_a_refactor_or_chore_task_branches_from_develop_and_keeps_its_type(keep_repo, monkeypatch, capsys, kind):
    code, out, _err = run(capsys, "task", "new", "Split the price module", "--type", kind)
    assert code == ExitCode.OK
    assert f"on branch {kind}/T-001-" in out
    assert git(keep_repo, "merge-base", "--is-ancestor", "develop", "HEAD") == ""
    assert state(keep_repo)["tasks"][0]["type"] == kind
    _code, out, _err = run(capsys, "status")
    assert f"type: {kind} (keeps the behaviour" in out
    assert f"- Type: {kind}" in (keep_repo / ".ThanhTan" / "STATE.md").read_text(encoding="utf-8")


def test_a_feature_task_keeps_its_type_too_and_says_nothing_more(keep_repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Add it") == ExitCode.OK
    assert state(keep_repo)["tasks"][0]["type"] == "feature"
    _code, out, _err = run(capsys, "status")
    assert "type: feature\n" in out


def test_a_task_recorded_before_types_were_kept_still_loads(keep_repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Old one") == ExitCode.OK
    path = keep_repo / ".ThanhTan" / "state.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["tasks"][0]["type"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert run(capsys, "state", "accept", "--reason", "test: an old state")[0] == ExitCode.OK
    code, out, _err = run(capsys, "status")
    assert code == ExitCode.OK and "type:" not in out


# ------------------------------------------------------------------ test-spec proves green


def test_green_tests_on_the_code_as_it_is_pass_the_gate_and_are_recorded_as_green(keep_repo, monkeypatch, capsys):
    at_spec_step(keep_repo, monkeypatch, capsys, PLAN2, "--type", "refactor")
    code, _out, err = spec_advance(keep_repo, monkeypatch, capsys, green_block("C1", "Split it"), green_block("C2", "Rename it", KEEP2_CMD))
    assert code == ExitCode.OK, err
    record = verify_record(keep_repo)
    assert record["mode"] == "green"
    assert {entry["status"] for entry in record["results"].values()} == {"green"}


def test_a_red_block_is_refused_for_a_task_that_keeps_the_behaviour(keep_repo, monkeypatch, capsys):
    at_spec_step(keep_repo, monkeypatch, capsys, PLAN, "--type", "refactor")
    code, _out, err = spec_advance(keep_repo, monkeypatch, capsys, green_block("C1", "Split it", verdict=None, red="fail"))
    assert code == 25
    assert "field 'green' must be 'pass'" in err and "field 'red' does not belong" in err


def test_a_command_that_fails_on_the_code_as_it_is_is_refused(keep_repo, monkeypatch, capsys):
    commit_files(keep_repo, {"tests/broken.py": GREEN_FAILING})
    at_spec_step(keep_repo, monkeypatch, capsys, PLAN, "--type", "chore")
    code, _out, err = spec_advance(keep_repo, monkeypatch, capsys, green_block("C1", "Upgrade it", f"{EXE} tests/broken.py"))
    assert code == 25
    assert "fails on the code as it is" in err


def test_a_feature_task_on_the_same_workflow_still_proves_red(keep_repo, monkeypatch, capsys):
    at_spec_step(keep_repo, monkeypatch, capsys, PLAN)
    code, _out, err = spec_advance(keep_repo, monkeypatch, capsys, green_block("C1", "Add it"))
    assert code == 25 and "field 'red' must be 'fail'" in err
    code, _out, err = spec_advance(keep_repo, monkeypatch, capsys, block("C1", "Add it"))
    assert code == ExitCode.OK, err
    assert verify_record(keep_repo)["mode"] == "red"


def test_the_approval_locks_the_green_tests(keep_repo, monkeypatch, capsys):
    locked_green(keep_repo, monkeypatch, capsys)
    assert {KEEP, KEEP2} <= set(lock_record(keep_repo)["files"])


def test_tests_pass_wants_the_locked_tests_to_pass_again_after_the_change(keep_repo, monkeypatch, capsys):
    locked_green(keep_repo, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # build
    (keep_repo / "broken.marker").write_text("x\n", encoding="utf-8")  # the refactor changed the behaviour
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == 25 and "C1: its command still fails" in err
    (keep_repo / "broken.marker").unlink()
    assert run(capsys, "task", "advance", "--result", "pass")[0] == ExitCode.OK


def test_an_amended_test_that_fails_on_the_old_code_is_refused(keep_repo, monkeypatch, capsys):
    locked_green(keep_repo, monkeypatch, capsys)
    assert run(capsys, "tests", "amend", KEEP, "--reason", "describe the new rounding")[0] == ExitCode.OK
    (keep_repo / KEEP).write_text(GREEN_FAILING, encoding="utf-8")
    git(keep_repo, "add", KEEP)
    code, _out, err = stage_and_commit(keep_repo, monkeypatch, capsys, "amend keep")
    assert code != ExitCode.OK
    assert "fails on the old code" in err and "feature or bugfix task" in err


def test_an_amended_test_that_still_passes_on_the_old_code_goes_through(keep_repo, monkeypatch, capsys):
    locked_green(keep_repo, monkeypatch, capsys)
    assert run(capsys, "tests", "amend", KEEP, "--reason", "name the case better")[0] == ExitCode.OK
    (keep_repo / KEEP).write_text(KEEP_SCRIPT + "# the case of a zero discount\n", encoding="utf-8")
    git(keep_repo, "add", KEEP)
    code, _out, err = stage_and_commit(keep_repo, monkeypatch, capsys, "amend keep")
    assert code == ExitCode.OK, err


# ------------------------------------------------------------------ diagnoses


def _task(round_: int = 0) -> Task:
    return Task("T-001", "Fix it", TaskStatus.OPEN, "implement", StepStatus.IN_PROGRESS, loop_round=round_)


def test_a_diagnosis_needs_the_two_sections():
    assert diagnosis.problems(DIAGNOSIS) == []
    assert diagnosis.problems("## Tái hiện\nx\n") == ["the diagnosis has no '## Nguyên nhân' section"]
    assert diagnosis.problems("  ") == ["the diagnosis is empty"]


def test_without_a_task_diagnoses_are_numbered(tmp_path):
    first = diagnosis.write(tmp_path, State(), DIAGNOSIS)
    second = diagnosis.write(tmp_path, State(), DIAGNOSIS)
    assert (first.name, second.name) == ("D-001", "D-002")
    assert first.path == tmp_path / "diagnoses" / "D-001.md" and first.task_id is None
    assert diagnosis.read(tmp_path, "D-002") == DIAGNOSIS


def test_with_a_task_open_a_diagnosis_belongs_to_its_round(tmp_path):
    state_ = State(active_task_id="T-001", tasks=(_task(2),))
    first = diagnosis.write(tmp_path, state_, DIAGNOSIS)
    again = diagnosis.write(tmp_path, state_, DIAGNOSIS)
    assert first.path == tmp_path / "tasks" / "T-001" / "diagnoses" / "round-2.md"
    assert again.name == "round-2-2"
    assert [d.name for d in diagnosis.listing(tmp_path, state_)] == ["round-2", "round-2-2"]


def test_a_bad_code_or_a_missing_diagnosis_is_refused(tmp_path):
    for code in ("../x", "D-9"):
        with pytest.raises(ThanhTanError):
            diagnosis.read(tmp_path, code)


def test_the_cli_writes_lists_and_shows_a_diagnosis(keep_repo, monkeypatch, capsys):
    assert say(monkeypatch, "diagnosis", "write", text=DIAGNOSIS) == ExitCode.OK
    capsys.readouterr()
    code, out, _err = run(capsys, "diagnosis", "list")
    assert code == ExitCode.OK and out.startswith("D-001: ")
    code, out, _err = run(capsys, "diagnosis", "show", "D-001")
    assert code == ExitCode.OK and out == DIAGNOSIS


def test_the_cli_refuses_a_diagnosis_without_the_sections(keep_repo, monkeypatch, capsys):
    assert say(monkeypatch, "diagnosis", "write", text="# nothing here\n") == ExitCode.INVALID_INPUT


def test_a_diagnosis_never_changes_the_task(keep_repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Fix it", "--type", "bugfix") == ExitCode.OK
    before = state(keep_repo)["tasks"][0]
    assert say(monkeypatch, "diagnosis", "write", text=DIAGNOSIS) == ExitCode.OK
    after = state(keep_repo)["tasks"][0]
    assert before == after
    assert (keep_repo / ".ThanhTan" / "tasks" / "T-001" / "diagnoses" / "round-0.md").is_file()
