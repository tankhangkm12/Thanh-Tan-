"""Tests for archive_release.py.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import archive_release as ar  # noqa: E402
import checkreport as cr  # noqa: E402

SCRIPT = Path(__file__).parent / "archive_release.py"
DAY = "2026-10-13"
HEAD = "| Gate | Giai đoạn | Trạng thái | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- | --- |\n"
DECISIONS = (
    "# Nhật ký quyết định\n\n"
    "| ID | Câu hỏi | Gate | Hội đồng | Trạng thái | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- | --- | --- | --- |\n"
    '| D-001 | Chọn DB? | G3 | 5 | đã quyết | "D-001: chọn B" | 2026-10-01 |\n'
    "| D-002 | Cache nào? | G4 | 3 | chờ người dùng | | |\n"
    '| D-003 | Kiểu kiến trúc? | G2 | 3 | đã quyết | "D-003: chọn A, cảm ơn" | 2026-10-02 |\n'
    "| D-<xxx> | <câu hỏi> | <G3> | <3> | brief | | |\n"
)
ACCEPTANCE = (
    "# Rủi ro đã chấp nhận\n\n| ID | Điểm | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- |\n"
    '| R-04 | 20 | "R-04: chấp nhận" | 2026-10-03 |\n| R-<xx> | <15–25> | <"R-04: chấp nhận"> | <YYYY-MM-DD> |\n'
)


def put(path: Path, text: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def state_text(approved_upto: int = 10, level: str = "M", skip: set[int] = frozenset(), quote=None) -> str:
    rows = ""
    for n in range(11):
        if n <= approved_upto and n not in skip:
            rows += f'| G{n} | giai đoạn | đã duyệt | "{quote(n) if quote else f"G{n}: duyệt"}" | {DAY} |\n'
        else:
            rows += f"| G{n} | giai đoạn | chưa làm | | |\n"
    return f"# Trạng thái\n\n## Hiện tại\n\n- **Mức áp dụng:** {level}\n- **Giai đoạn hiện tại:** G10\n\n## Gate\n\n{HEAD}{rows}\n## Task đang mở\n\nkhông\n"


class Project:
    """A project folder: an approved workspace with something in every part of the snapshot, and an architecture/ already released by promote_drafts."""

    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.ws = tmp_path / ".agent-workspace"
        self.arch = tmp_path / "architecture"
        put(self.ws / "state.md", state_text())
        put(self.ws / "models.md", "# models\n")
        put(self.ws / "plan" / "plan.md", "# plan\n")
        put(self.ws / "plan" / "tasks" / "T-001-x.md", "# task\n")
        put(self.ws / "stack" / "layers" / "data" / "scoring.md", "# scoring\n")
        put(self.ws / "capacity" / "assumptions.yaml", "dau: 1\n")
        put(self.ws / "decisions" / "decision-log.md", DECISIONS)
        put(self.ws / "decisions" / "D-001-db" / "brief.md", "# brief\n")
        put(self.ws / "reviews" / "R-001-x.md", "# review\n")
        put(self.ws / "risks" / "acceptance.md", ACCEPTANCE)
        put(self.ws / "drafts" / "README.md", "# README\n")
        put(self.ws / "checks" / "links-2026-10-13.md", "# links\n")
        put(self.ws / "inputs" / "ba" / "brief.md", "# ba\n")
        put(self.arch / "README.md", "# README\n")
        self.record()

    def current(self) -> dict[str, str]:
        """sha256 of every file now in architecture/ (the changelog left out), as promote_drafts.py records them."""
        return {p.relative_to(self.arch).as_posix(): cr.sha256_file(p) for p in sorted(self.arch.rglob("*")) if p.is_file() and p.relative_to(self.arch).as_posix() != "CHANGELOG.md"}

    def record(self, day: str = DAY, gate: int = 10, files: dict[str, str] | None = None) -> Path:
        """The report of a successful promote of `gate` that lists what architecture/ holds (default: what it holds now)."""
        files = self.current() if files is None else files
        return put(self.ws / "checks" / f"promote-{day}.md", f"# promote_drafts {day}\n\n## G{gate}: đã chép\n" + cr.render_promoted(gate, files))

    def arch_put(self, rel: str, text: str | bytes) -> Path:
        """A file of architecture/ as promote left it: written and recorded."""
        path = put(self.arch / rel, text)
        self.record()
        return path

    def state(self, **kw) -> None:
        put(self.ws / "state.md", state_text(**kw))

    def run(self, *extra: str) -> int:
        return ar.main(["--workspace", str(self.ws), "--date", DAY, *extra])

    def cli(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(self.ws), "--date", DAY, *extra], capture_output=True, text=True, encoding="utf-8")

    def archived(self, version: int = 1) -> set[str]:
        root = self.ws / "archive" / f"v{version}"
        return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} if root.is_dir() else set()

    def changelog(self) -> str:
        return (self.arch / "CHANGELOG.md").read_text(encoding="utf-8")

    def log(self) -> str:
        return (self.ws / "checks" / f"archive-{DAY}.md").read_text(encoding="utf-8")

    def tree(self) -> dict[str, bytes]:
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in sorted(self.root.rglob("*")) if p.is_file()}


@pytest.fixture
def proj(tmp_path):
    return Project(tmp_path)


# --- the happy path --------------------------------------------------------------------------------------------------------

def test_a_release_snapshots_exactly_the_listed_parts_byte_for_byte(proj, capsys):
    assert proj.run() == 0
    assert proj.archived() == {
        "state.md", "models.md", "plan/plan.md", "plan/tasks/T-001-x.md", "stack/layers/data/scoring.md", "capacity/assumptions.yaml",
        "decisions/decision-log.md", "decisions/D-001-db/brief.md", "reviews/R-001-x.md", "risks/acceptance.md",
    }
    for rel in proj.archived():
        assert (proj.ws / "archive" / "v1" / rel).read_bytes() == (proj.ws / rel).read_bytes()
    assert "đã chụp 10 file -> archive/v1/" in capsys.readouterr().out
    assert not list((proj.ws / "archive").glob("*.partial"))


def test_the_snapshot_keeps_crlf_and_binary_bytes(proj):
    put(proj.ws / "plan" / "crlf.md", b"a\r\nb\r\n")
    put(proj.ws / "stack" / "blob.bin", bytes(range(256)))
    assert proj.run() == 0
    assert (proj.ws / "archive" / "v1" / "plan" / "crlf.md").read_bytes() == b"a\r\nb\r\n"
    assert (proj.ws / "archive" / "v1" / "stack" / "blob.bin").read_bytes() == bytes(range(256))


def test_the_changelog_is_created_with_the_entry_of_the_release(proj):
    assert proj.run() == 0
    text = proj.changelog()
    assert text.startswith("# CHANGELOG\n\n## v1 (2026-10-13)\n")
    assert "- Mức áp dụng: M" in text and '- Phát hành khi người dùng duyệt: "G10: duyệt"' in text and "- Bản chụp: `archive/v1/`" in text
    assert "### So với bản trước" not in text


def test_the_entry_lists_the_decisions_the_user_settled_and_the_risks_accepted(proj):
    proj.run()
    text = proj.changelog()
    assert '- D-001 (G3): Chọn DB? -> B; người dùng nói "D-001: chọn B", 2026-10-01' in text
    assert '- D-003 (G2): Kiểu kiến trúc? -> A; người dùng nói "D-003: chọn A, cảm ơn", 2026-10-02' in text
    assert "D-002" not in text and "D-<xxx>" not in text
    assert '- R-04 (20 điểm): người dùng nói "R-04: chấp nhận", 2026-10-03' in text and "R-<xx>" not in text


def test_with_nothing_decided_or_accepted_the_entry_says_so(proj):
    put(proj.ws / "decisions" / "decision-log.md", "# log\n")
    (proj.ws / "risks" / "acceptance.md").unlink()
    assert proj.run() == 0
    text = proj.changelog()
    assert "### Quyết định đã chốt\n\n- không có" in text and "### Rủi ro đã chấp nhận\n\n- không có" in text


def test_the_run_is_logged_and_a_second_run_appends_to_the_same_report(proj):
    proj.run()
    proj.run()
    log = proj.log()
    assert log.startswith("# archive_release") and "## v1: đã phát hành" in log and "## v2: đã phát hành" in log
    assert "`archive/v1/`: 10 file" in log


# --- versions --------------------------------------------------------------------------------------------------------------

def test_the_version_goes_up_from_the_highest_archive_and_the_new_entry_is_first(proj):
    put(proj.ws / "archive" / "v1" / "state.md", "old")
    put(proj.ws / "archive" / "v4" / "state.md", "old")
    (proj.ws / "archive" / "notes").mkdir()
    assert proj.run() == 0
    assert proj.archived(5) and (proj.ws / "archive" / "v4" / "state.md").read_text() == "old"
    proj.run()
    text = proj.changelog()
    assert text.index("## v6 ") < text.index("## v5 ") and text.startswith("# CHANGELOG\n\n## v6")


@pytest.mark.parametrize("given", ["3", "v3", "V3"])
def test_a_given_version_is_used(proj, given):
    assert proj.run("--version", given) == 0
    assert proj.archived(3) and "## v3 (" in proj.changelog()


@pytest.mark.parametrize("given", ["0", "-1", "x", "v", "1.5", "v1a", ""])
def test_a_wrong_version_is_a_usage_error(proj, given):
    with pytest.raises(SystemExit) as stop:
        proj.run("--version", given)
    assert stop.value.code == 2 and not (proj.ws / "archive").exists()


def test_an_existing_version_is_never_overwritten(proj, capsys):
    put(proj.ws / "archive" / "v2" / "state.md", "old")
    before = proj.tree()
    assert proj.run("--version", "2") == 1
    assert "archive/v2 đã có" in capsys.readouterr().out
    assert {k: v for k, v in proj.tree().items() if not k.startswith(".agent-workspace/checks/archive")} == {k: v for k, v in before.items()}
    assert not (proj.arch / "CHANGELOG.md").exists()


def test_a_version_that_is_a_file_or_a_dangling_name_counts_as_existing(proj):
    put(proj.ws / "archive" / "v1", "a file")
    assert proj.run("--version", "1") == 1
    assert (proj.ws / "archive" / "v1").read_text() == "a file"


def test_the_changelog_already_having_the_version_is_refused(proj, capsys):
    put(proj.arch / "CHANGELOG.md", "# CHANGELOG\n\n## v3 (2026-01-01)\n\n- x\n")
    assert proj.run("--version", "3") == 1
    assert "CHANGELOG.md đã có mục v3" in capsys.readouterr().out
    assert not proj.archived(3)
    assert proj.run("--version", "31") == 0


# --- the changelog ---------------------------------------------------------------------------------------------------------

def test_the_entry_goes_before_the_first_entry_and_after_the_title_and_intro(proj):
    put(proj.arch / "CHANGELOG.md", "# Lịch sử\n\nGhi chú đầu.\n\n## v1 (2026-01-01)\n\n- cũ\n")
    assert proj.run("--version", "2") == 0
    text = proj.changelog()
    assert text.startswith("# Lịch sử\n\nGhi chú đầu.\n\n## v2 (2026-10-13)\n")
    assert text.index("## v2 ") < text.index("## v1 ") and text.endswith("## v1 (2026-01-01)\n\n- cũ\n")
    assert "\n\n## v1 (" in text


def test_a_changelog_without_entries_gets_the_entry_at_the_end(proj):
    put(proj.arch / "CHANGELOG.md", "# Lịch sử\n\nChưa có gì.\n")
    assert proj.run() == 0
    assert proj.changelog().startswith("# Lịch sử\n\nChưa có gì.\n\n## v1 (")


def test_an_empty_changelog_file_is_treated_as_new(proj):
    put(proj.arch / "CHANGELOG.md", "")
    assert proj.run() == 0
    assert proj.changelog().startswith("# CHANGELOG\n\n## v1 (")


def test_a_crlf_changelog_stays_crlf(proj):
    put(proj.arch / "CHANGELOG.md", b"# CHANGELOG\r\n\r\n## v1 (2026-01-01)\r\n\r\n- cu\r\n")
    assert proj.run("--version", "2") == 0
    raw = (proj.arch / "CHANGELOG.md").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert raw.startswith(b"# CHANGELOG\r\n\r\n## v2 (")


def test_a_changelog_that_is_a_folder_is_refused_up_front(proj, capsys):
    (proj.arch / "CHANGELOG.md").mkdir()
    assert proj.run() == 1 and not proj.archived()
    assert "không phải file" in capsys.readouterr().out


def test_rows_of_the_logs_with_a_wrong_id_are_not_listed(proj):
    put(proj.ws / "decisions" / "decision-log.md", DECISIONS + '| X-009 | Lạ? | G2 | 3 | đã quyết | "X-009: chọn A" | 2026-10-02 |\n')
    put(proj.ws / "risks" / "acceptance.md", ACCEPTANCE + '| Q-09 | 20 | "Q-09: chấp nhận" | 2026-10-03 |\n| R-05 | <15–25> | "R-05: chấp nhận" | 2026-10-03 |\n')
    proj.run()
    text = proj.changelog()
    assert "X-009" not in text and "Q-09" not in text and "R-05" not in text and "D-001" in text and "R-04" in text


def test_the_changelog_is_written_in_place_without_leaving_a_temporary_file(proj):
    proj.run()
    assert sorted(p.name for p in proj.arch.iterdir()) == ["CHANGELOG.md", "README.md"]


def test_with_entry_on_the_pieces():
    entry = "## v2 (d)\n\n- x\n"
    assert ar.with_entry(None, entry) == "# CHANGELOG\n\n" + entry
    assert ar.with_entry("  \n", entry) == "# CHANGELOG\n\n" + entry
    assert ar.with_entry("# T\n\n## v1\n\n- a\n", entry) == "# T\n\n## v2 (d)\n\n- x\n\n## v1\n\n- a\n"
    assert ar.with_entry("# T\n", entry) == "# T\n\n## v2 (d)\n\n- x\n"
    assert ar.with_entry("# T\r\n\r\n## v1\r\n", entry) == "# T\r\n\r\n## v2 (d)\r\n\r\n- x\r\n\r\n## v1\r\n"


def test_changelog_has_matches_the_exact_version():
    assert ar.changelog_has("## v1 (x)\n", 1) and ar.changelog_has("## v12\n", 12) and ar.changelog_has("##   v3: x\n", 3)
    assert not ar.changelog_has("## v12 (x)\n", 1) and not ar.changelog_has("### v1\n", 1) and not ar.changelog_has("text ## v1\n", 1)
    assert not ar.changelog_has("## v1a\n", 1) and not ar.changelog_has("## vv1\n", 1)


# --- the previous design ---------------------------------------------------------------------------------------------------

def old(proj, rel, text):
    return put(proj.ws / "inputs" / "previous-design" / rel, text)


def test_with_a_previous_design_the_entry_lists_files_added_changed_and_removed(proj):
    old(proj, "README.md", "# README\n")                    # same as architecture/README.md
    old(proj, "01-system/a.md", "old a\n")                  # changed
    old(proj, "01-system/gone.md", "gone\n")                # removed
    proj.arch_put("01-system/a.md", "new a\n")
    proj.arch_put("02-new/n.md", "new\n")             # added
    assert proj.run() == 0
    text = proj.changelog()
    section = text[text.index("### So với bản trước"):]
    assert "- Thêm (1):\n  - `02-new/n.md`" in section
    assert "- Đổi (1):\n  - `01-system/a.md`" in section
    assert "- Xóa (1):\n  - `01-system/gone.md`" in section
    assert "- Không đổi: 1 file" in section


def test_line_ends_alone_are_not_a_change(proj):
    old(proj, "README.md", "# README\r\nline\r\n")
    proj.arch_put("README.md", "# README\nline\n")
    proj.run()
    assert "- Đổi (0): không có" in proj.changelog() and "- Không đổi: 1 file" in proj.changelog()


def test_the_changelog_itself_is_not_compared(proj):
    old(proj, "CHANGELOG.md", "# old\n")
    old(proj, "README.md", "# README\n")
    proj.run()
    text = proj.changelog()
    assert "CHANGELOG.md`" not in text.split("### So với bản trước")[1]
    assert "- Thêm (0): không có" in text and "- Xóa (0): không có" in text


def test_an_identical_previous_design_reports_nothing_changed(proj):
    old(proj, "README.md", "# README\n")
    proj.run()
    section = proj.changelog().split("### So với bản trước")[1]
    assert "- Thêm (0): không có" in section and "- Đổi (0): không có" in section and "- Xóa (0): không có" in section


def test_an_empty_previous_design_folder_makes_every_file_added(proj):
    (proj.ws / "inputs" / "previous-design").mkdir(parents=True)
    proj.run()
    assert "- Thêm (1):\n  - `README.md`" in proj.changelog()


def test_the_previous_design_is_not_part_of_the_snapshot(proj):
    old(proj, "README.md", "# README\n")
    proj.run()
    assert not any(rel.startswith("inputs/") for rel in proj.archived())


# --- what is refused -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("gate", range(11))
def test_every_gate_up_to_g10_must_be_approved(proj, gate, capsys):
    proj.state(skip={gate})
    assert proj.run() == 1
    assert f"G{gate}: " in capsys.readouterr().out
    assert not proj.archived() and not (proj.arch / "CHANGELOG.md").exists()


def test_g10_approved_without_the_users_words_is_refused(proj, capsys):
    proj.state(quote=lambda n: "ok" if n == 10 else f"G{n}: duyệt")
    assert proj.run() == 1
    assert "không có \"G10: duyệt\"" in capsys.readouterr().out


def test_g1_words_do_not_approve_g10(proj):
    proj.state(quote=lambda n: "G1: duyệt" if n == 10 else f"G{n}: duyệt")
    assert proj.run() == 1


def test_no_state_md_is_refused(proj, capsys):
    (proj.ws / "state.md").unlink()
    assert proj.run() == 1
    assert "không có state.md" in capsys.readouterr().out


def test_no_architecture_folder_is_refused_and_nothing_is_created(proj, capsys):
    (proj.arch / "README.md").unlink()
    proj.arch.rmdir()
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "chưa có architecture/" in out and "promote_drafts.py --gate G10" in out
    assert not proj.arch.exists() and not proj.archived()


def test_every_reason_is_listed_at_once(proj, capsys):
    proj.state(skip={2, 5})
    (proj.arch / "README.md").unlink()
    proj.arch.rmdir()
    put(proj.ws / "archive" / "v1" / "x", "x")
    assert proj.run("--version", "1") == 1
    out = capsys.readouterr().out
    assert "4 điều kiện" in out and "G2: " in out and "G5: " in out and "architecture/" in out and "archive/v1 đã có" in out


def test_a_refusal_is_logged_and_writes_nothing_else(proj):
    proj.state(skip={4})
    before = proj.tree()
    assert proj.run() == 1
    assert "## v1: TỪ CHỐI" in proj.log() and "G4: " in proj.log()
    after = proj.tree()
    assert set(after) - set(before) == {".agent-workspace/checks/archive-2026-10-13.md"}
    assert all(after[k] == v for k, v in before.items())


def test_a_symlink_in_the_snapshot_is_refused(proj, monkeypatch, capsys):
    put(proj.ws / "plan" / "evil.md", "x")
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self.name == "evil.md" else real(self))
    assert proj.run() == 1
    assert "plan/evil.md là liên kết tượng trưng" in capsys.readouterr().out and not proj.archived()


def test_a_snapshot_folder_that_is_a_symlink_is_refused(proj, monkeypatch, capsys):
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self.name == "reviews" else real(self))
    assert proj.run() == 1
    assert "reviews là liên kết tượng trưng" in capsys.readouterr().out and not proj.archived()


def test_a_symlink_in_the_previous_design_is_refused(proj, monkeypatch, capsys):
    old(proj, "a.md", "x")
    old(proj, "link.md", "y")
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self.name == "link.md" else real(self))
    assert proj.run() == 1
    assert "inputs/previous-design/link.md là liên kết tượng trưng" in capsys.readouterr().out


def test_a_symlink_in_architecture_is_refused(proj, monkeypatch, capsys):
    proj.arch_put("link.md", "y")
    old(proj, "a.md", "x")
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self.name == "link.md" and "architecture" in self.parts else real(self))
    assert proj.run() == 1
    assert "architecture/link.md là liên kết tượng trưng" in capsys.readouterr().out


# --- notes and warnings ----------------------------------------------------------------------------------------------------

def test_a_part_that_is_missing_is_only_a_note(proj, capsys):
    import shutil
    shutil.rmtree(proj.ws / "reviews")
    (proj.ws / "models.md").unlink()
    assert proj.run() == 0
    out = capsys.readouterr().out
    assert "note: không có reviews trong workspace" in out and "note: không có models.md" in out
    assert "reviews/R-001-x.md" not in proj.archived()


# --- a release is what promote left: the report of the last G10 promote against architecture/ -------------------------------

def test_without_a_promote_report_nothing_is_released(proj, capsys):
    (proj.ws / "checks" / f"promote-{DAY}.md").unlink()
    before = proj.tree()
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "không có báo cáo checks/promote-<ngày>.md" in out and "promote_drafts.py --gate G10" in out
    assert not proj.archived() and not (proj.arch / "CHANGELOG.md").exists()
    assert set(proj.tree()) - set(before) == {".agent-workspace/checks/archive-2026-10-13.md"}


def test_a_promote_report_of_another_gate_does_not_count(proj):
    proj.record(gate=9)
    assert proj.run() == 1 and not proj.archived()


def test_a_promote_report_without_the_hash_block_does_not_count(proj):
    put(proj.ws / "checks" / f"promote-{DAY}.md", "# promote_drafts\n\n## G10: đã chép\n\n- `README.md`: mới\n")
    assert proj.run() == 1 and not proj.archived()


def test_a_block_without_files_or_without_a_valid_gate_is_ignored(proj):
    good = cr.render_promoted(10, proj.current())
    put(proj.ws / "checks" / f"promote-{DAY}.md", "## G10\n" + cr.render_promoted(10, {}) + "\n" + good.replace("- Gate: G10", "- Gate: G11"))
    assert proj.run() == 1 and not proj.archived()


def test_a_file_edited_by_hand_after_promote_is_named_and_refused(proj, capsys):
    (proj.arch / "README.md").write_text("# README\nedited\n", encoding="utf-8")
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "architecture/README.md khác bản đã chép" in out and "sửa tay" in out
    assert not proj.archived() and not (proj.arch / "CHANGELOG.md").exists()


def test_a_file_deleted_after_promote_is_named_and_refused(proj, capsys):
    proj.arch_put("01-system/a.md", "a\n")
    (proj.arch / "01-system" / "a.md").unlink()
    assert proj.run() == 1
    assert "architecture/01-system/a.md" in capsys.readouterr().out and "không còn" in proj.log()


def test_a_file_added_after_promote_is_named_and_refused(proj, capsys):
    put(proj.arch / "extra" / "x.md", "x\n")
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "architecture/extra/x.md không thuộc lần chép G10" in out and "file thừa" in out
    assert not proj.archived()


def test_every_file_that_is_off_is_listed(proj, capsys):
    proj.arch_put("a.md", "a\n")
    proj.arch_put("b.md", "b\n")
    (proj.arch / "a.md").write_text("changed", encoding="utf-8")
    (proj.arch / "b.md").unlink()
    put(proj.arch / "c.md", "c\n")
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "3 điều kiện" in out and "architecture/a.md khác" in out and "architecture/b.md" in out and "architecture/c.md không thuộc" in out


def test_line_endings_alone_do_not_make_a_file_differ_from_the_record(proj):
    proj.arch_put("a.md", "x\r\ny\r\n")
    (proj.arch / "a.md").write_bytes(b"x\ny\n")
    assert proj.run() == 0


def test_the_changelog_is_not_part_of_the_record(proj):
    put(proj.arch / "CHANGELOG.md", "# CHANGELOG\n\nedited by hand, or from an earlier release\n")
    assert proj.run() == 0
    assert proj.run() == 0 and proj.archived(2)


def test_the_latest_promote_report_by_date_is_the_one_that_counts(proj):
    stale = {"README.md": "0" * 64}
    proj.record(day="2026-10-01", files=stale)
    assert proj.run() == 0                                        # the newer, matching report wins over the older stale one
    proj.record(day="2026-10-20", files=stale)
    assert proj.run() == 1                                        # a newer report that does not match wins over the older matching one
    proj.record(day="2026-10-05")
    assert proj.run() == 1


def test_in_one_report_the_last_block_of_the_gate_counts(proj):
    path = proj.ws / "checks" / f"promote-{DAY}.md"
    good = cr.render_promoted(10, proj.current())
    path.write_text("## G10\n" + good + "\n## G10 again\n" + cr.render_promoted(10, {"README.md": "1" * 64}), encoding="utf-8")
    assert proj.run() == 1
    path.write_text("## G10\n" + cr.render_promoted(10, {"README.md": "1" * 64}) + "\n## G10 again\n" + good, encoding="utf-8")
    assert proj.run() == 0


def test_a_later_report_without_a_block_does_not_hide_an_earlier_success(proj):
    put(proj.ws / "checks" / "promote-2026-12-01.md", "# promote_drafts\n\n## G10: TỪ CHỐI\n\n- duyệt: G3\n")
    assert proj.run() == 0


def test_a_block_of_a_lower_gate_in_the_same_report_is_not_the_release(proj):
    path = proj.ws / "checks" / f"promote-{DAY}.md"
    path.write_text("## G9\n" + cr.render_promoted(9, proj.current()) + "\n## G10\n" + cr.render_promoted(10, {"README.md": "1" * 64}), encoding="utf-8")
    assert proj.run() == 1


def test_the_promote_check_comes_from_the_config_prefix(proj, tmp_path):
    (proj.ws / "checks" / f"promote-{DAY}.md").rename(proj.ws / "checks" / f"chep-{DAY}.md")
    assert proj.run() == 1
    assert proj.run("--config", str(config(tmp_path, promote_prefix="chep"))) == 0


def test_dry_run_also_refuses_a_changed_architecture(proj, capsys):
    (proj.arch / "README.md").write_text("changed", encoding="utf-8")
    before = proj.tree()
    assert proj.run("--dry-run") == 1
    assert "architecture/README.md khác" in capsys.readouterr().out and proj.tree() == before


def test_the_promote_check_is_skipped_when_architecture_is_missing(proj, capsys):
    (proj.arch / "README.md").unlink()
    proj.arch.rmdir()
    assert proj.run() == 1
    out = capsys.readouterr().out
    assert "chưa có architecture/" in out and "promote:" not in out


def test_a_real_promote_then_a_release(tmp_path, capsys):
    from test_promote_drafts import Project as PromoteProject
    p = PromoteProject(tmp_path, 10)
    assert p.promote() == 0
    capsys.readouterr()
    assert ar.main(["--workspace", str(p.ws), "--date", DAY]) == 0
    assert (p.ws / "archive" / "v1" / "state.md").is_file() and (p.arch / "CHANGELOG.md").is_file()
    (p.arch / "README.md").write_text("changed by hand", encoding="utf-8")
    assert ar.main(["--workspace", str(p.ws), "--date", DAY]) == 1
    assert "architecture/README.md khác bản đã chép" in capsys.readouterr().out
    assert not (p.ws / "archive" / "v2").exists()
    assert p.promote() == 0 and ar.main(["--workspace", str(p.ws), "--date", DAY]) == 0 and (p.ws / "archive" / "v2").is_dir()


@pytest.mark.parametrize("level", ["", "<chưa duyệt | S | M | L | XL>", "XXL", "chưa duyệt"])
def test_a_level_that_is_not_s_m_l_xl_is_a_warning_and_the_changelog_says_so(proj, level, capsys):
    proj.state(level=level)
    assert proj.run() == 0
    assert "- Mức áp dụng: chưa ghi" in proj.changelog()
    assert "warning: state.md: Mức áp dụng" in capsys.readouterr().out


@pytest.mark.parametrize("level", ["S", "M", "L", "XL"])
def test_each_level_is_written_as_is(proj, level):
    proj.state(level=level)
    proj.run()
    assert f"- Mức áp dụng: {level}\n" in proj.changelog()


# --- dry run ---------------------------------------------------------------------------------------------------------------

def test_dry_run_writes_nothing_but_says_what_it_would_do(proj, capsys):
    before = proj.tree()
    assert proj.run("--dry-run") == 0
    assert proj.tree() == before
    assert "sẽ chụp (--dry-run) 10 file -> archive/v1/" in capsys.readouterr().out


def test_dry_run_still_refuses(proj, capsys):
    proj.state(skip={7})
    before = proj.tree()
    assert proj.run("--dry-run") == 1
    assert "G7: " in capsys.readouterr().out and proj.tree() == before


# --- failures --------------------------------------------------------------------------------------------------------------

def test_a_copy_that_reads_back_different_leaves_no_snapshot_and_no_changelog(proj, monkeypatch, capsys):
    real = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: real(self, data + b"x" if self.name == "plan.md" else data))
    assert proj.run() == 1
    assert "plan/plan.md: đọc lại khác" in capsys.readouterr().out
    assert not (proj.ws / "archive" / "v1").exists() and not list((proj.ws / "archive").glob("*.partial"))
    assert not (proj.arch / "CHANGELOG.md").exists()
    assert "## v1: LỖI khi phát hành" in proj.log()


def test_a_failed_changelog_write_removes_the_snapshot(proj, monkeypatch, capsys):
    def boom(path, text):
        raise OSError("disk full")
    monkeypatch.setattr(ar, "write_changelog", boom)
    assert proj.run() == 1
    assert "CHANGELOG.md: disk full" in capsys.readouterr().out
    assert not (proj.ws / "archive" / "v1").exists() and not (proj.arch / "CHANGELOG.md").exists()
    assert proj.run() == 1  # still failing the same way, and still no v1 in the way


def test_after_a_failed_run_the_next_one_still_makes_v1(proj, monkeypatch):
    real = ar.write_changelog
    monkeypatch.setattr(ar, "write_changelog", lambda path, text: (_ for _ in ()).throw(OSError("x")))
    assert proj.run() == 1
    monkeypatch.setattr(ar, "write_changelog", real)
    assert proj.run() == 0 and proj.archived(1) and "## v1 (" in proj.changelog()


def test_a_leftover_partial_folder_is_replaced(proj):
    put(proj.ws / "archive" / "v1.partial" / "junk.md", "junk")
    assert proj.run() == 0
    assert "junk.md" not in proj.archived() and not (proj.ws / "archive" / "v1.partial").exists()


def test_a_partial_folder_does_not_count_as_a_version(proj):
    put(proj.ws / "archive" / "v7.partial" / "junk.md", "junk")
    assert ar.existing_versions(proj.ws / "archive") == []


def test_an_unreadable_snapshot_file_is_reported_not_a_traceback(proj, monkeypatch, capsys):
    real = Path.read_bytes

    def fail(self):
        if self.name == "plan.md" and "archive" not in self.parts:
            raise PermissionError("denied")
        return real(self)
    monkeypatch.setattr(Path, "read_bytes", fail)
    assert proj.run() == 1
    assert "denied" in capsys.readouterr().out and not (proj.ws / "archive" / "v1").exists()


# --- arguments and config --------------------------------------------------------------------------------------------------

def test_no_workspace_is_a_usage_error(tmp_path, capsys):
    assert ar.main(["--workspace", str(tmp_path / "nope")]) == 2
    assert "not a workspace" in capsys.readouterr().err


@pytest.mark.parametrize("where", ["inside", "same", "parent"])
def test_architecture_inside_around_or_equal_to_the_workspace_is_a_usage_error(proj, where, capsys):
    target = {"inside": proj.ws / "out", "same": proj.ws, "parent": proj.root}[where]
    assert proj.run("--architecture", str(target)) == 2
    assert "phải nằm ngoài workspace" in capsys.readouterr().err


def test_architecture_can_be_given(proj, tmp_path):
    other = tmp_path / "elsewhere" / "arch"
    put(other / "README.md", "# README\n")
    assert proj.run("--architecture", str(other)) == 0
    assert (other / "CHANGELOG.md").is_file() and not (proj.arch / "CHANGELOG.md").exists()


def config(tmp_path, **changes) -> Path:
    data = yaml.safe_load(ar.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data.update(changes)
    return put(tmp_path / "cfg.yaml", yaml.safe_dump(data, allow_unicode=True))


@pytest.mark.parametrize("changes", [
    {"gate": 11}, {"gate": "10"}, {"gate": True}, {"archive_dir": ""}, {"snapshot": []}, {"snapshot": "state.md"}, {"snapshot": ["a", "a"]},
    {"snapshot": ["../x"]}, {"snapshot": ["/etc"]}, {"snapshot": ["archive"]}, {"snapshot": ["archive/sub"]}, {"archive_dir": "../a"},
    {"changelog": 3}, {"previous_design": ".."}, {"levels": []}, {"levels": [1]},
    {"promote_prefix": ""}, {"promote_prefix": 3}, {"promote_prefix": "a/b"}, {"promote_prefix": "a\\b"},
])
def test_a_bad_config_is_a_usage_error(proj, tmp_path, changes, capsys):
    assert proj.run("--config", str(config(tmp_path, **changes))) == 2
    assert "config error" in capsys.readouterr().err


@pytest.mark.parametrize("key", ["archive_dir", "changelog", "previous_design"])
def test_an_absolute_path_in_the_config_is_a_usage_error(proj, tmp_path, key, capsys):
    assert proj.run("--config", str(config(tmp_path, **{key: str(tmp_path)}))) == 2
    assert "đường dẫn tương đối" in capsys.readouterr().err
    assert proj.run("--config", str(config(tmp_path, snapshot=[str(tmp_path)]))) == 2


def test_a_missing_or_broken_config_is_a_usage_error(proj, tmp_path):
    assert proj.run("--config", str(tmp_path / "none.yaml")) == 2
    assert proj.run("--config", str(put(tmp_path / "bad.yaml", ": : :\n  - ["))) == 2
    assert proj.run("--config", str(put(tmp_path / "list.yaml", "- a\n"))) == 2


def test_the_snapshot_list_comes_from_the_config(proj, tmp_path):
    assert proj.run("--config", str(config(tmp_path, snapshot=["state.md", "risks"]))) == 0
    assert proj.archived() == {"state.md", "risks/acceptance.md"}


def test_the_archive_folder_name_comes_from_the_config(proj, tmp_path):
    assert proj.run("--config", str(config(tmp_path, archive_dir="releases"))) == 0
    assert (proj.ws / "releases" / "v1" / "state.md").is_file() and not (proj.ws / "archive").exists()


def test_the_changelog_name_comes_from_the_config(proj, tmp_path):
    assert proj.run("--config", str(config(tmp_path, changelog="HISTORY.md"))) == 0
    assert (proj.arch / "HISTORY.md").is_file() and not (proj.arch / "CHANGELOG.md").exists()


def test_the_gate_comes_from_the_config(proj, tmp_path):
    proj.state(approved_upto=8)
    proj.record(gate=8)
    assert proj.run() == 1
    assert proj.run("--config", str(config(tmp_path, gate=8))) == 0


def test_the_shipped_config_snapshots_what_the_plan_says_plus_risks_and_models():
    cfg, errors = ar.load_config(ar.DEFAULT_CONFIG)
    assert errors == [] and cfg.gate == 10
    assert set(cfg.snapshot) == {"state.md", "plan", "stack", "capacity", "decisions", "reviews", "risks", "models.md"}
    assert cfg.levels == ["S", "M", "L", "XL"]


# --- the script run on its own ---------------------------------------------------------------------------------------------

def test_cli_exit_codes(proj):
    done = proj.cli()
    assert done.returncode == 0 and "đã chụp" in done.stdout
    again = proj.cli("--version", "1")
    assert again.returncode == 1 and "error:" in again.stdout
    assert proj.cli("--version", "zero").returncode == 2
    assert subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(proj.root / "none")], capture_output=True, text=True).returncode == 2
