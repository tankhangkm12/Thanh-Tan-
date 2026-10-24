"""The plan a planner writes, and the checks that make it fit to build from.

A plan is Markdown. Each checklist item is a heading ``### C1 - <title>`` followed by bullets
``- role: ...``, ``- files: ...``, ``- done-when: ...`` and ``- docs: ...``.
"""

import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from agentflow.constants import (
    DEFAULT_PLAN_TIER,
    PLAN_ITEM_CODE_PATTERN,
    PLAN_NO_DOCS_PREFIX,
    PLAN_NO_FILES_PREFIX,
    PLAN_QUESTION_CODE_PATTERN,
    PLAN_QUESTIONS_HEADING,
    PlanField,
    PlanItemKind,
    PlanTier,
)
from agentflow.interfaces import PlanRule, PlanWideRule, RoleRegistry

_HEADING = re.compile(rf"^###\s+({PLAN_ITEM_CODE_PATTERN})\b\s*(?:[—–:-]+\s*)?(.*?)\s*$")
_QUESTION_HEADING = re.compile(rf"^###\s+({PLAN_QUESTION_CODE_PATTERN})\b\s*(?:[—–:-]+\s*)?(.*?)\s*$")
_SECTION_HEADING = re.compile(r"^##\s+(.*?)\s*$")
_ITEM_FIELDS = {PlanField.ROLE, PlanField.FILES, PlanField.DONE_WHEN, PlanField.DOCS, PlanField.KIND, PlanField.TIER, PlanField.LAYER}
_QUESTION_FIELDS = {PlanField.ASK, PlanField.OPTIONS, PlanField.NEEDED_BY}
_BAD_HEADING = re.compile(r"^###\s+(\S+)")
_FIELD = re.compile(r"^\s*[-*]\s+([A-Za-z-]+)\s*:\s*(.*?)\s*$")
_FIELD_NAMES = {field.value: field for field in PlanField}
_URL = re.compile(r"https?://\S+")
_REQUIREMENT = re.compile(r"^\s*[-*]\s+(Y\d+)\s*[:\-—–]")
_REASON_SEPARATOR = re.compile(r"^\s*[—–:-]+\s*(.+)$")
_FILE_SEPARATOR = re.compile(r"\s*,\s*")
_BACKTICKS = "`"
_CODE_FENCE = "```"
# An item that changes more entries than this is too big to review in one piece (a folder or a glob counts as one).
MAX_ITEM_FILES = 10


@dataclass(frozen=True)
class PlanItem:
    code: str
    title: str
    role: str | None = None
    # ``None`` when the item has no files line at all; empty tuple for "không có".
    files: tuple[str, ...] | None = None
    done_when: str | None = None
    # Raw docs value: URLs, or "không có — <reason>".
    docs: str | None = None
    # interface, implement or other (lower case); ``None`` when the item has no kind line.
    kind: str | None = None
    # fast or deep (lower case) as written; ``None`` when the item has no tier line, which counts as deep.
    tier: str | None = None
    # One of the layers a ``layer-order`` convention declares (lower case); ``None`` when the item has no layer line.
    layer: str | None = None
    # Codes of the confirm report's requirements (Y1, ...) this item fulfils.
    covers: tuple[str, ...] = ()

    @property
    def effective_tier(self) -> str:
        return self.tier or DEFAULT_PLAN_TIER

    @property
    def docs_links(self) -> tuple[str, ...]:
        return tuple(_URL.findall(self.docs or ""))


@dataclass(frozen=True)
class PlanQuestion:
    """A convention the project lacks, which the planner needs a person to decide."""

    code: str
    title: str
    ask: str | None = None
    options: str | None = None
    needed_by: str | None = None


@dataclass(frozen=True)
class Plan:
    items: tuple[PlanItem, ...]
    # Headings that start with ``###`` but are not a valid item code, kept to report them.
    bad_headings: tuple[str, ...] = ()
    questions: tuple[PlanQuestion, ...] = ()


@dataclass(frozen=True)
class PlanProblem:
    message: str
    code: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}" if self.code else self.message


