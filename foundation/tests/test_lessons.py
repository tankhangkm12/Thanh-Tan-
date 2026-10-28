import io

import pytest
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode, StepStatus, TaskStatus
from agentflow.lessons import Lesson, parse_lessons, write_lessons
from agentflow.models import Task
from agentflow.seal import approval_tag
from agentflow.summary import build_summary

REPORT = """# Review

PC-01: đạt

## Bài học đề xuất

### L1 - Back off before retrying
Retries without a pause made the outage worse.
Use exponential backoff.

### L2 - Test the migration down path
The down migration was never run until review.

## Ghi chú khác

### L9 - not a lesson
"""


def test_lessons_are_read_from_their_section_only():
    lessons = parse_lessons(REPORT)
    assert [l.code for l in lessons] == ["L1", "L2"]
    assert lessons[0] == Lesson("L1", "Back off before retrying", "Retries without a pause made the outage worse.\nUse exponential backoff.")
    assert parse_lessons("# Review\nnothing proposed") == []
    assert parse_lessons("## bài học đề xuất\n### L1 - t\nx") == [Lesson("L1", "t", "x")]


def test_lessons_are_written_as_files_a_person_can_push(tmp_path):
    paths = write_lessons(tmp_path, "T-004", parse_lessons(REPORT))
    assert [p.relative_to(tmp_path).as_posix() for p in paths] == ["tasks/T-004/lessons/L1.md", "tasks/T-004/lessons/L2.md"]
    assert paths[0].read_text(encoding="utf-8") == "# Back off before retrying\n\nRetries without a pause made the outage worse.\nUse exponential backoff.\n"


def test_rewriting_replaces_lessons_of_an_earlier_seal(tmp_path):
    write_lessons(tmp_path, "T-004", parse_lessons(REPORT))
    write_lessons(tmp_path, "T-004", parse_lessons("## Bài học đề xuất\n### L1 - Only one\nbody"))
    assert sorted(p.name for p in (tmp_path / "tasks" / "T-004" / "lessons").iterdir()) == ["L1.md"]


def test_the_summary_lists_the_proposed_lessons():
    task = Task("T-004", "t", TaskStatus.DONE, "review", StepStatus.PASSED, branch="feature/T-004-t")
    text = build_summary(task, [], [], [], "me", "now", lessons=parse_lessons(REPORT))
    assert "## Bài học đề xuất" in text
    assert "- L1: Back off before retrying (tasks/T-004/lessons/L1.md)" in text
    assert "knowledge push" in text
    bare = build_summary(task, [], [], [], "me", "now")
    assert "## Bài học đề xuất" in bare and "- none" in bare.split("## Bài học đề xuất")[1]


# ---- sealing writes them


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]
    data["steps"][2]["requires_approval"] = True
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    main(["init", "--workflow", str(path)])
    capsys.readouterr()
    return gitflow_repo


@pytest.fixture(autouse=True)
def _no_container(monkeypatch):
    from agentflow.models import ScanResult

    class Clean:
        def __init__(self, runner):
            pass

        def scan_staged(self, repo):
            return ScanResult(True, "")

    monkeypatch.setattr("agentflow.cli.ContainerGitleaksScanner", Clean)


def say(monkeypatch, *argv, text=None):
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def test_sealing_a_task_writes_the_lessons_of_its_last_report(ws, monkeypatch):
    plan = "### C1 - Build it\n- role: builder\n- files: a.txt\n- done-when: `true`\n- docs: https://docs.example/a\n"
    say(monkeypatch, "task", "new", "t")
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "build", text=plan)
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    git(ws, "add", "a.txt")
    assert say(monkeypatch, "commit", "add a", "--item", "C1") == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "report", "--step", "check", text=REPORT)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    base = ws / ".ThanhTan" / "tasks" / "T-001"
    assert (base / "lessons" / "L1.md").is_file() and (base / "lessons" / "L2.md").is_file()
    summary = (base / SUMMARY).read_text(encoding="utf-8")
    assert "L1: Back off before retrying" in summary
    assert git(ws, "tag", "-l", approval_tag("T-001")) == approval_tag("T-001")


SUMMARY = "summary.md"
