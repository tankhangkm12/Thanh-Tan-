"""``CommandRunner`` for the real machine."""

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from agentflow.constants import ENCODING
from agentflow.models import CommandResult

# Return code reported when a program cannot start or runs out of time.
NOT_RUN = -1


class SubprocessRunner:
    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, args: Sequence[str], cwd: Path | None, timeout: int) -> CommandResult:
        try:
            done = subprocess.run(
                list(args),
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding=ENCODING,
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except OSError as exc:
            return CommandResult(NOT_RUN, "", f"cannot run {args[0]}: {exc}")
        except subprocess.TimeoutExpired:
            return CommandResult(NOT_RUN, "", f"{args[0]} did not finish within {timeout} seconds")
        return CommandResult(done.returncode, done.stdout, done.stderr)
