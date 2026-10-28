# /// script
# requires-python = ">=3.12"
# ///
"""Install or update everything this repository gives a machine, in one command: the `agentflow` engine and the plugins of
Claude Code and Antigravity. It never touches a project.

    uv run tools/install.py                  # install or update agentflow, dev-core in Claude Code and in Antigravity
    uv run tools/install.py --backend        # also dev-backend
    uv run tools/install.py --design         # also design-core and design-architecture
    uv run tools/install.py --only claude    # only Claude Code (or: agy); agentflow is always installed
    uv run tools/install.py --check          # change nothing: say what is installed and what is out of date

Run it from anywhere; it finds the repository from its own place. After `git pull`, run it again.

Python: agentflow is installed with a Python that uv manages (3.12, downloaded once by uv), never the one on PATH. On
Windows `python` is often only the Microsoft Store shortcut ("Python was not found"), or a tool environment still points
to a Python that was removed; a uv-managed Python avoids both.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FOUNDATION = REPO / "foundation"
MARKETPLACE = "thanh-tan-plugins"
PYTHON_VERSION = "3.12"
ENCODING = "utf-8"
TIMEOUT_SECONDS = 900
CLAUDE, AGY = "claude", "agy"
CORE, BACKEND, DESIGN_CORE, DESIGN_ARCHITECTURE = "dev-core", "dev-backend", "design-core", "design-architecture"
PLUGIN_DIRS = {
    CORE: REPO / "families" / "software-dev" / "core",
    BACKEND: REPO / "families" / "software-dev" / "backend",
    DESIGN_CORE: REPO / "families" / "design-system" / "core",
    DESIGN_ARCHITECTURE: REPO / "families" / "design-system" / "design-architecture",
}
# What Windows says when a running program (an open agy or Claude Code session) keeps a file open.
IN_USE_MARKERS = ("being used by another process", "Access is denied", "os error 5", "os error 32")
IN_USE_HINT = "a running Claude Code or Antigravity session keeps its files open: close those sessions, then run this again"
UNKNOWN_FLAG_MARKERS = ("unexpected argument", "unrecognized", "unknown option")
VERSION_PATTERN = re.compile(r"(\d+\.\d+\.\d+)")


@dataclass(frozen=True)
class Result:
    returncode: int
    output: str


class Runner:
    """Runs the programs; tests give a fake one."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, args: Sequence[str]) -> Result:
        # The full path, so a `.cmd` shim (claude, agy on Windows) starts without a shell.
        program = self.which(args[0]) or args[0]
        try:
            done = subprocess.run(
                [program, *args[1:]], capture_output=True, text=True, encoding=ENCODING, errors="replace",
                timeout=TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return Result(127, str(exc))
        return Result(done.returncode, (done.stdout or "") + (done.stderr or ""))


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""
    warning: bool = False  # not a failure: something optional is missing


# ------------------------------------------------------------------ versions in the repository


def repo_version(name: str) -> str:
    if name == "agentflow":
        text = (FOUNDATION / "pyproject.toml").read_text(encoding=ENCODING)
        found = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        return found.group(1) if found else "?"
    manifest = PLUGIN_DIRS[name] / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding=ENCODING)).get("version", "?")
    except (OSError, ValueError):
        return "?"


def in_use(output: str) -> bool:
    return any(marker in output for marker in IN_USE_MARKERS)


def tail(output: str, lines: int = 6) -> str:
    return "\n".join(output.strip().splitlines()[-lines:])


# ------------------------------------------------------------------ steps


def check_prerequisites(runner: Runner, clis: Sequence[str]) -> list[Step]:
    steps = [Step(f"{name} on PATH", runner.which(name) is not None, "" if runner.which(name) else f"install {name} first") for name in ("uv", "git")]
    if runner.which("docker") is None:
        steps.append(Step("docker", False, "not found: `agentflow commit` needs Docker Desktop (or Podman) to scan for secrets", warning=True))
    else:
        info = runner.run(["docker", "info"])
        steps.append(Step("docker engine running", info.returncode == 0, "" if info.returncode == 0 else "start Docker Desktop", warning=info.returncode != 0))
    for cli in clis:
        if runner.which(cli) is None:
            steps.append(Step(f"{cli} on PATH", False, "not found: its plugins are skipped", warning=True))
    return steps


def install_agentflow(runner: Runner) -> Step:
    python = runner.run(["uv", "python", "install", PYTHON_VERSION])
    if python.returncode != 0:
        return Step(f"uv-managed Python {PYTHON_VERSION}", False, tail(python.output))
    command = ["uv", "tool", "install", "--force", "--reinstall", "--python", PYTHON_VERSION, "--managed-python", str(FOUNDATION)]
    done = runner.run(command)
    if done.returncode != 0 and any(marker in done.output for marker in UNKNOWN_FLAG_MARKERS):
        # uv older than 0.7 has no --managed-python; the Python it just installed is still the one picked first.
        done = runner.run([part for part in command if part != "--managed-python"])
    if done.returncode != 0:
        return Step("install agentflow", False, IN_USE_HINT if in_use(done.output) else tail(done.output))
    return Step("install agentflow", True, f"Python {PYTHON_VERSION} managed by uv")


def check_agentflow(runner: Runner) -> Step:
    wanted = repo_version("agentflow")
    if runner.which("agentflow") is None:
        return Step("agentflow on PATH", False, "not found: run `uv tool update-shell`, then open a new terminal")
    done = runner.run(["agentflow", "--version"])
    found = VERSION_PATTERN.search(done.output)
    have = found.group(1) if found else "?"
    if done.returncode != 0:
        return Step("agentflow runs", False, tail(done.output) + "\n(a broken tool environment: run this script without --check)")
    return Step(f"agentflow {wanted}", have == wanted, f"PATH has {have}" if have != wanted else "")


