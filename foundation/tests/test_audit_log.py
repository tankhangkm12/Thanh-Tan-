"""Chặng D-checklist (D4): the pre-tool hook keeps `.ThanhTan/audit.jsonl`, and `task approve` reads it.

A line is written for every tool call whose path or command *mentions* a protected name (state.json, STATE.md,
integrity.json, approve-*.md, locked-files.json, confirmations.json): `at`, `cli`, `tool`, `kind` (`write` for a file
tool, `shell` for a command), `target` (shortened) and `decision` (`allow`, `deny` or `ask`). Reads by the Read, Glob
and Grep tools are not logged: the hook is not asked about them. Logging never changes the reply and never fails the hook.
`task approve` refuses (exit 37) when a call that was *allowed* and *could write* touched the step's checklist or the
state after the checklist was written and after the last `state accept`. Could write: a file tool (kind `write`), or a
command with a redirect (`>`, `>>`; not `2>&1`), `tee`, `sed -i`, `cp`, `mv`, `rm`, `Set-Content`, `Out-File`,
`Add-Content`, or an interpreter (python, node, `bash -c`, `pwsh -c`, powershell) that names the path. Read-only
commands (cat, type, head, Get-Content, grep) never block an approval: the hashes are the main layer.
"""

import json
import re

import pytest
from checklist_helpers import (
    INTEGRITY_FAILED,
    CHECKLIST_REFUSED,
    approve,
    audit_path,
    checklist_path,
    go_to_awaiting,
    now,
    open_workspace,
    task_now,
    tick,
    workspace,
)
from sdd_helpers import run, say

from thanhtan.constants import CliKind, ExitCode, HookEvent
from thanhtan.git import GitBranchLookup
from thanhtan.hook import handle_hook

PROTECTED = ["state.json", "STATE.md", "integrity.json", "approve-confirm.md", "locked-files.json", "confirmations.json"]
LINE_KEYS = {"at", "cli", "tool", "kind", "target", "decision"}


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    return open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)


def hook(repo, cli=CliKind.CLAUDE, *, command=None, tool="Bash", path=None) -> str:
    if cli is CliKind.CLAUDE:
        tool_input = {"command": command} if command is not None else {"file_path": str(path), "content": "x"}
        payload = {"cwd": str(repo), "tool_name": tool, "tool_input": tool_input}
    else:
        args = {"CommandLine": command} if command is not None else {"TargetFile": str(path), "CodeContent": "x"}
        payload = {"workspacePaths": [str(repo)], "toolCall": {"name": tool, "args": args}}
    return handle_hook(HookEvent.PRE_TOOL, cli, json.dumps(payload), GitBranchLookup())


def decision_of(output: str) -> str:
    if not output:
        return "allow"
    data = json.loads(output)
    found = data.get("hookSpecificOutput", {}).get("permissionDecision") or data.get("decision")
    return "ask" if found == "force_ask" else found


def lines(repo) -> list[dict]:
    if not audit_path(repo).is_file():
        return []
    return [json.loads(line) for line in audit_path(repo).read_text(encoding="utf-8").splitlines() if line.strip()]


# ------------------------------------------------------------------ what is logged


@pytest.mark.parametrize("name", PROTECTED)
def test_a_command_that_mentions_a_protected_name_is_logged(repo, name):
    output = hook(repo, command=f"cat .ThanhTan/{name}")
    (line,) = lines(repo)
    assert set(line) == LINE_KEYS
    assert line["kind"] == "shell" and line["tool"] == "Bash" and line["cli"] == "claude"
    assert name in line["target"]
    assert line["decision"] == decision_of(output)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", line["at"])


def test_a_checklist_of_any_step_counts_as_protected(repo):
    hook(repo, command="cat .ThanhTan/tasks/T-007/approve-plan.md")
    hook(repo, command="cat .ThanhTan/tasks/T-007/approve-review.2.md")
    assert len(lines(repo)) == 2


@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit", "MultiEdit"])
def test_a_file_tool_aimed_at_a_protected_file_is_logged_with_its_decision(repo, tool):
    target = workspace(repo) / "tasks" / "T-001" / "approve-confirm.md"
    output = hook(repo, tool=tool, path=target)
    (line,) = lines(repo)
    assert line["kind"] == "write" and line["tool"] == tool
    assert "approve-confirm.md" in line["target"]
    assert line["decision"] == decision_of(output) == "deny", "the workspace stays closed to file tools"


def test_antigravity_calls_are_logged_with_their_own_tool_names(repo):
    hook(repo, CliKind.ANTIGRAVITY, command="type .ThanhTan\\state.json", tool="run_command")
    hook(repo, CliKind.ANTIGRAVITY, tool="write_to_file", path=workspace(repo) / "state.json")
    first, second = lines(repo)
    assert (first["cli"], first["tool"], first["kind"]) == ("antigravity", "run_command", "shell")
    assert (second["cli"], second["tool"], second["kind"], second["decision"]) == ("antigravity", "write_to_file", "write", "deny")


