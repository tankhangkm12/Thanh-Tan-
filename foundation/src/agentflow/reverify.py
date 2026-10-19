"""The red proof, made again on the old code, for a test that a person changed.

A test is worth something only if it fails before the feature exists. When an approved test is amended, agentflow runs the
commands of the plan items that use it in a throwaway checkout of the commit where they were first run red (the ``head`` of
``verify-red.json``), with the new contents of the files copied in. A command that now exits 0 there no longer proves
anything. The checkout is removed afterwards; the working tree and the branch are not touched.
"""

import shutil
import tempfile
from pathlib import Path

from agentflow import testrun
from agentflow.git import run_git

NOT_RUN = "not-run"
GREEN, RED, TIMEOUT, NOT_FOUND = "green", "red", "timeout", "not-found"


def _status(result: testrun.RunResult) -> str:
    if result.timed_out:
        return TIMEOUT
    if result.not_found:
        return NOT_FOUND
    return GREEN if result.exit_code == 0 else RED


def old_code_results(
    root: Path,
    head: str,
    overlay: dict[str, bytes | None],
    jobs: list[tuple[str, str, list[str]]],
    timeout: float,
    at: str,
) -> dict[str, dict]:
    """``jobs`` are (plan item, command, files it uses). ``overlay`` maps a path to its new bytes (``None``: removed).
    Each distinct command runs once. A checkout that cannot be made gives every job the status ``not-run``."""
    results: dict[str, dict] = {}
    if not jobs:
        return results
    folder = Path(tempfile.mkdtemp(prefix="agentflow-red-"))
    made = False
    try:
        added = run_git(root, "worktree", "add", "--detach", str(folder), head)
        made = added.returncode == 0
        if not made:
            reason = (added.stderr or added.stdout).strip()
            return {code: {"command": command, "exit_code": None, "status": NOT_RUN, "files": files, "at": at, "reason": reason} for code, command, files in jobs}
        for relative, data in overlay.items():
            target = folder / relative
            if data is None:
                target.unlink(missing_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        done: dict[str, testrun.RunResult] = {}
        for code, command, files in jobs:
            if command not in done:
                done[command] = testrun.run_command(command, folder, timeout)
            run = done[command]
            results[code] = {"command": command, "exit_code": run.exit_code, "status": _status(run), "files": files, "at": at}
        return results
    finally:
        if made:
            run_git(root, "worktree", "remove", "--force", str(folder))
        shutil.rmtree(folder, ignore_errors=True)
        run_git(root, "worktree", "prune")
