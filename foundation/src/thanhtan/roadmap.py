"""``.ThanhTan/project/roadmap.md``: the project's goals, R1, R2, ... in order of priority.

    ### R1 - Short title
    - status: todo            # todo | doing | done | dropped
    - goal: one line
    - docs: https://... | path/to/file.md:12 | không có — reason

An agent proposes the list (through the ``project_write`` tool); only a person confirms an item or moves it to a status
of their choosing. What an agent may change is decided in ``merge_agent_roadmap``.
"""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from thanhtan.confirmations import Confirmations, project_path
from thanhtan.constants import (
    ENCODING,
    MARKDOWN_SUFFIX,
    ROADMAP_FILE_STEM,
    ROADMAP_ITEM_PATTERN,
    ExitCode,
    RoadmapField,
    RoadmapStatus,
)
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic
from thanhtan.mdutil import normalize_newlines

ROADMAP_FILE = f"{ROADMAP_FILE_STEM}{MARKDOWN_SUFFIX}"
_ITEM = re.compile(rf"^###\s+({ROADMAP_ITEM_PATTERN})\b\s*(?:[—–:-]+\s*)?(.*?)\s*$")
_ANY_ITEM_HEADING = re.compile(r"^###\s+(\S+)")
_FIELD = re.compile(r"^\s*[-*]\s+([A-Za-z-]+)\s*:\s*(.*?)\s*$")
_CODE = re.compile(rf"^{ROADMAP_ITEM_PATTERN}$")
_URL = re.compile(r"https?://\S+")
_FILE_LINE = re.compile(r"[\w./\\-]+:\d+")
_NO_DOCS = re.compile(r"^không có\s*[—–-]\s*\S")
_FIELDS = {field.value: field for field in RoadmapField}
_STATUSES = frozenset(status.value for status in RoadmapStatus)


@dataclass(frozen=True)
class RoadmapItem:
    code: str
    title: str
    status: RoadmapStatus
    goal: str
    docs: str

    @property
    def content(self) -> str:
        """What a person confirms: everything but the status, which thanhtan and people move without unconfirming."""
        return f"{self.code}\n{self.title}\n{self.goal}\n{self.docs}"

    @property
    def label(self) -> str:
        return f"{self.code} - {self.title}"


@dataclass(frozen=True)
class ParsedItem:
    code: str
    title: str
    given_status: str | None
    goal: str
    docs: str


@dataclass(frozen=True)
class RoadmapDoc:
    preface: str
    items: tuple[ParsedItem, ...]
    problems: tuple[str, ...]


def parse_roadmap(text: str) -> RoadmapDoc:
    """Read a roadmap; ``problems`` lists everything that breaks the format, and each problem names its item."""
    preface: list[str] = []
    items: list[ParsedItem] = []
    problems: list[str] = []
    seen: set[str] = set()
    heading: tuple[str, str] | None = None
    block: list[str] | None = None

    def close() -> None:
        if heading is None or block is None:
            return
        item, found = _read_item(heading[0], heading[1], block)
        problems.extend(found)
        if heading[0] in seen:
            problems.append(f"{heading[0]} appears more than once")
        seen.add(heading[0])
        items.append(item)

    for line in normalize_newlines(text).split("\n"):
        match = _ITEM.match(line)
        if match is not None:
            close()
            heading, block = (match.group(1), match.group(2)), []
            continue
        other = _ANY_ITEM_HEADING.match(line)
        if other is not None:
            close()
            heading, block = None, None
            problems.append(f"'{other.group(1)}' is not a roadmap item heading (### R1 - title: the code is R and digits)")
            continue
        (preface if block is None else block).append(line)
    close()
    if not items and not problems:
        problems.append("the roadmap has no items (### R1 - title)")
    return RoadmapDoc("\n".join(preface).strip(), tuple(items), tuple(problems))


