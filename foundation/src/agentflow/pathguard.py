"""Which paths belong to an agentflow workspace, so tools and shell commands of an agent can be kept out of them.

Paths are made absolute, cleaned of ``.``/``..``/repeated separators and symbolic links, and compared by name
without regard to case where the platform's file system ignores it (``os.path.normcase``). A directory only counts as
a workspace when it holds the config file, so an unrelated folder with the same name is left alone.
"""

import os
import re
from collections.abc import Callable
from pathlib import Path

from agentflow.constants import (
    CLAUDE_PROJECT_AGENTS_DIR,
    CONFIG_FILE,
    MARKDOWN_SUFFIX,
    PROJECT_AGENT_PREFIX,
    WORKSPACE_DIR_NAMES,
)

# Both kinds of separator split a path: on Windows a model may write either, and elsewhere a backslash in a
# name is rare enough that treating it as a separator only makes the check stricter.
_SEPARATORS = re.compile(r"[\\/]+")


class WorkspaceWritePolicy:
    """``WriteTargetPolicy`` that protects everything under a ``.ThanhTan/`` directory (or ``.agentflow/``, its name before
    0.8.0) that holds a config file, and
    the ``project-*`` agents that ``agentflow role`` generates in a project that has such a workspace."""

    def __init__(self, normcase: Callable[[str], str] = os.path.normcase) -> None:
        self._fold = normcase

    def is_protected(self, target: Path | str, cwd: Path) -> bool:
        resolved = self._resolve(target, cwd)
        parts = [part for part in _SEPARATORS.split(resolved) if part]
        wanted = {self._fold(name) for name in WORKSPACE_DIR_NAMES}
        for index, part in enumerate(parts):
            if self._fold(part) in wanted and self._is_workspace(resolved, parts[: index + 1]):
                return True
        return self._is_project_agent(resolved, parts)

    def _is_project_agent(self, resolved: str, parts: list[str]) -> bool:
        """``<project>/.claude/agents/project-*.md`` where ``<project>`` has an agentflow workspace."""
        folders = [self._fold(part) for part in CLAUDE_PROJECT_AGENTS_DIR.split("/")]
        if len(parts) <= len(folders) + 1:
            return False
        name = self._fold(parts[-1])
        if not (name.startswith(self._fold(PROJECT_AGENT_PREFIX)) and name.endswith(MARKDOWN_SUFFIX)):
            return False
        if [self._fold(part) for part in parts[-1 - len(folders) : -1]] != folders:
            return False
        return any(self._is_workspace(resolved, [*parts[: -1 - len(folders)], name]) for name in WORKSPACE_DIR_NAMES)

    @staticmethod
    def _resolve(target: Path | str, cwd: Path) -> str:
        text = os.fspath(target)
        if not os.path.isabs(text):
            text = os.path.join(cwd, text)
        return os.path.realpath(text)

    @staticmethod
    def _is_workspace(resolved: str, parts: list[str]) -> bool:
        # Rebuild the directory from the resolved string, keeping its drive or leading separator.
        head = os.path.splitdrive(resolved)[0]
        prefix = head + (os.sep if resolved[len(head) :].startswith(("/", "\\")) else "")
        return (Path(prefix, *parts) / CONFIG_FILE).is_file()
