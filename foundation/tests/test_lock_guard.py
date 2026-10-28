"""Chặng E-lock (E2): while a task has approved tests, the pre-tool hook keeps every tool and command away from them.

Once ``locked-files.json`` exists for a task that is still going, the hook denies, for every role and both CLIs:
- a file tool (Write, Edit, MultiEdit, NotebookEdit; Antigravity's three) aimed at a locked file;
- a shell command (Bash, PowerShell, ``run_command``) that writes, deletes, moves or copies over a locked file, in the
  forms the guard already reads for ``.ThanhTan/`` (redirects, tee, sed -i, cp, mv, rm, dd, truncate, Set-Content...);
- a git command that brings a locked file back from another commit (``git checkout <ref> -- file``, ``git restore -s``)
  or removes or renames it (``git rm``, ``git mv``);
- the creation of a test configuration file that is not in the lock (``conftest.py``, ``pytest.ini``, ``tox.ini``,
  ``jest.config.*``, ``vitest.config.*``...), and any change to such a file that exists.
Reading a locked file, running it, and creating an ordinary new test file stay free. The lock ends when the task is done or
cancelled, and it starts at the approval. The reason of a denial names ``agentflow tests amend``, the person's way in.
What the hook cannot see (a script that writes the file) is found by the hashes: see test_lock_bypass.py.
"""

import json

import pytest
from checklist_helpers import checklist_path, tick
from lock_helpers import (
    PACKAGE_JSON_TEST,
    PYTEST_PYPROJECT,
    SETUP_CFG_PYTEST,
    LOCKED,
    LOCKED2,
    commit_files,
    decide,
    decision_of,
    finish_task,
    folds_case,
    hook,
    lock_tests,
    next_task_at_spec,
    reason_of,
    start_lock,
    to_awaiting,
    workspace,
)
from sdd_helpers import run, say

from agentflow.constants import CliKind, ExitCode

LOCKED_NAMES = [LOCKED, LOCKED2, "conftest.py", "pytest.ini"]


@pytest.fixture
def locked(gitflow_repo, tmp_path, monkeypatch, capsys):
    """tests/flip.py and tests/flip2.py (the report), conftest.py and pytest.ini (found by name) are locked."""
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"conftest.py": "import pytest\n", "pytest.ini": "[pytest]\naddopts = -q\n"})
    lock_tests(repo, monkeypatch, capsys)
    return repo


@pytest.fixture
def fresh(gitflow_repo, tmp_path, monkeypatch, capsys):
    """A task whose test-spec is waiting for approval: nothing is locked yet."""
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    to_awaiting(repo, monkeypatch, capsys)
    return repo


def denied(repo, **kwargs) -> bool:
    return decide(repo, **kwargs) == "deny"


# ------------------------------------------------------------------ file tools


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
@pytest.mark.parametrize("name", LOCKED_NAMES)
def test_a_file_tool_of_claude_code_cannot_change_a_locked_file(locked, tool, name):
    output = hook(locked, tool=tool, path=locked / name)
    assert decision_of(output) == "deny"
    assert "tests amend" in reason_of(output) and "person" in reason_of(output).lower()


@pytest.mark.parametrize("tool", ["write_to_file", "replace_file_content", "multi_replace_file_content"])
@pytest.mark.parametrize("name", LOCKED_NAMES)
def test_a_file_tool_of_antigravity_cannot_change_a_locked_file(locked, tool, name):
    output = hook(locked, CliKind.ANTIGRAVITY, tool=tool, path=locked / name)
    assert decision_of(output) == "deny" and "tests amend" in reason_of(output)


@pytest.mark.parametrize(
    "path, cwd",
    [
        ("tests/flip.py", None),
        ("./tests/flip.py", None),
        ("tests/../tests/flip.py", None),
        ("tests//flip.py", None),
        ("tests\\flip.py", None),
        ("../tests/flip.py", "tests"),
        ("flip.py", "tests"),
        ("./flip.py", "tests"),
        ("../conftest.py", "tests"),
    ],
)
def test_a_relative_or_untidy_path_to_a_locked_file_does_not_get_round_the_lock(locked, path, cwd):
    where = locked / cwd if cwd else None
    assert denied(locked, tool="Write", path=path, cwd=where)


@pytest.mark.skipif(not folds_case(), reason="this file system tells A from a")
def test_the_case_of_a_name_does_not_get_round_the_lock_where_the_file_system_ignores_it(locked):
    assert denied(locked, tool="Write", path=locked / "TESTS" / "FLIP.PY")
    assert denied(locked, tool="Write", path=locked / "Conftest.PY")


