"""Secret scanning of staged changes with Gitleaks, run in a Docker or Podman container.

A container engine that is missing or not running is a hard error: nothing gets
committed without a scan.
"""

from pathlib import Path

from agentflow.constants import (
    CONTAINER_REPO_DIR,
    CONTAINER_TOOLS,
    ENGINE_INFO_ARG,
    GITLEAKS_IMAGE,
    GITLEAKS_LEAKS_EXIT_CODE,
    INSTALL_URLS,
    SCAN_TIMEOUT_SECONDS,
    TOOL_TIMEOUT_SECONDS,
    ExitCode,
)
from agentflow.container import running_engine
from agentflow.errors import AgentflowError
from agentflow.interfaces import CommandRunner
from agentflow.models import ScanResult

READ_ONLY_MOUNT = "ro"
_MOUNT_SEPARATOR = ":"
# git in the container sees the mounted repository as owned by someone else; trust it explicitly.
SAFE_DIRECTORY_ENV = (
    "GIT_CONFIG_COUNT=1",
    "GIT_CONFIG_KEY_0=safe.directory",
    f"GIT_CONFIG_VALUE_0={CONTAINER_REPO_DIR}",
)
RUN_ARGS = ("run", "--rm")
VOLUME_FLAG = "--volume"
ENV_FLAG = "--env"
GITLEAKS_ARGS = (
    "git",
    "--staged",
    "--redact",
    "--verbose",
    "--no-banner",
    "--no-color",
    "--exit-code",
    str(GITLEAKS_LEAKS_EXIT_CODE),
)


def gitleaks_command(engine: str, repo: Path) -> list[str]:
    mount = _MOUNT_SEPARATOR.join((str(repo), CONTAINER_REPO_DIR, READ_ONLY_MOUNT))
    env = [arg for value in SAFE_DIRECTORY_ENV for arg in (ENV_FLAG, value)]
    return [engine, *RUN_ARGS, VOLUME_FLAG, mount, *env, GITLEAKS_IMAGE, *GITLEAKS_ARGS, CONTAINER_REPO_DIR]


class ContainerGitleaksScanner:
    """``SecretScanner`` using the first container engine that is installed and running."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def running_engine(self) -> str:
        return running_engine(self.runner)

    def scan_staged(self, repo: Path) -> ScanResult:
        result = self.runner.run(gitleaks_command(self.running_engine(), repo), repo, SCAN_TIMEOUT_SECONDS)
        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if result.returncode == 0:
            return ScanResult(clean=True, output=output)
        if result.returncode == GITLEAKS_LEAKS_EXIT_CODE:
            return ScanResult(clean=False, output=output)
        raise AgentflowError(
            f"the secret scan could not run (exit {result.returncode}); nothing was committed:\n{output}",
            ExitCode.SCAN_FAILED,
        )
