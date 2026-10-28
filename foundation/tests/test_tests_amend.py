"""Chặng E-lock (E2): the one way to change an approved test is a person's command, and it leaves a trace.

``agentflow tests amend <file>... --reason "..."`` is for a person (the guard denies it to agents in every form, see
test_lock_guard.py). It opens a window for each file: the hook lets the tools change that file, and only that file. The
window closes when ``agentflow commit`` commits the file; then the lock holds the new bytes, ``decisions/`` keeps who
changed what and why (old and new hash), and agentflow runs the commands of the plan items that use the file again, in a
throwaway checkout of the commit where the red proof was made (so the amended test must still fail on the old code):
the outcome is kept in ``verify-red.json`` under ``reverified``. A test that now PASSES on the old code no longer proves
anything: ``agentflow commit`` refuses the commit (before anything is committed) unless the person opened the window with
``--accept-green`` and a reason, which is kept in ``decisions/`` and still printed as a warning.
The window is also how a test configuration file that does not exist yet (a ``conftest.py`` the project really needs)
gets into the lock.
"""

import re

import pytest
from lock_helpers import (
    FLIP,
    FLIP2,
    GATE_FAILED,
    INVALID_INPUT,
    LOCKED,
    LOCKED2,
    PYTEST_PYPROJECT,
    commit_files,
    decide,
    decisions,
    finish_task,
    head,
    integrity,
    lock_path,
    lock_record,
    lock_tests,
    locked_files,
    sha,
    stage_and_commit,
    start_lock,
    step_now,
    verify_red,
)
from sdd_helpers import run, say
from spec_helpers import block, no_test_block

from conftest import git
from agentflow.constants import ExitCode

REASON = "the expected value in the test was wrong"


@pytest.fixture
def locked(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"conftest.py": "import pytest\n", "pytest.ini": "[pytest]\naddopts = -q\n"})
    lock_tests(repo, monkeypatch, capsys)
    (repo / "built.marker").write_text("x\n", encoding="utf-8")  # the code is built: the test commands are green here, red on the old code
    return repo


def amend(capsys, *files: str, reason: str = REASON, flags: tuple[str, ...] = ()) -> tuple[int, str, str]:
    return run(capsys, "tests", "amend", *files, *flags, "--reason", reason)


def change_and_commit(repo, monkeypatch, capsys, name: str, text: str | None = None, message: str = "amend the test"):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text is not None else (path.read_text(encoding="utf-8") + "# amended by a person\n"), encoding="utf-8")
    git(repo, "add", name)
    return stage_and_commit(repo, monkeypatch, capsys, message)


def the_decision(repo) -> str:
    (path,) = decisions(repo, "tests-amend")
    return path.read_text(encoding="utf-8")


# ------------------------------------------------------------------ opening a window


def test_a_person_opens_a_window_for_an_approved_test(locked, capsys):
    code, out, _err = amend(capsys, LOCKED)
    assert code == ExitCode.OK and LOCKED in out
    window = lock_record(locked)["windows"][LOCKED]
    assert window["reason"] == REASON and window["opened_at"]
    assert set(lock_record(locked)["windows"]) == {LOCKED}


def test_opening_a_window_keeps_the_old_hash_and_writes_a_decision(locked, capsys):
    old = sha(locked / LOCKED)
    amend(capsys, LOCKED)
    text = the_decision(locked)
    assert REASON in text and LOCKED in text and old in text
    assert locked_files(locked)[LOCKED]["sha256"] == old, "the lock keeps the approved bytes until the new ones are committed"


def test_the_lock_file_stays_in_step_with_its_hash_in_integrity_json(locked, capsys):
    amend(capsys, LOCKED)
    assert integrity(locked)["locked_files_sha256"] == sha(lock_path(locked))


def test_several_files_can_be_opened_with_one_reason(locked, capsys):
    assert amend(capsys, LOCKED, "conftest.py")[0] == ExitCode.OK
    assert set(lock_record(locked)["windows"]) == {LOCKED, "conftest.py"}


def test_a_reason_is_required(locked, capsys):
    for argv in (("tests", "amend", LOCKED), ("tests", "amend", LOCKED, "--reason", "  ")):
        code, _out, err = run(capsys, *argv)
        assert code == INVALID_INPUT and "reason" in err
    assert lock_record(locked)["windows"] == {}
    assert decisions(locked, "tests-amend") == []