def test_a_symbolic_link_to_a_locked_file_does_not_get_round_the_lock(locked):
    link = locked / "link.py"
    try:
        link.symlink_to(locked / LOCKED)
    except (OSError, NotImplementedError):
        pytest.skip("this machine cannot make symbolic links")
    assert denied(locked, tool="Write", path=link)
    assert denied(locked, command="echo x > link.py")


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
@pytest.mark.parametrize("name", ["tests/test_new.py", "tests/helpers.py", "tests/mark.py", "app.py", "src/app.py", "README.md", "docs/notes.md"])
def test_a_file_that_is_not_locked_stays_free(locked, tool, name):
    assert decide(locked, tool=tool, path=locked / name) == "allow"


@pytest.mark.parametrize("cli, tool", [(CliKind.CLAUDE, "Write"), (CliKind.ANTIGRAVITY, "write_to_file")])
@pytest.mark.parametrize("agent", [None, "tester", "implementer-deep", "implementer-fast", "reviewer", "general-purpose"])
def test_the_lock_is_the_same_for_every_role(locked, cli, tool, agent):
    extra = {"agent_type": agent, "agent_id": "a1"} if agent else None
    assert decision_of(hook(locked, cli, tool=tool, path=locked / LOCKED, extra=extra)) == "deny"


# ------------------------------------------------------------------ shell commands


WRITES = [
    "echo x > {p}",
    "echo x >> {p}",
    "echo x>{p}",
    "printf x | tee {p}",
    "printf x | tee -a {p}",
    "sed -i 's/a/b/' {p}",
    "sed -i.bak 's/a/b/' {p}",
    "sed --in-place s/a/b/ {p}",
    "cp tests/red.py {p}",
    "cp -f tests/red.py {p}",
    "cp -t tests tests/red.py && mv tests/red.py {p}",
    "mv tests/red.py {p}",
    "mv {p} {p}.bak",
    "rm {p}",
    "rm -f {p}",
    "unlink {p}",
    "truncate -s 0 {p}",
    "dd if=tests/red.py of={p}",
    "bash -c 'echo x > {p}'",
    'sh -c "rm {p}"',
    "cat > {p} <<'EOF'\nx\nEOF",
    "cat tests/red.py > {p}",
    "true && rm {p}",
    "(rm {p})",
    "Set-Content -Path {p} -Value x",
    "Add-Content {p} x",
    "Out-File -FilePath {p}",
    "Remove-Item {p}",
    "Remove-Item -Force {p}",
    "Move-Item tests/red.py {p}",
    "Move-Item {p} elsewhere.py",
    "Rename-Item {p} new.py",
    "Copy-Item tests/red.py {p}",
    '"x" | Set-Content {p}',
    'powershell -Command "Remove-Item {p}"',
    "pwsh -c 'Set-Content {p} x'",
]


@pytest.mark.parametrize("template", WRITES)
@pytest.mark.parametrize("name", [LOCKED, "conftest.py"])
def test_a_shell_command_cannot_change_a_locked_file(locked, template, name):
    output = hook(locked, command=template.format(p=name))
    assert decision_of(output) == "deny" and "tests amend" in reason_of(output)


@pytest.mark.parametrize("tool, cli", [("Bash", CliKind.CLAUDE), ("PowerShell", CliKind.CLAUDE), ("run_command", CliKind.ANTIGRAVITY)])
def test_every_shell_tool_is_held_to_the_lock(locked, tool, cli):
    assert decision_of(hook(locked, cli, tool=tool, command=f"Set-Content {LOCKED} x")) == "deny"
    assert decision_of(hook(locked, cli, tool=tool, command=f"echo x > {LOCKED}")) == "deny"


def test_a_command_run_from_a_subdirectory_is_held_to_the_lock_too(locked):
    assert denied(locked, command="cd tests && echo x > flip.py")
    assert denied(locked, command="echo x > flip.py", cwd=locked / "tests")
    assert denied(locked, command="rm ../conftest.py", cwd=locked / "tests")
    assert denied(locked, command="cd tests; Remove-Item .\\flip.py")


