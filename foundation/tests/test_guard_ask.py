"""Phase D-guard (D3): the guard asks a person before `task approve` / `task cancel`, in every way the command can be called.

Two decisions the guard can give about an `agentflow` command in a project that has a workspace:

- ``ask``  : `task approve`, `task cancel`. The CLI must show the person a prompt (Claude Code `permissionDecision: "ask"`,
             Antigravity `decision: "force_ask"`); the agent cannot answer it. Nothing is blocked.
- ``deny`` : the commands only a person runs (`decide`, `ext add|sync`, `config set`, `task seal`, `project confirm`,
             `knowledge init|pull|push`, `role grant|revoke|sync`, `roadmap set`, `replan done|skip`), as before.

Before this phase the guard looked for `agentflow` only as the first word of a command, so `uv run agentflow ...`,
`python -m agentflow ...`, `timeout 5 agentflow ...` or `FOO=1 agentflow ...` got past every one of them. Tests marked
"Regression" are green before the phase and must stay green; the others describe the new behaviour.
"""

import io
import json
import re
from pathlib import Path

import pytest
from conftest import git

from agentflow.cli import main
from agentflow.constants import CliKind, ExitCode, GuardDecision, GuardRule, HookEvent, ReplyKind
from agentflow.git import GitBranchLookup
from agentflow.guard import evaluate, verdict_to_dict
from agentflow.hook import handle_hook
from agentflow.hook_adapters import AntigravityAdapter, ClaudeAdapter
from agentflow.models import HookReply

PROJECT = "/proj"
README = Path(__file__).resolve().parents[2] / "README.md"


class Workspaces:
    def __init__(self, *roots):
        self.roots = {Path(root) for root in roots}

    def has_workspace(self, directory):
        return Path(directory) in self.roots


class OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


def check(command, cwd=PROJECT, roots=(PROJECT,)):
    return evaluate(command, Path(cwd), OnFeature(), Workspaces(*roots))


# What a person decides for themselves and what the agent may not run at all.
PERSON_COMMANDS = [
    "decide --suppress x --reason y",
    "ext add e.yaml",
    "ext sync",
    "config set a.b c",
    "task seal T-001",
    "project confirm PC-01",
    "project confirm mission R1",
    "knowledge init",
    "knowledge pull semgrep/x.yaml",
    "knowledge push",
    "role grant tester",
    "role revoke tester",
    "role sync",
    "roadmap set R1 done",
    "replan done",
    "replan skip T-001 --reason x",
]
# The commands that give a person's approval: the agent may run them only if the person says yes at the prompt.
ASK_COMMANDS = [
    "task approve",
    "task approve --reason vendor-wait",
    "task cancel",
    "task cancel --reason x",
]

# Ways of calling a program that the guard already recognises today (Regression for both lists above).
KNOWN_FORMS = [
    "agentflow {c}",
    "AGENTFLOW.EXE {c}",
    "agentflow  {c}",
    "cd . && agentflow {c}",
    "echo x; agentflow {c}",
    "echo x | agentflow {c}",
    "(agentflow {c})",
    "& agentflow {c}",
    "$env:X='1'; agentflow {c}",
    "/usr/bin/agentflow {c}",
    "./agentflow {c}",
    r".\agentflow {c}",
    r"C:\Users\x\.local\bin\agentflow.exe {c}",
    '"C:\\Program Files\\x\\agentflow.exe" {c}',
    'bash -c "agentflow {c}"',
    "sh -c 'agentflow {c}'",
    'powershell -Command "agentflow {c}"',
    'cmd /c "agentflow {c}"',
    'sh -c "bash -c \\"agentflow {c}\\""',
    'eval "agentflow {c}"',
    'iex "agentflow {c}"',
    "Invoke-Expression 'agentflow {c}'",
]

