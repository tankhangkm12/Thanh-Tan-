"""Phase B3 and B4: tasks are tied to roadmap items, and `status` suggests the next item.

`agentflow task new "T" --roadmap R3` ties the task to R3 and moves R3 to `doing`. Finishing or approving a task never
moves an item to `done`: an item may need several tasks, and `done` is a person's call (`agentflow roadmap set R3 done`;
later through the replan and the last approval checklist).
"""

import json

import pytest
from conftest import git
from mcp_helpers import call
from sdd_helpers import INVALID_INPUT, ROADMAP, finish_task, init_workspace, project_dir, run, sample_workflow, say, statuses

from agentflow.mcp_server import build_server
from agentflow.models import ScanResult
from agentflow.services import WorkspaceServices
from agentflow.validation import schema_errors
from agentflow.workspace import find_workspace


@pytest.fixture(autouse=True)
def _no_container(monkeypatch):
    class Clean:
        def __init__(self, runner):
            pass

        def scan_staged(self, repo):
            return ScanResult(True, "")

    monkeypatch.setattr("agentflow.cli.ContainerGitleaksScanner", Clean)


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)
    WorkspaceServices(find_workspace(repo)).write_project("roadmap", ROADMAP)
    return repo


def state_task(repo):
    return json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][-1]


def branches(repo):
    return set(git(repo, "branch", "--format=%(refname:short)").split())


def lines_with(text, *words):
    return [line for line in text.splitlines() if all(word in line for word in words)]


# ------------------------------------------------------------- task new


def test_a_task_can_be_tied_to_a_roadmap_item(ws, capsys):
    code, out, _ = run(capsys, "task", "new", "Đặt món", "--roadmap", "R1")
    assert code == 0 and "roadmap R1" in out
    assert state_task(ws)["roadmap"] == "R1"
    assert statuses(ws) == {"R1": "doing", "R2": "todo", "R3": "todo"}


def test_the_link_is_shown_in_state_md_and_in_status(ws, capsys):
    run(capsys, "task", "new", "Đặt món", "--roadmap", "R1")
    assert "Roadmap: R1" in (ws / ".ThanhTan" / "STATE.md").read_text(encoding="utf-8")
    _, out, _ = run(capsys, "status")
    assert "roadmap: R1 - Đặt món" in out


def test_a_task_without_a_link_runs_but_warns(ws, capsys):
    code, _, err = run(capsys, "task", "new", "t")
    assert code == 0 and lines_with(err, "--roadmap")
    assert "roadmap" not in state_task(ws)
    assert statuses(ws) == {"R1": "todo", "R2": "todo", "R3": "todo"}


def test_the_link_warning_does_not_mention_the_mission(ws, capsys):
    _, _, err = run(capsys, "task", "new", "t")
    assert lines_with(err, "--roadmap")
    assert not any("mission" in line.lower() for line in lines_with(err, "--roadmap"))


