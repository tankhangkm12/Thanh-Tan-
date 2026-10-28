"""Semgrep rules, fetched at run time into a per-user cache and never stored in this repository.

The Semgrep Registry rules are under the Semgrep Rules License v1.0, which allows internal use only and does
not allow distributing the rules. So they are downloaded on the machine that scans, into a folder outside any
repository, and mounted read-only into the Semgrep container.
"""

import os
import re
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from agentflow.constants import (
    APP_CACHE_DIR,
    CACHE_DIR_ENV,
    ENCODING,
    FETCH_TIMEOUT_SECONDS,
    SEMGREP_RULES_DIR,
    SEMGREP_RULES_MAX_AGE_SECONDS,
    SEMGREP_RULES_URL,
    ExitCode,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic

RULES_SUFFIX = ".yaml"
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
USER_AGENT = "agentflow"


@runtime_checkable
class RuleFetcher(Protocol):
    def fetch(self, ruleset: str) -> str:
        """YAML text of ``ruleset`` (for example ``p/default``); raises ``OSError`` when it cannot be fetched."""
        ...


class HttpRuleFetcher:
    def fetch(self, ruleset: str) -> str:
        request = urllib.request.Request(SEMGREP_RULES_URL.format(ruleset=ruleset), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URL
            return response.read().decode(ENCODING)


def default_cache_dir(environ: dict[str, str] | None = None, windows: bool | None = None) -> Path:
    env = os.environ if environ is None else environ
    if env.get(CACHE_DIR_ENV):
        return Path(env[CACHE_DIR_ENV])
    on_windows = os.name == "nt" if windows is None else windows
    if on_windows and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / APP_CACHE_DIR / "cache"
    base = Path(env["XDG_CACHE_HOME"]) if env.get("XDG_CACHE_HOME") else Path.home() / ".cache"
    return base / APP_CACHE_DIR


def ruleset_file(directory: Path, ruleset: str) -> Path:
    return directory / f"{_UNSAFE.sub('_', ruleset)}{RULES_SUFFIX}"


def ensure_rules(
    cache_dir: Path,
    rulesets: Sequence[str],
    repo: Path,
    fetcher: RuleFetcher,
    now: float | None = None,
    warn=lambda message: None,
) -> Path:
    """Make sure every ruleset is cached and fresh enough; return the folder to mount into the container."""
    directory = cache_dir / SEMGREP_RULES_DIR
    if _inside(directory, repo):
        raise AgentflowError(
            f"the rule cache {directory} is inside the repository; Semgrep Registry rules must not be committed. "
            f"Point {CACHE_DIR_ENV} somewhere else",
            ExitCode.INVALID_CONFIG,
        )
    directory.mkdir(parents=True, exist_ok=True)
    current = time.time() if now is None else now
    for ruleset in rulesets:
        path = ruleset_file(directory, ruleset)
        fresh = path.is_file() and current - path.stat().st_mtime < SEMGREP_RULES_MAX_AGE_SECONDS
        if fresh:
            continue
        try:
            write_text_atomic(path, fetcher.fetch(ruleset))
        except OSError as exc:
            if not path.is_file():
                raise AgentflowError(
                    f"cannot download the Semgrep ruleset '{ruleset}' and there is no cached copy: {exc}",
                    ExitCode.SCAN_FAILED,
                ) from exc
            warn(f"could not refresh the Semgrep ruleset '{ruleset}' ({exc}); using the cached copy")
    return directory


def _inside(directory: Path, repo: Path) -> bool:
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        return False
    return True
