"""Running a scan tool in a Docker or Podman container: engine detection and the `run` command line."""

from collections.abc import Sequence
from pathlib import Path

from agentflow.constants import (
    CONTAINER_REPO_DIR,
    CONTAINER_TOOLS,
    ENGINE_INFO_ARG,
    HOST_GATEWAY_NAME,
    INSTALL_URLS,
    SCAN_TIMEOUT_SECONDS,
    TOOL_TIMEOUT_SECONDS,
    ExitCode,
    NetworkMode,
)
from agentflow.errors import AgentflowError
from agentflow.globs import glob_regex, select_files  # noqa: F401 - re-exported
from agentflow.interfaces import CommandRunner
from agentflow.models import CommandResult
from agentflow.scan_types import MountSpec, ScanToolSpec

READ_ONLY_MOUNT = "ro"
READ_WRITE_MOUNT = "rw"
_MOUNT_SEPARATOR = ":"
RUN_ARGS = ("run", "--rm")
VOLUME_FLAG = "--volume"
ENV_FLAG = "--env"
NETWORK_FLAG = "--network"
ADD_HOST_FLAG = "--add-host"
WORKDIR_FLAG = "--workdir"


def running_engine(runner: CommandRunner) -> str:
    """Path of the first container engine that is installed and running; anything else is a hard error."""
    installed = [(tool, path) for tool in CONTAINER_TOOLS if (path := runner.which(tool)) is not None]
    if not installed:
        urls = ", ".join(INSTALL_URLS[tool] for tool in CONTAINER_TOOLS)
        raise AgentflowError(
            f"scanning needs Docker or Podman, and neither is installed ({urls})", ExitCode.MISSING_REQUIREMENT
        )
    for _tool, path in installed:
        if runner.run([path, ENGINE_INFO_ARG], None, TOOL_TIMEOUT_SECONDS).returncode == 0:
            return path
    names = ", ".join(tool for tool, _path in installed)
    raise AgentflowError(
        f"{names} is installed but its engine is not running; start it and retry (nothing was scanned or committed)",
        ExitCode.ENGINE_NOT_RUNNING,
    )


def mount_argument(source: str, target: str, readonly: bool) -> str:
    return _MOUNT_SEPARATOR.join((source, target, READ_ONLY_MOUNT if readonly else READ_WRITE_MOUNT))


def tool_command(
    engine: str,
    spec: ScanToolSpec,
    repo: Path,
    args: Sequence[str],
    mounts: Sequence[MountSpec],
) -> list[str]:
    """`docker run` for ``spec``: pinned image, repository read-only, network as the tool asks."""
    command = [engine, *RUN_ARGS]
    match spec.network:
        case NetworkMode.NONE:
            command += [NETWORK_FLAG, NetworkMode.NONE]
        case NetworkMode.HOST_GATEWAY:
            command += [ADD_HOST_FLAG, f"{HOST_GATEWAY_NAME}:{NetworkMode.HOST_GATEWAY}"]
        case NetworkMode.BRIDGE:
            pass
    if spec.mount_repo:
        command += [VOLUME_FLAG, mount_argument(str(repo), CONTAINER_REPO_DIR, True), WORKDIR_FLAG, CONTAINER_REPO_DIR]
    for mount in mounts:
        command += [VOLUME_FLAG, mount_argument(mount.source, mount.target, mount.readonly)]
    for value in spec.env:
        command += [ENV_FLAG, value]
    return [*command, spec.image, *args]


def run_tool(runner: CommandRunner, command: Sequence[str], repo: Path) -> CommandResult:
    return runner.run(command, repo, SCAN_TIMEOUT_SECONDS)
