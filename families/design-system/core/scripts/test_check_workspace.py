"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import check_workspace as cw  # noqa: E402
import detect_models as dm  # noqa: E402
import run_spike as rs  # noqa: E402
from test_run_spike import spec_text  # noqa: E402
from test_tally_votes import brief_text  # noqa: E402

SCRIPT = Path(__file__).parent / "check_workspace.py"
CORE = Path(__file__).parent.parent
TODAY = "2026-10-12"
CFG, _ = cw.load_config(cw.DEFAULT_CONFIG)
SPIKE_CFG, _ = rs.load_config(rs.DEFAULT_CONFIG)


# --- builders --------------------------------------------------------------------------------------------------------------

def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def state_text(gate="G4", level="XL") -> str:
    return f"# Trạng thái\n\n## Hiện tại\n\n- **Dự án:** thử\n- **Mức áp dụng:** {level}\n- **Giai đoạn hiện tại:** {gate}\n- **Cập nhật lần cuối:** {TODAY}\n"


def task_text(gate="G1", status="đóng") -> str:
    return f"# T-001: thử\n\n- **Gate:** {gate}\n- **Giao cho:** Designer\n- **Trạng thái:** {status}\n- **Phụ thuộc:** không có\n\n## Mô tả\n\nx\n"


def log_text(rows: list[tuple[str, str, str, str, str]]) -> str:
    head = "# Nhật ký quyết định\n\n| ID | Câu hỏi | Gate | Hội đồng | Trạng thái | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- | --- | --- | --- |\n"
    return head + "".join(f"| {i} | câu hỏi | {g} | 3 | {s} | {q} | {d} |\n" for i, g, s, q, d in rows)


def decision_text(status="đã quyết", quote='"D-001: chọn A"', option="A", date=TODAY) -> str:
    return (f"# Quyết định D-001: x\n\n<!-- BEGIN:council (x) -->\nđề xuất A\n<!-- END:council -->\n\n<!-- BEGIN:user (x) -->\n\n## Quyết định của người dùng\n\n"
            f"- **Trạng thái:** {status}\n- **Người dùng nói (nguyên văn):** {quote}\n- **Ngày:** {date}\n- **Phương án được chọn:** {option}\n- **Rủi ro đã khai vào sổ:** chưa\n\n<!-- END:user -->\n")


def register_text(rows: list[tuple[str, str, str]]) -> str:
    head = "# Sổ rủi ro\n\n| ID | Mô tả | Nhóm | Khả năng × Tác động | Thành phần liên quan | Dấu hiệu sớm | Giảm thiểu | Phương án dự phòng | Trạng thái |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    return head + "".join(f"| {i} | mô tả | công nghệ | {s} | SVC-a | CPU > 70% | làm x | làm y | {st} |\n" for i, s, st in rows)


def acceptance_text(rows: list[tuple[str, str, str, str]]) -> str:
    head = "# Rủi ro đã được người dùng chấp nhận\n\n| ID | Điểm | Người dùng nói (nguyên văn) | Ngày |\n| --- | --- | --- | --- |\n"
    return head + "".join(f"| {i} | {p} | {q} | {d} |\n" for i, p, q, d in rows)


def models_text(rows: list[dm.ModelRow], assigned: list[tuple[str, str, str]]) -> str:
    text = dm.merge_into("", dm.render_block(rows, [], None, TODAY, []))
    return text.rstrip("\n") + "\n" + "".join(f"| {t} | {a} | {m} | {TODAY} |\n" for t, a, m in assigned) + "\n"


def model_row(name, status=dm.STATUS_OK, kind="subagent") -> dm.ModelRow:
    return dm.ModelRow(name=name, kind=kind, how="x", web="có", status=status)


