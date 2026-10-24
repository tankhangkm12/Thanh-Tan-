"""The documents a task works from, pinned when a person approves the step that names them.

The report of that step (dev-core: ``confirm``) lists them in a section::

    ## Tài liệu
    - docs/spec/orders.md
    - docs/design/
    - https://example.com/spec

When a person approves a step that has ``pin_docs_on_approval``, agentflow keeps the sha256 of every path (a file, or every
file of a folder) in ``tasks/<task>/docs-pinned.json``. Later steps compare: a document that changed since is shown in the
approval checklist of the review (``changed-docs``) and by ``agentflow status``, so the work is not checked against a
version nobody approved. Links cannot be read, so they are kept as they are and never compared.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from agentflow.constants import DOCS_HEADING, DOCS_PINNED_FILE, ENCODING, MARKDOWN_SUFFIX, REPORTS_DIR, TASKS_DIR, StepStatus, TaskStatus
from agentflow.fsutil import write_text_atomic
from agentflow.models import Task, Workflow

_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
_NONE_WORDS = frozenset({"không có", "khong co", "none"})
_SKIPPED_DIRS = frozenset({".git", ".agentflow", "node_modules", "__pycache__", ".venv"})
MISSING = "missing"
CHANGED = "changed"
APPEARED = "appeared"


@dataclass(frozen=True)
class DocChange:
    path: str
    # ``changed`` (the content differs), ``missing`` (gone since it was pinned) or ``appeared`` (not there when pinned).
    kind: str


def parse_docs(text: str) -> tuple[list[str], list[str]]:
    """The paths and the links of the ``## Tài liệu`` section of a report, in order."""
    paths: list[str] = []
    links: list[str] = []
    inside = False
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            inside = heading["title"].strip().lower() == DOCS_HEADING.lower()
            continue
        bullet = _BULLET.match(line) if inside else None
        if bullet is None:
            continue
        entry = bullet["text"].strip().strip("`").strip()
        if not entry or entry.rstrip(".").lower() in _NONE_WORDS:
            continue
        target = links if _SCHEME.match(entry) else paths
        if entry not in target:
            target.append(entry)
    return paths, links


def _resolve(root: Path, entry: str) -> Path:
    path = Path(entry.replace("\\", "/")) if os.sep == "/" else Path(entry)
    return path if path.is_absolute() else root / path


def digest(root: Path, entry: str) -> str | None:
    """The sha256 of a file, or of the names and contents of every file of a folder; ``None`` when there is nothing."""
    path = _resolve(root, entry)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        return None
    combined = hashlib.sha256()
    for folder, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in _SKIPPED_DIRS)
        for name in sorted(files):
            file = Path(folder, name)
            combined.update(file.relative_to(path).as_posix().encode(ENCODING) + b"\0")
            combined.update(hashlib.sha256(file.read_bytes()).hexdigest().encode(ENCODING) + b"\n")
    return combined.hexdigest()


def pinned_path(workspace_dir: Path, task_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / DOCS_PINNED_FILE


def pin_on_approval(workspace_dir: Path, root: Path, workflow: Workflow, task: Task, at: str) -> list[str]:
    """Pin the documents of the step a person is about to approve, when the workflow says so. Returns the lines to print."""
    step = workflow.get_step(task.current_step)
    if step is None or not step.pin_docs_on_approval or task.status is not TaskStatus.OPEN or task.step_status is not StepStatus.AWAITING_APPROVAL:
        return []
    report = workspace_dir / TASKS_DIR / task.id / REPORTS_DIR / f"{step.id}{MARKDOWN_SUFFIX}"
    paths, links = parse_docs(report.read_text(encoding=ENCODING)) if report.is_file() else ([], [])
    docs = {entry: digest(root, entry) for entry in paths}
    record = {"at": at, "step": step.id, "docs": docs, "links": links}
    target = pinned_path(workspace_dir, task.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(target, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    if not paths and not links:
        return [f"documents pinned: none (the {step.id} report has no '## {DOCS_HEADING}' section with entries)"]
    absent = [entry for entry, sha in docs.items() if sha is None]
    note = f"; not found: {', '.join(absent)}" if absent else ""
    return [f"documents pinned: {len(paths)} path(s), {len(links)} link(s) (links are not compared){note}"]


def changes(workspace_dir: Path, root: Path, task_id: str) -> list[DocChange]:
    """The pinned documents that are not as they were; none when nothing was pinned."""
    try:
        record = json.loads(pinned_path(workspace_dir, task_id).read_text(encoding=ENCODING))
        docs = record["docs"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    if not isinstance(docs, dict):
        return []
    found = []
    for entry, pinned in docs.items():
        now = digest(root, entry)
        if now == pinned:
            continue
        found.append(DocChange(entry, MISSING if now is None else APPEARED if pinned is None else CHANGED))
    return found