def _read_item(code: str, title: str, lines: Sequence[str]) -> tuple[ParsedItem, list[str]]:
    problems: list[str] = []
    values: dict[str, str] = {}
    if not title:
        problems.append(f"{code} has no title (### {code} - title)")
    for line in lines:
        if not line.strip():
            continue
        field = _FIELD.match(line)
        if field is None:
            problems.append(f"{code}: unexpected line '{line.strip()[:50]}' (an item holds only - status:, - goal: and - docs:)")
        elif field.group(1) not in _FIELDS:
            problems.append(f"{code}: unknown field '{field.group(1)}' (use {', '.join(_FIELDS)})")
        elif field.group(1) in values:
            problems.append(f"{code}: field '{field.group(1)}' appears twice")
        else:
            values[field.group(1)] = field.group(2)
    status = values.get(RoadmapField.STATUS)
    if status is not None and status not in _STATUSES:
        problems.append(f"{code}: unknown status '{status}' (use {', '.join(RoadmapStatus)})")
    if not values.get(RoadmapField.GOAL):
        problems.append(f"{code} needs a goal (- goal: one line)")
    docs = values.get(RoadmapField.DOCS, "")
    if not docs:
        problems.append(f"{code} needs docs (- docs: a link, file:line, or 'không có — reason')")
    elif not (_URL.search(docs) or _FILE_LINE.search(docs) or _NO_DOCS.match(docs)):
        problems.append(f"{code}: docs '{docs[:40]}' is neither a link, a file:line nor 'không có — reason'")
    return ParsedItem(code, title, status, values.get(RoadmapField.GOAL, ""), docs), problems


def render_roadmap(preface: str, items: Sequence[RoadmapItem]) -> str:
    blocks = [
        f"### {item.code} - {item.title}\n- {RoadmapField.STATUS}: {item.status}\n"
        f"- {RoadmapField.GOAL}: {item.goal}\n- {RoadmapField.DOCS}: {item.docs}\n"
        for item in items
    ]
    head = f"{preface}\n\n" if preface else ""
    return head + "\n".join(blocks)


# -------------------------------------------------------------------- the file


def roadmap_path(workspace_dir: Path) -> Path:
    return project_path(workspace_dir, ROADMAP_FILE)


def read_roadmap(workspace_dir: Path) -> tuple[str, list[RoadmapItem]] | None:
    """Preface and items of the stored roadmap, or ``None`` when there is none. Reads leniently."""
    path = roadmap_path(workspace_dir)
    if not path.is_file():
        return None
    doc = parse_roadmap(path.read_text(encoding=ENCODING))
    items = [
        RoadmapItem(
            item.code,
            item.title,
            RoadmapStatus(item.given_status) if item.given_status in _STATUSES else RoadmapStatus.TODO,
            item.goal,
            item.docs,
        )
        for item in doc.items
    ]
    return doc.preface, items


def write_roadmap(workspace_dir: Path, preface: str, items: Sequence[RoadmapItem]) -> None:
    path = roadmap_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, render_roadmap(preface, items))


def items_of(workspace_dir: Path) -> list[RoadmapItem]:
    found = read_roadmap(workspace_dir)
    return found[1] if found else []


def find_item(items: Sequence[RoadmapItem], code: str) -> RoadmapItem | None:
    return next((item for item in items if item.code == code), None)


def _unknown(code: str, items: Sequence[RoadmapItem]) -> str:
    return f"no roadmap item {code} (items: {', '.join(i.code for i in items) or 'none'})"


def set_status(workspace_dir: Path, code: str, status: RoadmapStatus) -> RoadmapStatus:
    """For a person (or for thanhtan when a task is tied to the item): move one item; returns the status it had."""
    found = read_roadmap(workspace_dir)
    if found is None:
        raise ThanhTanError("this project has no roadmap yet (the setup skill proposes one)", ExitCode.INVALID_INPUT)
    preface, items = found
    item = find_item(items, code)
    if item is None:
        raise ThanhTanError(_unknown(code, items), ExitCode.INVALID_INPUT)
    write_roadmap(workspace_dir, preface, [replace(i, status=status) if i.code == code else i for i in items])
    return item.status


# ---------------------------------------------------------- what an agent may do


