"""Phase C1: a finished task leaves `spec-delta.md`, the difference it made to the specification.

agentflow writes it when it seals the task (next to `summary.md`), so the agent that did the work cannot shape it:

    ## Đề xuất của reviewer     the reviewer's `## Đề xuất cập nhật hồ sơ` section, as written
    ## Thay đổi thật của task   plan items, commits and the files changed, from the plan and from git
    ## Liên kết                 the roadmap item and whether the mission, profile and architecture are confirmed

The replan reads it (see test_replan.py); a person reads it to see what the task really changed.
"""

import pytest
from conftest import git
from replan_helpers import (
    HEADING,
    NONE_PROPOSAL,
    review_report,
    run,
    run_task,
    say,
    section,
    spec_delta,
    start_workspace,
    summary,
    task_dir,
    write_project_file,
)
from sdd_helpers import PROFILE, ROADMAP

from agentflow.constants import ExitCode
from agentflow.seal import approval_tag

PROPOSALS = "- profile: thêm lệnh build mới\n- roadmap: R2 xong, thêm R5"


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    return start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)


def commit_on_develop(repo, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base files")


# ------------------------------------------------------------- the file and its parts


def test_approving_the_last_step_writes_the_spec_delta_next_to_the_summary(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report())
    text = spec_delta(ws)
    assert (task_dir(ws) / "summary.md").is_file()
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## Đề xuất của reviewer", "## Thay đổi thật của task", "## Liên kết"]
    assert text.startswith("# T-001")


def test_no_spec_delta_exists_before_the_person_approves(ws, monkeypatch):
    """Regression: green before phase C; nothing is written for a task nobody approved yet."""
    run_task(ws, monkeypatch, review=review_report(), approve=False)
    assert not (task_dir(ws) / "spec-delta.md").exists()


def test_the_summary_points_at_the_spec_delta(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report())
    assert "- Spec delta: tasks/T-001/spec-delta.md" in summary(ws).splitlines()


# ----------------------------------------------------- what the reviewer proposed


def test_the_reviewers_proposals_are_copied_as_written(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report(PROPOSALS))
    body = section(spec_delta(ws), "Đề xuất của reviewer")
    assert "- profile: thêm lệnh build mới" in body and "- roadmap: R2 xong, thêm R5" in body


def test_a_review_with_nothing_to_propose_says_so(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report())
    assert section(spec_delta(ws), "Đề xuất của reviewer").strip() == NONE_PROPOSAL


def test_only_the_section_of_the_review_is_copied_not_the_rest_of_the_report(ws, monkeypatch):
    report = review_report(PROPOSALS) + "\n## Bài học đề xuất\n\n### L1 - A lesson\nSome lesson text.\n"
    run_task(ws, monkeypatch, review=report)
    body = section(spec_delta(ws), "Đề xuất của reviewer")
    assert "Some lesson text" not in body and "Verdict" not in body


def test_a_heading_inside_a_code_block_of_the_review_is_not_the_section(ws, monkeypatch):
    fenced = f"```\n{HEADING}\n\n- profile: giả, chỉ là ví dụ trong khối code\n```\n"
    report = f"# Review\n\n{fenced}\n{HEADING}\n\n- architecture: thật\n"
    run_task(ws, monkeypatch, review=report)
    body = section(spec_delta(ws), "Đề xuất của reviewer")
    assert "- architecture: thật" in body and "giả" not in body


def test_a_task_from_a_workflow_without_the_drift_gate_and_without_a_review_report_says_there_was_none(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, drift_gate=False)
    run_task(repo, monkeypatch, review=None)
    body = section(spec_delta(repo), "Đề xuất của reviewer")
    assert "không có báo cáo review" in body


def test_a_review_report_from_before_the_drift_section_says_the_section_is_missing(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, drift_gate=False)
    run_task(repo, monkeypatch, review="# Review\n\nAll good.\n")
    body = section(spec_delta(repo), "Đề xuất của reviewer")
    assert "không có mục Đề xuất cập nhật hồ sơ" in body


# --------------------------------------------------------- what the task really changed


def test_the_plan_items_and_the_commits_of_the_task_are_listed(ws, monkeypatch):
    run_task(ws, monkeypatch, "Build the thing", review=review_report())
    body = section(spec_delta(ws), "Thay đổi thật của task")
    assert "- C1 - Build it" in body
    assert "T-001: change Build the thing" in body


def test_commits_of_other_branches_are_not_listed(ws, monkeypatch):
    git(ws, "switch", "-q", "-c", "side", "develop")
    (ws / "side.txt").write_text("x\n", encoding="utf-8")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "work on a side branch")
    git(ws, "switch", "-q", "develop")
    run_task(ws, monkeypatch, review=review_report())
    assert "side branch" not in spec_delta(ws) and "side.txt" not in spec_delta(ws)