@pytest.mark.parametrize("code", ["R9", "r1", "1", "banana", "R", "R1 R2"])
def test_a_link_to_something_that_is_not_an_item_is_refused_and_creates_nothing(ws, capsys, code):
    before = branches(ws)
    result, _, err = run(capsys, "task", "new", "t", "--roadmap", code)
    assert result == INVALID_INPUT and code.split()[0] in err
    assert branches(ws) == before
    assert json.loads((ws / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"] == []
    assert statuses(ws) == {"R1": "todo", "R2": "todo", "R3": "todo"}


@pytest.mark.parametrize("status", ["done", "dropped"])
def test_an_item_that_is_done_or_dropped_cannot_be_started_again(ws, capsys, status):
    run(capsys, "roadmap", "set", "R2", status)
    before = branches(ws)
    result, _, err = run(capsys, "task", "new", "t", "--roadmap", "R2")
    assert result == INVALID_INPUT and "roadmap set" in err
    assert branches(ws) == before and statuses(ws)["R2"] == status


def test_an_item_that_is_doing_may_get_another_task(ws, capsys):
    run(capsys, "roadmap", "set", "R2", "doing")
    result, out, _ = run(capsys, "task", "new", "t", "--roadmap", "R2")
    assert result == 0 and "roadmap R2" in out and statuses(ws)["R2"] == "doing"


def test_a_link_needs_a_roadmap(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)
    result, _, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert result == INVALID_INPUT and "roadmap" in err
    assert not (project_dir(repo) / "roadmap.md").exists()


def test_a_link_to_an_unconfirmed_item_warns_about_that_item(ws, capsys):
    _, _, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert lines_with(err, "R1", "unconfirmed")


def test_a_link_to_a_confirmed_item_does_not(ws, capsys):
    run(capsys, "project", "confirm", "R1")
    _, _, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert not lines_with(err, "R1", "unconfirmed")


def test_the_task_is_created_on_its_branch_whatever_the_item(ws, capsys):
    run(capsys, "task", "new", "Đặt món", "--roadmap", "R3")
    assert git(ws, "branch", "--show-current").startswith("feature/T-001-")


# ------------------------------------------------ what `task new` warns about (never blocks)

PROFILE_CONFIRMED_STEPS = ("project", "confirm", "mission")


def confirm_everything(ws, capsys):
    from sdd_helpers import PROFILE

    WorkspaceServices(find_workspace(ws)).write_project("profile", PROFILE)
    assert run(capsys, *PROFILE_CONFIRMED_STEPS, "R1", "R2", "R3")[0] == 0


def test_the_roadmap_missing_is_a_warning_not_an_error(gitflow_repo, tmp_path, monkeypatch, capsys):
    init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)
    code, _, err = run(capsys, "task", "new", "t")
    assert code == 0 and lines_with(err, "roadmap", "missing")


def test_unconfirmed_roadmap_items_are_listed_in_one_warning(ws, capsys):
    run(capsys, "project", "confirm", "R2")
    code, _, err = run(capsys, "task", "new", "t", "--roadmap", "R2")
    line = lines_with(err, "roadmap", "unconfirmed", "R1")
    assert code == 0 and line and "R3" in line[0] and "R2" not in line[0]


def test_the_warning_about_a_linked_item_says_that_the_link_is_to_an_unconfirmed_item(ws, capsys):
    run(capsys, "project", "confirm", "R2", "R3")
    code, _, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert code == 0 and lines_with(err, "R1", "unconfirmed", "linked")


def test_a_link_to_a_confirmed_item_gets_no_linked_item_warning(ws, capsys):
    run(capsys, "project", "confirm", "R1")
    _, _, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert not lines_with(err, "linked")


def test_a_mission_a_roadmap_and_a_link_that_are_all_confirmed_give_no_warning_at_all(ws, capsys):
    confirm_everything(ws, capsys)
    code, out, err = run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert code == 0 and "roadmap R1" in out and err == ""


def test_each_missing_piece_brings_back_its_own_warning(ws, capsys):
    confirm_everything(ws, capsys)
    _, _, err = run(capsys, "task", "new", "t")
    assert lines_with(err, "--roadmap") and not lines_with(err, "mission") and not lines_with(err, "unconfirmed")


def test_warnings_never_stop_the_task_from_being_created(ws, capsys):
    code, out, err = run(capsys, "task", "new", "t")
    assert code == 0 and "T-001 created" in out
    assert lines_with(err, "mission") and lines_with(err, "roadmap") and lines_with(err, "--roadmap")


# ------------------------------------------------- finishing never closes an item


def test_approving_the_last_step_leaves_the_item_doing_and_the_summary_names_it(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch, "dat-mon", "--roadmap", "R1")
    assert statuses(ws)["R1"] == "doing"
    summary = (ws / ".ThanhTan" / "tasks" / "T-001" / "summary.md").read_text(encoding="utf-8")
    assert "- Roadmap: R1 - Đặt món" in summary


def test_a_second_task_for_the_same_item_after_the_first_is_done(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch, "phan-mot", "--roadmap", "R1")
    capsys.readouterr()
    assert say(monkeypatch, "task", "new", "phan-hai", "--roadmap", "R1") == 0
    assert statuses(ws)["R1"] == "doing" and state_task(ws)["roadmap"] == "R1"


def test_a_person_closes_the_item_and_it_cannot_be_started_again(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch, "phan-mot", "--roadmap", "R1")
    run(capsys, "roadmap", "set", "R1", "done")
    assert say(monkeypatch, "task", "new", "phan-hai", "--roadmap", "R1") == INVALID_INPUT


# ------------------------------------------------------------------ cancelling


def test_cancelling_the_only_task_of_an_item_puts_it_back_to_todo(ws, capsys):
    run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert statuses(ws)["R1"] == "doing"
    code, _, _ = run(capsys, "task", "cancel")
    assert code == 0 and statuses(ws)["R1"] == "todo"


def test_cancelling_a_later_task_leaves_an_item_that_earlier_work_started_doing(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch, "phan-mot", "--roadmap", "R1")
    say(monkeypatch, "task", "new", "phan-hai", "--roadmap", "R1")
    capsys.readouterr()
    assert say(monkeypatch, "task", "cancel") == 0
    assert statuses(ws)["R1"] == "doing"


def test_cancelling_a_task_without_a_link_touches_no_item(ws, capsys):
    run(capsys, "roadmap", "set", "R2", "doing")
    run(capsys, "task", "new", "t")
    run(capsys, "task", "cancel")
    assert statuses(ws) == {"R1": "todo", "R2": "doing", "R3": "todo"}


# ------------------------------------------------------------- the state file

STATE_SCHEMA = "state.schema.json"


def task_data(**changes):
    task = {
        "id": "T-001", "title": "t", "status": "open", "current_step": "build", "step_status": "in_progress",
        "loop_round": 0, "branch": "feature/T-001-t", "history": [],
    }
    task.update(changes)
    return {"schema_version": 1, "updated_at": "2026-10-10T08:00:00Z", "active_task_id": "T-001", "tasks": [task]}


def test_the_state_schema_accepts_a_roadmap_link_and_still_accepts_tasks_without_one():
    assert schema_errors(task_data(roadmap="R12"), STATE_SCHEMA) == []
    assert schema_errors(task_data(), STATE_SCHEMA) == []


@pytest.mark.parametrize("value", ["x", "r1", "R", "R1 R2", 1, None, ""])
def test_the_state_schema_refuses_a_roadmap_link_that_is_not_an_item_code(value):
    assert schema_errors(task_data(roadmap="R1"), STATE_SCHEMA) == []  # the field exists; only its value is wrong
    assert schema_errors(task_data(roadmap=value), STATE_SCHEMA) != []


# ------------------------------------------------------------------ B4: status


def test_status_suggests_the_first_todo_item_in_file_order(ws, capsys):
    _, out, err = run(capsys, "status")
    assert "next roadmap: R1 - Đặt món (unconfirmed)" in out


def next_line(capsys):
    _, out, _ = run(capsys, "status")
    found = lines_with(out, "next roadmap:")
    return found[0] if found else None


def test_the_suggestion_skips_dropped_and_done_items(ws, capsys):
    run(capsys, "roadmap", "set", "R1", "dropped")
    run(capsys, "roadmap", "set", "R2", "done")
    assert next_line(capsys) == "next roadmap: R3 - Báo bếp (unconfirmed)"


def test_an_item_that_is_doing_with_no_open_task_comes_before_any_todo_item(ws, capsys):
    run(capsys, "roadmap", "set", "R2", "doing")
    assert next_line(capsys) == "next roadmap: R2 - Thanh toán (unconfirmed)"


def test_among_several_doing_items_the_first_in_the_file_wins(ws, capsys):
    run(capsys, "roadmap", "set", "R3", "doing")
    run(capsys, "roadmap", "set", "R2", "doing")
    assert next_line(capsys) == "next roadmap: R2 - Thanh toán (unconfirmed)"


def test_the_item_of_the_open_task_is_not_suggested_again(ws, capsys):
    run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert next_line(capsys) == "next roadmap: R2 - Thanh toán (unconfirmed)"


def test_another_doing_item_is_still_suggested_while_a_task_runs(ws, capsys):
    run(capsys, "roadmap", "set", "R3", "doing")
    run(capsys, "task", "new", "t", "--roadmap", "R1")
    assert next_line(capsys) == "next roadmap: R3 - Báo bếp (unconfirmed)"


def test_a_doing_item_is_suggested_again_once_its_task_is_done(ws, monkeypatch, capsys):
    finish_task(ws, monkeypatch, "phan-mot", "--roadmap", "R2")
    capsys.readouterr()
    assert next_line(capsys) == "next roadmap: R2 - Thanh toán (unconfirmed)"


def test_a_doing_item_the_open_task_is_not_linked_to_is_suggested(ws, capsys):
    run(capsys, "roadmap", "set", "R1", "doing")
    run(capsys, "task", "new", "t")
    assert next_line(capsys) == "next roadmap: R1 - Đặt món (unconfirmed)"


def test_a_confirmed_doing_item_is_suggested_without_the_note(ws, capsys):
    run(capsys, "project", "confirm", "R3")
    run(capsys, "roadmap", "set", "R3", "doing")
    assert next_line(capsys) == "next roadmap: R3 - Báo bếp"


def test_a_blocked_task_still_counts_as_an_open_task(ws, capsys):
    run(capsys, "task", "new", "t", "--roadmap", "R1")
    run(capsys, "task", "advance", "--result", "fail")  # the sample workflow has no way back from `confirm`: the task blocks
    _, out, _ = run(capsys, "status")
    assert "blocked" in out
    assert next_line(capsys) == "next roadmap: R2 - Thanh toán (unconfirmed)"


def test_there_is_no_suggestion_when_no_item_is_todo(ws, capsys):
    for code in ("R1", "R2", "R3"):
        run(capsys, "roadmap", "set", code, "done")
    _, out, _ = run(capsys, "status")
    assert "next roadmap" not in out


def test_there_is_no_roadmap_line_and_no_warning_in_a_project_without_a_roadmap(gitflow_repo, tmp_path, monkeypatch, capsys):
    init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)
    code, out, err = run(capsys, "status")
    assert code == 0 and err == ""
    assert not [line for line in out.splitlines() if line.startswith(("roadmap", "next roadmap"))]


def test_the_suggestion_is_shown_while_a_task_runs(ws, capsys):
    run(capsys, "task", "new", "t", "--roadmap", "R1")
    _, out, _ = run(capsys, "status")
    assert "roadmap: R1 - Đặt món" in out and "next roadmap: R2 - Thanh toán" in out


def test_the_status_service_and_the_mcp_tool_carry_the_suggestion(ws):
    service = WorkspaceServices(find_workspace(ws))
    assert service.status().next_roadmap == "R1 - Đặt món (unconfirmed)"
    server = build_server(service)
    assert call(server, "status").structured_content["next_roadmap"] == "R1 - Đặt món (unconfirmed)"


def test_the_status_of_a_linked_task_reaches_the_service(ws, capsys):
    run(capsys, "task", "new", "t", "--roadmap", "R2")
    info = WorkspaceServices(find_workspace(ws)).status()
    assert info.active_task.roadmap == "R2"