class Workspace:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path / ".agent-workspace"
        self.root.mkdir()
        put(self.root / "state.md", state_text())

    def put(self, rel: str, text: str) -> Path:
        return put(self.root / rel, text)

    def check(self, gate=4, level="XL"):
        return cw.run(self.root, CFG, gate, level)

    def codes(self, gate=4, level="XL", blocking=True) -> list[str]:
        result = self.check(gate, level)
        return sorted(f.code for f in (result.errors if blocking else result.warnings))

    def messages(self, gate=4, level="XL") -> list[str]:
        return [f.message for f in self.check(gate, level).errors]


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path)


# --- tasks -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["mở", "đang làm", "chờ soát"])
def test_a_task_that_is_not_closed_blocks_its_own_gate_and_later_ones(ws, status):
    ws.put("plan/tasks/T-001-thu.md", task_text("G4", status))
    assert ws.codes(4) == ["task-open"] and ws.codes(5) == ["task-open"]
    assert ws.codes(3) == []                        # a task of a later gate is not due yet


def test_closed_tasks_are_fine_at_any_gate(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "đóng"))
    ws.put("plan/tasks/T-002-thu.md", task_text("G4", "Đóng"))
    assert ws.codes(4) == [] and ws.codes(10) == []


def test_an_earlier_gates_open_task_still_blocks(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "đang làm"))
    assert ws.codes(7) == ["task-open"]


@pytest.mark.parametrize("gate, status", [("", "đóng"), ("<G0–G10>", "đóng"), ("G11", "đóng"), ("G4", "xong"), ("G4", ""), ("G4", "<mở | đang làm>")])
def test_a_malformed_task_is_an_error_not_silently_ignored(ws, gate, status):
    ws.put("plan/tasks/T-001-thu.md", task_text(gate, status))
    assert ws.codes(4) == ["task-malformed"]


def test_the_template_task_is_malformed(ws):
    ws.put("plan/tasks/T-000-mau.md", (CORE / "templates" / "workspace" / "task.md").read_text(encoding="utf-8"))
    assert ws.codes(4) == ["task-malformed"]


def test_files_that_are_not_tasks_are_ignored(ws):
    ws.put("plan/tasks/notes.md", "not a task")
    ws.put("plan/plan.md", "plan")
    assert ws.codes(4) == []


# --- decisions -------------------------------------------------------------------------------------------------------------

def decided(ws, status="đã quyết", quote='"D-001: chọn A"', date=TODAY, gate="G3", decision=None, brief=True):
    ws.put("decisions/decision-log.md", log_text([("D-001", gate, status, quote, date)]))
    if decision is not None:
        ws.put("decisions/D-001-arch/decision.md", decision)
    if brief:
        ws.put("decisions/D-001-arch/brief.md", brief_text())


def test_a_decided_decision_with_the_users_words_is_fine(ws):
    decided(ws, decision=decision_text())
    assert ws.codes(4) == []


@pytest.mark.parametrize("status", ["brief", "chờ phiếu", "chờ người dùng", "làm lại", "Làm lại"])
def test_a_decision_that_the_user_has_not_made_blocks(ws, status):
    decided(ws, status=status, quote="", date="", decision=decision_text())
    assert ws.codes(4) == ["decision-open"]


def test_redo_is_still_open_and_says_why(ws):
    decided(ws, status="làm lại", quote='"D-001: làm lại"', decision=decision_text(status="làm lại"))
    assert any("brief mới chưa có quyết định" in m for m in ws.messages(4))
    # even with a choice written next to the status, "làm lại" is not "đã quyết"
    decided(ws, status="làm lại", quote='"D-001: chọn A"', decision=decision_text(status="làm lại"))
    assert ws.codes(4) == ["decision-open"] and any("brief mới chưa có quyết định" in m for m in ws.messages(4))


def test_a_decision_of_a_later_gate_is_not_due(ws):
    decided(ws, status="brief", quote="", date="", gate="G7", decision=None)
    assert ws.codes(4) == [] and ws.codes(7) == ["decision-open"]


