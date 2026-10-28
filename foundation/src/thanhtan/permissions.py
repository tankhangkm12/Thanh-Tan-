"""``thanhtan permissions install``: put the Claude Code permission rules of README Bước 4 into a settings file.

The rules ship with the package (``data/claude-permissions.json``; a test keeps README identical to it). Installing merges
them into ``.claude/settings.json`` of the project (or ``~/.claude/settings.json`` with ``--user``): the person's own rules
stay, missing rules are added, and rules of the name before 1.0.0 (``agentflow``, ``.agentflow/``,
``mcp__plugin_dev-core_agentflow__*``) are removed, as is any ``allow`` rule that would let an agent approve or cancel.
``--check`` changes nothing and says what is missing.
"""

import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from thanhtan.constants import ENCODING, PACKAGE_NAME, ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic

DATA_DIR = "data"
RULES_FILE = "claude-permissions.json"
SETTINGS_DIR = ".claude"
SETTINGS_FILE = "settings.json"
PERMISSIONS = "permissions"
LISTS = ("allow", "ask", "deny")
BYPASS_KEY = "disableBypassPermissionsMode"
# Rules written for the program before it was renamed: they no longer match anything useful.
_STALE = re.compile(r"agentflow", re.IGNORECASE)
# An allow rule must never cover what only a person may approve.
_PERSON_ONLY = re.compile(r"^(Bash|PowerShell)\((thanhtan|agentflow) task (approve|cancel)\b")


@dataclass
class Merge:
    settings: dict[str, Any]
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)


def shipped_rules() -> dict[str, Any]:
    text = files(PACKAGE_NAME).joinpath(DATA_DIR, RULES_FILE).read_text(encoding=ENCODING)
    return json.loads(text)[PERMISSIONS]


def settings_path(project_root: Path, user_home: Path | None = None) -> Path:
    return (user_home if user_home is not None else project_root) / SETTINGS_DIR / SETTINGS_FILE


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding=ENCODING))
    except ValueError as exc:
        raise ThanhTanError(f"{path} is not valid JSON ({exc}); fix it by hand first", ExitCode.INVALID_INPUT) from exc
    if not isinstance(data, dict):
        raise ThanhTanError(f"{path} must hold a JSON object", ExitCode.INVALID_INPUT)
    return data


def merge(current: dict[str, Any], rules: dict[str, Any]) -> Merge:
    settings = json.loads(json.dumps(current))  # a copy, so --check never changes what it was given
    permissions = settings.setdefault(PERMISSIONS, {})
    if not isinstance(permissions, dict):
        raise ThanhTanError(f"'{PERMISSIONS}' in the settings must be an object", ExitCode.INVALID_INPUT)
    result = Merge(settings)
    for name in LISTS:
        existing = permissions.get(name, [])
        if not isinstance(existing, list):
            raise ThanhTanError(f"'{PERMISSIONS}.{name}' in the settings must be a list", ExitCode.INVALID_INPUT)
        kept = []
        for rule in existing:
            stale = isinstance(rule, str) and (_STALE.search(rule) or (name == "allow" and _PERSON_ONLY.match(rule)))
            (result.removed if stale else kept).append(rule)
        for rule in rules.get(name, []):
            if rule not in kept:
                kept.append(rule)
                result.added.append(rule)
        permissions[name] = kept
    wanted = rules.get(BYPASS_KEY)
    if wanted is not None:
        if BYPASS_KEY not in permissions:
            permissions[BYPASS_KEY] = wanted
            result.added.append(f"{BYPASS_KEY}: {wanted}")
        elif permissions[BYPASS_KEY] != wanted:
            result.notes.append(f"{BYPASS_KEY} is '{permissions[BYPASS_KEY]}' (README sets '{wanted}'); left as you set it")
    return result


def install(project_root: Path, *, check: bool = False, user_home: Path | None = None) -> tuple[Path, Merge]:
    path = settings_path(project_root, user_home)
    result = merge(_read(path), shipped_rules())
    if result.changed and not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, json.dumps(result.settings, indent=2, ensure_ascii=False) + "\n")
    return path, result
