"""Chặng E-lock (E2 + E3): approving the tests locks them, and the steps after refuse a changed one.

When a person approves a step that has ``lock_on_approval`` (the real workflow: ``test-spec``), agentflow writes
``.agentflow/tasks/<task>/locked-files.json``: the test files of the report, the test infrastructure the tester declared
under ``## Hạ tầng test``, and the test configuration files already in the project; each with the sha256 of its bytes.
The gate ``locked-files-intact`` and the gate ``tests-pass`` compare the working tree and HEAD with those hashes before
anything else; ``agentflow tests check`` does it on request. ``agentflow commit`` refuses a commit that changes a locked
file or adds a test configuration file. The hook that keeps agents out of the files is tested in test_lock_guard.py,
the ways round the lock in test_lock_bypass.py and the person's way to change a locked test in test_tests_amend.py.
"""

import json
import re

import pytest
from checklist_helpers import checklist_path, codes, tick
from conftest import git
from lock_helpers import (
    DEDICATED,
    EXE,
    FLIP,
    FLIP2,
    GATE_FAILED,
    INTEGRITY_FAILED,
    LOCKED,
    LOCKED2,
    PACKAGE_JSON_OTHER_PART,
    PACKAGE_JSON_SOFT_JEST,
    PACKAGE_JSON_SOFT_SCRIPT,
    PACKAGE_JSON_TEST,
    PLAIN_PYPROJECT,
    PLAN2,
    PYPROJECT_OTHER_PART,
    PYPROJECT_SOFT,
    PYTEST_PYPROJECT,
    SETUP_CFG_OTHER_PART,
    SETUP_CFG_PYTEST,
    SETUP_CFG_SOFT,
    SHARED,
    SOFT_BODY,
    both_blocks,
    commit_files,
    decisions,
    finish_task,
    head,
    integrity,
    lock_path,
    lock_record,
    lock_tests,
    locked_files,
    next_task_at_spec,
    sha,
    spec_text,
    stage_and_commit,
    start_lock,
    step_now,
    to_awaiting,
    to_check,
    verify_red,
    workspace,
)
from sdd_helpers import run, say
from spec_helpers import at_spec_step, block, no_test_block

from agentflow.constants import ExitCode


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    return start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)


def approve_spec(repo, capsys):
    tick(checklist_path(repo, "test-spec"))
    return run(capsys, "task", "approve")


def at_spec(repo, monkeypatch, capsys, *, infra=None, blocks=None):
    """The test-spec step in progress with a report saved but not yet passed."""
    at_spec_step(repo, monkeypatch, capsys, PLAN2)
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_text(*(blocks or both_blocks()), infra=infra)) == ExitCode.OK
    capsys.readouterr()


# ------------------------------------------------------------------ the lock is written on approval