def test_a_file_that_is_not_locked_cannot_be_opened(locked, capsys):
    code, _out, err = amend(capsys, "tests/mark.py")
    assert code == INVALID_INPUT and "tests/mark.py" in err and "not locked" in err
    assert amend(capsys, "src/app.py")[0] == INVALID_INPUT
    assert lock_record(locked)["windows"] == {}


def test_one_unknown_file_among_good_ones_opens_nothing(locked, capsys):
    assert amend(capsys, LOCKED, "src/app.py")[0] == INVALID_INPUT
    assert lock_record(locked)["windows"] == {}


def test_there_is_nothing_to_amend_before_the_approval(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    assert say(monkeypatch, "task", "new", "Do it") == ExitCode.OK
    code, _out, err = amend(capsys, LOCKED)
    assert code == INVALID_INPUT and "locked" in err
    assert not lock_path(repo).exists()


def test_there_is_nothing_to_amend_without_a_task(locked, monkeypatch, capsys):
    finish_task(locked, monkeypatch, capsys)
    assert amend(capsys, LOCKED)[0] != ExitCode.OK


@pytest.mark.parametrize("name", ["jest.config.js", "tests/conftest.py", "tox.ini", "pyproject.toml"])
def test_a_configuration_file_that_does_not_exist_yet_can_be_opened(locked, capsys, name):
    assert amend(capsys, name)[0] == ExitCode.OK
    assert name in lock_record(locked)["windows"]


# ------------------------------------------------------------------ what the window lets through


def test_the_window_opens_that_file_to_the_tools_and_no_other(locked, capsys):
    assert decide(locked, tool="Write", path=locked / LOCKED) == "deny"
    amend(capsys, LOCKED)
    assert decide(locked, tool="Write", path=locked / LOCKED) == "allow"
    assert decide(locked, tool="Edit", path=locked / LOCKED) == "allow"
    assert decide(locked, command=f"echo x >> {LOCKED}") == "allow"
    assert decide(locked, command=f"sed -i 's/a/b/' {LOCKED}") == "allow"
    assert decide(locked, tool="Write", path=locked / LOCKED2) == "deny"
    assert decide(locked, tool="Write", path=locked / "conftest.py") == "deny"
    assert decide(locked, tool="Write", path=locked / "tox.ini") == "deny"


def test_a_window_does_not_excuse_an_uncommitted_change(locked, capsys):
    amend(capsys, LOCKED)
    (locked / LOCKED).write_text((locked / LOCKED).read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED and LOCKED in out + err and "commit" in out + err
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED and LOCKED in err


def test_a_commit_of_a_different_locked_file_is_refused_while_another_window_is_open(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED2)
    assert code != ExitCode.OK and LOCKED2 in err


def test_a_commit_that_does_not_touch_the_file_leaves_the_window_open(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, "tests/test_more.py", "def test_more():\n    pass\n")
    assert code == ExitCode.OK, err
    assert set(lock_record(locked)["windows"]) == {LOCKED}


# ------------------------------------------------------------------ closing it: the new bytes are locked


def test_committing_the_amended_file_closes_the_window_and_locks_the_new_bytes(locked, monkeypatch, capsys):
    old = sha(locked / LOCKED)
    amend(capsys, LOCKED)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED)
    assert code == ExitCode.OK, err
    record = lock_record(locked)
    assert record["windows"] == {}
    assert record["files"][LOCKED]["sha256"] == sha(locked / LOCKED) != old
    assert integrity(locked)["locked_files_sha256"] == sha(lock_path(locked))
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
    assert decide(locked, tool="Write", path=locked / LOCKED) == "deny", "closed again"


def test_the_decision_ends_up_with_the_old_and_the_new_hash_and_the_commit(locked, monkeypatch, capsys):
    old = sha(locked / LOCKED)
    amend(capsys, LOCKED)
    change_and_commit(locked, monkeypatch, capsys, LOCKED)
    text = the_decision(locked)
    assert REASON in text and old in text and sha(locked / LOCKED) in text
    assert head(locked)[:7] in text


def test_the_task_goes_on_after_a_harmless_amend(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    change_and_commit(locked, monkeypatch, capsys, LOCKED)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # build
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # check
    assert step_now(locked) == ("review", "in_progress")


def test_a_commit_of_the_amended_file_with_other_files_goes_through(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    (locked / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (locked / LOCKED).write_text((locked / LOCKED).read_text(encoding="utf-8") + "# amended\n", encoding="utf-8")
    git(locked, "add", "app.py", LOCKED)
    code, _out, err = stage_and_commit(locked, monkeypatch, capsys)
    assert code == ExitCode.OK, err
    assert locked_files(locked)[LOCKED]["sha256"] == sha(locked / LOCKED)


def test_an_amended_configuration_file_is_locked_again_with_its_new_bytes(locked, monkeypatch, capsys):
    amend(capsys, "pytest.ini")
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, "pytest.ini", "[pytest]\naddopts = -q -ra\n")
    assert code == ExitCode.OK, err
    assert locked_files(locked)["pytest.ini"]["sha256"] == sha(locked / "pytest.ini")
    assert decide(locked, tool="Edit", path=locked / "pytest.ini") == "deny"


def test_a_new_configuration_file_enters_the_lock_through_a_window(locked, monkeypatch, capsys):
    assert decide(locked, tool="Write", path=locked / "jest.config.js") == "deny"
    amend(capsys, "jest.config.js")
    assert decide(locked, tool="Write", path=locked / "jest.config.js") == "allow"
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, "jest.config.js", "module.exports = {};\n")
    assert code == ExitCode.OK, err
    entry = locked_files(locked)["jest.config.js"]
    assert entry["kind"] == "infra" and entry["sha256"] == sha(locked / "jest.config.js")
    assert lock_record(locked)["windows"] == {}
    assert decide(locked, tool="Write", path=locked / "jest.config.js") == "deny"
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


def test_an_agent_cannot_use_the_window_of_a_person_for_another_file(locked, capsys):
    amend(capsys, "jest.config.js")
    assert decide(locked, tool="Write", path=locked / "vitest.config.ts") == "deny"
    assert decide(locked, tool="Write", path=locked / "jest.config.json") == "deny"


# ------------------------------------------------------------------ the red proof is made again, on the old code


def reverified(repo) -> dict:
    return verify_red(repo)["reverified"]


def test_a_harmless_amend_is_re_run_on_the_old_code_and_is_still_red(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED)
    assert code == ExitCode.OK and "warning" not in err.lower()
    again = reverified(locked)
    assert set(again) == {"C1"}, "only the plan items whose tests are in the amended file"
    entry = again["C1"]
    assert entry["status"] == "red" and entry["exit_code"] not in (0, None)
    assert entry["command"] == FLIP and entry["files"] == [LOCKED] and entry["at"]
    assert "C1" in the_decision(locked) and "red" in the_decision(locked)


def test_the_re_run_is_on_the_old_code_not_on_the_built_tree(locked, monkeypatch, capsys):
    """built.marker exists in the working tree, so the command is green there; on the old code it is red."""
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
    assert (locked / "built.marker").exists()
    amend(capsys, LOCKED)
    change_and_commit(locked, monkeypatch, capsys, LOCKED)
    assert reverified(locked)["C1"]["status"] == "red"


WEAKENED = "print('2 passed')\n"  # always green: it no longer needs the feature


def test_an_amend_that_makes_the_test_pass_on_the_old_code_is_refused_at_the_commit(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    before, approved = head(locked), sha(locked / LOCKED)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED, WEAKENED)
    assert code != ExitCode.OK
    assert LOCKED in err and "C1" in err and "accept-green" in err and "old code" in err
    assert head(locked) == before, "nothing is committed"
    assert locked_files(locked)[LOCKED]["sha256"] == approved, "the lock still holds the approved bytes"
    assert set(lock_record(locked)["windows"]) == {LOCKED}, "the window stays open"
    assert "reverified" not in verify_red(locked)


def test_after_the_refusal_a_test_that_still_fails_on_the_old_code_goes_through(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    still_red = (locked / LOCKED).read_text(encoding="utf-8") + "# amended by a person\n"
    assert change_and_commit(locked, monkeypatch, capsys, LOCKED, WEAKENED)[0] != ExitCode.OK
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED, still_red)
    assert code == ExitCode.OK, err
    assert reverified(locked)["C1"]["status"] == "red"


def test_a_person_can_accept_a_test_that_passes_on_the_old_code_with_a_flag_and_a_reason(locked, monkeypatch, capsys):
    code, _out, err = amend(capsys, LOCKED, flags=("--accept-green",), reason="the feature already exists in the old code, only the test was missing")
    assert code == ExitCode.OK, err
    assert lock_record(locked)["windows"][LOCKED]["accept_green"] is True
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED, WEAKENED)
    assert code == ExitCode.OK, err
    assert "warning" in err.lower() and LOCKED in err, "it is still said out loud"
    entry = reverified(locked)["C1"]
    assert entry["status"] == "green" and entry["accepted"] is True
    assert locked_files(locked)[LOCKED]["sha256"] == sha(locked / LOCKED)
    text = the_decision(locked)
    assert "accept-green" in text and "the feature already exists in the old code" in text and "green" in text


def test_accepting_green_needs_a_reason(locked, capsys):
    for reason in ("", "   "):
        code, _out, err = amend(capsys, LOCKED, flags=("--accept-green",), reason=reason)
        assert code == INVALID_INPUT and "reason" in err
    assert lock_record(locked)["windows"] == {}


def test_accepting_green_for_one_file_does_not_accept_it_for_another(locked, monkeypatch, capsys):
    assert amend(capsys, LOCKED2)[0] == ExitCode.OK
    assert amend(capsys, LOCKED, flags=("--accept-green",))[0] == ExitCode.OK
    assert lock_record(locked)["windows"][LOCKED2].get("accept_green") in (None, False)
    code, _out, err = change_and_commit(locked, monkeypatch, capsys, LOCKED2, WEAKENED)
    assert code != ExitCode.OK and LOCKED2 in err and "accept-green" in err


def test_a_flag_given_after_the_first_amend_does_not_loosen_an_open_window(locked, monkeypatch, capsys):
    """Opening the same file again without the flag takes the permission back: the last word of the person counts."""
    assert amend(capsys, LOCKED, flags=("--accept-green",))[0] == ExitCode.OK
    assert amend(capsys, LOCKED)[0] == ExitCode.OK
    assert change_and_commit(locked, monkeypatch, capsys, LOCKED, WEAKENED)[0] != ExitCode.OK


def test_a_configuration_file_amend_re_runs_every_plan_item_that_has_a_command(locked, monkeypatch, capsys):
    amend(capsys, "conftest.py")
    change_and_commit(locked, monkeypatch, capsys, "conftest.py", "import pytest  # amended\n")
    assert set(reverified(locked)) == {"C1", "C2"}
    assert reverified(locked)["C2"]["command"] == FLIP2


def test_an_item_without_automatic_tests_is_not_run(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"conftest.py": "import pytest\n"})
    lock_tests(repo, monkeypatch, capsys, blocks=(block("C1", "Build it"), no_test_block("C2", "Test it")))
    amend(capsys, "conftest.py")
    change_and_commit(repo, monkeypatch, capsys, "conftest.py", "import pytest  # amended\n")
    assert set(reverified(repo)) == {"C1"}