# Ways that get past the guard before this phase and must not any more.
NEW_FORMS = [
    # uv and python launchers
    "uv run agentflow {c}",
    "uv run --project foundation agentflow {c}",
    "uv run --with pyyaml agentflow {c}",
    "uv run -- agentflow {c}",
    "uvx agentflow {c}",
    "uv tool run agentflow {c}",
    "uv run python -m agentflow {c}",
    "python -m agentflow {c}",
    "python3 -m agentflow {c}",
    "py -3 -m agentflow {c}",
    "python.exe -m agentflow {c}",
    r"C:\Python312\python.exe -m agentflow {c}",
    "/usr/bin/python3 -m agentflow {c}",
    # wrappers and environment prefixes
    "timeout 5 agentflow {c}",
    "nohup agentflow {c}",
    "time agentflow {c}",
    "nice agentflow {c}",
    "command agentflow {c}",
    "env agentflow {c}",
    "env FOO=1 agentflow {c}",
    "FOO=1 agentflow {c}",
    "FOO=1 BAR=2 agentflow {c}",
    "xargs agentflow {c}",
    "timeout 5 uv run agentflow {c}",
    "FOO=1 uv run python -m agentflow {c}",
    # a shell inside a shell, other flags, evaluators, Start-Process
    "bash -lc 'agentflow {c}'",
    'bash -c "uv run agentflow {c}"',
    'powershell -NoProfile -Command "uv run agentflow {c}"',
    "Start-Process agentflow -ArgumentList '{c}'",
    "Start-Process -FilePath agentflow -ArgumentList '{c}' -Wait",
    "Start-Process -FilePath C:\\x\\agentflow.exe -ArgumentList '{c}'",
    "echo T-001 | xargs -n1 uv run agentflow {c}",
    "cd . && uv run agentflow {c}",
    "echo x; python -m agentflow {c}",
]

# `python -c "from agentflow.cli import main; main([...])"` carries the command as a list of quoted words.
PYTHON_C_FORMS = ['python -c "{py}"', 'python3 -c "{py}"', 'uv run python -c "{py}"', "python.exe -c \"{py}\""]
PYTHON_C_COMMANDS = ["task approve", "task cancel", "task seal T-001", "replan done", "roadmap set R1 done", "project confirm mission", "decide --suppress x --reason y"]


def python_call(words: str) -> str:
    return f"from agentflow.cli import main; main({words.split()!r})"


def deny(verdict, command=""):
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PERSON_ONLY, (command, verdict)
    assert verdict.denied


def ask(verdict, command=""):
    assert verdict.decision is GuardDecision.ASK, (command, verdict)
    assert verdict.rule is GuardRule.PERSON_CONFIRMS and verdict.reason
    assert verdict.asks and not verdict.denied


# ------------------------------------------------------------------ the new decision


def test_ask_is_a_decision_of_its_own_and_is_neither_allow_nor_deny():
    assert GuardDecision.ASK == "ask" and ReplyKind.ASK == "ask"
    verdict = check("agentflow task approve")
    assert verdict.decision is not GuardDecision.ALLOW and verdict.decision is not GuardDecision.DENY
    assert verdict.asks is True and verdict.denied is False


def test_the_reason_names_the_command_and_tells_the_agent_a_person_must_say_yes():
    reason = check("agentflow task cancel --reason x").reason
    assert "task cancel" in reason
    assert "person" in reason.lower()


def test_a_verdict_to_ask_serialises_like_the_others():
    verdict = check("agentflow task approve")
    assert json.loads(json.dumps(verdict_to_dict(verdict))) == {
        "decision": "ask",
        "rule": "person-confirms",
        "reason": verdict.reason,
    }


@pytest.mark.parametrize("command", ASK_COMMANDS)
def test_approving_or_cancelling_asks_a_person_in_a_project_with_a_workspace(command):
    ask(check(f"agentflow {command}"), command)


@pytest.mark.parametrize("command", ASK_COMMANDS)
def test_approving_or_cancelling_is_not_asked_outside_a_workspace(command):
    assert check(f"agentflow {command}", roots=()).decision is GuardDecision.ALLOW
    assert check(f"uv run agentflow {command}", roots=()).decision is GuardDecision.ALLOW
    assert check(f"agentflow {command}", cwd="/elsewhere").decision is GuardDecision.ALLOW


@pytest.mark.parametrize("command", PERSON_COMMANDS)
def test_commands_only_a_person_runs_stay_denied_not_asked(command):
    """Regression: `decide` and the others are not softened to `ask` (a person types them with `!`)."""
    deny(check(f"agentflow {command}"), command)


