"""Which paths the hook keeps agents away from because a task has approved tests.

``LockPolicy`` answers for a path: is it a locked file (not open to a person's window), or a test configuration file the
lock does not hold? It reads the locks of the tasks that are still going (``lockfiles.active_locks``), so a project with no
lock costs one directory listing. ``GuardedPaths`` puts it next to the policy for ``.agentflow/`` that the guard always had.
"""

import os
from pathlib import Path
from typing import Any

from agentflow import lockfiles
from agentflow.constants import CONFIG_FILE, WORKSPACE_DIR
from agentflow.pathguard import WorkspaceWritePolicy


def _workspace_of(resolved: str) -> Path | None:
    """The ``.agentflow`` directory of the project the path is in (a directory with a config file), if any."""
    folder = Path(resolved).parent
    for candidate in (folder, *folder.parents):
        workspace = candidate / WORKSPACE_DIR
        if (workspace / CONFIG_FILE).is_file():
            return workspace
    return None


class LockPolicy:
    """Whether a path is closed because of a lock."""

    def locked(self, target: Path | str, cwd: Path) -> bool:
        text = os.fspath(target)
        if not text:
            return False
        if os.sep == "/":
            # A model may write a Windows path (``.\tests\x.py``) on any platform: read a backslash as a separator,
            # as ``WorkspaceWritePolicy`` does, so the lock is not missed.
            text = text.replace("\\", "/")
        if not os.path.isabs(text):
            text = os.path.join(cwd, text)
        resolved = os.path.realpath(text)
        workspace = _workspace_of(resolved)
        if workspace is None:
            return False
        locks = lockfiles.active_locks(workspace)
        if not locks:
            return False
        relative = lockfiles.posix(os.path.relpath(resolved, workspace.parent))
        if relative.startswith("../") or relative == "..":
            return False
        return any(self._closes(lock, relative) for lock in locks)

    @staticmethod
    def _closes(lock: dict[str, Any], relative: str) -> bool:
        if lockfiles.window_for(lock, relative) is not None:
            return False
        held = lockfiles.entry_for(lock, relative)
        if held is not None:
            return held[1].get("scope") != lockfiles.SCOPE_PART
        return lockfiles.is_dedicated(relative)


class GuardedPaths:
    """``WriteTargetPolicy``: everything the workspace policy protects, and what the locks close."""

    def __init__(self, workspace: WorkspaceWritePolicy | None = None, locks: LockPolicy | None = None) -> None:
        self.workspace = workspace or WorkspaceWritePolicy()
        self.locks = locks or LockPolicy()

    def is_protected(self, target: Path | str, cwd: Path) -> bool:
        return self.workspace.is_protected(target, cwd) or self.locks.locked(target, cwd)

    def locked(self, target: Path | str, cwd: Path) -> bool:
        """Closed by a lock and not by the workspace policy (the reasons differ)."""
        return not self.workspace.is_protected(target, cwd) and self.locks.locked(target, cwd)