def test_changed_files_are_grouped_by_their_first_directory_with_what_happened_to_each(ws, monkeypatch):
    commit_on_develop(ws, {"src/old.py": "old\n", "src/gone.py": "gone\n", "docs/guide.md": "guide\n", "README.md": "readme\n"})

    def change(repo):
        (repo / "src" / "new.py").write_text("new\n", encoding="utf-8")
        (repo / "src" / "old.py").write_text("changed\n", encoding="utf-8")
        (repo / "src" / "gone.py").unlink()
        (repo / "README.md").write_text("readme, changed\n", encoding="utf-8")

    run_task(ws, monkeypatch, review=review_report(), mutate=change)
    files = section(spec_delta(ws), "Thay đổi thật của task").split("### File đổi", 1)[1]
    src = files.split("#### src/", 1)[1].split("####", 1)[0]
    assert "- A src/new.py" in src and "- M src/old.py" in src and "- D src/gone.py" in src
    root = files.split("#### ./", 1)[1].split("####", 1)[0]
    assert "- M README.md" in root
    assert "docs/guide.md" not in files  # not touched by the task


def test_a_renamed_file_is_one_line_with_both_names(ws, monkeypatch):
    commit_on_develop(ws, {"src/before.py": "the same content, long enough for git to see a rename\n" * 5})

    def rename(repo):
        git(repo, "mv", "src/before.py", "src/after.py")

    run_task(ws, monkeypatch, review=review_report(), mutate=rename)
    files = section(spec_delta(ws), "Thay đổi thật của task").split("### File đổi", 1)[1]
    assert "- R src/before.py -> src/after.py" in files
    assert files.count("src/before.py") == 1


def test_a_file_with_a_non_ascii_name_is_listed_as_it_is(ws, monkeypatch):
    def add(repo):
        (repo / "ghi-chú-đặt-món.md").write_text("x\n", encoding="utf-8")

    run_task(ws, monkeypatch, review=review_report(), mutate=add)
    assert "- A ghi-chú-đặt-món.md" in spec_delta(ws)  # not git's quoted "\\303\\240..." form


# --------------------------------------------------------------------------- links


def test_without_a_roadmap_item_the_link_says_none(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report())
    assert "- roadmap: không có" in section(spec_delta(ws), "Liên kết")


def test_the_roadmap_item_of_the_task_is_named(ws, monkeypatch):
    write_project_file(ws, "roadmap.md", ROADMAP)
    run_task(ws, monkeypatch, review=review_report(), extra=("--roadmap", "R1"))
    assert "- roadmap: R1 - Đặt món" in section(spec_delta(ws), "Liên kết")


@pytest.mark.parametrize("document", ["mission", "profile", "architecture"])
def test_a_document_that_does_not_exist_is_reported_as_missing(ws, monkeypatch, document):
    run_task(ws, monkeypatch, review=review_report())
    assert f"- {document}: missing" in section(spec_delta(ws), "Liên kết")