@dataclass(frozen=True)
class AgentRoadmap:
    preface: str
    items: tuple[RoadmapItem, ...]
    warnings: tuple[str, ...]
    # Confirmed items that are gone from the new roadmap, and the codes put back after an earlier removal.
    removed_confirmed: tuple[str, ...]
    returned: tuple[str, ...]


def merge_agent_roadmap(text: str, workspace_dir: Path, confirmations: Confirmations) -> AgentRoadmap:
    """The roadmap an agent proposed, brought to the rules: an agent cannot set a status, confirm anything or drop an
    item that has moved on. Raises ``ROADMAP_INVALID`` for a broken format and ``PROJECT_WRITE_REFUSED`` for a removal."""
    doc = parse_roadmap(text)
    if doc.problems:
        raise ThanhTanError("the roadmap is not valid:\n- " + "\n- ".join(doc.problems), ExitCode.ROADMAP_INVALID)
    previous = items_of(workspace_dir)
    before = {item.code: item for item in previous}
    warnings: list[str] = []
    items: list[RoadmapItem] = []
    for parsed in doc.items:
        old = before.get(parsed.code)
        status = old.status if old is not None else RoadmapStatus.TODO
        if parsed.given_status is not None and parsed.given_status != status:
            warnings.append(f"{parsed.code}: status stays '{status}' (an agent cannot set it; a person runs `thanhtan roadmap set`)")
        items.append(RoadmapItem(parsed.code, parsed.title, status, parsed.goal, parsed.docs))
    kept = {item.code for item in items}
    gone = [item for item in previous if item.code not in kept]
    moved_on = [item.code for item in gone if item.status is not RoadmapStatus.TODO]
    if moved_on:
        raise ThanhTanError(
            f"{', '.join(moved_on)} cannot be left out of the roadmap: only items that are still todo can be "
            "(a person changes the others with `thanhtan roadmap set`)",
            ExitCode.PROJECT_WRITE_REFUSED,
        )
    removed = [item.code for item in gone if confirmations.is_confirmed(item.code, item.content)]
    warnings += [f"{code} was confirmed and is removed from the roadmap (the previous roadmap is kept in history/)" for code in removed]
    returned = tuple(item.code for item in items if item.code in confirmations.removed)
    return AgentRoadmap(doc.preface, tuple(items), tuple(warnings), tuple(removed), returned)


# ------------------------------------------------------------------- reading it


def unconfirmed_codes(items: Sequence[RoadmapItem], confirmations: Confirmations) -> list[str]:
    return [item.code for item in items if not confirmations.is_confirmed(item.code, item.content)]


def next_item(items: Sequence[RoadmapItem], busy: Collection[str]) -> RoadmapItem | None:
    """The item to take up next: one that is doing and has no open task, else the first todo, in file order."""
    for wanted in (RoadmapStatus.DOING, RoadmapStatus.TODO):
        for item in items:
            if item.status is wanted and item.code not in busy:
                return item
    return None


def describe(item: RoadmapItem, confirmations: Confirmations) -> str:
    return item.label if confirmations.is_confirmed(item.code, item.content) else f"{item.label} (unconfirmed)"


def is_code(value: str) -> bool:
    return bool(_CODE.match(value))


def require_linkable(workspace_dir: Path, code: str) -> RoadmapItem:
    """The item a new task may be tied to; raises ``INVALID_INPUT`` (with what to do) otherwise."""
    if not is_code(code):
        raise ThanhTanError(f"'{code}' is not a roadmap item code (R and digits, for example R3)", ExitCode.INVALID_INPUT)
    found = read_roadmap(workspace_dir)
    if found is None:
        raise ThanhTanError(
            f"this project has no roadmap yet, so the task cannot be tied to {code} (the setup skill proposes one)", ExitCode.INVALID_INPUT
        )
    item = find_item(found[1], code)
    if item is None:
        raise ThanhTanError(_unknown(code, found[1]), ExitCode.INVALID_INPUT)
    if item.status in (RoadmapStatus.DONE, RoadmapStatus.DROPPED):
        raise ThanhTanError(
            f"roadmap item {code} is {item.status}: a person reopens it with `thanhtan roadmap set {code} doing`", ExitCode.INVALID_INPUT
        )
    return item
