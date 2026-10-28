"""Shared builders for the test-spec and tests-pass tests (phase E-spec).

Not a test module. Design these helpers rest on (the tests that use them pin it):

- A workflow step with the gate ``test-spec-valid`` is the step where the tester writes the tests first. Its report has
  one block per plan item (the plan is the report of the first step that has the gate ``plan-valid``):

      ### C1 - Title of the plan item
      - tests: tests/test_a.py::test_x, tests/test_a.py::test_y        (or: không có — <how it is checked instead>)
      - command: `<the command that runs them>`
      - red: fail
      - reason: <why they fail: the feature is not there yet>
      - output: |
          <the tail of the output>

- At ``task advance --result pass`` thanhtan runs each command itself and needs it to fail (exit code other than 0, and
  not 126/127, and not a timeout). It writes ``.ThanhTan/tasks/<task>/verify-red.json``. The same runner serves the gate
  ``tests-pass``, which runs the project's test command and writes ``tasks/<task>/tests-pass.json``.
- The command of ``tests-pass``: setting ``test_command`` (``thanhtan config set``), else the line
  ``- test-command: <command>`` of a *confirmed* ``project/profile.md``. Timeout: setting ``test_timeout_minutes``,
  default 15.
- Exit code 25 (GATE_FAILED) when a gate refuses.
"""

import json
import re
import sys
from pathlib import Path

from checklist_helpers import checklist_path, tick
from conftest import git, write_workflow
from sdd_helpers import PLAN, init_workspace, project_dir, run, say

from thanhtan.constants import ExitCode

GATE_FAILED = 25
INVALID_INPUT = 22
EXE = f'"{sys.executable}"'

PLAN2 = PLAN + "\n### C2 - Test it\n- role: builder\n- files: b.txt\n- done-when: `true`\n- docs: https://docs.example/b\n"
PLAN_OTHER = (
    "### C1 - Write the guide\n- role: builder\n- files: guide.md\n- kind: other\n"
    "- done-when: the guide is linked from the README\n- docs: https://docs.example/a\n"
)
PLAN_MIXED = PLAN_OTHER + "\n### C2 - Code it\n- role: builder\n- files: b.txt\n- kind: implement\n- done-when: `true`\n- docs: https://docs.example/b\n"

SCRIPTS = {
    "red.py": "import sys\nprint('FAILED tests/test_a.py::test_x - feature missing')\nsys.exit(1)\n",
    "flip.py": "import os, sys\nif os.path.exists('built.marker'):\n    print('2 passed')\n    sys.exit(0)\nprint('FAILED tests/test_a.py::test_x - feature missing')\nsys.exit(1)\n",
    "green.py": "print('2 passed')\n",
    "slow.py": "import time\ntime.sleep(8)\n",
    "loud.py": "import sys\nprint('x' * 20000 + 'THE-END')\nsys.exit(1)\n",
    "where.py": "import os, sys\nprint('CWD=' + os.getcwd())\nsys.exit(1)\n",
    "mark.py": "import sys\nopen('ran.marker', 'a').write('x')\nsys.exit(1)\n",
    "mark_ok.py": "open('ran.marker', 'a').write('x')\n",
}
RED = f"{EXE} tests/red.py"  # always fails
FLIP = f"{EXE} tests/flip.py"  # fails until built.marker exists: red before the build, green after
GREEN = f"{EXE} tests/green.py"


def spec_workflow(tmp_path: Path) -> Path:
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
                "approval_checklist": ["Do the tests measure the done-when?"],
                "approval_items": ["spec-items"],
            },
            {"id": "build", "name": "Build", "role": "builder"},
            {"id": "check", "name": "Check", "role": "checker", "gates": ["tests-pass"], "on_fail": "build"},
        ],
    }
    return write_workflow(tmp_path / "plugin" / "workflow.yaml", data)


