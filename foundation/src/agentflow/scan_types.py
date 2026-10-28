"""Typed data for scans: what a tool is, what it found, and the context it runs in."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentflow.constants import FileScope, NetworkMode, ResultKind, ScanStatus


@dataclass(frozen=True)
class ResultSpec:
    """How to read a tool's output."""

    kind: ResultKind
    # json_findings: dotted path to the list ("" = the document is the list; ``a[].b`` flattens ``a``).
    items: str = ""
    rule_field: str = ""
    severity_field: str | None = None
    location_field: str | None = None
    message_field: str | None = None
    # Severities that block; empty means every finding blocks.
    blocking_severities: tuple[str, ...] = ()
    # A finding blocks only if this field is present and non-empty (Trivy: ``FixedVersion``).
    require_field: str | None = None
    # exit_code: exit codes that mean "failed".
    fail_exit_codes: tuple[int, ...] = ()
    # Exit codes that still mean "the tool ran" (and whose output should be read).
    ok_exit_codes: tuple[int, ...] = (0,)


@dataclass(frozen=True)
class MountSpec:
    """A host path or named volume mounted into the container. ``source`` may hold placeholders."""

    source: str
    target: str
    readonly: bool = True
    volume: bool = False


@dataclass(frozen=True)
class FileSelection:
    """Files of the task a tool wants as arguments (``${files}``)."""

    scope: FileScope = FileScope.CHANGED
    globs: tuple[str, ...] = ()
    # Skip the scan (clean, with a note) when no file matches.
    skip_when_empty: bool = True


@dataclass(frozen=True)
class Condition:
    """When a tool applies; ``None`` conditions always apply."""

    config_equals: tuple[str, str] | None = None
    config_present: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanToolSpec:
    id: str
    image: str
    args: tuple[str, ...]
    result: ResultSpec
    # Step whose gate uses the result; ``None`` = the workflow's own scan-gated step.
    step: str | None = None
    network: NetworkMode = NetworkMode.NONE
    mount_repo: bool = True
    mounts: tuple[MountSpec, ...] = ()
    env: tuple[str, ...] = ()
    files: FileSelection | None = None
    when: Condition | None = None
    skip_note: str = ""
    # Run before the container (for example to fetch Semgrep rules into the cache).
    prepare: Callable[["ScanContext"], None] | None = None


@dataclass(frozen=True)
class ScanFinding:
    id: str
    rule: str
    severity: str
    location: str
    message: str
    blocking: bool


@dataclass(frozen=True)
class ScanOutcome:
    tool: str
    status: ScanStatus
    commit: str
    findings: tuple[ScanFinding, ...] = ()
    note: str = ""
    # Name of the raw output file inside the task's ``scans/`` folder.
    output_file: str | None = None
    step: str | None = None

    @property
    def blocking(self) -> tuple[ScanFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)


@dataclass
class ScanContext:
    """What a scan run knows: the repository, the task's range and how to look up project settings."""

    repo: Path
    base: str
    head: str
    changed_files: Sequence[str]
    lookup: Callable[[str], Any] = field(default=lambda key: None)
    cache_dir: Path = Path()
    rulesets: Sequence[str] = ()
    # Values for ``${var:name}`` placeholders (the range, the rules folder, ...).
    extra: dict[str, str] = field(default_factory=dict)
    fetcher: Any = None
    warn: Callable[[str], None] = field(default=lambda message: None)
