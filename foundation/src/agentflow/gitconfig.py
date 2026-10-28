"""The branch names a project chooses: the branch a task starts from, and the names of its main and development branches.

Settings (``agentflow config set``, a person's command)::

    git.main_branch      the stable branch              (default main)
    git.develop_branch   the integration branch         (default develop)
    git.base.default     the branch every task starts from, whatever its type
    git.base.<type>      the branch tasks of one type start from (feature, bugfix, hotfix, refactor, chore)

The branch a task starts from is, from the strongest: ``agentflow task new --base <branch>``, ``git.base.<type>``,
``git.base.default``, and then the built-in choice: ``git.main_branch`` for a hotfix and ``git.develop_branch`` for the
other types. It is recorded in the task when it is created, so a later change of a setting does not move a running task.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agentflow.constants import DEVELOP_BRANCH, MAIN_BRANCH, ExitCode, TaskType
from agentflow.errors import AgentflowError

ROOT = "git"
MAIN_KEY = "main_branch"
DEVELOP_KEY = "develop_branch"
BASE_KEY = "base"
DEFAULT_KEY = "default"
BASE_KEYS = (DEFAULT_KEY, *(str(task_type) for task_type in TaskType))
KNOWN_KEYS = (
    f"{ROOT}.{MAIN_KEY}",
    f"{ROOT}.{DEVELOP_KEY}",
    *(f"{ROOT}.{BASE_KEY}.{name}" for name in BASE_KEYS),
)
KEY_SEPARATOR = "."

# What a branch name must not hold (git check-ref-format, narrowed to what a person would type by mistake).
_FORBIDDEN = re.compile(r"[\s~^:?*\[\\\x00-\x1f\x7f]|\.\.|@\{|//")


def name_problem(name: object) -> str | None:
    """Why ``name`` cannot be a branch name, or ``None``."""
    if not isinstance(name, str) or not name.strip():
        return "a branch name is text and cannot be empty"
    if name != name.strip():
        return f"'{name}' has spaces around it"
    if _FORBIDDEN.search(name):
        return f"'{name}' is not a valid branch name (no spaces, '..', '//', '~', '^', ':', '?', '*', '[', '\\' or '@{{')"
    if name.startswith(("-", "/")) or name.endswith(("/", ".", ".lock")) or name == "@":
        return f"'{name}' is not a valid branch name"
    return None


def key_problem(key: str) -> str | None:
    """Why a ``git.*`` key is not one of the known settings, or ``None``."""
    if key in KNOWN_KEYS:
        return None
    return f"unknown setting '{key}' (known: {', '.join(KNOWN_KEYS)})"


def check_assignment(key: str, value: object) -> None:
    """Raise when ``agentflow config set <key> <value>`` would give a ``git.*`` setting a bad key or a bad branch name."""
    problem = key_problem(key) or name_problem(value)
    if problem:
        raise AgentflowError(f"{key}: {problem}", ExitCode.SETTINGS_INVALID)


def is_git_key(key: str) -> bool:
    return key == ROOT or key.startswith(ROOT + KEY_SEPARATOR)


@dataclass(frozen=True)
class GitNames:
    main: str = MAIN_BRANCH
    develop: str = DEVELOP_BRANCH
    base_default: str | None = None
    base_by_type: Mapping[str, str] = field(default_factory=dict)

    def base_for(self, task_type: str, explicit: str | None = None) -> str:
        """The branch a task of ``task_type`` starts from."""
        if explicit:
            return explicit
        chosen = self.base_by_type.get(str(task_type)) or self.base_default
        if chosen:
            return chosen
        return self.main if str(task_type) == str(TaskType.HOTFIX) else self.develop

    def protected(self, extra: Iterable[str | None] = ()) -> frozenset[str]:
        """Branches an agent must not commit on or merge into: the built-in names, the configured ones, every configured
        base and ``extra`` (the bases of the tasks that are open)."""
        names = {MAIN_BRANCH, DEVELOP_BRANCH, self.main, self.develop, *self.base_by_type.values(), *extra}
        if self.base_default:
            names.add(self.base_default)
        return frozenset(name for name in names if name)


def names_from(settings: Mapping[str, Any] | None) -> GitNames:
    """The names in the project settings; a value that is not a usable branch name is ignored (``config check`` reports it)."""
    section = (settings or {}).get(ROOT)
    if not isinstance(section, Mapping):
        return GitNames()

    def text(value: object) -> str | None:
        return value if isinstance(value, str) and name_problem(value) is None else None

    bases = section.get(BASE_KEY)
    bases = bases if isinstance(bases, Mapping) else {}
    return GitNames(
        main=text(section.get(MAIN_KEY)) or MAIN_BRANCH,
        develop=text(section.get(DEVELOP_KEY)) or DEVELOP_BRANCH,
        base_default=text(bases.get(DEFAULT_KEY)),
        base_by_type={name: value for name in map(str, TaskType) if (value := text(bases.get(name)))},
    )


def settings_problems(settings: Mapping[str, Any] | None) -> list[str]:
    """Every way the ``git`` section of the project settings is wrong; empty when it is absent."""
    section = (settings or {}).get(ROOT)
    if section is None:
        return []
    if not isinstance(section, Mapping):
        return [f"{ROOT}: must be a mapping of settings"]
    problems: list[str] = []
    for key, value in section.items():
        if key in (MAIN_KEY, DEVELOP_KEY):
            if (problem := name_problem(value)) is not None:
                problems.append(f"{ROOT}.{key}: {problem}")
        elif key == BASE_KEY:
            if not isinstance(value, Mapping):
                problems.append(f"{ROOT}.{BASE_KEY}: must hold {DEFAULT_KEY} or a task type")
                continue
            for name, branch in value.items():
                if name not in BASE_KEYS:
                    problems.append(f"{ROOT}.{BASE_KEY}.{name}: unknown (use {', '.join(BASE_KEYS)})")
                elif (problem := name_problem(branch)) is not None:
                    problems.append(f"{ROOT}.{BASE_KEY}.{name}: {problem}")
        else:
            problems.append(f"{ROOT}.{key}: unknown setting (known: {', '.join(KNOWN_KEYS)})")
    return problems
