"""The approval checklist: a file a person ticks before ``task approve`` moves a step on.

``.ThanhTan/tasks/<task>/approve-<step>.md`` is written when a step passes into ``awaiting_approval``:

    # Duyệt bước <step> của <task>
    - task: T-001
    - step: confirm
    - report: tasks/T-001/reports/confirm.md
    - generated: 2026-10-18T10:00:00Z
    - skeleton-sha256: <hash of the items>

    ## Checklist
    - [ ] K1: a fixed question of the workflow
    - [ ] C1: a plan item
    - [ ] (tùy chọn) roadmap: Mục R1 đã hoàn thành?

    ## Ghi chú của bạn

The *skeleton* is the list of items (code, text, optional or not) without the boxes. ``task approve`` refuses when a
required box is open, when the skeleton or the header is not what agentflow wrote (it keeps the hashes in
``integrity.json``), or when the audit log shows a call that could have written the file.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from agentflow import audit, docpin
from agentflow.constants import (
    CHECKLIST_DOCS_PREFIX,
    CHECKLIST_DRIFT_PREFIX,
    CHECKLIST_FIXED_PREFIX,
    CHECKLIST_LOCK_PREFIX,
    CHECKLIST_HEADING,
    CHECKLIST_NOTES_HEADING,
    CHECKLIST_OPTIONAL_MARK,
    CHECKLIST_PLAN_PREFIX,
    CHECKLIST_ROADMAP_CODE,
    DECISIONS_DIR,
    ENCODING,
    MARKDOWN_SUFFIX,
    REPORTS_DIR,
    TASKS_DIR,
    ApprovalItem,
    CheckKind,
    ExitCode,
    RoadmapStatus,
    StepStatus,
    TaskStatus,
)
from agentflow.convention_sources import load_effective_conventions
from agentflow.drift import drift_section
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.gates import plan_report_path, requirement_texts_of
from agentflow.integrity import ACCEPT_HINT, Integrity, sha256_hex
from agentflow.models import Step, Task, Workflow
from agentflow import lockfiles, testspec
from agentflow.plan import parse_plan
from agentflow.roadmap import set_status

APPROVE_PREFIX = "approve-"
APPROVAL_DECISION_SUFFIX = "-approval"
_ITEM = re.compile(r"^- \[(?P<box>[ xX])\] (?P<opt>\(tùy chọn\) )?(?P<code>[A-Za-z][\w\-]*): (?P<text>.+?)\s*$")
_HEADER = re.compile(r"^- (?P<key>[a-z0-9\-]+): (?P<value>.*?)\s*$")
_HEADER_KEYS = ("task", "step", "report", "generated")
_SKELETON_KEY = "skeleton-sha256"
_NONE_WORDS = frozenset({"không có", "khong co", "none"})
_BULLET = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")


@dataclass(frozen=True)
class Item:
    code: str
    text: str
    optional: bool = False
    ticked: bool = False

    def line(self) -> str:
        mark = f"{CHECKLIST_OPTIONAL_MARK} " if self.optional else ""
        return f"- [{'x' if self.ticked else ' '}] {mark}{self.code}: {self.text}"


@dataclass(frozen=True)
class Parsed:
    header: dict[str, str]
    items: tuple[Item, ...]
    notes: str


@dataclass(frozen=True)
class Approval:
    """What a successful check found: the note and the roadmap box, to be recorded once the step has moved on."""

    task_id: str
    step_id: str
    text: str
    note: str
    roadmap_done: bool


def checklist_path(workspace_dir: Path, task_id: str, step_id: str, round_: int | None = None) -> Path:
    name = f"{APPROVE_PREFIX}{step_id}{MARKDOWN_SUFFIX}" if round_ is None else f"{APPROVE_PREFIX}{step_id}.{round_}{MARKDOWN_SUFFIX}"
    return workspace_dir / TASKS_DIR / task_id / name


def _key(task_id: str, step_id: str) -> str:
    return f"{task_id}/{step_id}"


# ------------------------------------------------------------------ reading a file


def _normal(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse(text: str) -> Parsed:
    """The header, the items of the ``## Checklist`` section and the notes. Item-like lines elsewhere are ignored."""
    header: dict[str, str] = {}
    items: list[Item] = []
    notes: list[str] = []
    section = "header"
    for line in _normal(text).split("\n"):
        if line.startswith("## "):
            title = line[3:].strip()
            section = "items" if title == CHECKLIST_HEADING else "notes" if title == CHECKLIST_NOTES_HEADING else "other"
            continue
        if section == "header":
            found = _HEADER.match(line)
            if found:
                header.setdefault(found["key"], found["value"])
        elif section == "items":
            found = _ITEM.match(line)
            if found:
                items.append(Item(found["code"], found["text"], bool(found["opt"]), found["box"] != " "))
        elif section == "notes":
            notes.append(line)
    return Parsed(header, tuple(items), "\n".join(notes).strip())