def test_decide_stays_denied_and_is_not_among_the_asked_commands():
    deny(check("agentflow decide --answer S1 --text x"))
    assert check("agentflow decide --answer S1 --text x").decision is GuardDecision.DENY


# --------------------------------------------------------- every way of calling it


@pytest.mark.parametrize("form", KNOWN_FORMS)
@pytest.mark.parametrize("command", ASK_COMMANDS)
def test_approve_and_cancel_ask_in_the_forms_the_guard_already_reads(form, command):
    ask(check(form.format(c=command)), form)


@pytest.mark.parametrize("form", NEW_FORMS)
@pytest.mark.parametrize("command", ASK_COMMANDS)
def test_approve_and_cancel_ask_however_the_program_is_started(form, command):
    ask(check(form.format(c=command)), form)


@pytest.mark.parametrize("form", KNOWN_FORMS)
@pytest.mark.parametrize("command", PERSON_COMMANDS)
def test_regression_person_only_commands_are_denied_in_the_forms_the_guard_already_reads(form, command):
    deny(check(form.format(c=command)), form)


@pytest.mark.parametrize("form", NEW_FORMS)
@pytest.mark.parametrize("command", PERSON_COMMANDS)
def test_person_only_commands_are_denied_however_the_program_is_started(form, command):
    deny(check(form.format(c=command)), form)


@pytest.mark.parametrize("form", PYTHON_C_FORMS)
@pytest.mark.parametrize("command", PYTHON_C_COMMANDS)
def test_calling_the_cli_from_python_dash_c_is_seen_too(form, command):
    verdict = check(form.format(py=python_call(command)))
    if command.startswith("task "):
        if command.startswith("task seal"):
            deny(verdict, form)
        else:
            ask(verdict, form)
    else:
        deny(verdict, form)


def test_the_command_words_may_be_split_over_quoted_pieces():
    ask(check("agentflow 'task' \"approve\""))
    deny(check("uv run agentflow 'replan' 'done'"))


def test_options_before_the_words_do_not_hide_the_command():
    ask(check("uv run agentflow --quiet task approve"))
    deny(check("python -m agentflow --quiet roadmap set R1 done"))


# --------------------------------------------------------------- what must not ask


NOT_AGENTFLOW = [
    "agentflow status",
    "agentflow task new 'approve the design'",
    "agentflow task advance --result pass",
    "agentflow task",
    "agentflow report --step plan",
    "agentflow roadmap list",
    "agentflow project status",
    "agentflow replan status",
    "agentflow replan write",
    "uv run agentflow status",
    "uv run agentflow task advance --result pass",
    "python -m agentflow status",
    "uv run pytest",
    "uv run pytest tests/test_approve.py",
    "python -m pytest -k 'task and approve'",
    "python -c \"import agentflow; print(agentflow.__version__)\"",
    "uv tool install --force --reinstall ./foundation",
    'echo "agentflow task approve"',
    "echo agentflow task approve",
    "printf '%s' 'uv run agentflow task cancel'",
    'git log --grep "agentflow task approve"',
    "grep -rn 'task approve' docs",
    "grep approve README.md",
    "cat agentflow-task-approve.md",
    "ls agentflow",
    "Select-String -Pattern 'agentflow task approve' README.md",
    "agentflow commit 'document how task approve works'",
    "agentflow commit 'fix uv run agentflow task cancel'",
    "timeout 5 uv run pytest",
    "FOO=1 python -m pytest",
    "xargs echo agentflow task approve",
]


@pytest.mark.parametrize("command", NOT_AGENTFLOW)
def test_commands_that_only_mention_approve_or_that_are_other_agentflow_commands_pass(command):
    verdict = check(command)
    assert verdict.decision is GuardDecision.ALLOW and verdict.rule is None, (command, verdict)


def test_a_here_document_body_is_data_not_a_command():
    body = "agentflow report --step review <<'EOF'\n## Next\nA person runs\nagentflow task approve\nuv run agentflow task cancel\nEOF"
    assert check(body).decision is GuardDecision.ALLOW
    keyed = "agentflow report --step review <<-EOF\n\tagentflow replan done\n\tEOF\necho ok"
    assert check(keyed).decision is GuardDecision.ALLOW