def test_approving_the_test_spec_writes_the_lock_with_the_hash_of_every_test_file(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    record = lock_record(repo)
    assert record["task"] == "T-001" and record["step"] == "test-spec" and record["windows"] == {}
    assert set(record["files"]) == {LOCKED, LOCKED2}
    for name, entry in record["files"].items():
        assert entry["sha256"] == sha(repo / name) and entry["kind"] == "test"
    assert step_now(repo) == ("build", "in_progress")


def test_nothing_is_locked_before_the_approval(repo, monkeypatch, capsys):
    to_awaiting(repo, monkeypatch, capsys)
    assert not lock_path(repo).exists()


def test_a_refused_approval_locks_nothing(repo, monkeypatch, capsys):
    to_awaiting(repo, monkeypatch, capsys)
    code, _out, _err = run(capsys, "task", "approve")  # the boxes are not ticked
    assert code == 36
    assert not lock_path(repo).exists()
    assert step_now(repo) == ("test-spec", "awaiting_approval")


def test_the_lock_follows_the_tests_of_the_report_and_nothing_else(repo, monkeypatch, capsys):
    blocks = (block("C1", "Build it"), no_test_block("C2", "Test it"))
    lock_tests(repo, monkeypatch, capsys, blocks=blocks)
    assert set(locked_files(repo)) == {LOCKED}


def test_a_test_named_twice_is_locked_once_without_its_test_id(repo, monkeypatch, capsys):
    one = block("C1", "Build it", tests=f"{LOCKED}::test_x, {LOCKED}::test_y")
    two = block("C2", "Test it", tests=f"{LOCKED}::test_z")
    lock_tests(repo, monkeypatch, capsys, blocks=(one, two))
    assert set(locked_files(repo)) == {LOCKED}


def test_the_lock_is_kept_through_the_rest_of_the_task(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    before = lock_path(repo).read_bytes()
    to_check(repo, monkeypatch, capsys)
    assert lock_path(repo).read_bytes() == before


def test_the_hash_of_the_lock_file_is_kept_in_integrity_json(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    assert integrity(repo)["locked_files_sha256"] == sha(lock_path(repo))


# ------------------------------------------------------------------ infrastructure the tester declares


def test_declared_infrastructure_is_locked_as_infrastructure(repo, monkeypatch, capsys):
    commit_files(repo, {"tests/support.py": "VALUE = 1\n"})
    lock_tests(repo, monkeypatch, capsys, infra=["tests/support.py"])
    files = locked_files(repo)
    assert set(files) == {LOCKED, LOCKED2, "tests/support.py"}
    assert files["tests/support.py"]["kind"] == "infra" and files["tests/support.py"]["sha256"] == sha(repo / "tests" / "support.py")
    assert files[LOCKED]["kind"] == "test"


@pytest.mark.parametrize("line", ["`tests/support.py`", "tests/support.py — shared fixtures", "tests/support.py: shared fixtures", "tests/support.py"])
def test_a_declared_path_may_carry_backticks_or_a_note(repo, monkeypatch, capsys, line):
    commit_files(repo, {"tests/support.py": "VALUE = 1\n"})
    lock_tests(repo, monkeypatch, capsys, infra=[line])
    assert "tests/support.py" in locked_files(repo)


def test_an_empty_declaration_adds_nothing(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys, infra=[])
    assert set(locked_files(repo)) == {LOCKED, LOCKED2}


def test_a_report_without_the_section_still_locks_the_tests(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys, infra=None)
    assert set(locked_files(repo)) == {LOCKED, LOCKED2}


def test_a_file_declared_and_found_by_name_is_locked_once_as_infrastructure(repo, monkeypatch, capsys):
    commit_files(repo, {"pytest.ini": "[pytest]\naddopts = -q\n"})
    lock_tests(repo, monkeypatch, capsys, infra=["pytest.ini"])
    assert locked_files(repo)["pytest.ini"]["kind"] == "infra"


@pytest.mark.parametrize("declared", ["tests/ghost.py", "../outside.py", "/etc/hosts"])
def test_a_declared_file_that_is_missing_or_outside_the_project_stops_the_test_spec(repo, monkeypatch, capsys, declared):
    at_spec(repo, monkeypatch, capsys, infra=[declared])
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and declared in err
    assert step_now(repo) == ("test-spec", "in_progress")


def test_a_declared_file_that_is_not_committed_stops_the_test_spec(repo, monkeypatch, capsys):
    at_spec(repo, monkeypatch, capsys, infra=["tests/support.py"])
    (repo / "tests" / "support.py").write_text("VALUE = 1\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and "tests/support.py" in err and "commit" in err


# ------------------------------------------------------------------ test configuration found by its name


DETECTED = [
    ("conftest.py", "import pytest\n"),
    ("tests/conftest.py", "import pytest\n"),
    ("src/pkg/conftest.py", "import pytest\n"),
    ("pytest.ini", "[pytest]\naddopts = -q\n"),
    ("tox.ini", "[tox]\nenvlist = py\n"),
    ("jest.config.js", "module.exports = {};\n"),
    ("vitest.config.ts", "export default {};\n"),
    ("pyproject.toml", PYTEST_PYPROJECT),
    ("setup.cfg", SETUP_CFG_PYTEST),
    ("package.json", PACKAGE_JSON_TEST),
]
NOT_DETECTED = [
    ("pyproject.toml", PLAIN_PYPROJECT),
    ("setup.cfg", "[metadata]\nname = demo\n"),
    ("package.json", '{"name": "demo", "scripts": {"build": "tsc"}}\n'),
    ("src/app.py", "VALUE = 1\n"),
    ("README.md", "# Demo\n"),
    ("docs/conftest.txt", "notes\n"),
    ("tests/test_conftest_notes.py", "def test_notes():\n    pass\n"),
]


@pytest.mark.parametrize("name, body", DETECTED)
def test_a_test_configuration_file_in_the_project_is_locked_even_when_the_tester_did_not_declare_it(repo, monkeypatch, capsys, name, body):
    commit_files(repo, {name: body})
    lock_tests(repo, monkeypatch, capsys)
    entry = locked_files(repo)[name]
    assert entry["kind"] == "infra" and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
    if name in SHARED:
        assert entry["scope"] == "part" and entry["part"], "a file that carries more than the test settings is locked by those settings only"
    else:
        assert entry["scope"] == "file" and entry["sha256"] == sha(repo / name)


@pytest.mark.parametrize("name, body", NOT_DETECTED)
def test_a_file_that_is_not_test_configuration_is_not_locked_on_its_own(repo, monkeypatch, capsys, name, body):
    commit_files(repo, {name: body})
    lock_tests(repo, monkeypatch, capsys)
    assert name not in locked_files(repo)


@pytest.mark.parametrize("name", ["conftest.py", "pytest.ini", "tests/conftest.py"])
def test_a_test_configuration_file_that_is_not_committed_stops_the_test_spec(repo, monkeypatch, capsys, name):
    at_spec(repo, monkeypatch, capsys)
    (repo / name).write_text("[pytest]\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and name in err and "commit" in err


def test_a_test_configuration_file_with_uncommitted_changes_stops_the_test_spec(repo, monkeypatch, capsys):
    commit_files(repo, {"pytest.ini": "[pytest]\naddopts = -q\n"})
    at_spec(repo, monkeypatch, capsys)
    (repo / "pytest.ini").write_text("[pytest]\naddopts = -q -k nothing\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and "pytest.ini" in err


def test_a_git_ignored_file_with_a_configuration_name_is_left_alone(repo, monkeypatch, capsys):
    commit_files(repo, {".gitignore": "vendor/\n"})
    (repo / "vendor").mkdir()
    (repo / "vendor" / "conftest.py").write_text("x = 1\n", encoding="utf-8")
    lock_tests(repo, monkeypatch, capsys)
    assert "vendor/conftest.py" not in locked_files(repo)


# ------------------------------------------------------------------ what the person sees before approving


def test_the_checklist_lists_every_file_that_will_be_locked(repo, monkeypatch, capsys):
    commit_files(repo, {"tests/support.py": "VALUE = 1\n", "conftest.py": "import pytest\n"})
    to_awaiting(repo, monkeypatch, capsys, infra=["tests/support.py"])
    text = checklist_path(repo, "test-spec").read_text(encoding="utf-8")
    lock_lines = [line for line in text.splitlines() if re.match(r"- \[ \] L\d+:", line)]
    assert len(lock_lines) == 4
    for name in (LOCKED, LOCKED2, "tests/support.py", "conftest.py"):
        assert any(name in line for line in lock_lines), name
    assert [c for c in codes(text) if c.startswith("L")] == ["L1", "L2", "L3", "L4"]


def test_the_lines_of_the_lock_must_be_ticked_like_the_others(repo, monkeypatch, capsys):
    to_awaiting(repo, monkeypatch, capsys)
    tick(checklist_path(repo, "test-spec"), "K1", "C1", "C2")  # the lock lines stay open
    code, _out, err = run(capsys, "task", "approve")
    assert code == 36 and "L1" in err and not lock_path(repo).exists()


# ------------------------------------------------------------------ a stack agentflow does not know


def foreign_block(repo, name: str) -> str:
    commit_files(repo, {name: "package x\n"})
    return block("C1", "Build it", tests=f"{name}::TestX", command=f"{FLIP} {name}")


@pytest.mark.parametrize("name", ["tests/flip_test.go", "tests/flip_spec.rb", "tests/FlipTest.java"])
def test_tests_in_a_language_agentflow_does_not_know_get_a_warning_and_are_still_locked(repo, monkeypatch, capsys, name):
    to_awaiting(repo, monkeypatch, capsys, blocks=(foreign_block(repo, name), no_test_block("C2", "Test it")))
    code, _out, err = approve_spec(repo, capsys)
    assert code == ExitCode.OK
    assert "warning" in err.lower() and "Hạ tầng test" in err and name in err
    assert name in locked_files(repo)


@pytest.mark.parametrize("name", ["tests/flip.spec.ts", "tests/flip.test.js", "tests/flip.py"])
def test_tests_in_a_language_agentflow_knows_get_no_warning(repo, monkeypatch, capsys, name):
    blocks = None
    if name != "tests/flip.py":
        commit_files(repo, {name: "it('x', () => {});\n"})
        blocks = (block("C1", "Build it", tests=f"{name}::x", command=f"{FLIP} {name}"), no_test_block("C2", "Test it"))
    to_awaiting(repo, monkeypatch, capsys, blocks=blocks)
    code, _out, err = approve_spec(repo, capsys)
    assert code == ExitCode.OK and "Hạ tầng test" not in err


# ------------------------------------------------------------------ the lock file is guarded by the integrity record


def tamper(repo, change) -> None:
    data = lock_record(repo)
    change(data)
    lock_path(repo).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("command", [("task", "advance", "--result", "pass"), ("task", "approve")])
def test_a_hand_edited_lock_file_stops_advance_and_approve(repo, monkeypatch, capsys, command):
    lock_tests(repo, monkeypatch, capsys)
    tamper(repo, lambda data: data["files"].pop(LOCKED2))
    code, _out, err = run(capsys, *command)
    assert code == INTEGRITY_FAILED and "locked-files.json" in err and "agentflow state accept" in err


def test_a_lock_file_with_a_hash_swapped_by_hand_is_caught(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    tamper(repo, lambda data: data["files"][LOCKED].update(sha256="0" * 64))
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == INTEGRITY_FAILED and "locked-files.json" in err


def test_a_deleted_lock_file_does_not_lift_the_lock(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    lock_path(repo).unlink()
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == INTEGRITY_FAILED and "locked-files.json" in err


def test_a_person_who_has_looked_takes_the_lock_file_as_it_is(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    tamper(repo, lambda data: data.update(note="read by a person"))
    assert run(capsys, "task", "advance", "--result", "pass")[0] == INTEGRITY_FAILED
    assert run(capsys, "state", "accept", "--reason", "I read the lock file and it is fine")[0] == ExitCode.OK
    assert integrity(repo)["locked_files_sha256"] == sha(lock_path(repo))
    to_check(repo, monkeypatch, capsys)
    assert step_now(repo) == ("check", "in_progress")
    assert any("locked-files.json" in p.read_text(encoding="utf-8") for p in decisions(repo, "state-accept"))


# ------------------------------------------------------------------ the gate and `tests check`


MUTATIONS = {
    "edited": lambda path: path.write_text(path.read_text(encoding="utf-8") + "# weaker\n", encoding="utf-8"),
    "emptied": lambda path: path.write_text("", encoding="utf-8"),
    "deleted": lambda path: path.unlink(),
    "renamed": lambda path: path.rename(path.with_name("renamed.py")),
    "line endings": lambda path: path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n")),
}


@pytest.fixture
def locked(repo, monkeypatch, capsys):
    lock_tests(repo, monkeypatch, capsys)
    return repo


def test_an_untouched_lock_lets_the_task_through_to_the_end(locked, monkeypatch, capsys):
    to_check(locked, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # check: tests-pass
    assert step_now(locked) == ("review", "in_progress")


@pytest.mark.parametrize("how", sorted(MUTATIONS))
def test_a_changed_locked_file_stops_the_build_step_and_is_named(locked, capsys, how):
    MUTATIONS[how](locked / LOCKED)
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and LOCKED in err and "locked-files-intact" in err
    assert step_now(locked) == ("build", "in_progress")


@pytest.mark.parametrize("how", sorted(MUTATIONS))
def test_the_check_command_names_what_changed_and_changes_nothing(locked, capsys, how):
    MUTATIONS[how](locked / LOCKED)
    state_before = (workspace(locked) / "state.json").read_bytes()
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED and LOCKED in out + err
    assert LOCKED2 not in out + err
    assert (workspace(locked) / "state.json").read_bytes() == state_before


def test_the_check_command_says_so_when_everything_is_intact(locked, capsys):
    code, out, _err = run(capsys, "tests", "check")
    assert code == ExitCode.OK and "intact" in out


def test_the_check_command_with_no_lock_yet_says_there_is_nothing_locked(repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Do it") == ExitCode.OK
    capsys.readouterr()
    code, out, _err = run(capsys, "tests", "check")
    assert code == ExitCode.OK and "no locked files" in out


def test_a_change_to_every_locked_file_names_every_one(locked, capsys):
    MUTATIONS["edited"](locked / LOCKED)
    MUTATIONS["edited"](locked / LOCKED2)
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED and LOCKED in out + err and LOCKED2 in out + err


def test_a_file_that_differs_at_head_but_was_put_back_in_the_working_tree_is_still_caught(locked, capsys):
    original = (locked / LOCKED).read_bytes()
    (locked / LOCKED).write_bytes(original + b"# weaker\n")
    git(locked, "commit", "-q", "-am", "weaken the test behind agentflow's back")
    (locked / LOCKED).write_bytes(original)
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED and LOCKED in out + err
    assert "HEAD" in out + err or "commit" in out + err


def test_a_staged_change_is_a_change(locked, capsys):
    (locked / LOCKED).write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(locked, "add", LOCKED)
    assert run(capsys, "tests", "check")[0] == GATE_FAILED


@pytest.mark.parametrize("name", [*DEDICATED, *SHARED])
def test_a_test_configuration_file_that_appears_after_the_lock_stops_the_build(locked, capsys, name):
    (locked / name).parent.mkdir(parents=True, exist_ok=True)
    (locked / name).write_text(SOFT_BODY[name], encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and name in err


def test_a_committed_configuration_file_that_appears_after_the_lock_is_caught_too(locked, capsys):
    commit_files(locked, {"conftest.py": "collect_ignore_glob = ['*']\n"})
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and "conftest.py" in err


def test_a_file_that_becomes_test_configuration_after_the_lock_is_caught(repo, monkeypatch, capsys):
    commit_files(repo, {"pyproject.toml": PLAIN_PYPROJECT})
    lock_tests(repo, monkeypatch, capsys)
    assert "pyproject.toml" not in locked_files(repo)
    (repo / "pyproject.toml").write_text(PYTEST_PYPROJECT.replace('"-q"', '"-k nothing"'), encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and "pyproject.toml" in err


def test_a_new_ordinary_test_file_is_fine(locked, monkeypatch, capsys):
    (locked / "tests" / "test_more.py").write_text("def test_more():\n    pass\n", encoding="utf-8")
    to_check(locked, monkeypatch, capsys)
    assert step_now(locked) == ("check", "in_progress")


def test_an_ignored_file_with_a_configuration_name_is_left_alone_after_the_lock(repo, monkeypatch, capsys):
    commit_files(repo, {".gitignore": "vendor/\n"})
    lock_tests(repo, monkeypatch, capsys)
    (repo / "vendor").mkdir()
    (repo / "vendor" / "conftest.py").write_text("x = 1\n", encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


# ------------------------------------------------------------------ tests-pass looks before it runs


def test_tests_pass_does_not_run_anything_when_a_locked_file_changed(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys, build_gates=(), check_gates=("tests-pass",))
    assert run(capsys, "config", "set", "test_command", f"{EXE} tests/mark_ok.py")[0] == ExitCode.OK
    lock_tests(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    (repo / LOCKED).write_text((repo / LOCKED).read_text(encoding="utf-8") + "# weaker\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and LOCKED in err and "tests-pass" in err
    assert not (repo / "ran.marker").exists(), "no command may run on tests that are not the approved ones"
    assert step_now(repo) == ("check", "in_progress")


def test_tests_pass_runs_when_the_locked_files_are_intact(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys, build_gates=(), check_gates=("tests-pass",))
    assert run(capsys, "config", "set", "test_command", f"{EXE} tests/mark_ok.py")[0] == ExitCode.OK
    lock_tests(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert (repo / "ran.marker").exists()


def test_tests_pass_refuses_a_configuration_file_that_appeared_before_it_runs(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys, build_gates=(), check_gates=("tests-pass",))
    assert run(capsys, "config", "set", "test_command", f"{EXE} tests/mark_ok.py")[0] == ExitCode.OK
    lock_tests(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    (repo / "conftest.py").write_text("collect_ignore_glob = ['*']\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and "conftest.py" in err
    assert not (repo / "ran.marker").exists()


def test_a_failed_lock_check_leaves_the_state_untouched_so_the_agent_can_put_the_file_back(locked, monkeypatch, capsys):
    original = (locked / LOCKED).read_bytes()
    (locked / LOCKED).write_bytes(original + b"# weaker\n")
    assert run(capsys, "task", "advance", "--result", "pass")[0] == GATE_FAILED
    (locked / LOCKED).write_bytes(original)
    to_check(locked, monkeypatch, capsys)
    assert step_now(locked) == ("check", "in_progress")


def test_the_review_step_checks_the_lock_too(locked, monkeypatch, capsys):
    to_check(locked, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # check
    (locked / LOCKED).write_text("", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and LOCKED in err


# ------------------------------------------------------------------ agentflow commit


def test_a_commit_that_changes_a_locked_file_is_refused_and_nothing_is_committed(locked, monkeypatch, capsys):
    (locked / LOCKED).write_text((locked / LOCKED).read_text(encoding="utf-8") + "# weaker\n", encoding="utf-8")
    git(locked, "add", LOCKED)
    before = head(locked)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code != ExitCode.OK and LOCKED in err and "amend" in err
    assert head(locked) == before


def test_a_commit_that_deletes_a_locked_file_is_refused(locked, monkeypatch, capsys):
    git(locked, "rm", "-q", LOCKED)
    before = head(locked)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code != ExitCode.OK and LOCKED in err
    assert head(locked) == before


def test_a_commit_that_renames_a_locked_file_is_refused_under_its_old_name(locked, monkeypatch, capsys):
    git(locked, "mv", LOCKED, "tests/flip_renamed.py")
    before = head(locked)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code != ExitCode.OK and LOCKED in err
    assert head(locked) == before


@pytest.mark.parametrize("name", [*DEDICATED, *SHARED])
def test_a_commit_that_adds_a_test_configuration_file_is_refused(locked, monkeypatch, capsys, name):
    (locked / name).parent.mkdir(parents=True, exist_ok=True)
    (locked / name).write_text(SOFT_BODY[name], encoding="utf-8")
    git(locked, "add", name)
    before = head(locked)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code != ExitCode.OK and name in err and "amend" in err
    assert head(locked) == before


def test_a_refused_file_in_a_larger_commit_refuses_the_whole_commit(locked, monkeypatch, capsys):
    (locked / "tests" / "test_more.py").write_text("def test_more():\n    pass\n", encoding="utf-8")
    (locked / LOCKED).write_text("", encoding="utf-8")
    git(locked, "add", "tests")
    before = head(locked)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code != ExitCode.OK and LOCKED in err and "test_more.py" not in err
    assert head(locked) == before


def test_a_commit_of_new_tests_and_application_code_goes_through(locked, monkeypatch, capsys):
    (locked / "tests" / "test_more.py").write_text("def test_more():\n    pass\n", encoding="utf-8")
    (locked / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(locked, "add", "tests/test_more.py", "app.py")
    code, out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code == ExitCode.OK, err
    assert "committed" in out


def test_before_the_approval_the_tester_may_commit_what_it_likes(repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Do it") == ExitCode.OK
    (repo / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (repo / LOCKED).write_text((repo / LOCKED).read_text(encoding="utf-8") + "# tuned\n", encoding="utf-8")
    git(repo, "add", "conftest.py", LOCKED)
    code, _out, err = stage_and_commit(repo, monkeypatch, capsys)
    assert code == ExitCode.OK, err


def test_a_finished_task_frees_the_files_for_the_next_one(locked, monkeypatch, capsys):
    finish_task(locked, monkeypatch, capsys)
    assert say(monkeypatch, "task", "new", "Next one") == ExitCode.OK
    (locked / LOCKED).write_text((locked / LOCKED).read_text(encoding="utf-8") + "# tuned\n", encoding="utf-8")
    git(locked, "add", LOCKED)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code == ExitCode.OK, err
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


def test_two_tasks_keep_their_own_locks(locked, monkeypatch, capsys):
    finish_task(locked, monkeypatch, capsys)
    next_task_at_spec(locked, monkeypatch, capsys)
    only_second = (block("C1", "Build it", command=FLIP2), no_test_block("C2", "Test it"))
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_text(*only_second)) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    tick(checklist_path(locked, "test-spec", task="T-002"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    assert set(locked_files(locked, "T-002")) == {LOCKED2}
    assert set(locked_files(locked, "T-001")) == {LOCKED, LOCKED2}
    (locked / LOCKED).write_text("def test_x():\n    pass\n", encoding="utf-8")  # locked by T-001 only
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


# ------------------------------------------------------------------ what was proven red is what gets locked


def test_the_gate_keeps_the_hash_of_every_file_it_proved(repo, monkeypatch, capsys):
    commit_files(repo, {"conftest.py": "import pytest\n"})
    to_awaiting(repo, monkeypatch, capsys)
    files = verify_red(repo)["files"]
    assert set(files) == {LOCKED, LOCKED2, "conftest.py"}
    assert files[LOCKED] == sha(repo / LOCKED) and files["conftest.py"] == sha(repo / "conftest.py")


@pytest.mark.parametrize("name", [LOCKED, LOCKED2, "conftest.py"])
def test_a_file_changed_after_the_gate_ran_cannot_be_locked(repo, monkeypatch, capsys, name):
    commit_files(repo, {"conftest.py": "import pytest\n"})
    to_awaiting(repo, monkeypatch, capsys)
    (repo / name).write_text((repo / name).read_text(encoding="utf-8") + "# changed after the red proof\n", encoding="utf-8")
    code, _out, err = approve_spec(repo, capsys)
    assert code == GATE_FAILED and name in err
    assert not lock_path(repo).exists()
    assert step_now(repo) == ("test-spec", "awaiting_approval")


# ------------------------------------------------------------------ shared files: only their test settings are locked


SHARED_SAMPLES = [
    ("pyproject.toml", PYTEST_PYPROJECT, PYPROJECT_OTHER_PART, [PYPROJECT_SOFT, PLAIN_PYPROJECT]),
    ("setup.cfg", SETUP_CFG_PYTEST, SETUP_CFG_OTHER_PART, [SETUP_CFG_SOFT, "[metadata]\nname = demo\n"]),
    ("package.json", PACKAGE_JSON_TEST, PACKAGE_JSON_OTHER_PART, [PACKAGE_JSON_SOFT_JEST, PACKAGE_JSON_SOFT_SCRIPT, '{"name": "demo"}\n']),
]
SHARED_IDS = [name for name, *_rest in SHARED_SAMPLES]


@pytest.fixture
def shared(repo, monkeypatch, capsys):
    """A project whose pyproject.toml, setup.cfg and package.json carry test settings, locked at the approval."""
    commit_files(repo, {name: body for name, body, _other, _soft in SHARED_SAMPLES})
    lock_tests(repo, monkeypatch, capsys)
    return repo


@pytest.mark.parametrize("name, body, other, soft", SHARED_SAMPLES, ids=SHARED_IDS)
def test_changing_a_part_of_a_shared_file_that_is_not_the_test_settings_needs_no_amend(shared, monkeypatch, capsys, name, body, other, soft):
    (shared / name).write_text(other, encoding="utf-8")
    code, out, err = run(capsys, "tests", "check")
    assert code == ExitCode.OK and "intact" in out, out + err
    to_check(shared, monkeypatch, capsys)
    assert step_now(shared) == ("check", "in_progress")


@pytest.mark.parametrize("name, body, other, soft", SHARED_SAMPLES, ids=SHARED_IDS)
def test_the_test_settings_of_a_shared_file_are_locked(shared, capsys, name, body, other, soft):
    for changed in soft:
        (shared / name).write_text(changed, encoding="utf-8")
        code, out, err = run(capsys, "tests", "check")
        assert code == GATE_FAILED and name in out + err, changed
        code, _out, err = run(capsys, "task", "advance", "--result", "pass")
        assert code == GATE_FAILED and name in err and "locked-files-intact" in err
    assert step_now(shared) == ("build", "in_progress")


def test_a_shared_file_that_is_deleted_loses_its_test_settings_and_that_is_a_change(shared, capsys):
    (shared / "pyproject.toml").unlink()
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED and "pyproject.toml" in out + err


def test_laying_a_shared_file_out_differently_without_changing_its_test_settings_is_nothing(shared, capsys):
    (shared / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts   =   "-q"   # same\n\n\n[project]\nname = "demo"\n', encoding="utf-8")
    (shared / "package.json").write_text(PACKAGE_JSON_TEST.replace("\n  ", "\n        "), encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


@pytest.mark.parametrize("name, body, other, soft", SHARED_SAMPLES, ids=SHARED_IDS)
def test_a_commit_that_changes_only_other_parts_of_a_shared_file_goes_through(shared, monkeypatch, capsys, name, body, other, soft):
    (shared / name).write_text(other, encoding="utf-8")
    git(shared, "add", name)
    code, _out, err = stage_and_commit(shared, monkeypatch, capsys)
    assert code == ExitCode.OK, err
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


@pytest.mark.parametrize("name, body, other, soft", SHARED_SAMPLES, ids=SHARED_IDS)
def test_a_commit_that_changes_the_test_settings_of_a_shared_file_is_refused(shared, monkeypatch, capsys, name, body, other, soft):
    (shared / name).write_text(soft[0], encoding="utf-8")
    git(shared, "add", name)
    before = head(shared)
    code, _out, err = stage_and_commit(shared, monkeypatch, capsys)
    assert code != ExitCode.OK and name in err and "amend" in err
    assert head(shared) == before


@pytest.mark.parametrize(
    "name, body",
    [("pyproject.toml", PLAIN_PYPROJECT), ("setup.cfg", "[metadata]\nname = demo\n"), ("package.json", '{"name": "demo", "scripts": {"build": "tsc"}}\n')],
)
def test_a_new_shared_file_without_test_settings_is_fine(repo, monkeypatch, capsys, name, body):
    lock_tests(repo, monkeypatch, capsys)
    (repo / name).write_text(body, encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
    git(repo, "add", name)
    code, _out, err = stage_and_commit(repo, monkeypatch, capsys)
    assert code == ExitCode.OK, err


# ------------------------------------------------------------------ the tester makes the configuration before the lock


def test_the_tester_can_make_test_configuration_in_the_test_spec_step_and_it_is_locked_at_the_approval(repo, monkeypatch, capsys):
    at_spec_step(repo, monkeypatch, capsys, PLAN2)
    for name, body in {"conftest.py": SOFT_BODY["conftest.py"].replace("items.clear()", "pass"), "pytest.ini": "[pytest]\naddopts = -q\n", "pyproject.toml": PYTEST_PYPROJECT}.items():
        (repo / name).write_text(body, encoding="utf-8")
        git(repo, "add", name)
    code, _out, err = stage_and_commit(repo, monkeypatch, capsys, "test configuration")
    assert code == ExitCode.OK, err
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_text(*both_blocks())) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    tick(checklist_path(repo, "test-spec"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    files = locked_files(repo)
    assert {"conftest.py", "pytest.ini", "pyproject.toml"} <= set(files)
    assert files["conftest.py"]["scope"] == "file" and files["pyproject.toml"]["scope"] == "part"


def test_the_tester_can_declare_a_shared_file_and_it_is_locked_by_its_test_settings(repo, monkeypatch, capsys):
    commit_files(repo, {"package.json": PACKAGE_JSON_TEST})
    lock_tests(repo, monkeypatch, capsys, infra=["package.json"])
    assert locked_files(repo)["package.json"]["scope"] == "part"
    (repo / "package.json").write_text(PACKAGE_JSON_OTHER_PART, encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
