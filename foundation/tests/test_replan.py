"""Phase C2 and C3: the replan, the step between one task and the next.

After a task is done and sealed, the scout updates the project documents from what the task really did and writes
`.ThanhTan/tasks/<task>/replan.md` (through `thanhtan replan write` or the MCP tool `replan_write`). A person confirms
the documents and moves roadmap items (`thanhtan roadmap set R1 done`); the replan only PROPOSES which items are done.

    thanhtan replan status                  read-only: replan: no-finished-task | task-open | not-sealed | pending | proposed | done | skipped
    thanhtan replan write                   (stdin) the replan of the latest finished task: it is only PROPOSED
    thanhtan replan done                    for a person, after reading replan.md: the replan is done
    thanhtan replan skip T-001 --reason ..  for a person: decide not to replan, on purpose

A replan that an agent wrote stays `proposed` until a person runs `replan done`: only then is the task marked replanned
(`replanned_at`), the summary says done and the `removed:` lines of `project status` go.
`thanhtan task new` warns (never blocks) while the latest finished task is `pending` or `proposed`.
"""

import json
import re

import pytest
from conftest import git
from mcp_helpers import call, tool_list
from replan_helpers import (
    NOTHING_DONE,
    REPLAN,
    REPLAN_DATE,
    review_report,
    run,
    run_task,
    say,
    start_workspace,
    summary,
    task_dir,
    write_project_file,
)
from sdd_helpers import PROFILE, ROADMAP, statuses

from thanhtan.constants import STATE_SCHEMA_FILE, ExitCode, GuardDecision, GuardRule
from thanhtan.guard import evaluate
from thanhtan.mcp_server import build_server
from thanhtan.seal import approval_tag
from thanhtan.services import WorkspaceServices
from thanhtan.validation import schema_errors
from thanhtan.workspace import find_workspace

INVALID_INPUT = 22
REPORT_REFUSED = 30
PROJECT_WRITE_REFUSED = 31
TASK_NOT_SEALED = 26


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    write_project_file(repo, "roadmap.md", ROADMAP)
    return repo


@pytest.fixture
def finished(ws, monkeypatch, capsys):
    """T-001 is done and sealed; it served R1."""
    run_task(ws, monkeypatch, review=review_report(), extra=("--roadmap", "R1"))
    capsys.readouterr()
    return ws


def status_lines(capsys) -> list[str]:
    code, out, _ = run(capsys, "replan", "status")
    assert code == ExitCode.OK
    return out.strip().splitlines()


def write_replan(capsys, monkeypatch, text=REPLAN):
    return run(capsys, "replan", "write", text=text, monkeypatch=monkeypatch)


def confirm_replan(capsys):
    """What a person runs after reading replan.md."""
    return run(capsys, "replan", "done")


def history_of_replan(repo, task_id="T-001"):
    folder = repo / ".ThanhTan" / "project" / "history"
    return sorted(folder.glob(f"replan-{task_id}-*.md")) if folder.is_dir() else []


