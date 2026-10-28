"""Extensions: what a child plugin adds to a family, read from its ``extension.yaml``.

The contract is ``schemas/extension.schema.json``. Nothing here knows what any extension is for.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentflow.constants import (
    ENCODING,
    EXTENSION_SCHEMA_FILE,
    FileScope,
    GateKind,
    NetworkMode,
    ResultKind,
)
from agentflow.constants import ExitCode
from agentflow.errors import AgentflowError
from agentflow.placeholders import EXTENSION_PLACEHOLDERS, Placeholder, placeholders_in
from agentflow.scan_types import Condition, FileSelection, ResultSpec, ScanToolSpec
from agentflow.validation import schema_errors

LATEST_TAG = "latest"
# Tools like linters exit 1 when they report something; the output is still the result.
DEFAULT_OK_EXIT_CODES = (0, 1)
_INDENT = "\n  - "


@dataclass(frozen=True)
class RoleDecl:
    id: str
    description: str = ""


@dataclass(frozen=True)
class PathRule:
    id: str
    paths: tuple[str, ...]
    roles: tuple[str, ...]


@dataclass(frozen=True)
class PlanRuleDecl:
    id: str
    when_paths: tuple[str, ...]
    done_when_contains: tuple[str, ...]


@dataclass(frozen=True)
class Extension:
    name: str
    family: str
    description: str = ""
    settings_key: str | None = None
    settings_schema: Mapping[str, Any] | None = None
    roles: tuple[RoleDecl, ...] = ()
    path_rules: tuple[PathRule, ...] = ()
    plan_rules: tuple[PlanRuleDecl, ...] = ()
    scan_tools: tuple[ScanToolSpec, ...] = ()
    gates: tuple[tuple[str, GateKind], ...] = ()

    @property
    def role_ids(self) -> tuple[str, ...]:
        return tuple(role.id for role in self.roles)


def load_extension_file(path: Path) -> Extension:
    if not path.is_file():
        raise AgentflowError(f"extension file not found: {path}", ExitCode.EXTENSION_INVALID)
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AgentflowError(f"{path}: cannot read extension: {exc}", ExitCode.EXTENSION_INVALID) from exc
    return parse_extension(data, origin=str(path))


def parse_extension(data: Any, origin: str) -> Extension:
    problems = schema_errors(data, EXTENSION_SCHEMA_FILE)
    extension = None
    if not problems:
        extension = _from_dict(data)
        problems = reference_problems(extension)
    if problems:
        raise AgentflowError(f"{origin}: invalid extension:{_INDENT}{_INDENT.join(problems)}", ExitCode.EXTENSION_INVALID)
    assert extension is not None
    return extension


def _from_dict(data: Mapping[str, Any]) -> Extension:
    settings = data.get("settings")
    return Extension(
        name=data["name"],
        family=data["family"],
        description=data.get("description", ""),
        settings_key=settings["key"] if settings else None,
        settings_schema=settings["schema"] if settings else None,
        roles=tuple(RoleDecl(r["id"], r.get("description", "")) for r in data.get("roles", ())),
        path_rules=tuple(PathRule(r["id"], tuple(r["paths"]), tuple(r["roles"])) for r in data.get("path_rules", ())),
        plan_rules=tuple(
            PlanRuleDecl(r["id"], tuple(r["when_paths"]), tuple(r["done_when_contains"])) for r in data.get("plan_rules", ())
        ),
        scan_tools=tuple(_tool_from_dict(t) for t in data.get("scan_tools", ())),
        gates=tuple((g["step"], GateKind(g["kind"])) for g in data.get("gates", ())),
    )


def _tool_from_dict(data: Mapping[str, Any]) -> ScanToolSpec:
    result = data["result"]
    kind = ResultKind(result["kind"])
    when = data.get("when")
    files = data.get("files")
    condition = None
    if when:
        equals = when.get("config_equals")
        condition = Condition(
            config_equals=(equals["key"], equals["value"]) if equals else None,
            config_present=tuple(when.get("config_present", ())),
        )
    fail_codes = tuple(result.get("fail_exit_codes", ()))
    return ScanToolSpec(
        id=data["id"],
        step=data["step"],
        image=data["image"],
        args=tuple(data["args"]),
        network=NetworkMode(data.get("network", NetworkMode.NONE)),
        files=FileSelection(FileScope(files.get("scope", FileScope.CHANGED)), tuple(files.get("globs", ()))) if files else None,
        when=condition,
        skip_note=data.get("skip_note", ""),
        result=ResultSpec(
            kind=kind,
            items=result.get("items", ""),
            rule_field=result.get("rule_field", ""),
            severity_field=result.get("severity_field"),
            location_field=result.get("location_field"),
            message_field=result.get("message_field"),
            blocking_severities=tuple(result.get("blocking_severities", ())),
            require_field=result.get("require_field"),
            fail_exit_codes=fail_codes,
            ok_exit_codes=(0, *fail_codes) if kind is ResultKind.EXIT_CODE else DEFAULT_OK_EXIT_CODES,
        ),
    )


# ------------------------------------------------------------ cross checks


def reference_problems(extension: Extension) -> list[str]:
    """Rules JSON Schema cannot express: unique ids, pinned images, valid placeholders, own settings only."""
    problems: list[str] = []
    problems += _duplicates("role", [r.id for r in extension.roles])
    problems += _duplicates("path rule", [r.id for r in extension.path_rules])
    problems += _duplicates("plan rule", [r.id for r in extension.plan_rules])
    problems += _duplicates("scan tool", [t.id for t in extension.scan_tools])
    known_roles = set(extension.role_ids)
    for rule in extension.path_rules:
        problems += [f"path rule '{rule.id}': role '{r}' is not declared by this extension" for r in rule.roles if r not in known_roles]
    for tool in extension.scan_tools:
        if tool.when:
            keys = [*tool.when.config_present, *([tool.when.config_equals[0]] if tool.when.config_equals else [])]
            problems += [
                f"scan tool '{tool.id}': condition key '{key}' must be a setting under this extension's own key '{extension.settings_key}'"
                for key in keys
                if not _own_key(key, extension.settings_key)
            ]
        tag = tool.image.rsplit(":", 1)[1]
        if tag == LATEST_TAG:
            problems.append(f"scan tool '{tool.id}': image '{tool.image}' must be pinned to a version, not '{LATEST_TAG}'")
    for where, text in _templates(extension):
        problems += _placeholder_problems(where, text, extension.settings_key)
    return problems


def _duplicates(what: str, ids: list[str]) -> list[str]:
    return [f"duplicate {what} id '{i}'" for i in sorted({i for i in ids if ids.count(i) > 1})]


def _templates(extension: Extension) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for rule in extension.path_rules:
        found += [(f"path rule '{rule.id}'", p) for p in rule.paths]
    for rule in extension.plan_rules:
        found += [(f"plan rule '{rule.id}'", t) for t in (*rule.when_paths, *rule.done_when_contains)]
    for tool in extension.scan_tools:
        where = f"scan tool '{tool.id}'"
        found += [(where, a) for a in tool.args]
        if tool.files:
            found += [(where, g) for g in tool.files.globs]
    return found


def _placeholder_problems(where: str, text: str, settings_key: str | None) -> list[str]:
    problems = []
    for kind, name in placeholders_in(text):
        if kind not in EXTENSION_PLACEHOLDERS:
            problems.append(f"{where}: placeholder '${{{kind}}}' is not allowed in extensions")
        elif kind == Placeholder.FILES and text != f"${{{Placeholder.FILES}}}":
            problems.append(f"{where}: '${{files}}' must be a whole argument")
        elif kind in (Placeholder.CONFIG, Placeholder.HOST_URL) and not _own_key(name or "", settings_key):
            problems.append(f"{where}: '{name}' must be a setting under this extension's own key '{settings_key}'")
    return problems


def _own_key(key: str, settings_key: str | None) -> bool:
    return settings_key is not None and key.startswith(f"{settings_key}.")
