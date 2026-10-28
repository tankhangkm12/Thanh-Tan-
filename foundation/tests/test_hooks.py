import io
import json

import pytest
from conftest import git

from thanhtan.cli import main
from thanhtan.constants import CliKind, ExitCode, HookEvent, ReplyKind
from thanhtan.git import GitBranchLookup
from thanhtan.hook import handle_hook
from thanhtan.hook_adapters import ADAPTERS, AntigravityAdapter, ClaudeAdapter
from thanhtan.interfaces import HookAdapter
from thanhtan.models import HookReply

# ----------------------------------------------------------------- adapters


def test_adapters_implement_protocol():
    assert set(ADAPTERS) == set(CliKind)
    assert all(isinstance(adapter, HookAdapter) for adapter in ADAPTERS.values())


def test_claude_read_pre_tool():
    payload = {"cwd": "/p", "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git push"}}
    result = ClaudeAdapter().read(HookEvent.PRE_TOOL, payload)
    assert (str(result.cwd).replace("\\", "/"), result.command) == ("/p", "git push")


def test_claude_read_stop_flag_and_garbage():
    adapter = ClaudeAdapter()
    assert adapter.read(HookEvent.STOP, {"cwd": "/p", "stop_hook_active": True}).stop_hook_active
    empty = adapter.read(HookEvent.PRE_TOOL, {"tool_input": "oops", "cwd": 3})
    assert empty.cwd is None and empty.command is None and not empty.stop_hook_active


def test_claude_render():
    adapter = ClaudeAdapter()
    deny = json.loads(adapter.render(HookEvent.PRE_TOOL, HookReply(ReplyKind.DENY, "no push")))
    assert deny == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "no push",
        }
    }
    context = json.loads(adapter.render(HookEvent.SESSION_START, HookReply(ReplyKind.CONTEXT, "hello")))
    assert context["hookSpecificOutput"] == {"hookEventName": "SessionStart", "additionalContext": "hello"}
    reminder = json.loads(adapter.render(HookEvent.STOP, HookReply(ReplyKind.REMINDER, "update state")))
    assert reminder == {"systemMessage": "update state"}
    for event in HookEvent:
        assert adapter.render(event, HookReply()) == ""


def test_antigravity_read_prefers_tool_cwd_then_workspace():
    adapter = AntigravityAdapter()
    payload = {
        "workspacePaths": ["/ws"],
        "toolCall": {"name": "run_command", "args": {"CommandLine": "git push", "Cwd": "/tool"}},
        "invocationNum": 0,
    }
    result = adapter.read(HookEvent.PRE_TOOL, payload)
    assert str(result.cwd).replace("\\", "/") == "/tool" and result.command == "git push" and result.invocation_num == 0
    del payload["toolCall"]["args"]["Cwd"]
    assert str(adapter.read(HookEvent.PRE_TOOL, payload).cwd).replace("\\", "/") == "/ws"
    assert adapter.read(HookEvent.PRE_TOOL, {"invocationNum": True}).invocation_num is None
    assert adapter.read(HookEvent.PRE_TOOL, {"workspacePaths": []}).cwd is None


def test_antigravity_render():
    adapter = AntigravityAdapter()
    deny = json.loads(adapter.render(HookEvent.PRE_TOOL, HookReply(ReplyKind.DENY, "no push")))
    assert deny == {"decision": "deny", "reason": "no push"}
    # Never "allow" for a command that is not blocked: that would skip the CLI's own permission prompt.
    assert "allow" not in adapter.render(HookEvent.PRE_TOOL, HookReply())
    context = json.loads(adapter.render(HookEvent.SESSION_START, HookReply(ReplyKind.CONTEXT, "hello")))
    assert context == {"injectSteps": [{"ephemeralMessage": "hello"}]}
    assert json.loads(adapter.render(HookEvent.SESSION_START, HookReply())) == {}
    for reply in (HookReply(), HookReply(ReplyKind.REMINDER, "x")):
        assert json.loads(adapter.render(HookEvent.STOP, reply))["decision"] != "continue"


# -------------------------------------------------------------------- logic


@pytest.fixture
def project(gitflow_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def hook(event, cli, payload, raw=None):
    text = raw if raw is not None else json.dumps(payload)
    return handle_hook(event, cli, text, GitBranchLookup())


def claude_pre(project, command):
    return {"cwd": str(project), "tool_name": "Bash", "tool_input": {"command": command}}


def agy_pre(project, command):
    return {"workspacePaths": [str(project)], "toolCall": {"name": "run_command", "args": {"CommandLine": command}}}


def test_pre_tool_denies_push_for_both_clis(project):
    claude = json.loads(hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_pre(project, "git push")))
    assert claude["hookSpecificOutput"]["permissionDecision"] == "deny"
    agy = json.loads(hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, agy_pre(project, "git push origin develop")))
    assert agy["decision"] == "deny" and "push" in agy["reason"]