def test_a_command_after_a_here_document_is_still_looked_at():
    ask(check("agentflow report --step plan <<'EOF'\nbody\nEOF\nagentflow task approve"))
    deny(check("agentflow report --step plan <<'EOF'\nbody\nEOF\nuv run agentflow replan done"))


# ------------------------------------------------------ several commands in one line


def test_asking_is_found_in_a_chain_next_to_harmless_commands():
    ask(check("agentflow status && agentflow task approve"))
    ask(check("git status; uv run agentflow task cancel; echo done"))
    ask(check("agentflow task approve | tee out.txt"))


@pytest.mark.parametrize(
    "command",
    [
        "agentflow task approve && agentflow replan done",
        "agentflow replan done; agentflow task approve",
        "agentflow task approve && git push",
        "git push; uv run agentflow task approve",
        "uv run agentflow task cancel && uv run agentflow project confirm mission",
    ],
)
def test_a_denial_wins_over_a_question_wherever_it_stands_in_the_line(command):
    verdict = check(command, cwd=PROJECT)
    assert verdict.denied, (command, verdict)
    assert verdict.decision is GuardDecision.DENY


def test_two_questions_are_still_one_question():
    ask(check("agentflow task approve && agentflow task cancel"))


# ------------------------------------------------- what the guard cannot see (stated limits)


UNSEEN = [
    "& $exe task approve",
    "$verb = 'approve'; agentflow task $verb",
    "agentflow $args",
    "bash approve.sh",
    "make approve",
    "node run.js",
    "alias go='agentflow task approve'; go",
]


@pytest.mark.parametrize("command", UNSEEN)
def test_limit_what_is_not_spelled_out_in_the_command_line_is_not_seen(command):
    """Documented limit (README Bước 4, architecture): variables, scripts and aliases are not followed by the hook."""
    assert check(command).decision is GuardDecision.ALLOW


# --------------------------------------------------------------- the CLI adapters


def test_claude_renders_ask_with_the_documented_fields():
    out = json.loads(ClaudeAdapter().render(HookEvent.PRE_TOOL, HookReply(ReplyKind.ASK, "confirm it")))
    assert out == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "confirm it",
        }
    }


def test_antigravity_renders_ask_as_force_ask_so_the_always_allow_cache_cannot_skip_it():
    out = json.loads(AntigravityAdapter().render(HookEvent.PRE_TOOL, HookReply(ReplyKind.ASK, "confirm it")))
    assert out == {"decision": "force_ask", "reason": "confirm it"}


def test_regression_deny_is_rendered_as_before():
    claude = json.loads(ClaudeAdapter().render(HookEvent.PRE_TOOL, HookReply(ReplyKind.DENY, "no")))
    assert claude["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert json.loads(AntigravityAdapter().render(HookEvent.PRE_TOOL, HookReply(ReplyKind.DENY, "no"))) == {
        "decision": "deny",
        "reason": "no",
    }


@pytest.mark.parametrize("event", [HookEvent.SESSION_START, HookEvent.STOP])
def test_a_question_is_only_for_the_tool_call_event(event):
    assert ClaudeAdapter().render(event, HookReply(ReplyKind.ASK, "x")) == ""
    assert "force_ask" not in AntigravityAdapter().render(event, HookReply(ReplyKind.ASK, "x"))


# ---------------------------------------------------------- the hooks, end to end