def parse_plan(text: str) -> Plan:
    items: list[PlanItem] = []
    questions: list[PlanQuestion] = []
    bad: list[str] = []
    current: dict[str, object] | None = None
    asked: dict[str, str] | None = None
    in_questions = False
    in_fence = False

    def close() -> None:
        nonlocal asked
        if current is not None:
            items.append(PlanItem(**current))  # type: ignore[arg-type]
        if asked is not None:
            questions.append(PlanQuestion(**asked))  # type: ignore[arg-type]
            asked = None

    for line in text.replace("\r\n", "\n").split("\n"):
        if line.strip().startswith(_CODE_FENCE):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        section = _SECTION_HEADING.match(line)
        if section:
            close()
            current = None
            in_questions = section.group(1).strip().lower() == PLAN_QUESTIONS_HEADING.lower()
            continue
        if in_questions:
            question = _QUESTION_HEADING.match(line)
            if question:
                close()
                asked = {"code": question.group(1), "title": question.group(2)}
                continue
            field = _FIELD.match(line)
            if asked is not None and field and field.group(1).lower() in {f.value for f in _QUESTION_FIELDS}:
                asked[PlanField(field.group(1).lower()).name.lower()] = field.group(2)
            continue
        heading = _HEADING.match(line)
        if heading:
            close()
            current = {"code": heading.group(1), "title": heading.group(2)}
            continue
        loose = _BAD_HEADING.match(line)
        if loose:
            close()
            current = None
            bad.append(loose.group(1))
            continue
        field = _FIELD.match(line)
        if current is not None and field and field.group(1).lower() in _FIELD_NAMES:
            _store(current, _FIELD_NAMES[field.group(1).lower()], field.group(2))
    close()
    return Plan(tuple(items), tuple(bad), tuple(questions))


def _store(current: dict[str, object], field: PlanField, value: str) -> None:
    match field:
        case PlanField.ROLE:
            current["role"] = value.strip(_BACKTICKS).strip()
        case PlanField.FILES:
            current["files"] = _parse_files(value)
        case PlanField.DONE_WHEN:
            current["done_when"] = value
        case PlanField.DOCS:
            current["docs"] = value
        case PlanField.KIND:
            current["kind"] = value.strip(_BACKTICKS).strip().lower()
        case PlanField.TIER:
            current["tier"] = value.strip(_BACKTICKS).strip().lower()
        case PlanField.LAYER:
            current["layer"] = value.strip(_BACKTICKS).strip().lower()
        case PlanField.COVERS:
            current["covers"] = tuple(part.strip(_BACKTICKS + " ").upper() for part in _FILE_SEPARATOR.split(value) if part.strip(_BACKTICKS + " "))


def _parse_files(value: str) -> tuple[str, ...]:
    if value.lower().startswith(PLAN_NO_FILES_PREFIX):
        return ()
    parts = (part.strip().strip(_BACKTICKS).strip() for part in _FILE_SEPARATOR.split(value))
    return tuple(part for part in parts if part)


def docs_problem(docs: str | None) -> str | None:
    if docs is None or not docs.strip():
        return f"missing '{PlanField.DOCS}' (give a link, or '{PLAN_NO_DOCS_PREFIX} — <reason>')"
    if _URL.search(docs):
        return None
    if docs.lower().startswith(PLAN_NO_DOCS_PREFIX):
        reason = _REASON_SEPARATOR.match(docs[len(PLAN_NO_DOCS_PREFIX) :])
        if reason and reason.group(1).strip():
            return None
        return f"'{PlanField.DOCS}: {PLAN_NO_DOCS_PREFIX}' needs a reason after it"
    return f"'{PlanField.DOCS}' must be a link (http/https) or '{PLAN_NO_DOCS_PREFIX} — <reason>'"


def check_plan(
    plan: Plan,
    roles: RoleRegistry,
    rules: Sequence[PlanRule] = (),
    require_files: bool = False,
    wide_rules: Sequence[PlanWideRule] = (),
    answered_questions: Collection[str] | None = None,
    requirements: Collection[str] | None = None,
) -> list[PlanProblem]:
    """Every problem found, so the planner can fix them in one go. ``requirements`` are the codes of the confirm report."""
    problems: list[PlanProblem] = [PlanProblem(f"heading '### {name}' is not a valid item code (C1, C2, ...)") for name in plan.bad_headings]
    if not plan.items:
        problems.append(PlanProblem("the plan has no checklist items (### C1 - <title>)"))
    seen: set[str] = set()
    valid_roles = roles.roles()
    for item in plan.items:
        if item.code in seen:
            problems.append(PlanProblem("duplicate item code", item.code))
        seen.add(item.code)
        problems += _item_problems(item, valid_roles, require_files)
        for rule in rules:
            problems += (PlanProblem(message, item.code) for message in rule.problems(item))
    for wide in wide_rules:
        problems += (PlanProblem(message, code) for code, message in wide.problems(plan.items))
    problems += _question_problems(plan, answered_questions)
    problems += _requirement_problems(plan, requirements)
    return problems


