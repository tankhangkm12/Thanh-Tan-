"""PreToolUse hook of design-core: stop an agent from writing outside its own zone (workflow/permissions.md).

Claude Code sends one JSON object on stdin (https://code.claude.com/docs/en/hooks): `agent_type`, `tool_name`,
`tool_input` (`file_path`, `content` for Write; `file_path`, `old_string`, `new_string`, `replace_all` for Edit;
`command` for Bash and PowerShell) and `cwd`. A plugin subagent's `agent_type` is `<plugin>:<name>`, e.g. `design-core:reviewer`.
Exit 2 blocks the call and sends stderr to the agent; exit 0 lets it through. A call that carries no design-core
`agent_type` (a plain session, another plugin's agent) is never touched.

Zones are relative to `.agent-workspace/`; everything else, `architecture/` included, is closed to every agent
(only `promote_drafts.py` writes there).

    uv run guard_write.py < hook-input.json
"""

import json
import re
import shlex
import sys
import unicodedata
from pathlib import Path

WORKSPACE = ".agent-workspace"
PLUGIN = "design-core"
COUNCIL_PREFIX = "council-"
COUNCIL = ("fit", "cost-ops", "numbers-nfr", "evolution", "risk-data")
ROLES = ("orchestrator", "planner", "researcher", "designer", "reviewer") + tuple(COUNCIL_PREFIX + p for p in COUNCIL)

# Check scripts a Reviewer may `uv run` (never promote_drafts / archive_release / tally_votes). calc_capacity.py only
# with --check, which compares without writing (the plain run writes drafts/).
REVIEWER_SCRIPTS = ("check_links.py", "check_trace.py", "check_numbers.py", "check_profile.py", "check_versions.py", "check_workspace.py")
REVIEWER_CHECK_ONLY_SCRIPTS = ("calc_capacity.py",)
# Every script of the family the Orchestrator may `uv run` (promote_drafts, archive_release and tally_votes check their own
# preconditions).
ORCHESTRATOR_SCRIPTS = REVIEWER_SCRIPTS + (
    "init_workspace.py", "detect_models.py", "call_council_cli.py", "tally_votes.py", "calc_capacity.py", "promote_drafts.py", "archive_release.py",
    "run_spike.py",
)
READ_ONLY_COMMANDS = ("cat", "head", "tail", "wc", "ls", "dir", "type", "grep", "rg", "pwd", "diff", "stat", "echo", "cd", "find", "git")
GIT_READ_ONLY = ("status", "log", "diff", "show", "ls-files", "rev-parse")
GIT_WRITING_FLAGS = ("--output", "-o")
FIND_WRITING_FLAGS = ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls")
PLUGIN_ROOT_FORMS = ("${CLAUDE_PLUGIN_ROOT}", "$CLAUDE_PLUGIN_ROOT")

# Pieces of a file that only one writer may change.
STATUS_LINE = re.compile(r"^\s*(?:[-*]\s+)?\*{0,2}Trạng thái:?\*{0,2}:?")
USER_BLOCK = re.compile(r"(<!--\s*BEGIN:user\b.*?-->)(.*?)(<!--\s*END:user\s*-->)", re.DOTALL)
CALC_BLOCK = re.compile(r"<!--\s*BEGIN:calc:(\S+?)\s*-->(.*?)<!--\s*END:calc:\1\s*-->", re.DOTALL)


