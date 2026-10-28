import io

import pytest
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode
from agentflow.git import SubprocessGit
from agentflow.models import CommitInfo, Task
from agentflow.constants import StepStatus, TaskStatus
from agentflow.plan import PlanItem
from agentflow.seal import approval_tag, base_branch
from agentflow.summary import build_summary

PLAN = """### C1 - Build it
- role: builder
- files: a.txt
- done-when: `true`
- docs: https://docs.example/a
"""


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


def say(monkeypatch, *argv, text=None):
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def finish_task(ws, monkeypatch, title="t"):
    """Run the sample workflow to the last approval, with one commit on item C1."""
    assert say(monkeypatch, "task", "new", title) == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")  # confirm -> build
    say(monkeypatch, "report", "--step", "build", text=PLAN)
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    git(ws, "add", "a.txt")
    assert say(monkeypatch, "commit", "add a", "--item", "C1") == ExitCode.OK


def test_commit_with_item_adds_a_trailer_and_rejects_unknown_items(ws, monkeypatch, capsys):
    finish_task_pending = say(monkeypatch, "task", "new", "t")
    assert finish_task_pending == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "build", text=PLAN)
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    git(ws, "add", "a.txt")
    assert say(monkeypatch, "commit", "bad", "--item", "C9") == ExitCode.INVALID_INPUT
    assert say(monkeypatch, "commit", "add a", "--item", "C1") == ExitCode.OK
    assert git(ws, "log", "-1", "--format=%s") == "T-001: add a"
    commits = SubprocessGit(ws).commits_between("develop", "HEAD")
    assert [c.item for c in commits] == ["C1"]


@pytest.fixture(autouse=True)
def _no_container(monkeypatch):
    from agentflow.models import ScanResult

    class Clean:
        def __init__(self, runner):
            pass

        def scan_staged(self, repo):
            return ScanResult(True, "")

    monkeypatch.setattr("agentflow.cli.ContainerGitleaksScanner", Clean)


def drive_to_the_end(ws, monkeypatch):
    for _ in range(2):  # build, check
        say(monkeypatch, "task", "advance", "--result", "pass")


def test_last_approval_writes_summary_and_an_annotated_tag(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch)
    drive_to_the_end(ws, monkeypatch)
    assert git(ws, "tag", "-l", approval_tag("T-001")) == ""  # not before the person approves
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    tag = approval_tag("T-001")
    assert git(ws, "tag", "-l", tag) == tag
    assert git(ws, "cat-file", "-t", tag) == "tag"  # annotated
    message = git(ws, "tag", "-l", "--format=%(contents)", tag)
    assert "T-001" in message and "t" in message and "Test <test@example.invalid>" in message
    assert git(ws, "rev-parse", f"{tag}^{{commit}}") == git(ws, "rev-parse", "feature/T-001-t")
    summary = (ws / ".ThanhTan" / "tasks" / "T-001" / "summary.md").read_text(encoding="utf-8")
    assert "### C1 - Build it" in summary and "https://docs.example/a" in summary and "T-001: add a" in summary
    assert "scans were not run" in summary


def test_task_new_needs_the_approval_tag_of_the_last_done_task(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch)
    drive_to_the_end(ws, monkeypatch)
    say(monkeypatch, "task", "approve")
    git(ws, "switch", "-q", "develop")
    assert say(monkeypatch, "task", "new", "second") == ExitCode.OK
    say(monkeypatch, "task", "cancel")
    git(ws, "switch", "-q", "develop")
    git(ws, "tag", "-d", approval_tag("T-001"))
    capsys.readouterr()
    assert say(monkeypatch, "task", "new", "third") == ExitCode.TASK_NOT_SEALED
    assert "task seal T-001" in capsys.readouterr().err
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.OK
    assert say(monkeypatch, "task", "new", "third") == ExitCode.OK


def test_seal_can_use_an_explicit_commit_when_the_branch_is_gone(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch)
    drive_to_the_end(ws, monkeypatch)
    say(monkeypatch, "task", "approve")
    tip = git(ws, "rev-parse", "feature/T-001-t")
    git(ws, "tag", "-d", approval_tag("T-001"))
    git(ws, "switch", "-q", "develop")
    git(ws, "merge", "-q", "--no-ff", "-m", "merge", "feature/T-001-t")
    git(ws, "branch", "-d", "feature/T-001-t")
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.BRANCH_PROBLEM
    assert say(monkeypatch, "task", "seal", "T-001", "--commit", tip) == ExitCode.OK
    assert git(ws, "rev-parse", f"{approval_tag('T-001')}^{{commit}}") == tip


def test_a_failing_seal_leaves_the_task_unfinished(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch)
    drive_to_the_end(ws, monkeypatch)
    git(ws, "tag", approval_tag("T-001"))  # someone already made the tag
    assert say(monkeypatch, "task", "approve") == ExitCode.TASK_CONFLICT
    capsys.readouterr()
    main(["status"])
    assert "active task: T-001" in capsys.readouterr().out


def test_seal_rejects_unfinished_tasks(ws, monkeypatch):
    say(monkeypatch, "task", "new", "t")
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.INVALID_INPUT


def test_base_branch_follows_the_branch_prefix():
    task = Task("T-001", "x", TaskStatus.DONE, "review", StepStatus.PASSED, branch="hotfix/T-001-x")
    assert base_branch(task) == "main"
    assert base_branch(Task("T-002", "x", TaskStatus.DONE, "review", StepStatus.PASSED, branch="odd")) == "develop"


def test_summary_groups_commits_by_item():
    task = Task("T-001", "Title", TaskStatus.DONE, "review", StepStatus.PASSED, branch="feature/T-001-title")
    items = [PlanItem("C1", "One", "builder", None, "pytest", "không có — x")]
    commits = [CommitInfo("a" * 40, "T-001: one", "C1"), CommitInfo("b" * 40, "T-001: stray", None)]
    text = build_summary(task, items, commits, ["semgrep: clean"], "Me <m@x>", "2026-01-01T00:00:00Z")
    assert "### C1 - One" in text and "aaaaaaaaa T-001: one" in text
    assert "### other commits" in text and "bbbbbbbbb T-001: stray" in text
    assert "- semgrep: clean" in text and "Approved by: Me <m@x>" in text


def test_a_last_step_without_approval_is_sealed_when_it_passes(gitflow_repo, tmp_path, monkeypatch):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    main(["init", "--workflow", str(path)])
    finish_task(gitflow_repo, monkeypatch)
    drive_to_the_end(gitflow_repo, monkeypatch)
    assert git(gitflow_repo, "tag", "-l", approval_tag("T-001")) == approval_tag("T-001")


def test_summary_lists_each_items_tier_and_layer():
    from agentflow.models import Task
    from agentflow.plan import parse_plan
    from agentflow.summary import build_summary
    from agentflow.constants import StepStatus, TaskStatus

    plan = parse_plan(
        "### C1 - a\n- role: implementer\n- tier: fast\n- layer: api\n- done-when: ok\n- docs: không có — x\n"
        "### C2 - b\n- role: implementer\n- done-when: ok\n- docs: không có — x\n"
    )
    task = Task("T-001", "t", TaskStatus.DONE, "review", StepStatus.PASSED, branch="feature/t")
    text = build_summary(task, plan.items, [], [], "me", "now")
    assert "- Tier: fast\n- Layer: api" in text
    assert "- Tier: deep\n- Done when: ok" in text
