"""Review only what changed since the last review: the mark a review or security round leaves, and `thanhtan scope`."""

import json

from conftest import git
from spec_helpers import at_spec_step, run, start, task_dir

from thanhtan import reviewmarks


def task_with_commit(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = start(gitflow_repo, tmp_path, monkeypatch, capsys)
    at_spec_step(repo, monkeypatch, capsys)
    return repo


def add_commit(repo, name, item="C1"):
    (repo / name).write_text(name + "\n", encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"T-001: add {name}", "-m", f"Plan-Item: {item}")
    return git(repo, "rev-parse", "HEAD")


def test_without_a_mark_the_scope_is_the_whole_task(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = task_with_commit(gitflow_repo, tmp_path, monkeypatch, capsys)
    add_commit(repo, "a.txt")
    code, out, _ = run(capsys, "scope")
    assert code == 0 and "scope: whole task" in out and "a.txt" in out


def test_after_a_mark_only_the_newer_commits_and_files_are_in_scope(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = task_with_commit(gitflow_repo, tmp_path, monkeypatch, capsys)
    first = add_commit(repo, "a.txt")
    reviewmarks.record(task_dir(repo), "review", first, "2026-10-19T10:00:00Z")
    add_commit(repo, "b.txt")
    code, out, _ = run(capsys, "scope", "--step", "review")
    assert code == 0 and f"since {first[:7]}" in out
    assert "b.txt" in out and "a.txt" not in out


def test_a_mark_that_is_not_in_the_branch_any_more_falls_back_to_the_whole_task(gitflow_repo, tmp_path, monkeypatch, capsys):
    repo = task_with_commit(gitflow_repo, tmp_path, monkeypatch, capsys)
    add_commit(repo, "a.txt")
    reviewmarks.record(task_dir(repo), "review", "0" * 40, "2026-10-19T10:00:00Z")
    code, out, _ = run(capsys, "scope", "--step", "review")
    assert code == 0 and "scope: whole task" in out and "not in the branch" in out


def test_each_step_keeps_its_own_mark(tmp_path):
    reviewmarks.record(tmp_path, "review", "a" * 40, "t1")
    reviewmarks.record(tmp_path, "security", "b" * 40, "t2")
    reviewmarks.record(tmp_path, "review", "c" * 40, "t3")
    assert reviewmarks.mark(tmp_path, "review") == "c" * 40 and reviewmarks.mark(tmp_path, "security") == "b" * 40
    assert json.loads((tmp_path / "review-marks.json").read_text(encoding="utf-8"))["review"]["at"] == "t3"
    assert reviewmarks.mark(tmp_path, "test") is None
