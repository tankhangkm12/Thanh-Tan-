"""Finding the project from a process that is not necessarily running inside it.

Claude Code starts a plugin's MCP server in the project. Antigravity starts it in the plugin's own directory and
offers no variable or message that names the project. So the server looks, in this order, at: its working
directory, ``AGENTFLOW_PROJECT_DIR``, ``PWD`` (the shell that launched the CLI), and finally the project that
the last Antigravity hook call remembered in the user's agentflow folder (``~/.ThanhTan/active-project.txt``).
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from agentflow.constants import (
    ACTIVE_PROJECT_FILE,
    ENCODING,
    LEGACY_USER_DIR_NAME,
    PROJECT_DIR_ENV,
    SHELL_PWD_ENV,
    USER_DIR_ENV,
    USER_DIR_NAME,
    ExitCode,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.workspace import WorkspacePaths, find_workspace


def user_dir(environ: Mapping[str, str] | None = None) -> Path:
    """The user's agentflow folder (``~/.ThanhTan``, or ``AGENTFLOW_HOME``). A ``~/.agentflow`` from before 0.8.0 is moved
    to the new name the first time; when it cannot be moved (a file is open), it is used where it is."""
    env = os.environ if environ is None else environ
    if env.get(USER_DIR_ENV):
        return Path(env[USER_DIR_ENV])
    home = Path.home()
    folder, legacy = home / USER_DIR_NAME, home / LEGACY_USER_DIR_NAME
    if not folder.exists() and legacy.is_dir():
        try:
            legacy.rename(folder)
        except OSError:
            return legacy
    return folder


def remember_project(root: Path, environ: Mapping[str, str] | None = None) -> None:
    """Note ``root`` as the project in use; nothing is written when it is already noted."""
    pointer = user_dir(environ) / ACTIVE_PROJECT_FILE
    text = f"{root}\n"
    try:
        if pointer.is_file() and pointer.read_text(encoding=ENCODING) == text:
            return
        pointer.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(pointer, text)
    except OSError:
        pass  # a hook must never fail the agent over a convenience


class EnvironmentProjectLocator:
    """``ProjectLocator`` that tries the places listed in the module docstring."""

    def __init__(self, cwd: Callable[[], Path] = Path.cwd, environ: Mapping[str, str] | None = None) -> None:
        self._cwd = cwd
        self._environ = os.environ if environ is None else environ

    def _candidates(self) -> list[Path]:
        found = [self._cwd()]
        for name in (PROJECT_DIR_ENV, SHELL_PWD_ENV):
            if self._environ.get(name):
                found.append(Path(self._environ[name]))
        pointer = user_dir(self._environ) / ACTIVE_PROJECT_FILE
        try:
            if pointer.is_file():
                found.append(Path(pointer.read_text(encoding=ENCODING).strip()))
        except OSError:
            pass
        return found

    def find(self) -> WorkspacePaths:
        tried: list[str] = []
        for candidate in self._candidates():
            tried.append(str(candidate))
            if not candidate.is_dir():
                continue
            try:
                return find_workspace(candidate)
            except AgentflowError:
                continue
        raise AgentflowError(
            f"no agentflow workspace found (looked in: {', '.join(tried)}); run `agentflow init --workflow <file>` "
            f"in the project, or set {PROJECT_DIR_ENV}",
            ExitCode.NO_WORKSPACE,
        )