@pytest.mark.parametrize("quote", ["ok", "được", "", '"D-001: duyệt"', '"D-002: chọn A"', '"D-0010: chọn A"', '"D-001 chọn A"', "chọn A", '"XD-001: chọn A"', '"D-001: chọn"'])
def test_the_users_words_must_name_this_id_and_a_choice(ws, quote):
    decided(ws, quote=quote, decision=decision_text())
    assert ws.codes(4) == ["decision-open"]


@pytest.mark.parametrize("quote", ['"D-001: chọn A"', "D-001: chọn A", "Ừ, D-001: chọn A nhé", '"d-001: chọn A"'.replace("d-001", "D-001"), "D-001:chọn A"])
def test_the_words_may_sit_in_a_longer_message(ws, quote):
    decided(ws, quote=quote, decision=decision_text(quote=quote))
    assert ws.codes(4) == []


@pytest.mark.parametrize("date", ["", "hôm nay", "2026-13-01"])
def test_a_decision_needs_a_real_date(ws, date):
    decided(ws, date=date, decision=decision_text())
    assert ws.codes(4) == ["decision-open"]


def test_the_decision_file_must_agree_with_the_log(ws):
    decided(ws, decision=decision_text(status="chờ người dùng"))
    assert ws.codes(4) == ["decision-mismatch"]
    decided(ws, decision=decision_text(option="B"))
    assert ws.codes(4) == ["decision-choice-mismatch"]
    decided(ws, decision=decision_text(quote='"D-001: chọn A"', option="—"))
    assert ws.codes(4) == ["decision-choice-mismatch"]
    decided(ws, decision="# không có khối của người dùng\n")
    assert ws.codes(4) == ["decision-mismatch"]
    decided(ws, decision=None)
    (ws.root / "decisions/D-001-arch/decision.md").unlink(missing_ok=True)
    assert ws.codes(4) == ["decision-mismatch"]


def test_the_chosen_option_must_exist_in_the_brief(ws):
    decided(ws, quote='"D-001: chọn Z"', decision=decision_text(quote='"D-001: chọn Z"', option="Z"))
    assert ws.codes(4) == ["decision-choice-unknown"]


def test_a_decided_log_row_needs_its_folder(ws):
    decided(ws, decision=None, brief=False)
    assert ws.codes(4) == ["decision-mismatch"]


def test_a_decision_folder_that_is_not_in_the_log_blocks(ws):
    ws.put("decisions/decision-log.md", log_text([]))
    ws.put("decisions/D-001-arch/brief.md", brief_text())
    assert ws.codes(4) == ["decision-not-logged"] and ws.codes(3) == ["decision-not-logged"]
    assert ws.codes(2) == []   # the brief says G3: not due before it


def test_a_decision_folder_with_an_unreadable_brief_is_not_logged_either(ws):
    ws.put("decisions/decision-log.md", log_text([]))
    ws.put("decisions/D-001-arch/brief.md", "no frontmatter")
    assert ws.codes(2) == ["decision-not-logged"]


def test_no_log_but_decision_folders_is_an_error(ws):
    ws.put("decisions/D-001-arch/brief.md", brief_text())
    assert "decision-log-missing" in ws.codes(4)


def test_the_template_row_of_the_log_is_not_a_decision(ws):
    ws.put("decisions/decision-log.md", (CORE / "templates" / "workspace" / "decision-log.md").read_text(encoding="utf-8"))
    assert ws.codes(10) == []


def test_a_log_without_the_needed_columns_is_an_error(ws):
    ws.put("decisions/decision-log.md", "| ID | Câu hỏi |\n| --- | --- |\n| D-001 | x |\n")
    assert ws.codes(4) == ["decision-log-malformed"]


def test_a_log_row_with_a_bad_gate_is_an_error(ws):
    ws.put("decisions/decision-log.md", log_text([("D-001", "G99", "brief", "", "")]))
    assert ws.codes(4) == ["decision-log-malformed"]


