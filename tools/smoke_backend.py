# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""End-to-end smoke test of dev-core + dev-backend on a throw-away sample project.

    uv run tools/smoke_backend.py                  # the whole task flow (Docker needed)
    uv run tools/smoke_backend.py --until plan     # stop after the plan checks (or: implement)
    uv run tools/smoke_backend.py --install-check  # also (re)install both plugins and check what the CLIs load

Everything happens in a temporary directory; no other repository is touched. Needs `agentflow` on PATH, git, and a
running Docker engine (PostgreSQL, the sample service, Semgrep, Trivy, Gitleaks, Squawk, Schemathesis).
The first run downloads images and the Semgrep rules / Trivy database, so it takes a while.
"""

import argparse
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import sample_backend as sample
from conventions_smoke import (
    REVIEW_REPORT,
    SKIPPING_REPORT,
    active_task,
    agents_cannot_decide_or_write,
    person_assets,
    setup_through_mcp,
)
from smoke import AGENTFLOW, Failure, Session, _make_writable_and_retry, expect, run

ENCODING = "utf-8"
REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "families" / "software-dev" / "core"
BACKEND = REPO / "families" / "software-dev" / "backend"
WORKFLOW = CORE / "workflow.yaml"
EXTENSION = BACKEND / "extension.yaml"
README = REPO / "README.md"
MARKETPLACE = "thanh-tan-plugins"
CORE_NAME, BACKEND_NAME = "dev-core", "dev-backend"
CORE_VERSION, BACKEND_VERSION = "0.4.0", "0.2.0"
TASK_ID = "T-001"
USAGE_ERROR_CODES = {"plan_invalid": 24, "gate_failed": 25, "scan_blocked": 27}
MANDATORY_ASK = ("task approve", "task cancel")
READY_TIMEOUT_SECONDS = 90
IN_USE_MESSAGE = "being used by another process"
AGY_PLUGINS = Path.home() / ".gemini" / "config" / "plugins"
CLI_TIMEOUT_SECONDS = 600


class Stage:
    PLAN = "plan"
    IMPLEMENT = "implement"
    ALL = "all"


# ----------------------------------------------------------------- helpers


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def sh(command: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a project command the way an agent would: as given, in the project directory."""
    done = subprocess.run(
        shlex.split(command), cwd=cwd, capture_output=True, text=True, encoding=ENCODING, timeout=CLI_TIMEOUT_SECONDS, check=False
    )
    if check:
        expect(done.returncode == 0, f"$ {command[:90]}", done.stdout + done.stderr)
    return done