@pytest.fixture
def project(gitflow_repo, workflow_file, monkeypatch, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


def hook(cli, payload):
    return handle_hook(HookEvent.PRE_TOOL, cli, json.dumps(payload), GitBranchLookup())


def claude(project, command, tool="Bash", cwd=None):
    return {"cwd": str(cwd or project), "tool_name": tool, "tool_input": {"command": command}}


def agy(project, command):
    return {"workspacePaths": [str(project)], "toolCall": {"name": "run_command", "args": {"CommandLine": command}}}


def claude_decision(text):
    return json.loads(text)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("command", ["agentflow task approve", "agentflow task cancel --reason x", "uv run agentflow task approve", "python -m agentflow task cancel"])
def test_claude_is_asked_to_prompt_a_person(project, tool, command):
    out = hook(CliKind.CLAUDE, claude(project, command, tool))
    assert claude_decision(out) == "ask"
    assert "person" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"].lower()


@pytest.mark.parametrize("command", ["agentflow task approve", "agentflow task cancel", "uv run agentflow task approve", "timeout 5 agentflow task cancel"])
def test_antigravity_is_forced_to_ask(project, command):
    out = json.loads(hook(CliKind.ANTIGRAVITY, agy(project, command)))
    assert out["decision"] == "force_ask" and out["reason"]


@pytest.mark.parametrize("cli", list(CliKind))
@pytest.mark.parametrize("command", ["agentflow task approve", "uv run agentflow task cancel", "agentflow replan done", "uv run agentflow replan skip T-001 --reason x"])
def test_the_hook_never_answers_allow_for_these_commands(project, cli, command):
    payload = claude(project, command) if cli is CliKind.CLAUDE else agy(project, command)
    out = hook(cli, payload)
    assert out and '"allow"' not in out


@pytest.mark.parametrize("command", ["agentflow replan done", "uv run agentflow roadmap set R1 done", "python -m agentflow project confirm mission", "FOO=1 agentflow task seal T-001"])
def test_person_only_commands_are_denied_by_the_hook_in_both_clis(project, command):
    assert claude_decision(hook(CliKind.CLAUDE, claude(project, command))) == "deny"
    assert json.loads(hook(CliKind.ANTIGRAVITY, agy(project, command)))["decision"] == "deny"


def test_a_denial_in_the_same_line_wins_in_the_hook_too(project):
    assert claude_decision(hook(CliKind.CLAUDE, claude(project, "agentflow task approve && git push"))) == "deny"
    assert json.loads(hook(CliKind.ANTIGRAVITY, agy(project, "agentflow task approve && agentflow replan done")))["decision"] == "deny"


def test_other_commands_still_get_no_answer_from_the_hook(project):
    """Regression: silence lets the CLI use its own permission rules."""
    for command in ("agentflow status", "uv run agentflow status", "uv run pytest", "git status"):
        assert hook(CliKind.CLAUDE, claude(project, command)) == "", command
        assert "allow" not in hook(CliKind.ANTIGRAVITY, agy(project, command)), command


def test_a_subdirectory_of_the_project_is_still_the_project(project):
    sub = project / "src" / "deep"
    sub.mkdir(parents=True)
    assert claude_decision(hook(CliKind.CLAUDE, claude(project, "agentflow task approve", cwd=sub))) == "ask"


def test_outside_a_project_with_a_workspace_the_hook_is_silent(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    git(plain, "init", "-q")
    assert hook(CliKind.CLAUDE, claude(plain, "agentflow task approve")) == ""
    assert hook(CliKind.ANTIGRAVITY, agy(plain, "uv run agentflow task approve")) == ""


def test_the_hook_command_exits_zero_when_it_asks(project, capsys, monkeypatch):
    for cli, payload in ((CliKind.CLAUDE, claude(project, "agentflow task approve")), (CliKind.ANTIGRAVITY, agy(project, "agentflow task cancel"))):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        assert main(["hook", "pre-tool", "--cli", cli.value]) == ExitCode.OK
        assert capsys.readouterr().out.strip()


def test_regression_file_tools_are_judged_as_before(project):
    write = {"cwd": str(project), "tool_name": "Write", "tool_input": {"file_path": str(project / ".agentflow" / "state.json")}}
    assert claude_decision(hook(CliKind.CLAUDE, write)) == "deny"
    plain = {"cwd": str(project), "tool_name": "Write", "tool_input": {"file_path": str(project / "src" / "a.py")}}
    assert hook(CliKind.CLAUDE, plain) == ""


# ------------------------- text that an interpreter runs is scanned like a command (person's review, 18/10/2026)
#
# A here-document is data for `agentflow report`, `cat`, `tee`, `python script.py`: nothing runs it. When it (or a pipe,
# a here-string, `-c`) feeds an interpreter that executes what it reads, the text IS a command line: a person-only
# command in it is denied, approve/cancel in it asks. Text the guard cannot read (`curl ... | sh`, `bash < file`) asks.

SHELL_READERS = ["bash", "sh", "zsh", "bash -s", "bash -", "sh -s", "/bin/bash", "env bash", "timeout 5 bash"]
SCRIPT_READERS = ["python", "python3", "python -", "python3 -", "uv run python", "uv run python -", "node", "py -3", "python.exe"]
PIPE_READERS = SHELL_READERS + SCRIPT_READERS + ["pwsh", "powershell", "pwsh -Command -", "powershell -", "cmd"]

SHELL_BODIES = [
    ("agentflow task approve", ask),
    ("uv run agentflow task cancel", ask),
    ("echo start\nagentflow task approve\necho end", ask),
    ("agentflow replan done", deny),
    ("python -m agentflow roadmap set R1 done", deny),
    ("agentflow task approve\nagentflow replan done", deny),
]
SCRIPT_BODIES = [
    ("import subprocess\nsubprocess.run(['agentflow', 'decide', '--suppress', 'x', '--reason', 'y'])", deny),
    ("import subprocess\nsubprocess.run('agentflow task approve', shell=True)", ask),
    ("import subprocess\nsubprocess.run([\n    'agentflow',\n    'task',\n    'approve',\n])", ask),
    ("import os\nos.system('uv run agentflow replan skip T-001 --reason x')", deny),
    ("from agentflow.cli import main\nmain(['task', 'cancel'])", ask),
]
HARMLESS_BODIES = ["echo hello", "ls -la\ngit status", "agentflow status\nagentflow task advance --result pass", "print('hello')", "import os\nprint(os.getcwd())"]


@pytest.mark.parametrize("reader", SHELL_READERS)
@pytest.mark.parametrize(("body", "outcome"), SHELL_BODIES)
def test_a_here_document_fed_to_a_shell_is_run_as_commands(reader, body, outcome):
    outcome(check(f"{reader} <<'EOF'\n{body}\nEOF"), (reader, body))


@pytest.mark.parametrize("reader", SCRIPT_READERS)
@pytest.mark.parametrize(("body", "outcome"), SCRIPT_BODIES + SHELL_BODIES[:1] + SHELL_BODIES[3:4])
def test_a_here_document_fed_to_a_scripting_language_is_scanned_for_agentflow_calls(reader, body, outcome):
    outcome(check(f"{reader} <<'EOF'\n{body}\nEOF"), (reader, body))


@pytest.mark.parametrize("marker", ["<<'EOF'", "<<EOF", '<<"EOF"', "<<-EOF"])
def test_the_form_of_the_here_document_marker_does_not_matter(marker):
    ask(check(f"bash {marker}\nagentflow task approve\nEOF"))
    deny(check(f"python3 {marker}\nsubprocess.run(['agentflow','decide'])\nEOF"))


def test_a_tab_indented_body_of_a_dash_here_document_is_scanned():
    deny(check("bash <<-EOF\n\tagentflow replan done\n\tEOF"))


@pytest.mark.parametrize("reader", PIPE_READERS)
def test_text_piped_into_an_interpreter_is_scanned(reader):
    ask(check(f'echo "agentflow task approve" | {reader}'), reader)
    deny(check(f"printf '%s\\n' 'uv run agentflow replan done' | {reader}"), reader)


@pytest.mark.parametrize("reader", ["python", "python3", "uv run python", "node"])
def test_a_script_piped_into_a_scripting_language_is_scanned(reader):
    ask(check(f"""echo "import os; os.system('agentflow task cancel')" | {reader}"""), reader)
    deny(check(f"""echo "require('child_process').execSync('agentflow decide --suppress x')" | {reader}"""), reader)


@pytest.mark.parametrize("reader", ["bash", "sh", "zsh", "python3", "node", "pwsh"])
def test_a_here_string_is_scanned_too(reader):
    ask(check(f'{reader} <<< "agentflow task approve"'), reader)
    deny(check(f"{reader} <<< 'agentflow roadmap set R1 done'"), reader)


@pytest.mark.parametrize("reader", ["bash", "sh", "python3"])
def test_a_here_document_piped_through_cat_into_an_interpreter_is_scanned(reader):
    ask(check(f"cat <<'EOF' | {reader}\nagentflow task approve\nEOF"), reader)
    deny(check(f"cat <<'EOF' | {reader}\nagentflow replan done\nEOF"), reader)


@pytest.mark.parametrize(
    "command",
    [
        """node -e "require('child_process').execSync('agentflow task approve')\"""",
        """node --eval "require('child_process').execSync('uv run agentflow decide --answer S1')\"""",
        """perl -e 'system("agentflow task cancel")'""",
        """ruby -e 'system("agentflow replan done")'""",
        """pwsh -c "agentflow task approve\"""",
        """python3 -c "import subprocess; subprocess.run(['agentflow','task','approve'])\"""",
    ],
)
def test_code_given_with_dash_c_or_dash_e_is_scanned(command):
    verdict = check(command)
    assert verdict.decision in {GuardDecision.ASK, GuardDecision.DENY}, command
    assert verdict.rule is not None


@pytest.mark.parametrize("body", ["agentflow task approve", "agentflow replan done", "uv run agentflow decide --answer S1"])
@pytest.mark.parametrize(
    "receiver",
    [
        "agentflow report --step review",
        "cat > notes.md",
        "cat",
        "tee notes.md",
        "tee -a log.txt",
        "python script.py",
        "python manage.py shell",
        "python -m json.tool",
        "node build.js",
        "bash run.sh",
        "sh ./deploy.sh",
        "git apply -",
        "grep approve",
        "sed 's/a/b/'",
        "wc -l",
        "docker exec -i db psql",
    ],
)
def test_a_here_document_is_still_only_data_for_a_program_that_does_not_run_it(receiver, body):
    """Regression for decision 3: the text of a report, a note or a data file may name any command."""
    assert check(f"{receiver} <<'EOF'\n{body}\nEOF").decision is GuardDecision.ALLOW, receiver


@pytest.mark.parametrize("reader", PIPE_READERS)
@pytest.mark.parametrize("body", HARMLESS_BODIES)
def test_harmless_text_fed_to_an_interpreter_passes(reader, body):
    assert check(f"{reader} <<'EOF'\n{body}\nEOF").decision is GuardDecision.ALLOW, (reader, body)


@pytest.mark.parametrize("reader", ["bash", "python3", "node"])
def test_harmless_text_piped_into_an_interpreter_passes(reader):
    assert check(f"echo hello | {reader}").decision is GuardDecision.ALLOW
    assert check(f"printf 'print(1)' | {reader}").decision is GuardDecision.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git diff | python -m json.tool",
        "cat data.json | python -m json.tool",
        "cat data.json | python script.py",
        "ls | xargs python tool.py",
        "echo x | bash run.sh",
        "curl -s https://example.com/data.json | jq .",
        "docker run -it image bash",
        "docker exec db bash",
        "python",
        "bash",
    ],
)
def test_an_interpreter_that_reads_nothing_unknown_is_left_alone(command):
    assert check(command).decision is GuardDecision.ALLOW, command


