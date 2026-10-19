"""Check the external tools agentflow relies on."""

import shutil
import subprocess
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from agentflow.constants import (
    CONTAINER_TOOLS,
    ENCODING,
    ENGINE_INFO_ARG,
    REQUIRED_TOOLS,
    TOOL_TIMEOUT_SECONDS,
    VERSION_FLAG,
    Tool,
    ToolStatus,
)
from agentflow.interfaces import ToolProbe
from agentflow.models import DoctorReport, ProbeResult, ToolCheck

PROBE_FAILED = -1
VERSION_FAILED = f"`{VERSION_FLAG}` failed"
REINSTALL_COMMAND = "uv tool install --force --reinstall ./foundation"
PACKAGE = "agentflow"
ENGINE_NOT_RUNNING = "installed, but the engine is not running or not reachable"


class SystemToolProbe:
    """``ToolProbe`` for the real machine."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, args: Sequence[str]) -> ProbeResult:
        try:
            done = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                encoding=ENCODING,
                errors="replace",
                timeout=TOOL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ProbeResult(PROBE_FAILED, "")
        return ProbeResult(done.returncode, done.stdout)


def check_tool(probe: ToolProbe, tool: Tool, required: bool) -> ToolCheck:
    executable = probe.which(tool)
    if executable is None:
        return ToolCheck(tool, ToolStatus.MISSING, required)
    version = probe.run([executable, VERSION_FLAG])
    if version.returncode != 0:
        return ToolCheck(tool, ToolStatus.WARNING, required, detail=VERSION_FAILED)
    first_line = next(iter(version.stdout.strip().splitlines()), None)
    if tool in CONTAINER_TOOLS and probe.run([executable, ENGINE_INFO_ARG]).returncode != 0:
        return ToolCheck(tool, ToolStatus.WARNING, required, first_line, ENGINE_NOT_RUNNING)
    return ToolCheck(tool, ToolStatus.OK, required, first_line)


def running_version() -> str:
    try:
        return version(PACKAGE)
    except PackageNotFoundError:
        return "unknown"


def check_agentflow(probe: ToolProbe, running: str) -> ToolCheck:
    """The ``agentflow`` the hooks run (the one on PATH) against the one in use: an old build does not know new hook answers."""
    executable = probe.which(PACKAGE)
    if executable is None:
        return ToolCheck(
            PACKAGE, ToolStatus.WARNING, False, detail=f"not found on PATH, but the hooks run it; install it: {REINSTALL_COMMAND}"
        )
    result = probe.run([executable, VERSION_FLAG])
    first_line = next(iter(result.stdout.strip().splitlines()), None) if result.returncode == 0 else None
    if first_line is None:
        return ToolCheck(PACKAGE, ToolStatus.WARNING, False, detail=VERSION_FAILED)
    on_path = first_line.split()[-1]
    if on_path == running:
        return ToolCheck(PACKAGE, ToolStatus.OK, False, first_line)
    return ToolCheck(
        PACKAGE,
        ToolStatus.WARNING,
        False,
        first_line,
        f"PATH has {on_path} but {running} is in use; the hooks run the one on PATH. Install again: {REINSTALL_COMMAND}",
    )


def run_doctor(probe: ToolProbe, running_version: str | None = None) -> DoctorReport:
    """Required tools must exist, and at least one container tool must exist.

    A container engine that is installed but not running is only a warning here.
    """
    required = tuple(check_tool(probe, tool, required=True) for tool in REQUIRED_TOOLS)
    containers = tuple(check_tool(probe, tool, required=False) for tool in CONTAINER_TOOLS)
    ok = all(c.status is not ToolStatus.MISSING for c in required) and any(
        c.status is not ToolStatus.MISSING for c in containers
    )
    found = required + containers
    if running_version is not None:
        found += (check_agentflow(probe, running_version),)
    return DoctorReport(found, ok)