def test_pre_tool_denies_direct_commit_in_the_project(project):
    out = json.loads(hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_pre(project, "git commit -m x")))
    assert "thanhtan commit" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_pre_tool_stays_silent_for_safe_commands(project):
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_pre(project, "git status")) == ""
    assert "allow" not in hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, agy_pre(project, "git status"))


@pytest.mark.parametrize("event", list(HookEvent))
@pytest.mark.parametrize("cli", list(CliKind))
def test_nothing_happens_without_a_workspace(tmp_path, event, cli):
    repo = tmp_path / "plain-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    payload = {
        "cwd": str(repo),
        "workspacePaths": [str(repo)],
        "tool_input": {"command": "git push"},
        "toolCall": {"args": {"CommandLine": "git push"}},
        "invocationNum": 0,
    }
    assert hook(event, cli, payload) == ""


def test_nothing_happens_outside_a_repository_or_on_bad_input(tmp_path, project):
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, {"cwd": str(tmp_path / "missing"), "tool_input": {"command": "git push"}}) == ""
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, None, raw="not json") == ""
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, None, raw="[]") == ""
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, {"tool_input": {"command": "git push"}}) == ""


def test_session_start_summary(project, capsys):
    main(["task", "new", "Add login"])
    out = json.loads(hook(HookEvent.SESSION_START, CliKind.CLAUDE, {"cwd": str(project)}))
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "Active task: T-001 Add login" in text and "never edit files under .ThanhTan/" in text
    assert "step 'confirm'" in text