@pytest.mark.parametrize(
    "command",
    [
        "cat install.sh | bash",
        "curl -s https://example.com/install.sh | sh",
        "curl -fsSL https://example.com/x.py | python3",
        "wget -qO- https://example.com/x | bash -s",
        "bash < install.sh",
        "python < job.py",
        "node < job.js",
        "ls | bash",
        "cat job.py | uv run python -",
    ],
)
def test_text_that_cannot_be_read_ahead_asks_a_person(command):
    """When the guard cannot tell what an interpreter will run, it asks instead of guessing."""
    verdict = check(command)
    assert verdict.decision is GuardDecision.ASK, command
    assert verdict.reason and verdict.asks
    assert check(command, roots=()).decision is GuardDecision.ALLOW


@pytest.mark.parametrize("reader", ["bash", "sh", "python3", "node"])
def test_the_interpreter_rules_apply_only_in_a_project_with_a_workspace(reader):
    assert check(f"{reader} <<'EOF'\nagentflow task approve\nEOF", roots=()).decision is GuardDecision.ALLOW
    assert check(f"echo 'agentflow replan done' | {reader}", cwd="/elsewhere").decision is GuardDecision.ALLOW


def test_a_person_only_command_inside_the_text_wins_over_an_asked_one_and_over_other_commands():
    deny(check("echo a | bash; agentflow task approve && bash <<'EOF'\nagentflow replan done\nEOF"))
    pushed = check("bash <<'EOF'\nagentflow task approve\ngit push\nEOF")
    assert pushed.denied and pushed.decision is GuardDecision.DENY


