"""Which agent takes a plan item: the role's own agent, or the variant for the item's tier."""

from collections.abc import Callable, Collection, Sequence

from agentflow.constants import AGENT_NAME_SEPARATOR
from agentflow.interfaces import AgentNames
from agentflow.plan import PlanItem


class WorkflowAgentNames:
    """``AgentNames`` for a workflow: roles it calls tiered have ``<role>-<tier>`` agents, the others just ``<role>``."""

    def __init__(self, tiered_roles: Collection[str]) -> None:
        self.tiered_roles = frozenset(tiered_roles)

    def agent_for(self, role: str, tier: str) -> str:
        return f"{role}{AGENT_NAME_SEPARATOR}{tier}" if role in self.tiered_roles else role


class ProjectAgentNames:
    """``AgentNames`` that prefers the project's own copy of an agent (made by ``agentflow role grant``) over the plugin's."""

    def __init__(self, base: AgentNames, project_agent_for: Callable[[str, str], str | None]) -> None:
        self.base = base
        self.project_agent_for = project_agent_for

    def agent_for(self, role: str, tier: str) -> str:
        plugin_agent = self.base.agent_for(role, tier)
        return self.project_agent_for(role, plugin_agent) or plugin_agent


def assignment_lines(items: Sequence[PlanItem], names: AgentNames) -> list[str]:
    """One line per item: ``C1 <role> <tier> <agent>``."""
    return [f"{item.code} {item.role} {item.effective_tier} {names.agent_for(item.role or '', item.effective_tier)}" for item in items]
