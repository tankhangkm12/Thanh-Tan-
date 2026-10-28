from pathlib import Path

import pytest

from agentflow.constants import GITLEAKS_IMAGE, GITLEAKS_LEAKS_EXIT_CODE, ExitCode
from agentflow.errors import AgentflowError
from agentflow.interfaces import CommandRunner, SecretScanner
from agentflow.models import CommandResult
from agentflow.runner import NOT_RUN, SubprocessRunner
from agentflow.scanner import ContainerGitleaksScanner, gitleaks_command

REPO = Path("/work/repo")


class FakeRunner:
    def __init__(self, installed=("docker",), engines_up=("docker",), scan=CommandResult(0, "", "")):
        self.installed, self.engines_up, self.scan = installed, engines_up, scan
        self.calls = []

    def which(self, name):
        return f"/bin/{name}" if name in self.installed else None

    def run(self, args, cwd, timeout):
        self.calls.append((list(args), cwd))
        if args[1:] == ["info"]:
            engine = Path(args[0]).name
            return CommandResult(0 if engine in self.engines_up else 1, "", "")
        return self.scan


def test_protocols():
    assert isinstance(FakeRunner(), CommandRunner)
    assert isinstance(SubprocessRunner(), CommandRunner)
    assert isinstance(ContainerGitleaksScanner(FakeRunner()), SecretScanner)


def test_command_is_pinned_read_only_and_redacted():
    command = gitleaks_command("docker", REPO)
    assert command[0] == "docker"
    assert GITLEAKS_IMAGE in command
    assert f"{REPO}:/repo:ro" in command
    assert {"--staged", "--redact", "--no-banner"} <= set(command)
    assert command[command.index("--exit-code") + 1] == str(GITLEAKS_LEAKS_EXIT_CODE)
    assert command[-1] == "/repo"


def test_clean_scan():
    runner = FakeRunner(scan=CommandResult(0, "no leaks found", ""))
    result = ContainerGitleaksScanner(runner).scan_staged(REPO)
    assert result.clean and "no leaks" in result.output
    assert runner.calls[-1][1] == REPO


def test_leaks_found():
    runner = FakeRunner(scan=CommandResult(GITLEAKS_LEAKS_EXIT_CODE, "Finding: REDACTED", ""))
    result = ContainerGitleaksScanner(runner).scan_staged(REPO)
    assert not result.clean and "REDACTED" in result.output


def test_scanner_failure_is_a_hard_error():
    runner = FakeRunner(scan=CommandResult(1, "", "image pull failed"))
    with pytest.raises(AgentflowError) as exc:
        ContainerGitleaksScanner(runner).scan_staged(REPO)
    assert exc.value.code is ExitCode.SCAN_FAILED
    assert "image pull failed" in str(exc.value)


def test_no_container_tool_installed():
    with pytest.raises(AgentflowError) as exc:
        ContainerGitleaksScanner(FakeRunner(installed=())).scan_staged(REPO)
    assert exc.value.code is ExitCode.MISSING_REQUIREMENT


def test_engine_not_running_is_a_hard_error_and_scan_never_starts():
    runner = FakeRunner(engines_up=())
    with pytest.raises(AgentflowError) as exc:
        ContainerGitleaksScanner(runner).scan_staged(REPO)
    assert exc.value.code is ExitCode.ENGINE_NOT_RUNNING
    assert all(call[0][1:] == ["info"] for call in runner.calls)


def test_falls_back_to_podman_when_docker_is_down():
    runner = FakeRunner(installed=("docker", "podman"), engines_up=("podman",))
    ContainerGitleaksScanner(runner).scan_staged(REPO)
    assert runner.calls[-1][0][0].endswith("podman")


def test_subprocess_runner_reports_missing_program(tmp_path):
    result = SubprocessRunner().run(["definitely-not-a-real-program-xyz"], tmp_path, 5)
    assert result.returncode == NOT_RUN and "cannot run" in result.stderr