def test_powershell_commands_are_logged_as_shell(repo):
    hook(repo, tool="PowerShell", command="Get-Content .ThanhTan\\state.json")
    (line,) = lines(repo)
    assert line["kind"] == "shell" and line["tool"] == "PowerShell"


@pytest.mark.parametrize(
    "command",
    ["git status", "ls -la", "pytest -q", "thanhtan status", "cat src/state_machine.py", "echo statejson"],
)
def test_ordinary_commands_are_not_logged(repo, command):
    hook(repo, command=command)
    assert lines(repo) == []


def test_a_file_tool_on_an_ordinary_file_is_not_logged(repo):
    hook(repo, tool="Write", path=repo / "src" / "app.py")
    assert lines(repo) == []


def test_lines_are_appended_one_per_call_and_each_is_json(repo):
    for name in ("state.json", "integrity.json", "STATE.md"):
        hook(repo, command=f"cat .ThanhTan/{name}")
    raw = audit_path(repo).read_text(encoding="utf-8").splitlines()
    assert len(raw) == 3
    assert [json.loads(line)["target"].endswith(name) for line, name in zip(raw, ("state.json", "integrity.json", "STATE.md"))]


def test_a_long_command_is_shortened_but_keeps_the_protected_name_visible(repo):
    hook(repo, command="echo " + "x" * 5000 + " >> .ThanhTan/state.json")
    (line,) = lines(repo)
    assert len(line["target"]) <= 300
    assert "state.json" in line["target"]


def test_the_reply_of_the_hook_is_the_same_with_or_without_the_log(repo):
    denied = hook(repo, tool="Write", path=workspace(repo) / "state.json")
    assert decision_of(denied) == "deny"
    assert hook(repo, command="cat .ThanhTan/state.json") == "", "a plain read is let through, as before"


