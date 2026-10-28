"""Phase D-guard, part 2: four branches of phase C that no locked test reached.

They are code that already exists, so the tests are green on arrival; each was checked by breaking the branch on purpose
(see the progress log). Nothing here changes behaviour.

- `set_summary_replan` on a summary written before the `- Replan:` line existed,
- `replan skip` when the latest finished task is another task,
- the copy status of `git diff --name-status` in `SubprocessGit.changed_entries`,
- `reviewer_proposals` when the reviewer's section is there but empty.
"""

import subprocess
from pathlib import Path

import pytest
from replan_helpers import review_report, run, run_task, start_workspace, summary, task_dir

from agentflow.constants import DRIFT_HEADING, NO_REVIEW_REPORT_TEXT, SUMMARY_FILE, TASKS_DIR, ExitCode
from agentflow.errors import AgentflowError
from agentflow.git import SubprocessGit
from agentflow.models import FileChange
from agentflow.replan import set_summary_replan
from agentflow.specdelta import reviewer_proposals

# ------------------------------------------------------- set_summary_replan, old summary


OLD_SUMMARY = """# T-001: t

- Status: done
- Approved at: 2026-10-01T09:00:00Z
- Branch: feature/t
"""


def write_summary(workspace: Path, text: str = OLD_SUMMARY, task_id: str = "T-001") -> Path:
    path = workspace / TASKS_DIR / task_id / SUMMARY_FILE
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_summary_from_before_the_replan_line_gets_it_right_after_the_approval_time(tmp_path):
    path = write_summary(tmp_path)
    set_summary_replan(tmp_path, "T-001", "pending")
    assert path.read_text(encoding="utf-8").splitlines() == [
        "# T-001: t",
        "",
        "- Status: done",
        "- Approved at: 2026-10-01T09:00:00Z",
        "- Replan: pending",
        "- Branch: feature/t",
    ]


def test_the_line_added_to_an_old_summary_is_then_replaced_not_repeated(tmp_path):
    path = write_summary(tmp_path)
    set_summary_replan(tmp_path, "T-001", "pending")
    set_summary_replan(tmp_path, "T-001", "skipped (2026-10-18)")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.startswith("- Replan:")] == ["- Replan: skipped (2026-10-18)"]
    assert lines.index("- Replan: skipped (2026-10-18)") == lines.index("- Approved at: 2026-10-01T09:00:00Z") + 1


def test_a_summary_with_windows_line_endings_is_rewritten_with_the_line_too(tmp_path):
    path = write_summary(tmp_path, OLD_SUMMARY.replace("\n", "\r\n"))
    set_summary_replan(tmp_path, "T-001", "pending")
    assert "- Approved at: 2026-10-01T09:00:00Z\n- Replan: pending\n" in path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_a_missing_summary_is_left_missing(tmp_path):
    set_summary_replan(tmp_path, "T-001", "pending")
    assert not (tmp_path / TASKS_DIR).exists()


