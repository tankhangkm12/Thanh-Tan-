"""Chặng D-checklist (việc thêm): `thanhtan doctor` says when the `thanhtan` on PATH is not the one in use.

A hook runs the `thanhtan` found on PATH. After a plugin update that is still the old build until the person installs
it again, and an old hook does not understand `ask`. So `doctor` compares the version on PATH with the version running
now (the repo's, when started with `uv run`) and, when they differ, prints the command that fixes it. A difference is a
warning: the report stays `ok`.
"""

from collections.abc import Sequence

from thanhtan.cli import main
from thanhtan.constants import ExitCode, ToolStatus
from thanhtan.doctor import run_doctor
from thanhtan.models import ProbeResult

REINSTALL = "uv tool install --force --reinstall ./foundation"


class Machine:
    """Everything installed; `thanhtan --version` says ``on_path`` (or fails, or is absent)."""

    def __init__(self, on_path: str | None = "0.5.0", version_fails: bool = False) -> None:
        self.on_path = on_path
        self.version_fails = version_fails

    def which(self, name: str) -> str | None:
        if name == "thanhtan":
            return None if self.on_path is None else "/bin/thanhtan"
        return f"/bin/{name}"

    def run(self, args: Sequence[str]) -> ProbeResult:
        name = args[0].removeprefix("/bin/")
        if name == "thanhtan":
            return ProbeResult(1, "") if self.version_fails else ProbeResult(0, f"thanhtan {self.on_path}\n")
        return ProbeResult(0, f"{name} 1.0\n")


def thanhtan_check(report):
    found = [check for check in report.checks if check.tool == "thanhtan"]
    assert len(found) == 1, "doctor reports the thanhtan on PATH exactly once"
    return found[0]


def test_the_same_version_on_path_is_fine():
    check = thanhtan_check(run_doctor(Machine("0.5.0"), running_version="0.5.0"))
    assert check.status is ToolStatus.OK
    assert "0.5.0" in (check.version or "")


def test_a_different_version_on_path_is_a_warning_that_names_both_and_the_fix():
    report = run_doctor(Machine("0.4.0"), running_version="0.5.0")
    check = thanhtan_check(report)
    assert check.status is ToolStatus.WARNING
    detail = check.detail or ""
    assert "0.4.0" in detail and "0.5.0" in detail and REINSTALL in detail
    assert report.ok, "a stale install is a warning, not a failure of the machine"


def test_an_thanhtan_missing_from_path_is_a_warning_because_the_hooks_run_it():
    check = thanhtan_check(run_doctor(Machine(None), running_version="0.5.0"))
    assert check.status is ToolStatus.WARNING
    assert "PATH" in (check.detail or "") and REINSTALL in (check.detail or "")


def test_an_thanhtan_whose_version_cannot_be_read_is_a_warning():
    check = thanhtan_check(run_doctor(Machine(version_fails=True), running_version="0.5.0"))
    assert check.status is ToolStatus.WARNING


def test_without_a_running_version_nothing_about_thanhtan_is_reported():
    report = run_doctor(Machine("0.4.0"))
    assert [check.tool for check in report.checks if check.tool == "thanhtan"] == []


def test_the_command_prints_the_warning_and_the_fix_and_still_exits_ok(monkeypatch, capsys):
    monkeypatch.setattr("thanhtan.cli.SystemToolProbe", lambda: Machine("0.4.0"))
    monkeypatch.setattr("thanhtan.cli.running_version", lambda: "0.5.0")
    assert main(["doctor"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "thanhtan" in out and "0.4.0" in out and REINSTALL in out


def test_the_command_is_quiet_about_thanhtan_when_the_versions_match(monkeypatch, capsys):
    monkeypatch.setattr("thanhtan.cli.SystemToolProbe", lambda: Machine("0.5.0"))
    monkeypatch.setattr("thanhtan.cli.running_version", lambda: "0.5.0")
    assert main(["doctor"]) == ExitCode.OK
    assert REINSTALL not in capsys.readouterr().out


def test_the_running_version_is_read_from_the_installed_package():
    from thanhtan.doctor import running_version

    assert isinstance(running_version(), str) and running_version()
