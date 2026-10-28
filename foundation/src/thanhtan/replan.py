"""The replan: between one finished task and the next, the project documents are brought up to date.

An agent (the scout) writes ``tasks/<task>/replan.md``; that only PROPOSES. A person reads it and runs
``thanhtan replan done`` (or ``replan skip``): only then is the task marked replanned.

    pending   the latest finished task has no replan yet
    proposed  replan.md exists; a person has not said it is done
    done      a person said so (``replanned_at`` in state.json, ``Replan: done`` in summary.md)
    skipped   a person decided not to replan, on purpose (``decisions/<task>-replan-skip.md``)
"""

import re
from collections.abc import Collection
from dataclasses import dataclass, replace
from pathlib import Path

from thanhtan.confirmations import Confirmations
from thanhtan.constants import (
    DECISIONS_DIR,
    DRIFT_NONE_TEXT,
    ENCODING,
    IN_FLIGHT_TASK_STATUSES,
    MARKDOWN_SUFFIX,
    REPLAN_DONE_HEADING,
    REPLAN_FILE,
    REPLAN_HISTORY_NAME,
    REPLAN_PROCESS_HEADING,
    REPLAN_SKIP_HISTORY_NAME,
    REPLAN_SKIP_SUFFIX,
    SUMMARY_FILE,
    TASKS_DIR,
    ExitCode,
    ReplanState,
    TaskStatus,
)
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic
from thanhtan.interfaces import GitClient, StateStore
from thanhtan.mdutil import normalize_newlines, section_after, visible_lines
from thanhtan.models import State, Task
from thanhtan.project import keep_previous
from thanhtan.roadmap import items_of, read_roadmap
from thanhtan.seal import approval_tag, is_approved
from thanhtan.summary import REPLAN_SUMMARY_LABEL

_DONE_HEADING = re.compile(rf"^##[ \t]+{re.escape(REPLAN_DONE_HEADING)}[ \t]*$")
_PROCESS_HEADING = re.compile(rf"^##[ \t]+{re.escape(REPLAN_PROCESS_HEADING)}[ \t]*$")
_NONE = re.compile(rf"^{re.escape(DRIFT_NONE_TEXT)}\.?$", re.IGNORECASE)
_BULLET = re.compile(r"^-[ \t]+(R\d+)[ \t]*:[ \t]*(\S.*)$")
_SUMMARY_LINE = re.compile(rf"^- {REPLAN_SUMMARY_LABEL}:.*$", re.MULTILINE)
_DATE_CHARS = 10


@dataclass(frozen=True)
class ReplanStatus:
    state: ReplanState
    # The task the state is about: the open task, or the latest finished one; ``None`` when there is none.
    task_id: str | None = None


