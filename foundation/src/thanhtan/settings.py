"""Project settings: the ``settings`` section of ``.ThanhTan/config.yaml``, which extensions read."""

import copy
from collections.abc import Mapping, Sequence
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.extension import Extension

KEY_SEPARATOR = "."
STRUCTURED_TYPES = frozenset({"integer", "number", "boolean", "array"})


def get_value(settings: Mapping[str, Any], dotted: str) -> Any:
    node: Any = settings
    for part in dotted.split(KEY_SEPARATOR):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def set_value(settings: Mapping[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    """A copy of ``settings`` with ``dotted`` set; keys on the way become mappings."""
    parts = dotted.split(KEY_SEPARATOR)
    if not all(parts):
        raise ThanhTanError(f"'{dotted}' is not a setting key (use a.b.c)", ExitCode.INVALID_INPUT)
    updated = copy.deepcopy(dict(settings))
    node = updated
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value
    return updated


def declared_type(extensions: Sequence[Extension], dotted: str) -> str | None:
    """The JSON Schema type an extension declares for a setting, if any extension does."""
    root, _, rest = dotted.partition(KEY_SEPARATOR)
    for extension in extensions:
        if extension.settings_key != root or extension.settings_schema is None:
            continue
        node: Any = extension.settings_schema
        for part in rest.split(KEY_SEPARATOR):
            node = (node.get("properties") or {}).get(part) if isinstance(node, Mapping) else None
        if isinstance(node, Mapping) and isinstance(node.get("type"), str):
            return node["type"]
    return None


def coerce(extensions: Sequence[Extension], dotted: str, raw: str) -> Any:
    """Text stays text, unless an extension declares the setting as a number, boolean or list."""
    if declared_type(extensions, dotted) in STRUCTURED_TYPES:
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ThanhTanError(f"cannot read '{raw}' as a value for {dotted}: {exc}", ExitCode.INVALID_INPUT) from exc
    return raw


def settings_problems(extensions: Sequence[Extension], settings: Mapping[str, Any]) -> list[str]:
    """Every way the settings fall short of what the registered extensions declare."""
    problems: list[str] = []
    for extension in extensions:
        if extension.settings_key is None or extension.settings_schema is None:
            continue
        section = settings.get(extension.settings_key, {})
        validator = Draft202012Validator(dict(extension.settings_schema))
        for error in sorted(validator.iter_errors(section), key=lambda e: list(e.absolute_path)):
            path = KEY_SEPARATOR.join([extension.settings_key, *(str(p) for p in error.absolute_path)])
            problems.append(f"{extension.name}: {path or extension.settings_key}: {error.message}")
    return problems
