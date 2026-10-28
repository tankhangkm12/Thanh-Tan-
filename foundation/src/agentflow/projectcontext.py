"""What the checks need to know about the project: valid roles, plan rules, scan tools, gates and settings.

The workflow supplies the base; registered extensions add to it.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path
from typing import Any

from agentflow.constants import CheckKind, GateKind, PlanRuleKind
from agentflow.conventions import Convention
from agentflow.errors import AgentflowError
from agentflow.convention_sources import load_effective_conventions, semgrep_rule_files
from agentflow.plan_rules import ItemOrderRule, LayerOrderRule, MaxPlanItemsRule
from agentflow.ext_rules import ExtensionRules
from agentflow.extensions import load_registered
from agentflow.interfaces import PlanRule, PlanWideRule
from agentflow.models import Task, Workflow
from agentflow.scan_types import ScanToolSpec
from agentflow.settings import get_value
from agentflow.workspace import WorkspacePaths, load_config


@dataclass(frozen=True)
class RoleSet:
    names: frozenset[str]

    def roles(self) -> Collection[str]:
        return self.names


@dataclass(frozen=True)
class ProjectContext:
    roles: RoleSet
    plan_rules: Sequence[PlanRule] = field(default_factory=tuple)
    # True when some rule looks at the paths an item changes, so every item must list them.
    require_files: bool = False
    # Added by extensions: scan tools, gates (step id, kind), a project-settings lookup and commit rules.
    scan_tools: tuple[ScanToolSpec, ...] = ()
    extra_gates: tuple[tuple[str, GateKind], ...] = ()
    # Checks on a whole plan that enforced conventions switch on (such as the order of interface and implement items).
    plan_wide_rules: tuple[PlanWideRule, ...] = ()
    # Rule files of enforced `check: semgrep` conventions (code, path), and why some cannot be used.
    custom_semgrep: tuple[tuple[str, Path], ...] = ()
    custom_semgrep_problems: tuple[str, ...] = ()
    lookup: Callable[[str], Any] = field(default=lambda key: None)
    rules: ExtensionRules | None = None
    # Step id -> the scan tools it runs for the task's size; a step not listed runs all of its tools.
    scan_filter: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


_PLAN_RULES = frozenset({PlanRuleKind.ITEM_ORDER, PlanRuleKind.LAYER_ORDER})


def _plan_rule(convention: Convention) -> PlanWideRule:
    if convention.rule == PlanRuleKind.LAYER_ORDER:
        return LayerOrderRule(convention.code, convention.layer_names, convention.scope_globs)
    return ItemOrderRule(convention.code)


def load_project_context(workspace_dir: Path, workflow: Workflow, task: Task | None = None) -> ProjectContext:
    paths = WorkspacePaths(workspace_dir.parent)
    roles = {step.role for step in workflow.steps}
    registered = load_registered(paths)
    effective = load_effective_conventions(workspace_dir)
    profile = workflow.size_profile(task.size) if task is not None else None
    limit = (MaxPlanItemsRule(profile.max_plan_items, profile.id),) if profile is not None and profile.max_plan_items else ()
    wide = limit + tuple(_plan_rule(item.convention) for item in effective.checked_by(CheckKind.PLAN) if item.convention.rule in _PLAN_RULES)
    custom, custom_problems = semgrep_rule_files(workspace_dir, effective)
    from_conventions = {
        "plan_wide_rules": wide,
        "custom_semgrep": tuple(custom),
        "custom_semgrep_problems": tuple(custom_problems),
        "scan_filter": dict(profile.scans) if profile is not None else {},
    }
    try:
        settings = load_config(paths).settings
    except AgentflowError:
        settings = {}

    def lookup(key: str) -> Any:
        return get_value(settings, key)

    if not registered:
        return ProjectContext(RoleSet(frozenset(roles)), lookup=lookup, **from_conventions)
    extensions = [item.extension for item in registered]
    roles |= {role for extension in extensions for role in extension.role_ids}

    rules = ExtensionRules(extensions, lookup)
    return ProjectContext(
        roles=RoleSet(frozenset(roles)),
        plan_rules=(rules,),
        require_files=rules.requires_files,
        **from_conventions,
        scan_tools=tuple(tool for extension in extensions for tool in extension.scan_tools),
        extra_gates=tuple(gate for extension in extensions for gate in extension.gates),
        lookup=lookup,
        rules=rules,
    )
