"""Registering extensions in a workspace: copy the file in, remember where it came from, detect drift."""

from dataclasses import dataclass, replace
from pathlib import Path

from agentflow.constants import (
    EXTENSIONS_DIR,
    YAML_SUFFIX,
    DriftStatus,
    ExitCode,
    SyncOutcome,
)
from agentflow.errors import AgentflowError
from agentflow.extension import Extension, load_extension_file
from agentflow.fsutil import file_sha256, write_bytes_atomic
from agentflow.models import ExtensionRef, Workflow
from agentflow.scan_tools import BUILTIN_TOOLS
from agentflow.workspace import WorkspacePaths, load_config, save_config


@dataclass(frozen=True)
class RegisteredExtension:
    ref: ExtensionRef
    extension: Extension


@dataclass(frozen=True)
class SyncReport:
    name: str
    outcome: SyncOutcome


def copy_path(paths: WorkspacePaths, name: str) -> Path:
    return paths.dir / EXTENSIONS_DIR / f"{name}{YAML_SUFFIX}"


def _write_copy(paths: WorkspacePaths, name: str, source: Path) -> Path:
    target = copy_path(paths, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(target, source.read_bytes())
    return target


def load_registered(paths: WorkspacePaths) -> list[RegisteredExtension]:
    """Every registered extension, read from the workspace copies (never from the plugin's own file)."""
    registered = []
    for ref in load_config(paths).extensions:
        path = copy_path(paths, ref.name)
        registered.append(RegisteredExtension(ref, load_extension_file(path)))
    return registered


def drift(ref: ExtensionRef) -> DriftStatus:
    source = Path(ref.source_path)
    if not source.is_file():
        return DriftStatus.SOURCE_MISSING
    return DriftStatus.IN_SYNC if file_sha256(source) == ref.sha256 else DriftStatus.SOURCE_CHANGED


def conflicts(extension: Extension, workflow: Workflow, others: list[Extension]) -> list[str]:
    """Why ``extension`` cannot join the workspace next to the workflow and the extensions already there."""
    problems: list[str] = []
    steps = {step.id for step in workflow.steps}
    taken_roles = {step.role for step in workflow.steps} | {role for other in others for role in other.role_ids}
    taken_tools = {tool.id for tool in BUILTIN_TOOLS} | {tool.id for other in others for tool in other.scan_tools}
    problems += [f"role '{role}' already exists" for role in extension.role_ids if role in taken_roles]
    problems += [f"scan tool '{tool.id}' already exists" for tool in extension.scan_tools if tool.id in taken_tools]
    problems += [f"scan tool '{tool.id}': the workflow has no step '{tool.step}'" for tool in extension.scan_tools if tool.step not in steps]
    problems += [f"gate on step '{step}': the workflow has no such step" for step, _kind in extension.gates if step not in steps]
    keys = {other.settings_key for other in others if other.settings_key}
    if extension.settings_key in keys:
        problems.append(f"settings key '{extension.settings_key}' is already used by another extension")
    return problems


def add_extension(paths: WorkspacePaths, workflow: Workflow, source: Path) -> Extension:
    """Check ``source``, copy it into ``.ThanhTan/extensions/`` and register it in ``config.yaml``."""
    source = source.resolve()
    extension = load_extension_file(source)
    config = load_config(paths)
    if extension.family != config.workflow.family:
        raise AgentflowError(
            f"extension '{extension.name}' is for family '{extension.family}', this workspace uses '{config.workflow.family}'",
            ExitCode.EXTENSION_INVALID,
        )
    if any(ref.name == extension.name for ref in config.extensions):
        raise AgentflowError(f"extension '{extension.name}' is already registered; use `agentflow ext sync`", ExitCode.EXTENSION_INVALID)
    others = [item.extension for item in load_registered(paths)]
    problems = conflicts(extension, workflow, others)
    if problems:
        raise AgentflowError(f"extension '{extension.name}' conflicts:\n  - " + "\n  - ".join(problems), ExitCode.EXTENSION_INVALID)
    target = _write_copy(paths, extension.name, source)
    ref = ExtensionRef(extension.name, str(source), file_sha256(target))
    save_config(paths, replace(config, extensions=(*config.extensions, ref)))
    return extension


def sync_extensions(
    paths: WorkspacePaths, workflow: Workflow, name: str | None, in_flight: list[str], force: bool
) -> list[SyncReport]:
    """Replace the copies with their (checked) sources. Tasks in flight block it unless ``force``."""
    config = load_config(paths)
    selected = [ref for ref in config.extensions if name is None or ref.name == name]
    if not selected:
        raise AgentflowError(f"no registered extension{f' named {name}' if name else ''}", ExitCode.EXTENSION_INVALID)
    if in_flight and not force:
        raise AgentflowError(
            f"tasks are in progress ({', '.join(in_flight)}); finish them or use --force", ExitCode.SYNC_BLOCKED
        )
    reports: list[SyncReport] = []
    refs = list(config.extensions)
    for ref in selected:
        source = Path(ref.source_path)
        extension = load_extension_file(source) if source.is_file() else None
        if extension is None:
            raise AgentflowError(f"the source of extension '{ref.name}' is gone: {source}", ExitCode.SYNC_BLOCKED)
        if extension.name != ref.name:
            raise AgentflowError(f"{source} now declares extension '{extension.name}', not '{ref.name}'", ExitCode.EXTENSION_INVALID)
        others = [item.extension for item in load_registered(paths) if item.ref.name != ref.name]
        problems = conflicts(extension, workflow, others)
        if problems:
            raise AgentflowError(f"extension '{ref.name}' conflicts:\n  - " + "\n  - ".join(problems), ExitCode.EXTENSION_INVALID)
        new_sha = file_sha256(source)
        if new_sha == ref.sha256 and copy_path(paths, ref.name).is_file():
            reports.append(SyncReport(ref.name, SyncOutcome.UNCHANGED))
            continue
        refs[refs.index(ref)] = replace(ref, sha256=file_sha256(_write_copy(paths, ref.name, source)))
        reports.append(SyncReport(ref.name, SyncOutcome.UPDATED))
    save_config(paths, replace(config, extensions=tuple(refs)))
    return reports