def claude_listing(runner: Runner) -> dict[str, dict]:
    done = runner.run([CLAUDE, "plugin", "list", "--json"])
    if done.returncode != 0:
        return {}
    start = min((done.output.find(mark) for mark in "[{" if mark in done.output), default=0)  # skip a notice before the JSON
    try:
        data = json.loads(done.output[start:])
    except ValueError:
        return {}
    if isinstance(data, dict):
        return data
    return {item.get("id", ""): item for item in data if isinstance(item, dict)}


def install_claude(runner: Runner, plugins: Sequence[str]) -> list[Step]:
    marketplaces = runner.run([CLAUDE, "plugin", "marketplace", "list"])
    if MARKETPLACE in marketplaces.output:
        done = runner.run([CLAUDE, "plugin", "marketplace", "update", MARKETPLACE])
    else:
        done = runner.run([CLAUDE, "plugin", "marketplace", "add", str(REPO)])
    steps = [Step(f"Claude Code marketplace {MARKETPLACE}", done.returncode == 0, "" if done.returncode == 0 else tail(done.output))]
    if done.returncode != 0:
        return steps
    listed = claude_listing(runner)
    for name in plugins:
        plugin_id = f"{name}@{MARKETPLACE}"
        verb = "update" if plugin_id in listed else "install"
        done = runner.run([CLAUDE, "plugin", verb, plugin_id])
        detail = "" if done.returncode == 0 else (IN_USE_HINT if in_use(done.output) else tail(done.output))
        steps.append(Step(f"Claude Code {verb} {name}", done.returncode == 0, detail))
    return steps


def check_claude(runner: Runner, plugins: Sequence[str]) -> list[Step]:
    listed = claude_listing(runner)
    steps = []
    for name in plugins:
        entry = listed.get(f"{name}@{MARKETPLACE}")
        wanted = repo_version(name)
        if entry is None:
            steps.append(Step(f"Claude Code {name}", False, "not installed"))
            continue
        have = entry.get("version", "?")
        enabled = entry.get("enabled", True)
        problem = "disabled" if not enabled else (f"has {have}, the repository has {wanted}" if have != wanted else "")
        steps.append(Step(f"Claude Code {name} {wanted}", not problem, problem))
    return steps


def install_agy(runner: Runner, plugins: Sequence[str]) -> list[Step]:
    steps = []
    for name in plugins:
        done = runner.run([AGY, "plugin", "install", str(PLUGIN_DIRS[name])])
        detail = "" if done.returncode == 0 else (IN_USE_HINT if in_use(done.output) else tail(done.output))
        steps.append(Step(f"Antigravity install {name}", done.returncode == 0, detail))
    return steps


def check_agy(runner: Runner, plugins: Sequence[str]) -> list[Step]:
    listing = runner.run([AGY, "plugin", "list"]).output
    steps = []
    for name in plugins:
        found = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", listing) is not None
        steps.append(Step(f"Antigravity {name}", found, "" if found else "not installed"))
    return steps


# ------------------------------------------------------------------ main


def plan(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    plugins = [CORE]
    if args.backend:
        plugins.append(BACKEND)
    if args.design:
        plugins += [DESIGN_CORE, DESIGN_ARCHITECTURE]
    clis = [CLAUDE, AGY] if args.only is None else [args.only]
    return plugins, clis


def run(args: argparse.Namespace, runner: Runner) -> list[Step]:
    plugins, clis = plan(args)
    steps = check_prerequisites(runner, clis)
    if not all(step.ok or step.warning for step in steps):
        return steps
    if not args.check:
        installed = install_agentflow(runner)
        steps.append(installed)
        if not installed.ok:
            return steps
    steps.append(check_agentflow(runner))
    for cli in clis:
        if runner.which(cli) is None:
            continue
        if not args.check:
            steps += install_claude(runner, plugins) if cli == CLAUDE else install_agy(runner, plugins)
        steps += check_claude(runner, plugins) if cli == CLAUDE else check_agy(runner, plugins)
    return steps


def report(steps: Sequence[Step], check: bool) -> int:
    for step in steps:
        mark = "ok  " if step.ok else ("warn" if step.warning else "FAIL")
        print(f"[{mark}] {step.name}")
        for line in step.detail.splitlines() if step.detail else []:
            print(f"       {line}")
    failed = [step for step in steps if not step.ok and not step.warning]
    if failed:
        print(f"\n{len(failed)} problem(s).", "Run without --check to install or update." if check else "")
        return 1
    print("\nAll good." + ("" if check else " Open a new Claude Code / Antigravity session to load the new plugins."))
    print("Projects are not touched: in each project the next `agentflow` command moves an old .agentflow/ to .ThanhTan/, "
          "and `agentflow doctor` says when `agentflow workflow sync` is needed.")
    return 0


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install or update agentflow and the plugins of this repository.")
    parser.add_argument("--check", action="store_true", help="change nothing; say what is installed and what is out of date")
    parser.add_argument("--only", choices=(CLAUDE, AGY), help="only this CLI (agentflow is always handled)")
    parser.add_argument("--backend", action="store_true", help="also dev-backend")
    parser.add_argument("--design", action="store_true", help="also design-core and design-architecture")
    args = parser.parse_args(argv)
    return report(run(args, runner or Runner()), args.check)


if __name__ == "__main__":
    sys.exit(main())