# --- risks -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("score", ["3 × 5 = 15", "5×5", "4 × 4 = 16", "3 x 5", "25", "15"])
@pytest.mark.parametrize("status", ["Đang theo dõi", "đang giảm thiểu"])
def test_a_big_risk_not_accepted_or_closed_is_unresolved(ws, score, status):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", score, status)]))
    assert ws.codes(8, "M", blocking=False) == ["risk-unresolved"] and ws.codes(8, "M") == []         # a warning before G9
    assert ws.codes(9, "M") == ["risk-unresolved"] and ws.codes(10, "M") == ["risk-unresolved"]       # an error from G9


@pytest.mark.parametrize("score", ["2 × 5 = 10", "3 × 4 = 12", "5 × 2", "1", "14"])
def test_a_small_risk_is_never_unresolved(ws, score):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", score, "đang theo dõi")]))
    assert ws.codes(10, "M") == [] and ws.codes(10, "M", blocking=False) == []


def test_a_closed_risk_of_any_size_is_handled(ws):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "5 × 5", "đã đóng")]))
    assert ws.codes(10) == []


def test_an_accepted_risk_needs_the_users_row_both_ways(ws):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "4 × 4 = 16", "đã chấp nhận")]))
    assert ws.codes(10) == ["acceptance-missing"]
    ws.put("risks/acceptance.md", acceptance_text([("R-01", "16", '"R-01: chấp nhận"', TODAY)]))
    assert ws.codes(10) == []


def test_an_acceptance_row_without_a_risk_in_the_register(ws):
    ws.put("risks/acceptance.md", acceptance_text([("R-09", "16", '"R-09: chấp nhận"', TODAY)]))
    assert ws.codes(10) == ["acceptance-orphan"]               # no register at all
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "4 × 4", "đã chấp nhận")]))
    assert sorted(ws.codes(10)) == ["acceptance-missing", "acceptance-orphan"]


def test_an_acceptance_row_must_match_the_registers_score_and_status(ws):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "4 × 4 = 16", "đã chấp nhận"), ("R-02", "5 × 5", "đang giảm thiểu"), ("R-03", "2 × 2", "đã chấp nhận")]))
    ws.put("risks/acceptance.md", acceptance_text([
        ("R-01", "20", '"R-01: chấp nhận"', TODAY), ("R-02", "25", '"R-02: chấp nhận"', TODAY), ("R-03", "4", '"R-03: chấp nhận"', TODAY)]))
    assert ws.codes(8) == ["acceptance-orphan", "acceptance-score", "acceptance-status"]


@pytest.mark.parametrize("quote, code", [("ok", "acceptance-quote"), ('"R-02: chấp nhận"', "acceptance-quote"), ('"R-01: duyệt"', "acceptance-quote"), ("", "acceptance-quote"), ('"R-010: chấp nhận"', "acceptance-quote")])
def test_the_acceptance_words_must_be_the_users_for_this_id(ws, quote, code):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "4 × 4", "đã chấp nhận")]))
    ws.put("risks/acceptance.md", acceptance_text([("R-01", "16", quote, TODAY)]))
    assert ws.codes(10) == [code]


def test_the_acceptance_date_must_be_real(ws):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "4 × 4", "đã chấp nhận")]))
    ws.put("risks/acceptance.md", acceptance_text([("R-01", "16", '"R-01: chấp nhận"', "")]))
    assert ws.codes(10) == ["acceptance-date"]


@pytest.mark.parametrize("score", ["6 × 2", "0 × 3", "3 × 3 = 10", "nhiều", ""])
def test_an_unreadable_score_is_an_error(ws, score):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", score, "đang theo dõi")]))
    assert ws.codes(3) == ["risk-score"]