class Denied(Exception):
    pass


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def glob_regex(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z", re.IGNORECASE)


def matches(rel: str, pattern: str) -> bool:
    return bool(glob_regex(pattern).match(rel))


def normalize_path(raw: str, cwd: str = "") -> str:
    """Absolute-looking path with `/`, `.` and `..` resolved; a relative path is joined to `cwd` first."""
    raw = raw.replace("\\", "/")
    if cwd and not re.match(r"^(?:[A-Za-z]:)?/", raw):
        raw = cwd.replace("\\", "/").rstrip("/") + "/" + raw
    head = re.match(r"^([A-Za-z]:)?(/)?", raw)
    parts = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    if head.group(1) and parts and parts[0] == head.group(1):
        parts.pop(0)
    return (head.group(1) or "") + (head.group(2) or "") + "/".join(parts)


def find_workspace(cwd: str) -> str | None:
    """The `.agent-workspace/` of the project the session runs in: the nearest one at or above `cwd` that exists on disk."""
    if not cwd:
        return None
    current = normalize_path(cwd)
    while current:
        if (Path(current) / WORKSPACE).is_dir():
            return current.rstrip("/") + "/" + WORKSPACE
        current = current.rpartition("/")[0]
    return None


def workspace_relative(file_path: str, cwd: str = "", root: str | None = None) -> str | None:
    """Path below `.agent-workspace/`, or None when the file is not inside it.

    With a known `root` (see find_workspace) the file must be inside that very folder; without one (no workspace on disk
    yet, or no cwd in the data) any folder named `.agent-workspace` in the path counts.
    """
    normalized = normalize_path(file_path, cwd)
    if root:
        prefix = root.casefold() + "/"
        return normalized[len(prefix) :] if normalized.casefold().startswith(prefix) and len(normalized) > len(prefix) else None
    parts = [p for p in normalized.split("/") if p]
    lowered = [p.casefold() for p in parts]
    if WORKSPACE not in lowered:
        return None
    rest = parts[lowered.index(WORKSPACE) + 1 :]
    return "/".join(rest) if rest else None


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def new_content(tool: str, tool_input: dict, old: str | None) -> str:
    """What the file would hold after the call."""
    if tool == "Write":
        return tool_input.get("content", "")
    old = old or ""
    old_string, new_string = tool_input.get("old_string", ""), tool_input.get("new_string", "")
    if not old_string or old_string not in old:
        return old  # the tool itself will refuse this edit
    return old.replace(old_string, new_string) if tool_input.get("replace_all") else old.replace(old_string, new_string, 1)


# --- piece checks: each takes (old text, new text) and raises Denied -------------------------------------------------

def only_status_line(old: str | None, new: str) -> None:
    if old is None:
        raise Denied("Orchestrator không tạo file task mới; chỉ sửa dòng \"Trạng thái\" của file có sẵn")
    old_lines, new_lines = nfc(old).splitlines(), nfc(new).splitlines()
    if len(old_lines) != len(new_lines):
        raise Denied("Orchestrator chỉ được sửa dòng \"Trạng thái\" trong file task (số dòng không được đổi)")
    for before, after in zip(old_lines, new_lines):
        if before != after and not (STATUS_LINE.match(before) and STATUS_LINE.match(after)):
            raise Denied(f"Orchestrator chỉ được sửa dòng \"Trạng thái\" trong file task, không được đổi: {before.strip()[:60]!r}")


def only_user_block(old: str | None, new: str) -> None:
    if old is None:
        raise Denied("Orchestrator không tạo decision.md; chỉ ghi khối giữa BEGIN:user và END:user của file có sẵn")
    before, after = USER_BLOCK.findall(old), USER_BLOCK.findall(new)
    if len(before) != 1 or len(after) != 1:
        raise Denied("decision.md phải có đúng một khối BEGIN:user ... END:user, và Orchestrator không được xóa hay thêm dấu")
    if USER_BLOCK.sub("\0", old) != USER_BLOCK.sub("\0", new) or before[0][0] != after[0][0] or before[0][2] != after[0][2]:
        raise Denied("Orchestrator chỉ được sửa khối giữa BEGIN:user và END:user của decision.md (phần hội đồng do tally_votes.py sinh)")


PENDING_BLOCK = re.compile(r"(?:<!--\s*)?chờ script(?:\s*-->)?", re.IGNORECASE)


def calc_blocks_frozen(old: str | None, new: str) -> None:
    """A filled calc block is the script's. The Designer may only add (or remove) a block that holds just "chờ script"."""
    old, new = old or "", new
    old_blocks, new_blocks = CALC_BLOCK.findall(old), CALC_BLOCK.findall(new)
    message = "khối giữa BEGIN:calc:<bảng> và END:calc:<bảng> trong tables.md do calc_capacity.py sinh; Designer chỉ sửa phần ngoài khối, và chỉ được thêm/bỏ cặp dấu mà bên trong chỉ có \"chờ script\""
    if old.count("BEGIN:calc") != len(old_blocks) or new.count("BEGIN:calc") != len(new_blocks):
        if old.count("BEGIN:calc") == new.count("BEGIN:calc") and old_blocks == new_blocks:
            return  # a broken marker that was already there and is untouched
        raise Denied(message)
    before, after = dict(old_blocks), dict(new_blocks)
    if len(before) != len(old_blocks) or len(after) != len(new_blocks):
        raise Denied(message)
    for name, content in after.items():
        if name in before and before[name] != content:
            raise Denied(message)
        if name not in before and not PENDING_BLOCK.fullmatch(nfc(content).strip()):
            raise Denied(message)
    for name, content in before.items():
        if name not in after and not PENDING_BLOCK.fullmatch(nfc(content).strip()):
            raise Denied(message)


def create_only(old: str | None, new: str) -> None:
    if old is not None:
        raise Denied("Reviewer chỉ tạo file báo cáo mới trong reviews/, không sửa hay ghi đè file có sẵn")


# --- zones --------------------------------------------------------------------------------------------------------------

ANY = None
# The result of a spike is a fact only run_spike.py may write: no agent, whatever else its zone says (first match wins).
SPIKE_RESULT = ("stack/layers/*/spikes/*.result.md", "deny:là kết quả spike do run_spike.py sinh, không agent nào ghi")
ZONES = {
    "orchestrator": [
        ("state.md", ANY), ("models.md", ANY), ("questions.md", ANY), ("inputs/**", ANY),
        ("decisions/decision-log.md", ANY), ("risks/acceptance.md", ANY),
        ("plan/tasks/*.md", only_status_line), ("decisions/*/decision.md", only_user_block),
    ],
    "planner": [("plan/**", ANY), ("questions.md", ANY), ("drafts/00-context/project-profile.md", ANY)],
    "researcher": [SPIKE_RESULT, ("stack/**", ANY), ("capacity/db-constants/*.yaml", ANY)],
    "designer": [
        SPIKE_RESULT,
        ("capacity/db-constants/**", "deny:là hằng số DB đã xác minh nguồn, của Researcher"),
        ("drafts/00-context/assumptions.md", "deny:do calc_capacity.py sinh từ capacity/assumptions.yaml, không sửa tay"),
        ("drafts/03-capacity/**", "deny:do calc_capacity.py sinh"),
        ("drafts/07-data/databases/*/tables.md", calc_blocks_frozen),
        ("decisions/*/brief.md", ANY), ("drafts/**", ANY), ("capacity/**", ANY), ("questions.md", ANY),
        ("stack/layers/*/spikes/S-*.md", ANY),
    ],
}


def zone_check(role: str, rel: str, tool: str, tool_input: dict, file_path: str) -> None:
    if role.startswith(COUNCIL_PREFIX):
        perspective = role[len(COUNCIL_PREFIX) :]
        if not re.fullmatch(rf"decisions/[^/]+/votes/r[12]-{re.escape(perspective)}-[^/]+\.md", rel, re.IGNORECASE):
            raise Denied(f"thành viên hội đồng chỉ ghi phiếu của chính mình: decisions/<D>/votes/r<1|2>-{perspective}-<model>.md")
        return
    if role == "reviewer":
        if not re.fullmatch(r"reviews/R-\d+-[^/]+\.md", rel, re.IGNORECASE):
            raise Denied("Reviewer chỉ tạo file báo cáo mới reviews/R-<số>-<phần>.md")
        old = read_text(file_path)
        create_only(old, new_content(tool, tool_input, old))
        return
    for pattern, rule in ZONES.get(role, []):
        if not matches(rel, pattern):
            continue
        if isinstance(rule, str):
            raise Denied(f"{rel} {rule.split(':', 1)[1]}")
        if rule is not ANY:
            old = read_text(file_path)
            rule(old, new_content(tool, tool_input, old))
        return
    raise Denied(f"{rel} nằm ngoài vùng ghi của {role} (workflow/permissions.md)")


# --- Shell tools (Bash, PowerShell) ---------------------------------------------------------------------------------------
#
# Allow-list, not block-list: a command passes only if every piece of it is one of the allowed kinds below.

SHELLS = ("Bash", "PowerShell")
# Characters that can hide a write or another command. Outside single quotes for both shells; `$` and backtick also expand
# inside double quotes.
FORBIDDEN_BASH = {"<": "chuyển hướng (< >)", ">": "chuyển hướng (< >)", "`": "thay thế lệnh", "&": "chạy nền (&)"}
FORBIDDEN_POWERSHELL = {
    "<": "chuyển hướng (< >)", ">": "chuyển hướng (< >)", "`": "ký tự thoát (`)", "$": "biến hoặc thay thế lệnh ($)", "&": "toán tử gọi (&)",
    "(": "ngoặc đơn", ")": "ngoặc đơn", "{": "khối lệnh", "}": "khối lệnh", "@": "mảng/splatting (@)",
}
COPY_FLAGS = re.compile(r"^-[rRpavnf]+$")
POWERSHELL_COPY = ("copy-item", "cp", "copy", "cpi")
POWERSHELL_COPY_SWITCHES = ("-recurse", "-force", "-verbose", "-passthru", "-container")
POWERSHELL_COPY_VALUES = {"-path": "src", "-literalpath": "src", "-destination": "dest"}
POWERSHELL_READ_ONLY = (
    "get-content", "gc", "get-childitem", "gci", "select-string", "sls", "get-item", "gi", "test-path", "measure-object", "measure",
    "select-object", "select", "sort-object", "get-location", "gl", "resolve-path", "split-path", "join-path", "format-list", "fl",
    "format-table", "ft", "out-string", "write-output", "write-host", "where-object", "get-filehash", "set-location", "sl", "chdir",
)
CD_COMMANDS = ("cd", "chdir", "set-location", "sl")
DATE_FLAGS = ("-I", "-u", "-R", "--utc", "--rfc-2822")
DATE_FLAG_PREFIXES = ("-I", "--iso-8601", "--rfc-3339")


def split_commands(command: str, shell: str) -> list[str]:
    """Split on && || ; | and newlines outside quotes; refuse redirects, substitutions, background jobs and the like."""
    forbidden = FORBIDDEN_POWERSHELL if shell == "PowerShell" else FORBIDDEN_BASH
    command = re.sub(r"\s2>&1(?=\s|$|[|;&])", " ", command)
    segments, current, quote, i = [], "", "", 0
    while i < len(command):
        ch = command[i]
        if quote:
            if ch == quote:
                quote = ""
            elif quote == '"' and (ch == "`" or (shell == "PowerShell" and ch == "$") or (shell == "Bash" and command.startswith("$(", i))):
                raise Denied("không được dùng thay thế lệnh hay biến trong chuỗi nháy kép ($(...), $, `)")
            current += ch
        elif ch in "'\"":
            quote, current = ch, current + ch
        elif command.startswith("&&", i) or command.startswith("||", i):
            segments.append(current)
            current, i = "", i + 1
        elif ch in forbidden or (shell == "Bash" and command.startswith("$(", i)):
            raise Denied(f"không được dùng {forbidden.get(ch, 'thay thế lệnh $(...)')}: shell của agent không để ghi file")
        elif ch in ";|\n\r":
            segments.append(current)
            current = ""
        else:
            current += ch
        i += 1
    if quote:
        raise Denied("nháy chưa đóng")
    segments.append(current)
    return [s.strip() for s in segments if s.strip()]


def script_dir_ok(directory: str) -> bool:
    if directory in PLUGIN_ROOT_FORMS or directory.rstrip("/") in tuple(f + "/scripts" for f in PLUGIN_ROOT_FORMS):
        return True
    if not re.match(r"^(?:[A-Za-z]:)?/", directory):
        return False  # a relative path would depend on the current folder
    here = Path(__file__).resolve().parent
    try:
        return Path(directory).resolve() == here
    except OSError:
        return False


def uv_run_ok(tokens: list[str], scripts: tuple[str, ...], check_only: tuple[str, ...]) -> None:
    rest = tokens[2:]
    i = 0
    options_with_value = {"--with", "--python", "-p", "--project", "--directory", "--with-requirements", "--env-file"}
    while i < len(rest) and rest[i].startswith("-"):
        i += 2 if rest[i] in options_with_value else 1
    if i >= len(rest):
        raise Denied("chỉ được `uv run` script của design-core")
    script = rest[i].replace("\\", "/")
    directory, _, name = script.rpartition("/")
    args = rest[i + 1 :]
    if name in check_only:
        if "--check" not in args:
            raise Denied(f"chỉ chạy {name} với --check (không ghi bản nháp)")
    elif name not in scripts:
        raise Denied(f"chỉ được `uv run` các script: {', '.join(scripts + check_only)}")
    if not script_dir_ok(directory):
        raise Denied("chỉ chạy script nằm trong thư mục scripts/ của design-core")


def read_only_ok(tokens: list[str], shell: str) -> None:
    program = tokens[0].lower() if shell == "PowerShell" else tokens[0]
    if program not in READ_ONLY_COMMANDS and not (shell == "PowerShell" and program in POWERSHELL_READ_ONLY):
        raise Denied(f"chỉ được `uv run` script của design-core và lệnh chỉ đọc; không cho phép: {tokens[0]}")
    if program == "git":
        if len(tokens) < 2 or tokens[1] not in GIT_READ_ONLY or any(t == f or t.startswith(f + "=") for t in tokens for f in GIT_WRITING_FLAGS):
            raise Denied(f"chỉ được dùng git chỉ đọc: {', '.join(GIT_READ_ONLY)}")
    if program == "find" and any(t in FIND_WRITING_FLAGS for t in tokens):
        raise Denied("không được dùng find với -exec, -delete hoặc -fprint")


def date_ok(tokens: list[str], shell: str) -> None:
    """`date` that only prints (no `-s`, no positional MMDDhhmm that would set the clock), or Get-Date."""
    if shell == "PowerShell":
        return  # Get-Date only reads the clock
    for token in tokens[1:]:
        if not (token.startswith("+") or token in DATE_FLAGS or token.startswith(DATE_FLAG_PREFIXES)):
            raise Denied(f"date chỉ được in ngày, không đặt giờ: {token}")


def unresolvable(path: str) -> bool:
    return not path or any(c in path for c in "*?[]~$%") or path in ("-",)


def inputs_destination(dest: str, cwd: str, root: str | None) -> None:
    if unresolvable(dest) or not cwd and not re.match(r"^(?:[A-Za-z]:)?/", dest.replace("\\", "/")):
        raise Denied(f"không xác định được đích chép: {dest!r}")
    rel = workspace_relative(dest, cwd, root)
    if rel is None or not (rel.casefold() == "inputs" or rel.casefold().startswith("inputs/")):
        raise Denied(f"chỉ được chép file vào {WORKSPACE}/inputs/, không phải {dest}")


def copy_ok(tokens: list[str], cwd: str, shell: str, root: str | None) -> None:
    """Orchestrator may copy into .agent-workspace/inputs/ (nothing else)."""
    args = tokens[1:]
    if shell == "PowerShell":
        positional, named, i = [], {}, 0
        while i < len(args):
            token = args[i].lower()
            if token in POWERSHELL_COPY_SWITCHES:
                i += 1
            elif token in POWERSHELL_COPY_VALUES and i + 1 < len(args):
                named[POWERSHELL_COPY_VALUES[token]] = args[i + 1]
                i += 2
            elif token.startswith("-"):
                raise Denied(f"Copy-Item: tham số không được phép: {args[i]}")
            else:
                positional.append(args[i])
                i += 1
        source, dest, free = named.get("src"), named.get("dest"), list(positional)
        if source is None and free:
            source = free.pop(0)
        if dest is None and free:
            dest = free.pop(0)
        if free or not source or not dest:
            raise Denied("Copy-Item cần một nguồn và một đích trong inputs/")
        inputs_destination(dest, cwd, root)
        return
    flags = [a for a in args if a.startswith("-")]
    names = [a for a in args if not a.startswith("-")]
    if any(not COPY_FLAGS.match(f) for f in flags):
        raise Denied(f"cp: cờ không được phép: {', '.join(f for f in flags if not COPY_FLAGS.match(f))}")
    if len(names) < 2:
        raise Denied("cp cần ít nhất một nguồn và một đích trong inputs/")
    inputs_destination(names[-1], cwd, root)


def next_cwd(tokens: list[str], cwd: str) -> str:
    """Folder after a `cd`; '' (unknown) when it cannot be worked out, so later copies are refused."""
    if len(tokens) != 2 or unresolvable(tokens[1]):
        return ""
    return normalize_path(tokens[1], cwd) if cwd or re.match(r"^(?:[A-Za-z]:)?/", tokens[1].replace("\\", "/")) else ""


SHELL_POLICY = {
    # role: (scripts it may `uv run`, scripts only with --check, may print the date, may copy into inputs/)
    "reviewer": (REVIEWER_SCRIPTS, REVIEWER_CHECK_ONLY_SCRIPTS, False, False),
    "orchestrator": (ORCHESTRATOR_SCRIPTS, (), True, True),
}


def shell_check(role: str, shell: str, command: str, cwd: str = "") -> None:
    policy = SHELL_POLICY.get(role)
    if policy is None:
        raise Denied(f"{role} không có {shell} (workflow/permissions.md)")
    scripts, check_only, may_date, may_copy = policy
    cwd = cwd.replace("\\", "/") if cwd else ""
    root = find_workspace(cwd)
    try:
        segments = split_commands(command, shell)
    except Denied as reason:
        raise Denied(str(reason)) from None
    for segment in segments:
        try:
            tokens = shlex.split(segment.replace("\\", "/"), posix=True)
        except ValueError as error:
            raise Denied(f"lệnh không phân tích được ({error})") from error
        if not tokens:
            continue
        program = tokens[0].lower() if shell == "PowerShell" else tokens[0]
        try:
            if program == "uv" and len(tokens) > 1 and tokens[1].lower() == "run":
                uv_run_ok(tokens, scripts, check_only)
            elif (program == "date" and shell == "Bash") or (program == "get-date" and shell == "PowerShell"):
                if not may_date:
                    raise Denied(f"không cho phép: {tokens[0]}")
                date_ok(tokens, shell)
            elif (program == "cp" and shell == "Bash") or (program in POWERSHELL_COPY and shell == "PowerShell"):
                if not may_copy:
                    raise Denied(f"không cho phép: {tokens[0]}")
                copy_ok(tokens, cwd, shell, root)
            else:
                read_only_ok(tokens, shell)
                if program in CD_COMMANDS:
                    cwd = next_cwd(tokens, cwd)
        except Denied as reason:
            raise Denied(str(reason)) from None


# --- entry ----------------------------------------------------------------------------------------------------------------

def role_of(agent_type: str) -> str | None:
    prefix, _, name = (agent_type or "").partition(":")
    if name and prefix == PLUGIN and name in ROLES:
        return name
    return None


def decide(data: dict) -> None:
    """Raise Denied when the call must be blocked."""
    role = role_of(data.get("agent_type", ""))
    if role is None:
        return
    tool, tool_input = data.get("tool_name", ""), data.get("tool_input") or {}
    if tool in SHELLS:
        shell_check(role, tool, tool_input.get("command", ""), data.get("cwd", ""))
        return
    if tool not in ("Write", "Edit"):
        return
    file_path = tool_input.get("file_path", "")
    cwd = data.get("cwd", "")
    rel = workspace_relative(file_path, cwd, find_workspace(cwd))
    if rel is None:
        raise Denied(f"{file_path} nằm ngoài {WORKSPACE}/ (architecture/ chỉ do promote_drafts.py ghi)")
    if role == "reviewer" and tool == "Edit":
        raise Denied("Reviewer chỉ tạo file báo cáo mới trong reviews/, không sửa file có sẵn")
    zone_check(role, rel, tool, tool_input, str(Path(file_path)))


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as error:
        print(f"guard_write: dữ liệu hook không phải JSON ({error})", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("guard_write: dữ liệu hook không phải đối tượng JSON", file=sys.stderr)
        return 1
    try:
        decide(data)
    except Denied as reason:
        print(f"guard_write: chặn {data.get('tool_name')} của {data.get('agent_type')}: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
