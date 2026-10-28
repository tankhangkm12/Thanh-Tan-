# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Call one council member that runs on an outside CLI (not a Claude Code subagent) and write its vote.

The prompt is the body of the perspective file (`claude/agents/council/<perspective>.md` without its frontmatter, cut at the
line `<!-- body-end -->`), `brief.md` and, for round 2, `votes/r1-summary.md`, under a short header that gives decision, round,
perspective, member, model and via (`cli`). Nothing else is sent: no other vote, no other file. The answer is written, trimmed of
surrounding blank space but otherwise verbatim, to `decisions/D-xxx-<name>/votes/r<round>-<perspective>-<member>.md`. A vote in
the wrong format is still written: `tally_votes.py` rejects it (this script prints what it would reject, as a hint).

Which model: the row of `models.md` (written by detect_models.py) must be a `cli` row whose status is "gọi được" (a model that
was not probed, or failed its probe, is refused). The executable and the model id come from the "Cách gọi" cell of that row
(`agy -p <prompt> --model <id> (...)`). Default way of passing the prompt is stdin, as the CLI's data in `core/data/cli.yaml`
describes (agy: `--input-format stream-json`, one NDJSON line); `--mode argv` uses the row's own command, the prompt as an
argument, which is also the automatic fallback when the CLI rejects the stdin flags. Over the command-line limit it is an error, the
prompt is never cut. The CLI runs in an empty temporary folder, with no extra directory added, and ALWAYS as a locked agent
(data/cli.yaml `lock`): an agent definition with no tools and no MCP, so the member cannot read other files, run commands or write
(an unlocked agy reads any file, writes files even in `--mode plan`, and inherits the user's own rules). A CLI that does not know
the agent silently falls back to its default agent, so a first call asks for a secret code that only the agent's system prompt
holds; the brief is sent only after the CLI answers with it. A tool step in an answer voids the vote. A CLI with no `lock` in
cli.yaml is refused.

Exit 0: a vote was written. Exit 1: the CLI failed, timed out or answered nothing, the model is not usable, the file exists
(use `--overwrite`), the brief is not valid, round 2 has no r1-summary.md. Exit 2: bad arguments.
The call is appended to `<workspace>/checks/council-cli-<date>.md`.

    uv run call_council_cli.py --decision D-xxx-name --round 1 --perspective fit --model agy:<id> [--workspace DIR]
                               [--mode auto|stdin|argv] [--timeout SECONDS] [--overwrite]
"""

import argparse
import datetime
import json
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_models as dm  # noqa: E402
import tally_votes as tv  # noqa: E402

ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent
DEFAULT_CLI_CONFIG = CORE / "data" / "cli.yaml"
DEFAULT_COUNCIL_DIR = CORE / "claude" / "agents" / "council"
BODY_END = "<!-- body-end -->"
DEFAULT_TIMEOUT = 900
PROMPT_PLACEHOLDER = "<prompt>"
HOW_SUFFIX = " (chỉ qua"  # detect_models.py writes: `agy -p <prompt> --model <id> (chỉ qua ...); <title>`
HINTS_SHOWN = 5

HEADER = """# Lời giao

- decision: {decision}
- round: {round}
- perspective: {perspective}
- member: {member}
- model: {model}
- via: cli

Bạn là thành viên hội đồng. Làm đúng phần HƯỚNG DẪN dưới đây trên phần BRIEF{summary_note}. Không dùng công cụ nào (không đọc file, không chạy lệnh): mọi thông tin bạn cần nằm ở đây. Trả lời bằng toàn bộ nội dung đúng một phiếu và không gì khác, bắt đầu bằng dòng `---`.
"""


class CallError(Exception):
    """Exit 1: the call cannot produce a vote."""


@dataclass
class Row:
    name: str
    kind: str
    command: list[str]   # the row's own command: [exe, "-p", "<prompt>", "--model", id]
    status: str

    @property
    def exe(self) -> str:
        return self.command[0]

    @property
    def model_id(self) -> str:
        return self.command[self.command.index("--model") + 1]


# --- configuration ---------------------------------------------------------------------------------------------------------

def load_cli_config(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"{path}: {error}") from error
    clis = data.get("clis") if isinstance(data, dict) else None
    if not isinstance(clis, dict) or not clis:
        raise ValueError(f"{path}: thiếu mục clis")
    for name, spec in clis.items():
        stdin = spec.get("stdin") if isinstance(spec, dict) else None
        if stdin is None:
            continue
        ok = (
            isinstance(stdin, dict)
            and isinstance(stdin.get("args"), list) and all(isinstance(a, str) for a in stdin["args"])
            and isinstance(stdin.get("message"), dict)
            and isinstance(stdin.get("result"), dict)
            and all(isinstance(stdin["result"].get(k), str) for k in ("event", "key", "status_key", "ok", "text_key", "error_key"))
        )
        if not ok:
            raise ValueError(f"{path}: clis.{name}.stdin phải có args, message, result (event, key, status_key, ok, text_key, error_key)")
        lock = spec.get("lock")
        if lock is not None:
            ok = (
                isinstance(lock, dict)
                and all(isinstance(lock.get(k), str) and lock[k] for k in ("agent", "file", "text", "canary_prompt"))
                and isinstance(lock.get("flags"), list) and all(isinstance(a, str) for a in lock["flags"])
                and isinstance(lock.get("forbidden_steps"), list) and lock["forbidden_steps"]
                and isinstance(lock.get("steps"), dict) and all(isinstance(lock["steps"].get(k), str) for k in ("event", "key", "type_key"))
                and "{nonce}" in lock.get("text", "") and "{agent}" in " ".join(lock.get("flags", []))
            )
            if not ok:
                raise ValueError(f"{path}: clis.{name}.lock phải có agent, flags (có {{agent}}), file, text (có {{nonce}}), canary_prompt, forbidden_steps, steps (event, key, type_key)")
        limit = spec.get("argv_limit")
        if not isinstance(limit, dict) or not all(isinstance(limit.get(k), int) for k in ("windows", "other")):
            raise ValueError(f"{path}: clis.{name}.argv_limit phải có windows và other (số nguyên)")
    return clis


def parse_row(workspace: Path, model: str) -> Row:
    models_path = workspace / "models.md"
    if not models_path.is_file():
        raise CallError(f"không có {models_path}: chạy detect_models.py (G0) trước")
    rows = dm.previous_rows(models_path.read_text(encoding=ENCODING))
    cells = rows.get(model)
    if cells is None:
        raise LookupError(f"model {model} không có trong models.md (có: {', '.join(rows) or 'không có dòng nào'})")
    name, kind, how, _web, status = cells[0], cells[1], cells[2], cells[3], cells[4]
    if kind != "cli":
        raise LookupError(f"{model} là model loại {kind}, không phải qua CLI ngoài: dùng làm subagent Claude, không dùng script này")
    if status != dm.STATUS_OK:
        raise CallError(f"{model} có trạng thái \"{status}\" trong models.md: chỉ model \"{dm.STATUS_OK}\" (đã --probe đạt) mới được dùng")
    command_text = how.split(HOW_SUFFIX)[0].strip()
    try:
        command = shlex.split(command_text)
    except ValueError as error:
        raise CallError(f"cột \"Cách gọi\" của {model} không đọc được ({error}): {how}")
    if PROMPT_PLACEHOLDER not in command or "--model" not in command or command.index("--model") + 1 >= len(command):
        raise CallError(f"cột \"Cách gọi\" của {model} phải có `{PROMPT_PLACEHOLDER}` và `--model <id>`: {how}")
    row = Row(name, kind, command, status)
    if name != f"{row.exe}:{row.model_id}":
        raise CallError(f"tên {name} không khớp lệnh trong cột \"Cách gọi\" ({row.exe}:{row.model_id})")
    return row


# --- the prompt ------------------------------------------------------------------------------------------------------------

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.casefold()).strip("-")


def council_body(path: Path) -> str:
    if not path.is_file():
        raise CallError(f"không có file góc nhìn {path}")
    raw, body = tv.split_frontmatter(path.read_text(encoding=ENCODING))
    lines = body.splitlines()
    cut = [i for i, line in enumerate(lines) if line.strip() == BODY_END]
    if len(cut) != 1:
        raise CallError(f"{path.name} phải có đúng một dòng {BODY_END} (có {len(cut)})")
    return "\n".join(lines[: cut[0]]).strip()


def build_prompt(brief: tv.Brief, round_no: int, perspective: str, member: str, model: str, body: str, brief_text: str, summary: str | None) -> str:
    head = HEADER.format(decision=brief.decision, round=round_no, perspective=perspective, member=member, model=model,
                         summary_note=" và TÓM TẮT VÒNG 1" if summary is not None else "")
    parts = [head, "=== HƯỚNG DẪN ===", body, "=== BRIEF ===", brief_text.strip()]
    if summary is not None:
        parts += ["=== TÓM TẮT VÒNG 1 (ẩn danh) ===", summary.strip()]
    parts.append("=== HẾT ===")
    return "\n\n".join(parts) + "\n"


# --- calling the CLI -------------------------------------------------------------------------------------------------------

def substitute(value, replacements: dict[str, str]):
    if isinstance(value, str):
        for key, text in replacements.items():
            value = value.replace(key, text)
        return value
    if isinstance(value, dict):
        return {k: substitute(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, replacements) for v in value]
    return value


@dataclass
class Outcome:
    text: str = ""
    error: str = ""
    rejected_flags: bool = False   # no event on stdout and a non-zero exit: the CLI did not understand the stdin flags
    steps: list[str] = field(default_factory=list)   # type of each step the CLI reports (a `tool` step = a tool was used)


def run_process(argv: list[str], stdin: bytes | None, timeout: int, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(argv, input=stdin if stdin is not None else b"", capture_output=True, timeout=timeout, cwd=cwd)


def tail(data: bytes, limit: int = 300) -> str:
    text = data.decode(ENCODING, errors="replace").strip()
    return text[-limit:]


def call_stdin(prefix: list[str], row: Row, spec: dict, prompt: str, timeout: int, cwd: str, extra: list[str] | None = None) -> Outcome:
    stdin_spec = spec["stdin"]
    args = substitute(stdin_spec["args"], {"{model}": row.model_id})
    message = substitute(stdin_spec["message"], {"{prompt}": prompt})
    payload = (json.dumps(message, ensure_ascii=False) + "\n").encode(ENCODING)
    try:
        proc = run_process([*prefix, *args, *(extra or [])], payload, timeout, cwd)
    except subprocess.TimeoutExpired:
        return Outcome(error=f"quá {timeout}s không có câu trả lời")
    except OSError as error:
        return Outcome(error=f"không chạy được {prefix[0]}: {error}")
    result_spec = stdin_spec["result"]
    events = []
    for line in proc.stdout.decode(ENCODING, errors="replace").splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and "event" in data:
            events.append(data)
    if not events:
        detail = tail(proc.stderr) or tail(proc.stdout)
        return Outcome(error=f"CLI không in sự kiện nào (mã {proc.returncode}): {detail}", rejected_flags=proc.returncode != 0)
    steps_spec = (spec.get("lock") or {}).get("steps")
    steps = []
    if steps_spec:
        for event in events:
            if event.get("event") == steps_spec["event"]:
                detail = event.get(steps_spec["key"])
                steps.append(str(detail.get(steps_spec["type_key"])) if isinstance(detail, dict) else "?")
    results = [e for e in events if e.get("event") == result_spec["event"]]
    if not results:
        return Outcome(error=f"CLI không in sự kiện \"{result_spec['event']}\" (mã {proc.returncode}): {tail(proc.stderr)}", steps=steps)
    payload_result = results[-1].get(result_spec["key"])
    if not isinstance(payload_result, dict):
        return Outcome(error=f"sự kiện \"{result_spec['event']}\" không có khóa \"{result_spec['key']}\"", steps=steps)
    status = payload_result.get(result_spec["status_key"])
    if status != result_spec["ok"] or proc.returncode != 0:
        reason = payload_result.get(result_spec["error_key"]) or tail(proc.stderr) or "không rõ"
        return Outcome(error=f"CLI báo {result_spec['status_key']} {status!r}, mã {proc.returncode}: {reason}", steps=steps)
    return Outcome(text=str(payload_result.get(result_spec["text_key"]) or ""), steps=steps)


def argv_limit(spec: dict | None) -> int:
    limit = (spec or {}).get("argv_limit") or {"windows": 30000, "other": 120000}
    return limit["windows"] if sys.platform == "win32" else limit["other"]


def call_argv(prefix: list[str], row: Row, spec: dict | None, prompt: str, timeout: int, cwd: str, extra: list[str] | None = None) -> Outcome:
    argv = [*prefix, *substitute(row.command[1:], {PROMPT_PLACEHOLDER: prompt}), *(extra or [])]
    length = len(subprocess.list2cmdline(argv)) if sys.platform == "win32" else sum(len(a) + 1 for a in argv)
    if length > argv_limit(spec):
        return Outcome(error=f"prompt đưa qua đối số dài {length} ký tự, quá giới hạn dòng lệnh {argv_limit(spec)}: không cắt; dùng cách stdin (--mode stdin) hoặc rút brief")
    try:
        proc = run_process(argv, None, timeout, cwd)
    except subprocess.TimeoutExpired:
        return Outcome(error=f"quá {timeout}s không có câu trả lời")
    except OSError as error:
        return Outcome(error=f"không chạy được {argv[0]}: {error}")
    if proc.returncode != 0:
        return Outcome(error=f"CLI thoát mã {proc.returncode}: {tail(proc.stderr) or tail(proc.stdout)}")
    return Outcome(text=proc.stdout.decode(ENCODING, errors="replace"))


def forbidden_steps(outcome: Outcome, lock: dict) -> list[str]:
    return [step for step in outcome.steps if step in lock["forbidden_steps"]]


def call_cli(prefix: list[str], row: Row, clis: dict, mode: str, prompt: str, timeout: int) -> tuple[str, str, list[str]]:
    """Returns (answer, way used, notes for the report). Raises CallError.

    The CLI always runs as a locked agent (data/cli.yaml `lock`): an agent definition with no tools and no MCP, written into an empty
    temporary folder that is the working directory. A CLI that does not know the agent falls back to its default agent with every
    tool (it reports success either way), so before the brief is sent a first call asks for the secret code written in the
    agent's own system prompt; only a CLI that answers with it has loaded the lock. Any tool step in an answer voids it."""
    spec = clis.get(row.exe)
    lock = spec.get("lock") if spec else None
    if not lock:
        raise CallError(f"cli.yaml không có mục lock cho {row.exe}: chưa cô lập được công cụ của CLI này nên không đưa brief cho nó")
    has_stdin = bool(spec.get("stdin"))
    if mode == "stdin" and not has_stdin:
        raise CallError(f"cli.yaml không mô tả cách đưa prompt qua stdin cho {row.exe}")
    nonce = "NONCE-" + secrets.token_hex(6)
    agent = lock["agent"]
    with tempfile.TemporaryDirectory(prefix="council-", ignore_cleanup_errors=True) as folder:
        definition = Path(folder) / lock["file"].replace("{agent}", agent)
        definition.parent.mkdir(parents=True, exist_ok=True)
        definition.write_text(substitute(lock["text"], {"{agent}": agent, "{nonce}": nonce}), encoding=ENCODING, newline="\n")
        extra = substitute(lock["flags"], {"{agent}": agent})

        def run(way: str, text: str) -> Outcome:
            if way == "stdin":
                return call_stdin(prefix, row, spec, text, timeout, folder, extra)
            return call_argv(prefix, row, spec, text, timeout, folder, extra)

        way = "stdin" if mode in ("auto", "stdin") and has_stdin else "argv"
        canary = run(way, lock["canary_prompt"])
        if canary.rejected_flags and mode == "auto" and way == "stdin":
            way = "argv"
            canary = run(way, lock["canary_prompt"])
        if canary.error:
            raise CallError(f"{row.name} ({way}): kiểm khóa công cụ lỗi: {canary.error}")
        if nonce not in canary.text:
            raise CallError(f"{row.name} ({way}): CLI không nạp agent khóa công cụ `{agent}` (nó không đọc ra mã xác nhận trong prompt hệ thống của agent): không đưa brief cho nó")
        bad = forbidden_steps(canary, lock)
        if bad:
            raise CallError(f"{row.name} ({way}): CLI gọi công cụ ({', '.join(bad)}) ngay ở bước kiểm khóa")
        outcome = run(way, prompt)
        if outcome.error:
            raise CallError(f"{row.name} ({way}): {outcome.error}")
        bad = forbidden_steps(outcome, lock)
        if bad:
            raise CallError(f"{row.name} ({way}): CLI gọi công cụ ({len(bad)} bước {', '.join(sorted(set(bad)))}) dù đã khóa: bỏ kết quả, không ghi phiếu")
    answer = outcome.text.strip()
    if not answer:
        raise CallError(f"{row.name} ({way}): CLI trả về nội dung rỗng")
    notes = [f"khóa công cụ: agent `{agent}` (không công cụ, không MCP), nạp đạt (mã xác nhận đọc ra đúng)"]
    notes.append(f"bước công cụ trong câu trả lời: {len(forbidden_steps(outcome, lock))}" if way == "stdin" else "bước công cụ: chưa kiểm được ở cách argv (CLI chỉ in văn bản)")
    return answer, way, notes


# --- main ------------------------------------------------------------------------------------------------------------------

def append_report(workspace: Path, today: str, lines: list[str]) -> Path:
    target = workspace / "checks" / f"council-cli-{today}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = tv.read_text(target) if target.is_file() else f"# call_council_cli {today}\n"
    tv.write_text(target, existing.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--decision", required=True, help="folder name of the decision (D-007-name) or its path")
    parser.add_argument("--round", type=int, required=True, choices=(1, 2))
    parser.add_argument("--perspective", required=True, help="fit, cost-ops, numbers-nfr, evolution or risk-data")
    parser.add_argument("--model", required=True, help="name of a cli row of models.md, for example agy:gemini-3.8-flash-low")
    parser.add_argument("--mode", choices=("auto", "stdin", "argv"), default="auto", help="how the prompt reaches the CLI (default auto: stdin, argument when the CLI rejects the stdin flags)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds to wait for the CLI (default %(default)s)")
    parser.add_argument("--overwrite", action="store_true", help="replace a vote file that exists")
    parser.add_argument("--config", type=Path, default=tv.DEFAULT_CONFIG, help="council sizes (default: core/data/council.yaml)")
    parser.add_argument("--cli-config", type=Path, default=DEFAULT_CLI_CONFIG, help="how to call each CLI (default: core/data/cli.yaml)")
    parser.add_argument("--council-dir", type=Path, default=DEFAULT_COUNCIL_DIR, help=argparse.SUPPRESS)
    parser.add_argument("--cli-prefix", action="append", help=argparse.SUPPRESS)  # tests: replace the executable by this command
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout phải là số dương")
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    cfg, config_errors = tv.load_config(args.config.resolve())
    if cfg is None:
        print("config error: " + "; ".join(config_errors), file=sys.stderr)
        return 2
    try:
        clis = load_cli_config(args.cli_config.resolve())
    except ValueError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 2
    directories = tv.discover(workspace, args.decision)
    if not directories:
        print(f"not a decision folder: {args.decision}", file=sys.stderr)
        return 2
    directory = directories[0]
    if args.perspective not in cfg.perspectives:
        print(f"perspective phải là một trong {', '.join(cfg.perspectives)}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    rel_dir = directory.relative_to(workspace).as_posix()
    try:
        brief_text = tv.read_text(directory / "brief.md")
        brief, problems = tv.parse_brief(brief_text, directory.name, f"{rel_dir}/brief.md")
        if brief is None:
            raise CallError("brief không hợp lệ: " + "; ".join(p.render() for p in problems))
        if brief.size not in cfg.sizes or args.perspective not in cfg.sizes[brief.size]:
            print(f"hội đồng {brief.size} thành viên không có góc nhìn {args.perspective}", file=sys.stderr)
            return 2
        try:
            row = parse_row(workspace, args.model)
        except LookupError as error:
            print(str(error), file=sys.stderr)
            return 2
        summary = None
        if args.round == 2:
            summary_path = directory / "votes" / tv.SUMMARY_NAME
            if not summary_path.is_file():
                raise CallError(f"vòng 2 cần {rel_dir}/votes/{tv.SUMMARY_NAME}: chạy tally_votes.py sau khi đủ phiếu vòng 1")
            summary = tv.read_text(summary_path)
        member = slug(row.name)
        target = directory / "votes" / f"r{args.round}-{args.perspective}-{member}.md"
        if target.exists() and not args.overwrite:
            raise CallError(f"{target.relative_to(workspace).as_posix()} đã có (phiếu vòng 1 phải độc lập, không ghi đè lặng lẽ): dùng --overwrite nếu muốn thay")
        body = council_body(args.council_dir / f"{args.perspective}.md")
        prompt = build_prompt(brief, args.round, args.perspective, member, row.model_id, body, brief_text, summary)
        prefix = args.cli_prefix or [shutil.which(row.exe) or row.exe]
        answer, way, notes = call_cli(prefix, row, clis, args.mode, prompt, args.timeout)
    except CallError as error:
        append_report(workspace, today, [f"## {args.decision} · vòng {args.round} · {args.perspective} · {args.model}", "", f"- LỖI: {error}"])
        print(f"error: {error}")
        return 1
    tv.write_text(target, answer + "\n")
    rel = target.relative_to(workspace).as_posix()
    vote, errors, _ = tv.validate_vote(answer + "\n", rel, args.round, args.perspective, member, brief, cfg)
    hints = [e.render() for e in errors]
    lines = [f"## {args.decision} · vòng {args.round} · {args.perspective} · {args.model}", "", f"- Đã ghi: {rel} ({len(answer)} ký tự, cách gọi: {way})"]
    lines += [f"- {note}" for note in notes]
    lines += [f"- định dạng chưa đạt (tally_votes.py sẽ từ chối): {h}" for h in hints] or ["- định dạng: đạt kiểm của tally_votes.py (chưa đếm)"]
    report = append_report(workspace, today, lines)
    print(f"call_council_cli: đã ghi {rel} (cách gọi: {way}); báo cáo: {report}")
    for hint in hints[:HINTS_SHOWN]:
        print(f"warning: phiếu chưa đúng định dạng, tally_votes.py sẽ từ chối: {hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
