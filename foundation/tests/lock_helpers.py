"""Shared builders for the locked-test tests (phase E-lock).

Not a test module. Design these helpers rest on (the tests that use them pin it):

- A workflow step with ``lock_on_approval: true`` (here ``test-spec``) locks files when a person approves it. Which files:
  the test files named in the ``- tests:`` lines of the step's report; the files listed under the heading
  ``## Hạ tầng test`` of that report (``- <path>`` per line, or ``không có``); and the test configuration files that
  already exist in the project under well-known names (``conftest.py`` anywhere, ``pytest.ini``, ``tox.ini``,
  ``jest.config.*``, ``vitest.config.*``, ...; ``pyproject.toml`` and ``setup.cfg`` only when they hold pytest settings).
- ``.agentflow/tasks/<task>/locked-files.json`` keeps ``files`` (path -> ``sha256`` of the bytes, ``kind`` ``test`` or
  ``infra``) and ``windows`` (path -> why a person opened it for a change). ``integrity.json`` keeps the hash of that file
  under ``locked_files_sha256``.
- The lock holds from the approval of the step until the task is done or cancelled. It is the same for every role.
- The gate ``locked-files-intact`` (and the gate ``tests-pass``, before it runs anything) compares the working tree and
  ``HEAD`` with the hashes; ``agentflow tests check`` does the same on request and changes nothing.
- A person changes an approved test with ``agentflow tests amend <file>... --reason "..."``, then the file is edited and
  committed with ``agentflow commit``, which closes the window.
- Exit codes: 25 GATE_FAILED, 37 INTEGRITY_FAILED, 22 INVALID_INPUT.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from checklist_helpers import checklist_path, tick
from conftest import git, write_workflow
from sdd_helpers import PLAN, init_workspace, run, say
from spec_helpers import FLIP, GREEN, SCRIPTS, at_spec_step, block, spec_report  # noqa: F401 - FLIP is re-exported to the tests

from agentflow.constants import CliKind, ExitCode, HookEvent
from agentflow.git import GitBranchLookup
from agentflow.hook import handle_hook
from agentflow.scanner import ScanResult

GATE_FAILED = 25
INVALID_INPUT = 22
INTEGRITY_FAILED = 37
EXE = f'"{sys.executable}"'

PLAN2 = PLAN + "\n### C2 - Test it\n- role: builder\n- files: b.txt\n- done-when: `true`\n- docs: https://docs.example/b\n"
INFRA_HEADING = "## Hạ tầng test"

# Extra scripts: a second test file that goes green after the build, one that reports the environment it was started in.
EXTRA_SCRIPTS = {
    "flip2.py": SCRIPTS["flip.py"],
    "test_b.py": "def test_y():\n    assert False\n",
    "envcheck.py": "import os, sys\nsys.exit(1 if os.environ.get('PYTEST_ADDOPTS') or os.environ.get('PYTEST_PLUGINS') else 0)\n",
}
FLIP2 = f"{EXE} tests/flip2.py"
LOCKED = "tests/flip.py"
LOCKED2 = "tests/flip2.py"

PYTEST_PYPROJECT = '[project]\nname = "demo"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n'
PLAIN_PYPROJECT = '[project]\nname = "demo"\nversion = "1"\n'
# The same project with something else changed (a dependency, a version, a script): the test settings are as they were.
PYPROJECT_OTHER_PART = '[project]\nname = "demo"\nversion = "2"\ndependencies = ["requests"]\n\n[tool.black]\nline-length = 100\n\n[tool.pytest.ini_options]\naddopts = "-q"\n'
PYPROJECT_SOFT = PYTEST_PYPROJECT.replace('"-q"', '"-q -k nothing"')
SETUP_CFG_PYTEST = "[metadata]\nname = demo\n\n[tool:pytest]\naddopts = -q\n"
SETUP_CFG_OTHER_PART = "[metadata]\nname = demo\nversion = 2\n\n[options]\ninstall_requires = requests\n\n[tool:pytest]\naddopts = -q\n"
SETUP_CFG_SOFT = SETUP_CFG_PYTEST.replace("-q", "-q -k nothing")
PACKAGE_JSON_TEST = '{\n  "name": "demo",\n  "scripts": {"build": "tsc", "test": "jest"},\n  "jest": {"testMatch": ["**/*.spec.js"]},\n  "dependencies": {}\n}\n'
PACKAGE_JSON_OTHER_PART = '{\n  "name": "demo",\n  "version": "2",\n  "scripts": {"build": "tsc -b", "lint": "eslint .", "test": "jest"},\n  "jest": {"testMatch": ["**/*.spec.js"]},\n  "dependencies": {"left-pad": "1.3.0"}\n}\n'
PACKAGE_JSON_SOFT_JEST = PACKAGE_JSON_TEST.replace('"**/*.spec.js"', '"**/nothing.js"')
PACKAGE_JSON_SOFT_SCRIPT = PACKAGE_JSON_TEST.replace('"test": "jest"', '"test": "echo ok"')
# Files that only exist for the tests, and shared files that carry test settings; what each holds when it is made to skip tests.
DEDICATED = ["conftest.py", "tests/conftest.py", "pytest.ini", "tox.ini", "jest.config.js", "vitest.config.ts"]
SHARED = ["pyproject.toml", "setup.cfg", "package.json"]
SOFT_BODY = {
    "conftest.py": "import pytest\n\ndef pytest_collection_modifyitems(items):\n    items.clear()\n",
    "tests/conftest.py": "import pytest\n\ndef pytest_collection_modifyitems(items):\n    items.clear()\n",
    "pytest.ini": "[pytest]\naddopts = -k nothing\n",
    "tox.ini": "[tox]\nenvlist = py\n[pytest]\naddopts = -k nothing\n",
    "jest.config.js": "module.exports = {testMatch: []};\n",
    "vitest.config.ts": "export default {test: {include: []}};\n",
    "pyproject.toml": PYPROJECT_SOFT,
    "setup.cfg": SETUP_CFG_SOFT,
    "package.json": PACKAGE_JSON_SOFT_SCRIPT,
}


class Clean:
    def __init__(self, runner=None) -> None:
        pass

    def scan_staged(self, repo):
        return ScanResult(True, "")


def clean_scanner(monkeypatch) -> None:
    monkeypatch.setattr("agentflow.cli.ContainerGitleaksScanner", Clean)


# ------------------------------------------------------------------ the project


def lock_workflow(tmp_path: Path, *, build_gates=("locked-files-intact",), check_gates=("locked-files-intact", "tests-pass")) -> Path:
    """plan -> test-spec (locks on approval) -> build -> check -> review (needs a person, the last step)."""
    data = {
        "schema_version": 1,
        "family": "sample",
        "max_rounds": 3,
        "sizes": {"default": "normal", "profiles": {"normal": {}, "small": {"skip_approval": ["plan"]}}},
        "steps": [
            {"id": "plan", "name": "Plan", "role": "lead", "requires_approval": True, "gates": ["plan-valid"]},
            {
                "id": "test-spec",
                "name": "Tests first",
                "role": "tester",
                "requires_approval": True,
                "gates": ["test-spec-valid"],
                "on_fail": "plan",
                "lock_on_approval": True,
                "approval_checklist": ["Do the tests measure the done-when?"],
                "approval_items": ["spec-items", "locked-files"],
            },
            {"id": "build", "name": "Build", "role": "builder", "gates": list(build_gates)},
            {"id": "check", "name": "Check", "role": "checker", "gates": list(check_gates), "on_fail": "build"},
            {"id": "review", "name": "Review", "role": "reviewer", "requires_approval": True, "gates": ["locked-files-intact"], "on_fail": "build"},
        ],
    }
    return write_workflow(tmp_path / "plugin" / "workflow.yaml", data)


def start_lock(repo: Path, tmp_path: Path, monkeypatch, capsys, **workflow_options) -> Path:
    """A workspace on ``lock_workflow`` with the test scripts committed on develop."""
    init_workspace(repo, lock_workflow(tmp_path, **workflow_options), monkeypatch, capsys)
    clean_scanner(monkeypatch)
    tests = repo / "tests"
    tests.mkdir()
    for name, body in {**SCRIPTS, **EXTRA_SCRIPTS}.items():
        (tests / name).write_text(body, encoding="utf-8")
    (tests / "test_a.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "add test scripts")
    # The project's own test command: it passes whatever the tests are, so only the spec commands decide the gate.
    assert run(capsys, "config", "set", "test_command", GREEN)[0] == ExitCode.OK
    return repo


def commit_files(repo: Path, files: dict[str, str], message: str = "add files") -> None:
    """Write and commit files with plain git (the harness, not an agent)."""
    for name, body in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


def spec_text(*blocks: str, infra: list[str] | None = None) -> str:
    """A test-spec report; ``infra`` adds the ``## Hạ tầng test`` section (an empty list writes ``không có``)."""
    text = spec_report(*blocks)
    if infra is None:
        return text
    body = "không có\n" if not infra else "".join(f"- {name}\n" for name in infra)
    return f"{text}\n{INFRA_HEADING}\n\n{body}"