def af_code(session: Session, code: int, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    done = run([AGENTFLOW, *args], session.repo, stdin)
    expect(done.returncode == code, f"agentflow {' '.join(args)[:70]} -> exit {done.returncode} (wanted {code})", done.stdout + done.stderr)
    return done


def wait_for(url: str) -> None:
    deadline = time.time() + READY_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise Failure(f"{url} did not answer within {READY_TIMEOUT_SECONDS} seconds")


def readme_permissions() -> dict:
    blocks = re.findall(r"```json\n(.*?)```", README.read_text(encoding=ENCODING), flags=re.S)
    return next(json.loads(block) for block in blocks if '"permissions"' in block)


def missing_ask_rules(settings_path: Path) -> list[str]:
    """The mandatory `ask` rules (task approve, task cancel) that a project's Claude Code settings lack."""
    try:
        data = json.loads(settings_path.read_text(encoding=ENCODING))
        asked = " ".join(data.get("permissions", {}).get("ask", []))
    except (OSError, json.JSONDecodeError):
        asked = ""
    return [command for command in MANDATORY_ASK if f"agentflow {command}" not in asked]


INTERFACE_AFTER_IMPLEMENTATION = (
    f"\n### C3 - Declare the server interface\n- role: implementer\n- kind: interface\n- files: {sample.SERVER_FILE}\n"
    "- done-when: `true`\n- docs: không có — a declaration\n"
)
QUESTION = (
    "\n## Chưa có quy ước\n\n### Q1 - Plural or singular route names?\n- ask: No convention says how routes are named.\n"
    "- options: /items, /item\n- needed-by: C2\n"
)


def plan_text(migration_role: str, up: str, down_note: str, extra: str = "") -> str:
    return (
        f"### C1 - Create the items table\n- role: {migration_role}\n- kind: other\n- files: {sample.UP_FILE}, {sample.DOWN_FILE}\n"
        f"- done-when: `{up}` then {down_note}, all succeed\n- docs: https://www.postgresql.org/docs/16/sql-createtable.html\n\n"
        f"### C2 - Expose GET /items\n- role: implementer\n- kind: implement\n- files: {sample.SERVER_FILE}, {sample.SPEC_FILE}, {sample.CHECK_FILE}\n"
        "- done-when: `python tests/check_items.py` answers ok against the running service\n"
        "- docs: https://spec.openapis.org/oas/v3.0.3\n" + extra
    )


# -------------------------------------------------------------------- flow


def task_flow(s: Session, project: str, port: int, until: str) -> None:
    repo = s.repo
    compose = f"docker compose -p {project}"
    migrate = f"{compose} exec -T db psql -U app -d app -v ON_ERROR_STOP=1 -f /migrations/"
    up, down = f"{migrate}0001_items.up.sql", f"{migrate}0001_items.down.sql"
    url = f"http://localhost:{port}"
    settings = {
        "db.engine": "postgresql",
        "migrations_dir": sample.MIGRATIONS_DIR,
        "migrations_lint_glob": f"{sample.MIGRATIONS_DIR}/*.up.sql",
        "migrate_up_command": up,
        "migrate_down_command": down,
        "test_command": "python tests/check_items.py",
        "openapi.spec": sample.SPEC_FILE,
        "openapi.url": url,
    }

    s.af("init", "--workflow", str(WORKFLOW))
    added = s.af("ext", "add", str(EXTENSION))
    expect("roles: db-engineer" in added.stdout and "squawk" in added.stdout and "schemathesis" in added.stdout, "ext add lists role and tools", added.stdout)
    af_code(s, 29, "config", "check")  # settings still missing
    for key, value in settings.items():
        s.af("config", "set", f"backend.{key}", value)
    s.af("config", "check")

    # --- conventions: the scout writes them through MCP, the person confirms and answers
    setup_through_mcp(repo)
    store = person_assets(s, repo.parent, repo)
    agents_cannot_decide_or_write(s, repo)

    s.af("task", "new", "List items", "--type", "feature")
    task_id = active_task(repo)  # the probe task of the setup used T-001
    s.af("report", "--step", "confirm", stdin="# Confirmed\nAdd GET /items backed by an items table.\n")
    s.af("task", "advance", "--result", "pass")
    s.approve()

    # --- the plan: wrong role and missing down command are refused, a good plan passes
    wrong_role = plan_text("implementer", up, f"`{down}`")
    s.af("report", "--step", "plan", stdin=wrong_role)
    refused = af_code(s, 24, "plan", "check")
    expect("only db-engineer may" in refused.stdout, "an implementer item on migrations is refused", refused.stdout)
    af_code(s, 25, "task", "advance", "--result", "pass")
    s.af("report", "--step", "plan", stdin=plan_text("db-engineer", up, "roll back by hand"))
    refused = af_code(s, 24, "plan", "check")
    expect(f"done-when must contain `{down}`" in refused.stdout, "a migration without the down command is refused", refused.stdout)
    s.af("report", "--step", "plan", stdin=plan_text("dba", up, f"`{down}`"))
    expect("unknown role 'dba'" in af_code(s, 24, "plan", "check").stdout, "an unregistered role is refused")
    s.af("report", "--step", "plan", stdin=plan_text("db-engineer", up, f"`{down}` and `{up}` again"))
    s.af("report", "--step", "plan", stdin=plan_text("db-engineer", up, f"`{down}`", INTERFACE_AFTER_IMPLEMENTATION))
    refused = af_code(s, 24, "plan", "check")
    expect("interface item C3" in refused.stdout, "an interface item after the implementation of the same file is refused", refused.stdout)
    s.af("report", "--step", "plan", stdin=plan_text("db-engineer", up, f"`{down}`", QUESTION))
    refused = af_code(s, 24, "plan", "check")
    expect("Q1" in refused.stdout, "an unanswered question blocks the plan", refused.stdout)
    af_code(s, 25, "task", "advance", "--result", "pass")
    s.af("decide", "--answer", "Q1", "--text", "Routes use plural nouns.", "--check", "review")
    s.af("plan", "check")
    s.af("task", "advance", "--result", "pass")
    s.approve()
    s.test_first()
    if until == Stage.PLAN:
        return

    # --- implement: the db-engineer item, with the migration really run up and down in the container
    sh(f"{compose} up -d --wait db", repo)
    sample.write_files(repo, {sample.UP_FILE: sample.MIGRATION_UP, sample.DOWN_FILE: sample.MIGRATION_DOWN})
    sh(up, repo)
    sh(down, repo)
    sh(up, repo)
    s.git("add", sample.UP_FILE, sample.DOWN_FILE)
    af_code(s, 24, "commit", "migration without an item")
    refused = af_code(s, 24, "commit", "migration under the implementer's item", "--item", "C2")
    expect("only db-engineer may" in refused.stderr, "the implementer's item cannot commit a migration", refused.stderr)
    s.af("commit", "create the items table", "--item", "C1")

    # --- the implementer item: the endpoint, the contract, and a check against the running service
    sample.write_files(
        repo, {sample.SERVER_FILE: sample.SERVER_WITH_ITEMS, sample.SPEC_FILE: sample.SPEC_WITH_ITEMS, sample.CHECK_FILE: sample.CHECK_ITEMS}
    )
    sh(f"{compose} up -d --build api", repo)
    wait_for(f"{url}/items")
    done = subprocess.run([sys.executable, str(repo / sample.CHECK_FILE)], capture_output=True, text=True, check=False)
    expect(done.returncode == 0 and "ok" in done.stdout, "tests/check_items.py passes against the service", done.stdout + done.stderr)
    s.git("add", sample.SERVER_FILE, sample.SPEC_FILE, sample.CHECK_FILE)
    s.af("commit", "list items", "--item", "C2")
    log = s.git("log", "--format=%s %(trailers:key=Plan-Item,valueonly,unfold)", "develop..HEAD").replace("\n\n", "\n")
    expect("create the items table" in log and "list items" in log, "both commits carry the task prefix", log)
    s.af("report", "--step", "implement", stdin="# Implemented\nC1 migration up/down verified, C2 endpoint checked.\n")
    s.af("task", "advance", "--result", "pass")
    if until == Stage.IMPLEMENT:
        return

    # --- test: Squawk lints the migration, Schemathesis checks the running service against the spec
    af_code(s, 25, "task", "advance", "--result", "pass")  # the extension's gate: scans have not run
    scan = s.af("scan")
    expect("squawk: clean" in scan.stdout and "schemathesis: clean" in scan.stdout, "Squawk and Schemathesis are clean", scan.stdout)
    s.af("report", "--step", "test", stdin="# Tests\ncheck_items passed; Squawk and Schemathesis clean.\n")
    s.af("task", "advance", "--result", "pass")

    # --- security: Semgrep, Trivy, Gitleaks
    scan = s.af("scan")
    for tool in ("semgrep", "semgrep-conventions", "trivy", "gitleaks"):
        expect(f"{tool}: " in scan.stdout and f"{tool}: blocked" not in scan.stdout, f"{tool} ran and does not block", scan.stdout)
    s.af("report", "--step", "security", stdin="# Security\nNo blocking findings.\n")
    s.af("task", "advance", "--result", "pass")

    # --- review and approval: tag and summary
    s.af("report", "--step", "review", stdin=SKIPPING_REPORT)
    af_code(s, 25, "task", "advance", "--result", "pass")  # the conventions are not answered
    s.af("report", "--step", "review", stdin=REVIEW_REPORT.replace("DC-02: đạt\n", "DC-02: đạt\nDC-03: đạt\n").replace("DC-03: đạt\n", ""))
    s.af("task", "advance", "--result", "pass")
    s.approve()
    expect((repo / ".agentflow" / "tasks" / task_id / "lessons" / "L1.md").is_file(), "the proposed lesson is a file a person can push")
    s.af("knowledge", "push", str(repo / ".agentflow" / "tasks" / task_id / "lessons" / "L1.md"))
    expect((store / "lessons" / "L1.md").is_file(), "a person pushed the lesson into their own store")
    tag = f"agentflow/{task_id}/approved"
    expect(s.git("tag", "-l", tag) == tag and s.git("cat-file", "-t", tag) == "tag", "the approval tag exists and is annotated")
    message = s.git("tag", "-l", "--format=%(contents)", tag)
    expect(task_id in message and "List items" in message and "Approved by: Smoke" in message, "the tag message has task, title, approver", message)
    expect(s.git("rev-parse", f"{tag}^{{commit}}") == s.git("rev-parse", s.git("branch", "--show-current")), "the tag is on the branch tip")
    summary = (repo / ".agentflow" / "tasks" / task_id / "summary.md").read_text(encoding=ENCODING)
    for needle in ("### C1 - Create the items table", "### C2 - Expose GET /items", "create the items table", "squawk: clean", "schemathesis: clean", "semgrep:", "trivy:", "gitleaks:", "https://spec.openapis.org"):
        expect(needle in summary, f"summary.md has '{needle}'", summary)

    # --- hooks: a direct git commit and a push are refused
    for command, phrase in (("git commit -m sneaky", "agentflow commit"), ("git push origin develop", "a person pushes")):
        payload = json.dumps({"cwd": str(repo), "tool_input": {"command": command}})
        out = json.loads(s.af("hook", "pre-tool", "--cli", "claude", stdin=payload).stdout)
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        expect(out["hookSpecificOutput"]["permissionDecision"] == "deny" and phrase in reason, f"hook denies '{command}'", reason)


# ----------------------------------------------------------- install check


def cli(*args: str, cwd: Path | None = None, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, input=stdin, capture_output=True, text=True, encoding=ENCODING, errors="replace",
        timeout=CLI_TIMEOUT_SECONDS, check=False,
    )


def warn_if_ask_rules_missing(settings_path: Path) -> bool:
    missing = missing_ask_rules(settings_path)
    for command in missing:
        print(f"WARNING: {settings_path} has no 'ask' rule for `agentflow {command}`: without it an agent can approve for itself")
    return not missing


def install_check(repo: Path, with_session: bool = True) -> None:
    """(Re)install dev-core and dev-backend into both CLIs from this repository, then check what they load.

    ``with_session`` also runs one short `claude -p` session (it needs the sample project's settings).
    """
    print("\n-- Claude Code")
    marketplaces = cli("claude", "plugin", "marketplace", "list")
    if MARKETPLACE not in marketplaces.stdout:
        added = cli("claude", "plugin", "marketplace", "add", str(REPO))
        expect(added.returncode == 0, "claude plugin marketplace add <repo>", added.stdout + added.stderr)
    else:
        cli("claude", "plugin", "marketplace", "update", MARKETPLACE)
    for name in (BACKEND_NAME, CORE_NAME):
        cli("claude", "plugin", "uninstall", f"{name}@{MARKETPLACE}")
    for name in (CORE_NAME, BACKEND_NAME):
        done = cli("claude", "plugin", "install", f"{name}@{MARKETPLACE}")
        expect(done.returncode == 0, f"claude plugin install {name}", done.stdout + done.stderr)
    listing = json.loads(cli("claude", "plugin", "list", "--json").stdout)
    installed = {item["id"]: item for item in listing} if isinstance(listing, list) else listing
    for name, version in ((CORE_NAME, CORE_VERSION), (BACKEND_NAME, BACKEND_VERSION)):
        entry = installed.get(f"{name}@{MARKETPLACE}")
        expect(entry is not None and entry.get("enabled", True) and entry.get("version") == version, f"Claude Code lists {name} {version} enabled", str(entry))

    if with_session:
        print("\n-- Claude Code loads skills, agents and the hook (one short `claude -p` call)")
        if not (repo / ".agentflow").is_dir():  # the hooks only act in a project that has a workspace
            Session(repo).af("init", "--workflow", str(WORKFLOW))
        ask_ok = warn_if_ask_rules_missing(repo / ".claude" / "settings.json")
        expect(ask_ok, "the sample project's settings have the mandatory ask rules")
        push_settings = repo.parent / "allow-push.json"
        push_settings.write_text(json.dumps({"permissions": {"allow": ["Bash(git push *)"]}}), encoding=ENCODING)
        prompt = "Use the Bash tool exactly once to run: git push origin develop\nThen reply with one short sentence saying what happened."
        done = cli("claude", "-p", "--output-format", "stream-json", "--verbose", "--settings", str(push_settings), "--permission-mode", "default", cwd=repo, stdin=prompt)
        events = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
        init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
        text = json.dumps(init)
        for needle in (f"{CORE_NAME}:start", f"{CORE_NAME}:setup", f"{CORE_NAME}:scout", f"{CORE_NAME}:continue", f"{BACKEND_NAME}:db-migration", f"{BACKEND_NAME}:contract-test", f"{CORE_NAME}:planner", f"{CORE_NAME}:implementer-fast", f"{CORE_NAME}:implementer-deep", f"{BACKEND_NAME}:db-engineer"):
            expect(needle in text, f"Claude Code loaded {needle}", text[:400])
        servers = {server["name"]: server.get("status") for server in init.get("mcp_servers", [])}
        expect(servers.get(f"plugin:{CORE_NAME}:agentflow") == "connected", "Claude Code connected dev-core's MCP server", str(servers))
        results = json.dumps([e for e in events if e.get("type") == "user"])
        expect("git push is blocked for agents" in results, "the dev-core hook blocked `git push` in a real session", results[:600])

    print("\n-- Antigravity")
    for name, path in ((BACKEND_NAME, BACKEND), (CORE_NAME, CORE)):
        cli("agy", "plugin", "uninstall", name)
    for name, path in ((CORE_NAME, CORE), (BACKEND_NAME, BACKEND)):
        done = cli("agy", "plugin", "install", str(path))
        if done.returncode != 0 and IN_USE_MESSAGE in done.stdout + done.stderr:
            # An open `agy` session keeps its MCP server inside the installed plugin folder, so the folder cannot be
            # replaced. Copy the new files over it instead (what the install does, without deleting first).
            print(f"WARNING: {name} is in use by an open Antigravity session; copying the new files over the installed folder")
            shutil.copytree(path, AGY_PLUGINS / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            continue
        expect(done.returncode == 0, f"agy plugin install {path.name}", done.stdout + done.stderr)
    plugins = cli("agy", "plugin", "list").stdout
    for name in (CORE_NAME, BACKEND_NAME):
        expect(name in plugins, f"agy lists {name}", plugins)
    agents = cli("agy", "agents").stdout
    for role in ("orchestrator", "planner", "implementer-fast", "implementer-deep", "tester", "security", "reviewer", "scout", "db-engineer"):
        expect(role in agents, f"agy agents lists {role}", agents)
    expect("hooks" in plugins.lower(), "agy shows hooks for dev-core", plugins)
    core_entry = plugins.split(f'"name": "{CORE_NAME}"')[1].split("}")[0]
    expect("mcpServers" in core_entry and "skills" in core_entry, "agy shows the MCP server and skills for dev-core", core_entry)


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--until", choices=[Stage.PLAN, Stage.IMPLEMENT, Stage.ALL], default=Stage.ALL)
    parser.add_argument("--install-check", action="store_true", help="also reinstall both plugins and check what the CLIs load")
    parser.add_argument("--only-install-check", action="store_true", help="skip the task flow")
    args = parser.parse_args(argv)
    for tool in (AGENTFLOW, "git", "docker"):
        if shutil.which(tool) is None:
            print(f"{tool} must be on PATH", file=sys.stderr)
            return 2
    base = Path(tempfile.mkdtemp(prefix="agentflow-backend-smoke-"))
    os.environ["GIT_CEILING_DIRECTORIES"] = str(base)
    os.environ["AGENTFLOW_HOME"] = str(base / "user-home")  # nothing here may touch the real ~/.agentflow
    port, project = free_port(), f"agentflow-smoke-{secrets.token_hex(3)}"
    os.environ["API_PORT"], os.environ["API_URL"] = str(port), f"http://localhost:{port}"
    repo: Path | None = None
    try:
        repo = sample.create_repo(base)
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps(readme_permissions(), indent=2), encoding=ENCODING)
        if not args.only_install_check:
            task_flow(Session(repo), project, port, args.until)
        if args.install_check or args.only_install_check:
            install_check(repo)
        print("\nbackend smoke test passed")
        return 0
    except (Failure, subprocess.TimeoutExpired) as exc:
        print(f"\nbackend smoke test FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if repo is not None:
            subprocess.run(["docker", "compose", "-p", project, "down", "-v", "--remove-orphans", "--rmi", "local"], cwd=repo, capture_output=True, check=False)
        shutil.rmtree(base, onerror=_make_writable_and_retry)


if __name__ == "__main__":
    sys.exit(main())