def parse_requirements(text: str) -> tuple[str, ...]:
    """The requirement codes (``- Y1: ...``) a confirm report lists, in order."""
    return tuple(parse_requirement_texts(text))


def parse_requirement_texts(text: str) -> dict[str, str]:
    """The requirements (``- Y1: <text>``) a confirm report lists, code to text, in order; the first line of a code wins."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = _REQUIREMENT.match(line)
        if match and match.group(1) not in found:
            found[match.group(1)] = line[match.end() :].strip()
    return found


def _requirement_problems(plan: Plan, requirements: Collection[str] | None) -> list[PlanProblem]:
    """With requirements listed, each one needs an item that covers it, and an item may only cover a listed one."""
    if not requirements:
        return []
    covered = {code for item in plan.items for code in item.covers}
    found = [
        PlanProblem(f"requirement {code} is not covered by any plan item (add `covers: {code}` to the item that does it)")
        for code in requirements
        if code not in covered
    ]
    for item in plan.items:
        unknown = [code for code in item.covers if code not in requirements]
        if unknown:
            found.append(PlanProblem(f"covers {', '.join(unknown)}, which the confirm report does not list", item.code))
    return found


def _question_problems(plan: Plan, answered: Collection[str] | None) -> list[PlanProblem]:
    """A question needs to say what it asks, and (inside a task) a person's answer before the plan may pass."""
    found: list[PlanProblem] = []
    seen: set[str] = set()
    for question in plan.questions:
        if question.code in seen:
            found.append(PlanProblem("duplicate question code", question.code))
        seen.add(question.code)
        if not (question.ask or "").strip():
            found.append(PlanProblem(f"missing '{PlanField.ASK}' (say what the person must decide)", question.code))
        if answered is not None and question.code not in answered:
            found.append(
                PlanProblem(
                    f"no answer yet: a person answers with `agentflow decide --answer {question.code} --text \"...\" --check plan|semgrep|review`",
                    question.code,
                )
            )
    return found


def _item_problems(item: PlanItem, valid_roles: Iterable[str], require_files: bool) -> list[PlanProblem]:
    found: list[PlanProblem] = []
    if not item.role:
        found.append(PlanProblem(f"missing '{PlanField.ROLE}'", item.code))
    elif item.role not in valid_roles:
        found.append(PlanProblem(f"unknown role '{item.role}' (valid: {', '.join(sorted(valid_roles))})", item.code))
    if not item.done_when or not item.done_when.strip():
        found.append(PlanProblem(f"missing '{PlanField.DONE_WHEN}'", item.code))
    if (message := docs_problem(item.docs)) is not None:
        found.append(PlanProblem(message, item.code))
    if item.kind is not None and item.kind not in {kind.value for kind in PlanItemKind}:
        found.append(PlanProblem(f"unknown kind '{item.kind}' (one of: {', '.join(PlanItemKind)})", item.code))
    if item.tier is not None and item.tier not in {tier.value for tier in PlanTier}:
        found.append(PlanProblem(f"unknown tier '{item.tier}' (one of: {', '.join(PlanTier)}; no tier counts as {DEFAULT_PLAN_TIER})", item.code))
    if require_files and item.files is None:
        found.append(PlanProblem(f"missing '{PlanField.FILES}' (list the paths this item changes, or '{PLAN_NO_FILES_PREFIX}')", item.code))
    if item.files is not None and len(item.files) > MAX_ITEM_FILES:
        found.append(PlanProblem(f"lists {len(item.files)} files (the limit is {MAX_ITEM_FILES}): split it into smaller items, each easy to review", item.code))
    return found
