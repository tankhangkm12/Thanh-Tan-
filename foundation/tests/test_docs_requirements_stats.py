"""Docs pinned at confirm, a verdict per requirement at review, and `agentflow stats`.

- A step with ``pin_docs_on_approval`` keeps, when a person approves it, the sha256 of each path its report lists under
  ``## Tài liệu`` (``tasks/<task>/docs-pinned.json``). A document that changes afterwards gets a ``TL<n>`` box in the
  checklist of a step with ``changed-docs`` and a warning in ``agentflow status``.
- The gate ``requirements-reviewed`` wants ``Y1: đạt ...`` or ``Y1: chưa đạt ...`` for every requirement of the first
  step's report; ``review-requirements`` gives the person one box per requirement.
- Every gate refusal adds a line to ``tasks/<task>/gate-log.jsonl``; ``agentflow stats`` reads it with the history.
"""

import json
from pathlib import Path

import pytest
from checklist_helpers import PLAN2, approve, checklist_path, checklist_workflow, codes, items, open_workspace, task_dir, tick
from conftest import git
from sdd_helpers import run, say

from agentflow import docpin, stats
from agentflow.constants import ExitCode, HistoryEvent, StepStatus, TaskStatus
from agentflow.gates import requirement_problems
from agentflow.models import HistoryEntry, Task
from agentflow.workflow import load_workflow

REAL_WORKFLOW = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core" / "workflow.yaml"

CONFIRM = """# Confirm

## Yêu cầu
- Y1: Khách xem được lịch sử đơn hàng.
- Y2: Người khác không xem được.

## Tài liệu
- `docs/spec.md`
- docs/design
- https://example.com/contract
"""

REVIEW_OK = """# Review

Y1: đạt ở src/orders.py:10
- Y2: đạt — kiểm bằng test tests/test_orders.py::test_other_user

## Đề xuất cập nhật hồ sơ
không có
"""


def pinning_workflow(tmp_path: Path) -> Path:
    path = checklist_workflow(tmp_path)
    data = json.loads(json.dumps(__import__("yaml").safe_load(path.read_text(encoding="utf-8"))))
    data["steps"][0]["pin_docs_on_approval"] = True
    data["steps"][2]["gates"] = ["requirements-reviewed"]
    data["steps"][2]["approval_items"] = ["review-requirements", "changed-docs"]
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    docs = gitflow_repo / "docs"
    (docs / "design").mkdir(parents=True)
    (docs / "spec.md").write_text("spec v1\n", encoding="utf-8")
    (docs / "design" / "screen.md").write_text("screen v1\n", encoding="utf-8")
    git(gitflow_repo, "add", "-A")
    git(gitflow_repo, "commit", "-q", "-m", "docs")
    return open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, pinning_workflow(tmp_path))


def to_confirm_approved(repo, monkeypatch, capsys, confirm: str = CONFIRM, task: str = "T-001") -> str:
    assert say(monkeypatch, "task", "new", "Orders") == ExitCode.OK
    assert say(monkeypatch, "report", "--step", "confirm", text=confirm) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    tick(checklist_path(repo, "confirm", task=task))
    capsys.readouterr()
    code, out, err = approve(capsys)
    assert code == ExitCode.OK, err
    return out


