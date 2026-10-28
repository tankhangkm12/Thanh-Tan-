"""Decide whether one shell command an agent wants to run is allowed.

The guard reads the command the way a shell would split it, finds every git
invocation in it (also inside chains, pipes, ``bash -c "..."`` and similar), and
denies the ones that publish work, rewrite or drop it, or commit straight onto a
protected branch. It also finds the `agentflow` commands that give a person's decision: the ones only a person runs
are denied, and `task approve` / `task cancel` make the CLI ask the person. It reads `agentflow` however it is
started (`uv run`, `python -m`, wrappers, environment prefixes, `Start-Process`) and reads the text an interpreter is
given (here-document, pipe, here-string, `-c`). It is a safety net for agents, not a sandbox: git aliases, variables,
scripts and environment tricks can still get around it.
"""

import json
import os
import re
import shlex
from collections.abc import Collection
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agentflow.constants import (
    AGENTFLOW_PROGRAM,
    APPROVAL_TAG_PREFIX,
    GIT_EXECUTABLE,
    TAG_REF_PREFIX,
    PROTECTED_BRANCHES,
    ExitCode,
    GuardDecision,
    GuardKey,
    GuardRule,
)
from agentflow import gitpaths
from agentflow.errors import AgentflowError
from agentflow.interfaces import BranchLookup, WorkspaceLookup, WriteTargetPolicy
from agentflow.models import GuardVerdict
from agentflow.lockguard import GuardedPaths
from agentflow.scriptscan import mentioned_commands

# ------------------------------------------------------------ tokenizing

# Characters that end a token and, alone or in runs, separate commands
# (`&&`, `||`, `;`, `|`, `&`, newlines, subshells, blocks, backticks, redirections).
_PUNCTUATION = "();<>|&\n`{}"
_WHITESPACE = " \t\r"
_FALLBACK_TOKENS = re.compile(r"[^\s();<>|&`{}]+|[();<>|&`{}\n]+")
_EXECUTABLE_SUFFIX = ".exe"
_PATH_SEPARATORS = re.compile(r"[\\/]")
_MAX_NESTING = 5
_LEFTOVER_QUOTING = "\\\"'"

# Programs that run their argument as another command line, and the flags that introduce it.
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "pwsh", "powershell", "cmd"})
_SHELL_COMMAND_FLAGS = frozenset({"-c", "-command", "/c", "/k"})
_EVALUATORS = frozenset({"eval", "iex", "invoke-expression"})
# `bash -lc "..."`, `sh -ec "..."`: bundled short flags that end in `c`.
_BUNDLED_COMMAND_FLAG = re.compile(r"^-[a-z]{1,3}c$")
_CHANGE_DIRECTORY = frozenset({"cd", "chdir", "pushd", "set-location", "sl"})
# cmd.exe's `cd /d <dir>` also changes drive.
_CMD_DRIVE_FLAG = "/d"

# ----------------------------------------------------------------- git cli

# Global options placed before the subcommand that take a separate value.
_GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"})
_GIT_DIRECTORY_OPTION = "-C"
_LONG_PREFIX = "--"
_SHORT_PREFIX = "-"
_END_OF_OPTIONS = "--"

_PUSH = "push"
_RESET = "reset"
_CLEAN = "clean"
_BRANCH = "branch"
_TAG = "tag"
_COMMIT = "commit"
_UPDATE_REF = "update-ref"
# Commands only a person runs (an agent would be granting itself decisions), as their leading words.
_PERSON_ONLY = frozenset(
    {
        ("decide",), ("ext", "add"), ("ext", "sync"), ("config", "set"), ("task", "seal"), ("project", "confirm"),
        ("knowledge", "init"), ("knowledge", "pull"), ("knowledge", "push"),
        ("role", "grant"), ("role", "revoke"), ("role", "sync"), ("roadmap", "set"),
        ("replan", "done"), ("replan", "skip"), ("state", "accept"), ("tests", "amend"),
    }  # fmt: skip
)
# Commands that need a person's yes at a prompt (the agent cannot give it); the person-only ones are denied instead.
_ASKED = frozenset({("task", "approve"), ("task", "cancel")})
_SWITCH = "switch"
_CHECKOUT = "checkout"
# Subcommands that write commits onto the checked-out branch.
_COMMITTING = frozenset({"commit", "merge", "rebase", "cherry-pick", "revert", "am"})
_STOP_FLAGS = frozenset({"--abort", "--quit"})

_HARD = "--hard"
_FORCE_LONG = "--force"
_DELETE_LONG = "--delete"
_FORCE_SHORT = "f"
_DIRECTORIES_SHORT = "d"
_DELETE_SHORT = "d"
_FORCE_DELETE_SHORT = "D"

