"""A fast hotfix: a task type picks its own default size, and a hotfix tells the person how to merge it.

- A workflow's ``types`` section may give a type ``size: <profile>``: a task of that type gets that size unless
  ``--size`` names another one. The size must be one of the workflow's profiles.
- dev-core's workflow gives ``hotfix`` the size ``hotfix``: no approval of the plan, at most 3 plan items, and every scan
  (the change goes straight to main). Confirm, test-spec and review still need a person.
- ``task new --type hotfix`` does not warn that the task is not tied to a roadmap item: a hotfix is unplanned work.
- A finished hotfix lists, in summary.md and on the command line, the commands a person runs to merge it into main
  (with a tag) and back into develop. agentflow never runs them.
"""

import copy
import io
from pathlib import Path

import pytest
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow.cli import main
from agentflow.constants import ExitCode, StepStatus, TaskEvent, TaskStatus
from agentflow.engine import needs_approval, start_task, transition
from agentflow.models import CommitInfo, Task, workflow_from_dict
from agentflow.summary import build_summary
from agentflow.tasks import resolve_size
from agentflow.workflow import load_workflow, parse_workflow

REAL_WORKFLOW = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core" / "workflow.yaml"

SIZES = {
    "default": "normal",
    "profiles": {
        "normal": {},
        "small": {"skip_approval": ["plan"], "max_plan_items": 3},
        "hotfix": {"skip_approval": ["plan"], "max_plan_items": 3},
    },
}

PLAN = """### C1 - Fix it
- role: builder
- files: a.txt
- done-when: `true`
- docs: không có — a one-line fix
"""


def workflow_data(**changes):
    data = copy.deepcopy(SAMPLE_WORKFLOW)
    data["steps"] = [
        {"id": "confirm", "name": "Confirm", "role": "lead", "requires_approval": True},
        {"id": "plan", "name": "Plan", "role": "lead", "requires_approval": True, "gates": ["plan-valid"]},
        {"id": "build", "name": "Build", "role": "builder"},
        {"id": "check", "name": "Check", "role": "checker", "on_fail": "build", "requires_approval": True},
    ]
    data["sizes"] = copy.deepcopy(SIZES)
    data["types"] = {"hotfix": {"size": "hotfix"}}
    data.update(changes)
    return data


# ------------------------------------------------------------------ the workflow


def test_a_type_may_name_its_default_size():
    workflow = parse_workflow(workflow_data(), "w")
    assert workflow.type_sizes == {"hotfix": "hotfix"}
    assert parse_workflow(workflow_data(types={}), "w").type_sizes == {}


def test_a_type_size_can_sit_next_to_its_test_spec_mode():
    workflow = parse_workflow(workflow_data(types={"chore": {"test_spec": "green", "size": "small"}}), "w")
    assert workflow.type_sizes == {"chore": "small"}
    assert str(workflow.test_spec_modes["chore"]) == "green"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (workflow_data(types={"hotfix": {"size": "huge"}}), "size 'huge'"),
        (workflow_data(types={"hotfix": {"size": 3}}), "invalid workflow"),
        ({**workflow_data(types={"hotfix": {"size": "hotfix"}}), "sizes": {}}, "size 'hotfix'"),
    ],
)
def test_a_type_size_must_be_one_of_the_profiles(data, message):
    if not data.get("sizes"):
        data.pop("sizes", None)
    with pytest.raises(Exception, match=message):
        parse_workflow(data, "w")


# ------------------------------------------------------------------ the size a task gets


def test_a_hotfix_gets_the_size_its_type_names():
    workflow = workflow_from_dict(workflow_data())
    assert resolve_size(workflow, None, "hotfix") == "hotfix"


def test_a_size_asked_for_wins_over_the_types():
    workflow = workflow_from_dict(workflow_data())
    assert resolve_size(workflow, "normal", "hotfix") == "normal"
    assert resolve_size(workflow, "small", "hotfix") == "small"


def test_a_type_without_a_size_gets_the_workflow_default():
    workflow = workflow_from_dict(workflow_data())
    assert resolve_size(workflow, None, "feature") == "normal"
    assert resolve_size(workflow, None, None) == "normal"


def test_the_hotfix_size_skips_only_the_approval_of_the_plan():
    workflow = workflow_from_dict(workflow_data())
    task = start_task(workflow, "T-001", "t", None, "2026-01-01T00:00:00Z", "hotfix", None, "hotfix")
    task = transition(workflow, task, TaskEvent.PASS, "t")
    assert task.step_status is StepStatus.AWAITING_APPROVAL and task.current_step == "confirm"
    task = transition(workflow, task, TaskEvent.APPROVE, "t")
    task = transition(workflow, task, TaskEvent.PASS, "t")  # the plan: no approval
    assert task.current_step == "build" and task.step_status is StepStatus.IN_PROGRESS
    assert needs_approval(workflow, task, workflow.get_step("check"))


# ------------------------------------------------------------------ dev-core's workflow


def test_dev_core_gives_a_hotfix_its_own_size():
    workflow = load_workflow(REAL_WORKFLOW)
    assert workflow.type_sizes.get("hotfix") == "hotfix"
    profile = workflow.size_profile("hotfix")
    assert profile is not None
    assert profile.skip_approval == ("plan",)
    assert profile.max_plan_items == 3
    assert dict(profile.scans) == {}  # every scan: the change goes straight to main


