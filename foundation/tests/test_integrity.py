"""Chặng D-checklist (D4): state.json is hashed on every save, and a hand edit is caught before `advance` / `approve`.

`.ThanhTan/integrity.json` holds `state_sha256` (the sha256 of the bytes agentflow last wrote) and, once a person has
accepted something, `accepted_at`. A mismatch ends `task advance` and `task approve` with exit 37. `agentflow state
accept --reason "..."` is a person's command: it records a decision and takes the file as it is.
"""

import hashlib
import json

import pytest
from checklist_helpers import (
    INTEGRITY_FAILED,
    INVALID_INPUT,
    approve,
    checklist_path,
    decisions,
    go_to_awaiting,
    integrity_path,
    open_workspace,
    state_path,
    task_now,
    tick,
)
from sdd_helpers import run, say

from agentflow.constants import CliKind, ExitCode, HookEvent
from agentflow.git import GitBranchLookup
from agentflow.hook import handle_hook


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    path = open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys)
    assert say(monkeypatch, "task", "new", "Do it") == ExitCode.OK
    capsys.readouterr()
    return path


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tamper(repo) -> None:
    """A valid but hand-made change: the title of the task."""
    data = json.loads(state_path(repo).read_text(encoding="utf-8"))
    data["tasks"][0]["title"] = "Changed by hand"
    state_path(repo).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ the hash is kept


def test_every_save_records_the_hash_of_state_json(repo):
    assert json.loads(integrity_path(repo).read_text(encoding="utf-8"))["state_sha256"] == sha(state_path(repo))


def test_the_hash_follows_each_save(repo, monkeypatch, capsys):
    before = sha(state_path(repo))
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK
    after = sha(state_path(repo))
    assert after != before
    assert json.loads(integrity_path(repo).read_text(encoding="utf-8"))["state_sha256"] == after


# ------------------------------------------------------------------ a hand edit is caught


@pytest.mark.parametrize("command", [("task", "advance", "--result", "pass"), ("task", "approve")])
def test_a_hand_edited_state_json_stops_advance_and_approve(repo, capsys, command):
    tamper(repo)
    edited = state_path(repo).read_bytes()
    code, _out, err = run(capsys, *command)
    assert code == INTEGRITY_FAILED
    assert "state.json" in err and "agentflow state accept" in err
    assert state_path(repo).read_bytes() == edited, "agentflow must not overwrite what it refused"


def test_status_still_works_on_a_hand_edited_state(repo, capsys):
    tamper(repo)
    assert run(capsys, "status")[0] == ExitCode.OK


def test_a_changed_hash_in_integrity_json_is_caught(repo, capsys):
    data = json.loads(integrity_path(repo).read_text(encoding="utf-8"))
    data["state_sha256"] = "0" * 64
    integrity_path(repo).write_text(json.dumps(data), encoding="utf-8")
    assert run(capsys, "task", "advance", "--result", "pass")[0] == INTEGRITY_FAILED


def test_an_unreadable_integrity_json_is_caught(repo, capsys):
    integrity_path(repo).write_text("{not json", encoding="utf-8")
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == INTEGRITY_FAILED and "integrity.json" in err


def test_a_workspace_without_integrity_json_starts_one_and_warns_once(repo, capsys):
    integrity_path(repo).unlink()
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == ExitCode.OK
    assert "integrity.json" in err
    assert integrity_path(repo).is_file()
    assert json.loads(integrity_path(repo).read_text(encoding="utf-8"))["state_sha256"] == sha(state_path(repo))
    _code, _out, again = run(capsys, "status")
    assert "integrity.json" not in again


# ------------------------------------------------------------------ a person accepts, with a reason


def test_state_accept_takes_the_file_as_it_is_and_records_why(repo, monkeypatch, capsys):
    tamper(repo)
    code, _out, _err = run(capsys, "state", "accept", "--reason", "Tôi đã xem: chỉ đổi tiêu đề")
    assert code == ExitCode.OK
    assert json.loads(integrity_path(repo).read_text(encoding="utf-8"))["state_sha256"] == sha(state_path(repo))
    assert run(capsys, "task", "advance", "--result", "pass")[0] == ExitCode.OK
    kept = [p for p in decisions(repo) if "state-accept" in p.name]
    assert len(kept) == 1
    body = kept[0].read_text(encoding="utf-8")
    assert "chỉ đổi tiêu đề" in body
    assert "Changed by hand" in body, "the record says what the state looked like when it was accepted"