_SWITCH_CREATE = frozenset({"-c", "-C", "--create", "--force-create", "--orphan"})
_CHECKOUT_CREATE = frozenset({"-b", "-B", "--orphan"})
_DETACH = frozenset({"--detach"})
_SWITCH_DETACH_SHORT = "-d"

REASONS = {
    GuardRule.PUSH: "git push is blocked for agents: a person pushes",
    GuardRule.PROTECTED_BRANCH: "git {subcommand} on '{branch}' is blocked: work on the task branch "
    "(`agentflow task new`) and let a person merge",
    GuardRule.RESET_HARD: "git reset --hard is blocked: it throws away work",
    GuardRule.CLEAN_FORCE_DIRS: "git clean with -f and -d is blocked: it deletes untracked files and directories",
    GuardRule.BRANCH_FORCE_DELETE: "force-deleting a branch is blocked",
    GuardRule.TAG_DELETE: "deleting a tag is blocked",
    GuardRule.DIRECT_COMMIT: "git commit is blocked in an agentflow project: stage files and use `agentflow commit`",
    GuardRule.APPROVAL_TAG: "tags under 'agentflow/' are written by `agentflow task approve` only",
    GuardRule.PERSON_ONLY: "`agentflow {command}` is for a person: ask them to run it themselves (in Claude Code: `! agentflow {command} ...`)",
}

REASONS[GuardRule.PERSON_CONFIRMS] = (
    "`agentflow {command}` records a person's decision: a person must confirm it at the prompt "
    "(the agent cannot answer for them); do not try again, ask the person"
)
REASONS[GuardRule.SCRIPT_UNREAD] = (
    "this command gives an interpreter text the guard cannot read ahead ({source}); it could run `agentflow task approve` "
    "or another command that is a person's, so a person must confirm it"
)
REASONS[GuardRule.LOCKED_FILE] = (
    "this file belongs to the tests a person approved (the test files, the test infrastructure or the test configuration of the "
    "project): no tool or command of an agent changes, deletes, renames or adds it. If a test looks wrong, stop and tell the person: "
    'only a person changes it, with `agentflow tests amend <file> --reason "..."`'
)
REASONS[GuardRule.WORKSPACE_WRITE] = (
    "files under .ThanhTan/ (and the project-* agents in .claude/agents/ that `agentflow role` generates) are written by "
    "agentflow only: use the `agentflow` commands (or its MCP tools), never edit or write there by hand"
)

ALLOW = GuardVerdict(GuardDecision.ALLOW)

# ------------------------------------------------------- writes into .ThanhTan/
# Best effort: the commands people and models usually write files with. Scripts and interpreters (`python -c`,
# `node -e`), aliases and variables are not followed; see docs/architecture.md.