def test_an_unknown_risk_status_is_an_error(ws):
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-01", "2 × 2", "xong")]))
    assert ws.codes(3) == ["risk-status"]


def test_the_template_rows_and_placeholder_ids_are_skipped(ws):
    ws.put("risks/acceptance.md", (CORE / "templates" / "workspace" / "acceptance.md").read_text(encoding="utf-8"))
    ws.put("drafts/11-risks/risk-register.md", register_text([("R-xx", "5 × 5", "đang theo dõi")]))
    assert ws.codes(10) == []


def test_a_register_without_the_columns_is_an_error(ws):
    ws.put("drafts/11-risks/risk-register.md", "| ID | Mô tả |\n| --- | --- |\n| R-01 | x |\n")
    assert ws.codes(3) == ["risk-register-malformed"]


def test_an_acceptance_table_without_the_columns_is_an_error(ws):
    ws.put("risks/acceptance.md", "| ID | x |\n| --- | --- |\n| R-01 | y |\n")
    assert ws.codes(3) == ["acceptance-malformed"]


# --- models ----------------------------------------------------------------------------------------------------------------

def test_a_model_that_was_not_probed_or_failed_cannot_be_assigned(ws):
    rows = [model_row("sonnet"), model_row("opus", dm.STATUS_STATIC), model_row("haiku", dm.STATUS_BAD + ": mã 1, hết hạn mức")]
    ws.put("models.md", models_text(rows, [("T-001", "designer", "sonnet"), ("T-002", "planner", "opus"), ("T-003", "reviewer", "haiku")]))
    result = ws.check()
    assert sorted(f.code for f in result.errors) == ["model-unusable", "model-untested"][::-1] or sorted(f.code for f in result.errors) == ["model-untested", "model-unusable"]
    by_code = {f.code: f.message for f in result.errors}
    assert "opus" in by_code["model-untested"] and "T-002" in by_code["model-untested"] and "haiku" in by_code["model-unusable"]


def broken_models(ws, assigned):
    rows = [model_row("sonnet"), model_row("haiku", dm.STATUS_BAD + ": mã 1"), model_row("opus", dm.STATUS_STATIC)]
    ws.put("models.md", models_text(rows, assigned))


def test_a_broken_model_on_a_closed_task_is_history_not_an_error(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "đóng"))
    broken_models(ws, [("T-001", "designer", "haiku"), ("T-001", "designer", "opus")])
    assert ws.codes() == []
    assert any("2 dòng của task đã đóng" in note for note in ws.check().notes)


def test_a_broken_model_on_an_open_task_is_an_error(ws):
    for status in ("mở", "đang làm", "chờ soát"):
        ws.put("plan/tasks/T-001-thu.md", task_text("G9", status))
        broken_models(ws, [("T-001", "designer", "haiku")])
        assert "model-unusable" in ws.codes(2)              # whatever the task's gate: the task is the one being worked on


def test_a_replacement_row_for_an_open_task_fixes_nothing_retroactively(ws):
    """Rows are never edited: the old broken row of the open task stays an error; closing the task turns it into history."""
    ws.put("plan/tasks/T-001-thu.md", task_text("G9", "đang làm"))
    broken_models(ws, [("T-001", "designer", "haiku"), ("T-001", "designer", "sonnet")])
    assert ws.codes() == ["model-unusable"]
    ws.put("plan/tasks/T-001-thu.md", task_text("G9", "đóng"))
    assert ws.codes() == []


def test_only_the_closed_tasks_rows_are_skipped(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "đóng"))
    ws.put("plan/tasks/T-002-thu.md", task_text("G9", "đang làm"))
    broken_models(ws, [("T-001", "designer", "haiku"), ("T-002", "designer", "opus"), ("T-010", "designer", "haiku")])
    result = ws.check()
    assert sorted(f.code for f in result.errors) == ["model-untested", "model-unusable"][::-1] or sorted(f.code for f in result.errors) == ["model-untested", "model-unusable"]
    assert {f.message.split()[1] for f in result.errors} == {"T-002", "T-010"}      # T-010 has no file: not closed, so checked


