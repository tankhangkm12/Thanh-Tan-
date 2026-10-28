"""Chặng D-checklist (việc thêm): `agentflow doctor` says when the `agentflow` on PATH is not the one in use.

A hook runs the `agentflow` found on PATH. After a plugin update that is still the old build until the person installs
it again, and an old hook does not understand `ask`. So `doctor` compares the version on PATH with the version running
now (the repo's, when started with `uv run`) and, when they differ, prints the command that fixes it. A difference is a
warning: the report stays `ok`.
"""

from collections.abc import Sequence

from agentflow.cli import main
from agentflow.constants import ExitCode, ToolStatus
from agentflow.doctor import run_doctor
from agentflow.models import ProbeResult

REINSTALL = "uv tool install --force --reinstall ./foundation"


class Machine:
    """Everything installed; `agentflow --version` says ``on_path`` (or fails, or is absent)."""

    def __init__(self, on_path: str | None = "0.5.0", version_fails: bool = False) -> None:
        self.on_path = on_path
        self.version_fails = version_fails

    def which(self, name: str) -> str | None:
        if name == "agentflow":
            return None if self.on_path is None else "/bin/agentflow"
        return f"/bin/{name}"

    def run(self, args: Sequence[str]) -> ProbeResult:
        name = args[0].removeprefix("/bin/")
        if name == "agentflow":
            return ProbeResult(1, "") if self.version_fails else ProbeResult(0, f"agentflow {self.on_path}\n")
        return ProbeResult(0, f"{name} 1.0\n")


def agentflow_check(report):
    found = [check for check in report.checks if check.tool == "agentflow"]
    assert len(found) == 1, "doctor reports the agentflow on PATH exactly once"
    return found[0]


def test_the_same_version_on_path_is_fine():
    check = agentflow_check(run_doctor(Machine("0.5.0"), running_version="0.5.0"))
    assert check.status is ToolStatus.OK
    assert "0.5.0" in (check.version or "")


def test_a_different_version_on_path_is_a_warning_that_names_both_and_the_fix():
    report = run_doctor(Machine("0.4.0"), running_version="0.5.0")
    check = agentflow_check(report)
    assert check.status is ToolStatus.WARNING
    detail = check.detail or ""
    assert "0.4.0" in detail and "0.5.0" in detail and REINSTALL in detail
    assert report.ok, "a stale install is a warning, not a failure of the machine"


def test_an_agentflow_missing_from_path_is_a_warning_because_the_hooks_run_it():
    check = agentflow_check(run_doctor(Machine(None), running_version="0.5.0"))
    assert check.status is ToolStatus.WARNING
    assert "PATH" in (check.detail or "") and REINSTALL in (check.detail or "")


def test_an_agentflow_whose_version_cannot_be_read_is_a_warning():
    check = agentflow_check(run_doctor(Machine(version_fails=True), running_version="0.5.0"))
    assert check.status is ToolStatus.WARNING


def test_without_a_running_version_nothing_about_agentflow_is_reported():
    report = run_doctor(Machine("0.4.0"))
    assert [check.tool for check in report.checks if check.tool == "agentflow"] == []


def test_the_command_prints_the_warning_and_the_fix_and_still_exits_ok(monkeypatch, capsys):
    monkeypatch.setattr("agentflow.cli.SystemToolProbe", lambda: Machine("0.4.0"))
    monkeypatch.setattr("agentflow.cli.running_version", lambda: "0.5.0")
    assert main(["doctor"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "agentflow" in out and "0.4.0" in out and REINSTALL in out


def test_the_command_is_quiet_about_agentflow_when_the_versions_match(monkeypatch, capsys):
    monkeypatch.setattr("agentflow.cli.SystemToolProbe", lambda: Machine("0.5.0"))
    monkeypatch.setattr("agentflow.cli.running_version", lambda: "0.5.0")
    assert main(["doctor"]) == ExitCode.OK
    assert REINSTALL not in capsys.readouterr().out


def test_the_running_version_is_read_from_the_installed_package():
    from agentflow.doctor import running_version

    assert isinstance(running_version(), str) and running_version()