def _skeleton(items: tuple[Item, ...]) -> str:
    return sha256_hex("\n".join(f"{'?' if i.optional else '!'}|{i.code}|{i.text}" for i in items).encode(ENCODING))


def skeleton_sha256(text: str) -> str:
    """The hash of the items of a checklist, whatever its boxes, line endings or notes."""
    return _skeleton(parse(text).items)


def _header_sha256(header: dict[str, str]) -> str:
    return sha256_hex("\n".join(f"{key}={header.get(key, '')}" for key in _HEADER_KEYS).encode(ENCODING))


# ------------------------------------------------------------------ writing a file


def _fixed(step: Step) -> list[Item]:
    return [Item(f"{CHECKLIST_FIXED_PREFIX}{n}", question) for n, question in enumerate(step.approval_checklist, 1)]


def _plan_items(workspace_dir: Path, task: Task, step: Step) -> list[Item]:
    path = plan_report_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        return []
    found = []
    for item in parse_plan(path.read_text(encoding=ENCODING)).items:
        done = f" (done-when: {item.done_when})" if item.done_when else ""
        found.append(Item(f"{CHECKLIST_PLAN_PREFIX}{item.code.removeprefix(CHECKLIST_PLAN_PREFIX)}", f"{item.title}{done}"))
    return found


def _review_conventions(workspace_dir: Path) -> list[Item]:
    wanted = load_effective_conventions(workspace_dir).checked_by(CheckKind.REVIEW)
    return [Item(c.convention.code, f"{c.convention.title}: the review answers it with a line `{c.convention.code}: đạt` or the place of the violation") for c in wanted]


def _drift_proposals(workspace_dir: Path, task: Task, step: Step) -> list[Item]:
    path = plan_report_path(workspace_dir, task.id, step.id)
    section = drift_section(path.read_text(encoding=ENCODING)) if path.is_file() else None
    if section is None or section.strip().rstrip(".").strip().lower() in _NONE_WORDS:
        return []
    bullets = [m["text"] for m in map(_BULLET.match, section.split("\n")) if m]
    return [Item(f"{CHECKLIST_DRIFT_PREFIX}{n}", f"Đề xuất: {text}") for n, text in enumerate(bullets, 1)]


def _spec_items(workspace_dir: Path, workflow: Workflow, task: Task, step: Step) -> list[Item]:
    """One line per plan item: the tests, the command and what agentflow saw when it ran it (``verify-red.json``)."""
    path = testspec.report_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        return []
    try:
        results = json.loads(testspec.task_file(workspace_dir, task.id, testspec.VERIFY_RED_FILE).read_text(encoding=ENCODING))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        results = {}
    found = []
    for block in testspec.parse_report(path.read_text(encoding=ENCODING)):
        if block.is_none:
            found.append(Item(block.code, f"{testspec.NONE_WORD} — {block.how}"))
            continue
        seen = results.get(block.code, {})
        outcome = f"agentflow ran it: exit {seen.get('exit_code', '?')} ({seen.get('status', 'not run')})"
        found.append(Item(block.code, f"tests {', '.join(block.tests)}; command `{block.command}`; {outcome}"))
    return found


def _locked_files(workspace_dir: Path, task: Task, step: Step) -> list[Item]:
    """One line per file that will be locked when this step is approved (the same plan the approval will carry out)."""
    path = testspec.report_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        return []
    text = path.read_text(encoding=ENCODING)
    blocks = testspec.parse_report(text)
    plan = lockfiles.build_plan(workspace_dir.parent, [file for block in blocks for file in block.files], lockfiles.declared_infra(text))
    found = []
    for number, (name, entry) in enumerate(plan.entries.items(), 1):
        scope = f", only its test settings ({entry['part']})" if entry["scope"] == lockfiles.SCOPE_PART else ""
        found.append(Item(f"{CHECKLIST_LOCK_PREFIX}{number}", f"{name} ({entry['kind']}{scope}) will be locked"))
    return found


