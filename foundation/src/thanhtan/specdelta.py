"""``spec-delta.md``: what a finished task changed in the specification, written by thanhtan when it seals the task.

Three parts, none of them written by the agent that did the work:

- what the reviewer proposed for the project documents (copied from the review report),
- what the task really changed (the plan items, the commits and the files git reports),
- links: the roadmap item and whether the mission, profile and architecture are confirmed.

The replan reads it to bring the project documents up to date.
"""

from collections.abc import Sequence

from thanhtan.constants import (
    DRIFT_HEADING,
    NO_REVIEW_REPORT_TEXT,
    SPEC_DELTA_CHANGES_HEADING,
    SPEC_DELTA_LINKS_HEADING,
    SPEC_DELTA_PROPOSALS_HEADING,
    ConfirmUnit,
)
from thanhtan.drift import drift_section
from thanhtan.models import CommitInfo, FileChange, Task
from thanhtan.plan import PlanItem

SHORT_SHA = 9
NONE_LINE = "- không có"
ROOT_GROUP = "./"
_MISSING_SECTION = f"không có mục {DRIFT_HEADING} trong báo cáo review"


def reviewer_proposals(review_report: str | None) -> str:
    """The reviewer's section as written, or a line saying why there is none."""
    if review_report is None:
        return NO_REVIEW_REPORT_TEXT
    section = drift_section(review_report)
    return _MISSING_SECTION if section is None else section


def build_spec_delta(
    task: Task,
    review_report: str | None,
    items: Sequence[PlanItem],
    commits: Sequence[CommitInfo],
    files: Sequence[FileChange],
    roadmap: str | None,
    states: dict[str, str],
) -> str:
    lines = [
        f"# {task.id}: {task.title}",
        "",
        f"## {SPEC_DELTA_PROPOSALS_HEADING}",
        "",
        reviewer_proposals(review_report),
        "",
        f"## {SPEC_DELTA_CHANGES_HEADING}",
        "",
        "### Mục kế hoạch",
        "",
        *([f"- {item.code} - {item.title}" for item in items] or [NONE_LINE]),
        "",
        "### Commit",
        "",
        *([f"- {commit.sha[:SHORT_SHA]} {commit.subject}" for commit in commits] or [NONE_LINE]),
        "",
        "### File đổi",
        "",
        *_file_lines(files),
        "",
        f"## {SPEC_DELTA_LINKS_HEADING}",
        "",
        f"- roadmap: {roadmap or 'không có'}",
        *[f"- {unit}: {states[unit]}" for unit in (ConfirmUnit.MISSION, ConfirmUnit.PROFILE, ConfirmUnit.ARCHITECTURE)],
    ]
    return "\n".join(lines) + "\n"


def _file_lines(files: Sequence[FileChange]) -> list[str]:
    if not files:
        return [NONE_LINE]
    groups: dict[str, list[FileChange]] = {}
    for change in files:
        groups.setdefault(_group(change.path), []).append(change)
    lines: list[str] = []
    for name in sorted(groups, key=lambda group: (group != ROOT_GROUP, group)):
        lines += [f"#### {name}", ""]
        lines += [_file_line(change) for change in sorted(groups[name], key=lambda change: change.path)]
        lines.append("")
    return lines[:-1]


def _group(path: str) -> str:
    first, separator, _ = path.partition("/")
    return f"{first}/" if separator else ROOT_GROUP


def _file_line(change: FileChange) -> str:
    if change.status == "R" and change.old_path:
        return f"- R {change.old_path} -> {change.path}"
    return f"- {change.status} {change.path}"
