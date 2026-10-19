"""Shared builders for the approval-checklist, integrity and audit tests (phase D-checklist).

Not a test module. Design these helpers rest on (the tests that use them pin it):

- A step opts in with ``approval_checklist`` (fixed questions, codes K1, K2, ...) and/or ``approval_items``
  (``plan-items`` -> C<n>, ``review-conventions`` -> PC-xx, ``drift-proposals`` -> D<n>). A step that declares neither
  has no checklist and ``task approve`` behaves as it always did.
- ``task advance --result pass`` into ``awaiting_approval`` writes ``.agentflow/tasks/<task>/approve-<step>.md``.
- Exit codes: 36 CHECKLIST_REFUSED, 37 INTEGRITY_FAILED (spelled as numbers, like the phase B helpers do).
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from conftest import write_workflow
from sdd_helpers import PLAN, ROADMAP, init_workspace, project_dir, run, say

from agentflow.constants import ExitCode

CHECKLIST_REFUSED = 36
INTEGRITY_FAILED = 37
INVALID_INPUT = 22

CONFIRM_QUESTIONS = ["Mục tiêu được nhắc lại đúng ý bạn?", "Phạm vi khớp những gì bạn viết?"]
BUILD_QUESTIONS = ["Mỗi mục có done-when kiểm được?"]
CHECK_QUESTIONS = ["Thay đổi đúng kế hoạch đã duyệt?"]

PLAN2 = PLAN + "\n### C2 - Test it\n- role: builder\n- files: b.txt\n- done-when: `true`\n- docs: https://docs.example/b\n"

CONVENTIONS_FILE = """# Quy ước

### PC-01 - Constants
- check: review
- status: confirmed
- source: src/constants.py
- description: Fixed values live in constants.

### PC-02 - Plan order
- check: plan
- rule: item-order
- status: confirmed
- source: docs
- description: Not for the reviewer.
"""

REVIEW_REPORT = """# Review

PC-01: đạt

## Đề xuất cập nhật hồ sơ
- profile: thêm lệnh build mới
- roadmap: R2 đã hoàn thành
"""

REVIEW_REPORT_NO_PROPOSAL = """# Review

PC-01: đạt

