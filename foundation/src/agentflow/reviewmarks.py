"""Where the last review of a task stopped, so that the next round reads only what changed since.

A review or security round that ends (passed or sent back) leaves a mark: the commit it looked at. The next round of the same
step reads ``agentflow scope`` and reviews the difference from that commit, not the whole task again. A mark is a convenience
for the reviewer, not a protection: a missing or odd mark means the whole task is in scope.
"""

import json
from pathlib import Path

from agentflow.constants import ENCODING
from agentflow.fsutil import write_text_atomic

MARKS_FILE = "review-marks.json"


def _load(task_dir: Path) -> dict:
    try:
        data = json.loads((task_dir / MARKS_FILE).read_text(encoding=ENCODING))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record(task_dir: Path, step_id: str, head: str, at: str) -> None:
    data = _load(task_dir)
    data[step_id] = {"head": head, "at": at}
    write_text_atomic(task_dir / MARKS_FILE, json.dumps(data, indent=2, sort_keys=True) + "\n")


def mark(task_dir: Path, step_id: str) -> str | None:
    entry = _load(task_dir).get(step_id)
    head = entry.get("head") if isinstance(entry, dict) else None
    return head if isinstance(head, str) and head else None