def test_a_project_without_a_workspace_gets_no_log(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    assert hook(outside, command="cat .ThanhTan/state.json") == ""
    assert not (outside / ".ThanhTan").exists()


# ------------------------------------------------------------------ the log cannot get in the way, or be wiped by an agent


def test_a_log_that_cannot_be_written_never_fails_the_hook(repo):
    audit_path(repo).mkdir()
    assert decision_of(hook(repo, tool="Write", path=workspace(repo) / "state.json")) == "deny"
    assert hook(repo, command="cat .ThanhTan/state.json") == ""


@pytest.mark.parametrize(
    "command",
    [
        "rm .ThanhTan/audit.jsonl",
        "echo > .ThanhTan/audit.jsonl",
        "truncate -s 0 .ThanhTan/audit.jsonl",
        "sed -i d .ThanhTan/audit.jsonl",
        "mv .ThanhTan/audit.jsonl /tmp/gone",
    ],
)
def test_an_agent_cannot_remove_or_rewrite_the_log_with_a_shell(repo, command):
    assert decision_of(hook(repo, command=command)) == "deny"


@pytest.mark.parametrize("tool", ["Write", "Edit"])
def test_an_agent_cannot_remove_or_rewrite_the_log_with_a_file_tool(repo, tool):
    assert decision_of(hook(repo, tool=tool, path=workspace(repo) / "audit.jsonl")) == "deny"


# ------------------------------------------------------------------ approve reads the log


def entry(**changes) -> str:
    base = {"at": now(), "cli": "claude", "tool": "Bash", "kind": "shell", "target": "x", "decision": "allow"}
    return json.dumps({**base, **changes}) + "\n"


def log(repo, *rows: str) -> None:
    with audit_path(repo).open("a", encoding="utf-8") as handle:
        handle.write("".join(rows))


@pytest.fixture
def waiting(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "confirm", monkeypatch, capsys)
    tick(checklist_path(repo, "confirm"))
    return repo


@pytest.mark.parametrize("kind,tool", [("shell", "Bash"), ("shell", "PowerShell"), ("write", "Write")])
def test_approve_refuses_when_an_allowed_call_touched_the_checklist(waiting, capsys, kind, tool):
    log(waiting, entry(kind=kind, tool=tool, target="python -c \"...\" .ThanhTan/tasks/T-001/approve-confirm.md"))
    code, _out, err = approve(capsys)
    assert code == INTEGRITY_FAILED
    assert "approve-confirm.md" in err, "the refusal quotes the line of the log"
    assert "thanhtan state accept" in err
    assert task_now(waiting)[2] == "awaiting_approval"


def test_approve_refuses_when_an_allowed_call_touched_state_json(waiting, capsys):
    log(waiting, entry(target="python tweak.py .ThanhTan/state.json"))
    assert approve(capsys)[0] == INTEGRITY_FAILED


WRITING = [
    "echo x >> .ThanhTan/state.json",
    "echo x > .ThanhTan/state.json",
    "python -c \"open('.ThanhTan/state.json','w').write('{}')\"",
    "node -e \"require('fs').writeFileSync('.ThanhTan/state.json','{}')\"",
    "bash -c 'echo x >> .ThanhTan/state.json'",
    "pwsh -c \"Set-Content .ThanhTan/state.json x\"",
    "echo x | tee .ThanhTan/state.json",
    "sed -i s/a/b/ .ThanhTan/state.json",
    "cp /tmp/x .ThanhTan/state.json",
    "mv /tmp/x .ThanhTan/state.json",
    "rm .ThanhTan/state.json",
    "Set-Content .ThanhTan\\state.json x",
    "Out-File .ThanhTan\\state.json",
    "Add-Content .ThanhTan\\state.json x",
    "python tweak.py .ThanhTan/tasks/T-001/approve-confirm.md",
]
READING = [
    "cat .ThanhTan/state.json",
    "cat .ThanhTan/state.json 2>&1",
    "type .ThanhTan\\state.json",
    "head -n 5 .ThanhTan/state.json",
    "Get-Content .ThanhTan\\state.json",
    "grep version .ThanhTan/state.json",
    "cat .ThanhTan/tasks/T-001/approve-confirm.md",
    "thanhtan status  # looks at .ThanhTan/state.json",
]


@pytest.mark.parametrize("command", WRITING)
def test_a_command_that_could_write_the_checklist_or_state_blocks_the_approval(waiting, capsys, command):
    log(waiting, entry(target=command))
    code, _out, err = approve(capsys)
    assert code == INTEGRITY_FAILED and "thanhtan state accept" in err


@pytest.mark.parametrize("command", READING)
def test_a_command_that_only_reads_never_blocks_the_approval(waiting, capsys, command):
    log(waiting, entry(target=command))
    assert approve(capsys)[0] == ExitCode.OK


def test_cat_of_state_json_does_not_block_but_a_write_after_it_does(waiting, capsys):
    log(waiting, entry(target="cat .ThanhTan/state.json"), entry(target="echo x >> .ThanhTan/state.json"))
    assert approve(capsys)[0] == INTEGRITY_FAILED


def test_approve_refuses_when_an_allowed_call_touched_integrity_json(waiting, capsys):
    log(waiting, entry(target="python tweak.py .ThanhTan/integrity.json"))
    assert approve(capsys)[0] == INTEGRITY_FAILED


def test_a_call_that_was_denied_is_not_evidence(waiting, capsys):
    log(waiting, entry(kind="write", tool="Write", target=".ThanhTan/tasks/T-001/approve-confirm.md", decision="deny"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_call_the_person_was_asked_about_is_not_evidence(waiting, capsys):
    log(waiting, entry(decision="ask", target=".ThanhTan/state.json"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_call_from_before_the_checklist_was_written_is_not_evidence(waiting, capsys):
    log(waiting, entry(at="2000-01-01T00:00:00Z", target=".ThanhTan/state.json"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_call_about_the_checklist_of_another_step_is_not_evidence(waiting, capsys):
    log(waiting, entry(target="cat .ThanhTan/tasks/T-001/approve-build.md"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_call_that_only_mentions_unprotected_files_is_not_evidence(waiting, capsys):
    log(waiting, entry(target="cat src/app.py"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_damaged_line_in_the_log_is_skipped_not_fatal(waiting, capsys):
    log(waiting, "this is not json\n", "\n", entry(decision="deny"))
    assert approve(capsys)[0] == ExitCode.OK


def test_a_missing_log_is_no_evidence(waiting, capsys):
    assert not audit_path(waiting).exists()
    assert approve(capsys)[0] == ExitCode.OK


def test_a_person_clears_the_evidence_with_state_accept(waiting, monkeypatch, capsys):
    log(waiting, entry(target="python tweak.py .ThanhTan/state.json"))
    assert approve(capsys)[0] == INTEGRITY_FAILED
    code, _out, _err = run(capsys, "state", "accept", "--reason", "Tôi đã đọc nhật ký: chỉ là lệnh cat")
    assert code == ExitCode.OK
    assert approve(capsys)[0] == ExitCode.OK


def test_evidence_logged_after_the_accept_counts_again(waiting, capsys):
    log(waiting, entry(target="python tweak.py .ThanhTan/state.json"))
    run(capsys, "state", "accept", "--reason", "đã xem")
    log(waiting, entry(at="2999-01-01T00:00:00Z", target="python tweak.py .ThanhTan/state.json"))
    assert approve(capsys)[0] == INTEGRITY_FAILED


def test_the_log_is_only_read_by_approve_never_by_advance(repo, monkeypatch, capsys):
    say(monkeypatch, "task", "new", "Do it")
    log(repo, entry(target="python tweak.py .ThanhTan/state.json"))
    assert run(capsys, "task", "advance", "--result", "pass")[0] == ExitCode.OK


def test_a_refusal_for_an_open_box_comes_before_the_log_is_looked_at(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "confirm", monkeypatch, capsys)
    log(repo, entry(target=".ThanhTan/state.json"))
    assert approve(capsys)[0] == CHECKLIST_REFUSED
