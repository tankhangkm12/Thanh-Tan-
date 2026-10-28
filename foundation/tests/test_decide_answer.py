import io

import pytest
from conftest import SAMPLE_WORKFLOW, write_workflow

from thanhtan.cli import main
from thanhtan.constants import ExitCode
from thanhtan.knowledge import init_store

PLAN = """### C1 - Build it
- role: builder
- kind: other
- done-when: `pytest`
- docs: không có — internal change

## Chưa có quy ước

### Q1 - Tên bảng số ít hay số nhiều?
- ask: Chưa có quy ước đặt tên bảng.
- options: số ít, số nhiều
"""

CONVENTIONS = """### PC-01 - Constants
- check: review
- status: unconfirmed
- source: src/constants.py
- description: Fixed values live in constants.

## Câu hỏi mở

### S1 - pytest or unittest?
- docs: docs/testing.md:5
- code: Makefile:14
"""


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]  # "build" plays the plan step
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def say(monkeypatch, *argv, text=None):
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def at_plan_step(monkeypatch, capsys, plan=PLAN):
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])
    say(monkeypatch, "report", "--step", "build", text=plan)
    capsys.readouterr()


def test_an_unanswered_question_blocks_the_plan_until_a_person_answers(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys)
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    assert "Q1" in capsys.readouterr().err
    assert main(["plan", "check"]) == ExitCode.PLAN_INVALID
    assert "decide --answer Q1" in capsys.readouterr().out
    assert main(["decide", "--answer", "Q1", "--text", "Table names are singular.", "--check", "review"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "DC-01" in out and (ws / ".ThanhTan" / "decisions" / "T-001-answer-Q1.md").is_file()
    assert main(["plan", "check"]) == ExitCode.OK
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK


def test_the_answer_becomes_a_convention_agents_are_given(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys)
    main(["decide", "--answer", "Q1", "--text", "Table names are singular.", "--check", "review"])
    capsys.readouterr()
    assert main(["conventions"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "DC-01 (decisions, check=review)" in out and "Table names are singular." in out
    assert "unconfirmed" not in out  # a person's decision needs no confirming


def test_codes_continue_and_each_question_is_answered_once(ws, monkeypatch, capsys):
    plan = PLAN + "\n### Q2 - Soft delete?\n- ask: Chưa rõ.\n"
    at_plan_step(monkeypatch, capsys, plan)
    assert main(["decide", "--answer", "Q1", "--text", "a", "--check", "review"]) == ExitCode.OK
    assert main(["decide", "--answer", "Q2", "--text", "b", "--check", "review"]) == ExitCode.OK
    assert "DC-02" in capsys.readouterr().out
    assert main(["decide", "--answer", "Q1", "--text", "again", "--check", "review"]) == ExitCode.INVALID_INPUT


def test_bad_answers_are_refused(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys)
    assert main(["decide", "--answer", "Q9", "--text", "x", "--check", "review"]) == ExitCode.INVALID_INPUT
    assert main(["decide", "--answer", "Q1", "--check", "review"]) == ExitCode.INVALID_INPUT  # no text
    assert main(["decide", "--answer", "Q1", "--text", "x"]) == ExitCode.INVALID_INPUT  # no check
    assert main(["decide", "--answer", "Q1", "--text", "x", "--check", "semgrep"]) == ExitCode.CONVENTIONS_INVALID  # needs a rule file
    assert main(["decide", "--answer", "Q1", "--text", "x", "--check", "plan", "--rule", "sort"]) == ExitCode.CONVENTIONS_INVALID
    assert not list((ws / ".ThanhTan" / "decisions").glob("*answer*"))


def test_suppress_and_answer_cannot_be_combined_and_one_is_needed(ws, capsys):
    with pytest.raises(SystemExit):
        main(["decide", "--suppress", "x", "--answer", "Q1", "--reason", "r"])
    with pytest.raises(SystemExit):
        main(["decide"])


def test_an_answer_can_switch_on_the_item_order_rule(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys)
    assert main(["decide", "--answer", "Q1", "--text", "Interfaces first.", "--check", "plan", "--rule", "item-order"]) == ExitCode.OK
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.OK  # C1 says `kind: other`
    say(monkeypatch, "report", "--step", "build", text=PLAN.replace("- kind: other\n", ""))
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.PLAN_INVALID
    assert "missing 'kind'" in capsys.readouterr().out


def test_global_also_writes_the_answer_into_the_personal_store(ws, monkeypatch, capsys, tmp_path):
    store = tmp_path / "kb"
    init_store(store)
    main(["knowledge", "init", "--dir", str(store)])
    at_plan_step(monkeypatch, capsys)
    assert main(["decide", "--answer", "Q1", "--text", "Singular names.", "--check", "review", "--global"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "KC-01" in out
    text = (store / "conventions.md").read_text(encoding="utf-8")
    assert "### KC-01" in text and "Singular names." in text and "answer to Q1 of T-001" in text


def test_global_without_a_store_changes_nothing(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys)
    assert main(["decide", "--answer", "Q1", "--text", "x", "--check", "review", "--global"]) == ExitCode.INVALID_INPUT
    assert "knowledge init" in capsys.readouterr().err
    assert not list((ws / ".ThanhTan" / "decisions").glob("*answer*"))


def test_a_setup_question_is_answered_for_the_project(ws, capsys):
    (ws / ".ThanhTan" / "project" / "conventions.md").write_text(CONVENTIONS, encoding="utf-8")
    assert main(["decide", "--answer", "S1", "--text", "Use pytest.", "--check", "review"]) == ExitCode.OK
    assert (ws / ".ThanhTan" / "decisions" / "project-answer-S1.md").is_file()
    capsys.readouterr()
    main(["conventions"])
    assert "Use pytest." in capsys.readouterr().out


TWO_LAYERS_PLAN = """### C1 - Domain
- role: builder
- layer: domain
- done-when: `pytest`
- docs: không có — internal change

### C2 - Interface
- role: builder
- layer: interface
- done-when: `pytest`
- docs: không có — internal change

## Chưa có quy ước

### Q1 - Thứ tự lớp?
- ask: Chưa có quy ước về thứ tự lớp.
"""


def test_an_answer_can_switch_on_the_layer_order_rule(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys, TWO_LAYERS_PLAN)
    assert main(["decide", "--answer", "Q1", "--text", "Lower layers first.", "--check", "plan", "--rule", "layer-order", "--layers", "interface, domain"]) == ExitCode.OK
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.PLAN_INVALID
    assert "C2" in capsys.readouterr().out
    swapped = TWO_LAYERS_PLAN.replace("layer: domain", "layer: X").replace("layer: interface", "layer: domain").replace("layer: X", "layer: interface")
    say(monkeypatch, "report", "--step", "build", text=swapped)
    capsys.readouterr()
    assert main(["plan", "check"]) == ExitCode.OK


def test_a_layer_order_answer_without_layers_is_refused(ws, monkeypatch, capsys):
    at_plan_step(monkeypatch, capsys, TWO_LAYERS_PLAN)
    assert main(["decide", "--answer", "Q1", "--text", "x", "--check", "plan", "--rule", "layer-order"]) == ExitCode.CONVENTIONS_INVALID