def _review_requirements(workspace_dir: Path, workflow: Workflow, task: Task) -> list[Item]:
    """One line per requirement of the confirm report: the person checks the work meets it (the review gives a verdict)."""
    texts = requirement_texts_of(workspace_dir, task.id, workflow.steps[0].id)
    return [Item(code, f"{text} (the review says `{code}: đạt` and where)") for code, text in texts.items()]


_DOC_CHANGE_TEXT = {
    docpin.CHANGED: "changed",
    docpin.MISSING: "is gone",
    docpin.APPEARED: "did not exist then and does now",
}


def _changed_docs(workspace_dir: Path, task: Task) -> list[Item]:
    """One line per pinned document that is not as it was when a person approved the step that named it."""
    return [
        Item(
            f"{CHECKLIST_DOCS_PREFIX}{number}",
            f"{change.path} {_DOC_CHANGE_TEXT[change.kind]} since you approved the task: the work follows the version you want",
        )
        for number, change in enumerate(docpin.changes(workspace_dir, workspace_dir.parent, task.id), 1)
    ]


def build_items(workspace_dir: Path, workflow: Workflow, task: Task, step: Step) -> list[Item]:
    items = _fixed(step)
    for source in step.approval_items:
        match source:
            case ApprovalItem.PLAN_ITEMS:
                items += _plan_items(workspace_dir, task, step)
            case ApprovalItem.REVIEW_CONVENTIONS:
                items += _review_conventions(workspace_dir)
            case ApprovalItem.DRIFT_PROPOSALS:
                items += _drift_proposals(workspace_dir, task, step)
            case ApprovalItem.SPEC_ITEMS:
                items += _spec_items(workspace_dir, workflow, task, step)
            case ApprovalItem.LOCKED_FILES:
                items += _locked_files(workspace_dir, task, step)
            case ApprovalItem.REVIEW_REQUIREMENTS:
                items += _review_requirements(workspace_dir, workflow, task)
            case ApprovalItem.CHANGED_DOCS:
                items += _changed_docs(workspace_dir, task)
    if task.roadmap and workflow.steps[-1].id == step.id:
        items.append(Item(CHECKLIST_ROADMAP_CODE, f"Mục {task.roadmap} đã hoàn thành?", optional=True))
    return items


def render(task: Task, step: Step, items: list[Item], generated: str) -> tuple[str, dict[str, str]]:
    """The text of a new checklist and the record ``integrity.json`` keeps of it."""
    skeleton = _skeleton(tuple(items))
    header = {
        "task": task.id,
        "step": step.id,
        "report": f"{TASKS_DIR}/{task.id}/{REPORTS_DIR}/{step.id}{MARKDOWN_SUFFIX}",
        "generated": generated,
    }
    lines = [
        f"# Duyệt bước {step.id} của {task.id}",
        "",
        *[f"- {key}: {header[key]}" for key in _HEADER_KEYS],
        f"- {_SKELETON_KEY}: {skeleton}",
        "",
        f"## {CHECKLIST_HEADING}",
        "",
        "Tick a box with an x: `- [x]`. Do not add, delete or reword a line.",
        "",
        *[item.line() for item in items],
        "",
        f"## {CHECKLIST_NOTES_HEADING}",
        "",
    ]
    return "\n".join(lines), {"skeleton_sha256": skeleton, "header_sha256": _header_sha256(header), "generated": generated}


class ChecklistWriter:
    """Writes the checklist of a step that has just passed into ``awaiting_approval``."""

    def __init__(self, workspace_dir: Path) -> None:
        self.dir = workspace_dir

    def write(self, workflow: Workflow, after: Task) -> Path | None:
        step = workflow.get_step(after.current_step)
        if step is None or not step.has_checklist or after.step_status is not StepStatus.AWAITING_APPROVAL:
            return None
        text, record = render(after, step, build_items(self.dir, workflow, after, step), after.history[-1].at)
        path = checklist_path(self.dir, after.id, step.id)
        fresh = path.with_name(path.name + ".new")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(fresh, text)
            if path.exists():
                number = 1
                while checklist_path(self.dir, after.id, step.id, number).exists():
                    number += 1
                os.replace(path, checklist_path(self.dir, after.id, step.id, number))
            os.replace(fresh, path)
            Integrity(self.dir).set_checklist(_key(after.id, step.id), record)
        except OSError as exc:
            fresh.unlink(missing_ok=True)
            raise AgentflowError(f"cannot write the approval checklist {path.name}: {exc}", ExitCode.CHECKLIST_REFUSED) from exc
        return path