def test_a_task_id_is_matched_whole_not_as_a_prefix(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "đóng"))
    broken_models(ws, [("T-0010", "designer", "haiku")])
    assert ws.codes() == ["model-unusable"]


def test_a_usable_model_is_fine_and_so_are_notes_after_it(ws):
    ws.put("models.md", models_text([model_row("sonnet")], [("T-001", "designer", "sonnet"), ("T-002", "planner", "sonnet (claude-sonnet-5-5)"), ("T-003", "x", "`sonnet`")]))
    assert ws.codes() == []


def test_a_model_missing_from_the_catalogue_is_only_a_warning(ws):
    ws.put("models.md", models_text([model_row("sonnet")], [("T-001", "designer", "mystery")]))
    assert ws.codes(4, "M") == [] and ws.codes(4, "M", blocking=False) == ["model-unknown"]


def test_an_empty_assignment_table_and_a_missing_models_file_are_fine(ws):
    ws.put("models.md", models_text([model_row("sonnet")], []))
    assert ws.codes() == []
    (ws.root / "models.md").unlink()
    assert ws.codes() == []


def test_the_empty_template_row_of_the_assignment_table_is_skipped(ws):
    ws.put("models.md", dm.merge_into("", dm.render_block([model_row("sonnet")], [], None, TODAY, [])))
    assert ws.codes() == []


def test_cli_models_are_checked_by_their_full_name(ws):
    ws.put("models.md", models_text([model_row("agy:gemini-x", dm.STATUS_STATIC, "cli")], [("T-001", "council-fit", "agy:gemini-x")]))
    assert ws.codes() == ["model-untested"]


# --- spikes (level XL, from G4) ----------------------------------------------------------------------------------------------

def spike(ws, layer="data", name="S-01-x", spike_id="S-01", result="đạt", fresh=True, **overrides) -> Path:
    path = ws.put(f"stack/layers/{layer}/spikes/{name}.md", spec_text(layer=layer, spike=spike_id, **overrides))
    if result:
        front = {"spike": spike_id, "layer": layer, "result": result, "spec_sha256": rs.spec_hash(path.read_text(encoding="utf-8")) if fresh else "0" * 64}
        ws.put(f"stack/layers/{layer}/spikes/{name}.result.md", "---\n" + yaml.safe_dump(front, allow_unicode=True) + "---\n\n# Kết quả\n")
    return path


def all_required_layers(ws, **kwargs):
    for index, layer in enumerate(SPIKE_CFG.xl_required_layers, start=1):
        spike(ws, layer, f"S-0{index}-x", f"S-0{index}", **kwargs)


def test_xl_at_g4_needs_a_passing_spike_for_every_required_layer(ws):
    all_required_layers(ws)
    assert ws.codes(4) == []
    assert any("4/4 lớp bắt buộc" in n for n in ws.check().notes)


@pytest.mark.parametrize("layer", ["data", "messaging", "backend", "infrastructure"])
def test_each_required_layer_with_a_folder_needs_its_own_spike(ws, layer):
    all_required_layers(ws)
    for path in (ws.root / "stack" / "layers" / layer / "spikes").iterdir():
        path.unlink()
    result = ws.check(4)
    assert [f.code for f in result.errors] == ["spike-missing"] and layer in result.errors[0].message and "chưa có đề bài" in result.errors[0].message


@pytest.mark.parametrize("state, needle", [("không đạt", "không đạt"), ("lỗi", "lỗi"), (None, "chưa chạy")])
def test_a_spike_that_did_not_pass_or_never_ran_does_not_count(ws, state, needle):
    spike(ws, "data", result=state)
    result = ws.check(4)
    assert [f.code for f in result.errors] == ["spike-missing"] and needle in result.errors[0].message


