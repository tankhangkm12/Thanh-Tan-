"""The ``## Đề xuất cập nhật hồ sơ`` section of a review report: does the change make a project document wrong?

The reviewer only proposes. This module checks the form of the section (it exists once, and holds either
``không có`` or bullets ``- <document>: <proposal>``); whether a proposal is right is for the person to judge.
"""

import re

from agentflow.constants import DRIFT_HEADING, DRIFT_NONE_TEXT, DriftDoc

_HEADING = re.compile(rf"^##[ \t]+{re.escape(DRIFT_HEADING)}[ \t]*$")
_ANY_TOP_HEADING = re.compile(r"^#{1,2}[ \t]+\S")
_NONE = re.compile(rf"^{re.escape(DRIFT_NONE_TEXT)}\.?$", re.IGNORECASE)
_BULLET = re.compile(r"^-[ \t]+([A-Za-z][\w-]*)[ \t]*:[ \t]*(.*?)[ \t]*$")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_CRLF = "\r\n"
_LF = "\n"
_TAB_STOP = 4
# Markdown (CommonMark): up to three columns of indentation are still markup, four or more make a code block.
_MAX_MARKUP_INDENT = 3
_PREFIX = f'the "## {DRIFT_HEADING}" section'


def _split_indent(line: str) -> tuple[int, str]:
    """Columns of leading white space (a tab goes to the next multiple of four) and the rest of the line."""
    columns = 0
    for position, char in enumerate(line):
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += _TAB_STOP - columns % _TAB_STOP
        else:
            return columns, line[position:]
    return columns, ""


def _markup(line: str) -> str | None:
    """The line without its indentation, or ``None`` when it is indented so far that it is code."""
    columns, rest = _split_indent(line)
    return rest if columns <= _MAX_MARKUP_INDENT else None


def _is(pattern: re.Pattern[str], line: str) -> bool:
    marked = _markup(line)
    return marked is not None and pattern.match(marked) is not None


def _visible_lines(text: str) -> list[str]:
    """Lines of the report outside HTML comments and fenced code blocks (neither counts as report content).

    A fence opens with three or more backticks or tildes and closes with the same character, at least as many
    of them and nothing else on the line; an unclosed fence runs to the end of the report.
    """
    lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in _HTML_COMMENT.sub("", text.replace(_CRLF, _LF)).split(_LF):
        marked = _markup(line)
        found = _FENCE.match(marked) if marked is not None else None
        if fence is not None:
            if found and found.group(1)[0] == fence[0] and len(found.group(1)) >= fence[1] and not found.group(2).strip():
                fence = None
            continue
        if found and not (found.group(1)[0] == "`" and "`" in found.group(2)):
            fence = (found.group(1)[0], len(found.group(1)))
            continue
        lines.append(line)
    return lines


def drift_problems(text: str) -> list[str]:
    """Problems with the section; empty when it is well formed."""
    lines = _visible_lines(text)
    starts = [number for number, line in enumerate(lines) if _is(_HEADING, line)]
    if not starts:
        return [f"the report has no {_PREFIX}: write `{DRIFT_NONE_TEXT}`, or one `- <document>: <proposal>` per project document to change"]
    if len(starts) > 1:
        return [f"the report has {_PREFIX} {len(starts)} times: keep one"]
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if _is(_ANY_TOP_HEADING, line):
            break
        body.append(line)
    entries = [line for line in body if line.strip()]
    if not entries:
        return [f"{_PREFIX} is empty: write `{DRIFT_NONE_TEXT}`, or the proposals"]
    return _entry_problems(entries)


def _entry_problems(entries: list[str]) -> list[str]:
    problems: list[str] = []
    none_seen = False
    bullets = 0
    allowed = ", ".join(f"`{doc}`" for doc in DriftDoc)
    previous_was_bullet = False
    for line in entries:
        stripped = line.strip()
        if _NONE.match(stripped):
            none_seen = True
            previous_was_bullet = False
            continue
        bullet = _BULLET.match(line) if not line[:1].isspace() else None
        if bullet is not None:
            bullets += 1
            previous_was_bullet = True
            document, proposal = bullet.group(1), bullet.group(2)
            if document.lower() not in set(DriftDoc):
                problems.append(f"{_PREFIX} names '{document}', which is not a project document ({allowed})")
            elif not proposal:
                problems.append(f"{_PREFIX}: the proposal for '{document}' is empty")
            continue
        if line[:1].isspace() and previous_was_bullet:
            continue  # a continuation of the previous proposal
        previous_was_bullet = False
        problems.append(f"{_PREFIX} has a line that is neither `{DRIFT_NONE_TEXT}` nor `- <document>: <proposal>`: {stripped[:60]}")
    if none_seen and bullets:
        problems.append(f"{_PREFIX} says `{DRIFT_NONE_TEXT}` and also lists proposals: keep one of the two")
    return problems
