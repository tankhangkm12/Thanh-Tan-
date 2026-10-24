import io
import json

import pytest
from conftest import git

from agentflow import cli
from agentflow.cli import main
from agentflow.constants import ExitCode
from agentflow.errors import AgentflowError
from agentflow.models import ScanResult


@pytest.fixture
def ws(gitflow_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_task_commands_need_a_subcommand(ws):
    with pytest.raises(SystemExit) as exc:
        main(["task"])
    assert exc.value.code == ExitCode.USAGE


def test_task_new_creates_branch_and_records_it(ws, capsys):
    code, out, _ = run(capsys, "task", "new", "Thêm đăng nhập", "--type", "bugfix")
    assert code == ExitCode.OK
    assert "T-001 created on branch bugfix/T-001-them-dang-nhap" in out
    assert git(ws, "branch", "--show-current") == "bugfix/T-001-them-dang-nhap"
    _, out, _ = run(capsys, "status")
    assert "active task: T-001 Thêm đăng nhập" in out
    assert "branch: bugfix/T-001-them-dang-nhap" in out


def test_task_new_defaults_to_feature_and_refuses_dirty_tree(ws, capsys):
    (ws / "stray.txt").write_text("x", encoding="utf-8")
    code, _, err = run(capsys, "task", "new", "x")
    assert code == ExitCode.DIRTY_WORKING_TREE and err.startswith("error:")
    (ws / "stray.txt").unlink()
    assert run(capsys, "task", "new", "x")[1].startswith("T-001 created on branch feature/T-001-x")


def test_task_new_rejects_unknown_type(ws):
    with pytest.raises(SystemExit) as exc:
        main(["task", "new", "x", "--type", "spike"])
    assert exc.value.code == ExitCode.USAGE


def test_full_lifecycle_through_the_cli(ws, capsys):
    # Sample workflow: confirm (approval) -> build -> check (on_fail build), 2 rounds.
    run(capsys, "task", "new", "t")
    code, out, _ = run(capsys, "task", "advance", "--result", "pass")
    assert "step 'confirm' is now awaiting_approval" in out and "wait for a person to approve" in out
    code, _, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == ExitCode.INVALID_TRANSITION and "approve" in err
    assert "step 'build' is now in_progress" in run(capsys, "task", "approve")[1]
    run(capsys, "task", "advance", "--result", "pass")
    _, out, _ = run(capsys, "task", "advance", "--result", "fail")
    assert "step 'build' is now in_progress" in out and "rework round 1/2" in out
    run(capsys, "task", "advance", "--result", "pass")
    _, out, _ = run(capsys, "task", "advance", "--result", "pass")
    assert "task done" in out and "start a new task" in out


def test_blocked_task_override_records_decision(ws, capsys):
    run(capsys, "task", "new", "t")
    run(capsys, "task", "advance", "--result", "pass")
    run(capsys, "task", "approve")
    _, out, _ = run(capsys, "task", "advance", "--result", "fail")  # build has no on_fail
    assert "task blocked" in out and "blocked" in out
    code, out, _ = run(capsys, "task", "approve", "--reason", "checked by hand")
    assert code == ExitCode.OK and "decision recorded:" in out
    decisions = [p for p in (ws / ".agentflow" / "decisions").iterdir() if p.suffix == ".md"]
    assert len(decisions) == 1 and "checked by hand" in decisions[0].read_text(encoding="utf-8")


def test_cancel_and_no_active_task(ws, capsys):
    assert run(capsys, "task", "advance", "--result", "pass")[0] == ExitCode.NO_ACTIVE_TASK
    run(capsys, "task", "new", "t")
    assert run(capsys, "task", "cancel")[1].startswith("T-001 cancelled")
    assert run(capsys, "task", "cancel")[0] == ExitCode.NO_ACTIVE_TASK


def test_report_reads_stdin(ws, capsys, monkeypatch):
    run(capsys, "task", "new", "t")
    monkeypatch.setattr("sys.stdin", io.StringIO("# Check\nfine"))
    code, out, _ = run(capsys, "report", "--step", "confirm")
    assert code == ExitCode.OK and "report saved:" in out
    report = ws / ".agentflow" / "tasks" / "T-001" / "reports" / "confirm.md"
    assert report.read_text(encoding="utf-8") == "# Check\nfine\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("x"))
    assert run(capsys, "report", "--step", "ghost")[0] == ExitCode.UNKNOWN_STEP
    assert run(capsys, "report", "--step", "check")[0] == ExitCode.REPORT_REFUSED


class FakeScanner:
    def __init__(self, result=None, error=None):
        self.result, self.error = result or ScanResult(True, ""), error

    def scan_staged(self, repo):
        if self.error:
            raise self.error
        return self.result


def use_scanner(monkeypatch, scanner):
    monkeypatch.setattr(cli, "ContainerGitleaksScanner", lambda runner: scanner)


def stage(repo):
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")


def test_commit_prefixes_the_task_id(ws, capsys, monkeypatch):
    use_scanner(monkeypatch, FakeScanner())
    run(capsys, "task", "new", "t")
    stage(ws)
    code, out, _ = run(capsys, "commit", "add a")
    assert code == ExitCode.OK and "T-001: add a" in out
    assert git(ws, "log", "-1", "--format=%s") == "T-001: add a"


def test_commit_blocked_by_leaks_and_by_engine_down(ws, capsys, monkeypatch):
    run(capsys, "task", "new", "t")
    stage(ws)
    use_scanner(monkeypatch, FakeScanner(ScanResult(False, "Finding: REDACTED")))
    code, _, err = run(capsys, "commit", "add a")
    assert code == ExitCode.SECRETS_FOUND and "REDACTED" in err
    use_scanner(monkeypatch, FakeScanner(error=AgentflowError("engine down", ExitCode.ENGINE_NOT_RUNNING)))
    assert run(capsys, "commit", "add a")[0] == ExitCode.ENGINE_NOT_RUNNING
    assert git(ws, "log", "-1", "--format=%s") == "initial"


def test_guard_denies_push_and_allows_status(ws, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"command": "git push origin develop"})))
    code, out, _ = run(capsys, "guard")
    assert code == ExitCode.OK
    assert json.loads(out)["decision"] == "deny" and json.loads(out)["rule"] == "push"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"command": "git status", "cwd": str(ws)})))
    assert json.loads(run(capsys, "guard")[1])["decision"] == "allow"


def test_guard_blocks_direct_commit_in_a_workspace(ws, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"command": "git commit -m x", "cwd": str(ws)})))
    out = json.loads(run(capsys, "guard")[1])
    assert out["decision"] == "deny" and out["rule"] == "direct-commit"


def test_guard_rejects_bad_input(ws, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("nope"))
    assert run(capsys, "guard")[0] == ExitCode.INVALID_INPUT