def test_a_result_older_than_the_spec_does_not_count(ws):
    path = spike(ws, "data")
    assert ws.codes(4) == []
    put(path, spec_text(layer="data", spike="S-01", commands=["echo changed"]))     # the spec changed after the run
    result = ws.check(4)
    assert [f.code for f in result.errors] == ["spike-missing"] and "cũ hơn đề bài" in result.errors[0].message


def test_a_forged_pass_with_the_wrong_hash_does_not_count(ws):
    spike(ws, "data", fresh=False)
    assert ws.codes(4) == ["spike-missing"]


def test_one_passing_spike_is_enough_for_a_layer(ws):
    spike(ws, "data", "S-01-a", "S-01", result="không đạt")
    spike(ws, "data", "S-02-b", "S-02", result="đạt")
    assert ws.codes(4) == []


def test_the_spike_check_waits_for_g4_and_for_level_xl(ws):
    spike(ws, "data", result=None)
    assert ws.codes(3) == [] and ws.codes(4) == ["spike-missing"] and ws.codes(10) == ["spike-missing"]
    for level in ("S", "M", "L", "chưa duyệt", ""):
        assert ws.codes(4, level) == [], level


def test_tooling_and_third_party_are_never_required(ws):
    spike(ws, "tooling", result=None)
    spike(ws, "third-party", "S-02-x", "S-02", result=None)
    assert ws.codes(4) == []
    ws.put("plan/plan.md", "# Kế hoạch\n\n## Lớp cần spike\n\n- tooling: muốn thử\n- third-party: muốn thử\n")
    assert ws.codes(4) == []


def test_a_layer_the_planner_added_needs_a_spike_too(ws):
    spike(ws, "frontend", result=None)
    assert ws.codes(4) == []                       # not required until the Planner marks it
    ws.put("plan/plan.md", "# Kế hoạch\n\n## Quyết định khó đảo ngược\n\n- x\n\n## Lớp cần spike\n\n- `frontend`: giả thuyết hiệu năng quyết định stack (NFR-01)\n- cache - ghi chú\n\n## Task\n\n- không phải lớp\n")
    assert ws.codes(4) == ["spike-missing"] and "frontend" in ws.messages(4)[0]
    assert any("cache" in f.message for f in ws.check(4).warnings if f.code == "spike-layer-absent")    # `cache` has no folder: a warning only
    spike(ws, "frontend")
    assert ws.codes(4) == []


def test_a_required_layer_with_no_folder_is_only_a_warning(ws):
    spike(ws, "data")
    assert ws.codes(4) == [] and ws.codes(4, blocking=False) == ["spike-layer-absent"] * 3


def test_layer_names_are_matched_ignoring_case(ws):
    spike(ws, "Data", result=None)
    assert ws.codes(4) == ["spike-missing"]


# --- everything together and the script --------------------------------------------------------------------------------------

def test_an_empty_workspace_is_clean(ws):
    assert ws.codes(0) == [] and ws.codes(10, level="S") == []


def cli(ws_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(ws_root), "--date", TODAY, *args], capture_output=True, text=True, encoding="utf-8")


