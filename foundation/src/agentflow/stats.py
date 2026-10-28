"""What a task cost: rounds, approvals, time by step and the gates that refused a pass (``agentflow stats``).

Everything comes from what agentflow already keeps: the history of each task in ``state.json`` and the gate log
(``tasks/<task>/gate-log.jsonl``, one line each time a gate refuses ``task advance --result pass``). Token use is not
known to agentflow; the CLI shows it (``/usage`` in Claude Code).
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentflow.constants import ENCODING, GATE_LOG_FILE, TASKS_DIR, HistoryEvent
from agentflow.models import State, Task
from agentflow.state import TIMESTAMP_FORMAT

# Events after which a task is no longer at the step of the entry.
_LEAVES = frozenset({HistoryEvent.STARTED, HistoryEvent.DONE, HistoryEvent.CANCELLED, HistoryEvent.BLOCKED})


@dataclass(frozen=True)
class TaskStats:
    id: str
    title: str
    status: str
    size: str | None
    type: str | None
    started: str | None
    ended: str | None
    seconds: int
    approvals: int
    fails: dict[str, int]
    blocked: int
    resumed: int
    # Time at each step, from entering it to leaving it, and the part of it spent waiting for a person.
    step_seconds: dict[str, int]
    waiting_seconds: int
    gate_refusals: dict[str, int] = field(default_factory=dict)

    @property
    def rounds(self) -> int:
        return sum(self.fails.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "size": self.size,
            "type": self.type,
            "started": self.started,
            "ended": self.ended,
            "seconds": self.seconds,
            "approvals": self.approvals,
            "rounds": self.rounds,
            "fails": self.fails,
            "blocked": self.blocked,
            "resumed": self.resumed,
            "step_seconds": self.step_seconds,
            "waiting_seconds": self.waiting_seconds,
            "gate_refusals": self.gate_refusals,
        }


def parse_time(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _between(start: str, end: str) -> int:
    first, last = parse_time(start), parse_time(end)
    if first is None or last is None:
        return 0
    return max(0, int((last - first).total_seconds()))


def gate_log_path(workspace_dir: Path, task_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / GATE_LOG_FILE


def record_refusal(workspace_dir: Path, task_id: str, step_id: str, kinds: list[str], at: str) -> None:
    """Add a line to the gate log of the task. A log that cannot be written never stops the command."""
    path = gate_log_path(workspace_dir, task_id)
    line = json.dumps({"at": at, "step": step_id, "gates": kinds}, ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=ENCODING, newline="\n") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def gate_refusals(workspace_dir: Path, task_id: str) -> Counter[str]:
    """How many times each gate refused a pass of the task (a refusal by several gates counts for each)."""
    counted: Counter[str] = Counter()
    try:
        text = gate_log_path(workspace_dir, task_id).read_text(encoding=ENCODING)
    except OSError:
        return counted
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        gates = entry.get("gates") if isinstance(entry, dict) else None
        if isinstance(gates, list):
            counted.update(str(gate) for gate in gates)
    return counted


def task_stats(task: Task, refusals: Counter[str] | None = None) -> TaskStats:
    history = task.history
    step_seconds: Counter[str] = Counter()
    waiting = 0
    for index, entry in enumerate(history):
        following = history[index + 1] if index + 1 < len(history) else None
        if entry.event is HistoryEvent.STARTED:
            leave = next((later for later in history[index + 1 :] if later.event in _LEAVES), None)
            if leave is not None:
                step_seconds[entry.step] += _between(entry.at, leave.at)
        elif entry.event is HistoryEvent.PASSED and following is not None and following.event in (HistoryEvent.APPROVED, HistoryEvent.FAILED):
            waiting += _between(entry.at, following.at)
    started = history[0].at if history else None
    ended = history[-1].at if history else None
    fails = Counter(entry.step for entry in history if entry.event is HistoryEvent.FAILED)
    return TaskStats(
        id=task.id,
        title=task.title,
        status=str(task.status),
        size=task.size,
        type=task.type,
        started=started,
        ended=ended,
        seconds=_between(started, ended) if started and ended else 0,
        approvals=sum(1 for entry in history if entry.event is HistoryEvent.APPROVED),
        fails=dict(fails),
        blocked=sum(1 for entry in history if entry.event is HistoryEvent.BLOCKED),
        resumed=sum(1 for entry in history if entry.event is HistoryEvent.RESUMED),
        step_seconds=dict(step_seconds),
        waiting_seconds=waiting,
        gate_refusals=dict(refusals or {}),
    )


def collect(workspace_dir: Path, state: State, task_id: str | None = None) -> list[TaskStats]:
    tasks = [task for task in state.tasks if task_id is None or task.id == task_id]
    return [task_stats(task, gate_refusals(workspace_dir, task.id)) for task in tasks]


def duration(seconds: int) -> str:
    """``1h05m``, ``12m``, ``40s``."""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def render(found: list[TaskStats]) -> list[str]:
    if not found:
        return ["no tasks yet"]
    lines = []
    for item in found:
        size = f", size {item.size}" if item.size else ""
        kind = f", {item.type}" if item.type else ""
        lines.append(f"{item.id} {item.title} ({item.status}{kind}{size})")
        lines.append(
            f"  time {duration(item.seconds)} (waiting for a person {duration(item.waiting_seconds)}); "
            f"approvals {item.approvals}; rounds {item.rounds}; blocked {item.blocked}"
        )
        if item.fails:
            lines.append("  failed at: " + ", ".join(f"{step} x{count}" for step, count in item.fails.items()))
        if item.step_seconds:
            lines.append("  by step: " + ", ".join(f"{step} {duration(seconds)}" for step, seconds in item.step_seconds.items()))
        if item.gate_refusals:
            lines.append("  gates that refused a pass: " + ", ".join(f"{gate} x{count}" for gate, count in item.gate_refusals.items()))
    if len(found) > 1:
        lines.extend(_totals(found))
    return lines


def _totals(found: list[TaskStats]) -> list[str]:
    statuses = Counter(item.status for item in found)
    refusals: Counter[str] = Counter()
    fails: Counter[str] = Counter()
    for item in found:
        refusals.update(item.gate_refusals)
        fails.update(item.fails)
    total_rounds = sum(item.rounds for item in found)
    lines = [
        "",
        f"total: {len(found)} task(s) (" + ", ".join(f"{status} {count}" for status, count in sorted(statuses.items())) + ")",
        f"  rounds {total_rounds} ({total_rounds / len(found):.1f} per task); approvals {sum(item.approvals for item in found)}; "
        f"waiting for a person {duration(sum(item.waiting_seconds for item in found))}",
    ]
    if fails:
        lines.append("  failed at: " + ", ".join(f"{step} x{count}" for step, count in fails.most_common()))
    if refusals:
        lines.append("  gates that refused a pass: " + ", ".join(f"{gate} x{count}" for gate, count in refusals.most_common()))
    return lines