def test_session_start_without_task_points_to_start(project):
    text = json.loads(hook(HookEvent.SESSION_START, CliKind.CLAUDE, {"cwd": str(project)}))["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "No active task" in text


def test_antigravity_summary_only_on_first_invocation(project):
    first = {"workspacePaths": [str(project)], "invocationNum": 0}
    steps = json.loads(hook(HookEvent.SESSION_START, CliKind.ANTIGRAVITY, first))["injectSteps"]
    assert "thanhtan workspace found" in steps[0]["ephemeralMessage"]
    later = json.loads(hook(HookEvent.SESSION_START, CliKind.ANTIGRAVITY, {**first, "invocationNum": 3}))
    assert later == {}
    assert json.loads(hook(HookEvent.SESSION_START, CliKind.ANTIGRAVITY, {"workspacePaths": [str(project)]})) == {}


def test_corrupt_state_gives_no_summary(project):
    (project / ".ThanhTan" / "state.json").write_text("{", encoding="utf-8")
    assert hook(HookEvent.SESSION_START, CliKind.CLAUDE, {"cwd": str(project)}) == ""


def test_stop_reminder_only_while_a_step_is_in_progress(project, capsys):
    stop = {"cwd": str(project), "stop_hook_active": False}
    assert hook(HookEvent.STOP, CliKind.CLAUDE, stop) == ""  # no task
    main(["task", "new", "t"])
    assert hook(HookEvent.STOP, CliKind.CLAUDE, stop) == ""  # step just began, nothing done yet
    _save_report(project, "T-001", "confirm")
    message = json.loads(hook(HookEvent.STOP, CliKind.CLAUDE, stop))["systemMessage"]
    assert "T-001" in message and "thanhtan task advance" in message
    assert hook(HookEvent.STOP, CliKind.CLAUDE, {**stop, "stop_hook_active": True}) == ""
    main(["task", "advance", "--result", "pass"])  # now awaiting approval
    assert hook(HookEvent.STOP, CliKind.CLAUDE, stop) == ""


def _save_report(project, task_id, step):
    path = project / ".ThanhTan" / "tasks" / task_id / "reports" / f"{step}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("done\n", encoding="utf-8")


def test_stale_report_from_before_the_step_began_does_not_trigger_a_reminder(project):
    import os

    main(["task", "new", "t"])
    _save_report(project, "T-001", "confirm")
    old = (project / ".ThanhTan" / "tasks" / "T-001" / "reports" / "confirm.md")
    os.utime(old, (0, 0))
    assert hook(HookEvent.STOP, CliKind.CLAUDE, {"cwd": str(project), "stop_hook_active": False}) == ""


def test_antigravity_stop_never_blocks(project):
    main(["task", "new", "t"])
    out = json.loads(hook(HookEvent.STOP, CliKind.ANTIGRAVITY, {"workspacePaths": [str(project)]}))
    assert out["decision"] == "allow"


# ---------------------------------------------------------------------- cli


def test_hook_command_prints_output_and_exits_zero(project, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(claude_pre(project, "git push"))))
    assert main(["hook", "pre-tool", "--cli", "claude"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_command_is_silent_without_workspace(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert main(["hook", "session-start", "--cli", "antigravity"]) == ExitCode.OK
    assert capsys.readouterr().out == ""


def test_hook_command_never_fails_the_agent(project, capsys, monkeypatch):
    monkeypatch.setattr("thanhtan.cli.handle_hook", lambda *args: 1 / 0)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert main(["hook", "stop", "--cli", "claude"]) == ExitCode.OK
    assert "hook failed" in capsys.readouterr().err


def test_hook_command_needs_valid_arguments():
    with pytest.raises(SystemExit):
        main(["hook", "nope", "--cli", "claude"])
    with pytest.raises(SystemExit):
        main(["hook", "stop"])


# ------------------------------------------------------------ file-writing tools


def claude_write(project, tool, path, key="file_path"):
    return {"cwd": str(project), "tool_name": tool, "tool_input": {key: str(path)}}


def agy_write(project, tool, path):
    return {"workspacePaths": [str(project)], "toolCall": {"name": tool, "args": {"TargetFile": str(path)}}}


def test_adapters_read_the_target_of_file_writing_tools():
    claude = ClaudeAdapter()
    for tool, key in [("Write", "file_path"), ("Edit", "file_path"), ("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path")]:
        read = claude.read(HookEvent.PRE_TOOL, {"cwd": "/p", "tool_name": tool, "tool_input": {key: "/p/a.txt"}})
        assert read.write_target is not None and read.write_target.name == "a.txt"
    # Reading a file is not writing it, and a Bash command has no target.
    assert claude.read(HookEvent.PRE_TOOL, {"cwd": "/p", "tool_name": "Read", "tool_input": {"file_path": "/p/a"}}).write_target is None
    assert claude.read(HookEvent.PRE_TOOL, {"cwd": "/p", "tool_name": "Bash", "tool_input": {"command": "ls"}}).write_target is None
    agy = AntigravityAdapter()
    for tool in ["write_to_file", "replace_file_content", "multi_replace_file_content"]:
        read = agy.read(HookEvent.PRE_TOOL, {"workspacePaths": ["/p"], "toolCall": {"name": tool, "args": {"TargetFile": "/p/a.txt"}}})
        assert read.write_target is not None and read.write_target.name == "a.txt"
    assert agy.read(HookEvent.PRE_TOOL, {"toolCall": {"name": "view_file", "args": {"AbsolutePath": "/p/a"}}}).write_target is None


@pytest.mark.parametrize("tool,key", [("Write", "file_path"), ("Edit", "file_path"), ("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path")])
def test_claude_file_tools_cannot_write_into_the_workspace(project, tool, key):
    for path in [project / ".ThanhTan" / "decisions" / "x.md", ".ThanhTan/state.json", project / "src" / ".." / ".ThanhTan" / "a"]:
        out = json.loads(hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_write(project, tool, path, key)))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert ".ThanhTan" in out["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("tool", ["write_to_file", "replace_file_content", "multi_replace_file_content"])
def test_antigravity_file_tools_cannot_write_into_the_workspace(project, tool):
    out = json.loads(hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, agy_write(project, tool, project / ".ThanhTan" / "decisions" / "x.md")))
    assert out["decision"] == "deny" and ".ThanhTan" in out["reason"]


def test_file_tools_may_write_everywhere_else(project):
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_write(project, "Write", project / "src" / "a.py")) == ""
    assert "deny" not in hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, agy_write(project, "write_to_file", project / "a.py"))
    assert hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_write(project, "Write", project / ".ThanhTan-notes" / "a")) == ""


# ------------------------------------------------- remembering the project for MCP servers


def test_antigravity_hooks_leave_a_pointer_to_the_project_and_claude_hooks_do_not(project, monkeypatch, tmp_path):
    home = tmp_path / "pointer-home"
    monkeypatch.setenv("THANHTAN_HOME", str(home))
    hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, claude_pre(project, "git status"))
    assert not (home / "active-project.txt").exists()
    hook(HookEvent.PRE_TOOL, CliKind.ANTIGRAVITY, agy_pre(project, "git status"))
    assert (home / "active-project.txt").read_text(encoding="utf-8").strip() == str(project)
