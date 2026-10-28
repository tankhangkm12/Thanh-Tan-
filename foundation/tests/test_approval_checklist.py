"""Chặng D-checklist (D1 + D2 gốc): a step that needs a person gets a checklist file, and `task approve` reads it.

A step opts in with `approval_checklist` / `approval_items` in the workflow. The file is
`.ThanhTan/tasks/<task>/approve-<step>.md`: a header (task, step, report, generated, skeleton-sha256), a
`## Checklist` section of `- [ ] <code>: <text>` lines and a last `## Ghi chú của bạn` section for the person's notes.
`task approve` refuses (exit 36) while a required box is open or the skeleton (items, header) was changed.
"""

import json
import re
from pathlib import Path

import pytest
from checklist_helpers import (
    BUILD_QUESTIONS,
    CHECK_QUESTIONS,
    CHECKLIST_REFUSED,
    CONFIRM_QUESTIONS,
    PLAN2,
    REVIEW_REPORT,
    REVIEW_REPORT_NO_PROPOSAL,
    add_note,
    approve,
    checklist_path,
    checklist_workflow,
    codes,
    decisions,
    go_to_awaiting,
    items,
    open_workspace,
    task_now,
    tick,
    workspace,
    write_conventions,
    write_roadmap,
)
from conftest import SAMPLE_WORKFLOW, git
from sdd_helpers import project_dir, run, sample_workflow, say, statuses

from agentflow.constants import ExitCode
from agentflow.errors import AgentflowError
from agentflow.workflow import load_workflow, parse_workflow

REAL_WORKFLOW = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core" / "workflow.yaml"


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    return open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)


def at_confirm(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "confirm", monkeypatch, capsys)
    return checklist_path(repo, "confirm")


# ------------------------------------------------------------------ the workflow declares it


def workflow_data(**step_extra):
    data = json.loads(json.dumps(SAMPLE_WORKFLOW))
    data["steps"][0].update(step_extra)
    return data


def test_a_step_can_declare_fixed_questions_and_dynamic_item_sources():
    data = workflow_data(approval_checklist=["Một?", "Hai?"], approval_items=["plan-items", "drift-proposals"])
    step = parse_workflow(data, "t").steps[0]
    assert tuple(step.approval_checklist) == ("Một?", "Hai?")
    assert tuple(str(item) for item in step.approval_items) == ("plan-items", "drift-proposals")


def test_a_step_without_the_fields_has_none():
    step = parse_workflow(workflow_data(), "t").steps[0]
    assert tuple(step.approval_checklist) == () and tuple(step.approval_items) == ()


@pytest.mark.parametrize(
    "extra",
    [
        {"approval_items": ["nonsense"]},
        {"approval_checklist": [""]},
        {"approval_checklist": "one question"},
        {"approval_checklist": ["   "]},
    ],
)
def test_the_workflow_schema_rejects_bad_checklist_declarations(extra):
    with pytest.raises(AgentflowError):
        parse_workflow(workflow_data(**extra), "t")


def test_a_checklist_on_a_step_that_needs_no_approval_is_rejected():
    data = workflow_data(approval_checklist=["Nope?"])
    data["steps"][1]["approval_checklist"] = ["Nope?"]  # `build` needs no approval
    with pytest.raises(AgentflowError, match="build"):
        parse_workflow(data, "t")


def test_the_real_software_dev_workflow_declares_the_checklists_of_its_three_approvals():
    workflow = load_workflow(REAL_WORKFLOW)
    steps = {step.id: step for step in workflow.steps}
    for name in ("confirm", "plan", "review"):
        assert len(steps[name].approval_checklist) >= 3, name
    assert "plan-items" in [str(i) for i in steps["plan"].approval_items]
    assert "review-conventions" in [str(i) for i in steps["review"].approval_items]
    assert "drift-proposals" in [str(i) for i in steps["review"].approval_items]
    assert all(not step.approval_checklist for step in workflow.steps if not step.requires_approval)


# ------------------------------------------------------------------ D1: the file is written