@pytest.mark.parametrize("reason", ["", "   "])
def test_state_accept_needs_a_reason_and_changes_nothing_without_one(repo, capsys, reason):
    tamper(repo)
    code, _out, _err = run(capsys, "state", "accept", "--reason", reason)
    assert code == INVALID_INPUT
    assert [p for p in decisions(repo) if "state-accept" in p.name] == []
    assert run(capsys, "task", "advance", "--result", "pass")[0] == INTEGRITY_FAILED


def test_state_accept_without_the_option_is_a_usage_error(repo):
    from agentflow.cli import main

    with pytest.raises(SystemExit) as stop:
        main(["state", "accept"])
    assert stop.value.code == 2


def test_state_accept_with_nothing_to_accept_writes_no_decision(repo, capsys):
    code, out, _err = run(capsys, "state", "accept", "--reason", "chỉ kiểm thử")
    assert code == ExitCode.OK
    assert "nothing to accept" in out.lower()
    assert [p for p in decisions(repo) if "state-accept" in p.name] == []


# ------------------------------------------------------------------ an agent cannot run it


def hook(command: str, repo, cli=CliKind.CLAUDE) -> str:
    if cli is CliKind.CLAUDE:
        payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    else:
        payload = {"workspacePaths": [str(repo)], "toolCall": {"name": "run_command", "args": {"CommandLine": command}}}
    return handle_hook(HookEvent.PRE_TOOL, cli, json.dumps(payload), GitBranchLookup())


@pytest.mark.parametrize(
    "command",
    [
        'agentflow state accept --reason "ok"',
        "AGENTFLOW.EXE state accept --reason ok",
        'uv run agentflow state accept --reason "ok"',
        'python -m agentflow state accept --reason "ok"',
        'cd .ThanhTan && agentflow state accept --reason "ok"',
        'bash -c "agentflow state accept --reason ok"',
        "timeout 5 agentflow state accept --reason ok",
        "FOO=1 agentflow state accept --reason ok",
    ],
)
@pytest.mark.parametrize("cli", [CliKind.CLAUDE, CliKind.ANTIGRAVITY])
def test_state_accept_is_a_command_for_a_person_in_every_form_the_guard_reads(repo, command, cli):
    reply = json.loads(hook(command, repo, cli))
    decision = reply.get("hookSpecificOutput", {}).get("permissionDecision") or reply.get("decision")
    assert decision == "deny"


@pytest.mark.parametrize("cli", [CliKind.CLAUDE, CliKind.ANTIGRAVITY])
def test_leaving_the_project_and_coming_back_does_not_hide_state_accept(repo, cli):
    command = f'cd .. && cd "{repo.name}" && agentflow state accept --reason "ok"'
    reply = json.loads(hook(command, repo, cli))
    decision = reply.get("hookSpecificOutput", {}).get("permissionDecision") or reply.get("decision")
    assert decision == "deny"


def test_state_accept_is_not_confused_with_talk_about_it(repo):
    assert hook('echo "agentflow state accept"', repo) == ""
    assert hook("agentflow state", repo) == ""


# ------------------------------------------------------------------ the checklist hash is kept too


def test_the_hash_of_a_checklist_skeleton_is_kept_outside_the_checklist(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "confirm", monkeypatch, capsys, first=False)
    data = json.loads(integrity_path(repo).read_text(encoding="utf-8"))
    kept = json.dumps(data["checklists"])
    assert "confirm" in kept
    text = checklist_path(repo, "confirm").read_text(encoding="utf-8")
    header = [line for line in text.splitlines() if line.startswith("- skeleton-sha256:")][0].split(": ")[1]
    assert header in kept


def test_a_checklist_that_matches_its_own_header_but_not_integrity_json_is_refused(repo, monkeypatch, capsys):
    go_to_awaiting(repo, "confirm", monkeypatch, capsys, first=False)
    path = checklist_path(repo, "confirm")
    tick(path)
    text = path.read_text(encoding="utf-8")
    # Rewrite the whole skeleton (one question gone) and make the header agree with it.
    import re

    lines = [line for line in text.splitlines(keepends=True) if " K2:" not in line]
    edited = "".join(lines)
    from agentflow.checklist import skeleton_sha256

    fresh = skeleton_sha256(edited)
    path.write_text(re.sub(r"skeleton-sha256: [0-9a-f]{64}", f"skeleton-sha256: {fresh}", edited), encoding="utf-8")
    code, _out, _err = approve(capsys)
    assert code != ExitCode.OK
    assert task_now(repo)[1] == "confirm"
