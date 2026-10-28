"""Every script that judges the workspace ends its report with the hash block promote_drafts.py relies on.

For each script: run it for real, read the block of the report it wrote, and check that it names the script, the result, the gate
and mode, the right files with the right hashes, and that a report written just now is not stale by the rules of data/gates.yaml
(so the scope of gates.yaml and what the script records cannot drift apart).

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import calc_capacity as cc  # noqa: E402
import check_links as cl  # noqa: E402
import check_numbers as cn  # noqa: E402
import check_profile as cp  # noqa: E402
import check_trace as ct  # noqa: E402
import check_versions as cv  # noqa: E402
import check_workspace as cw  # noqa: E402
import checkreport as cr  # noqa: E402
import tally_votes as tv  # noqa: E402
import test_calc_capacity as tcc  # noqa: E402
import test_check_profile as tcp  # noqa: E402
import test_check_workspace as tcw  # noqa: E402
import test_check_versions as tcv  # noqa: E402
import test_tally_votes as ttv  # noqa: E402

DAY = "2026-10-12"
GATES, _ = cr.load_config()


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def block_of(ws: Path, prefix: str) -> cr.Block:
    block = cr.parse((ws / "checks" / f"{prefix}-{DAY}.md").read_text(encoding="utf-8"))
    assert block is not None, f"no block in the {prefix} report"
    return block


def fresh(ws: Path, script: str, block: cr.Block) -> None:
    """A report written just now is not stale by the scope of gates.yaml, and its hashes are those of the files."""
    assert cr.stale_reasons(ws, block, GATES.reports[script].scope) == []
    assert block.files == cr.hash_files(ws, [cr.resolve(ws, rel) for rel in block.files])


# --- check_links -----------------------------------------------------------------------------------------------------------

def links_ws(tmp_path: Path) -> Path:
    ws = tmp_path / ".agent-workspace"
    put(ws / "drafts" / "a.md", "# A\n\nxem [B](sub/b.md)\n")
    put(ws / "drafts" / "sub" / "b.md", "# B\n")
    put(ws / "drafts" / "notes.txt", "không phải md")
    return ws


def test_check_links_lists_every_md_file_with_its_hash(tmp_path):
    ws = links_ws(tmp_path)
    assert cl.main(["--workspace", str(ws), "--date", DAY]) == 0
    block = block_of(ws, "links")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_links.py", True, None, None)
    assert block.files == {"drafts/a.md": cr.sha256_file(ws / "drafts/a.md"), "drafts/sub/b.md": cr.sha256_file(ws / "drafts/sub/b.md")}
    fresh(ws, "check_links", block)


def test_check_links_marks_a_dirty_run_and_still_lists_the_files(tmp_path):
    ws = links_ws(tmp_path)
    put(ws / "drafts" / "a.md", "# A\n\nxem [B](sub/missing.md)\n")
    assert cl.main(["--workspace", str(ws), "--date", DAY]) == 1
    block = block_of(ws, "links")
    assert block.clean is False and set(block.files) == {"drafts/a.md", "drafts/sub/b.md"}


def test_check_links_report_goes_stale_when_a_draft_changes_or_appears(tmp_path):
    ws = links_ws(tmp_path)
    cl.main(["--workspace", str(ws), "--date", DAY])
    block = block_of(ws, "links")
    put(ws / "drafts" / "sub" / "b.md", "# B đổi\n")
    assert cr.stale_reasons(ws, block, GATES.reports["check_links"].scope) == ["đã đổi sau khi kiểm: drafts/sub/b.md"]
    put(ws / "drafts" / "c.md", "# C\n")
    assert len(cr.stale_reasons(ws, block, GATES.reports["check_links"].scope)) == 2


def test_check_links_hashes_ignore_line_endings(tmp_path):
    ws = links_ws(tmp_path)
    cl.main(["--workspace", str(ws), "--date", DAY])
    block = block_of(ws, "links")
    text = (ws / "drafts" / "a.md").read_text(encoding="utf-8")
    put(ws / "drafts" / "a.md", text.replace("\n", "\r\n"))
    assert cr.stale_reasons(ws, block, GATES.reports["check_links"].scope) == []


def test_a_root_outside_the_workspace_is_recorded_with_absolute_paths(tmp_path):
    ws = tmp_path / ".agent-workspace"
    ws.mkdir()
    other = tmp_path / "elsewhere"
    put(other / "a.md", "# A\n")
    cl.main(["--workspace", str(ws), "--root", str(other), "--date", DAY])
    block = block_of(ws, "links")
    assert list(block.files) == [(other / "a.md").resolve().as_posix()]


# --- check_numbers ---------------------------------------------------------------------------------------------------------

def test_check_numbers_records_the_drafts_and_the_capacity_inputs(tmp_path):
    ws = tcc.make(tmp_path)
    assert tcc.run(ws) == 0                                   # calc_capacity writes the generated documents
    assert cn.main(["--workspace", str(ws), "--date", DAY]) == 0
    block = block_of(ws, "numbers")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_numbers.py", True, None, None)
    assert "drafts/00-context/project-profile.md" in block.files
    assert any(rel.startswith("capacity/") and rel.endswith(".yaml") for rel in block.files)
    assert "capacity/db-constants/postgresql-16.yaml" in block.files
    fresh(ws, "check_numbers", block)


def test_check_numbers_goes_stale_when_a_capacity_input_changes(tmp_path):
    ws = tcc.make(tmp_path)
    tcc.run(ws)
    cn.main(["--workspace", str(ws), "--date", DAY])
    block = block_of(ws, "numbers")
    path = ws / "capacity" / "db-constants" / "postgresql-16.yaml"
    put(path, path.read_text(encoding="utf-8") + "\n# đổi\n")
    assert cr.stale_reasons(ws, block, GATES.reports["check_numbers"].scope) == ["đã đổi sau khi kiểm: capacity/db-constants/postgresql-16.yaml"]


def test_check_numbers_marks_a_dirty_run(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "drafts" / "a.md", "# A\n\nHệ thống chịu 5000 request/s.\n")
    assert cn.main(["--workspace", str(ws), "--date", DAY]) == 1
    assert block_of(ws, "numbers").clean is False


# --- check_versions --------------------------------------------------------------------------------------------------------

def test_check_versions_records_the_two_files_it_reads(tmp_path):
    ws = tmp_path / ".agent-workspace"
    tcv.tree(ws / "drafts")
    put(ws / "drafts" / "01-system" / "other.md", "# không liên quan\n")
    assert cv.main(["--workspace", str(ws), "--date", DAY]) == 0
    block = block_of(ws, "versions")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_versions.py", True, None, None)
    assert set(block.files) == {"drafts/02-tech-stack/README.md", "drafts/02-tech-stack/versions-features.md"}
    fresh(ws, "check_versions", block)


def test_check_versions_with_a_missing_file_is_dirty_and_lists_only_what_exists(tmp_path):
    ws = tmp_path / ".agent-workspace"
    tcv.tree(ws / "drafts", versions=None)
    assert cv.main(["--workspace", str(ws), "--date", DAY]) == 1
    block = block_of(ws, "versions")
    assert block.clean is False and set(block.files) == {"drafts/02-tech-stack/README.md"}


# --- check_profile ---------------------------------------------------------------------------------------------------------

def profile_ws(tmp_path: Path) -> Path:
    ws = tmp_path / ".agent-workspace"
    tcp.base(ws)
    return ws


def test_check_profile_records_the_gate_and_the_template_mode(tmp_path):
    ws = profile_ws(tmp_path)
    templates = tmp_path / "templates"
    put(templates / "00-context" / "glossary.md", "# Thuật ngữ\n")
    assert cp.main(["--workspace", str(ws), "--gate", "G1", "--templates", str(templates), "--date", DAY]) == 0
    block = block_of(ws, "profile")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_profile.py", True, "G1", "templates")
    assert "drafts/00-context/project-profile.md" in block.files
    fresh(ws, "check_profile", block)


def test_check_profile_with_errors_is_dirty(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "drafts" / "a.md", "# không có hồ sơ dự án\n")
    assert cp.main(["--workspace", str(ws), "--gate", "G1", "--no-templates", "--date", DAY]) == 1
    block = block_of(ws, "profile")
    assert block.clean is False and block.gate == "G1" and set(block.files) == {"drafts/a.md"}


def test_check_profile_without_templates_says_so_and_gates_yaml_refuses_it(tmp_path):
    ws = profile_ws(tmp_path)
    assert cp.main(["--workspace", str(ws), "--gate", "G1", "--no-templates", "--date", DAY]) == 0
    block = block_of(ws, "profile")
    assert block.mode == "no-templates" and block.clean is True
    assert block.mode not in GATES.reports["check_profile"].modes_for(1)


def test_check_profile_gate_is_the_one_asked_for(tmp_path):
    ws = profile_ws(tmp_path)
    cp.main(["--workspace", str(ws), "--gate", "g0", "--no-templates", "--date", DAY])
    assert block_of(ws, "profile").gate == "G0"


# --- check_trace -----------------------------------------------------------------------------------------------------------

def test_check_trace_records_the_drafts_and_the_outside_sources(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "drafts" / "a.md", "# A\n")
    put(ws / "decisions" / "decision-log.md", "# log\n")
    put(ws / "questions.md", "# q\n")
    put(ws / "inputs" / "ui-design" / "screens.txt", "SCR-001\n")
    put(ws / "inputs" / "ui-design" / "deep" / "more.txt", "SCR-002\n")
    put(ws / "inputs" / "ba" / "ignored.md", "không đọc\n")
    assert ct.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY]) == 0
    block = block_of(ws, "trace")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_trace.py", True, "G3", None)
    assert set(block.files) == {"drafts/a.md", "decisions/decision-log.md", "questions.md", "inputs/ui-design/screens.txt", "inputs/ui-design/deep/more.txt"}
    fresh(ws, "check_trace", block)


def test_check_trace_dirty_run(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "drafts" / "a.md", "# A\n\nxem FR-001\n")
    assert ct.main(["--workspace", str(ws), "--gate", "G6", "--date", DAY]) == 1
    assert block_of(ws, "trace").clean is False


# --- check_workspace -------------------------------------------------------------------------------------------------------

def test_check_workspace_records_the_files_it_judges(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "state.md", "# Trạng thái\n\n## Hiện tại\n\n- **Mức áp dụng:** M\n- **Giai đoạn hiện tại:** G2\n")
    put(ws / "plan" / "tasks" / "T-001-x.md", "# T-001\n\n- **Gate:** G1\n- **Trạng thái:** đóng\n")
    put(ws / "models.md", "# models\n")
    put(ws / "decisions" / "decision-log.md", "# log\n")
    put(ws / "drafts" / "11-risks" / "risk-register.md", tcw.register_text([]))
    put(ws / "drafts" / "01-system" / "x.md", "# không thuộc phạm vi\n")
    assert cw.main(["--workspace", str(ws), "--date", DAY]) == 0
    block = block_of(ws, "workspace")
    assert (block.script, block.clean, block.gate, block.mode) == ("check_workspace.py", True, "G2", None)
    assert set(block.files) == {"state.md", "plan/tasks/T-001-x.md", "models.md", "decisions/decision-log.md", "drafts/11-risks/risk-register.md"}
    fresh(ws, "check_workspace", block)


def test_check_workspace_report_goes_stale_when_a_task_is_reopened(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "state.md", "# Trạng thái\n\n- **Mức áp dụng:** M\n- **Giai đoạn hiện tại:** G2\n")
    task = put(ws / "plan" / "tasks" / "T-001-x.md", "# T-001\n\n- **Gate:** G1\n- **Trạng thái:** đóng\n")
    cw.main(["--workspace", str(ws), "--date", DAY])
    block = block_of(ws, "workspace")
    put(task, task.read_text(encoding="utf-8").replace("đóng", "mở"))
    assert cr.stale_reasons(ws, block, GATES.reports["check_workspace"].scope) == ["đã đổi sau khi kiểm: plan/tasks/T-001-x.md"]


def test_check_workspace_dirty_run_and_gate_flag(tmp_path):
    ws = tmp_path / ".agent-workspace"
    put(ws / "state.md", "# Trạng thái\n\n- **Mức áp dụng:** M\n- **Giai đoạn hiện tại:** G2\n")
    put(ws / "plan" / "tasks" / "T-001-x.md", "# T-001\n\n- **Gate:** G1\n- **Trạng thái:** mở\n")
    assert cw.main(["--workspace", str(ws), "--gate", "G4", "--date", DAY]) == 1
    block = block_of(ws, "workspace")
    assert block.clean is False and block.gate == "G4"


# --- tally_votes -----------------------------------------------------------------------------------------------------------

def test_tally_votes_records_the_files_of_every_decision_it_counted(tmp_path):
    ws = ttv.workspace(tmp_path)
    ttv.cast(ws, ttv.unanimous())
    other = ttv.workspace(tmp_path / "x")                    # a second decision of another gate, to be left out
    assert tv.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY]) == 0
    block = block_of(ws, "tally")
    assert (block.script, block.clean, block.gate, block.mode) == ("tally_votes.py", True, "G3", None)
    names = set(block.files)
    assert any(n.endswith("/brief.md") for n in names) and any(n.endswith("/tally.md") for n in names) and any(n.endswith("/decision.md") for n in names)
    assert sum(1 for n in names if "/votes/" in n) == 3
    assert all(n.startswith("decisions/" + ttv.DEC + "/") for n in names)
    fresh(ws, "tally_votes", block)
    assert other.is_dir()


def test_tally_votes_without_a_gate_says_all(tmp_path):
    ws = ttv.workspace(tmp_path)
    ttv.cast(ws, ttv.unanimous())
    tv.main(["--workspace", str(ws), "--date", DAY])
    assert block_of(ws, "tally").gate == cr.ALL_GATES


def test_tally_votes_hashes_are_taken_after_it_wrote_its_files(tmp_path):
    ws = ttv.workspace(tmp_path)
    ttv.cast(ws, ttv.unanimous())
    tv.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY])
    block = block_of(ws, "tally")
    rel = f"decisions/{ttv.DEC}/tally.md"
    assert rel in block.files and block.files[rel] == cr.sha256_file(ws / rel)


def test_tally_votes_goes_stale_when_a_vote_changes(tmp_path):
    ws = ttv.workspace(tmp_path)
    ttv.cast(ws, ttv.unanimous())
    tv.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY])
    block = block_of(ws, "tally")
    vote = sorted((ws / "decisions" / ttv.DEC / "votes").glob("*.md"))[0]
    put(vote, vote.read_text(encoding="utf-8") + "\nsửa sau\n")
    assert len(cr.stale_reasons(ws, block, GATES.reports["tally_votes"].scope)) == 1


def test_tally_votes_with_a_bad_vote_is_dirty(tmp_path):
    ws = ttv.workspace(tmp_path)
    assert tv.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY]) in (0, 1)
    ttv.cast(ws, [ttv.default_vote("fit", choice="Z")])
    assert tv.main(["--workspace", str(ws), "--gate", "G3", "--date", DAY]) == 1
    assert block_of(ws, "tally").clean is False


def test_tally_votes_with_nothing_to_count_is_clean_with_no_files(tmp_path):
    ws = ttv.workspace(tmp_path)
    assert tv.main(["--workspace", str(ws), "--gate", "G9", "--date", DAY]) == 0
    block = block_of(ws, "tally")
    assert block.clean and block.gate == "G9" and block.files == {}


# --- calc_capacity ---------------------------------------------------------------------------------------------------------

def test_calc_capacity_write_mode_records_inputs_and_what_it_wrote(tmp_path):
    ws = tcc.make(tmp_path)
    assert tcc.run(ws) == 0
    block = block_of(ws, "capacity")
    assert (block.script, block.clean, block.gate, block.mode) == ("calc_capacity.py", True, None, "write")
    assert "capacity/db-constants/postgresql-16.yaml" in block.files
    assert "drafts/00-context/assumptions.md" in block.files
    assert "drafts/07-data/databases/order-db/tables.md" in block.files          # a file with a calc block, filled in
    for rel, digest in block.files.items():
        assert digest == cr.sha256_file(ws / rel)                                  # the hash is of the file AFTER the write
    fresh(ws, "calc_capacity", block)


def test_calc_capacity_check_mode_after_a_write_is_clean_and_says_check(tmp_path):
    ws = tcc.make(tmp_path)
    tcc.run(ws)
    assert tcc.run(ws, "--check") == 0
    block = block_of(ws, "capacity")
    assert block.mode == "check" and block.clean


def test_calc_capacity_check_mode_on_a_hand_edited_file_is_dirty(tmp_path):
    ws = tcc.make(tmp_path)
    tcc.run(ws)
    path = ws / "drafts" / "00-context" / "assumptions.md"
    put(path, path.read_text(encoding="utf-8") + "\nsửa tay\n")
    assert tcc.run(ws, "--check") == 1
    assert block_of(ws, "capacity").clean is False


def test_calc_capacity_assumptions_only_mode(tmp_path):
    ws = tcc.make(tmp_path)
    assert tcc.run(ws, "--assumptions-only") == 0
    block = block_of(ws, "capacity")
    assert block.mode == "assumptions-only" and block.clean
    assert "drafts/00-context/assumptions.md" in block.files and "drafts/03-capacity/storage.md" not in block.files
    fresh(ws, "calc_capacity", block)


def test_calc_capacity_with_a_missing_input_is_dirty(tmp_path):
    ws = tcc.make(tmp_path)
    (ws / "capacity" / "assumptions.yaml").unlink()
    assert tcc.run(ws) == 1
    assert block_of(ws, "capacity").clean is False


def test_calc_capacity_goes_stale_when_an_input_changes(tmp_path):
    ws = tcc.make(tmp_path)
    tcc.run(ws)
    block = block_of(ws, "capacity")
    path = ws / "capacity" / "assumptions.yaml"
    put(path, path.read_text(encoding="utf-8") + "\n# đổi\n")
    assert cr.stale_reasons(ws, block, GATES.reports["calc_capacity"].scope) == ["đã đổi sau khi kiểm: capacity/assumptions.yaml"]


# --- the data file and the scripts agree ------------------------------------------------------------------------------------

@pytest.mark.parametrize("script", sorted(GATES.reports))
def test_every_report_script_of_gates_yaml_is_a_real_script_that_imports_checkreport(script):
    path = Path(__file__).parent / f"{script}.py"
    assert path.is_file()
    assert "import checkreport as cr" in path.read_text(encoding="utf-8")
    assert f'cr.render("{script}.py"' in path.read_text(encoding="utf-8")


def test_the_prefix_of_each_script_is_the_name_it_writes_its_report_under():
    for script, spec in GATES.reports.items():
        source = (Path(__file__).parent / f"{script}.py").read_text(encoding="utf-8")
        assert f"{spec.prefix}-{{" in source, f"{script}.py does not write checks/{spec.prefix}-<date>.md"