@pytest.mark.parametrize(
    "command",
    [
        "cat tests/flip.py",
        "type tests\\flip.py",
        "head -5 tests/flip.py",
        "grep -n def tests/flip.py",
        "Get-Content tests/flip.py",
        "python tests/flip.py",
        "python -m pytest tests/flip.py",
        "uv run pytest tests/flip.py -q",
        "cp tests/flip.py /tmp/copy.py",
        "cp tests/flip.py tests/flip_copy.py",
        "diff tests/flip.py tests/flip2.py",
        "wc -l tests/flip.py > count.txt",
        "ls -la tests",
        "echo x > tests/test_new.py",
        "echo x > notes.txt",
        "touch tests/helpers.py",
        "git status",
        "git diff tests/flip.py",
        "git log -p -- tests/flip.py",
        "git add tests/flip.py",
        "git restore tests/flip.py",
        "git restore --staged tests/flip.py",
        "git checkout -- tests/flip.py",
        "agentflow tests check",
        "agentflow tests verify-red",
        "agentflow status",
    ],
)
def test_reading_running_and_copying_from_a_locked_file_stay_free(locked, command):
    assert decide(locked, command=command) == "allow"


GIT_DENIED = [
    "git rm tests/flip.py",
    "git rm -f tests/flip.py",
    "git rm --cached tests/flip.py",
    "git mv tests/flip.py tests/other.py",
    "git mv conftest.py tests/conftest.py",
    "git checkout HEAD~1 -- tests/flip.py",
    "git checkout main -- tests/flip.py",
    "git checkout main tests/flip.py",
    "git checkout stash@{0} -- conftest.py",
    "git restore --source=HEAD~1 tests/flip.py",
    "git restore --source HEAD~1 -- tests/flip.py",
    "git restore -s HEAD~1 tests/flip.py",
    "git restore -s main --staged --worktree tests/flip.py",
]


@pytest.mark.parametrize("command", GIT_DENIED)
def test_git_cannot_take_a_locked_file_from_another_commit_remove_it_or_rename_it(locked, command):
    output = hook(locked, command=command)
    assert decision_of(output) == "deny" and "tests amend" in reason_of(output)


# ------------------------------------------------------------------ test configuration that is not there yet


NEW_CONFIG = [
    "tests/sub/conftest.py",
    "src/pkg/conftest.py",
    "tox.ini",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.json",
    "vitest.config.ts",
    "vitest.config.mts",
    "vitest.workspace.ts",
    ".mocharc.json",
    ".mocharc.yml",
    "karma.conf.js",
    "phpunit.xml",
    "phpunit.xml.dist",
]
FREE_NAMES = [
    # files that carry test settings among other things may be made: the gates look at what is in them (test_locked_files)
    "setup.cfg",
    "pyproject.toml",
    "package.json",
    "tests/test_new.py",
    "tests/test_conftest.py",
    "tests/helpers.py",
    "src/app.py",
    "conftest.txt",
    "mypytest.ini",
    "docs/pytest.ini.md",
    "tests/data/pytest.ini.sample",
    "tests/data/config.json",
]


@pytest.mark.parametrize("name", NEW_CONFIG)
@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit"])
def test_a_file_tool_cannot_create_a_test_configuration_file(locked, name, tool):
    output = hook(locked, tool=tool, path=locked / name)
    assert decision_of(output) == "deny" and "tests amend" in reason_of(output)


@pytest.mark.parametrize("name", NEW_CONFIG)
@pytest.mark.parametrize("template", ["echo x > {p}", "touch {p}", "cp tests/red.py {p}", "printf x | tee {p}", "Set-Content {p} x", "New-Item -ItemType File {p}", "cat > {p} <<EOF\nx\nEOF"])
def test_a_shell_command_cannot_create_a_test_configuration_file(locked, name, template):
    assert denied(locked, command=template.format(p=name))


@pytest.mark.parametrize("name", NEW_CONFIG[:4])
def test_antigravity_cannot_create_a_test_configuration_file_either(locked, name):
    assert decision_of(hook(locked, CliKind.ANTIGRAVITY, tool="write_to_file", path=locked / name)) == "deny"


@pytest.mark.parametrize("name", FREE_NAMES)
def test_new_ordinary_files_whose_names_only_look_like_configuration_are_free(locked, name):
    assert decide(locked, tool="Write", path=locked / name) == "allow"
    assert decide(locked, command=f"echo x > {name}") == "allow"


@pytest.fixture
def shared(gitflow_repo, tmp_path, monkeypatch, capsys):
    """pyproject.toml, setup.cfg and package.json carry test settings and are locked by those settings."""
    repo = start_lock(gitflow_repo, tmp_path, monkeypatch, capsys)
    commit_files(repo, {"pyproject.toml": PYTEST_PYPROJECT, "setup.cfg": SETUP_CFG_PYTEST, "package.json": PACKAGE_JSON_TEST})
    lock_tests(repo, monkeypatch, capsys)
    return repo


