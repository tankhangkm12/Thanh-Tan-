"""Decide whether one shell command an agent wants to run is allowed.

The guard reads the command the way a shell would split it, finds every git
invocation in it (also inside chains, pipes, ``bash -c "..."`` and similar), and
denies the ones that publish work, rewrite or drop it, or commit straight onto a
protected branch. It is a safety net for agents, not a sandbox: git aliases,
scripts and environment tricks can still get around it.
"""

import json
import os
import re
import shlex
from dataclasses import dataclass, field
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
from agentflow.errors import AgentflowError
from agentflow.interfaces import BranchLookup, WorkspaceLookup, WriteTargetPolicy
from agentflow.models import GuardVerdict
from agentflow.pathguard import WorkspaceWritePolicy

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
        ("replan", "done"), ("replan", "skip"),
    }  # fmt: skip
)
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

REASONS[GuardRule.WORKSPACE_WRITE] = (
    "files under .agentflow/ (and the project-* agents in .claude/agents/ that `agentflow role` generates) are written by "
    "agentflow only: use the `agentflow` commands (or its MCP tools), never edit or write there by hand"
)

ALLOW = GuardVerdict(GuardDecision.ALLOW)

# ------------------------------------------------------- writes into .agentflow/
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


@dataclass
class _Context:
    """What the guard knows while walking a command line left to right."""

    cwd: Path
    branches: BranchLookup
    workspaces: WorkspaceLookup | None = None
    # Branches the command line itself switched to, per repository directory (None = detached).
    switched: dict[Path, str | None] = field(default_factory=dict)
    writes: WriteTargetPolicy = field(default_factory=WorkspaceWritePolicy)

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
) -> GuardVerdict:
    start = Path(os.path.normpath(cwd))
    context = _Context(start, branches, workspaces, writes=writes or WorkspaceWritePolicy())
    verdict = _evaluate(command, context, depth=0)
    if verdict.denied:
        return verdict
    return _evaluate_writes(_without_heredoc_bodies(command), start, context.writes, depth=0)


def writes_into_workspace(target: Path | str, cwd: Path, writes: WriteTargetPolicy | None = None) -> GuardVerdict:
    """Verdict for a file-writing tool (not a shell command) that is about to change ``target``."""
    if (writes or WorkspaceWritePolicy()).is_protected(target, cwd):
        return _deny(GuardRule.WORKSPACE_WRITE)
    return ALLOW


def _evaluate(command: str, context: _Context, depth: int) -> GuardVerdict:
    for segment in split_commands(command):
        verdict = _evaluate_segment(segment, context, depth)
        if verdict.denied:
            return verdict
    return ALLOW


def split_commands(command: str) -> list[list[str]]:
    """Tokens of each simple command in ``command``, split at separators outside quotes."""
    segments: list[list[str]] = []
    current: list[str] = []
    for token in _tokens(command):
        if token and all(char in _PUNCTUATION for char in token):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


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
    for index, token in enumerate(tokens):
        program = _program(token)
        if depth < _MAX_NESTING and _runs_nested_command(program, tokens, index):
            nested = " ".join(tokens[_nested_start(program, tokens, index) :])
            verdict = _evaluate(nested, context, depth + 1)
            if verdict.denied:
                return verdict
        if program == GIT_EXECUTABLE:
            verdict = _evaluate_git([_bare(token) for token in tokens[index + 1 :]], context)
            if verdict.denied:
                return verdict
        elif program == AGENTFLOW_PROGRAM and index == 0:
            verdict = _evaluate_agentflow([_bare(token) for token in tokens[1:]], context)
            if verdict.denied:
                return verdict
    return ALLOW


def _without_heredoc_bodies(command: str) -> str:
    """``command`` with the text of here-documents removed: it is data for the command that reads it."""
    lines = command.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        match = _HEREDOC.search(line)
        if match is None:
            continue
        delimiter = match.group(3) or match.group(4)
        strip_tabs = match.group(1) == "-"
        while index < len(lines):
            body = lines[index]
            index += 1
            if (body.lstrip(_TABS) if strip_tabs else body) == delimiter:
                break
    return "\n".join(kept)


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
        paths = [*simple.redirects, *_changed_paths(simple.words)]
        if any(writes.is_protected(_bare(path), cwd) for path in paths):
            return _deny(GuardRule.WORKSPACE_WRITE)
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
    for restricted in _PERSON_ONLY:
        if words[: len(restricted)] == restricted and context.in_workspace(context.cwd):
            return _deny(GuardRule.PERSON_ONLY, command=" ".join(restricted))
    return ALLOW


def _runs_nested_command(program: str, tokens: list[str], index: int) -> bool:
    if program in _EVALUATORS:
        return index + 1 < len(tokens)
    return program in _SHELLS and any(token.lower() in _SHELL_COMMAND_FLAGS for token in tokens[index + 1 :])


def _nested_start(program: str, tokens: list[str], index: int) -> int:
    if program in _EVALUATORS:
        return index + 1
    flag = next(i for i in range(index + 1, len(tokens)) if tokens[i].lower() in _SHELL_COMMAND_FLAGS)
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
        if branch in PROTECTED_BRANCHES:
            return _deny(GuardRule.PROTECTED_BRANCH, subcommand=subcommand, branch=branch)
    if subcommand == _SWITCH:
        _track_switch(rest, directory, context)
    elif subcommand == _CHECKOUT:
        _track_checkout(rest, directory, context)
    return ALLOW


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
        if target is not None and (target in PROTECTED_BRANCHES or context.branches.branch_exists(directory, target)):
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
