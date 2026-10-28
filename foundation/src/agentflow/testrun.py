"""The one runner of project commands that agentflow itself runs: the gates ``test-spec-valid`` (a test must fail first)
and ``tests-pass`` (and then pass). What an agent writes about a run is never taken for the run.

The command goes to the platform shell from the project root. A run that outlives its time is killed with every process
it started. Only the tail of the output is kept.
"""

import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from agentflow.constants import ENCODING

DEFAULT_TIMEOUT_MINUTES = 15
OUTPUT_LIMIT = 4000
NOT_EXECUTABLE = 126
NOT_FOUND = 127
_SECONDS_PER_MINUTE = 60
_NOT_FOUND_TEXT = re.compile(r"is not recognized as an internal or external command|command not found|not recognized as the name of a cmdlet", re.I)
_KILL_GRACE_SECONDS = 5
# Variables that change what pytest runs: `PYTEST_ADDOPTS="-k nothing" agentflow task advance ...` must not reach the tests.
SCRUBBED_ENVIRONMENT = frozenset({"PYTEST_ADDOPTS", "PYTEST_PLUGINS"})


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    output: str
    timed_out: bool
    duration_seconds: float

    @property
    def not_found(self) -> bool:
        """The shell could not start the program (a typo is not a failing test)."""
        return not self.timed_out and (self.exit_code in {NOT_EXECUTABLE, NOT_FOUND} or bool(_NOT_FOUND_TEXT.search(self.output)))


def tail(text: str, limit: int = OUTPUT_LIMIT) -> str:
    return text if len(text) <= limit else text[-limit:]


def timeout_seconds(minutes: object) -> float:
    """Seconds for a ``test_timeout_minutes`` setting (``None``: the default); a value that makes no sense is an error."""
    if minutes is None:
        return DEFAULT_TIMEOUT_MINUTES * _SECONDS_PER_MINUTE
    try:
        value = float(str(minutes).strip())
    except ValueError as exc:
        raise ValueError(f"test_timeout_minutes is '{minutes}', which is not a number of minutes") from exc
    if not value > 0:
        raise ValueError(f"test_timeout_minutes is '{minutes}': it must be more than 0")
    return value * _SECONDS_PER_MINUTE


def run_command(command: str, cwd: str | Path, timeout: float) -> RunResult:
    """Run ``command`` in ``cwd``; ``timeout`` is in seconds."""
    started = time.monotonic()
    environment = {name: value for name, value in os.environ.items() if name.upper() not in SCRUBBED_ENVIRONMENT}
    options: dict = {"cwd": str(cwd), "shell": True, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "env": environment}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(command, **options)  # noqa: S602 - the command is the project's own, from its settings or reports
    try:
        raw, _ = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        try:
            raw, _ = process.communicate(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            raw = b""
        timed_out = True
    output = (raw or b"").decode(ENCODING, errors="replace")
    return RunResult(process.returncode if process.returncode is not None else 1, tail(output), timed_out, round(time.monotonic() - started, 3))


def _kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, check=False)  # noqa: S603, S607
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