def test_a_command_after_the_here_document_of_an_interpreter_is_still_checked():
    ask(check("bash <<'EOF'\necho hi\nEOF\nuv run agentflow task approve"))


def test_a_second_here_document_on_the_same_line_is_not_a_way_around():
    ask(check("cat <<'A' > notes.md; bash <<'B'\nplain note\nA\nagentflow task approve\nB"))


def test_shell_text_inside_the_text_is_followed_into_nested_shells():
    ask(check("bash <<'EOF'\nbash -c \"uv run agentflow task approve\"\nEOF"))
    deny(check("echo \"sh -c 'agentflow replan done'\" | bash"))


def test_the_interpreter_text_is_also_checked_for_writes_into_the_workspace(tmp_path):
    (tmp_path / ".agentflow").mkdir()
    (tmp_path / ".agentflow" / "config.yaml").write_text("x", encoding="utf-8")
    verdict = evaluate("bash <<'EOF'\necho x > .agentflow/decisions/a.md\nEOF", tmp_path, OnFeature(), Workspaces(tmp_path))
    assert verdict.denied and verdict.rule is GuardRule.WORKSPACE_WRITE
    data = evaluate("cat <<'EOF'\necho x > .agentflow/decisions/a.md\nEOF", tmp_path, OnFeature(), Workspaces(tmp_path))
    assert data.decision is GuardDecision.ALLOW