_REDIRECT_CHAR = ">"
_FD_DUPLICATE_SUFFIX = "&"
# Programs whose every path argument is changed (written, created, deleted or moved away).
_CHANGES_ARGUMENTS = frozenset(
    {
        "tee", "touch", "truncate", "shred", "unlink", "mkdir", "md",
        "rm", "del", "erase", "rd", "rmdir", "ri", "remove-item",
        "mv", "move", "mi", "move-item", "ren", "rename", "rni", "rename-item",
        "set-content", "sc", "add-content", "ac", "out-file", "clear-content", "clc", "new-item", "ni",
    }
)  # fmt: skip
# Programs that only change their last argument (the destination).
_COPIES = frozenset({"cp", "copy", "cpi", "copy-item", "xcopy", "robocopy"})
_COPY_TARGET_OPTIONS = frozenset({"-t", "--target-directory", "-destination"})
_SED = "sed"
_IN_PLACE_PREFIXES = ("-i", "--in-place")
_DD = "dd"
_DD_OUTPUT = "of="
_MKDIR_ALIASES = frozenset({"mkdir", "md"})
_HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(?:(['\"])(\w+)\2|(\w+))")
_TABS = "\t"

# ------------------------------------------------------- how a program is launched
# Programs that run the next program: `timeout 5 agentflow`, `xargs -n1 uv run agentflow`. For each: the options that
# take a value, and whether the first plain word is a number (a duration) that belongs to the wrapper.
_WRAPPERS = {
    "timeout": (frozenset({"-s", "--signal", "-k", "--kill-after"}), True),
    "nice": (frozenset({"-n", "--adjustment"}), False),
    "env": (frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}), False),
    "xargs": (frozenset({"-n", "-I", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs", "--delimiter"}), False),
    "sudo": (frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U"}), False),
    "stdbuf": (frozenset(), False),
    "nohup": (frozenset(), False),
    "time": (frozenset(), False),
    "command": (frozenset(), False),
    "builtin": (frozenset(), False),
    "exec": (frozenset({"-a"}), False),
    "setsid": (frozenset(), False),
}  # fmt: skip
_UV = "uv"
_UVX = "uvx"
_UV_VALUE_OPTIONS = frozenset(
    {
        "--project", "--with", "--python", "-p", "--directory", "--from", "--with-requirements", "--with-editable",
        "--env-file", "--extra", "--group", "--package", "--index", "--index-url", "--exclude-newer", "--cache-dir",
        "--config-file", "-w", "--no-extra", "--only-group", "--no-group", "--default-index", "--extra-index-url",
    }
)  # fmt: skip
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^(python|pypy|py)[\d.]*$")
_OTHER_SCRIPT_INTERPRETERS = frozenset({"node", "nodejs", "deno", "bun", "ruby", "perl", "php", "lua", "rscript"})
_PYTHON_VALUE_OPTIONS = frozenset({"-W", "-X", "-Q"})
_MODULE_FLAG = "-m"
_NUMBER = re.compile(r"^\d")
_TOOL = "tool"
_RUN = "run"
# `Start-Process agentflow -ArgumentList 'task approve'`
_START_PROCESS = frozenset({"start-process", "saps"})
_START_VALUE_FLAGS = frozenset(
    {"-workingdirectory", "-wd", "-verb", "-redirectstandardinput", "-redirectstandardoutput", "-redirectstandarderror", "-windowstyle", "-credential"}
)  # fmt: skip
_START_FILE_FLAGS = frozenset({"-filepath", "-path"})
_START_ARGUMENT_FLAGS = frozenset({"-argumentlist", "-args"})
_ARGUMENT_SPLIT = re.compile(r"[,\s]+")
# Flags that hand a program its code on the command line, and the ones that name a module or a script file instead.
_INLINE_CODE_FLAGS = frozenset({"-c", "-e", "--eval", "-p", "--print", "-r"})
_CODE_OR_FILE_FLAGS = _INLINE_CODE_FLAGS | frozenset({"-m", "-command", "-file", "-encodedcommand", "/c", "/k"})
_STDIN_MARKER = "-"
# What fills the standard input of the next command in a line.
_PIPES = ("|", "|&")
_HERE_STRING = "<<<"
_HERE_DOCUMENT = "<<"
_INPUT_FILE = "<"
# Producers whose text is known before they run.
_ECHOES = frozenset({"echo", "printf", "write-output", "write-host", "write"})
_ECHO_OPTIONS = re.compile(r"^-[neE]+$")
_CAT = "cat"


@dataclass
class _Context:
    """What the guard knows while walking a command line left to right."""

    cwd: Path
    branches: BranchLookup
    workspaces: WorkspaceLookup | None = None
    # Branches the command line itself switched to, per repository directory (None = detached).
    switched: dict[Path, str | None] = field(default_factory=dict)
    writes: WriteTargetPolicy = field(default_factory=GuardedPaths)
    # Branches nobody commits on but a person: main and develop, plus the ones the project named (see gitconfig.py).
    protected: frozenset[str] = PROTECTED_BRANCHES

    def in_workspace(self, directory: Path) -> bool:
        return self.workspaces is not None and self.workspaces.has_workspace(directory)

    def branch_of(self, directory: Path) -> str | None:
        if directory in self.switched:
            return self.switched[directory]
        return self.branches.current_branch(directory)


def evaluate(
    command: str,
    cwd: Path,
    branches: BranchLookup,
    workspaces: WorkspaceLookup | None = None,
    writes: WriteTargetPolicy | None = None,
    protected_branches: Collection[str] | None = None,
) -> GuardVerdict:
    start = Path(os.path.normpath(cwd))
    protected = PROTECTED_BRANCHES | frozenset(protected_branches or ())
    context = _Context(start, branches, workspaces, writes=writes or GuardedPaths(), protected=protected)
    verdict = _evaluate_whole(command, context, depth=0)
    if verdict.denied:
        return verdict
    writes = _evaluate_writes(_without_heredoc_bodies(command), start, context.writes, depth=0)
    if not writes.denied:
        writes = _evaluate_git_text(command, start, context.writes)
    return writes if writes.denied else verdict


def writes_into_workspace(target: Path | str, cwd: Path, writes: WriteTargetPolicy | None = None) -> GuardVerdict:
    """Verdict for a file-writing tool (not a shell command) that is about to change ``target``."""
    rule = _protection([os.fspath(target)], cwd, writes or GuardedPaths())
    return ALLOW if rule is None else _deny(rule)


def _protection(paths: list[str], cwd: Path, writes: WriteTargetPolicy) -> GuardRule | None:
    """The rule that keeps an agent away from the first of ``paths`` that is protected: a lock or the workspace."""
    for path in paths:
        if writes.is_protected(path, cwd):
            locked = getattr(writes, "locked", None)
            return GuardRule.LOCKED_FILE if locked is not None and locked(path, cwd) else GuardRule.WORKSPACE_WRITE
    return None


def _merge(first: GuardVerdict, second: GuardVerdict) -> GuardVerdict:
    """A denial wins over a question, and a question over nothing; among equals the first one stands."""
    if first.denied or second.decision is GuardDecision.ALLOW:
        return first
    if second.denied or first.decision is GuardDecision.ALLOW:
        return second
    return first


def _evaluate_whole(command: str, context: _Context, depth: int) -> GuardVerdict:
    """``command`` as a shell would run it: the lines, and the text its here-documents hand to interpreters."""
    stripped, documents = _heredocs(command)
    verdict = _evaluate(stripped, context, depth)
    for document in documents:
        if verdict.denied:
            break
        verdict = _merge(verdict, _evaluate_here_document(document, context, depth))
    return verdict


def _evaluate(command: str, context: _Context, depth: int) -> GuardVerdict:
    parts = _parts(command)
    verdict = ALLOW
    for index, part in enumerate(parts):
        verdict = _merge(verdict, _evaluate_segment(part.tokens, context, depth))
        if not verdict.denied:
            verdict = _merge(verdict, _evaluate_input(parts, index, context, depth))
        if verdict.denied:
            return verdict
    return verdict


@dataclass
class _Part:
    """One simple command of a line and the separator that came right before it (``|``, ``<<<``, ``&&``...)."""

    tokens: list[str]
    before: str | None = None


def _parts(command: str) -> list[_Part]:
    parts: list[_Part] = []
    current: list[str] = []
    before: str | None = None
    separator: str | None = None
    for token in _tokens(command):
        if token and all(char in _PUNCTUATION for char in token):
            if current:
                parts.append(_Part(current, before))
                current = []
            separator = token
        else:
            if not current:
                before = separator
                separator = None
            current.append(token)
    if current:
        parts.append(_Part(current, before))
    return parts


def split_commands(command: str) -> list[list[str]]:
    """Tokens of each simple command in ``command``, split at separators outside quotes."""
    return [part.tokens for part in _parts(command)]


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=_PUNCTUATION)
    lexer.whitespace = _WHITESPACE
    lexer.whitespace_split = True
    lexer.escape = ""  # keep Windows paths intact
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:  # unbalanced quotes: fall back to a rough split
        return _FALLBACK_TOKENS.findall(command)


def _bare(token: str) -> str:
    """Token without leftover quotes or backslashes from escaped quoting (``\\"git push\\"``)."""
    return token.strip(_LEFTOVER_QUOTING)


def _program(token: str) -> str:
    name = _PATH_SEPARATORS.split(_bare(token))[-1].lower()
    return name.removesuffix(_EXECUTABLE_SUFFIX)


def _evaluate_segment(tokens: list[str], context: _Context, depth: int) -> GuardVerdict:
    first = _program(tokens[0])
    if first in _CHANGE_DIRECTORY:
        target = next(
            (token for token in tokens[1:] if not token.startswith(_SHORT_PREFIX) and token.lower() != _CMD_DRIVE_FLAG),
            None,
        )
        if target is not None:
            context.cwd = _join(context.cwd, target)
        return ALLOW
    verdict = ALLOW
    launched = _launched_agentflow(tokens)
    if launched is not None:
        verdict = _evaluate_agentflow([_bare(token) for token in tokens[launched:]], context)
        if verdict.denied:
            return verdict
    inline = _inline_code(tokens)
    if inline is not None:
        verdict = _merge(verdict, _scan_script(inline, context))
        if verdict.denied:
            return verdict
    for index, token in enumerate(tokens):
        program = _program(token)
        if depth < _MAX_NESTING and _runs_nested_command(program, tokens, index):
            nested = " ".join(tokens[_nested_start(program, tokens, index) :])
            verdict = _merge(verdict, _evaluate(nested, context, depth + 1))
        if program == GIT_EXECUTABLE:
            verdict = _merge(verdict, _evaluate_git([_bare(token) for token in tokens[index + 1 :]], context))
        elif program in _START_PROCESS:
            verdict = _merge(verdict, _evaluate_start_process(tokens[index + 1 :], context))
        if verdict.denied:
            return verdict
    return verdict


# ------------------------------------------------------- the program that really runs


def _skip_options(tokens: list[str], position: int, with_value: frozenset[str]) -> int:
    """Position after the options that start at ``position``; ``--`` ends them."""
    while position < len(tokens) and _bare(tokens[position]).startswith(_SHORT_PREFIX):
        option = _bare(tokens[position])
        if option == _END_OF_OPTIONS:
            return position + 1
        position += 2 if option in with_value else 1
    return position


def _final_program(tokens: list[str]) -> int | None:
    """Index of the program that runs once wrappers, environment assignments and ``uv run`` are looked through."""
    position = 0
    while position < len(tokens):
        word = _bare(tokens[position])
        if _ENV_ASSIGNMENT.match(word):
            position += 1
            continue
        program = _program(word)
        if program in _WRAPPERS:
            with_value, duration = _WRAPPERS[program]
            position = _skip_options(tokens, position + 1, with_value)
            if duration and position < len(tokens) and _NUMBER.match(_bare(tokens[position])):
                position += 1
        elif program == _UV:
            following = [_bare(token) for token in tokens[position + 1 : position + 3]]
            if following[:2] == [_TOOL, _RUN]:
                position += 3
            elif following[:1] == [_RUN]:
                position += 2
            else:
                return None
            position = _skip_options(tokens, position, _UV_VALUE_OPTIONS)
        elif program == _UVX:
            position = _skip_options(tokens, position + 1, _UV_VALUE_OPTIONS)
        else:
            return position
    return None


def _launched_agentflow(tokens: list[str]) -> int | None:
    """Position of the first argument of ``agentflow`` when ``tokens`` start it (directly or through a launcher)."""
    position = _final_program(tokens)
    if position is None:
        return None
    program = _program(tokens[position])
    if program == AGENTFLOW_PROGRAM:
        return position + 1
    if _PYTHON.match(program):
        position += 1
        while position < len(tokens) and _bare(tokens[position]).startswith(_SHORT_PREFIX):
            option = _bare(tokens[position])
            if option == _MODULE_FLAG:
                module = _bare(tokens[position + 1]) if position + 1 < len(tokens) else ""
                return position + 2 if module == AGENTFLOW_PROGRAM or module.startswith(AGENTFLOW_PROGRAM + ".") else None
            position += 2 if option in _PYTHON_VALUE_OPTIONS else 1
    return None


def _is_script_interpreter(program: str) -> bool:
    return bool(_PYTHON.match(program)) or program in _OTHER_SCRIPT_INTERPRETERS


def _is_command_flag(token: str) -> bool:
    return token.lower() in _SHELL_COMMAND_FLAGS or bool(_BUNDLED_COMMAND_FLAG.match(token))


def _inline_code(tokens: list[str]) -> str | None:
    """The code given on the command line to a scripting language (``python -c "..."``, ``node -e "..."``)."""
    position = _final_program(tokens)
    if position is None or not _is_script_interpreter(_program(tokens[position])):
        return None
    for index in range(position + 1, len(tokens) - 1):
        if _bare(tokens[index]) in _INLINE_CODE_FLAGS:
            return tokens[index + 1]
    return None


def _evaluate_start_process(args: list[str], context: _Context) -> GuardVerdict:
    """``Start-Process agentflow -ArgumentList 'task approve'`` and the same with a launcher as the file."""
    file: str | None = None
    arguments: str | None = None
    position = 0
    while position < len(args):
        word = _bare(args[position])
        flag = word.lower()
        if flag in _START_FILE_FLAGS and position + 1 < len(args):
            file, position = _bare(args[position + 1]), position + 2
        elif flag in _START_ARGUMENT_FLAGS and position + 1 < len(args):
            arguments, position = _bare(args[position + 1]), position + 2
        elif flag in _START_VALUE_FLAGS:
            position += 2
        elif word.startswith(_SHORT_PREFIX):
            position += 1
        else:
            if file is None:
                file = word
            elif arguments is None:
                arguments = word
            position += 1
    if file is None:
        return ALLOW
    words = [file, *(part for part in _ARGUMENT_SPLIT.split(arguments or "") if part)]
    launched = _launched_agentflow(words)
    if launched is None:
        return ALLOW
    return _evaluate_agentflow(words[launched:], context)


@dataclass
class _HereDocument:
    """A here-document: the text before its marker on the line, the text after, and the body."""

    prefix: str
    rest: str
    body: str


def _heredocs(command: str) -> tuple[str, list[_HereDocument]]:
    """``command`` without the bodies of its here-documents, and those bodies with the commands they are given to."""
    lines = command.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    documents: list[_HereDocument] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        matches = list(_HEREDOC.finditer(line))
        for number, match in enumerate(matches):
            delimiter = match.group(3) or match.group(4)
            strip_tabs = match.group(1) == "-"
            body: list[str] = []
            while index < len(lines):
                text = lines[index]
                index += 1
                if (text.lstrip(_TABS) if strip_tabs else text) == delimiter:
                    break
                body.append(text)
            begin = matches[number - 1].end() if number else 0
            stop = matches[number + 1].start() if number + 1 < len(matches) else len(line)
            documents.append(_HereDocument(line[begin : match.start()], line[match.end() : stop], "\n".join(body)))
    return "\n".join(kept), documents


def _without_heredoc_bodies(command: str) -> str:
    """``command`` with the text of here-documents removed: it is data for the command that reads it."""
    return _heredocs(command)[0]


# ----------------------------------------------- text that an interpreter runs


def _reads_stdin(args: list[str]) -> bool:
    """Whether an interpreter started with ``args`` runs the text it is given on its standard input."""
    if _STDIN_MARKER in args:
        return True
    if any(arg.lower() in _CODE_OR_FILE_FLAGS or _is_command_flag(arg) for arg in args):
        return False
    return not [arg for arg in args if not arg.startswith(_SHORT_PREFIX)]


def _stdin_reader(tokens: list[str]) -> bool:
    position = _final_program(tokens)
    if position is None:
        return False
    program = _program(tokens[position])
    if program not in _SHELLS and not _is_script_interpreter(program):
        return False
    return _reads_stdin([_bare(token) for token in tokens[position + 1 :]])


def _evaluate_input(parts: list[_Part], index: int, context: _Context, depth: int) -> GuardVerdict:
    """What the command at ``index`` is given on its standard input (a pipe, a here-string, a file), when it runs it."""
    part = parts[index]
    if not _stdin_reader(part.tokens) or not context.in_workspace(context.cwd):
        return ALLOW
    following = parts[index + 1] if index + 1 < len(parts) else None
    if following is not None and following.before == _HERE_STRING:
        return _scan_input(" ".join(following.tokens), context, depth)
    if following is not None and following.before == _INPUT_FILE:
        return _unread(f"a file: {' '.join(following.tokens)}")
    if following is not None and following.before == _HERE_DOCUMENT:
        return ALLOW  # the body is judged with the here-document
    if part.before in _PIPES and index > 0:
        producer = parts[index - 1]
        if producer.before == _HERE_DOCUMENT:
            return ALLOW  # `cat <<EOF | bash`: the body is judged with the here-document
        return _evaluate_producer(producer.tokens, context, depth)
    return ALLOW


def _evaluate_producer(tokens: list[str], context: _Context, depth: int) -> GuardVerdict:
    program = _program(tokens[0])
    if program not in _ECHOES:
        return _unread(f"the output of `{program}`")
    words = tokens[1:]
    while words and _ECHO_OPTIONS.match(words[0]):
        words = words[1:]
    return _scan_input(" ".join(words), context, depth)


def _evaluate_here_document(document: _HereDocument, context: _Context, depth: int) -> GuardVerdict:
    """The body of a here-document is data, unless the command it is given to runs what it reads."""
    if not context.in_workspace(context.cwd):
        return ALLOW
    receivers = split_commands(document.prefix)
    if not receivers:
        return ALLOW
    runs = _stdin_reader(receivers[-1])
    if not runs and _program(receivers[-1][0]) == _CAT and document.rest.lstrip().startswith(_PIPES):
        next_commands = split_commands(document.rest)
        runs = bool(next_commands) and _stdin_reader(next_commands[0])
    return _scan_input(document.body, context, depth) if runs else ALLOW


def _scan_input(text: str, context: _Context, depth: int) -> GuardVerdict:
    """Text that will run as a program: read it as a script and as a command line."""
    verdict = _scan_script(text, context)
    if verdict.denied or depth >= _MAX_NESTING:
        return verdict
    inner = replace(context, switched=dict(context.switched))
    verdict = _merge(verdict, _evaluate_whole(text, inner, depth + 1))
    if verdict.denied:
        return verdict
    writes = _evaluate_writes(_without_heredoc_bodies(text), context.cwd, context.writes, depth + 1)
    return writes if writes.denied else verdict


def _scan_script(text: str, context: _Context) -> GuardVerdict:
    """The verdict for a script that calls ``agentflow``: its words are looked for, its syntax is not followed."""
    if not context.in_workspace(context.cwd):
        return ALLOW
    found = mentioned_commands(text, [*sorted(_PERSON_ONLY), *sorted(_ASKED)])
    person_only = next((command for command in found if command in _PERSON_ONLY), None)
    if person_only is not None:
        return _deny(GuardRule.PERSON_ONLY, command=" ".join(person_only))
    asked = next((command for command in found if command in _ASKED), None)
    return ALLOW if asked is None else _ask(GuardRule.PERSON_CONFIRMS, command=" ".join(asked))


def _unread(source: str) -> GuardVerdict:
    return _ask(GuardRule.SCRIPT_UNREAD, source=source)


@dataclass
class _Simple:
    """One simple command: its words, and the files its redirections write to."""

    words: list[str] = field(default_factory=list)
    redirects: list[str] = field(default_factory=list)


def _simple_commands(command: str) -> list[_Simple]:
    commands: list[_Simple] = []
    current = _Simple()
    redirecting = False
    for token in _tokens(command):
        if token and all(char in _PUNCTUATION for char in token):
            if _REDIRECT_CHAR in token and not token.endswith(_FD_DUPLICATE_SUFFIX):
                redirecting = True
                continue
            redirecting = False
            if current.words or current.redirects:
                commands.append(current)
            current = _Simple()
        elif redirecting:
            current.redirects.append(token)
            redirecting = False
        else:
            current.words.append(token)
    if current.words or current.redirects:
        commands.append(current)
    return commands


def _evaluate_writes(command: str, cwd: Path, writes: WriteTargetPolicy, depth: int) -> GuardVerdict:
    for simple in _simple_commands(command):
        if simple.words and _program(simple.words[0]) in _CHANGE_DIRECTORY:
            target = next((t for t in simple.words[1:] if not t.startswith(_SHORT_PREFIX) and t.lower() != _CMD_DRIVE_FLAG), None)
            if target is not None:
                cwd = _join(cwd, target)
            continue
        paths = [_bare(path) for path in [*simple.redirects, *_changed_paths(simple.words)]]
        rule = _protection(paths, cwd, writes)
        if rule is not None:
            return _deny(rule)
        for index, token in enumerate(simple.words):
            program = _program(token)
            if depth < _MAX_NESTING and _runs_nested_command(program, simple.words, index):
                nested = " ".join(simple.words[_nested_start(program, simple.words, index) :])
                verdict = _evaluate_writes(_without_heredoc_bodies(nested), cwd, writes, depth + 1)
                if verdict.denied:
                    return verdict
    return ALLOW


def _changed_paths(words: list[str]) -> list[str]:
    """Path arguments of ``words`` that the program would write, create, delete or move away."""
    if not words:
        return []
    program, args = _program(words[0]), words[1:]
    positional = [arg for arg in args if not arg.startswith(_SHORT_PREFIX)]
    if program in _CHANGES_ARGUMENTS:
        return positional
    if program in _COPIES:
        explicit = [
            args[i + 1] for i in range(len(args) - 1) if args[i].lower() in _COPY_TARGET_OPTIONS
        ] + [arg.split("=", 1)[1] for arg in args if arg.lower().startswith("--target-directory=")]
        return explicit or positional[-1:]
    if program == _SED and any(arg.startswith(_IN_PLACE_PREFIXES) for arg in args):
        return positional
    if program == _DD:
        return [arg[len(_DD_OUTPUT) :] for arg in args if arg.startswith(_DD_OUTPUT)]
    return []


def _evaluate_agentflow(args: list[str], context: _Context) -> GuardVerdict:
    words = tuple(arg for arg in args if not arg.startswith(_SHORT_PREFIX))[:2]
    if not context.in_workspace(context.cwd):
        return ALLOW
    for restricted in _PERSON_ONLY:
        if words[: len(restricted)] == restricted:
            return _deny(GuardRule.PERSON_ONLY, command=" ".join(restricted))
    for asked in _ASKED:
        if words[: len(asked)] == asked:
            return _ask(GuardRule.PERSON_CONFIRMS, command=" ".join(asked))
    return ALLOW


def _runs_nested_command(program: str, tokens: list[str], index: int) -> bool:
    if program in _EVALUATORS:
        return index + 1 < len(tokens)
    return program in _SHELLS and any(_is_command_flag(token) for token in tokens[index + 1 :])


def _nested_start(program: str, tokens: list[str], index: int) -> int:
    if program in _EVALUATORS:
        return index + 1
    flag = next(i for i in range(index + 1, len(tokens)) if _is_command_flag(tokens[i]))
    return flag + 1


# --------------------------------------------------------------------- git


def _evaluate_git(args: list[str], context: _Context) -> GuardVerdict:
    directory = context.cwd
    position = 0
    while position < len(args) and args[position].startswith(_SHORT_PREFIX):
        option = args[position]
        if option in _GIT_VALUE_OPTIONS and position + 1 < len(args):
            if option == _GIT_DIRECTORY_OPTION:
                directory = _join(directory, args[position + 1])
            position += 2
        else:
            position += 1
    if position >= len(args):
        return ALLOW
    subcommand, rest = args[position], args[position + 1 :]
    shorts = _short_flags(rest)

    rule = _protection(gitpaths.touched_paths(subcommand, rest), directory, context.writes)
    if rule is not None:
        return _deny(rule)
    if subcommand == _PUSH:
        return _deny(GuardRule.PUSH)
    if subcommand == _RESET and _HARD in rest:
        return _deny(GuardRule.RESET_HARD)
    if subcommand == _CLEAN and (_FORCE_LONG in rest or _FORCE_SHORT in shorts) and _DIRECTORIES_SHORT in shorts:
        return _deny(GuardRule.CLEAN_FORCE_DIRS)
    if subcommand == _BRANCH and (
        _FORCE_DELETE_SHORT in shorts
        or ((_DELETE_LONG in rest or _DELETE_SHORT in shorts) and (_FORCE_LONG in rest or _FORCE_SHORT in shorts))
    ):
        return _deny(GuardRule.BRANCH_FORCE_DELETE)
    if subcommand == _TAG and (_DELETE_LONG in rest or _DELETE_SHORT in shorts):
        return _deny(GuardRule.TAG_DELETE)
    if _writes_approval_ref(subcommand, rest):
        return _deny(GuardRule.APPROVAL_TAG)
    if subcommand == _COMMIT and context.in_workspace(directory):
        return _deny(GuardRule.DIRECT_COMMIT)
    if subcommand in _COMMITTING and not _STOP_FLAGS.intersection(rest):
        branch = context.branch_of(directory)
        if branch in context.protected:
            return _deny(GuardRule.PROTECTED_BRANCH, subcommand=subcommand, branch=branch)
    if subcommand == _SWITCH:
        _track_switch(rest, directory, context)
    elif subcommand == _CHECKOUT:
        _track_checkout(rest, directory, context)
    return ALLOW


def _evaluate_git_text(command: str, cwd: Path, writes: WriteTargetPolicy) -> GuardVerdict:
    rule = _protection([_bare(token) for token in gitpaths.checkout_paths_in_text(command)], cwd, writes)
    return ALLOW if rule is None else _deny(rule)


def _writes_approval_ref(subcommand: str, args: list[str]) -> bool:
    if subcommand == _TAG:
        return any(arg.startswith(APPROVAL_TAG_PREFIX) for arg in args)
    if subcommand == _UPDATE_REF:
        return any(arg.startswith(TAG_REF_PREFIX + APPROVAL_TAG_PREFIX) for arg in args)
    return False


def _short_flags(args: list[str]) -> set[str]:
    """Letters of short option clusters such as ``-fd``; stops at ``--``."""
    letters: set[str] = set()
    for arg in args:
        if arg == _END_OF_OPTIONS:
            break
        if arg.startswith(_SHORT_PREFIX) and not arg.startswith(_LONG_PREFIX):
            letters.update(arg[1:])
    return letters


def _track_switch(args: list[str], directory: Path, context: _Context) -> None:
    created = _value_after(args, _SWITCH_CREATE)
    if created is not None:
        context.switched[directory] = created
    elif _DETACH.intersection(args) or _SWITCH_DETACH_SHORT in args:
        context.switched[directory] = None
    else:
        target = _first_positional(args)
        if target is not None:
            context.switched[directory] = target


def _track_checkout(args: list[str], directory: Path, context: _Context) -> None:
    created = _value_after(args, _CHECKOUT_CREATE)
    if created is not None:
        context.switched[directory] = created
    elif _DETACH.intersection(args):
        context.switched[directory] = None
    elif _END_OF_OPTIONS not in args:
        # `git checkout <name>` is a branch switch only if such a branch exists; otherwise it restores files.
        target = _first_positional(args)
        if target is not None and (target in context.protected or context.branches.branch_exists(directory, target)):
            context.switched[directory] = target


def _value_after(args: list[str], options: frozenset[str]) -> str | None:
    for index, arg in enumerate(args[:-1]):
        if arg in options:
            return args[index + 1]
    return None


def _first_positional(args: list[str]) -> str | None:
    return next((arg for arg in args if not arg.startswith(_SHORT_PREFIX)), None)


def _join(base: Path, part: str) -> Path:
    return Path(os.path.normpath(base / part))


def _deny(rule: GuardRule, **details: str) -> GuardVerdict:
    return GuardVerdict(GuardDecision.DENY, rule, REASONS[rule].format(**details))


def _ask(rule: GuardRule, **details: str) -> GuardVerdict:
    return GuardVerdict(GuardDecision.ASK, rule, REASONS[rule].format(**details))


# ------------------------------------------------------------------- JSON io


@dataclass(frozen=True)
class GuardRequest:
    command: str
    cwd: Path | None


def parse_request(text: str) -> GuardRequest:
    """Parse ``{"command": "...", "cwd": "..."}``; ``cwd`` may be missing or null."""
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentflowError(f"guard input is not JSON: {exc}", ExitCode.INVALID_INPUT) from exc
    command = data.get(GuardKey.COMMAND) if isinstance(data, dict) else None
    cwd = data.get(GuardKey.CWD) if isinstance(data, dict) else None
    if not isinstance(command, str):
        raise AgentflowError(f"guard input needs a string '{GuardKey.COMMAND}'", ExitCode.INVALID_INPUT)
    if cwd is not None and not isinstance(cwd, str):
        raise AgentflowError(f"guard input '{GuardKey.CWD}' must be a string", ExitCode.INVALID_INPUT)
    return GuardRequest(command, Path(cwd) if cwd else None)


def verdict_to_dict(verdict: GuardVerdict) -> dict[str, str | None]:
    return {
        GuardKey.DECISION: verdict.decision,
        GuardKey.RULE: verdict.rule,
        GuardKey.REASON: verdict.reason,
    }
