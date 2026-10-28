"""What the smoke tests share: running commands, checking, and a session in a throw-away repository.

Kept apart from smoke.py so that a script run as ``__main__`` and the helpers it imports use one ``Failure`` class.
"""

import json
import os
import re
import secrets
import stat
import string
import subprocess
import sys
from pathlib import Path

ENCODING = "utf-8"
FOUNDATION = Path(__file__).resolve().parent.parent / "foundation"


def _repo_thanhtan() -> str:
    """The `thanhtan` built from foundation/ of this repository, never the one installed on PATH.

    A copy installed earlier can be older than the code under test (it did not know a gate and failed every smoke), so
    the smoke tests sync foundation/'s own environment and use its script, and put it first on PATH for the tools
    that call `thanhtan` themselves.
    """
    scripts = FOUNDATION / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    exe = scripts / ("thanhtan.exe" if sys.platform == "win32" else "thanhtan")
    done = subprocess.run(
        ["uv", "sync", "--quiet", "--project", str(FOUNDATION)], capture_output=True, text=True, encoding=ENCODING, check=False
    )
    if done.returncode != 0 or not exe.is_file():
        raise SystemExit(f"cannot build thanhtan from {FOUNDATION}: {done.stderr or 'script missing'}")
    os.environ["PATH"] = str(scripts) + os.pathsep + os.environ.get("PATH", "")
    return str(exe)


THANHTAN = _repo_thanhtan()
STEP_TIMEOUT = 900
# A made-up GitHub-style token; the random part is generated at run time.
FAKE_TOKEN_PREFIX = "ghp" + "_"
FAKE_TOKEN_LENGTH = 36


class Failure(Exception):
    pass


def run(args: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, input=stdin, capture_output=True, text=True, encoding=ENCODING, timeout=STEP_TIMEOUT, check=False
    )


def expect(condition: bool, what: str, detail: str = "") -> None:
    print(f"{'ok  ' if condition else 'FAIL'} {what}")
    if not condition:
        raise Failure(f"{what}\n{detail}")


class Session:
    def __init__(self, repo: Path) -> None:
        self.repo = repo

    def git(self, *args: str) -> str:
        done = run(["git", *args], self.repo)
        if done.returncode != 0:
            raise Failure(f"git {' '.join(args)} failed: {done.stderr}")
        return done.stdout.strip()

    def approve(self, *extra: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        """What a person does: tick the checklist of the step that waits (when thanhtan wrote one), then approve."""
        state = json.loads((self.repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))
        task = next((t for t in state["tasks"] if t["id"] == state["active_task_id"]), None)
        if task is not None and task["step_status"] == "awaiting_approval":
            path = self.repo / ".ThanhTan" / "tasks" / task["id"] / f"approve-{task['current_step']}.md"
            if path.is_file():
                lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
                ticked = [line.replace("- [ ]", "- [x]", 1) if re.match(r"- \[ \] (?!\(tùy chọn\))", line) else line for line in lines]
                path.write_text("".join(ticked), encoding="utf-8", newline="")
        return self.af("task", "approve", *extra, ok=ok)

    def test_first(self) -> None:
        """What the tester does at the test-spec step: a check that fails until a planned file exists, committed, reported,
        run again by thanhtan (it must fail), then approved by a person. Sets the project's test command on the way."""
        state = json.loads((self.repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))
        task = next(t for t in state["tasks"] if t["id"] == state["active_task_id"])
        plan = (self.repo / ".ThanhTan" / "tasks" / task["id"] / "reports" / "plan.md").read_text(encoding="utf-8")
        codes = re.findall(r"^### (C\d+)\b", plan, flags=re.M)
        files = re.findall(r"^- files:\s*(.+)$", plan, flags=re.M)
        planned = [name.strip() for line in files for name in line.split(",") if name.strip()]
        planned = [name for name in planned if not (self.repo / name).exists()] or planned  # red needs a file that is not there yet
        script = self.repo / "tests" / "check_planned.py"
        script.parent.mkdir(exist_ok=True)
        script.write_text(
            "import pathlib, sys\n"
            f"planned = {planned!r}\n"
            "if any(pathlib.Path(name).exists() for name in planned):\n"
            "    print('planned files exist')\n"
            "    sys.exit(0)\n"
            "print('FAILED check_planned: none of the planned files exists yet')\n"
            "sys.exit(1)\n",
            encoding="utf-8",
        )
        self.git("add", "tests/check_planned.py")
        self.git("commit", "-q", "-m", f"{task['id']}: tests first")
        command = f'"{sys.executable}" tests/check_planned.py'
        blocks = "".join(
            f"### {code} - tests for {code}\n- tests: tests/check_planned.py::check\n- command: `{command}`\n- red: fail\n"
            "- reason: the planned files do not exist yet\n- output: |\n    FAILED check_planned: none of the planned files exists yet\n\n"
            for code in codes
        )
        self.af("report", "--step", "test-spec", stdin="# Test-spec\n\n" + blocks)
        self.af("tests", "verify-red")
        self.af("task", "advance", "--result", "pass")
        self.approve()
        self.af("config", "set", "test_command", command)

    def af(self, *args: str, stdin: str | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
        done = run([THANHTAN, *args], self.repo, stdin)
        expect((done.returncode == 0) is ok, f"thanhtan {' '.join(args)} -> exit {done.returncode}", done.stdout + done.stderr)
        return done


def fake_token_body() -> str:
    """Random characters, so no token-looking string is ever stored in this repository."""
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(FAKE_TOKEN_LENGTH))


def _make_writable_and_retry(function, path, _excinfo) -> None:
    # git object files are read-only, which Windows refuses to delete.
    os.chmod(path, stat.S_IWRITE)
    function(path)