def test_the_gate_defaults_to_the_current_stage_of_state_md(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G4", "đang làm"))
    ws.put("state.md", state_text("G3", "M"))
    assert cli(ws.root).returncode == 0
    ws.put("state.md", state_text("G4", "M"))
    proc = cli(ws.root)
    assert proc.returncode == 1 and "task-open" in proc.stdout and "check_workspace G4" in proc.stdout
    assert cli(ws.root, "--gate", "G3").returncode == 0     # --gate wins over state.md


def test_the_report_is_written_with_numbers_errors_and_warnings(ws):
    ws.put("plan/tasks/T-001-thu.md", task_text("G1", "mở"))
    ws.put("models.md", models_text([model_row("sonnet")], [("T-001", "x", "mystery")]))
    ws.put("state.md", state_text("G4", "M"))
    proc = cli(ws.root)
    assert proc.returncode == 1 and "warning:" in proc.stdout
    report = (ws.root / "checks" / f"workspace-{TODAY}.md").read_text(encoding="utf-8")
    assert "1 lỗi chặn, 1 cảnh báo" in report and "[task-open]" in report and "[model-unknown]" in report and "task: 1 file, 1 chưa đóng" in report


def test_a_clean_workspace_exits_zero(ws):
    proc = cli(ws.root)
    assert proc.returncode == 0 and "0 lỗi chặn" in proc.stdout


def test_bad_arguments_exit_two(ws, tmp_path):
    assert cli(tmp_path / "nope").returncode == 2
    for gate in ("4", "G11", "g4", "banana", "G"):
        assert cli(ws.root, "--gate", gate).returncode == 2, gate
    (ws.root / "state.md").unlink()
    assert cli(ws.root).returncode == 2                      # no --gate and no state.md
    assert cli(ws.root, "--gate", "G4", "--config", str(tmp_path / "none.yaml")).returncode == 2


def test_many_errors_are_cut_on_screen_but_all_are_in_the_report(ws):
    for n in range(40):
        ws.put(f"plan/tasks/T-{n:03d}-x.md", task_text("G1", "mở"))
    proc = cli(ws.root)
    assert proc.returncode == 1 and "và 15 lỗi nữa" in proc.stdout
    assert (ws.root / "checks" / f"workspace-{TODAY}.md").read_text(encoding="utf-8").count("[task-open]") == 40


# --- data and documents ------------------------------------------------------------------------------------------------------

def test_the_data_file_is_valid_and_holds_the_agreed_thresholds():
    cfg, errors = cw.load_config(cw.DEFAULT_CONFIG)
    assert not errors and cfg is not None
    assert cfg.risk_threshold == 15 and cfg.risk_block_from_gate == 9 and cfg.spike_from_gate == 4 and cfg.spike_level == "XL"
    assert cfg.task_closed == "đóng" and cfg.decision_resolved == "đã quyết" and cfg.risk_accepted == "đã chấp nhận"


@pytest.mark.parametrize("mutate", [
    lambda d: d["tasks"].update(closed="xong"), lambda d: d["decisions"].update(resolved="ok"), lambda d: d["risks"].update(threshold=0),
    lambda d: d["risks"].update(threshold=26), lambda d: d["risks"].update(handled=["lạ"]), lambda d: d["risks"].pop("register"), lambda d: d.pop("spikes"),
    lambda d: d["tasks"].update(statuses=[]), lambda d: d["risks"].update(block_from_gate="9"),
])
def test_a_bad_data_file_is_refused(tmp_path, mutate):
    data = yaml.safe_load(cw.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "workspace.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    cfg, errors = cw.load_config(path)
    assert cfg is None and errors


def test_the_words_match_the_templates_and_documents():
    log = (CORE / "templates" / "workspace" / "decision-log.md").read_text(encoding="utf-8")
    for status in CFG.decision_statuses:
        assert status in log, status
    task = (CORE / "templates" / "workspace" / "task.md").read_text(encoding="utf-8")
    for status in CFG.task_statuses:
        assert status in task, status
    decision = (CORE / "templates" / "workspace" / "decision.md").read_text(encoding="utf-8")
    assert all(label in decision for label in ("Trạng thái", "Người dùng nói", "Phương án được chọn"))
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    for status in CFG.risk_statuses:
        assert status.capitalize() in plan or status in plan, status
    row = next(line for line in plan.splitlines() if line.startswith("| `check_workspace.py"))
    for needle in ("--gate", "G9", "workspace.yaml", "spike", "Gán model"):
        assert needle in row, needle
    stages = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")
    assert "check_workspace.py --gate" in stages and "data/workspace.yaml" in stages
