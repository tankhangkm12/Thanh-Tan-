"""Chặng E-lock: the ways round the lock. Each one is either stopped by the hook or found by the step that runs the tests.

An agent that wants a green test run without the work has a few moves: edit the approved test, delete or rename it, add a
``conftest.py`` that skips it, put ``-k`` into ``addopts`` of ``pytest.ini`` or ``pyproject.toml``, or change the command
that runs the tests. Every move below is tried twice:

1. the hook gets the call the agent would make; for the moves it can read (a file tool, ``sed -i``, ``rm``, ``mv``,
   ``git mv``, ``agentflow config set``) it must deny;
2. whatever the hook said, the move is then carried out directly (this is what a script or a program the hook cannot read
   does), and the step must notice: ``agentflow tests check`` and ``task advance`` fail with exit 25 naming the file, or
   (for the test command, which lives in ``.agentflow/config.yaml``) ``task advance`` fails with exit 37.

The honest part: the hook reads a fixed list of commands. ``python -c``, ``node -e``, ``perl -pi``, ``patch``,
``git apply``, a script the agent wrote, and anything else that writes a file are not read, so for them only the second
layer exists. Two things the layers do not reach are pinned at the end so the documents have to say so.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from lock_helpers import (
    EXE,
    GATE_FAILED,
    INTEGRITY_FAILED,
    LOCKED,
    LOCKED2,
    PACKAGE_JSON_TEST,
    PLAIN_PYPROJECT,
    PYTEST_PYPROJECT,
    SETUP_CFG_PYTEST,
    commit_files,
    decide,
    decision_of,
    hook,
    lock_tests,
    start_lock,
    step_now,
    to_check,
    workspace,
)
from sdd_helpers import run, say

from agentflow.constants import ExitCode

CONFTEST_SKIP = "import pytest\n\ndef pytest_collection_modifyitems(items):\n    for item in items:\n        item.add_marker(pytest.mark.skip)\n"


@pytest.fixture
def locked(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(
        repo,
        {
            "conftest.py": "import pytest\n",
            "pytest.ini": "[pytest]\naddopts = -q\n",
            "pyproject.toml": PYTEST_PYPROJECT,
            "setup.cfg": SETUP_CFG_PYTEST,
            "package.json": PACKAGE_JSON_TEST,
        },
    )
    lock_tests(repo, monkeypatch, capsys)
    return repo


# ------------------------------------------------------------------ what a move does to the project


def append(name: str, text: str) -> Callable[[Path], None]:
    def effect(repo: Path) -> None:
        path = repo / name
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    return effect


def replace_text(name: str, old: str, new: str) -> Callable[[Path], None]:
    def effect(repo: Path) -> None:
        path = repo / name
        text = path.read_text(encoding="utf-8")
        assert old in text, f"{old!r} is not in {name}"
        path.write_text(text.replace(old, new), encoding="utf-8")

    return effect


def empty(name: str) -> Callable[[Path], None]:
    return lambda repo: (repo / name).write_text("", encoding="utf-8")


def delete(name: str) -> Callable[[Path], None]:
    return lambda repo: (repo / name).unlink()


def rename(name: str, to: str) -> Callable[[Path], None]:
    return lambda repo: (repo / name).rename(repo / to)


def create(name: str, text: str = CONFTEST_SKIP) -> Callable[[Path], None]:
    def effect(repo: Path) -> None:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")

    return effect


def edit_setting(key: str, value) -> Callable[[Path], None]:
    """What a script does to ``.agentflow/config.yaml``: read it, change a setting, write it back."""

    def effect(repo: Path) -> None:
        path = workspace(repo) / "config.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.setdefault("settings", {})[key] = value
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    return effect


def hard_link_write(name: str) -> Callable[[Path], None]:
    """Another name for the same file: the hook goes by names, so a write through the link is not seen as a write to the test."""

    def effect(repo: Path) -> None:
        os.link(repo / name, repo / "link.py")
        (repo / "link.py").write_text("", encoding="utf-8")

    return effect


@dataclass(frozen=True)
class Way:
    name: str
    attempt: dict
    effect: Callable[[Path], None]
    names: tuple[str, ...]
    must_deny: bool = False
    where: str = "lock"

    def __repr__(self) -> str:
        return self.name


WEAKEN_FLIP = replace_text(LOCKED, "sys.exit(1)", "sys.exit(0)")
SOFT_PYTEST_INI = replace_text("pytest.ini", "addopts = -q", 'addopts = -q -k "not test_x"')
SOFT_PYPROJECT = replace_text("pyproject.toml", 'addopts = "-q"', 'addopts = "-q -k nothing"')
SOFT_SETUP_CFG = replace_text("setup.cfg", "addopts = -q", "addopts = -q -k nothing")
SOFT_JEST = replace_text("package.json", '"**/*.spec.js"', '"**/nothing.js"')
SOFT_NPM_TEST = replace_text("package.json", '"test": "jest"', '"test": "echo ok"')

WAYS = [
    # --- the file tools and the shell commands the hook reads
    Way("Write replaces the test", {"tool": "Write", "path": LOCKED}, empty(LOCKED), (LOCKED,), True),
    Way("Edit softens the test", {"tool": "Edit", "path": LOCKED}, WEAKEN_FLIP, (LOCKED,), True),
    Way("MultiEdit softens the test", {"tool": "MultiEdit", "path": LOCKED2}, replace_text(LOCKED2, "sys.exit(1)", "sys.exit(0)"), (LOCKED2,), True),
    Way("sed -i softens the test", {"command": f"sed -i 's/sys.exit(1)/sys.exit(0)/' {LOCKED}"}, WEAKEN_FLIP, (LOCKED,), True),
    Way("echo > empties the test", {"command": f"echo > {LOCKED}"}, empty(LOCKED), (LOCKED,), True),
    Way("Set-Content empties the test", {"command": f"Set-Content {LOCKED} ''"}, empty(LOCKED), (LOCKED,), True),
    Way("rm deletes the test", {"command": f"rm {LOCKED}"}, delete(LOCKED), (LOCKED,), True),
    Way("Remove-Item deletes the test", {"command": f"Remove-Item {LOCKED}"}, delete(LOCKED), (LOCKED,), True),
    Way("mv renames the test", {"command": f"mv {LOCKED} tests/flip_old.py"}, rename(LOCKED, "tests/flip_old.py"), (LOCKED,), True),
    Way("git mv renames the test", {"command": f"git mv {LOCKED} tests/flip_old.py"}, rename(LOCKED, "tests/flip_old.py"), (LOCKED,), True),
    Way("git rm removes the test", {"command": f"git rm {LOCKED}"}, delete(LOCKED), (LOCKED,), True),
    Way("a conftest.py that skips every test", {"tool": "Write", "path": "conftest.py"}, append("conftest.py", CONFTEST_SKIP), ("conftest.py",), True),
    Way("a new conftest.py in a test folder", {"tool": "Write", "path": "tests/sub/conftest.py"}, create("tests/sub/conftest.py"), ("tests/sub/conftest.py",), True),
    Way("echo > makes a conftest.py", {"command": "echo 'import pytest' > tests/conftest.py"}, create("tests/conftest.py"), ("tests/conftest.py",), True),
    Way("addopts -k in pytest.ini (Edit)", {"tool": "Edit", "path": "pytest.ini"}, SOFT_PYTEST_INI, ("pytest.ini",), True),
    Way("addopts -k in pytest.ini (sed -i)", {"command": "sed -i 's/-q/-q -k nothing/' pytest.ini"}, SOFT_PYTEST_INI, ("pytest.ini",), True),
    Way("addopts -k in pyproject.toml (Edit)", {"tool": "Edit", "path": "pyproject.toml"}, SOFT_PYPROJECT, ("pyproject.toml",)),
    Way("addopts -k in setup.cfg (sed -i)", {"command": "sed -i 's/-q/-q -k nothing/' setup.cfg"}, SOFT_SETUP_CFG, ("setup.cfg",)),
    Way("testMatch emptied in package.json (Edit)", {"tool": "Edit", "path": "package.json"}, SOFT_JEST, ("package.json",)),
    Way("scripts.test replaced in package.json (Write)", {"tool": "Write", "path": "package.json"}, SOFT_NPM_TEST, ("package.json",)),
    Way("the pytest table removed from pyproject.toml", {"tool": "Write", "path": "pyproject.toml"}, create("pyproject.toml", PLAIN_PYPROJECT), ("pyproject.toml",)),
    Way("a new tox.ini", {"tool": "Write", "path": "tox.ini"}, create("tox.ini", "[tox]\n"), ("tox.ini",), True),
    Way("a new jest.config.js", {"tool": "Write", "path": "jest.config.js"}, create("jest.config.js", "module.exports = {testMatch: []};\n"), ("jest.config.js",), True),
    Way("a new vitest.config.ts", {"command": "touch vitest.config.ts"}, create("vitest.config.ts", "export default {};\n"), ("vitest.config.ts",), True),
    Way("a new package.json whose test script does nothing", {"tool": "Write", "path": "sub/package.json"}, create("sub/package.json", '{"scripts": {"test": "true"}}\n'), ("sub/package.json",)),
    # --- the test command lives in .agentflow/config.yaml
    Way("agentflow config set test_command", {"command": 'agentflow config set test_command "true"'}, edit_setting("test_command", "true"), ("config.yaml",), True, "settings"),
    Way("uv run agentflow config set test_command", {"command": 'uv run agentflow config set test_command "true"'}, edit_setting("test_command", "true"), ("config.yaml",), True, "settings"),
    Way("Write on config.yaml", {"tool": "Write", "path": ".agentflow/config.yaml"}, edit_setting("test_command", "true"), ("config.yaml",), True, "settings"),
    Way("sed -i on config.yaml", {"command": "sed -i 's/tests\\/green.py/-c pass/' .agentflow/config.yaml"}, edit_setting("test_command", f"{EXE} -c pass"), ("config.yaml",), True, "settings"),
    # --- the moves the hook cannot read: only the hashes see them
    Way("python -c empties the test", {"command": f"python -c \"open('{LOCKED}','w').write('')\""}, empty(LOCKED), (LOCKED,)),
    Way("python -c deletes the test", {"command": f"python -c \"import os; os.remove('{LOCKED}')\""}, delete(LOCKED), (LOCKED,)),
    Way("python -c renames the test", {"command": f"python -c \"import os; os.rename('{LOCKED}', 'tests/x.py')\""}, rename(LOCKED, "tests/x.py"), (LOCKED,)),
    Way("python -c makes a conftest.py", {"command": "python -c \"open('tests/conftest.py','w').write('import pytest')\""}, create("tests/conftest.py"), ("tests/conftest.py",)),
    Way("python - <<EOF edits pytest.ini", {"command": "python - <<'EOF'\nopen('pytest.ini','a').write('x')\nEOF"}, SOFT_PYTEST_INI, ("pytest.ini",)),
    Way("python -c edits pyproject.toml", {"command": "python -c \"import pathlib; pathlib.Path('pyproject.toml').write_text('x')\""}, SOFT_PYPROJECT, ("pyproject.toml",)),
    Way("node -e softens the test", {"command": f"node -e \"require('fs').writeFileSync('{LOCKED}','')\""}, empty(LOCKED), (LOCKED,)),
    Way("perl -pi softens the test", {"command": f"perl -pi -e 's/exit\\(1\\)/exit(0)/' {LOCKED}"}, WEAKEN_FLIP, (LOCKED,)),
    Way("patch softens the test", {"command": "patch -p0 < soften.diff"}, WEAKEN_FLIP, (LOCKED,)),
    Way("git apply softens the test", {"command": "git apply soften.diff"}, WEAKEN_FLIP, (LOCKED,)),
    Way("a hard link writes through to the test", {"command": "echo x > link.py"}, hard_link_write(LOCKED), (LOCKED,)),
    Way("a script the agent wrote softens the test", {"command": "python tests/hack.py"}, WEAKEN_FLIP, (LOCKED,)),
    Way("python -c edits config.yaml", {"command": "python -c \"import yaml; yaml.safe_dump({}, open('.agentflow/config.yaml','w'))\""}, edit_setting("test_command", "true"), ("config.yaml",), False, "settings"),
    Way("a script edits config.yaml", {"command": "python tests/hack.py"}, edit_setting("test_command", f"{EXE} -c pass"), ("config.yaml",), False, "settings"),
]


# ------------------------------------------------------------------ how a move is found


def lock_found(repo, capsys, way: Way) -> None:
    code, out, err = run(capsys, "tests", "check")
    assert code == GATE_FAILED, f"`tests check` let {way.name} through"
    for name in way.names:
        assert name in out + err, f"`tests check` does not name {name}"
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == GATE_FAILED, f"the build step let {way.name} through"
    for name in way.names:
        assert name in err
    assert step_now(repo) == ("build", "in_progress")


def settings_found(repo, capsys, way: Way) -> None:
    (repo / "built.marker").write_text("x\n", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")  # build
    if code == ExitCode.OK:
        code, _out, err = run(capsys, "task", "advance", "--result", "pass")  # check: tests-pass
    assert code == INTEGRITY_FAILED, f"no step noticed {way.name}"
    assert "config.yaml" in err and "test_command" in err
    assert step_now(repo)[0] in {"build", "check"}


@pytest.mark.parametrize("way", WAYS, ids=lambda way: way.name)
def test_every_way_round_the_lock_is_stopped_or_found(locked, capsys, way):
    if "tests/hack.py" in way.attempt.get("command", ""):
        (locked / "tests" / "hack.py").write_text("open('tests/flip.py', 'w').write('')\n", encoding="utf-8")
    output = hook(locked, **{**way.attempt, **({"path": locked / way.attempt["path"]} if "path" in way.attempt else {})})
    if way.must_deny:
        assert decision_of(output) == "deny", f"the hook let this through: {way.attempt}"
    way.effect(locked)
    (lock_found if way.where == "lock" else settings_found)(locked, capsys, way)


def test_the_hook_does_not_read_interpreters_and_patch_tools_and_says_so(locked):
    """Not a promise to keep forever, a statement the documents have to match: these are found by the hashes, not stopped."""
    unread = [way for way in WAYS if not way.must_deny]
    assert len(unread) >= 10
    for way in unread:
        assert decide(locked, **{**way.attempt, **({"path": locked / way.attempt["path"]} if "path" in way.attempt else {})}) == "allow", way.name


# ------------------------------------------------------------------ the test command is the person's


def test_a_person_changing_the_test_command_with_the_cli_is_not_flagged(locked, monkeypatch, capsys):
    assert run(capsys, "config", "set", "test_command", f"{EXE} tests/green.py --fast")[0] == ExitCode.OK
    to_check(locked, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert step_now(locked) == ("review", "in_progress")


def test_a_hand_edited_command_stops_the_check_step_even_when_the_build_step_had_no_gate(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys, build_gates=(), check_gates=("tests-pass",))
    lock_tests(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    edit_setting("test_command", "true")(repo)
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == INTEGRITY_FAILED and "config.yaml" in err
    assert step_now(repo) == ("check", "in_progress")


def first_refusal(repo, capsys) -> tuple[int, str]:
    """The build step and the check step, one after the other, until one of them refuses."""
    (repo / "built.marker").write_text("x\n", encoding="utf-8")
    for _ in range(2):
        code, _out, err = run(capsys, "task", "advance", "--result", "pass")
        if code != ExitCode.OK:
            return code, err
    return ExitCode.OK, ""


def test_a_person_who_has_looked_takes_the_edited_command(locked, monkeypatch, capsys):
    edit_setting("test_command", f"{EXE} tests/green.py --fast")(locked)
    code, err = first_refusal(locked, capsys)
    assert code == INTEGRITY_FAILED and "config.yaml" in err
    assert run(capsys, "state", "accept", "--reason", "I changed the command myself")[0] == ExitCode.OK
    for _ in range(2):
        if step_now(locked)[0] == "review":
            break
        assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert step_now(locked) == ("review", "in_progress")


def test_the_runner_drops_the_environment_variables_that_change_what_pytest_runs(gitflow_repo, tmp_path, monkeypatch, capsys):
    """`PYTEST_ADDOPTS="-k nothing" agentflow task advance ...` must not reach the tests agentflow runs."""
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    assert run(capsys, "config", "set", "test_command", f"{EXE} tests/envcheck.py")[0] == ExitCode.OK
    lock_tests(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k nothing")
    monkeypatch.setenv("PYTEST_PLUGINS", "evil_plugin")
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert step_now(repo) == ("review", "in_progress")


# ------------------------------------------------------------------ what does not count as a change


def test_touching_a_locked_file_without_changing_its_bytes_is_nothing(locked, capsys):
    os.utime(locked / LOCKED, (1_000_000_000, 1_000_000_000))
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


def test_rewriting_a_locked_file_with_the_same_bytes_is_nothing(locked, capsys):
    path = locked / LOCKED
    path.write_bytes(path.read_bytes())
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


def test_a_new_test_file_next_to_the_locked_ones_is_nothing(locked, capsys):
    (locked / "tests" / "test_more.py").write_text("def test_more():\n    assert True\n", encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
    assert decide(locked, tool="Write", path=locked / "tests" / "test_more.py") == "allow"


# ------------------------------------------------------------------ the limits, written down


def test_a_build_script_that_runs_the_tests_is_locked_only_when_the_tester_declares_it(gitflow_repo, tmp_path, monkeypatch, capsys):
    """`make test`, `npm test` and `tox` go through a file agentflow cannot know is test configuration. Declared, it is
    locked like the rest; not declared, it is not (the documents say so and ask the tester to declare it)."""
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"Makefile": "test:\n\t$(PY) -m pytest\n", "scripts.mk": "all:\n"})
    lock_tests(repo, monkeypatch, capsys, infra=["Makefile"])
    assert decide(repo, tool="Edit", path=repo / "Makefile") == "deny"
    assert decide(repo, tool="Edit", path=repo / "scripts.mk") == "allow"
    (repo / "scripts.mk").write_text("all:\n\ttrue\n", encoding="utf-8")
    assert run(capsys, "tests", "check")[0] == ExitCode.OK


def test_a_file_the_tests_import_is_not_locked_unless_declared(locked, capsys):
    """A helper module the tests import can make them pass; only a declared one is locked."""
    commit_files(locked, {"tests/helper_lib.py": "VALUE = 1\n"})
    (locked / "tests" / "helper_lib.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert decide(locked, tool="Edit", path=locked / "tests" / "helper_lib.py") == "allow"
    assert run(capsys, "tests", "check")[0] == ExitCode.OK
