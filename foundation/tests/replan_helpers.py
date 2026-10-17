"""Shared builders for the spec-delta and replan tests (phase C).

Not a test module. It runs a task through a workflow of the shape dev-core has around the review
(confirm -> build -> review, where the review carries the `drift-reviewed` gate) and leaves it done and sealed.
"""

import copy
import io
import re
from collections.abc import Callable
from pathlib import Path

from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode

HEADING = "## Đề xuất cập nhật hồ sơ"
NONE_PROPOSAL = "không có"

PLAN = """### C1 - Build it
- role: builder
- files: a.txt
- done-when: `true`
- docs: https://docs.example/a
"""

# A replan report the way the scout writes it for the first task, naming the roadmap item the task finished.
REPLAN = """# Replan T-001

## Mục roadmap đã hoàn thành

- R1: summary.md của T-001 ghi C1 đã xong và test chạy xanh.

## Đề xuất cải tiến quy trình

- Thêm ô kiểm "chạy lại smoke" vào checklist của bước review.
"""

NOTHING_DONE = REPLAN.replace("- R1: summary.md của T-001 ghi C1 đã xong và test chạy xanh.", NONE_PROPOSAL)

REPLAN_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def review_workflow(tmp_path: Path, drift_gate: bool = True) -> Path:
    data = copy.deepcopy(SAMPLE_WORKFLOW)
    data["steps"] = [
        {"id": "confirm", "name": "Confirm", "role": "lead", "requires_approval": True},
        {"id": "build", "name": "Build", "role": "builder", "gates": ["plan-valid"]},
        {"id": "review", "name": "Review", "role": "reviewer", "requires_approval": True, "on_fail": "build"},
    ]
    if drift_gate:
        data["steps"][2]["gates"] = ["drift-reviewed"]
    return write_workflow(tmp_path / "plugin" / "workflow.yaml", data)


def start_workspace(repo: Path, tmp_path: Path, monkeypatch, capsys, drift_gate: bool = True) -> Path:
    monkeypatch.chdir(repo)
    assert main(["init", "--workflow", str(review_workflow(tmp_path, drift_gate))]) == ExitCode.OK
    capsys.readouterr()
    return repo


def say(monkeypatch, *argv: str, text: str | None = None) -> int:
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def run(capsys, *argv: str, text: str | None = None, monkeypatch=None) -> tuple[int, str, str]:
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def review_report(proposals: str = NONE_PROPOSAL) -> str:
    return f"# Review\n\nVerdict: no must-fix items.\n\n{HEADING}\n\n{proposals}\n"


def run_task(
    repo: Path,
    monkeypatch,
    title: str = "t",
    *,
    review: str | None = None,
    mutate: Callable[[Path], None] | None = None,
    extra: tuple[str, ...] = (),
    approve: bool = True,
) -> None:
    """Take a task to the end of the review: a plan with item C1, one commit on C1, a review report, then the approval.

    `mutate` changes the working tree (it must leave the changes for the commit); by default it adds `a.txt`.
    `review=None` writes no review report at all. With `approve=False` the task stops waiting for the approval.
    """
    assert say(monkeypatch, "task", "new", title, *extra) == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")  # confirm -> build
    say(monkeypatch, "report", "--step", "build", text=PLAN)
    if mutate is None:
        (repo / "a.txt").write_text(f"{title}\n", encoding="utf-8")
    else:
        mutate(repo)
    git(repo, "add", "-A")
    assert say(monkeypatch, "commit", f"change {title}", "--item", "C1") == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")  # build -> review
    if review is not None:
        assert say(monkeypatch, "report", "--step", "review", text=review) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # review -> awaiting approval
    if approve:
        assert say(monkeypatch, "task", "approve") == ExitCode.OK
        git(repo, "switch", "-q", "develop")


def task_dir(repo: Path, task_id: str = "T-001") -> Path:
    return repo / ".agentflow" / "tasks" / task_id


def spec_delta(repo: Path, task_id: str = "T-001") -> str:
    return (task_dir(repo, task_id) / "spec-delta.md").read_text(encoding="utf-8")


def summary(repo: Path, task_id: str = "T-001") -> str:
    return (task_dir(repo, task_id) / "summary.md").read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """The body of a `## heading` section up to the next `## `."""
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    assert found, f"no '## {heading}' section in:\n{text}"
    return found.group(1)


def write_project_file(repo: Path, name: str, text: str) -> None:
    folder = repo / ".agentflow" / "project"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
