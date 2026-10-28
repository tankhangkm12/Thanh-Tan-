from collections.abc import Sequence

import pytest

from thanhtan.constants import Tool, ToolStatus
from thanhtan.doctor import ENGINE_NOT_RUNNING, SystemToolProbe, check_tool, run_doctor
from thanhtan.interfaces import ToolProbe
from thanhtan.models import ProbeResult


class FakeProbe:
    """Installed tools map to (version exit code, engine `info` exit code)."""

    def __init__(self, installed: dict[str, tuple[int, int]]) -> None:
        self.installed = installed

    def which(self, name: str) -> str | None:
        return f"/bin/{name}" if name in self.installed else None

    def run(self, args: Sequence[str]) -> ProbeResult:
        name = args[0].removeprefix("/bin/")
        version_code, info_code = self.installed[name]
        if args[1] == "--version":
            return ProbeResult(version_code, f"{name} 1.0\nmore\n")
        return ProbeResult(info_code, "")


ALL_OK = {"uv": (0, 0), "git": (0, 0), "docker": (0, 0), "podman": (0, 0)}


def statuses(report):
    return {check.tool: check.status for check in report.checks}


def test_probes_implement_protocol():
    assert isinstance(FakeProbe({}), ToolProbe)
    assert isinstance(SystemToolProbe(), ToolProbe)


def test_everything_present():
    report = run_doctor(FakeProbe(ALL_OK))
    assert report.ok
    assert set(statuses(report).values()) == {ToolStatus.OK}
    assert report.checks[0].version == "uv 1.0"


@pytest.mark.parametrize("missing", ["uv", "git"])
def test_missing_required_tool_fails(missing):
    installed = {k: v for k, v in ALL_OK.items() if k != missing}
    report = run_doctor(FakeProbe(installed))
    assert not report.ok
    check = next(c for c in report.checks if c.tool == missing)
    assert check.status is ToolStatus.MISSING and check.required
    assert check.install_url.startswith("https://")


def test_one_container_tool_is_enough():
    installed = {k: v for k, v in ALL_OK.items() if k != "podman"}
    report = run_doctor(FakeProbe(installed))
    assert report.ok
    assert statuses(report)[Tool.PODMAN] is ToolStatus.MISSING


def test_no_container_tool_fails():
    report = run_doctor(FakeProbe({"uv": (0, 0), "git": (0, 0)}))
    assert not report.ok


def test_engine_not_running_is_only_a_warning():
    report = run_doctor(FakeProbe({"uv": (0, 0), "git": (0, 0), "docker": (0, 1)}))
    assert report.ok
    docker = next(c for c in report.checks if c.tool is Tool.DOCKER)
    assert docker.status is ToolStatus.WARNING
    assert docker.detail == ENGINE_NOT_RUNNING


def test_failing_version_is_a_warning():
    check = check_tool(FakeProbe({"git": (1, 0)}), Tool.GIT, required=True)
    assert check.status is ToolStatus.WARNING


def test_system_probe_reports_unrunnable_command():
    result = SystemToolProbe().run(["thanhtan-surely-not-installed-xyz"])
    assert result.returncode != 0
