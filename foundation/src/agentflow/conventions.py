"""Conventions: rules a project or a person wants kept, in a Markdown file agentflow can read and rewrite.

Each convention is a heading ``### PC-01 - <title>`` followed by ``- key: value`` lines (``check``, ``rule``,
``status``, ``source``, ``description``, optional ``overrides``). Questions a scout could not settle go under
``## Câu hỏi mở`` as ``### S1 - <question>`` with ``- docs:`` and ``- code:`` lines.
"""

import re
from dataclasses import dataclass, replace
from pathlib import PurePath

from agentflow.constants import (
    OPEN_QUESTIONS_HEADING,
    SEMGREP_RULE_SUFFIXES,
    SETUP_QUESTION_PATTERN,
    LIST_SEPARATOR,
    CheckKind,
    ConventionField,
    ConventionPrefix,
    ConventionStatus,
    PlanRuleKind,
)

_HEADING = re.compile(r"^###\s+(\S+)\s*(?:[—–:-]+\s*)?(.*?)\s*$")
_FIELD = re.compile(r"^\s*[-*]\s+([A-Za-z-]+)\s*:\s*(.*?)\s*$")
_CODE_FENCE = "```"
_OVERRIDE_CODE = re.compile(rf"^({'|'.join(prefix.value for prefix in ConventionPrefix)})-\d{{2,}}$")
_QUESTION_CODE = re.compile(f"^{SETUP_QUESTION_PATTERN}$")
_FIELD_NAMES = {field.value for field in ConventionField}
# Keys of a parsed item that cannot clash with a field name (``code`` is a field of questions).
_ITEM_CODE, _ITEM_TITLE = "@code", "@title"


@dataclass(frozen=True)
class Convention:
    code: str
    title: str
    check: CheckKind | None = None
    rule: str | None = None
    status: ConventionStatus = ConventionStatus.UNCONFIRMED
    source: str | None = None
    description: str | None = None
    overrides: str | None = None
    # Parameters of a ``layer-order`` plan rule, as written (comma separated): the layers from first to last, and
    # the path globs that limit the rule (none: it covers the whole plan).
    layers: str | None = None
    scope: str | None = None

    @property
    def layer_names(self) -> tuple[str, ...]:
        return split_list(self.layers)

    @property
    def scope_globs(self) -> tuple[str, ...]:
        return split_list(self.scope, lower=False)

    def same_content(self, other: "Convention") -> bool:
        """Equal in everything but the status (what a person confirmed is the content, not the flag)."""
        return replace(self, status=other.status) == other


def split_list(value: str | None, lower: bool = True) -> tuple[str, ...]:
    """The items of a comma separated field, trimmed (layer names also lower-cased); empty ones dropped."""
    parts = ((part.strip().strip("`").strip()) for part in (value or "").split(LIST_SEPARATOR))
    return tuple((part.lower() if lower else part) for part in parts if part)


@dataclass(frozen=True)
class OpenQuestion:
    code: str
    title: str
    docs: str | None = None
    code_ref: str | None = None


@dataclass(frozen=True)
class ConventionDoc:
    conventions: tuple[Convention, ...] = ()
    questions: tuple[OpenQuestion, ...] = ()
    preamble: str = ""
    # Problems found while reading (bad headings, unknown values); validation adds the rest.
    problems: tuple[str, ...] = ()
    prefix: str = ConventionPrefix.PROJECT


def _code_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(prefix)}-\d{{2,}}$")


def parse_conventions(text: str, prefix: str = ConventionPrefix.PROJECT) -> ConventionDoc:
    """Read a conventions file. Never raises: what is wrong is listed in ``problems``."""
    wanted = _code_pattern(prefix)
    problems: list[str] = []
    preamble: list[str] = []
    conventions: list[Convention] = []
    questions: list[OpenQuestion] = []
    current: dict[str, str] | None = None
    current_is_question = False
    in_questions = False
    in_fence = False
    seen_heading = False

    def close() -> None:
        nonlocal current
        if current is None:
            return
        fields, current = current, None
        if current_is_question:
            questions.append(OpenQuestion(fields[_ITEM_CODE], fields[_ITEM_TITLE], fields.get("docs"), fields.get("code")))
        else:
            conventions.append(_convention(fields, problems))

    for line in text.replace("\r\n", "\n").split("\n"):
        if line.strip().startswith(_CODE_FENCE):
            in_fence = not in_fence
            if current is None and not seen_heading:
                preamble.append(line)
            continue
        if in_fence:
            if current is None and not seen_heading:
                preamble.append(line)
            continue
        if line.strip().lower() == OPEN_QUESTIONS_HEADING.lower():
            close()
            in_questions = True
            seen_heading = True
            continue
        heading = _HEADING.match(line)
        if heading:
            close()
            seen_heading = True
            code, title = heading.group(1), heading.group(2)
            valid = _QUESTION_CODE.match(code) if in_questions else wanted.match(code)
            if not valid:
                kind = "question" if in_questions else "convention"
                expected = SETUP_QUESTION_PATTERN if in_questions else f"{prefix}-NN"
                problems.append(f"'{code}' is not a valid {kind} code (expected {expected})")
                continue
            current = {_ITEM_CODE: code, _ITEM_TITLE: title}
            current_is_question = in_questions
            continue
        field = _FIELD.match(line)
        if current is not None and field and field.group(1).lower() in _FIELD_NAMES:
            current.setdefault(field.group(1).lower(), field.group(2))
        elif current is None and not seen_heading:
            preamble.append(line)
    close()
    return ConventionDoc(tuple(conventions), tuple(questions), "\n".join(preamble).strip("\n"), tuple(problems), prefix)