@pytest.mark.parametrize("name", ["pyproject.toml", "setup.cfg", "package.json"])
@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_a_shared_file_with_locked_test_settings_stays_open_to_the_tools(shared, name, tool):
    """The hook cannot tell which part an edit touches; the hashes can, so a dependency can still be added."""
    assert decide(shared, tool=tool, path=shared / name) == "allow"


@pytest.mark.parametrize("name", ["pyproject.toml", "setup.cfg", "package.json"])
@pytest.mark.parametrize("template", ["sed -i 's/a/b/' {p}", "echo x >> {p}", "cp tests/red.py {p}"])
def test_a_shell_command_on_a_shared_file_with_locked_test_settings_is_left_to_the_hashes(shared, name, template):
    assert decide(shared, command=template.format(p=name)) == "allow"


def test_a_configuration_file_that_exists_but_is_not_locked_is_closed_as_well(locked):
    """A file found after the lock (made by something the hook cannot see) is closed to the tools: the hashes flag it."""
    (locked / "tox.ini").write_text("[tox]\n", encoding="utf-8")
    assert denied(locked, tool="Edit", path=locked / "tox.ini")
    assert denied(locked, command="echo x >> tox.ini")
    assert denied(locked, command="rm tox.ini")


# ------------------------------------------------------------------ when the lock holds


def test_nothing_is_locked_until_a_person_approves_the_test_spec(fresh):
    assert decide(fresh, tool="Write", path=fresh / LOCKED) == "allow"
    assert decide(fresh, tool="Write", path=fresh / "conftest.py") == "allow"
    assert decide(fresh, command=f"echo x > {LOCKED}") == "allow"


@pytest.mark.parametrize("name", ["pytest.ini", "tox.ini", "pyproject.toml", "setup.cfg", "jest.config.js", "tests/conftest.py", "package.json"])
def test_the_tester_may_make_test_configuration_until_the_approval(fresh, name):
    assert decide(fresh, tool="Write", path=fresh / name) == "allow"
    assert decide(fresh, command=f"echo x > {name}") == "allow"