def test_the_mission_and_profile_are_reported_as_confirmed_or_not(ws, monkeypatch, capsys):
    write_project_file(ws, "profile.md", PROFILE)
    assert run(capsys, "project", "confirm", "mission")[0] == ExitCode.OK
    run_task(ws, monkeypatch, review=review_report())
    links = section(spec_delta(ws), "Liên kết")
    assert "- mission: confirmed" in links and "- profile: unconfirmed" in links


def test_a_profile_edited_after_confirming_is_reported_as_unconfirmed(ws, monkeypatch, capsys):
    write_project_file(ws, "profile.md", PROFILE)
    assert run(capsys, "project", "confirm", "mission", "profile")[0] == ExitCode.OK
    write_project_file(ws, "profile.md", PROFILE.replace("## Build", "## Build\nsomething new\n\n## Build again"))
    run_task(ws, monkeypatch, review=review_report())
    links = section(spec_delta(ws), "Liên kết")
    assert "- profile: unconfirmed" in links


# ------------------------------------------------------------ sealing: all or nothing


def test_a_seal_that_fails_leaves_no_spec_delta_and_the_task_open(ws, monkeypatch, capsys):
    """Regression: a failing seal already changed nothing; the spec delta must not break that."""
    run_task(ws, monkeypatch, review=review_report(), approve=False)
    git(ws, "tag", approval_tag("T-001"))  # someone already made the tag
    assert say(monkeypatch, "task", "approve") == ExitCode.TASK_CONFLICT
    assert not (task_dir(ws) / "spec-delta.md").exists()
    assert not (task_dir(ws) / "summary.md").exists()
    capsys.readouterr()
    assert "active task: T-001" in run(capsys, "status")[1]


def test_sealing_by_hand_writes_the_spec_delta_of_a_task_sealed_without_one(ws, monkeypatch, capsys):
    run_task(ws, monkeypatch, review=review_report(PROPOSALS))
    git(ws, "tag", "-d", approval_tag("T-001"))
    (task_dir(ws) / "spec-delta.md").unlink()  # how a task looks that was approved before spec deltas existed
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.OK
    assert "- profile: thêm lệnh build mới" in spec_delta(ws)


def test_sealing_a_task_whose_review_cannot_be_found_still_writes_one(ws, monkeypatch, capsys):
    run_task(ws, monkeypatch, review=review_report(PROPOSALS))
    git(ws, "tag", "-d", approval_tag("T-001"))
    (task_dir(ws) / "reports" / "review.md").unlink()
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.OK
    assert "không có báo cáo review" in section(spec_delta(ws), "Đề xuất của reviewer")


# ------------------------------------------------------------- an agent cannot write it


def test_there_is_no_step_an_agent_can_save_a_spec_delta_as(ws, monkeypatch, capsys):
    """Regression: reports are saved per workflow step, so there is no way to hand-write this file."""
    run_task(ws, monkeypatch, review=review_report(), approve=False)
    code, _, _ = run(capsys, "report", "--step", "spec-delta", text="# fake\n", monkeypatch=monkeypatch)
    assert code != ExitCode.OK
    assert not (task_dir(ws) / "reports" / "spec-delta.md").exists()


def test_git_is_the_source_of_the_files_not_the_plan(ws, monkeypatch):
    """The plan says `files: a.txt`; the task also touched b.txt. The spec delta shows what git saw."""

    def two_files(repo):
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        (repo / "b.txt").write_text("b\n", encoding="utf-8")

    run_task(ws, monkeypatch, review=review_report(), mutate=two_files)
    assert "- A b.txt" in spec_delta(ws) and "- A a.txt" in spec_delta(ws)


def test_the_file_is_plain_utf8_with_unix_line_ends(ws, monkeypatch):
    run_task(ws, monkeypatch, review=review_report(PROPOSALS))
    raw = (task_dir(ws) / "spec-delta.md").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    raw.decode("utf-8")
