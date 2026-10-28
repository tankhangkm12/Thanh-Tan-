"""Run with: uv run --with pytest pytest families/design-system/core/scripts"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import init_workspace as iw  # noqa: E402

TREE_DIRS = [
    "inputs/ba",
    "inputs/ui-design",
    "inputs/previous-design",
    "plan/tasks",
    "stack/layers",
    "capacity",
    "decisions",
    "risks",
    "drafts",
    "reviews",
    "checks",
    "archive",
]
TREE_FILES = ["state.md", "questions.md", "decisions/decision-log.md", "risks/acceptance.md"]


def lines(path: Path) -> list[str]:
    return iw.read(path).splitlines()


def snapshot(project: Path) -> dict[str, bytes]:
    return {str(p.relative_to(project)): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


def test_creates_the_tree(tmp_path: Path):
    iw.init(tmp_path)
    root = tmp_path / ".agent-workspace"
    for relative in TREE_DIRS:
        assert (root / relative).is_dir(), relative
    for relative in TREE_FILES:
        assert (root / relative).is_file(), relative
    # Only the four templates are copied; the files other agents own are not made here.
    assert sorted(p.name for p in root.rglob("*") if p.is_file()) == sorted(Path(f).name for f in TREE_FILES)


def test_templates_are_copied_unchanged(tmp_path: Path):
    iw.init(tmp_path)
    for name, target in iw.TEMPLATES.items():
        assert (tmp_path / ".agent-workspace" / target).read_bytes() == (iw.TEMPLATES_DIR / name).read_bytes()


def test_acceptance_template_is_copied_to_risks(tmp_path: Path):
    iw.init(tmp_path)
    copied = tmp_path / ".agent-workspace" / "risks" / "acceptance.md"
    assert copied.read_bytes() == (iw.TEMPLATES_DIR / "acceptance.md").read_bytes()
    assert "Người dùng nói (nguyên văn)" in iw.read(copied)


def test_second_run_changes_nothing(tmp_path: Path):
    iw.init(tmp_path)
    before = snapshot(tmp_path)
    report = iw.init(tmp_path)
    assert snapshot(tmp_path) == before
    assert not report.created and not report.updated


def test_second_run_keeps_edited_data(tmp_path: Path):
    iw.init(tmp_path)
    state = tmp_path / ".agent-workspace" / "state.md"
    state.write_text("# my own state\n", encoding="utf-8")
    note = tmp_path / ".agent-workspace" / "drafts" / "keep.md"
    note.write_text("draft\n", encoding="utf-8")
    iw.init(tmp_path)
    assert state.read_text(encoding="utf-8") == "# my own state\n"
    assert note.read_text(encoding="utf-8") == "draft\n"


def test_missing_template_is_recreated_but_existing_one_is_not(tmp_path: Path):
    iw.init(tmp_path)
    (tmp_path / ".agent-workspace" / "questions.md").unlink()
    iw.init(tmp_path)
    assert (tmp_path / ".agent-workspace" / "questions.md").is_file()


def test_new_instruction_files_are_created_and_ignored(tmp_path: Path):
    iw.init(tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert iw.BLOCK in text and ".agent-workspace/state.md" in text
    ignored = lines(tmp_path / ".gitignore")
    assert {".agent-workspace/", "CLAUDE.md", "GEMINI.md"} <= set(ignored)
    assert len(ignored) == len(set(ignored))
    assert not (tmp_path / "AGENTS.md").exists()


def test_existing_instruction_file_gets_one_block_and_is_not_ignored(tmp_path: Path):
    original = "# Project rules\n\nUse tabs.\n"
    (tmp_path / "CLAUDE.md").write_text(original, encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text(original, encoding="utf-8")
    iw.init(tmp_path)
    iw.init(tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert text.startswith(original)
        assert text.count(iw.BEGIN) == 1 and text.count(iw.END) == 1
    ignored = lines(tmp_path / ".gitignore")
    assert ".agent-workspace/" in ignored
    assert "CLAUDE.md" not in ignored and "GEMINI.md" not in ignored


def test_outdated_block_is_replaced_and_the_rest_is_untouched(tmp_path: Path):
    before = "# Mine\n\nkeep this\n\n"
    after = "\n\nkeep that too\n"
    old = f"{iw.BEGIN}\nmột quy tắc cũ\n{iw.END}\n"
    (tmp_path / "CLAUDE.md").write_text(before + old + after, encoding="utf-8")
    report = iw.init(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert text == before + iw.BLOCK + after
    assert any("CLAUDE.md (block updated)" in item for item in report.updated)
    again = iw.init(tmp_path)
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == text
    assert any("block up to date" in item for item in again.kept) and not again.updated


def test_outdated_block_keeps_crlf(tmp_path: Path):
    old = f"top\r\n{iw.BEGIN}\r\nold\r\n{iw.END}\r\nbottom\r\n"
    (tmp_path / "GEMINI.md").write_bytes(old.encode())
    iw.init(tmp_path)
    expected = f"top\r\n{iw.BEGIN}\r\n{iw.RULE}\r\n{iw.END}\r\nbottom\r\n"
    assert (tmp_path / "GEMINI.md").read_bytes() == expected.encode()


def test_existing_file_without_trailing_newline_and_crlf(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_bytes(b"line one\r\nline two")
    iw.init(tmp_path)
    data = (tmp_path / "CLAUDE.md").read_bytes()
    assert data.startswith(b"line one\r\nline two\r\n\r\n" + iw.BEGIN.encode())
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_existing_gitignore_is_appended_not_rewritten(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("node_modules/\n*.log", encoding="utf-8")
    iw.init(tmp_path)
    ignored = lines(tmp_path / ".gitignore")
    assert ignored[:2] == ["node_modules/", "*.log"]
    assert ignored.count(".agent-workspace/") == 1
    iw.init(tmp_path)
    assert lines(tmp_path / ".gitignore") == ignored


def test_workspace_already_ignored_is_not_added_twice(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(".agent-workspace\n", encoding="utf-8")
    iw.init(tmp_path)
    assert [line for line in lines(tmp_path / ".gitignore") if line.startswith(".agent-workspace")] == [".agent-workspace"]


def test_agents_md_is_used_by_antigravity_when_there_is_no_gemini_md(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Shared\n", encoding="utf-8")
    iw.init(tmp_path)
    assert iw.BEGIN in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert not (tmp_path / "GEMINI.md").exists()
    assert "AGENTS.md" not in lines(tmp_path / ".gitignore")


def test_new_claude_md_imports_existing_agents_md(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Shared\n", encoding="utf-8")
    report = iw.init(tmp_path)
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.index(iw.AGENTS_IMPORT) < claude.index(iw.BEGIN)
    assert "CLAUDE.md" in lines(tmp_path / ".gitignore")
    assert report.warnings


def test_dot_claude_claude_md_counts_as_existing(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
    iw.init(tmp_path)
    assert not (tmp_path / "CLAUDE.md").exists()
    assert iw.BEGIN in (tmp_path / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")


def test_broken_marker_is_left_alone(tmp_path: Path):
    broken = f"# x\n{iw.BEGIN}\nnothing else\n"
    (tmp_path / "CLAUDE.md").write_text(broken, encoding="utf-8")
    report = iw.init(tmp_path)
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == broken
    assert report.warnings


def test_main_returns_error_for_missing_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert iw.main([str(tmp_path / "nope")]) == 2
    assert "not a folder" in capsys.readouterr().err


def test_main_prints_a_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert iw.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "created: .agent-workspace/state.md" in out
    iw.main([str(tmp_path)])
    assert "created:" not in capsys.readouterr().out
