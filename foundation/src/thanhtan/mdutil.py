"""Markdown rules shared by the parts that read reports and project documents.

Follows CommonMark where it matters here: up to three columns of indentation are still markup and four or more make a
code block, a fence closes with the same character and at least as many of them, and an unclosed fence runs to the end.
"""

import re

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_TOP_HEADING = re.compile(r"^#{1,2}[ \t]+\S")
_CRLF = "\r\n"
LF = "\n"
_TAB_STOP = 4
_MAX_MARKUP_INDENT = 3


def normalize_newlines(text: str) -> str:
    return text.replace(_CRLF, LF)


def split_indent(line: str) -> tuple[int, str]:
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


def markup(line: str) -> str | None:
    """The line without its indentation, or ``None`` when it is indented so far that it is code."""
    columns, rest = split_indent(line)
    return rest if columns <= _MAX_MARKUP_INDENT else None


def matches(pattern: re.Pattern[str], line: str) -> bool:
    marked = markup(line)
    return marked is not None and pattern.match(marked) is not None


def is_top_heading(line: str) -> bool:
    """A level 1 or 2 heading, which ends a ``##`` section."""
    return matches(_TOP_HEADING, line)


def visible_lines(text: str) -> list[str]:
    """Lines outside HTML comments and fenced code blocks (neither counts as document content)."""
    lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in _HTML_COMMENT.sub("", normalize_newlines(text)).split(LF):
        marked = markup(line)
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


def section_after(lines: list[str], heading: re.Pattern[str]) -> list[list[str]]:
    """Bodies of every ``##`` section whose heading matches, each up to the next level 1 or 2 heading."""
    bodies: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if matches(heading, line):
            current = []
            bodies.append(current)
        elif current is not None:
            if is_top_heading(line):
                current = None
            else:
                current.append(line)
    return bodies