def to_check(repo, monkeypatch, capsys) -> None:
    assert say(monkeypatch, "report", "--step", "build", text=PLAN2) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    tick(checklist_path(repo, "build"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    capsys.readouterr()


def pinned(repo) -> dict:
    return json.loads((task_dir(repo) / "docs-pinned.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the docs section


def test_the_docs_section_gives_paths_and_links_and_nothing_else():
    text = CONFIRM + "\n## Khác\n- not/a/doc.md\n"
    assert docpin.parse_docs(text) == (["docs/spec.md", "docs/design"], ["https://example.com/contract"])


@pytest.mark.parametrize("body", ["- không có", "- none", ""])
def test_a_docs_section_with_none_lists_nothing(body):
    assert docpin.parse_docs(f"## Tài liệu\n{body}\n") == ([], [])


def test_a_report_without_the_section_lists_nothing():
    assert docpin.parse_docs("# Confirm\n\n## Yêu cầu\n- Y1: x\n") == ([], [])


# ------------------------------------------------------------------ pinning at the approval


def test_approving_the_step_pins_each_file_and_folder_and_keeps_the_links(repo, monkeypatch, capsys):
    out = to_confirm_approved(repo, monkeypatch, capsys)
    assert "documents pinned: 2 path(s), 1 link(s)" in out
    record = pinned(repo)
    assert record["step"] == "confirm"
    assert set(record["docs"]) == {"docs/spec.md", "docs/design"}
    assert all(len(sha) == 64 for sha in record["docs"].values())
    assert record["links"] == ["https://example.com/contract"]


def test_a_path_that_does_not_exist_is_pinned_as_absent_and_named(repo, monkeypatch, capsys):
    out = to_confirm_approved(repo, monkeypatch, capsys, CONFIRM.replace("docs/design", "docs/missing.md"))
    assert "not found: docs/missing.md" in out
    assert pinned(repo)["docs"]["docs/missing.md"] is None


def test_a_windows_path_is_read_on_every_platform(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys, CONFIRM.replace("`docs/spec.md`", "docs\\spec.md"))
    assert pinned(repo)["docs"]["docs\\spec.md"] is not None


def test_a_step_without_the_flag_pins_nothing(gitflow_repo, tmp_path, monkeypatch, capsys):
    open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    to_confirm_approved(gitflow_repo, monkeypatch, capsys)
    assert not (task_dir(gitflow_repo) / "docs-pinned.json").exists()


# ------------------------------------------------------------------ a document that changed


def test_no_change_gives_no_docs_box_and_no_warning(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "report", "--step", "check", text=REVIEW_OK) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert not [code for code in codes(checklist_path(repo, "check").read_text(encoding="utf-8")) if code.startswith("TL")]
    _code, _out, err = run(capsys, "status")
    assert "document" not in err


def test_a_changed_file_and_a_changed_folder_each_get_a_box_the_person_must_tick(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    (repo / "docs" / "spec.md").write_text("spec v2\n", encoding="utf-8")
    (repo / "docs" / "design" / "new.md").write_text("new\n", encoding="utf-8")
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "report", "--step", "check", text=REVIEW_OK) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    path = checklist_path(repo, "check")
    lines = {code: text for _box, _opt, code, text in items(path.read_text(encoding="utf-8"))}
    assert "docs/spec.md changed" in lines["TL1"]
    assert "docs/design changed" in lines["TL2"]
    tick(path, "Y1", "Y2", "K1")
    code, _out, err = approve(capsys)
    assert code == 36 and "TL1" in err
    tick(path)
    assert approve(capsys)[0] == ExitCode.OK


def test_status_warns_about_a_document_that_is_gone(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    (repo / "docs" / "spec.md").unlink()
    code, _out, err = run(capsys, "status")
    assert code == ExitCode.OK
    assert "docs/spec.md missing" in err
    assert docpin.changes(repo / ".agentflow", repo, "T-001") == [docpin.DocChange("docs/spec.md", docpin.MISSING)]


def test_a_document_that_appears_after_being_absent_counts_as_a_change(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys, CONFIRM.replace("docs/design", "docs/later.md"))
    (repo / "docs" / "later.md").write_text("now\n", encoding="utf-8")
    assert docpin.changes(repo / ".agentflow", repo, "T-001") == [docpin.DocChange("docs/later.md", docpin.APPEARED)]


# ------------------------------------------------------------------ a verdict per requirement


@pytest.mark.parametrize(
    "line",
    ["Y1: đạt", "- Y1: đạt ở src/a.py:3", "* `Y1`: đạt — kiểm tay", "> Y1 - đạt (vòng trước, không đổi)"],
)
def test_a_met_requirement_line_is_accepted(line):
    assert requirement_problems(f"# Review\n{line}\n", ["Y1"]) == []


def test_a_requirement_without_a_verdict_is_named():
    problems = requirement_problems("# Review\nY2: đạt\n", ["Y1", "Y2"])
    assert len(problems) == 1 and problems[0].startswith("Y1 has no verdict")


def test_an_unmet_requirement_fails_the_review():
    problems = requirement_problems("# Review\nY1: chưa đạt — thiếu phân trang\n", ["Y1"])
    assert len(problems) == 1 and "fails" in problems[0]


def test_y1_is_not_satisfied_by_y10():
    assert requirement_problems("Y10: đạt\n", ["Y1"]) != []


def test_the_gate_refuses_a_review_without_verdicts_and_lets_one_with_them_pass(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "report", "--step", "check", text="# Review\nY1: đạt\n") == ExitCode.OK
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == ExitCode.GATE_FAILED
    assert "[requirements-reviewed] Y2 has no verdict" in err
    assert say(monkeypatch, "report", "--step", "check", text=REVIEW_OK) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    lines = {code: text for _box, _opt, code, text in items(checklist_path(repo, "check").read_text(encoding="utf-8"))}
    assert lines["Y1"].startswith("Khách xem được lịch sử đơn hàng.")
    assert lines["Y2"].startswith("Người khác không xem được.")


def test_without_requirements_the_gate_asks_nothing(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys, "# Confirm\n\n## Tài liệu\n- không có\n")
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "report", "--step", "check", text="# Review\nok\n") == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK


# ------------------------------------------------------------------ stats


def _task(*events: tuple[str, str, HistoryEvent]) -> Task:
    history = tuple(HistoryEntry(at, step, event) for at, step, event in events)
    return Task("T-009", "Sample", TaskStatus.DONE, "check", StepStatus.PASSED, history=history, size="small")


def test_the_history_gives_time_by_step_waiting_rounds_and_approvals():
    task = _task(
        ("2026-10-01T10:00:00Z", "confirm", HistoryEvent.STARTED),
        ("2026-10-01T10:05:00Z", "confirm", HistoryEvent.PASSED),
        ("2026-10-01T10:15:00Z", "confirm", HistoryEvent.APPROVED),
        ("2026-10-01T10:15:00Z", "build", HistoryEvent.STARTED),
        ("2026-10-01T10:45:00Z", "build", HistoryEvent.PASSED),
        ("2026-10-01T10:45:00Z", "check", HistoryEvent.STARTED),
        ("2026-10-01T10:50:00Z", "check", HistoryEvent.FAILED),
        ("2026-10-01T10:50:00Z", "build", HistoryEvent.STARTED),
        ("2026-10-01T11:00:00Z", "build", HistoryEvent.PASSED),
        ("2026-10-01T11:00:00Z", "check", HistoryEvent.STARTED),
        ("2026-10-01T11:10:00Z", "check", HistoryEvent.PASSED),
        ("2026-10-01T11:30:00Z", "check", HistoryEvent.APPROVED),
        ("2026-10-01T11:30:00Z", "check", HistoryEvent.DONE),
    )
    found = stats.task_stats(task)
    assert found.seconds == 90 * 60
    assert found.step_seconds == {"confirm": 15 * 60, "build": 40 * 60, "check": 35 * 60}
    assert found.waiting_seconds == 30 * 60
    assert found.approvals == 2
    assert found.fails == {"check": 1} and found.rounds == 1
    assert found.blocked == 0


def test_a_duration_reads_in_hours_minutes_or_seconds():
    assert [stats.duration(s) for s in (40, 12 * 60, 3900)] == ["40s", "12m", "1h05m"]


def test_a_gate_refusal_is_logged_and_counted_by_stats(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    to_check(repo, monkeypatch, capsys)
    assert say(monkeypatch, "report", "--step", "check", text="# Review\n") == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.GATE_FAILED
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.GATE_FAILED
    log = (task_dir(repo) / "gate-log.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["gates"] for line in log] == [["requirements-reviewed"]] * 2
    capsys.readouterr()
    code, out, _err = run(capsys, "stats")
    assert code == ExitCode.OK
    assert "T-001 Orders (open" in out
    assert "gates that refused a pass: requirements-reviewed x2" in out
    code, out, _err = run(capsys, "stats", "--task", "T-001", "--json")
    data = json.loads(out)
    assert data[0]["gate_refusals"] == {"requirements-reviewed": 2}
    assert data[0]["approvals"] == 2


def test_stats_for_an_unknown_task_is_refused(repo, capsys):
    code, _out, err = run(capsys, "stats", "--task", "T-404")
    assert code == ExitCode.INVALID_INPUT and "T-404" in err


def test_stats_with_no_task_says_so(repo, capsys):
    code, out, _err = run(capsys, "stats")
    assert code == ExitCode.OK and out.strip() == "no tasks yet"


def test_several_tasks_get_a_total(repo, monkeypatch, capsys):
    to_confirm_approved(repo, monkeypatch, capsys)
    assert say(monkeypatch, "task", "cancel") == ExitCode.OK
    git(repo, "checkout", "-q", "develop")
    to_confirm_approved(repo, monkeypatch, capsys, task="T-002")
    capsys.readouterr()
    _code, out, _err = run(capsys, "stats")
    assert "total: 2 task(s) (cancelled 1, open 1)" in out


# ------------------------------------------------------------------ the dev-core workflow uses them


def test_the_software_dev_workflow_pins_docs_at_confirm_and_reviews_every_requirement():
    steps = {step.id: step for step in load_workflow(REAL_WORKFLOW).steps}
    assert steps["confirm"].pin_docs_on_approval
    assert "requirements-reviewed" in [str(g) for g in steps["review"].gates]
    assert {"review-requirements", "changed-docs"} <= {str(i) for i in steps["review"].approval_items}
