"""``review-map.md``: what a task changed, by plan item, worked out from git and from the results agentflow ran itself.

It is a guide for the person who reviews a large change: which commits and files belong to which item, which files an item
changed that its plan did not list, and what agentflow last ran for the item. It holds no opinion of an agent.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agentflow.constants import PLAN_ITEM_TRAILER, ExitCode
from agentflow.errors import AgentflowError
from agentflow.ext_rules import file_listed
from agentflow.git import run_git
from agentflow.plan import PlanItem

REVIEW_MAP_FILE = "review-map.md"
SHORT_SHA = 7
_RECORD, _FIELD = "\x1e", "\x1f"
_LOG = f"--format={_RECORD}%H{_FIELD}%s{_FIELD}%(trailers:key={PLAN_ITEM_TRAILER},valueonly,unfold){_FIELD}"
_BINARY = "-"


@dataclass(frozen=True)
class CommitFiles:
    sha: str
    subject: str
    item: str | None
    files: tuple[tuple[str, int, int], ...]  # (path, lines added, lines removed)


def collect_commits(root: Path, base: str, head: str) -> list[CommitFiles]:
    """The commits of ``base..head`` with the files each changed and their line counts."""
    done = run_git(root, "log", "--reverse", "--numstat", "--no-renames", _LOG, f"{base}..{head}")
    if done.returncode != 0:
        raise AgentflowError(f"git log failed: {(done.stderr or done.stdout).strip()}", ExitCode.GIT_FAILED)
    commits = []
    for record in done.stdout.split(_RECORD):
        if not record.strip():
            continue
        sha, subject, item, rest = record.split(_FIELD, 3)
        files = []
        for line in rest.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added, removed, path = parts
                files.append((path, 0 if added == _BINARY else int(added), 0 if removed == _BINARY else int(removed)))
        commits.append(CommitFiles(sha.strip(), subject, item.strip() or None, tuple(files)))
    return commits


def build_review_map(
    task_id: str,
    title: str,
    items: Sequence[PlanItem],
    commits: Sequence[CommitFiles],
    results: Mapping[str, Mapping],
) -> str:
    """``results`` maps an item code to what agentflow last ran for it (``status``), from ``tests-pass.json``."""
    lines = [
        f"# {task_id}: {title} - review map",
        "",
        "Worked out by agentflow from git and from the commands it ran itself. It is a guide to where to read, not a review.",
        "",
        "## By plan item",
        "",
    ]
    for item in items:
        mine = [commit for commit in commits if commit.item == item.code]
        lines += [f"### {item.code} - {item.title}", ""]
        lines.append(f"- done-when: {item.done_when or 'none'}")
        status = (results.get(item.code) or {}).get("status")
        lines.append(f"- last run by agentflow: {status}" if status else "- not run by agentflow (no test-spec command for this item)")
        if not mine:
            lines += ["- no commit names this item", ""]
            continue
        listed = item.files or ()
        outside: list[str] = []
        for commit in mine:
            lines.append(f"- commit {commit.sha[:SHORT_SHA]} {commit.subject}")
            for path, added, removed in commit.files:
                lines.append(f"  - {path} (+{added} -{removed})")
                if listed and not file_listed(path, listed) and path not in outside:
                    outside.append(path)
        if outside:
            lines.append(f"- outside the files of {item.code}: {', '.join(outside)}")
        lines.append("")
    loose = [commit for commit in commits if commit.item is None]
    if loose:
        lines += ["## Commits without a plan item", ""]
        for commit in loose:
            lines.append(f"- commit {commit.sha[:SHORT_SHA]} {commit.subject}")
            lines += [f"  - {path} (+{added} -{removed})" for path, added, removed in commit.files]
        lines.append("")
    unknown = sorted({commit.item for commit in commits if commit.item and commit.item not in {item.code for item in items}})
    if unknown:
        lines += ["## Commits naming an item the plan does not have", "", f"- {', '.join(unknown)}", ""]
    touched = {path for commit in commits for path, _, _ in commit.files}
    added = sum(a for commit in commits for _, a, _ in commit.files)
    removed = sum(r for commit in commits for _, _, r in commit.files)
    lines += ["## Total", "", f"{len(touched)} files, +{added} -{removed}", ""]
    return "\n".join(lines)