def start(repo: Path, tmp_path: Path, monkeypatch, capsys) -> Path:
    init_workspace(repo, spec_workflow(tmp_path), monkeypatch, capsys)
    tests = repo / "tests"
    tests.mkdir()
    for name, body in SCRIPTS.items():
        (tests / name).write_text(body, encoding="utf-8")
    (tests / "test_a.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "add test scripts")
    return repo


def at_spec_step(repo: Path, monkeypatch, capsys, plan: str = PLAN2, *extra: str) -> None:
    """A new task whose plan is approved: the test-spec step is in progress."""
    assert say(monkeypatch, "task", "new", "Do it", *extra) == ExitCode.OK
    assert say(monkeypatch, "report", "--step", "plan", text=plan) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    if json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][0]["step_status"] == "awaiting_approval":
        assert say(monkeypatch, "task", "approve") == ExitCode.OK
    capsys.readouterr()


def block(code: str, title: str, *, tests: str | None = None, command: str = FLIP, red: str | None = "fail", reason: str | None = "the feature is not there yet", output: str | None = "FAILED tests/test_a.py::test_x") -> str:
    if tests is None:
        named = re.search(r"tests/\w+\.py", command or "")
        tests = f"{named.group()}::test_x" if named else "tests/flip.py::test_x"
    lines = [f"### {code} - {title}", f"- tests: {tests}"]
    if command is not None:
        lines.append(f"- command: `{command}`")
    if red is not None:
        lines.append(f"- red: {red}")
    if reason is not None:
        lines.append(f"- reason: {reason}")
    if output is not None:
        lines += ["- output: |", f"    {output}"]
    return "\n".join(lines) + "\n"


def no_test_block(code: str, title: str, how: str | None = "run it by hand and look at the page") -> str:
    suffix = "" if how is None else f" — {how}"
    return f"### {code} - {title}\n- tests: không có{suffix}\n"


def spec_report(*blocks: str) -> str:
    return "# Test-spec\n\n" + "\n".join(blocks)


def write_spec(monkeypatch, *blocks: str) -> None:
    assert say(monkeypatch, "report", "--step", "test-spec", text=spec_report(*blocks)) == ExitCode.OK


def both_red() -> tuple[str, str]:
    return block("C1", "Build it"), block("C2", "Test it")


def advance(capsys) -> tuple[int, str, str]:
    return run(capsys, "task", "advance", "--result", "pass")


def task_dir(repo: Path) -> Path:
    return repo / ".ThanhTan" / "tasks" / "T-001"


def verify_red_record(repo: Path) -> dict:
    return json.loads((task_dir(repo) / "verify-red.json").read_text(encoding="utf-8"))


def tests_pass_record(repo: Path) -> dict:
    return json.loads((task_dir(repo) / "tests-pass.json").read_text(encoding="utf-8"))


tests_pass_record.__test__ = False  # a name that pytest would take for a test when a test module imports it


def step_now(repo: Path) -> tuple[str, str]:
    task = json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][0]
    return task["current_step"], task["step_status"]


def set_config(capsys, key: str, value: str) -> None:
    code, _out, err = run(capsys, "config", "set", key, value)
    assert code == ExitCode.OK, err


def write_profile(repo: Path, text: str, *, confirm: bool = True, capsys=None) -> None:
    project_dir(repo).mkdir(parents=True, exist_ok=True)
    (project_dir(repo) / "profile.md").write_text(text, encoding="utf-8")
    if confirm:
        assert say_confirm(capsys) == ExitCode.OK


def say_confirm(capsys) -> int:
    from thanhtan.cli import main

    code = main(["project", "confirm", "profile"])
    if capsys is not None:
        capsys.readouterr()
    return code


def profile_with(command: str) -> str:
    return f"# Profile\n\nA sample project.\n\n## Build\n- build-command: `make`\n- test-command: `{command}`\n"


def at_test_step(repo: Path, monkeypatch, capsys, plan: str = PLAN2, blocks: tuple[str, ...] | None = None, built: bool = True) -> None:
    """The plan and the test-spec step are approved and the build is done; the `check` step (tests-pass) is in progress.

    ``built`` creates ``built.marker``, which turns the commands of ``flip.py`` from red to green (the "implementation")."""
    at_spec_step(repo, monkeypatch, capsys, plan)
    if blocks is None:
        blocks = (block("C1", "Build it"),) + ((block("C2", "Test it"),) if "C2" in plan else ())
    write_spec(monkeypatch, *blocks)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    tick(checklist_path(repo, "test-spec"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # build
    if built:
        (repo / "built.marker").write_text("x\n", encoding="utf-8")
    capsys.readouterr()