def test_skipping_through_the_cli_puts_the_line_into_a_summary_that_lacks_it(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    run_task(repo, monkeypatch, review=review_report())
    path = task_dir(repo) / SUMMARY_FILE
    path.write_text("".join(line for line in path.read_text(encoding="utf-8").splitlines(keepends=True) if not line.startswith("- Replan:")), encoding="utf-8")
    capsys.readouterr()
    assert run(capsys, "replan", "skip", "T-001", "--reason", "nothing changed")[0] == ExitCode.OK
    lines = summary(repo).splitlines()
    skipped = [line for line in lines if line.startswith("- Replan:")]
    assert len(skipped) == 1 and skipped[0].startswith("- Replan: skipped (")
    assert lines[lines.index(skipped[0]) - 1].startswith("- Approved at:")


# ------------------------------------------------ replan skip when another task is the latest


def test_skipping_an_older_task_is_refused_and_names_the_latest_one(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    run_task(repo, monkeypatch, "first", review=review_report())
    run_task(repo, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    code, out, err = run(capsys, "replan", "skip", "T-001", "--reason", "too old to matter")
    assert code == ExitCode.INVALID_INPUT
    assert "T-001" in err and "T-002" in err
    assert not list((repo / ".ThanhTan" / "decisions").glob("*replan-skip*"))
    assert "- Replan: pending" in summary(repo, "T-001")


def test_the_latest_task_can_be_skipped_while_the_older_one_is_left_alone(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    run_task(repo, monkeypatch, "first", review=review_report())
    run_task(repo, monkeypatch, "second", review=review_report())
    capsys.readouterr()
    assert run(capsys, "replan", "skip", "T-002", "--reason", "only a typo fix")[0] == ExitCode.OK
    assert list((repo / ".ThanhTan" / "decisions").glob("T-002-replan-skip*"))
    assert not list((repo / ".ThanhTan" / "decisions").glob("T-001-replan-skip*"))


# ---------------------------------------------------------- changed_entries, copy status


class FakeDiff:
    """Stands for `git diff --name-status -z -M`: NUL-separated status and paths."""

    def __init__(self, *fields: str, code: int = 0):
        self.fields, self.code = fields, code
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, cwd, *args):
        self.calls.append(args)
        return subprocess.CompletedProcess(args, self.code, "".join(f"{field}\0" for field in self.fields), "boom" if self.code else "")


def entries(monkeypatch, tmp_path, *fields: str) -> list[FileChange]:
    monkeypatch.setattr("agentflow.git.run_git", FakeDiff(*fields))
    return SubprocessGit(tmp_path).changed_entries("develop", "feature/t")


def test_a_copy_is_reported_as_an_added_file_without_an_old_path(monkeypatch, tmp_path):
    assert entries(monkeypatch, tmp_path, "C085", "src/old.py", "src/new.py") == [FileChange("A", "src/new.py")]


def test_a_rename_keeps_the_old_path_and_a_copy_does_not(monkeypatch, tmp_path):
    found = entries(monkeypatch, tmp_path, "R100", "a.txt", "b.txt", "C090", "b.txt", "c.txt")
    assert found == [FileChange("R", "b.txt", "a.txt"), FileChange("A", "c.txt")]


def test_a_copy_between_other_entries_does_not_shift_the_ones_after_it(monkeypatch, tmp_path):
    found = entries(monkeypatch, tmp_path, "M", "x.py", "C100", "x.py", "y.py", "D", "z.py", "T", "w.py")
    assert found == [FileChange("M", "x.py"), FileChange("A", "y.py"), FileChange("D", "z.py"), FileChange("M", "w.py")]


def test_a_failing_diff_is_a_git_error_with_the_message(monkeypatch, tmp_path):
    monkeypatch.setattr("agentflow.git.run_git", FakeDiff(code=128))
    with pytest.raises(AgentflowError) as exc:
        SubprocessGit(tmp_path).changed_entries("develop", "feature/t")
    assert exc.value.code is ExitCode.GIT_FAILED and "boom" in str(exc.value)


# ------------------------------------------------------ reviewer_proposals, empty section


MISSING = f"không có mục {DRIFT_HEADING} trong báo cáo review"


@pytest.mark.parametrize(
    "report",
    [
        f"# Review\n\n## {DRIFT_HEADING}\n",
        f"# Review\n\n## {DRIFT_HEADING}\n\n\n   \n",
        f"# Review\n\n## {DRIFT_HEADING}\n\n## Next\n\nbody\n",
        f"# Review\n\n## {DRIFT_HEADING}\n\n```\n- profile: inside a code block\n```\n",
        f"# Review\n\n## {DRIFT_HEADING}\n\n<!-- profile: only a comment -->\n",
    ],
    ids=["heading-last", "blank-lines", "next-heading", "code-block-only", "comment-only"],
)
def test_a_reviewer_section_that_is_there_but_empty_reads_as_missing(report):
    assert reviewer_proposals(report) == MISSING


def test_the_three_cases_are_told_apart():
    assert reviewer_proposals(None) == NO_REVIEW_REPORT_TEXT
    assert reviewer_proposals("# Review\n\nno such section\n") == MISSING
    assert reviewer_proposals(f"# Review\n\n## {DRIFT_HEADING}\n\n- profile: add the mission\n") == "- profile: add the mission"
