# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""End-to-end smoke test of the installed `agentflow` on a throw-away git repository.

    uv run tools/smoke.py

Everything happens in a temporary directory; no other repository is touched. Needs `agentflow` on PATH
(see the README), git, and a running Docker or Podman engine for the Gitleaks scan.
"""

import json
import os
import secrets
import shutil
import stat
import string
import subprocess
import sys
import tempfile
from pathlib import Path

from smoke_support import (  # noqa: F401 - re-exported for the other smoke scripts
    AGENTFLOW,
    ENCODING,
    FAKE_TOKEN_PREFIX,
    STEP_TIMEOUT,
    Failure,
    Session,
    _make_writable_and_retry,
    expect,
    fake_token_body,
    run,
)

WORKFLOW = Path(__file__).resolve().parents[1] / "families" / "software-dev" / "core" / "workflow.yaml"
MAIN, DEVELOP = "main", "develop"
TASK_ID = "T-001"
PLAN = (
    "### C1 - Add a greeting\n- role: implementer\n- files: greeting.txt\n"
    "- done-when: `test -f greeting.txt`\n- docs: không có — a one-line text file\n"
)
REPLAN = "# Replan\n\n## Mục roadmap đã hoàn thành\nkhông có\n\n## Đề xuất cải tiến quy trình\nkhông có\n"


def main() -> int:
    if shutil.which(AGENTFLOW) is None or shutil.which("git") is None:
        print("git must be on PATH", file=sys.stderr)
        return 2
    base = Path(tempfile.mkdtemp(prefix="agentflow-smoke-"))
    repo = base / "sample"
    repo.mkdir()
    env = {"GIT_CEILING_DIRECTORIES": str(base)}
    os.environ.update(env)
    os.environ["AGENTFLOW_HOME"] = str(base / "user-home")  # nothing here may touch the real ~/.agentflow
    try:
        s = Session(repo)
        s.git("init", "-q", "-b", MAIN)
        for key, value in {"user.name": "Smoke", "user.email": "smoke@example.invalid", "commit.gpgsign": "false"}.items():
            s.git("config", key, value)
        (repo / "README.md").write_text("sample\n", encoding=ENCODING)
        s.git("add", "README.md")
        s.git("commit", "-q", "-m", "initial")
        s.git("switch", "-q", "-c", DEVELOP)

        s.af("init", "--workflow", str(WORKFLOW))
        s.af("task", "new", "Add a greeting", "--type", "feature")
        branch = s.git("branch", "--show-current")
        expect(branch == f"feature/{TASK_ID}-add-a-greeting", "task branch name", branch)

        s.af("report", "--step", "confirm", stdin="# Confirmed\n")
        s.af("task", "advance", "--result", "pass")
        s.af("task", "advance", "--result", "pass", ok=False)  # confirm now waits for approval
        checklist = repo / ".agentflow" / "tasks" / TASK_ID / "approve-confirm.md"
        expect(checklist.is_file(), "the confirm checklist is written when the step waits for approval", str(checklist))
        refused = s.af("task", "approve", ok=False)  # nothing is ticked yet
        expect("K1" in refused.stderr, "approve names the boxes still open", refused.stderr)
        s.af("report", "--step", "confirm", stdin="# Changed my mind\n", ok=False)  # the approved report is final
        s.af("report", "--step", "plan", stdin="# Too early\n", ok=False)  # only the current step can be reported
        s.approve()  # confirm -> plan
        bad = s.af("plan", "check", "--file", str(repo / "README.md"), ok=False)
        expect("no checklist items" in bad.stdout, "plan check rejects a README as a plan", bad.stdout)
        s.af("task", "advance", "--result", "pass", ok=False)  # no plan report yet: the plan-valid gate refuses
        s.af("report", "--step", "plan", stdin=PLAN)
        s.af("plan", "check")
        s.af("task", "advance", "--result", "pass")
        s.approve()  # plan -> implement

        (repo / "greeting.txt").write_text("hello\n", encoding=ENCODING)
        s.git("add", "greeting.txt")
        direct = json.loads(s.af("guard", stdin=json.dumps({"command": "git commit -m x", "cwd": str(repo)})).stdout)
        expect(direct["rule"] == "direct-commit", "guard blocks a direct git commit in the project", str(direct))
        done = s.af("commit", "add greeting", "--item", "C1")
        expect(s.git("log", "-1", "--format=%s") == f"{TASK_ID}: add greeting", "commit has the task prefix")
        expect("committed" in done.stdout, "commit reports success")

        s.af("task", "advance", "--result", "pass")  # implement -> test
        s.af("task", "advance", "--result", "fail")  # test fails -> back to implement, round 1
        status = s.af("status").stdout
        expect("step 'implement'" in status and "rework rounds: 1/3" in status, "fail goes back to implement", status)
        for _ in range(2):  # implement, test
            s.af("task", "advance", "--result", "pass")
        s.af("task", "advance", "--result", "pass", ok=False)  # security: no scan results yet, the scans-clean gate refuses
        scan = s.af("scan")  # Semgrep, Trivy, Gitleaks in containers
        expect("semgrep: " in scan.stdout and "trivy: " in scan.stdout and "gitleaks: " in scan.stdout, "scan runs three tools", scan.stdout)
        s.af("task", "advance", "--result", "pass")  # security
        s.af("report", "--step", "review", stdin="# Review\nNo findings.\n\n## Đề xuất cập nhật hồ sơ\nkhông có\n")
        s.af("task", "advance", "--result", "pass")  # review passes -> awaiting approval
        s.approve()
        state = json.loads((repo / ".agentflow" / "state.json").read_text(encoding=ENCODING))
        expect(state["tasks"][0]["status"] == "done" and state["active_task_id"] is None, "task is done after review approval")
        tag = f"agentflow/{TASK_ID}/approved"
        expect(s.git("tag", "-l", tag) == tag and s.git("cat-file", "-t", tag) == "tag", "approval tag is annotated")
        summary = (repo / ".agentflow" / "tasks" / TASK_ID / "summary.md").read_text(encoding=ENCODING)
        expect("### C1 - Add a greeting" in summary, "summary.md lists the plan item")
        delta = (repo / ".agentflow" / "tasks" / TASK_ID / "spec-delta.md").read_text(encoding=ENCODING)
        expect("- A greeting.txt" in delta and "T-001: add greeting" in delta, "the seal wrote a spec delta from git")
        expect(s.af("replan", "status").stdout.splitlines()[0] == "replan: pending", "a finished task waits for its replan")
        s.af("replan", "write", stdin=REPLAN)
        expect(s.af("replan", "status").stdout.splitlines()[0] == "replan: proposed", "the replan is only proposed")
        asked = json.loads(s.af("guard", stdin=json.dumps({"command": "agentflow replan done", "cwd": str(repo)})).stdout)
        expect(asked["decision"] == "deny", "guard keeps `replan done` for a person", str(asked))
        s.af("replan", "done")  # what a person runs after reading replan.md
        expect(s.af("replan", "status").stdout.splitlines()[0] == "replan: done", "a person closed the replan")

        s.af("task", "new", "Second task")
        s.af("task", "cancel")

        # A finding that blocks: Semgrep ERROR in a changed file stops the security step.
        s.af("task", "new", "Risky code")
        s.af("task", "advance", "--result", "pass")
        s.approve()
        s.af("report", "--step", "plan", stdin=PLAN.replace("greeting.txt", "risky.py"))
        s.af("task", "advance", "--result", "pass")
        s.approve()
        (repo / "risky.py").write_text("import subprocess\n\n\ndef run(cmd):\n    subprocess.call(cmd, shell=True)\n", encoding=ENCODING)
        s.git("add", "risky.py")
        s.af("commit", "add risky code", "--item", "C1")
        s.af("task", "advance", "--result", "pass")  # implement
        s.af("task", "advance", "--result", "pass")  # test
        blocked = s.af("scan", ok=False)
        expect("semgrep: blocked" in blocked.stdout, "Semgrep ERROR blocks the scan", blocked.stdout)
        s.af("task", "advance", "--result", "pass", ok=False)
        s.af("task", "cancel")
        s.git("switch", "-q", DEVELOP)

        secret_file = repo / "leak.txt"
        s.af("task", "new", "Leak check")
        secret_file.write_text(f'token = "{FAKE_TOKEN_PREFIX}{fake_token_body()}"\n', encoding=ENCODING)
        s.git("add", "leak.txt")
        before = s.git("rev-parse", "HEAD")
        s.af("commit", "should be blocked", ok=False)
        expect(s.git("rev-parse", "HEAD") == before, "a staged secret blocks the commit")
        s.git("reset", "-q")
        secret_file.unlink()
        s.af("task", "cancel")
        s.git("switch", "-q", DEVELOP)

        guard = json.loads(s.af("guard", stdin=json.dumps({"command": "git push origin develop", "cwd": str(repo)})).stdout)
        expect(guard["decision"] == "deny" and guard["rule"] == "push", "guard blocks git push", str(guard))
        allowed = json.loads(s.af("guard", stdin=json.dumps({"command": "git status", "cwd": str(repo)})).stdout)
        expect(allowed["decision"] == "allow", "guard allows git status")
        merge = json.loads(s.af("guard", stdin=json.dumps({"command": "git merge feature/x", "cwd": str(repo)})).stdout)
        expect(merge["rule"] == "protected-branch", "guard blocks merging on develop")

        claude = s.af("hook", "pre-tool", "--cli", "claude", stdin=json.dumps({"cwd": str(repo), "tool_input": {"command": "git push"}}))
        expect(json.loads(claude.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny", "claude pre-tool hook denies push")
        agy = s.af(
            "hook",
            "pre-tool",
            "--cli",
            "antigravity",
            stdin=json.dumps({"workspacePaths": [str(repo)], "toolCall": {"name": "run_command", "args": {"CommandLine": "git push"}}}),
        )
        expect(json.loads(agy.stdout)["decision"] == "deny", "antigravity pre-tool hook denies push")
        summary = s.af("hook", "session-start", "--cli", "claude", stdin=json.dumps({"cwd": str(repo)}))
        expect("agentflow workspace found" in summary.stdout, "session-start hook prints the summary")

        from conventions_smoke import conventions_flow

        conventions_flow(s, base, repo)

        bare = base / "no-workspace"
        bare.mkdir()
        run(["git", "init", "-q"], bare)
        silent = run([AGENTFLOW, "hook", "pre-tool", "--cli", "claude"], bare, json.dumps({"cwd": str(bare), "tool_input": {"command": "git push"}}))
        expect(silent.returncode == 0 and silent.stdout == "", "hooks do nothing without .agentflow/")

        print("\nsmoke test passed")
        return 0
    except Failure as exc:
        print(f"\nsmoke test FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(base, onerror=_make_writable_and_retry)


if __name__ == "__main__":
    sys.exit(main())