# ------------------------------------------------------------------ approving


def check_approval(workspace_dir: Path, workflow: Workflow, task: Task) -> Approval | None:
    """Raise unless the person has ticked the checklist of the step ``task`` waits at; ``None`` when that step has none."""
    step = workflow.get_step(task.current_step)
    if step is None or not step.has_checklist:
        return None
    if task.status is not TaskStatus.OPEN or task.step_status is not StepStatus.AWAITING_APPROVAL:
        return None
    path = checklist_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        raise _refused(f"the checklist {path.name} of step '{step.id}' is missing: tick it in {path}")
    text = _normal(path.read_bytes().decode(ENCODING))
    parsed = parse(text)
    _require_unchanged(workspace_dir, task, step, parsed, path)
    open_codes = [i.code for i in parsed.items if not i.optional and not i.ticked]
    if open_codes:
        raise _refused(f"{path.name}: tick these first: {', '.join(open_codes)} (open the file, write x in the boxes)")
    integrity = Integrity(workspace_dir)
    blocking = audit.evidence(workspace_dir, parsed.header.get("generated"), integrity.accepted_at(), step.id)
    if blocking:
        quoted = "; ".join(f"{e.at} {e.tool}: {e.target}" for e in blocking[:3])
        raise AgentflowError(
            f"the audit log shows a call that could have written {path.name} or the state: {quoted}. {ACCEPT_HINT}",
            ExitCode.INTEGRITY_FAILED,
        )
    ticked_roadmap = any(i.code == CHECKLIST_ROADMAP_CODE and i.optional and i.ticked for i in parsed.items)
    return Approval(task.id, step.id, text, parsed.notes, ticked_roadmap)


def _require_unchanged(workspace_dir: Path, task: Task, step: Step, parsed: Parsed, path: Path) -> None:
    problems = []
    if parsed.header.get("task") != task.id or parsed.header.get("step") != step.id:
        problems.append("its header names another task or step")
    skeleton = _skeleton(parsed.items)
    if parsed.header.get(_SKELETON_KEY) != skeleton:
        problems.append("its items are not the ones agentflow wrote (a line was added, deleted or reworded)")
    record = Integrity(workspace_dir).checklist(_key(task.id, step.id))
    if record is not None:
        if record.get("skeleton_sha256") != skeleton:
            problems.append("its items do not match the hash agentflow keeps in integrity.json")
        if record.get("header_sha256") != _header_sha256(parsed.header):
            problems.append("its header was changed")
    if problems:
        raise _refused(f"{path.name} was changed: " + "; ".join(problems) + ". Ask for a new one by sending the step back (`agentflow task advance --result fail`)")


def finish_approval(workspace_dir: Path, approval: Approval, task: Task, workflow: Workflow, at: str) -> Path | None:
    """After the step has moved on: keep the person's note with a copy of the checklist, and close the roadmap item."""
    if approval.roadmap_done and task.roadmap:
        set_status(workspace_dir, task.roadmap, RoadmapStatus.DONE)
    if not approval.note.strip():
        return None
    base = f"{approval.task_id}-{approval.step_id}{APPROVAL_DECISION_SUFFIX}"
    path = workspace_dir / DECISIONS_DIR / f"{base}{MARKDOWN_SUFFIX}"
    number = 1
    while path.exists():
        number += 1
        path = workspace_dir / DECISIONS_DIR / f"{base}-{number}{MARKDOWN_SUFFIX}"
    body = [
        f"# {approval.task_id}: approval of step {approval.step_id}",
        "",
        f"- Time: {at}",
        "",
        "## Note",
        "",
        approval.note.strip(),
        "",
        "## Checklist as approved",
        "",
        "```markdown",
        approval.text.rstrip("\n"),
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, "\n".join(body) + "\n")
    return path


def _refused(message: str) -> AgentflowError:
    return AgentflowError(message, ExitCode.CHECKLIST_REFUSED)
