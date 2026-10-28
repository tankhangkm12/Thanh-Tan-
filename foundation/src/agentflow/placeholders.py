"""``${...}`` placeholders in extension rules and scan tool arguments.

Forms: ``${config:area.folder}`` (a project setting), ``${host_url:area.url}`` (a setting
holding a URL, with ``localhost`` rewritten so a container can reach the host), ``${files}`` (the task's files,
one argument each) and ``${var:name}`` (a value the scan run provides, used by built-in tools).
"""

import re
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from agentflow.constants import HOST_GATEWAY_NAME, ExitCode
from agentflow.errors import AgentflowError

PLACEHOLDER = re.compile(r"\$\{([a-z_]+)(?::([^}]*))?\}")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})

Lookup = Callable[[str], Any]


class Placeholder(StrEnum):
    CONFIG = "config"
    HOST_URL = "host_url"
    FILES = "files"
    VAR = "var"


# What extension files may use; `var` is for built-in tools only.
EXTENSION_PLACEHOLDERS = frozenset({Placeholder.CONFIG, Placeholder.HOST_URL, Placeholder.FILES})


def placeholders_in(text: str) -> list[tuple[str, str | None]]:
    return [(match.group(1), match.group(2)) for match in PLACEHOLDER.finditer(text)]


def host_url(url: str) -> str:
    """The URL with a local host name replaced by the name containers use for the host."""
    parts = urlsplit(url)
    if (parts.hostname or "") not in LOCAL_HOSTS:
        return url
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit(parts._replace(netloc=f"{HOST_GATEWAY_NAME}{port}"))


def setting(lookup: Lookup, key: str) -> str:
    value = lookup(key)
    if value is None or value == "":
        raise AgentflowError(
            f"the project setting '{key}' is not set (a person sets it with `agentflow config set {key} <value>`)",
            ExitCode.SETTINGS_INVALID,
        )
    return str(value)


def expand_text(text: str, lookup: Lookup, variables: dict[str, str] | None = None) -> str:
    """Replace every placeholder except ``${files}`` (which is only valid as a whole argument)."""

    def replace(match: re.Match[str]) -> str:
        kind, name = match.group(1), match.group(2) or ""
        match kind:
            case Placeholder.CONFIG:
                return setting(lookup, name)
            case Placeholder.HOST_URL:
                return host_url(setting(lookup, name))
            case Placeholder.VAR:
                if variables is None or name not in variables:
                    raise AgentflowError(f"unknown scan variable '{name}'", ExitCode.EXTENSION_INVALID)
                return variables[name]
        raise AgentflowError(f"placeholder '{match.group(0)}' cannot be used here", ExitCode.EXTENSION_INVALID)

    return PLACEHOLDER.sub(replace, text)


def expand_args(
    args: Sequence[str], lookup: Lookup, files: Sequence[str], variables: dict[str, str] | None = None
) -> list[str]:
    """Expand each argument; an argument that is exactly ``${files}`` becomes one argument per file."""
    expanded: list[str] = []
    for arg in args:
        if arg == f"${{{Placeholder.FILES}}}":
            expanded.extend(files)
        else:
            expanded.append(expand_text(arg, lookup, variables))
    return expanded