def test_the_lock_starts_with_the_approval(fresh, monkeypatch):
    tick(checklist_path(fresh, "test-spec"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    assert denied(fresh, tool="Write", path=fresh / LOCKED)
    assert denied(fresh, tool="Write", path=fresh / "conftest.py")


def test_the_lock_ends_when_the_task_is_done(locked, monkeypatch, capsys):
    assert denied(locked, tool="Write", path=locked / LOCKED), "it held until now"
    finish_task(locked, monkeypatch, capsys)
    assert decide(locked, tool="Write", path=locked / LOCKED) == "allow"
    assert decide(locked, command=f"echo x > {LOCKED}") == "allow"
    assert decide(locked, tool="Write", path=locked / "conftest.py") == "allow"
    assert decide(locked, tool="Write", path=locked / "tox.ini") == "allow"


def test_the_lock_ends_when_the_task_is_cancelled(locked, capsys):
    assert denied(locked, tool="Write", path=locked / LOCKED), "it held until now"
    assert run(capsys, "task", "cancel")[0] == ExitCode.OK
    assert decide(locked, tool="Write", path=locked / LOCKED) == "allow"
    assert decide(locked, tool="Write", path=locked / "tox.ini") == "allow"


def test_the_next_task_has_no_lock_until_its_own_approval(locked, monkeypatch, capsys):
    assert denied(locked, tool="Write", path=locked / LOCKED), "the first task's lock held until now"
    finish_task(locked, monkeypatch, capsys)
    next_task_at_spec(locked, monkeypatch, capsys)
    assert decide(locked, tool="Write", path=locked / LOCKED) == "allow"
    assert decide(locked, tool="Write", path=locked / "tox.ini") == "allow"


def test_a_blocked_task_keeps_its_lock(locked, capsys):
    run(capsys, "task", "advance", "--result", "fail")  # `build` has no step to go back to: the task is blocked
    state = json.loads((workspace(locked) / "state.json").read_text(encoding="utf-8"))["tasks"][0]
    assert state["status"] == "blocked"
    assert denied(locked, tool="Write", path=locked / LOCKED)
    assert denied(locked, tool="Write", path=locked / "tox.ini")


def test_a_state_file_that_cannot_be_read_does_not_open_a_lock(locked):
    (workspace(locked) / "state.json").write_text("{ not json", encoding="utf-8")
    assert denied(locked, tool="Write", path=locked / LOCKED)
    assert denied(locked, command=f"echo x > {LOCKED}")


def test_a_state_file_that_cannot_be_read_does_not_invent_a_lock(fresh):
    (workspace(fresh) / "state.json").write_text("{ not json", encoding="utf-8")
    assert decide(fresh, tool="Write", path=fresh / LOCKED) == "allow"


def test_a_project_without_a_workspace_is_left_alone(tmp_path):
    plain = tmp_path / "plain"
    (plain / "tests").mkdir(parents=True)
    assert decision_of(hook(plain, tool="Write", path=plain / "tests" / "flip.py")) == "allow"


def test_a_call_with_nothing_to_judge_is_let_through(locked):
    assert decision_of(hook(locked, command="")) == "allow"
    assert decision_of(hook(locked, tool="Write", path="")) == "allow"


# ------------------------------------------------------------------ the person's commands are the person's


AMEND = "agentflow tests amend tests/flip.py --reason 'the expected value was wrong'"
AMEND_FORMS = [
    AMEND,
    "AGENTFLOW.EXE tests amend tests/flip.py --reason x",
    "uv run agentflow tests amend tests/flip.py --reason x",
    "agentflow tests amend tests/flip.py --accept-green --reason 'the test is meant to pass now'",
    "uv run agentflow tests amend tests/flip.py --reason x --accept-green",
    "uv run --project foundation agentflow tests amend tests/flip.py --reason x",
    "uvx agentflow tests amend tests/flip.py --reason x",
    "python -m agentflow tests amend tests/flip.py --reason x",
    "py -3 -m agentflow tests amend tests/flip.py --reason x",
    "timeout 5 agentflow tests amend tests/flip.py --reason x",
    "FOO=1 agentflow tests amend tests/flip.py --reason x",
    "cd tests && agentflow tests amend flip.py --reason x",
    "bash -c \"agentflow tests amend tests/flip.py --reason x\"",
    "powershell -Command \"agentflow tests amend tests/flip.py --reason x\"",
    r"C:\Users\x\.local\bin\agentflow.exe tests amend tests/flip.py --reason x",
    "/home/x/.local/bin/agentflow tests amend tests/flip.py --reason x",
    "cat <<EOF | bash\nagentflow tests amend tests/flip.py --reason x\nEOF",
    "echo 'agentflow tests amend tests/flip.py --reason x' | sh",
    "Start-Process agentflow -ArgumentList 'tests amend tests/flip.py --reason x'",
]


@pytest.mark.parametrize("command", AMEND_FORMS)
def test_an_agent_cannot_amend_an_approved_test_in_any_form(locked, command):
    output = hook(locked, command=command)
    assert decision_of(output) == "deny" and "person" in reason_of(output).lower()


@pytest.mark.parametrize("command", AMEND_FORMS[:6])
def test_antigravity_cannot_amend_an_approved_test_either(locked, command):
    assert decision_of(hook(locked, CliKind.ANTIGRAVITY, tool="run_command", command=command)) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "agentflow tests check",
        "uv run agentflow tests check",
        "python -m agentflow tests check",
        "agentflow tests verify-red",
        "echo 'run agentflow tests amend later'",
        "grep -rn 'tests amend' docs",
    ],
)
def test_checking_the_tests_and_talking_about_amending_are_not_amending(locked, command):
    assert decide(locked, command=command) == "allow"


@pytest.mark.parametrize(
    "command",
    [
        'agentflow config set test_command "true"',
        'uv run agentflow config set test_command "true"',
        'agentflow config set test_timeout_minutes 1',
        "agentflow state accept --reason ok",
        "agentflow project confirm profile",
    ],
)
def test_the_commands_that_change_what_the_tests_run_or_accept_a_change_stay_the_persons(locked, command):
    assert denied(locked, command=command)


@pytest.mark.parametrize(
    "path",
    [".ThanhTan/config.yaml", ".ThanhTan/tasks/T-001/locked-files.json", ".ThanhTan/tasks/T-001/verify-red.json", ".ThanhTan/integrity.json", ".ThanhTan/project/profile.md"],
)
def test_the_files_that_say_what_is_locked_and_what_is_run_are_closed_to_the_tools(locked, path):
    assert denied(locked, tool="Write", path=locked / path)
    assert denied(locked, tool="Edit", path=locked / path)
    assert denied(locked, command=f"echo x > {path}")
    assert denied(locked, command=f"rm {path}")
    assert denied(locked, command=f"sed -i 's/a/b/' {path}")
