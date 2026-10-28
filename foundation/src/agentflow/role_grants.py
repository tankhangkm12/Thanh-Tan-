"""Tools a project grants a role, and the rules for granting them.

A grant is a person's setting for one project (``agentflow role grant``). A role that only reads may be granted
nothing that could write: the tool must be named exactly, and its name must start with a verb that reads.
"""

import re
from collections.abc import Collection

from agentflow.constants import (
    AGENT_NAME_SEPARATOR,
    MCP_TOOL_PREFIX,
    MCP_TOOL_SEPARATOR,
    MCP_WILDCARD,
    PlanTier,
    ExitCode,
    ReadVerb,
)
from agentflow.errors import AgentflowError

# A server name has no double underscore (that separates it from the tool); a tool name may have one.
_SERVER = r"(?:[A-Za-z0-9.-]|_(?!_))+"
_TOOL = r"[A-Za-z0-9_.-]+"
# mcp__<server>, mcp__<server>__* or mcp__<server>__<tool>
_PATTERN = re.compile(rf"^{MCP_TOOL_PREFIX}(?P<server>{_SERVER})(?:{MCP_TOOL_SEPARATOR}(?P<tool>{_TOOL}|\*))?$")
_LEADING_WORD = re.compile(r"^[a-z]+")


class WorkflowGrantPolicy:
    """``RoleGrantPolicy`` for a workflow: known roles only, MCP tools only, and read-only roles read-only tools only."""

    def __init__(self, known_roles: Collection[str], read_only_roles: Collection[str]) -> None:
        self.known_roles = frozenset(known_roles)
        self.read_only_roles = frozenset(read_only_roles)

    def check(self, role: str, tool: str) -> None:
        if role not in self.known_roles:
            raise _refused(f"unknown role '{role}' (roles: {', '.join(sorted(self.known_roles))})")
        match = _PATTERN.match(tool)
        if match is None:
            raise _refused(
                f"'{tool}' is not an MCP tool name or pattern (mcp__<server>, mcp__<server>__* or mcp__<server>__<tool>)"
            )
        if role in self.read_only_roles:
            self._require_reading(role, tool, match.group("tool"))

    @staticmethod
    def _require_reading(role: str, tool: str, name: str | None) -> None:
        if name is None or name == MCP_WILDCARD:
            raise _refused(f"'{role}' only reads: grant it single tools by their exact name, not '{tool}', which may include tools that write")
        verb = _LEADING_WORD.match(name)
        if verb is None or verb.group(0) not in {item.value for item in ReadVerb}:
            allowed = ", ".join(item.value for item in ReadVerb)
            raise _refused(f"'{role}' only reads, and '{name}' does not look like a read-only tool (its name must start with one of: {allowed})")


def agents_of(role: str, tiered_roles: Collection[str]) -> tuple[str, ...]:
    """The plugin agents that do ``role``: one per tier for a tiered role, otherwise one named after the role."""
    if role in tiered_roles:
        return tuple(f"{role}{AGENT_NAME_SEPARATOR}{tier}" for tier in PlanTier)
    return (role,)


def _refused(message: str) -> AgentflowError:
    return AgentflowError(message, ExitCode.ROLE_GRANT_REFUSED)