def both_blocks() -> tuple[str, str]:
    return block("C1", "Build it"), block("C2", "Test it", command=FLIP2)


def to_awaiting(repo: Path, monkeypatch, capsys, *, blocks=None, infra=None, plan: str = PLAN2, extra=()) -> None:
    """The plan is approved and the test-spec report passed the gate: the checklist waits for a person."""
    at_spec_step(repo, monkeypatch, capsys, plan, *extra)
    chosen = blocks or both_blocks()
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_text(*chosen, infra=infra)) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    capsys.readouterr()


def lock_tests(repo: Path, monkeypatch, capsys, **options) -> None:
    """Approve the test-spec step: the files are locked and the ``build`` step is in progress."""
    to_awaiting(repo, monkeypatch, capsys, **options)
    tick(checklist_path(repo, "test-spec"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    capsys.readouterr()


def to_check(repo: Path, monkeypatch, capsys) -> None:
    """The build is done (``built.marker`` turns the test commands green) and the ``check`` step is in progress."""
    (repo / "built.marker").write_text("x\n", encoding="utf-8")
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    capsys.readouterr()


def next_task_at_spec(repo: Path, monkeypatch, capsys, title: str = "Next one") -> None:
    """After a finished task: a new task whose plan is approved, with the test-spec step in progress."""
    assert say(monkeypatch, "task", "new", title) == ExitCode.OK
    assert say(monkeypatch, "report", "--step", "plan", text=PLAN2) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    capsys.readouterr()


def finish_task(repo: Path, monkeypatch, capsys) -> None:
    """From the ``build`` step of a locked task to ``done`` (sealed); develop is checked out again."""
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # check
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # review
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    git(repo, "switch", "-q", "develop")
    (repo / "built.marker").unlink(missing_ok=True)
    capsys.readouterr()


# ------------------------------------------------------------------ reading what agentflow kept


def workspace(repo: Path) -> Path:
    return repo / ".agentflow"


def lock_path(repo: Path, task: str = "T-001") -> Path:
    return workspace(repo) / "tasks" / task / "locked-files.json"


def lock_record(repo: Path, task: str = "T-001") -> dict:
    return json.loads(lock_path(repo, task).read_text(encoding="utf-8"))


def locked_files(repo: Path, task: str = "T-001") -> dict[str, dict]:
    return lock_record(repo, task)["files"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrity(repo: Path) -> dict:
    return json.loads((workspace(repo) / "integrity.json").read_text(encoding="utf-8"))


def verify_red(repo: Path, task: str = "T-001") -> dict:
    return json.loads((workspace(repo) / "tasks" / task / "verify-red.json").read_text(encoding="utf-8"))


def decisions(repo: Path, needle: str = "") -> list[Path]:
    folder = workspace(repo) / "decisions"
    return sorted(p for p in folder.glob("*") if needle in p.name) if folder.is_dir() else []


def step_now(repo: Path) -> tuple[str, str]:
    tasks = json.loads((workspace(repo) / "state.json").read_text(encoding="utf-8"))["tasks"]
    task = tasks[-1]
    return task["current_step"], task["step_status"]


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD")


def stage_and_commit(repo: Path, monkeypatch, capsys, message: str = "change") -> tuple[int, str, str]:
    """``agentflow commit`` of what is staged, the way an agent has to commit."""
    capsys.readouterr()
    code = say(monkeypatch, "commit", message)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ------------------------------------------------------------------ hook calls


def hook(
    repo: Path,
    cli: CliKind = CliKind.CLAUDE,
    *,
    command: str | None = None,
    tool: str = "Bash",
    path: str | Path | None = None,
    cwd: Path | None = None,
    extra: dict | None = None,
) -> str:
    """The reply of the pre-tool hook for one call, as the CLI would print it."""
    where = str(cwd or repo)
    if cli is CliKind.CLAUDE:
        tool_input = {"command": command} if command is not None else {"file_path": str(path), "content": "x"}
        payload = {"cwd": where, "tool_name": tool, "tool_input": tool_input, **(extra or {})}
    else:
        args = {"CommandLine": command, "Cwd": where} if command is not None else {"TargetFile": str(path), "CodeContent": "x"}
        payload = {"workspacePaths": [str(repo)], "toolCall": {"name": tool, "args": args}, **(extra or {})}
    return handle_hook(HookEvent.PRE_TOOL, cli, json.dumps(payload), GitBranchLookup())


def decision_of(output: str) -> str:
    if not output:
        return "allow"
    data = json.loads(output)
    found = data.get("hookSpecificOutput", {}).get("permissionDecision") or data.get("decision")
    return "ask" if found == "force_ask" else found


def reason_of(output: str) -> str:
    if not output:
        return ""
    data = json.loads(output)
    return data.get("hookSpecificOutput", {}).get("permissionDecisionReason") or data.get("reason") or ""


def decide(repo: Path, **kwargs) -> str:
    return decision_of(hook(repo, **kwargs))


def folds_case() -> bool:
    """Whether this machine's file system ignores the case of names (Windows, macOS)."""
    return os.path.normcase("A") == "a"
