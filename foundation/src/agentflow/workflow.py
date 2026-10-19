"""Load a family's workflow file and check it: JSON Schema first, then cross-references."""

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from agentflow.constants import ENCODING, WORKFLOW_SCHEMA_FILE, ExitCode
from agentflow.errors import AgentflowError
from agentflow.fsutil import file_sha256
from agentflow.models import Workflow, workflow_from_dict
from agentflow.validation import schema_errors

_INDENT = "\n  - "


def load_workflow(path: Path) -> Workflow:
    if not path.is_file():
        raise AgentflowError(f"workflow file not found: {path}", ExitCode.WORKFLOW_NOT_FOUND)
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AgentflowError(f"{path}: cannot read workflow: {exc}", ExitCode.INVALID_WORKFLOW) from exc
    return parse_workflow(data, origin=str(path))


def parse_workflow(data: Any, origin: str) -> Workflow:
    problems = schema_errors(data, WORKFLOW_SCHEMA_FILE)
    if not problems:
        workflow = workflow_from_dict(data)
        problems = reference_problems(workflow)
    if problems:
        raise AgentflowError(
            f"{origin}: invalid workflow:{_INDENT}{_INDENT.join(problems)}",
            ExitCode.INVALID_WORKFLOW,
        )
    return workflow


def reference_problems(workflow: Workflow) -> list[str]:
    """Rules JSON Schema cannot express: unique ids, and on_fail pointing at an earlier step."""
    problems: list[str] = []
    counts = Counter(step.id for step in workflow.steps)
    problems += [f"duplicate step id '{step_id}'" for step_id, n in counts.items() if n > 1]

    step_roles = {step.role for step in workflow.steps}
    problems += [f"tiered role '{role}' is not the role of any step" for role in workflow.tiered_roles if role not in step_roles]

    problems += _size_problems(workflow)
    problems += [
        f"step '{step.id}': an approval checklist needs requires_approval"
        for step in workflow.steps
        if step.has_checklist and not step.requires_approval
    ]

    position = {step.id: index for index, step in enumerate(workflow.steps)}
    for index, step in enumerate(workflow.steps):
        if step.on_fail is None:
            continue
        if step.on_fail not in position:
            problems.append(f"step '{step.id}': on_fail '{step.on_fail}' does not exist")
        elif position[step.on_fail] >= index:
            problems.append(f"step '{step.id}': on_fail '{step.on_fail}' must be an earlier step")
    return problems


def _size_problems(workflow: Workflow) -> list[str]:
    if not workflow.sizes:
        return []
    problems: list[str] = []
    ids = {profile.id for profile in workflow.sizes}
    if workflow.default_size not in ids:
        problems.append(f"sizes: default '{workflow.default_size}' is not one of the profiles ({', '.join(sorted(ids))})")
    approval = {step.id for step in workflow.steps if step.requires_approval}
    steps = {step.id for step in workflow.steps}
    for profile in workflow.sizes:
        for step_id in profile.skip_approval:
            if step_id not in approval:
                problems.append(f"size '{profile.id}': skip_approval '{step_id}' is not a step that needs approval")
        for step_id in profile.scans:
            if step_id not in steps:
                problems.append(f"size '{profile.id}': scans names step '{step_id}', which does not exist")
    return problems


class FileWorkflowSource:
    """``WorkflowSource`` backed by a YAML file on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Workflow:
        return load_workflow(self.path)

    def fingerprint(self) -> str:
        return file_sha256(self.path)
