from importlib.metadata import version

import pytest

from agentflow import cli
from agentflow.cli import main
from agentflow.constants import ExitCode, StepStatus, TaskStatus
from agentflow.doctor import ENGINE_NOT_RUNNING
from agentflow.models import ProbeResult, State, Task
from agentflow.state import JsonStateStore
from agentflow.workspace import WorkspacePaths, load_workspace_workflow


def test_version_prints_name_and_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"agentflow {version('agentflow')}"


def test_no_command_prints_help_and_usage_code(capsys):
    assert main([]) == ExitCode.USAGE
    assert "usage:" in capsys.readouterr().out


class FakeProbe:
    def __init__(self, installed, engine_ok=True):
        self.installed, self.engine_ok = installed, engine_ok

    def which(self, name):
        return name if name in self.installed else None

    def run(self, args):
        if args[1] == "--version":
            return ProbeResult(0, f"{args[0]} 1.0\n")
        return ProbeResult(0 if self.engine_ok else 1, "")


@pytest.fixture
def probe(monkeypatch):
    def install(installed, engine_ok=True):
        monkeypatch.setattr(cli, "SystemToolProbe", lambda: FakeProbe(installed, engine_ok))

    return install


def test_doctor_all_ok(probe, capsys):
    probe({"uv", "git", "docker"})
    assert main(["doctor"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "[ok]" in out and "result: all required tools found" in out
    assert "https://podman.io/docs/installation" in out  # missing optional tool still shows its link


def test_doctor_missing_required(probe, capsys):
    probe({"git", "docker"})
    assert main(["doctor"]) == ExitCode.MISSING_REQUIREMENT
    out = capsys.readouterr().out
    assert "[missing] uv" in out
    assert "https://docs.astral.sh/uv/getting-started/installation/" in out


def test_doctor_without_container_runtime(probe, capsys):
    probe({"uv", "git"})
    assert main(["doctor"]) == ExitCode.MISSING_REQUIREMENT
    assert "install at least one of docker, podman" in capsys.readouterr().out


def test_doctor_engine_down_is_warning_only(probe, capsys):
    probe({"uv", "git", "docker"}, engine_ok=False)
    assert main(["doctor"]) == ExitCode.OK
    assert ENGINE_NOT_RUNNING in capsys.readouterr().out


def test_init_requires_workflow_option(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["init"])
    assert exc.value.code == ExitCode.USAGE


def test_init_creates_workspace(git_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "workflow: sample (copied;" in out
    assert "git exclude: added .ThanhTan/" in out
    assert (git_repo / ".ThanhTan" / "state.json").is_file()


def test_init_twice_is_safe(git_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    main(["init", "--workflow", str(workflow_file)])
    capsys.readouterr()
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "created: nothing, workspace was complete" in out
    assert "git exclude: already excluded" in out


def test_init_outside_git_reports_error(tmp_path, workflow_file, monkeypatch, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.NOT_GIT_REPO
    assert capsys.readouterr().err.startswith("error: not inside a git repository")


@pytest.fixture
def workspace(git_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    capsys.readouterr()
    return git_repo


def save_tasks(repo, *tasks, active=None):
    paths = WorkspacePaths(repo)
    JsonStateStore(paths.dir, load_workspace_workflow(paths)).save(State(active_task_id=active, tasks=tasks))


def make_task(task_id="T-001", step="check", step_status="in_progress", status="open", loop_round=0, branch=None):
    return Task(task_id, "Do it", TaskStatus(status), step, StepStatus(step_status), loop_round, branch)


@pytest.mark.parametrize("command", ["status", "next"])
def test_status_and_next_need_a_workspace(git_repo, monkeypatch, capsys, command):
    monkeypatch.chdir(git_repo)
    assert main([command]) == ExitCode.NO_WORKSPACE
    assert "agentflow init --workflow" in capsys.readouterr().err


def test_status_without_tasks(workspace, capsys):
    assert main(["status"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "workflow: sample (3 steps)" in out
    assert "active task: none" in out
    assert "next: start a new task at step 'confirm' (Confirm; role lead, needs approval)" in out


def test_status_with_active_task(workspace, capsys):
    save_tasks(
        workspace,
        make_task(loop_round=1, branch="feature/x"),
        make_task("T-002", "build", "in_progress"),
        active="T-001",
    )
    assert main(["status"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "active task: T-001 Do it" in out
    assert "current step: step 'check' (Check; role checker), in_progress" in out
    assert "rework rounds: 1/2; branch: feature/x" in out
    assert "other open tasks: T-002 (build, open)" in out
    assert "next: work on step 'check' (Check; role checker), rework round 1/2" in out


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (None, "start_task: start a new task at step 'confirm'"),
        (make_task(step="confirm", step_status="awaiting_approval"), "await_approval: wait for a person"),
        (make_task(step="build"), "continue: work on step 'build'"),
        (make_task(status="blocked", step_status="failed", loop_round=2), "blocked: blocked at step 'check'"),
    ],
)
def test_next(workspace, capsys, task, expected):
    if task is not None:
        save_tasks(workspace, task, active=task.id)
    assert main(["next"]) == ExitCode.OK
    assert capsys.readouterr().out.startswith(expected)


def test_next_reads_the_copy_and_warns_on_drift(workspace, workflow_file, capsys):
    text = workflow_file.read_text(encoding="utf-8").replace("name: Confirm", "name: Confirm v2")
    workflow_file.write_text(text, encoding="utf-8")
    assert main(["next"]) == ExitCode.OK
    captured = capsys.readouterr()
    assert "(Confirm;" in captured.out  # still the copy
    assert "agentflow workflow sync" in captured.err


def test_next_uses_copy_when_source_is_gone(workspace, workflow_file, capsys):
    workflow_file.unlink()
    assert main(["next"]) == ExitCode.OK
    captured = capsys.readouterr()
    assert captured.out.startswith("start_task:")
    assert "no longer exists" in captured.err


def test_status_reports_corrupt_state(workspace, capsys):
    (workspace / ".ThanhTan" / "state.json").write_text("{}", encoding="utf-8")
    assert main(["status"]) == ExitCode.INVALID_STATE
    assert capsys.readouterr().err.startswith("error:")


def change_source(workflow_file):
    text = workflow_file.read_text(encoding="utf-8").replace("name: Build", "name: Build v2")
    workflow_file.write_text(text, encoding="utf-8")


def test_workflow_needs_a_subcommand(workspace, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["workflow"])
    assert exc.value.code == ExitCode.USAGE


def test_sync_when_unchanged(workspace, capsys):
    assert main(["workflow", "sync"]) == ExitCode.OK
    assert "already in sync" in capsys.readouterr().out


def test_sync_replaces_copy_and_silences_warning(workspace, workflow_file, capsys):
    change_source(workflow_file)
    assert main(["workflow", "sync"]) == ExitCode.OK
    assert "copy replaced" in capsys.readouterr().out
    assert main(["status"]) == ExitCode.OK
    assert capsys.readouterr().err == ""


def test_sync_blocked_by_open_task_then_forced(workspace, workflow_file, capsys):
    save_tasks(workspace, make_task(step="build", step_status="in_progress"), active="T-001")
    change_source(workflow_file)
    assert main(["workflow", "sync"]) == ExitCode.SYNC_BLOCKED
    assert "--force" in capsys.readouterr().err
    assert main(["workflow", "sync", "--force"]) == ExitCode.OK
    captured = capsys.readouterr()
    assert "copy replaced" in captured.out
    assert "T-001" in captured.err


def test_sync_rejects_invalid_source(workspace, workflow_file, capsys):
    workflow_file.write_text("schema_version: 1\nfamily: sample\nsteps: []\n", encoding="utf-8")
    assert main(["workflow", "sync"]) == ExitCode.INVALID_WORKFLOW
    assert "invalid workflow" in capsys.readouterr().err


def test_init_warns_when_source_changed_since_copy(git_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    main(["init", "--workflow", str(workflow_file)])
    workflow_file.write_text(workflow_file.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    assert "agentflow workflow sync" in capsys.readouterr().err
