"""The ``## Đề xuất cập nhật hồ sơ`` section of a review report: does the change make a project document wrong?

The reviewer only proposes. This module checks the form of the section (it exists once, and holds either
``không có`` or bullets ``- <document>: <proposal>``); whether a proposal is right is for the person to judge.
"""

import re

from thanhtan.constants import DRIFT_HEADING, DRIFT_NONE_TEXT, DriftDoc
from thanhtan.mdutil import is_top_heading, matches, visible_lines

_HEADING = re.compile(rf"^##[ \t]+{re.escape(DRIFT_HEADING)}[ \t]*$")
_NONE = re.compile(rf"^{re.escape(DRIFT_NONE_TEXT)}\.?$", re.IGNORECASE)
_BULLET = re.compile(r"^-[ \t]+([A-Za-z][\w-]*)[ \t]*:[ \t]*(.*?)[ \t]*$")
_PREFIX = f'the "## {DRIFT_HEADING}" section'


def drift_problems(text: str) -> list[str]:
    """Problems with the section; empty when it is well formed."""
    lines = visible_lines(text)
    starts = [number for number, line in enumerate(lines) if matches(_HEADING, line)]
    if not starts:
        return [f"the report has no {_PREFIX}: write `{DRIFT_NONE_TEXT}`, or one `- <document>: <proposal>` per project document to change"]
    if len(starts) > 1:
        return [f"the report has {_PREFIX} {len(starts)} times: keep one"]
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if is_top_heading(line):
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


def drift_section(text: str) -> str | None:
    """The body of the section as written (code blocks and comments left out), or ``None`` when it is missing or empty."""
    lines = visible_lines(text)
    starts = [number for number, line in enumerate(lines) if matches(_HEADING, line)]
    if not starts:
        return None
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if is_top_heading(line):
            break
        body.append(line.rstrip())
    found = "\n".join(body).strip("\n")
    return found if found.strip() else None
