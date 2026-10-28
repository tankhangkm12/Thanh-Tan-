"""Where scan results live: ``.ThanhTan/tasks/<task>/scans/``, plus the decisions that suppress findings."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from agentflow.constants import (
    DECISION_SUPPRESS_SUFFIX,
    DECISIONS_DIR,
    ENCODING,
    MARKDOWN_SUFFIX,
    SCAN_SUMMARY_FILE,
    SCANS_DIR,
    SCHEMA_VERSION,
    TASKS_DIR,
    ExitCode,
    ScanStatus,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.scan_types import ScanFinding, ScanOutcome

JSON_INDENT = 2
FRONTMATTER_FENCE = "---"
SUPPRESS_KIND = "suppress"
ID_DIGEST_LENGTH = 10


class ScanStore:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir

    def scans_dir(self, task_id: str) -> Path:
        return self.workspace_dir / TASKS_DIR / task_id / SCANS_DIR

    def save(self, task_id: str, outcomes: list[ScanOutcome], outputs: dict[str, str]) -> None:
        """Write each tool's raw output and merge the outcomes into ``summary.json`` (one entry per tool)."""
        directory = self.scans_dir(task_id)
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in outputs.items():
            write_text_atomic(directory / name, text if text.endswith("\n") else text + "\n")
        merged = {outcome.tool: outcome for outcome in self.load(task_id).values()}
        merged.update({outcome.tool: outcome for outcome in outcomes})
        document = {"schema_version": SCHEMA_VERSION, "outcomes": [_to_dict(o) for o in merged.values()]}
        write_text_atomic(directory / SCAN_SUMMARY_FILE, json.dumps(document, indent=JSON_INDENT, ensure_ascii=False) + "\n")

    def load(self, task_id: str) -> dict[str, ScanOutcome]:
        path = self.scans_dir(task_id) / SCAN_SUMMARY_FILE
        if not path.is_file():
            return {}
        try:
            document = json.loads(path.read_text(encoding=ENCODING))
            outcomes = [_from_dict(item) for item in document["outcomes"]]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AgentflowError(f"{path}: cannot read scan results: {exc}", ExitCode.SCAN_FAILED) from exc
        return {outcome.tool: outcome for outcome in outcomes}


def _to_dict(outcome: ScanOutcome) -> dict[str, Any]:
    data = asdict(outcome)
    data["status"] = str(outcome.status)
    return data


def _from_dict(data: dict[str, Any]) -> ScanOutcome:
    findings = tuple(ScanFinding(**finding) for finding in data.pop("findings"))
    return ScanOutcome(findings=findings, **{**data, "status": ScanStatus(data["status"])})


# ------------------------------------------------------------ suppression


def suppression_path(workspace_dir: Path, task_id: str, finding_id: str) -> Path:
    digest = hashlib.sha256(finding_id.encode(ENCODING)).hexdigest()[:ID_DIGEST_LENGTH]
    name = f"{task_id}-{DECISION_SUPPRESS_SUFFIX}-{digest}{MARKDOWN_SUFFIX}"
    return workspace_dir / DECISIONS_DIR / name


def write_suppression(workspace_dir: Path, task_id: str, finding: ScanFinding, reason: str, at: str) -> Path:
    """Record that a person accepts ``finding`` for this task. The reason is required."""
    if not reason.strip():
        raise AgentflowError("a suppression needs a reason (--reason)", ExitCode.INVALID_INPUT)
    path = suppression_path(workspace_dir, task_id, finding.id)
    header = {
        "kind": SUPPRESS_KIND,
        "task": task_id,
        "finding": finding.id,
        "rule": finding.rule,
        "severity": finding.severity,
        "reason": reason.strip(),
        "decided_at": at,
    }
    text = (
        f"{FRONTMATTER_FENCE}\n{yaml.safe_dump(header, sort_keys=False, allow_unicode=True)}{FRONTMATTER_FENCE}\n"
        f"# Finding suppressed by a person\n\n{finding.message}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, text)
    return path


def suppressed_ids(workspace_dir: Path, task_id: str) -> set[str]:
    """Finding ids a person suppressed for ``task_id``; unreadable decision files count for nothing."""
    ids: set[str] = set()
    directory = workspace_dir / DECISIONS_DIR
    if not directory.is_dir():
        return ids
    for path in directory.glob(f"{task_id}-{DECISION_SUPPRESS_SUFFIX}-*{MARKDOWN_SUFFIX}"):
        lines = path.read_text(encoding=ENCODING).splitlines()
        if not lines or lines[0] != FRONTMATTER_FENCE or FRONTMATTER_FENCE not in lines[1:]:
            continue
        try:
            header = yaml.safe_load("\n".join(lines[1 : lines.index(FRONTMATTER_FENCE, 1)]))
        except yaml.YAMLError:
            continue
        if isinstance(header, dict) and header.get("kind") == SUPPRESS_KIND and header.get("task") == task_id:
            ids.add(str(header.get("finding")))
    return ids