def replan_path(workspace_dir: Path, task_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / REPLAN_FILE


def skip_path(workspace_dir: Path, task_id: str) -> Path:
    return workspace_dir / DECISIONS_DIR / f"{task_id}{REPLAN_SKIP_SUFFIX}{MARKDOWN_SUFFIX}"


def replan_status(workspace_dir: Path, state: State, git: GitClient) -> ReplanStatus:
    """An open (or blocked) task wins over everything: documents are rewritten between tasks, not during one."""
    open_tasks = [task for task in state.tasks if task.status in IN_FLIGHT_TASK_STATUSES]
    if open_tasks:
        return ReplanStatus(ReplanState.TASK_OPEN, max(open_tasks, key=lambda task: task.id).id)
    finished = [task for task in state.tasks if task.status is TaskStatus.DONE]
    if not finished:
        return ReplanStatus(ReplanState.NO_FINISHED_TASK)
    last = max(finished, key=lambda task: task.id)
    if not is_approved(git, last.id):
        return ReplanStatus(ReplanState.NOT_SEALED, last.id)
    if last.replanned_at:
        return ReplanStatus(ReplanState.DONE, last.id)
    if skip_path(workspace_dir, last.id).is_file():
        return ReplanStatus(ReplanState.SKIPPED, last.id)
    if replan_path(workspace_dir, last.id).is_file():
        return ReplanStatus(ReplanState.PROPOSED, last.id)
    return ReplanStatus(ReplanState.PENDING, last.id)


# ------------------------------------------------------------------ the content


def replan_problems(text: str, roadmap_codes: Collection[str] | None) -> list[str]:
    """Problems with a replan report; empty when it can be saved. ``roadmap_codes`` is ``None`` when there is no roadmap."""
    lines = visible_lines(text)
    problems: list[str] = []
    done = _section(lines, _DONE_HEADING)
    if done is None:
        problems.append(f'the replan has no "## {REPLAN_DONE_HEADING}" section: write `{DRIFT_NONE_TEXT}`, or one `- R<n>: <evidence>` per item')
    elif not done:
        problems.append(f'the "## {REPLAN_DONE_HEADING}" section is empty: write `{DRIFT_NONE_TEXT}`, or one `- R<n>: <evidence>` per item')
    else:
        problems += _done_problems(done, roadmap_codes)
    process = _section(lines, _PROCESS_HEADING)
    if process is None:
        problems.append(f'the replan has no "## {REPLAN_PROCESS_HEADING}" section: write `{DRIFT_NONE_TEXT}`, or what to change')
    elif not process:
        problems.append(f'the "## {REPLAN_PROCESS_HEADING}" section is empty: write `{DRIFT_NONE_TEXT}`, or what to change')
    return problems


def _section(lines: list[str], heading: re.Pattern[str]) -> list[str] | None:
    """Non-blank lines of the first section with this heading; ``None`` when there is no such section."""
    bodies = section_after(lines, heading)
    if not bodies:
        return None
    return [line for line in bodies[0] if line.strip()]


def _done_problems(entries: list[str], roadmap_codes: Collection[str] | None) -> list[str]:
    problems: list[str] = []
    none_seen = False
    items = 0
    previous_was_bullet = False
    for line in entries:
        stripped = line.strip()
        if _NONE.match(stripped):
            none_seen = True
            previous_was_bullet = False
            continue
        bullet = None if line[:1].isspace() else _BULLET.match(line.rstrip())
        if bullet is not None:
            items += 1
            previous_was_bullet = True
            code = bullet.group(1)
            if roadmap_codes is None:
                problems.append(f"{code} cannot be named: the project has no roadmap yet")
            elif code not in roadmap_codes:
                problems.append(f"{code} is not an item of the roadmap (items: {', '.join(sorted(roadmap_codes))})")
            continue
        if line[:1].isspace() and previous_was_bullet:
            continue  # the evidence goes on over several lines
        previous_was_bullet = False
        problems.append(
            f'"## {REPLAN_DONE_HEADING}": each line must be a bullet `- R<n>: <evidence>` (or `{DRIFT_NONE_TEXT}`): {stripped[:60]}'
        )
    if none_seen and items:
        problems.append(f'"## {REPLAN_DONE_HEADING}" says `{DRIFT_NONE_TEXT}` and also lists items: keep one of the two')
    return problems


# --------------------------------------------------------------------- summary


def set_summary_replan(workspace_dir: Path, task_id: str, value: str) -> None:
    """Rewrite the ``- Replan:`` line of summary.md (a summary from before the line existed gets it after ``Approved at``)."""
    path = workspace_dir / TASKS_DIR / task_id / SUMMARY_FILE
    if not path.is_file():
        return
    text = normalize_newlines(path.read_text(encoding=ENCODING))
    line = f"- {REPLAN_SUMMARY_LABEL}: {value}"
    if _SUMMARY_LINE.search(text):
        text = _SUMMARY_LINE.sub(lambda _: line, text, count=1)
    else:
        text = re.sub(r"^(- Approved at:.*)$", lambda m: f"{m.group(1)}\n{line}", text, count=1, flags=re.MULTILINE)
    write_text_atomic(path, text)


# ------------------------------------------------------------------- the verbs


def require_writable(status: ReplanStatus) -> str:
    """The task a replan may be written for; raises when the state does not allow it."""
    match status.state:
        case ReplanState.TASK_OPEN:
            raise ThanhTanError(
                f"task {status.task_id} is still open: the replan is written between tasks, not during one",
                ExitCode.PROJECT_WRITE_REFUSED,
            )
        case ReplanState.NO_FINISHED_TASK:
            raise ThanhTanError("no task is finished yet, so there is nothing to replan", ExitCode.INVALID_INPUT)
        case ReplanState.NOT_SEALED:
            raise ThanhTanError(
                f"task {status.task_id} is done but has no approval tag '{approval_tag(status.task_id or '')}'; "
                f"a person runs `thanhtan task seal {status.task_id}` first",
                ExitCode.TASK_NOT_SEALED,
            )
        case ReplanState.DONE:
            raise ThanhTanError(
                f"the replan of {status.task_id} is already done (a person confirmed it): it is not written again",
                ExitCode.INVALID_INPUT,
            )
    assert status.task_id is not None
    return status.task_id


def write_replan(workspace_dir: Path, state: State, git: GitClient, content: str) -> Path:
    """Save the replan of the latest finished task as a proposal. Changes no state and moves no roadmap item."""
    if not content.strip():
        raise ThanhTanError("the replan is empty", ExitCode.INVALID_INPUT)
    task_id = require_writable(replan_status(workspace_dir, state, git))
    found = read_roadmap(workspace_dir)
    codes = None if found is None else {item.code for item in items_of(workspace_dir)}
    text = normalize_newlines(content)
    problems = replan_problems(text, codes)
    if problems:
        raise ThanhTanError("the replan cannot be saved:\n- " + "\n- ".join(problems), ExitCode.REPORT_REFUSED)
    final = text if text.endswith("\n") else text + "\n"
    path = replan_path(workspace_dir, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        previous = path.read_text(encoding=ENCODING)
        if previous != final:
            keep_previous(workspace_dir, REPLAN_HISTORY_NAME.format(task_id=task_id), previous)
    skipped = skip_path(workspace_dir, task_id)
    if skipped.is_file():  # writing a replan after a skip takes the skip back; the record is kept
        keep_previous(workspace_dir, REPLAN_SKIP_HISTORY_NAME.format(task_id=task_id), skipped.read_text(encoding=ENCODING))
        skipped.unlink()
    write_text_atomic(path, final)
    set_summary_replan(workspace_dir, task_id, str(ReplanState.PROPOSED))
    return path


def confirm_replan(store: StateStore, workspace_dir: Path, git: GitClient, at: str) -> Task:
    """For a person: the proposed replan is done. Marks the task, updates the summary and forgets the removed items."""
    state = store.load()
    status = replan_status(workspace_dir, state, git)
    if status.state is not ReplanState.PROPOSED:
        raise ThanhTanError(
            f"the replan cannot be marked done: its state is {status.state}"
            + (f" (task {status.task_id})" if status.task_id else "")
            + _how_to_continue(status.state),
            ExitCode.INVALID_INPUT,
        )
    task = next(task for task in state.tasks if task.id == status.task_id)
    done = replace(task, replanned_at=at)
    store.save(replace(state, tasks=tuple(done if t.id == task.id else t for t in state.tasks)))
    set_summary_replan(workspace_dir, task.id, f"{ReplanState.DONE} ({at[:_DATE_CHARS]})")
    confirmations = Confirmations.load(workspace_dir)
    if confirmations.removed:
        confirmations.removed = []
        confirmations.save()
    return done


def skip_replan(store: StateStore, workspace_dir: Path, git: GitClient, task_id: str, reason: str, at: str) -> Path:
    """For a person: decide not to replan the latest finished task, and say why."""
    if not reason.strip():
        raise ThanhTanError("say why with --reason: a skipped replan is a decision", ExitCode.INVALID_INPUT)
    state = store.load()
    task = next((t for t in state.tasks if t.id == task_id), None)
    if task is None or task.status is not TaskStatus.DONE:
        raise ThanhTanError(f"{task_id} is not a finished task", ExitCode.INVALID_INPUT)
    status = replan_status(workspace_dir, state, git)
    if status.task_id != task_id or status.state not in {ReplanState.PENDING, ReplanState.PROPOSED}:
        raise ThanhTanError(
            f"the replan of {task_id} cannot be skipped: its state is {status.state}"
            + (f" (task {status.task_id})" if status.task_id and status.task_id != task_id else ""),
            ExitCode.INVALID_INPUT,
        )
    path = skip_path(workspace_dir, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        path,
        f"# Replan skipped: {task_id}\n\n- Task: {task_id}\n- Time: {at}\n- Reason: {reason.strip()}\n",
    )
    set_summary_replan(workspace_dir, task_id, f"{ReplanState.SKIPPED} ({at[:_DATE_CHARS]})")
    return path


def _how_to_continue(state: ReplanState) -> str:
    match state:
        case ReplanState.PENDING:
            return ": the scout writes the replan first (replan skill), then you read replan.md and run `thanhtan replan done`"
        case ReplanState.TASK_OPEN:
            return ": finish or cancel the open task first"
        case ReplanState.NOT_SEALED:
            return ": seal the task first (`thanhtan task seal <task>`)"
    return ""
