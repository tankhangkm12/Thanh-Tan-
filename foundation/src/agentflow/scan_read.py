"""Turn a scan tool's output into findings, as its ``ResultSpec`` describes."""

import json
from collections.abc import Iterator
from typing import Any

from agentflow.constants import ExitCode, ResultKind, ScanStatus
from agentflow.errors import AgentflowError
from agentflow.scan_types import ResultSpec, ScanFinding

FLATTEN = "[]"
PATH_SEPARATOR = "."
UNKNOWN = "unknown"
EXCERPT_LINES = 40


def _walk(data: Any, path: str) -> Iterator[Any]:
    """Items found by following ``path`` (``Results[].Vulnerabilities``) through ``data``."""
    if not path:
        yield from data if isinstance(data, list) else []
        return
    head, _, rest = path.partition(PATH_SEPARATOR)
    flatten = head.endswith(FLATTEN)
    key = head[: -len(FLATTEN)] if flatten else head
    node = data.get(key) if isinstance(data, dict) else None
    if node is None:
        return
    if flatten:
        for element in node if isinstance(node, list) else []:
            yield from _walk(element, rest) if rest else iter([element])
    elif rest:
        yield from _walk(node, rest)
    elif isinstance(node, list):
        yield from node
    else:
        yield node


def _field(item: Any, path: str | None) -> str:
    node = item
    for part in (path or "").split(PATH_SEPARATOR):
        if not part:
            return ""
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            return ""
    return str(node)


def _excerpt(tool: str, output: str) -> str:
    """The end of the tool's own output (where tools print their verdict), so the finding explains itself."""
    lines = [line for line in output.strip().splitlines() if line.strip()]
    tail = "\n".join(lines[-EXCERPT_LINES:])
    return f"{tool} failed:\n{tail}" if tail else f"{tool} failed"


def parse_findings(tool: str, spec: ResultSpec, output: str) -> tuple[ScanFinding, ...]:
    """Findings in JSON ``output``; unreadable output is a hard error, never "no findings"."""
    try:
        data = json.loads(output) if output.strip() else []
    except json.JSONDecodeError as exc:
        raise AgentflowError(f"{tool}: the output is not JSON: {exc}", ExitCode.SCAN_FAILED) from exc
    findings = []
    for item in _walk(data, spec.items):
        rule = _field(item, spec.rule_field) or UNKNOWN
        severity = _field(item, spec.severity_field) if spec.severity_field else ""
        location = _field(item, spec.location_field)
        message = _field(item, spec.message_field)
        blocks = not spec.blocking_severities or severity in spec.blocking_severities
        if spec.require_field and not _field(item, spec.require_field):
            blocks = False
        findings.append(ScanFinding(f"{tool}:{rule}:{location}", rule, severity or UNKNOWN, location, message, blocks))
    return tuple(findings)


def status_of(findings: tuple[ScanFinding, ...]) -> ScanStatus:
    return ScanStatus.BLOCKED if any(f.blocking for f in findings) else ScanStatus.CLEAN


def read_result(tool: str, spec: ResultSpec, returncode: int, output: str) -> tuple[ScanStatus, tuple[ScanFinding, ...]]:
    """Status and findings of a finished run; an exit code outside the tool's known codes is a hard error."""
    if spec.kind is ResultKind.EXIT_CODE:
        if returncode == 0:
            return ScanStatus.CLEAN, ()
        if returncode in spec.fail_exit_codes:
            finding = ScanFinding(f"{tool}:exit-{returncode}:", f"exit-{returncode}", UNKNOWN, "", _excerpt(tool, output), True)
            return ScanStatus.BLOCKED, (finding,)
        raise AgentflowError(f"{tool} could not run properly (exit {returncode}):\n{output.strip()}", ExitCode.SCAN_FAILED)
    if returncode not in spec.ok_exit_codes:
        raise AgentflowError(f"{tool} could not run properly (exit {returncode}):\n{output.strip()}", ExitCode.SCAN_FAILED)
    findings = parse_findings(tool, spec, output)
    return status_of(findings), findings