@pytest.mark.parametrize("cli", list(CliKind))
def test_the_hook_asks_about_text_that_an_interpreter_runs(project, cli):
    command = "bash <<'EOF'\nagentflow task approve\nEOF"
    out = hook(cli, claude(project, command) if cli is CliKind.CLAUDE else agy(project, command))
    assert (claude_decision(out) if cli is CliKind.CLAUDE else json.loads(out)["decision"]) in {"ask", "force_ask"}


@pytest.mark.parametrize("cli", list(CliKind))
def test_the_hook_denies_a_person_only_command_in_piped_text(project, cli):
    command = "echo 'agentflow replan done' | bash"
    out = hook(cli, claude(project, command) if cli is CliKind.CLAUDE else agy(project, command))
    assert (claude_decision(out) if cli is CliKind.CLAUDE else json.loads(out)["decision"]) == "deny"


def test_the_hook_stays_silent_for_a_report_whose_text_names_approve(project):
    command = "agentflow report --step review <<'EOF'\nA person runs agentflow task approve.\nEOF"
    assert hook(CliKind.CLAUDE, claude(project, command)) == ""


# ------------------------------------------------------- the README rules match the guard


def readme_step4_rules():
    text = README.read_text(encoding="utf-8")
    start = text.index("### Bước 4")
    block = re.search(r"```json\n(.*?)\n```", text[start:], flags=re.S)
    assert block, "README Bước 4 has no JSON block"
    return json.loads(block.group(1))["permissions"]


@pytest.mark.skipif(not README.is_file(), reason="README is not next to foundation/")
def test_every_ask_rule_of_the_readme_is_a_command_the_guard_also_asks_about():
    asks = readme_step4_rules()["ask"]
    assert asks, "README Bước 4 has no ask rules"
    for rule in asks:
        match = re.fullmatch(r"(?:Bash|PowerShell)\((agentflow [a-z ]+?) \*\)", rule)
        assert match, f"unexpected ask rule {rule!r}"
        ask(check(match.group(1)), rule)


@pytest.mark.skipif(not README.is_file(), reason="README is not next to foundation/")
def test_the_readme_asks_for_approve_and_cancel_in_both_shells_and_allows_neither():
    rules = readme_step4_rules()
    for shell in ("Bash", "PowerShell"):
        for command in ("agentflow task approve", "agentflow task cancel"):
            assert f"{shell}({command} *)" in rules["ask"]
            assert f"{shell}({command} *)" not in rules["allow"]