def state_task(repo, index=0):
    return json.loads((repo / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][index]


# ----------------------------------------------------------------------- status


def test_status_without_a_finished_task(ws, capsys):
    assert status_lines(capsys) == ["replan: no-finished-task"]


def test_status_of_a_finished_task_that_was_not_replanned(finished, capsys):
    assert status_lines(capsys) == ["replan: pending", "task: T-001"]


def test_status_with_a_task_open_names_the_open_task(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    capsys.readouterr()
    assert status_lines(capsys) == ["replan: task-open", "task: T-002"]


def test_a_blocked_task_counts_as_open(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    say(monkeypatch, "task", "advance", "--result", "fail")  # `confirm` has no way back: the task blocks
    capsys.readouterr()
    assert status_lines(capsys) == ["replan: task-open", "task: T-002"]


def test_an_open_task_wins_over_an_older_task_that_was_not_replanned(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    capsys.readouterr()
    assert status_lines(capsys)[0] == "replan: task-open"


def test_status_of_a_finished_task_whose_tag_is_missing(finished, capsys):
    git(finished, "tag", "-d", approval_tag("T-001"))
    assert status_lines(capsys) == ["replan: not-sealed", "task: T-001"]


def test_status_after_the_replan_was_written_is_proposed_not_done(finished, monkeypatch, capsys):
    assert write_replan(capsys, monkeypatch)[0] == ExitCode.OK
    assert status_lines(capsys) == ["replan: proposed", "task: T-001"]


def test_status_after_a_person_confirmed_the_replan(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert confirm_replan(capsys)[0] == ExitCode.OK
    assert status_lines(capsys) == ["replan: done", "task: T-001"]


def test_status_after_a_person_skipped_the_replan(finished, capsys):
    assert run(capsys, "replan", "skip", "T-001", "--reason", "only a typo fix")[0] == ExitCode.OK
    assert status_lines(capsys) == ["replan: skipped", "task: T-001"]


def test_status_looks_at_the_latest_finished_task_only(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    run_task(finished, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    assert status_lines(capsys) == ["replan: pending", "task: T-002"]


def test_a_cancelled_task_does_not_hide_the_finished_one(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "abandoned")
    say(monkeypatch, "task", "cancel")
    git(finished, "switch", "-q", "develop")
    capsys.readouterr()
    assert status_lines(capsys) == ["replan: pending", "task: T-001"]


def test_status_changes_nothing(finished, capsys):
    before = {path: path.read_bytes() for path in (finished / ".ThanhTan").rglob("*") if path.is_file()}
    status_lines(capsys)
    assert {path: path.read_bytes() for path in (finished / ".ThanhTan").rglob("*") if path.is_file()} == before


# ------------------------------------------------------------------ writing it


def test_the_replan_is_saved_in_the_folder_of_the_finished_task(finished, monkeypatch, capsys):
    code, out, _ = write_replan(capsys, monkeypatch)
    assert code == ExitCode.OK and "replan.md" in out
    assert (task_dir(finished) / "replan.md").read_text(encoding="utf-8") == REPLAN


def test_a_missing_final_newline_is_added_and_windows_line_ends_are_not_kept(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch, REPLAN.rstrip("\n").replace("\n", "\r\n"))
    raw = (task_dir(finished) / "replan.md").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")


def test_writing_does_not_mark_the_task_replanned(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert "replanned_at" not in state_task(finished)


def test_confirming_marks_the_task_replanned_in_its_state(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    assert re.match(r"\d{4}-\d{2}-\d{2}T", state_task(finished)["replanned_at"])


def test_a_task_not_replanned_has_no_replanned_at_in_its_state(finished):
    """Regression: the state of a task stays as before until something replans it."""
    task = json.loads((finished / ".ThanhTan" / "state.json").read_text(encoding="utf-8"))["tasks"][0]
    assert "replanned_at" not in task


def test_the_summary_follows_the_replan_from_pending_to_proposed_to_done(finished, monkeypatch, capsys):
    assert "- Replan: pending" in summary(finished).splitlines()
    write_replan(capsys, monkeypatch)
    assert "- Replan: proposed" in summary(finished).splitlines()
    confirm_replan(capsys)
    line = next(line for line in summary(finished).splitlines() if line.startswith("- Replan:"))
    assert re.fullmatch(r"- Replan: done \(\d{4}-\d{2}-\d{2}\)", line), line
    assert summary(finished).count("- Replan:") == 1


def test_writing_a_second_time_replaces_the_file_and_keeps_the_first_in_the_history(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert write_replan(capsys, monkeypatch, NOTHING_DONE)[0] == ExitCode.OK
    assert (task_dir(finished) / "replan.md").read_text(encoding="utf-8") == NOTHING_DONE
    assert [path.read_text(encoding="utf-8") for path in history_of_replan(finished)] == [REPLAN]
    assert status_lines(capsys)[0] == "replan: proposed"


def test_the_first_write_leaves_no_history(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert history_of_replan(finished) == []


def test_every_older_version_is_kept_even_when_written_within_the_same_second(finished, monkeypatch, capsys):
    monkeypatch.setattr("thanhtan.project.utc_now", lambda: "2026-10-17T10:00:00Z")
    versions = [REPLAN, NOTHING_DONE, REPLAN.replace("smoke", "lint")]
    for text in versions:
        write_replan(capsys, monkeypatch, text)
    assert (task_dir(finished) / "replan.md").read_text(encoding="utf-8") == versions[2]
    assert sorted(path.read_text(encoding="utf-8") for path in history_of_replan(finished)) == sorted(versions[:2])


def test_writing_the_same_text_again_keeps_no_history(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    write_replan(capsys, monkeypatch)
    assert history_of_replan(finished) == []


def test_the_history_is_per_task(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    write_replan(capsys, monkeypatch, NOTHING_DONE)
    confirm_replan(capsys)
    run_task(finished, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    write_replan(capsys, monkeypatch)
    write_replan(capsys, monkeypatch, NOTHING_DONE)
    assert len(history_of_replan(finished, "T-001")) == 1 and len(history_of_replan(finished, "T-002")) == 1


def test_the_replan_goes_to_the_latest_finished_task_and_leaves_the_earlier_one_alone(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    first = (task_dir(finished, "T-001") / "replan.md").read_text(encoding="utf-8")
    run_task(finished, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    assert write_replan(capsys, monkeypatch, NOTHING_DONE)[0] == ExitCode.OK
    assert (task_dir(finished, "T-002") / "replan.md").read_text(encoding="utf-8") == NOTHING_DONE
    assert (task_dir(finished, "T-001") / "replan.md").read_text(encoding="utf-8") == first


def test_a_replan_can_still_be_written_after_it_was_skipped(finished, monkeypatch, capsys):
    run(capsys, "replan", "skip", "T-001", "--reason", "changed my mind later")
    assert write_replan(capsys, monkeypatch)[0] == ExitCode.OK
    assert status_lines(capsys)[0] == "replan: proposed"


def test_a_replan_a_person_confirmed_cannot_be_written_again(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    code, _, err = write_replan(capsys, monkeypatch, NOTHING_DONE)
    assert code == INVALID_INPUT and "done" in err
    assert (task_dir(finished) / "replan.md").read_text(encoding="utf-8") == REPLAN
    assert history_of_replan(finished) == []


def test_the_replan_never_moves_a_roadmap_item_it_only_proposes(finished, monkeypatch, capsys):
    assert statuses(finished)["R1"] == "doing"
    write_replan(capsys, monkeypatch)  # the replan names R1 as done
    assert statuses(finished)["R1"] == "doing"


def test_a_person_closes_the_item_after_reading_the_proposal(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert run(capsys, "roadmap", "set", "R1", "done")[0] == ExitCode.OK
    assert statuses(finished)["R1"] == "done"


def drop_confirmed_item_r2(finished, capsys):
    run(capsys, "project", "confirm", "R2")
    service = WorkspaceServices(find_workspace(finished))
    service.write_project("roadmap", ROADMAP.split("### R2")[0] + "### R3" + ROADMAP.split("### R3")[1])  # the scout dropped R2
    assert "removed: R2 (confirmed)" in run(capsys, "project", "status")[1]


def test_writing_leaves_the_removed_lines_for_the_person_to_see(finished, monkeypatch, capsys):
    drop_confirmed_item_r2(finished, capsys)
    write_replan(capsys, monkeypatch)
    assert "removed: R2 (confirmed)" in run(capsys, "project", "status")[1]


def test_confirming_the_replan_clears_the_removed_lines(finished, monkeypatch, capsys):
    drop_confirmed_item_r2(finished, capsys)
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    assert "removed:" not in run(capsys, "project", "status")[1]


def test_a_failed_write_leaves_the_removed_lines_and_the_state_alone(finished, monkeypatch, capsys):
    run(capsys, "project", "confirm", "R2")
    service = WorkspaceServices(find_workspace(finished))
    service.write_project("roadmap", ROADMAP.split("### R2")[0] + "### R3" + ROADMAP.split("### R3")[1])
    state_before = (finished / ".ThanhTan" / "state.json").read_bytes()
    assert write_replan(capsys, monkeypatch, "# Replan\n\nno sections\n")[0] == REPORT_REFUSED
    assert "removed: R2 (confirmed)" in run(capsys, "project", "status")[1]
    assert (finished / ".ThanhTan" / "state.json").read_bytes() == state_before
    assert not (task_dir(finished) / "replan.md").exists()


# ------------------------------------------------------- a person says the replan is done


def test_done_needs_a_proposed_replan_and_changes_nothing_otherwise(finished, capsys):
    before = {path: path.read_bytes() for path in (finished / ".ThanhTan").rglob("*") if path.is_file()}
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "pending" in err
    assert {path: path.read_bytes() for path in (finished / ".ThanhTan").rglob("*") if path.is_file()} == before


def test_done_says_which_task_it_closed(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    code, out, _ = confirm_replan(capsys)
    assert code == ExitCode.OK and "T-001" in out


def test_done_cannot_be_run_twice(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "done" in err


def test_done_is_refused_after_the_replan_was_skipped(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    run(capsys, "replan", "skip", "T-001", "--reason", "not worth it")
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "skipped" in err


def test_done_is_refused_while_a_task_is_open(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    say(monkeypatch, "task", "new", "next one")
    capsys.readouterr()
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "task-open" in err
    assert "replanned_at" not in state_task(finished)


def test_done_is_refused_while_the_finished_task_has_no_approval_tag(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    git(finished, "tag", "-d", approval_tag("T-001"))
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "not-sealed" in err


def test_done_is_refused_when_no_task_is_finished(ws, capsys):
    code, _, err = confirm_replan(capsys)
    assert code == INVALID_INPUT and "no-finished-task" in err


def test_done_never_moves_a_roadmap_item(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    assert statuses(finished)["R1"] == "doing"  # the person closes it with `roadmap set R1 done`


def test_done_applies_to_the_latest_finished_task_only(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    run_task(finished, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    write_replan(capsys, monkeypatch, NOTHING_DONE)
    confirm_replan(capsys)
    assert "replanned_at" not in state_task(finished, 0) and "replanned_at" in state_task(finished, 1)


# ------------------------------------------------------------ when it is refused


def test_it_is_refused_while_a_task_is_open(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    capsys.readouterr()
    code, _, err = write_replan(capsys, monkeypatch)
    assert code == PROJECT_WRITE_REFUSED and "T-002" in err and "open" in err
    assert not (task_dir(finished) / "replan.md").exists()


def test_it_is_refused_while_a_task_is_blocked(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    say(monkeypatch, "task", "advance", "--result", "fail")
    capsys.readouterr()
    assert write_replan(capsys, monkeypatch)[0] == PROJECT_WRITE_REFUSED


def test_it_is_refused_when_no_task_is_finished(ws, monkeypatch, capsys):
    code, _, err = write_replan(capsys, monkeypatch)
    assert code == INVALID_INPUT and "finished" in err


def test_it_is_refused_while_the_finished_task_has_no_approval_tag(finished, monkeypatch, capsys):
    git(finished, "tag", "-d", approval_tag("T-001"))
    code, _, err = write_replan(capsys, monkeypatch)
    assert code == TASK_NOT_SEALED and "task seal T-001" in err


@pytest.mark.parametrize("text", ["", "   \n\n"])
def test_an_empty_replan_is_refused(finished, monkeypatch, capsys, text):
    assert write_replan(capsys, monkeypatch, text)[0] == INVALID_INPUT


@pytest.mark.parametrize(
    ("text", "named"),
    [
        (REPLAN.replace("## Mục roadmap đã hoàn thành", "## Việc khác"), "Mục roadmap đã hoàn thành"),
        (REPLAN.replace("## Đề xuất cải tiến quy trình", "## Việc khác"), "Đề xuất cải tiến quy trình"),
        ("# Replan\n\n```\n## Mục roadmap đã hoàn thành\n- R1: x\n```\n\n## Đề xuất cải tiến quy trình\nkhông có\n", "Mục roadmap đã hoàn thành"),
        ("# Replan\n\n## Mục roadmap đã hoàn thành\n\n## Đề xuất cải tiến quy trình\nkhông có\n", "Mục roadmap đã hoàn thành"),
        ("# Replan\n\n## Mục roadmap đã hoàn thành\nkhông có\n\n## Đề xuất cải tiến quy trình\n\n", "Đề xuất cải tiến quy trình"),
    ],
    ids=["no roadmap section", "no process section", "section only inside a code block", "empty roadmap section", "empty process section"],
)
def test_a_replan_without_both_sections_filled_in_is_refused_and_says_which(finished, monkeypatch, capsys, text, named):
    code, _, err = write_replan(capsys, monkeypatch, text)
    assert code == REPORT_REFUSED and named in err
    assert not (task_dir(finished) / "replan.md").exists()


@pytest.mark.parametrize(
    ("done_section", "problem"),
    [
        ("- R9: xong rồi", "R9"),
        ("- R1:", "R1"),
        ("- R1", "R1"),
        ("R1 đã xong", "bullet"),
        ("- Q1: không phải mục roadmap", "Q1"),
    ],
    ids=["unknown item", "no evidence", "no colon", "prose", "not an item code"],
)
def test_the_list_of_finished_items_must_name_real_items_with_their_evidence(finished, monkeypatch, capsys, done_section, problem):
    text = REPLAN.replace("- R1: summary.md của T-001 ghi C1 đã xong và test chạy xanh.", done_section)
    code, _, err = write_replan(capsys, monkeypatch, text)
    assert code == REPORT_REFUSED and problem in err


@pytest.mark.parametrize("none_text", ["không có", "Không có.", "KHÔNG CÓ"])
def test_nothing_finished_is_said_with_khong_co_in_any_case(finished, monkeypatch, capsys, none_text):
    text = NOTHING_DONE.replace("không có", none_text, 1)
    assert write_replan(capsys, monkeypatch, text)[0] == ExitCode.OK


@pytest.mark.parametrize("none_text", ["không có", "Không có.", "KHÔNG CÓ"])
def test_no_process_proposal_is_said_with_khong_co_too(finished, monkeypatch, capsys, none_text):
    text = REPLAN.replace('- Thêm ô kiểm "chạy lại smoke" vào checklist của bước review.', none_text)
    assert write_replan(capsys, monkeypatch, text)[0] == ExitCode.OK


def test_only_an_empty_process_section_is_refused(finished, monkeypatch, capsys):
    text = REPLAN.replace('- Thêm ô kiểm "chạy lại smoke" vào checklist của bước review.', "")
    code, _, err = write_replan(capsys, monkeypatch, text)
    assert code == REPORT_REFUSED and "Đề xuất cải tiến quy trình" in err


def test_the_process_section_may_be_free_text(finished, monkeypatch, capsys):
    text = REPLAN.replace('- Thêm ô kiểm "chạy lại smoke" vào checklist của bước review.', "Giữ nguyên quy trình, nhưng xem lại thời gian chạy smoke.")
    assert write_replan(capsys, monkeypatch, text)[0] == ExitCode.OK


def test_any_item_of_the_roadmap_can_be_named_not_only_the_one_the_task_served(finished, monkeypatch, capsys):
    text = REPLAN.replace("\n\n## Đề xuất", "\n- R2: đã làm cùng lúc, xem spec-delta.md\n\n## Đề xuất", 1)
    assert write_replan(capsys, monkeypatch, text)[0] == ExitCode.OK


def test_naming_an_item_when_the_project_has_no_roadmap_is_refused(finished, monkeypatch, capsys):
    (finished / ".ThanhTan" / "project" / "roadmap.md").unlink()
    code, _, err = write_replan(capsys, monkeypatch)
    assert code == REPORT_REFUSED and "R1" in err and "roadmap" in err


def test_without_a_roadmap_nothing_finished_is_still_a_valid_replan(finished, monkeypatch, capsys):
    (finished / ".ThanhTan" / "project" / "roadmap.md").unlink()
    assert write_replan(capsys, monkeypatch, NOTHING_DONE)[0] == ExitCode.OK


# ------------------------------------------------------------------ the MCP tool


@pytest.fixture
def server(finished):
    return build_server(WorkspaceServices(find_workspace(finished)))


def test_the_mcp_server_offers_the_replan_write_tool(server):
    names = {tool.name for tool in tool_list(server)}
    assert "replan_write" in names


def test_replan_write_is_the_only_replan_tool(server):
    names = {tool.name for tool in tool_list(server)}
    assert {name for name in names if "replan" in name} == {"replan_write"}


def test_the_replan_tool_writes_to_disk(server, finished):
    result = call(server, "replan_write", content=REPLAN)
    assert not result.is_error
    assert (task_dir(finished) / "replan.md").read_text(encoding="utf-8") == REPLAN


def test_the_replan_tool_is_not_a_read_only_tool(server):
    tool = next(tool for tool in tool_list(server) if tool.name == "replan_write")
    assert tool.annotations.read_only_hint is False


def test_the_replan_tool_is_refused_while_a_task_is_open_and_says_why(server, finished, monkeypatch):
    say(monkeypatch, "task", "new", "next one")
    result = call(server, "replan_write", content=REPLAN)
    assert result.is_error and "open" in result.content[0].text
    assert not (task_dir(finished) / "replan.md").exists()


def test_the_replan_tool_returns_the_same_refusals_as_the_command(server):
    result = call(server, "replan_write", content="# Replan\n\nno sections\n")
    assert result.is_error and "Mục roadmap đã hoàn thành" in result.content[0].text


def test_the_replan_tool_only_proposes_like_the_command(server, finished, capsys):
    call(server, "replan_write", content=REPLAN)
    assert status_lines(capsys)[0] == "replan: proposed"
    assert "replanned_at" not in state_task(finished)


def test_the_replan_tool_keeps_the_older_version_when_it_writes_again(server, finished):
    call(server, "replan_write", content=REPLAN)
    call(server, "replan_write", content=NOTHING_DONE)
    assert [path.read_text(encoding="utf-8") for path in history_of_replan(finished)] == [REPLAN]


# ------------------------------------------------------------------------ skip


def test_skipping_records_the_reason_as_a_decision(finished, capsys):
    code, out, _ = run(capsys, "replan", "skip", "T-001", "--reason", "only a typo fix, nothing to learn")
    assert code == ExitCode.OK
    text = (finished / ".ThanhTan" / "decisions" / "T-001-replan-skip.md").read_text(encoding="utf-8")
    assert "T-001" in text and "only a typo fix, nothing to learn" in text


def test_skipping_shows_in_the_summary(finished, capsys):
    run(capsys, "replan", "skip", "T-001", "--reason", "only a typo fix")
    line = next(line for line in summary(finished).splitlines() if line.startswith("- Replan:"))
    assert re.fullmatch(r"- Replan: skipped \(\d{4}-\d{2}-\d{2}\)", line), line


def test_skipping_needs_a_reason(finished, capsys):
    with pytest.raises(SystemExit) as exc:
        run(capsys, "replan", "skip", "T-001")
    assert exc.value.code == 2
    assert "--reason" in capsys.readouterr().err  # asked for the missing option, not "unknown command"


@pytest.mark.parametrize("reason", ["", "   "])
def test_a_blank_reason_is_refused(finished, capsys, reason):
    assert run(capsys, "replan", "skip", "T-001", "--reason", reason)[0] == INVALID_INPUT
    assert not (finished / ".ThanhTan" / "decisions" / "T-001-replan-skip.md").exists()


def test_only_a_finished_task_can_be_skipped(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "next one")
    capsys.readouterr()
    assert run(capsys, "replan", "skip", "T-002", "--reason", "x")[0] == INVALID_INPUT  # still open
    assert run(capsys, "replan", "skip", "T-009", "--reason", "x")[0] == INVALID_INPUT  # no such task


def test_a_task_whose_replan_is_done_cannot_be_skipped(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    code, _, err = run(capsys, "replan", "skip", "T-001", "--reason", "x")
    assert code == INVALID_INPUT and "done" in err


def test_a_proposed_replan_can_still_be_skipped(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    assert run(capsys, "replan", "skip", "T-001", "--reason", "the proposal is not worth keeping")[0] == ExitCode.OK
    assert status_lines(capsys)[0] == "replan: skipped"


def test_a_task_cannot_be_skipped_twice(finished, capsys):
    assert run(capsys, "replan", "skip", "T-001", "--reason", "one")[0] == ExitCode.OK
    assert run(capsys, "replan", "skip", "T-001", "--reason", "two")[0] == INVALID_INPUT


# ----------------------------------------------------------- the warning of task new


def new_task_stderr(monkeypatch, capsys, title="next one"):
    capsys.readouterr()
    code = say(monkeypatch, "task", "new", title)
    return code, capsys.readouterr().err


def replan_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if "replan" in line.lower()]


def test_starting_a_task_after_an_unreplanned_one_warns_and_still_starts(finished, monkeypatch, capsys):
    code, err = new_task_stderr(monkeypatch, capsys)
    assert code == ExitCode.OK
    lines = replan_lines(err)
    assert len(lines) == 1 and lines[0].startswith("warning: ")
    assert "T-001" in lines[0] and "thanhtan replan skip T-001" in lines[0]


def test_the_very_first_task_gets_no_replan_warning(ws, monkeypatch, capsys):
    """Regression: nothing to replan before the first task is done."""
    code, err = new_task_stderr(monkeypatch, capsys)
    assert code == ExitCode.OK and replan_lines(err) == []


def test_a_proposed_replan_still_warns_and_says_what_the_person_does(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    code, err = new_task_stderr(monkeypatch, capsys)
    lines = replan_lines(err)
    assert code == ExitCode.OK and len(lines) == 1 and lines[0].startswith("warning: ")
    assert "T-001" in lines[0] and "thanhtan replan done" in lines[0]


def test_there_is_no_warning_once_a_person_confirmed_the_replan(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    code, err = new_task_stderr(monkeypatch, capsys)
    assert code == ExitCode.OK and replan_lines(err) == []


def test_there_is_no_warning_once_a_person_skipped_it(finished, monkeypatch, capsys):
    run(capsys, "replan", "skip", "T-001", "--reason", "only a typo fix")
    code, err = new_task_stderr(monkeypatch, capsys)
    assert code == ExitCode.OK and replan_lines(err) == []


def test_the_warning_names_the_latest_finished_task_only(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    run_task(finished, monkeypatch, "second", review=review_report())
    code, err = new_task_stderr(monkeypatch, capsys, "third")
    assert code == ExitCode.OK
    assert len(replan_lines(err)) == 1 and "T-002" in err and "T-001" not in "".join(replan_lines(err))


def test_a_cancelled_task_does_not_start_or_hide_the_warning(finished, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "abandoned")
    say(monkeypatch, "task", "cancel")
    git(finished, "switch", "-q", "develop")
    code, err = new_task_stderr(monkeypatch, capsys, "again")
    assert code == ExitCode.OK and len(replan_lines(err)) == 1 and "T-001" in err


def test_the_warning_does_not_hide_the_other_warnings(finished, monkeypatch, capsys):
    code, err = new_task_stderr(monkeypatch, capsys)
    assert code == ExitCode.OK and "mission" in err and len(replan_lines(err)) == 1


# --------------------------------------------------------- state files from before


def test_a_state_file_without_the_new_field_is_valid(state_data):
    """Regression: state files from before phase C stay valid."""
    assert schema_errors(state_data, STATE_SCHEMA_FILE) == []


def test_replanned_at_is_a_string_in_the_state_schema(state_data):
    state_data["tasks"][0]["replanned_at"] = "2026-10-17T10:00:00Z"
    assert schema_errors(state_data, STATE_SCHEMA_FILE) == []
    state_data["tasks"][0]["replanned_at"] = 5
    assert schema_errors(state_data, STATE_SCHEMA_FILE) != []


def test_a_task_started_after_a_replan_does_not_get_the_field(finished, monkeypatch, capsys):
    write_replan(capsys, monkeypatch)
    confirm_replan(capsys)
    say(monkeypatch, "task", "new", "next one")
    assert "replanned_at" in state_task(finished, 0) and "replanned_at" not in state_task(finished, 1)


def test_a_finished_task_from_before_the_field_existed_is_simply_pending(finished, capsys):
    state_path = finished / ".ThanhTan" / "state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["tasks"][0].pop("replanned_at", None)
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert status_lines(capsys)[0] == "replan: pending"


# ------------------------------------------------------------------------ guard


class Workspaces:
    def __init__(self, root):
        self.root = root

    def has_workspace(self, directory):
        return directory == self.root


class OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


@pytest.mark.parametrize(
    "command",
    ["thanhtan replan skip T-001 --reason x", "thanhtan replan skip T-001 --reason 'no need'", "cd . && thanhtan replan skip T-001 --reason x"],
)
def test_skipping_a_replan_is_a_persons_command(ws, command):
    verdict = evaluate(command, ws, OnFeature(), Workspaces(ws))
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PERSON_ONLY


# The forms the guard recognises for every command that is a person's (`roadmap set`, `project confirm`, ...).
# `timeout 5 ...`, `FOO=1 ...`, `uv run ...` and `python -m thanhtan ...` get past it for all of them today.
PERSON_FORMS = [
    "thanhtan {c}",
    "THANHTAN.EXE {c}",
    "thanhtan  {c}",
    "cd . && thanhtan {c}",
    "echo x; thanhtan {c}",
    "echo x | thanhtan {c}",
    "(thanhtan {c})",
    "/usr/bin/thanhtan {c}",
    'bash -c "thanhtan {c}"',
    'powershell -Command "thanhtan {c}"',
]


@pytest.mark.parametrize("form", PERSON_FORMS)
def test_confirming_a_replan_is_a_persons_command_in_every_form_the_guard_knows(ws, form):
    verdict = evaluate(form.format(c="replan done"), ws, OnFeature(), Workspaces(ws))
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PERSON_ONLY


@pytest.mark.parametrize("form", PERSON_FORMS)
def test_skipping_a_replan_is_a_persons_command_in_every_form_the_guard_knows(ws, form):
    verdict = evaluate(form.format(c="replan skip T-001 --reason x"), ws, OnFeature(), Workspaces(ws))
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PERSON_ONLY


@pytest.mark.parametrize("command", ["thanhtan replan status", "thanhtan replan write"])
def test_the_agent_may_read_the_replan_state_and_write_the_replan(ws, command):
    """Regression: allowed today, and the person-only rule for `replan skip` must not sweep these up."""
    assert evaluate(command, ws, OnFeature(), Workspaces(ws)).decision is GuardDecision.ALLOW


def test_the_mission_stays_a_persons_to_confirm_after_a_replan(ws):
    """Regression: the replan writes documents as unconfirmed; confirming them stays a person's command."""
    assert evaluate("thanhtan project confirm profile", ws, OnFeature(), Workspaces(ws)).rule is GuardRule.PERSON_ONLY


def test_documents_the_scout_rewrote_after_the_task_are_unconfirmed_until_a_person_confirms(finished, capsys):
    """Regression: green before phase C; what the replan relies on to keep a person in charge of the documents."""
    write_project_file(finished, "profile.md", PROFILE)
    assert run(capsys, "project", "confirm", "profile")[0] == ExitCode.OK
    service = WorkspaceServices(find_workspace(finished))
    service.write_project("profile", PROFILE + "\nsomething the task changed\n")
    assert "profile: unconfirmed" in run(capsys, "project", "status")[1]
