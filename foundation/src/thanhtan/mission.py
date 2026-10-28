"""The ``## Mission`` section of the project profile: why the project exists, for whom, its scope and what is out of it.

A scout writes it from the documents a person gave (never from code). The section is read the way people write
Markdown: headings and bullets inside fenced code or HTML comments do not count.
"""

import re
from dataclasses import dataclass

from thanhtan.constants import MISSION_HEADING, MissionField
from thanhtan.mdutil import section_after, visible_lines

_HEADING = re.compile(rf"^##[ \t]+{re.escape(MISSION_HEADING)}[ \t]*$")
_FIELD = re.compile(r"^-[ \t]+([A-Za-z][\w-]*)[ \t]*:[ \t]*(.*?)[ \t]*$")
_FIELDS = tuple(MissionField)


@dataclass(frozen=True)
class Mission:
    lines: tuple[str, ...]
    values: dict[str, str]
    sections: int

    def warnings(self) -> list[str]:
        found: list[str] = []
        if self.sections > 1:
            found.append(f'the profile has the "## {MISSION_HEADING}" section twice: the first one is used')
        for name in _FIELDS:
            if name not in self.values:
                found.append(f"the {MISSION_HEADING} section lacks '- {name}:'")
            elif not self.values[name]:
                found.append(f"the {MISSION_HEADING} field '{name}' is empty")
        return found

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def parse_mission(profile_text: str) -> Mission | None:
    """The first mission section of the profile, or ``None`` when it has none."""
    bodies = section_after(visible_lines(profile_text), _HEADING)
    if not bodies:
        return None
    values: dict[str, str] = {}
    for line in bodies[0]:
        found = _FIELD.match(line)
        if found and found.group(1).lower() in _FIELDS:
            values.setdefault(found.group(1).lower(), found.group(2))
    return Mission(tuple(bodies[0]), values, len(bodies))


def missing_text() -> str:
    fields = ", ".join(_FIELDS)
    return f'the profile has no "## {MISSION_HEADING}" section ({fields}): the scout writes it from the documents you give'


def mission_warnings(profile_text: str) -> list[str]:
    mission = parse_mission(profile_text)
    return [missing_text()] if mission is None else mission.warnings()