## Đề xuất cập nhật hồ sơ
không có
"""

_ITEM = re.compile(r"^- \[(?P<box>[ xX])\] (?P<opt>\(tùy chọn\) )?(?P<code>[A-Za-z][\w-]*): (?P<text>.+?)\r?$", re.M)


def checklist_workflow(tmp_path: Path, **overrides) -> Path:
    """confirm -> build -> check, each needing approval and each with a checklist; ``small`` drops the approval of build."""
    data = {
        "schema_version": 1,
        "family": "sample",
        "max_rounds": 3,
        "sizes": {
            "default": "normal",
            "profiles": {"normal": {}, "small": {"skip_approval": ["build"]}},
        },
        "steps": [
            {
                "id": "confirm",
                "name": "Confirm",
                "role": "lead",
                "requires_approval": True,
                "approval_checklist": CONFIRM_QUESTIONS,
            },
            {
                "id": "build",
                "name": "Build",
                "role": "builder",
                "requires_approval": True,
                "approval_checklist": BUILD_QUESTIONS,
                "approval_items": ["plan-items"],
            },
            {
                "id": "check",
                "name": "Check",
                "role": "checker",
                "on_fail": "build",
                "requires_approval": True,
                "approval_checklist": CHECK_QUESTIONS,
                "approval_items": ["review-conventions", "drift-proposals"],
            },
        ],
    }
    data.update(overrides)
    return write_workflow(tmp_path / "plugin" / "workflow.yaml", data)


def open_workspace(repo: Path, tmp_path: Path, monkeypatch, capsys, workflow: Path | None = None) -> Path:
    return init_workspace(repo, workflow or checklist_workflow(tmp_path), monkeypatch, capsys)


def workspace(repo: Path) -> Path:
    return repo / ".agentflow"


def task_dir(repo: Path, task: str = "T-001") -> Path:
    return workspace(repo) / "tasks" / task


def checklist_path(repo: Path, step: str, round_: int | None = None, task: str = "T-001") -> Path:
    name = f"approve-{step}.md" if round_ is None else f"approve-{step}.{round_}.md"
    return task_dir(repo, task) / name


def state_path(repo: Path) -> Path:
    return workspace(repo) / "state.json"


def integrity_path(repo: Path) -> Path:
    return workspace(repo) / "integrity.json"


def audit_path(repo: Path) -> Path:
    return workspace(repo) / "audit.jsonl"


def decisions(repo: Path) -> list[Path]:
    folder = workspace(repo) / "decisions"
    return sorted(folder.glob("*")) if folder.is_dir() else []


def task_now(repo: Path) -> tuple[str, str, str]:
    """(status, current step, step status) of the first task, read the way a person would."""
    task = json.loads(state_path(repo).read_text(encoding="utf-8"))["tasks"][0]
    return task["status"], task["current_step"], task["step_status"]


def items(text: str) -> list[tuple[str, bool, str, str]]:
    """(box, optional, code, text) of every checklist line."""
    return [(m["box"], bool(m["opt"]), m["code"], m["text"]) for m in _ITEM.finditer(text)]


def codes(text: str, *, optional: bool | None = None) -> list[str]:
    return [code for _box, opt, code, _text in items(text) if optional is None or opt is optional]


def tick(path: Path, *wanted: str) -> None:
    """Tick the named items, or every required (not optional) item when none is named."""

    def flip(match: re.Match) -> str:
        chosen = match["code"] in wanted if wanted else not match["opt"]
        return match.group(0).replace("- [ ]", "- [x]", 1) if chosen else match.group(0)

    path.write_text(_ITEM.sub(flip, path.read_text(encoding="utf-8")), encoding="utf-8", newline="")


def add_note(path: Path, note: str) -> None:
    """The notes section is the last one of the file: text added at the end belongs to it."""
    text = path.read_text(encoding="utf-8")
    path.write_text(text.rstrip("\n") + "\n" + note + "\n", encoding="utf-8", newline="")


def write_conventions(repo: Path) -> None:
    (project_dir(repo)).mkdir(parents=True, exist_ok=True)
    (project_dir(repo) / "conventions.md").write_text(CONVENTIONS_FILE, encoding="utf-8")


def write_roadmap(repo: Path) -> None:
    project_dir(repo).mkdir(parents=True, exist_ok=True)
    (project_dir(repo) / "roadmap.md").write_text(ROADMAP, encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def passed(capsys) -> tuple[int, str, str]:
    return run(capsys, "task", "advance", "--result", "pass")


def approve(capsys, *extra: str) -> tuple[int, str, str]:
    return run(capsys, "task", "approve", *extra)


def go_to_awaiting(repo: Path, step: str, monkeypatch, capsys, *, report: str | None = None, first=True, extra=()) -> None:
    """Drive a new task to ``step`` awaiting approval, ticking and approving the steps before it."""
    if first:
        assert say(monkeypatch, "task", "new", "Do it", *extra) == ExitCode.OK
    order = ["confirm", "build", "check"]
    for before in order[: order.index(step)]:
        _pass_with_report(repo, before, monkeypatch)
        tick(checklist_path(repo, before))
        assert say(monkeypatch, "task", "approve") == ExitCode.OK
    _pass_with_report(repo, step, monkeypatch, report)
    capsys.readouterr()


def _pass_with_report(repo: Path, step: str, monkeypatch, report: str | None = None) -> None:
    text = report or {"build": PLAN2, "check": REVIEW_REPORT}.get(step)
    if text is not None:
        assert say(monkeypatch, "report", "--step", step, text=text) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK


