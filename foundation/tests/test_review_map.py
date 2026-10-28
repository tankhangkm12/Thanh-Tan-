from conftest import git

from thanhtan.plan import PlanItem
from thanhtan.reviewmap import CommitFiles, build_review_map, collect_commits

ITEMS = [
    PlanItem(code="C1", title="Add greeting", files=("src/greet.py", "tests/"), done_when="`uv run pytest tests/test_greet.py`"),
    PlanItem(code="C2", title="Wire it", files=("src/app.py",), done_when="the app prints it"),
]


def commit(sha, item, *files):
    return CommitFiles(sha, f"change {sha}", item, tuple(files))


def test_each_item_lists_its_commits_files_and_lines():
    text = build_review_map("T-001", "Greeting", ITEMS, [commit("aaaaaaa1", "C1", ("src/greet.py", 10, 2), ("tests/t.py", 5, 0))], {})
    section = text.split("### C1")[1].split("### C2")[0]
    assert "src/greet.py (+10 -2)" in section and "tests/t.py (+5 -0)" in section
    assert "`uv run pytest tests/test_greet.py`" in section and "aaaaaaa" in section
    assert "### C2" in text and "no commit" in text.split("### C2")[1]


def test_a_file_outside_the_files_of_the_item_and_a_commit_without_an_item_stand_out():
    text = build_review_map(
        "T-001", "Greeting", ITEMS,
        [commit("aaaaaaa1", "C1", ("src/other.py", 3, 0)), commit("bbbbbbb2", None, ("README.md", 1, 1))], {},
    )  # fmt: skip
    assert "outside the files of C1: src/other.py" in text
    assert "## Commits without a plan item" in text and "README.md" in text


def test_the_last_check_of_each_item_and_the_totals_are_shown():
    results = {"C1": {"status": "green"}}
    text = build_review_map("T-001", "Greeting", ITEMS, [commit("aaaaaaa1", "C1", ("src/greet.py", 4, 1))], results)
    assert "last run by thanhtan: green" in text.split("### C1")[1].split("### C2")[0]
    assert "not run by thanhtan" in text.split("### C2")[1]
    assert "1 files, +4 -1" in text


def test_collect_commits_reads_the_items_and_line_counts_from_git(gitflow_repo):
    git(gitflow_repo, "switch", "-q", "-c", "feature/x")
    (gitflow_repo / "a.py").write_text("one\ntwo\n", encoding="utf-8")
    git(gitflow_repo, "add", "a.py")
    git(gitflow_repo, "commit", "-q", "-m", "T-001: add a", "-m", "Plan-Item: C1")
    (gitflow_repo / "b.py").write_text("x\n", encoding="utf-8")
    git(gitflow_repo, "add", "b.py")
    git(gitflow_repo, "commit", "-q", "-m", "T-001: add b")
    base = git(gitflow_repo, "rev-parse", "develop")
    found = collect_commits(gitflow_repo, base, "HEAD")
    assert [c.item for c in found] == ["C1", None]
    assert found[0].files == (("a.py", 2, 0),) and found[1].files == (("b.py", 1, 0),)


def test_the_command_writes_the_map_of_the_active_task(gitflow_repo, tmp_path, monkeypatch, capsys):
    from spec_helpers import at_spec_step, run, start, task_dir

    repo = start(gitflow_repo, tmp_path, monkeypatch, capsys)
    at_spec_step(repo, monkeypatch, capsys)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "T-001: add a", "-m", "Plan-Item: C1")
    code, out, _err = run(capsys, "review-map")
    assert code == 0 and "review-map.md" in out
    text = (task_dir(repo) / "review-map.md").read_text(encoding="utf-8")
    assert "### C1" in text and "a.txt (+1 -0)" in text and "outside the files of C1: a.txt" not in text
