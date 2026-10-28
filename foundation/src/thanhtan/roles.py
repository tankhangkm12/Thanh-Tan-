"""``thanhtan role``: tools a person grants a role for this project, and the Claude Code agents that carry them.

Grants live in ``.ThanhTan/config.yaml``. For Claude Code each grant becomes a project-level copy of the role's plugin
agents (see ``overlay.py``). Antigravity needs none: its agents already see every MCP server that is installed, so a
grant is only recorded there, to keep the two CLIs' settings the same.
"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from thanhtan.constants import (
    CLAUDE_PROJECT_AGENTS_DIR,
    PROJECT_AGENT_EXCLUDE_ENTRY,
    ExitCode,
)
from thanhtan.errors import ThanhTanError
from thanhtan.interfaces import AgentOverlay, RoleGrantPolicy
from thanhtan.models import Workflow
from thanhtan.overlay import CURRENT, ClaudeAgentOverlay, project_agent_file, project_agent_name
from thanhtan.projectcontext import load_project_context
from thanhtan.role_grants import WorkflowGrantPolicy, agents_of
from thanhtan.workspace import WorkspacePaths, ensure_excluded, git_exclude_file, load_config, save_config

CLAUDE = "claude"
ANTIGRAVITY_NOTE = (
    "Antigravity: its agents see every MCP server that is installed, so a grant changes nothing there; "
    "it is recorded only to keep the two CLIs' settings the same."
)


class RoleGrants:
    """Grants for one workspace. Every call reads the config afresh."""

    def __init__(self, paths: WorkspacePaths, workflow: Workflow) -> None:
        self.paths = paths
        self.workflow = workflow

    # ------------------------------------------------------------ collaborators

    def policy(self) -> RoleGrantPolicy:
        roles = load_project_context(self.paths.dir, self.workflow).roles.roles()
        return WorkflowGrantPolicy(roles, self.workflow.read_only_roles)

    def overlay(self) -> AgentOverlay:
        relative = self.workflow.agent_dirs.get(CLAUDE)
        if relative is None:
            raise ThanhTanError(
                "the workflow does not say where its Claude Code agents are (agent_dirs.claude), so project agents cannot be made",
                ExitCode.ROLE_GRANT_REFUSED,
            )
        config = load_config(self.paths)
        sources = [Path(config.workflow.source_path).parent, *(Path(ref.source_path).parent for ref in config.extensions)]
        return ClaudeAgentOverlay(self.paths.root, [source / relative for source in sources])

    def tools_by_agent(self, grants: Mapping[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        return {agent: tools for role, tools in grants.items() for agent in agents_of(role, self.workflow.tiered_roles)}

    # ------------------------------------------------------------------ actions

    def grant(self, role: str, tool: str) -> list[str]:
        self.policy().check(role, tool)
        config = load_config(self.paths)
        current = config.role_grants.get(role, ())
        if tool in current:
            raise ThanhTanError(f"'{role}' already has {tool}", ExitCode.ROLE_GRANT_REFUSED)
        grants = {**config.role_grants, role: (*current, tool)}
        files = self._render(grants)  # fails before anything is saved when a plugin agent cannot be found
        save_config(self.paths, replace(config, role_grants=grants))
        return self._apply(files)

    def revoke(self, role: str, tool: str) -> list[str]:
        config = load_config(self.paths)
        current = config.role_grants.get(role, ())
        if tool not in current:
            raise ThanhTanError(f"'{role}' has no grant {tool} (thanhtan role list shows them)", ExitCode.ROLE_GRANT_REFUSED)
        remaining = tuple(item for item in current if item != tool)
        grants = {key: value for key, value in config.role_grants.items() if key != role}
        if remaining:
            grants[role] = remaining
        files = self._render(grants)
        save_config(self.paths, replace(config, role_grants=grants))
        return self._apply(files)

    def sync(self) -> list[str]:
        return self._apply(self._render(dict(load_config(self.paths).role_grants)))

    def listing(self) -> list[str]:
        config = load_config(self.paths)
        if not config.role_grants:
            return ["no role has extra tools in this project (thanhtan role grant <role> <tool>)", ANTIGRAVITY_NOTE]
        files = self._render(dict(config.role_grants))
        states = self.overlay().state(files)
        lines = []
        for role, tools in config.role_grants.items():
            lines.append(f"{role}: {', '.join(tools)}")
            for agent in agents_of(role, self.workflow.tiered_roles):
                name = project_agent_file(agent)
                lines.append(f"  Claude Code agent: {project_agent_name(agent)} ({states[name]})")
        if any(state != CURRENT for state in states.values()):
            lines.append("some project agents are out of date or missing: run `thanhtan role sync`")
        lines.append(ANTIGRAVITY_NOTE)
        return lines

    def project_agent_for(self, role: str, agent: str) -> str | None:
        """The project agent that stands in for ``agent`` (a plugin agent of ``role``), when the role has grants and the file exists."""
        if not load_config(self.paths).role_grants.get(role):
            return None
        present = (self.paths.root / CLAUDE_PROJECT_AGENTS_DIR / project_agent_file(agent)).is_file()
        return project_agent_name(agent) if present else None

    # ------------------------------------------------------------------ helpers

    def _render(self, grants: Mapping[str, tuple[str, ...]]) -> Mapping[str, str]:
        return self.overlay().render(self.tools_by_agent(grants))

    def _apply(self, files: Mapping[str, str]) -> list[str]:
        if files:
            ensure_excluded(git_exclude_file(self.paths.root), PROJECT_AGENT_EXCLUDE_ENTRY)
        return list(self.overlay().write(files))