def test_the_throwaway_checkout_is_gone_and_the_working_tree_is_as_it_was(locked, monkeypatch, capsys):
    amend(capsys, LOCKED)
    change_and_commit(locked, monkeypatch, capsys, LOCKED)
    listing = git(locked, "worktree", "list", "--porcelain")
    assert len(re.findall(r"^worktree ", listing, flags=re.M)) == 1
    assert (locked / "built.marker").exists() and git(locked, "status", "--porcelain", "--untracked-files=no") == ""


def test_the_red_proof_of_the_test_spec_is_not_overwritten_by_the_re_run(locked, monkeypatch, capsys):
    before = verify_red(locked)["results"]
    amend(capsys, LOCKED)
    change_and_commit(locked, monkeypatch, capsys, LOCKED)
    record = verify_red(locked)
    assert record["results"] == before and record["head"]
    assert record["results"]["C1"]["status"] == "red"


# ------------------------------------------------------------------ a shared file is amended by its test settings


def test_the_test_settings_of_a_shared_file_are_changed_through_a_window_like_any_locked_test(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"pyproject.toml": PYTEST_PYPROJECT})
    lock_tests(repo, monkeypatch, capsys)
    (repo / "built.marker").write_text("x\n", encoding="utf-8")
    assert amend(capsys, "pyproject.toml")[0] == ExitCode.OK
    old = locked_files(repo)["pyproject.toml"]["sha256"]
    code, _out, err = change_and_commit(repo, monkeypatch, capsys, "pyproject.toml", PYTEST_PYPROJECT.replace('"-q"', '"-q -ra"'))
    assert code == ExitCode.OK, err
    entry = locked_files(repo)["pyproject.toml"]
    assert entry["scope"] == "part" and entry["sha256"] != old
    assert lock_record(repo)["windows"] == {} and run(capsys, "tests", "check")[0] == ExitCode.OK
    assert set(reverified(repo)) == {"C1", "C2"}, "a file that holds test settings can change every item"
