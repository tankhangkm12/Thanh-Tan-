"""E-spec: cases found while proving the protections by mutation (the locked files did not cover them)."""

import pytest
from spec_helpers import GATE_FAILED, advance, at_spec_step, block, start, write_spec


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    at_spec_step(gitflow_repo, monkeypatch, capsys)
    return gitflow_repo


def test_a_test_file_that_git_ignores_is_not_committed_and_is_refused(repo, monkeypatch, capsys):
    (repo / ".git" / "info" / "exclude").write_text("tests/hidden_test.py" + chr(10), encoding="utf-8")
    (repo / "tests" / "hidden_test.py").write_text("import sys" + chr(10) + "sys.exit(1)" + chr(10), encoding="utf-8")
    write_spec(monkeypatch, block("C1", "Build it", command="python tests/hidden_test.py"), block("C2", "Test it"))
    code, _out, err = advance(capsys)
    assert code == GATE_FAILED
    assert "tests/hidden_test.py" in err and "not committed" in err
