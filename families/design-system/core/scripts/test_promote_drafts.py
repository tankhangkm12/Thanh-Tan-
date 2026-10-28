"""Tests for promote_drafts.py.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import approvals as ap  # noqa: E402
import check_profile as cp  # noqa: E402
import checkreport as cr  # noqa: E402
import promote_drafts as pd  # noqa: E402

SCRIPT = Path(__file__).parent / "promote_drafts.py"
CONFIG, _ = cr.load_config()
DAY = "2026-10-12"
HEAD = "| Gate | Giai đoạn | Trạng thái | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- | --- |\n"


def put(path: Path, text: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def state_text(approved_upto: int) -> str:
    rows = "".join(
        (f'| G{n} | giai đoạn | đã duyệt | "G{n}: duyệt" | {DAY} |\n' if n <= approved_upto else f"| G{n} | giai đoạn | chưa làm | | |\n")
        for n in range(11)
    )
    return f"# Trạng thái\n\n## Gate\n\n{HEAD}{rows}\n## Task đang mở\n\nkhông\n"


class Project:
    """A project folder: .agent-workspace/ with drafts for `gate`, an approved state and a clean fresh report of every script it needs."""

    def __init__(self, tmp_path: Path, gate: int):
        self.root = tmp_path
        self.ws = tmp_path / ".agent-workspace"
        self.gate = gate
        self.arch = tmp_path / "architecture"
        put(self.ws / "state.md", state_text(gate))
        for entry in pd.entries_of(gate):
            if entry.endswith(".md"):
                put(self.ws / "drafts" / entry, f"# {entry}\n")
            else:
                put(self.ws / "drafts" / entry / "a.md", f"# {entry} a\n")
                put(self.ws / "drafts" / entry / "sub" / "b.md", f"# {entry} b\n")
        self.reports()

    def reports(self, day=DAY, **overrides):
        for script in CONFIG.gates[self.gate]:
            self.report(script, day, **overrides)

    def report(self, script, day=DAY, ok=True, gate="default", mode="default", files=None):
        spec = CONFIG.reports[script]
        gate = (f"G{self.gate}" if spec.gated else None) if gate == "default" else gate
        modes = spec.modes_for(self.gate)
        mode = (modes[0] if modes else None) if mode == "default" else mode
        if files is None:
            files = cr.hash_files(self.ws, cr.expand(self.ws, spec.scope))
        return put(self.ws / "checks" / f"{spec.prefix}-{day}.md", "# báo cáo\n" + cr.render(script + ".py", ok, files, gate, mode))

    def draft(self, rel: str) -> Path:
        return self.ws / "drafts" / rel

    def run(self, *extra: str, gate: int | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--gate", f"G{self.gate if gate is None else gate}", "--workspace", str(self.ws), "--date", DAY, *extra],
                              capture_output=True, text=True, encoding="utf-8")

    def promote(self, *extra: str, gate: int | None = None) -> int:
        return pd.main(["--gate", f"G{self.gate if gate is None else gate}", "--workspace", str(self.ws), "--date", DAY, *extra])

    def copied(self) -> set[str]:
        return {p.relative_to(self.arch).as_posix() for p in self.arch.rglob("*") if p.is_file()} if self.arch.is_dir() else set()

    def log(self) -> str:
        return (self.ws / "checks" / f"promote-{DAY}.md").read_text(encoding="utf-8")


@pytest.fixture
def g3(tmp_path):
    return Project(tmp_path, 3)


# --- the happy path --------------------------------------------------------------------------------------------------------

def test_an_approved_gate_with_clean_fresh_reports_is_copied_byte_for_byte(g3, capsys):
    assert g3.promote() == 0
    assert g3.copied() == {"01-system/a.md", "01-system/sub/b.md"}
    for rel in g3.copied():
        assert (g3.arch / rel).read_bytes() == g3.draft(rel).read_bytes()
    out = capsys.readouterr().out
    assert "đã chép 2 file (2 mới, 0 ghi đè)" in out and "warning" not in out


def test_the_run_is_logged_and_a_second_run_appends_to_the_same_report(g3):
    g3.promote()
    g3.promote()
    log = g3.log()
    assert log.startswith("# promote_drafts") and log.count("## G3: đã chép") == 2
    assert "2 file: 2 mới" in log and "2 file: 0 mới, 0 ghi đè, 2 không đổi" in log


def test_a_copy_that_reads_back_different_is_an_error(g3, monkeypatch, capsys):
    real = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: real(self, data + b"x" if self.name == "a.md" else data))
    assert g3.promote() == 1
    assert "đọc lại khác" in capsys.readouterr().out


def test_running_again_changes_nothing_and_still_succeeds(g3, capsys):
    g3.promote()
    capsys.readouterr()
    before = {rel: (g3.arch / rel).read_bytes() for rel in g3.copied()}
    assert g3.promote() == 0
    out = capsys.readouterr().out
    assert "warning" not in out and "0 mới, 0 ghi đè" in out
    assert {rel: (g3.arch / rel).read_bytes() for rel in g3.copied()} == before


def test_line_endings_and_binary_files_are_copied_exactly(g3):
    put(g3.draft("01-system/crlf.md"), b"a\r\nb\r\n")
    put(g3.draft("01-system/diagram.png"), bytes(range(256)))
    g3.reports()
    assert g3.promote() == 0
    assert (g3.arch / "01-system/crlf.md").read_bytes() == b"a\r\nb\r\n"
    assert (g3.arch / "01-system/diagram.png").read_bytes() == bytes(range(256))


def test_the_default_architecture_folder_is_next_to_the_workspace_and_a_flag_overrides_it(g3, tmp_path):
    other = tmp_path / "elsewhere" / "arch"
    assert g3.promote("--architecture", str(other)) == 0
    assert (other / "01-system/a.md").is_file() and not g3.arch.exists()


@pytest.mark.parametrize("gate, expected", [
    (0, {"00-context/project-profile.md"}),
    (1, {"00-context/a.md", "00-context/sub/b.md"}),
    (2, {"02-tech-stack/selection-criteria.md"}),
    (4, {"02-tech-stack/a.md", "02-tech-stack/sub/b.md"}),
    (5, {"03-capacity/a.md", "03-capacity/sub/b.md"}),
    (6, {"04-flows/a.md", "04-flows/sub/b.md"}),
    (7, {f"{p}/{n}" for p in ("05-frontend", "06-backend", "07-data") for n in ("a.md", "sub/b.md")}),
    (8, {f"{p}/{n}" for p in ("08-security", "09-infrastructure", "10-process") for n in ("a.md", "sub/b.md")}),
    (9, {f"{p}/{n}" for p in ("11-risks", "12-roadmap") for n in ("a.md", "sub/b.md")}),
])
def test_each_gate_copies_exactly_its_entries(tmp_path, gate, expected):
    project = Project(tmp_path, gate)
    # drafts of every other part exist too: only this gate's entries may be copied
    for part in cp.PARTS:
        put(project.draft(f"{part}/other.md"), "# khác\n")
    project.reports()
    assert project.promote() == 0
    others = {f"{entry}/other.md" for entry in pd.entries_of(gate) if not entry.endswith(".md")}      # a folder entry is copied whole
    assert project.copied() == expected | others


def test_g2_copies_the_single_file_not_the_rest_of_its_part(tmp_path):
    project = Project(tmp_path, 2)
    put(project.draft("02-tech-stack/versions-features.md"), "# chưa tới G4\n")
    project.reports()
    assert project.promote() == 0
    assert project.copied() == {"02-tech-stack/selection-criteria.md"}


def test_the_entries_are_those_of_check_profile():
    for gate in range(10):
        assert pd.entries_of(gate) == cp.GATE_ENTRIES[gate]
    assert pd.entries_of(10)[-1] == "README.md" and set(pd.entries_of(10)) >= {e for g in range(10) for e in cp.GATE_ENTRIES[g]}


# --- approval ---------------------------------------------------------------------------------------------------------------

def refused(project: Project, *extra: str) -> str:
    proc = project.run(*extra)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "TỪ CHỐI" in proc.stdout
    assert project.copied() == set()
    return proc.stdout


def test_an_unapproved_gate_is_refused_and_nothing_is_copied(g3):
    put(g3.ws / "state.md", state_text(2))
    out = refused(g3)
    assert "G3" in out and "chưa" in out and "duyệt" in out


def test_an_earlier_gate_that_is_not_approved_blocks_a_later_one(g3):
    text = state_text(3).replace('| G1 | giai đoạn | đã duyệt | "G1: duyệt" |', "| G1 | giai đoạn | chờ duyệt | |")
    put(g3.ws / "state.md", text)
    g3.reports()                                   # the workspace report follows the edited state: only the approval is wrong
    out = refused(g3)
    assert out.count("error:") == 1 and "error: duyệt: G1:" in out


@pytest.mark.parametrize("quote", ["ok", "G3 duyệt", "G13: duyệt", "G2: duyệt", ""])
def test_an_approval_without_the_exact_words_is_refused(g3, quote):
    put(g3.ws / "state.md", state_text(3).replace('"G3: duyệt"', quote))
    assert "G3" in refused(g3)


def test_an_approval_without_a_date_is_refused(g3):
    put(g3.ws / "state.md", state_text(3).replace(f'"G3: duyệt" | {DAY}', '"G3: duyệt" | '))
    assert "ngày" in refused(g3)


def test_a_missing_state_file_is_refused(g3):
    (g3.ws / "state.md").unlink()
    assert "state.md" in refused(g3)


def test_a_gate_approved_later_than_the_one_asked_is_not_enough_for_the_earlier_ones_being_unapproved(g3):
    put(g3.ws / "state.md", state_text(10).replace('| G0 | giai đoạn | đã duyệt | "G0: duyệt" |', "| G0 | giai đoạn | đang làm | |"))
    assert "G0:" in refused(g3)


# --- the reports ------------------------------------------------------------------------------------------------------------

def test_a_missing_report_is_refused_and_named(g3):
    (g3.ws / "checks" / "links-2026-10-12.md").unlink()
    out = refused(g3)
    assert "check_links.py" in out and "chưa có báo cáo" in out


def test_no_checks_folder_at_all_lists_every_script_of_the_gate(g3):
    for path in (g3.ws / "checks").iterdir():
        path.unlink()
    out = refused(g3)
    for script in CONFIG.gates[3]:
        assert f"{script}.py" in out


def test_a_report_with_errors_is_refused(g3):
    g3.report("check_numbers", ok=False)
    assert "check_numbers.py" in refused(g3) and "có lỗi" in g3.run().stdout


def test_a_draft_edited_after_the_checks_makes_them_stale(g3):
    g3.draft("01-system/a.md").write_text("# sửa sau khi kiểm\n", encoding="utf-8")
    out = refused(g3)
    assert "đã cũ" in out and "01-system/a.md" in out


def test_a_draft_edited_to_the_same_mtime_is_still_caught_because_hashes_not_mtime_decide(g3):
    path = g3.draft("01-system/a.md")
    stamp = path.stat().st_mtime_ns
    path.write_text("# sửa nhưng giữ mtime\n", encoding="utf-8")
    os.utime(path, ns=(stamp, stamp))
    assert "01-system/a.md" in refused(g3)


def test_touching_a_file_without_changing_it_does_not_make_the_checks_stale(g3):
    path = g3.draft("01-system/a.md")
    os.utime(path, (4102444800, 4102444800))             # year 2100
    assert g3.promote() == 0


def test_a_file_added_after_the_checks_makes_them_stale(g3):
    put(g3.draft("01-system/new.md"), "# mới\n")
    out = refused(g3)
    assert "mới thêm sau khi kiểm" in out and "01-system/new.md" in out


def test_a_file_deleted_after_the_checks_makes_them_stale(g3):
    g3.draft("01-system/sub/b.md").unlink()
    assert "đã xóa sau khi kiểm" in refused(g3)


def test_a_change_in_another_part_of_the_drafts_also_makes_the_checks_stale(g3):
    put(g3.draft("12-roadmap/new.md"), "# sớm\n")
    assert "12-roadmap/new.md" in refused(g3)


def test_the_workspace_report_goes_stale_when_state_changes(g3):
    put(g3.ws / "state.md", state_text(3) + "\nghi chú thêm\n")
    out = refused(g3)
    assert "check_workspace.py" in out and "state.md" in out


def test_a_report_of_another_gate_is_refused(g3):
    g3.report("check_profile", gate="G5")
    out = refused(g3)
    assert "check_profile.py" in out and "G5" in out and "--gate G3" in out


def test_a_tally_over_every_decision_counts_for_the_gate(g3):
    g3.report("tally_votes", gate="tất cả")
    assert g3.promote() == 0


def test_check_profile_without_templates_is_refused(g3):
    g3.report("check_profile", mode="no-templates")
    out = refused(g3)
    assert "check_profile.py" in out and "no-templates" in out


def test_capacity_in_assumptions_only_mode_is_enough_for_g1_but_not_for_g5(tmp_path):
    g1 = Project(tmp_path / "a", 1)
    g1.report("calc_capacity", mode="assumptions-only")
    assert g1.promote() == 0
    g5 = Project(tmp_path / "b", 5)
    g5.report("calc_capacity", mode="assumptions-only")
    assert "calc_capacity.py" in refused(g5)


def test_only_the_latest_report_counts(g3):
    g3.report("check_links", day="2026-10-13", ok=False)
    assert "check_links.py" in refused(g3)
    g3.report("check_links", day="2026-10-14", ok=True)
    assert g3.promote() == 0


def test_every_problem_is_listed_not_only_the_first(g3):
    put(g3.ws / "state.md", state_text(1))
    g3.report("check_links", ok=False)
    (g3.ws / "checks" / "numbers-2026-10-12.md").unlink()
    out = refused(g3)
    assert out.count("error:") >= 4 and "check_links.py" in out and "check_numbers.py" in out and "G2:" in out and "G3:" in out


def test_a_forged_clean_report_without_hashes_does_not_pass(g3):
    put(g3.ws / "checks" / "links-2026-10-12.md", "# check_links\n\nQuét: 2 file, 0 lỗi chặn.\n")
    assert "check_links.py" in refused(g3)


def test_a_hand_made_block_that_lists_no_files_fails_the_scope_check(g3):
    g3.report("check_links", files={})
    assert "check_links.py" in refused(g3) and "mới thêm" in g3.run().stdout


# --- the plan: new, overwritten, unchanged, orphans ---------------------------------------------------------------------------

def test_a_file_that_differs_in_architecture_is_overwritten_and_named(g3, capsys):
    put(g3.arch / "01-system/a.md", "bản cũ\n")
    assert g3.promote() == 0
    assert (g3.arch / "01-system/a.md").read_text(encoding="utf-8") == "# 01-system a\n"
    out = capsys.readouterr().out
    assert "ghi đè: 01-system/a.md" in out and "1 mới, 1 ghi đè" in out


def test_a_file_only_in_architecture_is_reported_and_kept(g3, capsys):
    put(g3.arch / "01-system/old.md", "đã xóa khỏi bản nháp\n")
    assert g3.promote() == 0
    assert (g3.arch / "01-system/old.md").is_file()
    assert "warning: 01-system/old.md" in capsys.readouterr().out


def test_files_of_other_parts_in_architecture_are_not_judged(g3, capsys):
    put(g3.arch / "02-tech-stack/x.md", "của gate khác\n")
    assert g3.promote() == 0
    assert "warning" not in capsys.readouterr().out


def test_a_part_the_profile_dropped_is_a_note_not_an_error(tmp_path, capsys):
    project = Project(tmp_path, 7)
    for path in sorted((project.ws / "drafts" / "05-frontend").rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (project.ws / "drafts" / "05-frontend").rmdir()
    project.reports()
    assert project.promote() == 0
    assert "05-frontend" in capsys.readouterr().out and not any(r.startswith("05-frontend") for r in project.copied())


def test_a_gate_with_nothing_to_copy_says_so(tmp_path, capsys):
    project = Project(tmp_path, 9)
    for part in ("11-risks", "12-roadmap"):
        for path in sorted((project.ws / "drafts" / part).rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        (project.ws / "drafts" / part).rmdir()
    project.reports()
    assert project.promote() == 0
    assert "không có file nào để chép" in capsys.readouterr().out


def test_a_symlink_in_the_drafts_is_refused_and_not_followed(g3, monkeypatch, capsys):
    """Simulated (in process), because creating a symlink needs a privilege some machines do not give."""
    put(g3.draft("01-system/link.md"), "đích của liên kết\n")
    g3.reports()
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "link.md" or real(self))
    assert g3.promote() == 1
    out = capsys.readouterr().out
    assert "liên kết tượng trưng" in out and "01-system/link.md" in out and g3.copied() == set()


def test_a_symlink_in_the_drafts_is_refused_for_real_when_the_machine_allows_it(g3):
    target = g3.root / "secret.txt"
    put(target, "bí mật")
    link = g3.draft("01-system/link.md")
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    g3.reports()
    assert "liên kết tượng trưng" in refused(g3)


# --- G10 --------------------------------------------------------------------------------------------------------------------

def test_g10_copies_every_part_and_the_readme(tmp_path):
    project = Project(tmp_path, 10)
    assert project.promote() == 0
    parts = {p for p in cp.PARTS if (project.ws / "drafts" / p).is_dir()}
    assert {r.split("/")[0] for r in project.copied()} >= parts | {"README.md"}
    assert (project.arch / "README.md").read_bytes() == project.draft("README.md").read_bytes()


def test_g10_without_a_readme_is_refused(tmp_path):
    project = Project(tmp_path, 10)
    project.draft("README.md").unlink()
    project.reports()
    assert "README.md" in refused(project)


def test_g10_updates_a_part_that_changed_after_its_own_gate_and_says_which(tmp_path, capsys):
    project = Project(tmp_path, 10)
    put(project.arch / "03-capacity/a.md", "bản đã chép ở G5\n")
    assert project.promote() == 0
    assert (project.arch / "03-capacity/a.md").read_text(encoding="utf-8") == "# 03-capacity a\n"
    assert "phần của G5" in capsys.readouterr().out


def test_g10_does_not_copy_files_that_belong_to_no_part(tmp_path):
    project = Project(tmp_path, 10)
    put(project.draft("notes.md"), "ghi chú rời\n")
    project.reports()
    assert project.promote() == 0
    assert "notes.md" not in project.copied()


def test_g10_needs_every_script_clean(tmp_path):
    project = Project(tmp_path, 10)
    project.report("check_trace", ok=False)
    assert "check_trace.py" in refused(project)


# --- dry run ----------------------------------------------------------------------------------------------------------------

def test_dry_run_copies_nothing_and_writes_no_report(g3):
    proc = g3.run("--dry-run")
    assert proc.returncode == 0 and "--dry-run" in proc.stdout and "01-system/a.md" in proc.stdout
    assert not g3.arch.exists() and not (g3.ws / "checks" / f"promote-{DAY}.md").exists()


def test_dry_run_still_refuses_when_a_condition_is_missing(g3):
    g3.draft("01-system/a.md").write_text("đổi\n", encoding="utf-8")
    proc = g3.run("--dry-run")
    assert proc.returncode == 1 and "TỪ CHỐI" in proc.stdout and not g3.arch.exists()


# --- failures and wrong arguments --------------------------------------------------------------------------------------------

def test_a_copy_that_fails_is_reported_and_exits_1(g3, capsys):
    put(g3.arch / "01-system" / "a.md" / "blocker.txt", "a.md là thư mục ở đích")      # a.md would have to be a file
    assert g3.promote() == 1
    out = capsys.readouterr().out
    assert "error:" in out and "01-system/a.md" in out
    assert "LỖI khi chép" in g3.log()


@pytest.mark.parametrize("gate", ["G11", "3", "gate3", "", "G-1"])
def test_a_bad_gate_is_exit_2(g3, gate):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--gate", gate, "--workspace", str(g3.ws)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 2


def test_a_lowercase_gate_is_accepted(g3):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--gate", "g3", "--workspace", str(g3.ws), "--date", DAY], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0


def test_the_gate_is_required(g3):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(g3.ws)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 2


def test_no_workspace_or_no_drafts_is_exit_2(tmp_path):
    assert pd.main(["--gate", "G1", "--workspace", str(tmp_path / "nope")]) == 2
    (tmp_path / "ws").mkdir()
    assert pd.main(["--gate", "G1", "--workspace", str(tmp_path / "ws")]) == 2


@pytest.mark.parametrize("where", ["inside", "same", "parent", "drafts"])
def test_architecture_inside_or_around_the_workspace_is_exit_2(g3, where):
    target = {"inside": g3.ws / "architecture", "same": g3.ws, "parent": g3.root, "drafts": g3.ws / "drafts"}[where]
    assert g3.promote("--architecture", str(target)) == 2
    assert not (g3.ws / "architecture").exists()


def test_a_broken_config_is_exit_2(g3, tmp_path):
    bad = tmp_path / "gates.yaml"
    bad.write_text("version: 1\n", encoding="utf-8")
    assert g3.promote("--config", str(bad)) == 2


def test_the_config_decides_which_scripts_a_gate_needs(g3, tmp_path):
    data = yaml.safe_load(cr.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["gates"]["G3"] = ["check_links"]
    custom = tmp_path / "gates.yaml"
    custom.write_text(yaml.safe_dump(data), encoding="utf-8")
    (g3.ws / "checks" / "numbers-2026-10-12.md").unlink()
    assert g3.promote("--config", str(custom)) == 0


# --- with the real scripts --------------------------------------------------------------------------------------------------

def test_g0_end_to_end_with_the_real_check_workspace(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "state.md", state_text(0).replace("# Trạng thái\n", "# Trạng thái\n\n- **Mức áp dụng:** M\n- **Giai đoạn hiện tại:** G0\n", 1))
    put(ws / "drafts" / "00-context" / "project-profile.md", "# Hồ sơ\n\n- **Mức:** M\n")
    env = {**os.environ}
    run = lambda *a: subprocess.run([sys.executable, *a, "--workspace", str(ws), "--date", DAY], capture_output=True, text=True, encoding="utf-8", env=env)  # noqa: E731
    first = run(str(SCRIPT), "--gate", "G0")
    assert first.returncode == 1 and "check_workspace.py" in first.stdout                 # no report yet
    assert run(str(Path(__file__).parent / "check_workspace.py"), "--gate", "G0").returncode == 0
    done = run(str(SCRIPT), "--gate", "G0")
    assert done.returncode == 0, done.stdout
    assert (tmp_path / "architecture" / "00-context" / "project-profile.md").is_file()
    put(ws / "drafts" / "00-context" / "project-profile.md", "# Hồ sơ\n\n- **Mức:** XL\n")
    assert run(str(SCRIPT), "--gate", "G0").returncode == 0           # drafts are not in the workspace report's scope: only its own files count
    put(ws / "state.md", state_text(0) + "\nthêm\n")
    assert run(str(SCRIPT), "--gate", "G0").returncode == 1           # but state.md is


# --- the block archive_release.py compares architecture/ with -------------------------------------------------------------------

def promoted_blocks(project):
    return cr.parse_promoted(project.log())


def test_a_run_that_copied_records_the_hash_of_every_file_of_the_gate(g3):
    assert g3.promote() == 0
    blocks = promoted_blocks(g3)
    assert len(blocks) == 1 and blocks[0].gate == "G3"
    assert blocks[0].files == {rel: cr.sha256_file(g3.arch / rel) for rel in g3.copied()} and set(blocks[0].files) == {"01-system/a.md", "01-system/sub/b.md"}


def test_files_that_did_not_change_are_in_the_block_too(g3):
    g3.promote()
    g3.promote()
    blocks = promoted_blocks(g3)
    assert len(blocks) == 2 and blocks[0].files == blocks[1].files and len(blocks[1].files) == 2


def test_the_block_holds_what_architecture_has_not_the_draft_when_they_could_differ(g3):
    g3.promote()
    put(g3.draft("01-system/a.md"), "# changed draft\r\n")
    g3.reports()
    g3.promote()
    last = promoted_blocks(g3)[-1].files["01-system/a.md"]
    assert last == cr.sha256_file(g3.arch / "01-system" / "a.md") == cr.sha256_file(g3.draft("01-system/a.md"))


def test_a_refused_run_and_a_dry_run_record_no_block(g3):
    put(g3.ws / "state.md", state_text(1))
    assert g3.promote() == 1
    assert promoted_blocks(g3) == []
    put(g3.ws / "state.md", state_text(3))
    assert g3.promote("--dry-run") == 0
    assert not (g3.ws / "checks" / f"promote-{DAY}.md").exists() or promoted_blocks(g3) == []


def test_a_copy_failure_records_no_block(g3, monkeypatch):
    real = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: real(self, data + b"x" if self.name == "a.md" else data))
    assert g3.promote() == 1
    assert promoted_blocks(g3) == []


def test_g10_records_every_part_and_the_readme(tmp_path):
    project = Project(tmp_path, 10)
    assert project.promote() == 0
    files = promoted_blocks(project)[-1].files
    assert "README.md" in files and set(files) == project.copied()


def test_a_hash_that_cannot_be_read_back_is_a_failure_and_records_no_block(g3, monkeypatch, capsys):
    real = cr.sha256_file

    def fail(path):
        if g3.arch in Path(path).parents:
            raise OSError("cannot read")
        return real(path)
    monkeypatch.setattr(cr, "sha256_file", fail)
    assert g3.promote() == 1
    assert "đọc lại architecture/ để ghi hash: cannot read" in capsys.readouterr().out
    assert promoted_blocks(g3) == []


def test_a_refused_run_after_a_good_one_adds_no_block_even_though_architecture_holds_the_files(g3):
    assert g3.promote() == 0
    put(g3.ws / "state.md", state_text(1))
    assert g3.promote() == 1
    assert len(promoted_blocks(g3)) == 1 and "## G3: TỪ CHỐI" in g3.log()