def test_dev_core_hotfix_still_needs_a_person_at_confirm_test_spec_and_review():
    workflow = load_workflow(REAL_WORKFLOW)
    task = start_task(workflow, "T-001", "t", None, "2026-01-01T00:00:00Z", "hotfix", None, "hotfix")
    waits = {step.id for step in workflow.steps if needs_approval(workflow, task, step)}
    assert waits == {"confirm", "test-spec", "review"}


def test_dev_core_other_types_keep_the_normal_size():
    workflow = load_workflow(REAL_WORKFLOW)
    for task_type in ("feature", "bugfix", "refactor", "chore"):
        assert resolve_size(workflow, None, task_type) == "normal", task_type


# ------------------------------------------------------------------ the summary


def hotfix_task(**changes):
    values = {"branch": "hotfix/T-001-fix-login", "type": "hotfix", "size": "hotfix"}
    values.update(changes)
    return Task("T-001", "Fix login", TaskStatus.DONE, "check", StepStatus.PASSED, **values)


def summary_of(task):
    return build_summary(task, [], [CommitInfo("a" * 40, "T-001: fix", None)], [], "Me <m@x>", "2026-01-01T00:00:00Z")


def test_a_hotfix_summary_lists_the_merge_commands_in_order():
    text = summary_of(hotfix_task())
    assert "## Merge the hotfix" in text
    commands = [
        "git switch main",
        "git merge --no-ff hotfix/T-001-fix-login",
        "git tag -a v",
        "git switch develop",
        "git merge --no-ff hotfix/T-001-fix-login",
    ]
    position = 0
    for command in commands:
        found = text.find(command, position)
        assert found >= 0, command
        position = found + len(command)
    assert "a person" in text.split("## Merge the hotfix", 1)[1]


def test_other_summaries_have_no_merge_section():
    task = hotfix_task(branch="feature/T-001-fix-login", type="feature", size="normal")
    assert "## Merge the hotfix" not in summary_of(task)
    assert "## Merge the hotfix" not in summary_of(hotfix_task(type=None))


# ------------------------------------------------------------------ the commands


@pytest.fixture(autouse=True)
def _no_container(monkeypatch):
    from agentflow.models import ScanResult

    class Clean:
        def __init__(self, runner):
            pass

        def scan_staged(self, repo):
            return ScanResult(True, "")

    monkeypatch.setattr("agentflow.cli.ContainerGitleaksScanner", Clean)


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", workflow_data())
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def say(monkeypatch, *argv, text=None):
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def test_task_new_hotfix_gets_the_hotfix_size_and_branches_from_main(ws, capsys):
    assert main(["task", "new", "fix login", "--type", "hotfix"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "on branch hotfix/T-001-fix-login" in out and "(size hotfix)" in out
    assert git(ws, "merge-base", "HEAD", "main") == git(ws, "rev-parse", "main")


def test_task_new_hotfix_with_a_size_keeps_that_size(ws, capsys):
    assert main(["task", "new", "fix login", "--type", "hotfix", "--size", "normal"]) == ExitCode.OK
    assert "(size normal)" in capsys.readouterr().out


def test_a_hotfix_is_not_warned_about_a_missing_roadmap_item(ws, capsys):
    assert main(["task", "new", "fix login", "--type", "hotfix"]) == ExitCode.OK
    assert "not tied to a roadmap item" not in capsys.readouterr().err


def test_a_feature_is_still_warned_about_a_missing_roadmap_item(ws, capsys):
    assert main(["task", "new", "add export"]) == ExitCode.OK
    assert "not tied to a roadmap item" in capsys.readouterr().err


def finish_hotfix(ws, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "fix login", "--type", "hotfix") == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")  # confirm -> plan
    say(monkeypatch, "report", "--step", "plan", text=PLAN)
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK  # plan -> build, no approval
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    git(ws, "add", "a.txt")
    assert say(monkeypatch, "commit", "fix login", "--item", "C1") == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")  # build -> check
    say(monkeypatch, "task", "advance", "--result", "pass")  # check -> awaiting approval
    capsys.readouterr()
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    return capsys.readouterr().out


def test_finishing_a_hotfix_prints_the_merge_commands(ws, monkeypatch, capsys):
    out = finish_hotfix(ws, monkeypatch, capsys)
    assert "git merge --no-ff hotfix/T-001-fix-login" in out
    assert "git switch develop" in out and "git switch main" in out


def test_finishing_a_hotfix_writes_the_merge_commands_to_the_summary(ws, monkeypatch, capsys):
    finish_hotfix(ws, monkeypatch, capsys)
    summary = (ws / ".ThanhTan" / "tasks" / "T-001" / "summary.md").read_text(encoding="utf-8")
    assert "## Merge the hotfix" in summary and "git merge --no-ff hotfix/T-001-fix-login" in summary


def test_agentflow_merges_nothing_itself(ws, monkeypatch, capsys):
    main_before = git(ws, "rev-parse", "main")
    develop_before = git(ws, "rev-parse", "develop")
    finish_hotfix(ws, monkeypatch, capsys)
    assert git(ws, "rev-parse", "main") == main_before
    assert git(ws, "rev-parse", "develop") == develop_before
