import pytest

from thanhtan.cli import main
from thanhtan.constants import ExitCode

DOC = """# Quy ước

### PC-01 - Constants
- check: review
- status: unconfirmed
- source: src/constants.py (inferred from code)
- description: Fixed values live in constants or enums.

### PC-02 - Interface first
- check: plan
- rule: item-order
- status: unconfirmed
- source: docs/CONTRIBUTING.md:12
- description: Interfaces come before implementations.

## Câu hỏi mở

### S1 - pytest or unittest?
- docs: docs/testing.md:5
- code: Makefile:14
"""


@pytest.fixture
def ws(gitflow_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def doc_path(ws):
    return ws / ".ThanhTan" / "project" / "conventions.md"


def put(ws, text=DOC):
    doc_path(ws).write_text(text, encoding="utf-8")


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def statuses(ws):
    text = doc_path(ws).read_text(encoding="utf-8")
    return {code: "status: confirmed" in block for code, block in ((c, text.split(f"### {c} -")[1].split("###")[0]) for c in ("PC-01", "PC-02"))}


def test_confirm_marks_only_the_named_conventions(ws, capsys):
    put(ws)
    code, out, _ = run(capsys, "project", "confirm", "PC-02")
    assert code == ExitCode.OK and "confirmed: PC-02" in out
    assert statuses(ws) == {"PC-01": False, "PC-02": True}
    assert "still unconfirmed: PC-01" in out
    assert "open questions: S1" in out


def test_confirm_all(ws, capsys):
    put(ws)
    code, out, _ = run(capsys, "project", "confirm", "--all")
    assert code == ExitCode.OK and statuses(ws) == {"PC-01": True, "PC-02": True}
    assert "confirmed: PC-01, PC-02" in out and "still unconfirmed" not in out
    assert "## Câu hỏi mở" in doc_path(ws).read_text(encoding="utf-8")  # the questions stay for the person to answer


def test_confirming_twice_reports_it(ws, capsys):
    put(ws)
    run(capsys, "project", "confirm", "PC-01")
    code, out, _ = run(capsys, "project", "confirm", "PC-01")
    assert code == ExitCode.OK and "already confirmed: PC-01" in out


def test_an_unknown_code_changes_nothing(ws, capsys):
    put(ws)
    code, _, err = run(capsys, "project", "confirm", "PC-01", "PC-99")
    assert code == ExitCode.INVALID_INPUT and "PC-99" in err
    assert statuses(ws) == {"PC-01": False, "PC-02": False}


def test_it_needs_codes_or_all(ws, capsys):
    put(ws)
    assert run(capsys, "project", "confirm")[0] == ExitCode.INVALID_INPUT
    assert run(capsys, "project", "confirm", "PC-01", "--all")[0] == ExitCode.INVALID_INPUT


def test_there_must_be_conventions(ws, capsys):
    code, _, err = run(capsys, "project", "confirm", "--all")
    assert code == ExitCode.INVALID_INPUT and "setup" in err


def test_a_document_with_problems_is_not_confirmed(ws, capsys):
    put(ws, DOC.replace("- check: review", "- check: lint"))
    code, _, err = run(capsys, "project", "confirm", "--all")
    assert code == ExitCode.CONVENTIONS_INVALID and "check" in err


def test_task_new_warns_while_conventions_are_unconfirmed(ws, capsys):
    put(ws)
    code, _, err = run(capsys, "task", "new", "first")
    assert code == ExitCode.OK and "2 convention(s) are still unconfirmed" in err and "project confirm" in err
    run(capsys, "task", "cancel")
    run(capsys, "project", "confirm", "--all")
    code, _, err = run(capsys, "task", "new", "second")
    assert code == ExitCode.OK and "unconfirmed" not in err


def test_task_new_does_not_warn_without_conventions(ws, capsys):
    code, _, err = run(capsys, "task", "new", "first")
    assert code == ExitCode.OK and "unconfirmed" not in err


def test_conventions_command_lists_the_merged_conventions(ws, capsys):
    code, out, _ = run(capsys, "conventions")
    assert code == ExitCode.OK and "no conventions yet" in out
    put(ws)
    run(capsys, "project", "confirm", "PC-02")
    code, out, _ = run(capsys, "conventions")
    assert "PC-01 (project, check=review) [unconfirmed" in out and "PC-02 (project, check=plan rule=item-order):" in out
