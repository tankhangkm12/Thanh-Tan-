"""The task summary a person reads before (and after) approving the last step."""

from collections.abc import Sequence

from thanhtan.constants import (
    DEVELOP_BRANCH,
    LESSONS_DIR,
    LESSONS_HEADING,
    MAIN_BRANCH,
    MARKDOWN_SUFFIX,
    TASKS_DIR,
    TaskType,
)
from thanhtan.lessons import Lesson
from thanhtan.models import CommitInfo, Task
from thanhtan.plan import PlanItem

SHORT_SHA = 9
REPLAN_SUMMARY_LABEL = "Replan"
NO_ITEM_GROUP = "other commits"
NONE_LINE = "- none"
HOTFIX_MERGE_HEADING = "Merge the hotfix"
HOTFIX_MERGE_NOTE = (
    "These are for a person to run; thanhtan and its agents never merge into the main or the development branch. "
    "Pick the next version for the tag."
)


def build_summary(
    task: Task,
    items: Sequence[PlanItem],
    commits: Sequence[CommitInfo],
    scan_lines: Sequence[str],
    approver: str,
    approved_at: str,
    lessons: Sequence[Lesson] = (),
    roadmap: str | None = None,
    spec_delta: str | None = None,
    replan: str | None = None,
    develop_branch: str = DEVELOP_BRANCH,
) -> str:
    lines = [
        f"# {task.id}: {task.title}",
        "",
        f"- Branch: {task.branch}",
        *([f"- Base: {task.base}"] if task.base else []),
        *([f"- Size: {task.size}"] if task.size else []),
        *([f"- Type: {task.type}"] if task.type else []),
        *([f"- Roadmap: {roadmap}"] if roadmap else []),
        *([f"- Spec delta: {spec_delta}"] if spec_delta else []),
        *([f"- {REPLAN_SUMMARY_LABEL}: {replan}"] if replan else []),
        f"- Approved by: {approver}",
        f"- Approved at: {approved_at}",
        "",
        "## Plan items",
        "",
    ]
    by_item: dict[str | None, list[CommitInfo]] = {}
    for commit in commits:
        by_item.setdefault(commit.item, []).append(commit)
    for item in items:
        lines += [f"### {item.code} - {item.title}", ""]
        lines += [f"- Role: {item.role or '?'}", f"- Tier: {item.effective_tier}"]
        if item.layer:
            lines.append(f"- Layer: {item.layer}")
        lines.append(f"- Done when: {item.done_when or '?'}")
        links = item.docs_links
        lines.append(f"- Docs: {', '.join(links) if links else (item.docs or 'none')}")
        lines += ["- Commits:", *_commit_lines(by_item.pop(item.code, []), indent="  ")]
        lines.append("")
    leftover = [commit for group in by_item.values() for commit in group]
    if leftover or not items:
        lines += [f"### {NO_ITEM_GROUP}", "", *_commit_lines(leftover), ""]
    lines += ["## Scans", ""]
    lines += [f"- {line}" for line in scan_lines] or [NONE_LINE]
    lines += ["", f"## {LESSONS_HEADING}", ""]
    if lessons:
        lines += [f"- {lesson.code}: {lesson.title} ({lesson_path_text(task.id, lesson.code)})" for lesson in lessons]
        lines += ["", "Proposals only. A person decides what goes into the personal store: `thanhtan knowledge push <file>`."]
    else:
        lines.append(NONE_LINE)
    if task.type == TaskType.HOTFIX and task.branch:
        lines += ["", f"## {HOTFIX_MERGE_HEADING}", "", HOTFIX_MERGE_NOTE, "", "```", *hotfix_merge_commands(task.branch, task.base or MAIN_BRANCH, develop_branch), "```"]
    return "\n".join(lines) + "\n"


def hotfix_merge_commands(branch: str, main: str = MAIN_BRANCH, develop: str = DEVELOP_BRANCH) -> list[str]:
    """What a person runs to bring a finished hotfix into the main branch (with a version tag) and back into develop."""
    return [
        f"git switch {main}",
        f"git merge --no-ff {branch}",
        'git tag -a v<version> -m "<version>"',
        f"git switch {develop}",
        f"git merge --no-ff {branch}",
    ]


def lesson_path_text(task_id: str, code: str) -> str:
    return f"{TASKS_DIR}/{task_id}/{LESSONS_DIR}/{code}{MARKDOWN_SUFFIX}"


def _commit_lines(commits: Sequence[CommitInfo], indent: str = "") -> list[str]:
    if not commits:
        return [f"{indent}{NONE_LINE}"]
    return [f"{indent}- {commit.sha[:SHORT_SHA]} {commit.subject}" for commit in commits]