def test_passing_into_approval_writes_the_checklist_and_says_where(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it")
    capsys.readouterr()
    code, out, _err = run(capsys, "task", "advance", "--result", "pass")
    assert code == ExitCode.OK
    path = checklist_path(repo, "confirm")
    assert path.is_file()
    assert "approve-confirm.md" in out


def test_the_file_has_a_header_the_questions_and_an_empty_notes_section(repo, monkeypatch, capsys):
    text = at_confirm(repo, monkeypatch, capsys).read_text(encoding="utf-8")
    assert re.search(r"^- task: T-001$", text, flags=re.M)
    assert re.search(r"^- step: confirm$", text, flags=re.M)
    assert re.search(r"^- report: .*reports/confirm\.md$", text, flags=re.M)
    assert re.search(r"^- generated: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", text, flags=re.M)
    assert re.search(r"^- skeleton-sha256: [0-9a-f]{64}$", text, flags=re.M)
    headings = re.findall(r"^## (.+)$", text, flags=re.M)
    assert headings == ["Checklist", "Ghi chú của bạn"]
    assert [(box, text_) for box, _opt, _code, text_ in items(text)] == [(" ", q) for q in CONFIRM_QUESTIONS]
    assert codes(text) == ["K1", "K2"]
    notes = text.split("## Ghi chú của bạn", 1)[1]
    assert notes.strip() == ""


def test_ticking_a_box_does_not_change_the_skeleton_hash_in_the_header(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    before = re.search(r"skeleton-sha256: ([0-9a-f]{64})", path.read_text(encoding="utf-8"))[1]
    tick(path)
    assert re.search(r"skeleton-sha256: ([0-9a-f]{64})", path.read_text(encoding="utf-8"))[1] == before
    assert approve(capsys)[0] == ExitCode.OK


def test_a_step_that_declares_no_checklist_gets_no_file_and_approves_as_before(tmp_path, gitflow_repo, monkeypatch, capsys):
    plain = open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, sample_workflow(tmp_path))
    say(monkeypatch, "task", "new", "Do it")
    say(monkeypatch, "task", "advance", "--result", "pass")
    assert list((workspace(plain) / "tasks" / "T-001").glob("approve-*")) == []
    assert approve(capsys)[0] == ExitCode.OK
    assert task_now(plain)[1] == "build"


def test_no_file_while_the_step_is_still_in_progress(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it")
    assert not checklist_path(repo, "confirm").exists()


def test_a_size_that_drops_the_approval_of_a_step_gets_no_checklist_for_it(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it", "--size", "small")
    go_to_awaiting(repo, "build", monkeypatch, capsys, first=False)
    assert not checklist_path(repo, "build").exists()
    assert task_now(repo)[1] == "check"
    assert checklist_path(repo, "confirm").is_file()


# ------------------------------------------------------------------ the dynamic items


def test_plan_items_become_one_line_each_after_the_fixed_questions(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "build", monkeypatch, capsys)
    text = checklist_path(repo, "build").read_text(encoding="utf-8")
    assert codes(text) == ["K1", "C1", "C2"]
    by_code = {code: line for _b, _o, code, line in items(text)}
    assert by_code["K1"] == BUILD_QUESTIONS[0]
    assert "Build it" in by_code["C1"] and "Test it" in by_code["C2"]


def test_a_plan_with_no_items_still_gives_a_valid_file_with_the_fixed_questions(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "build", monkeypatch, capsys, report="# Plan\n\nNothing to build.\n")
    text = checklist_path(repo, "build").read_text(encoding="utf-8")
    assert codes(text) == ["K1"]
    tick(checklist_path(repo, "build"))
    assert approve(capsys)[0] == ExitCode.OK


def test_every_effective_review_convention_gets_a_line_and_other_checks_do_not(repo, monkeypatch, capsys):
    write_conventions(repo)
    go_to_awaiting(repo, "check", monkeypatch, capsys)
    text = checklist_path(repo, "check").read_text(encoding="utf-8")
    assert "PC-01" in codes(text)
    assert "PC-02" not in codes(text)


def test_each_proposal_of_the_review_to_update_the_project_documents_gets_a_line(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "check", monkeypatch, capsys, report=REVIEW_REPORT)
    text = checklist_path(repo, "check").read_text(encoding="utf-8")
    proposals = [line for code, line in ((c, t) for _b, _o, c, t in items(text)) if re.fullmatch(r"D\d+", code)]
    assert len(proposals) == 2
    assert "build mới" in proposals[0] and "R2" in proposals[1]


def test_no_proposal_means_no_proposal_lines(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "check", monkeypatch, capsys, report=REVIEW_REPORT_NO_PROPOSAL)
    text = checklist_path(repo, "check").read_text(encoding="utf-8")
    assert not [c for c in codes(text) if re.fullmatch(r"D\d+", c)]


# ------------------------------------------------------------------ the file cannot be written: nothing changes


def test_when_the_file_cannot_be_written_the_pass_is_refused_and_the_state_stays(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it")
    capsys.readouterr()
    before = (workspace(repo) / "state.json").read_bytes()

    def broken(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("agentflow.checklist.write_text_atomic", broken)
    code, _out, _err = run(capsys, "task", "advance", "--result", "pass")
    assert code != ExitCode.OK
    assert (workspace(repo) / "state.json").read_bytes() == before
    assert task_now(repo) == ("open", "confirm", "in_progress")


# ------------------------------------------------------------------ D2: approve reads the file


def test_approve_with_every_required_box_ticked_moves_on(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    code, _out, _err = approve(capsys)
    assert code == ExitCode.OK
    assert task_now(repo) == ("open", "build", "in_progress")


def test_approve_refuses_while_a_box_is_open_names_it_and_changes_nothing(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path, "K1")
    before = (workspace(repo) / "state.json").read_bytes()
    code, _out, err = approve(capsys)
    assert code == CHECKLIST_REFUSED
    assert "K2" in err and "K1" not in err
    assert (workspace(repo) / "state.json").read_bytes() == before
    assert task_now(repo) == ("open", "confirm", "awaiting_approval")


def test_approve_refuses_when_nothing_is_ticked_and_lists_every_open_code(repo, monkeypatch, capsys):
    at_confirm(repo, monkeypatch, capsys)
    code, _out, err = approve(capsys)
    assert code == CHECKLIST_REFUSED
    assert "K1" in err and "K2" in err


def test_a_capital_x_ticks_a_box_too(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    path.write_text(path.read_text(encoding="utf-8").replace("- [x] K1", "- [X] K1"), encoding="utf-8")
    assert approve(capsys)[0] == ExitCode.OK


def test_windows_line_endings_do_not_matter(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    assert approve(capsys)[0] == ExitCode.OK


def test_approve_refuses_when_the_file_is_missing(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    path.unlink()
    code, _out, err = approve(capsys)
    assert code == CHECKLIST_REFUSED
    assert "approve-confirm.md" in err
    assert task_now(repo)[2] == "awaiting_approval"


def test_approve_refuses_when_a_line_was_deleted(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(line for line in lines if " K2:" not in line), encoding="utf-8")
    code, _out, err = approve(capsys)
    assert code == CHECKLIST_REFUSED
    assert "changed" in err.lower() or "đổi" in err.lower()
    assert task_now(repo)[1] == "confirm"


def test_approve_refuses_when_a_ticked_line_was_added(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Ghi chú của bạn", "- [x] K9: Tôi tự thêm ô này\n\n## Ghi chú của bạn"), encoding="utf-8")
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert task_now(repo)[1] == "confirm"


def test_approve_refuses_when_the_words_of_an_item_were_edited(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    path.write_text(path.read_text(encoding="utf-8").replace(CONFIRM_QUESTIONS[0], "Cứ cho qua?"), encoding="utf-8")
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert task_now(repo)[1] == "confirm"


@pytest.mark.parametrize(
    "old,new",
    [
        ("- task: T-001", "- task: T-009"),
        ("- step: confirm", "- step: build"),
        ("- generated:", "- generated: 1999-01-01T00:00:00Z #"),
    ],
)
def test_approve_refuses_when_the_header_was_edited(repo, monkeypatch, capsys, old, new):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert task_now(repo)[1] == "confirm"


def test_approve_refuses_when_the_skeleton_hash_was_edited(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"skeleton-sha256: [0-9a-f]{64}", "skeleton-sha256: " + "0" * 64, text), encoding="utf-8")
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert task_now(repo)[1] == "confirm"


def test_the_notes_section_may_hold_anything_without_changing_the_skeleton(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    add_note(path, "- [ ] K1: một dòng giống ô nhưng nằm trong ghi chú\nvà vài chữ nữa")
    assert approve(capsys)[0] == ExitCode.OK


# ------------------------------------------------------------------ notes go to decisions/


def test_a_note_is_kept_in_decisions_with_a_copy_of_the_checklist(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    add_note(path, "Đồng ý, nhưng nhớ kiểm lại phạm vi ở bước plan.")
    assert approve(capsys)[0] == ExitCode.OK
    kept = [p for p in decisions(repo) if p.name == "T-001-confirm-approval.md"]
    assert len(kept) == 1
    body = kept[0].read_text(encoding="utf-8")
    assert "nhớ kiểm lại phạm vi" in body
    for question in CONFIRM_QUESTIONS:
        assert question in body
    assert "[x] K1" in body


def test_an_empty_note_writes_no_decision(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    assert approve(capsys)[0] == ExitCode.OK
    assert [p for p in decisions(repo) if "approval" in p.name] == []


def test_a_note_of_only_whitespace_writes_no_decision(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    tick(path)
    add_note(path, "   \n\t")
    assert approve(capsys)[0] == ExitCode.OK
    assert [p for p in decisions(repo) if "approval" in p.name] == []


def test_a_refused_approval_writes_no_decision_even_with_a_note(repo, monkeypatch, capsys):
    path = at_confirm(repo, monkeypatch, capsys)
    add_note(path, "ghi chú nhưng chưa tick")
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert [p for p in decisions(repo) if "approval" in p.name] == []


# ------------------------------------------------------------------ rework: a step comes round again


def test_a_step_that_comes_round_again_keeps_the_old_file_and_makes_a_new_one(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "check", monkeypatch, capsys)
    first_build = checklist_path(repo, "build").read_text(encoding="utf-8")
    first_check = checklist_path(repo, "check").read_text(encoding="utf-8")
    say(monkeypatch, "task", "advance", "--result", "fail")  # check -> build
    say(monkeypatch, "report", "--step", "build", text=PLAN2)
    say(monkeypatch, "task", "advance", "--result", "pass")
    assert checklist_path(repo, "build", 1).read_text(encoding="utf-8") == first_build
    fresh = checklist_path(repo, "build").read_text(encoding="utf-8")
    assert [box for box, *_ in items(fresh)] == [" "] * len(items(fresh)), "the new file starts with every box open"
    tick(checklist_path(repo, "build"))
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "check", text=REVIEW_REPORT)
    say(monkeypatch, "task", "advance", "--result", "pass")
    assert checklist_path(repo, "check", 1).read_text(encoding="utf-8") == first_check


def test_the_tick_of_an_old_round_does_not_approve_the_new_round(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "build", monkeypatch, capsys)
    tick(checklist_path(repo, "build"))
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "check", text=REVIEW_REPORT)
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "advance", "--result", "fail")
    say(monkeypatch, "report", "--step", "build", text=PLAN2)
    say(monkeypatch, "task", "advance", "--result", "pass")
    capsys.readouterr()
    code, _out, err = approve(capsys)
    assert code == CHECKLIST_REFUSED and "K1" in err


def test_two_approvals_of_the_same_step_keep_both_notes(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "build", monkeypatch, capsys)
    add_note(checklist_path(repo, "build"), "vòng một")
    tick(checklist_path(repo, "build"))
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "check", text=REVIEW_REPORT)
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "advance", "--result", "fail")
    say(monkeypatch, "report", "--step", "build", text=PLAN2)
    say(monkeypatch, "task", "advance", "--result", "pass")
    add_note(checklist_path(repo, "build"), "vòng hai")
    tick(checklist_path(repo, "build"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    texts = [p.read_text(encoding="utf-8") for p in decisions(repo) if "approval" in p.name]
    assert len(texts) == 2
    assert any("vòng một" in t for t in texts) and any("vòng hai" in t for t in texts)


# ------------------------------------------------------------------ a blocked task needs no checklist


def test_overriding_a_blocked_task_needs_no_checklist(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it")
    assert say(monkeypatch, "task", "advance", "--result", "fail") == ExitCode.OK  # confirm has no way back: blocked
    assert task_now(repo)[0] == "blocked"
    capsys.readouterr()
    code, out, _err = approve(capsys, "--reason", "đã xem lại")
    assert code == ExitCode.OK and "decision recorded" in out
    assert task_now(repo)[0] == "open"


# ------------------------------------------------------------------ Q-B3: the roadmap box of the last step


def roadmap_task(repo, monkeypatch, capsys):
    write_roadmap(repo)
    go_to_awaiting(repo, "check", monkeypatch, capsys, extra=("--roadmap", "R1"))
    return checklist_path(repo, "check")


def test_the_last_step_of_a_task_with_a_roadmap_item_asks_whether_the_item_is_done(repo, monkeypatch, capsys):
    path = roadmap_task(repo, monkeypatch, capsys)
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^- \[ \] \(tùy chọn\) roadmap: .*R1.*\?\s*$", text, flags=re.M)
    assert "roadmap" in codes(text, optional=True)
    assert "roadmap" not in codes(text, optional=False)


def test_leaving_the_roadmap_box_open_still_approves_and_keeps_the_item_doing(repo, monkeypatch, capsys):
    path = roadmap_task(repo, monkeypatch, capsys)
    tick(path)
    assert approve(capsys)[0] == ExitCode.OK
    assert statuses(repo)["R1"] == "doing"
    assert task_now(repo)[0] == "done"


def test_ticking_the_roadmap_box_moves_the_item_to_done_when_approved(repo, monkeypatch, capsys):
    path = roadmap_task(repo, monkeypatch, capsys)
    tick(path)
    tick(path, "roadmap")
    assert approve(capsys)[0] == ExitCode.OK
    assert statuses(repo)["R1"] == "done"


def test_a_refused_approval_does_not_touch_the_roadmap(repo, monkeypatch, capsys):
    path = roadmap_task(repo, monkeypatch, capsys)
    tick(path, "roadmap")  # the required boxes are still open
    assert approve(capsys)[0] == CHECKLIST_REFUSED
    assert statuses(repo)["R1"] == "doing"


def test_other_steps_and_tasks_without_a_roadmap_item_have_no_roadmap_box(repo, monkeypatch, capsys):
    write_roadmap(repo)
    go_to_awaiting(repo, "build", monkeypatch, capsys, extra=("--roadmap", "R1"))
    assert "roadmap" not in codes(checklist_path(repo, "confirm").read_text(encoding="utf-8"))
    assert "roadmap" not in codes(checklist_path(repo, "build").read_text(encoding="utf-8"))


def test_a_task_without_a_roadmap_item_has_no_roadmap_box_at_the_end(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "check", monkeypatch, capsys)
    assert "roadmap" not in codes(checklist_path(repo, "check").read_text(encoding="utf-8"))


def test_the_roadmap_box_is_not_added_to_a_last_step_that_declares_no_checklist(tmp_path, gitflow_repo, monkeypatch, capsys):
    plain = open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, sample_workflow(tmp_path))
    write_roadmap(plain)
    say(monkeypatch, "task", "new", "Do it", "--roadmap", "R1")
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")
    say(monkeypatch, "report", "--step", "build", text="### C1 - x\n- role: builder\n- files: a.txt\n- done-when: `true`\n- docs: https://d.example\n")
    (plain / "a.txt").write_text("x\n", encoding="utf-8")
    git(plain, "add", "a.txt")
    say(monkeypatch, "commit", "add", "--item", "C1")
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "advance", "--result", "pass")
    assert not list((workspace(plain) / "tasks" / "T-001").glob("approve-*"))
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    assert statuses(plain)["R1"] == "doing"


def test_a_task_on_the_real_dev_core_workflow_gets_a_checklist_at_confirm(gitflow_repo, monkeypatch, capsys):
    from sdd_helpers import init_workspace

    init_workspace(gitflow_repo, REAL_WORKFLOW, monkeypatch, capsys)
    say(monkeypatch, "task", "new", "Do it")
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    text = checklist_path(gitflow_repo, "confirm").read_text(encoding="utf-8")
    assert len(codes(text)) >= 3 and codes(text)[0] == "K1"
    capsys.readouterr()
    assert approve(capsys)[0] == CHECKLIST_REFUSED