def _convention(fields: dict[str, str], problems: list[str]) -> Convention:
    code = fields[_ITEM_CODE]

    def enum(kind: type, key: str, default=None):
        raw = fields.get(key)
        if raw is None or raw == "":
            return default
        try:
            return kind(raw.strip().lower())
        except ValueError:
            allowed = ", ".join(item.value for item in kind)
            problems.append(f"{code}: '{key}: {raw}' is not one of: {allowed}")
            return default

    return Convention(
        code=code,
        title=fields[_ITEM_TITLE],
        check=enum(CheckKind, ConventionField.CHECK),
        rule=fields.get(ConventionField.RULE) or None,
        status=enum(ConventionStatus, ConventionField.STATUS, ConventionStatus.UNCONFIRMED),
        source=fields.get(ConventionField.SOURCE) or None,
        description=fields.get(ConventionField.DESCRIPTION) or None,
        overrides=fields.get(ConventionField.OVERRIDES) or None,
        layers=fields.get(ConventionField.LAYERS) or None,
        scope=fields.get(ConventionField.SCOPE) or None,
    )


def validate_conventions(doc: ConventionDoc) -> list[str]:
    """Every problem in the document, so an author can fix them in one go."""
    problems = list(doc.problems)
    seen: set[str] = set()
    for item in doc.conventions:
        if item.code in seen:
            problems.append(f"{item.code}: duplicate code")
        seen.add(item.code)
        problems += _item_problems(item)
    asked: set[str] = set()
    for question in doc.questions:
        if question.code in asked:
            problems.append(f"{question.code}: duplicate question code")
        asked.add(question.code)
        if not question.title:
            problems.append(f"{question.code}: the question is empty")
    return problems


def _item_problems(item: Convention) -> list[str]:
    found: list[str] = []
    if item.check is None:
        found.append(f"{item.code}: missing 'check' (one of: {', '.join(CheckKind)})")
    if not item.source:
        found.append(f"{item.code}: missing 'source' (a document line, or the code it was inferred from)")
    if not item.description:
        found.append(f"{item.code}: missing 'description'")
    if item.overrides and not _OVERRIDE_CODE.match(item.overrides):
        found.append(f"{item.code}: 'overrides: {item.overrides}' is not a convention code (PC-NN, DC-NN or KC-NN)")
    match item.check:
        case CheckKind.PLAN:
            if item.rule not in {kind.value for kind in PlanRuleKind}:
                found.append(f"{item.code}: a plan convention needs 'rule' to be one of: {', '.join(PlanRuleKind)}")
            found += _layer_problems(item)
        case CheckKind.SEMGREP:
            if not item.rule:
                found.append(f"{item.code}: a semgrep convention needs 'rule: <file>.yaml' (a rule file a person put in knowledge/semgrep/)")
            elif PurePath(item.rule).name != item.rule or "\\" in item.rule or not item.rule.endswith(SEMGREP_RULE_SUFFIXES):
                found.append(f"{item.code}: 'rule: {item.rule}' must be a plain file name ending in .yaml or .yml")
        case CheckKind.REVIEW:
            if item.rule:
                found.append(f"{item.code}: a review convention has no 'rule'")
    return found


def _layer_problems(item: Convention) -> list[str]:
    """``layers`` (and the optional ``scope``) belong to the ``layer-order`` rule, and it cannot work without layers."""
    found: list[str] = []
    if item.rule != PlanRuleKind.LAYER_ORDER:
        for key, value in ((ConventionField.LAYERS, item.layers), (ConventionField.SCOPE, item.scope)):
            if value:
                found.append(f"{item.code}: '{key}' belongs to rule {PlanRuleKind.LAYER_ORDER}, not {item.rule}")
        return found
    layers = item.layer_names
    if len(layers) < 2:
        found.append(f"{item.code}: rule {PlanRuleKind.LAYER_ORDER} needs 'layers: a, b, c' (at least two layers, first to last)")
    elif len(set(layers)) != len(layers):
        found.append(f"{item.code}: 'layers: {item.layers}' names a layer twice")
    if item.scope is not None and not item.scope_globs:
        found.append(f"{item.code}: 'scope' is empty (give path globs, or leave it out to cover the whole plan)")
    return found


def render_conventions(doc: ConventionDoc) -> str:
    """The document in its canonical form (what agentflow writes back)."""
    parts: list[str] = []
    if doc.preamble.strip():
        parts.append(doc.preamble.strip("\n") + "\n")
    for item in doc.conventions:
        lines = [f"### {item.code} - {item.title}"]
        for key, value in (
            (ConventionField.CHECK, item.check),
            (ConventionField.RULE, item.rule),
            (ConventionField.STATUS, item.status),
            (ConventionField.SOURCE, item.source),
            (ConventionField.DESCRIPTION, item.description),
            (ConventionField.OVERRIDES, item.overrides),
            (ConventionField.LAYERS, item.layers),
            (ConventionField.SCOPE, item.scope),
        ):
            if value:
                lines.append(f"- {key}: {value}")
        parts.append("\n".join(lines) + "\n")
    if doc.questions:
        block = [OPEN_QUESTIONS_HEADING + "\n"]
        for question in doc.questions:
            lines = [f"### {question.code} - {question.title}"]
            if question.docs:
                lines.append(f"- {ConventionField.DOCS}: {question.docs}")
            if question.code_ref:
                lines.append(f"- {ConventionField.CODE}: {question.code_ref}")
            block.append("\n".join(lines) + "\n")
        parts.append("\n".join(block))
    return "\n".join(parts)
