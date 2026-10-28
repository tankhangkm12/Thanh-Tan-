"""Detect which models the design-system workflow can call here and write `.agent-workspace/models.md`.

Two kinds of line, as PLAN.md ("Hai cách gọi model") says:

- `subagent`: a Claude Code model the Orchestrator passes in the `model` parameter of the Agent tool;
- `cli`: a model of another CLI (Antigravity `agy`), only usable as a council member through `call_council_cli.py`.

Detection is static: the Claude aliases are listed and `agy models` lists what Antigravity offers. A model is "chưa thử"
(and not usable) until `--probe NAME,NAME` really calls it once (costs tokens). Only the named models are called; the
Orchestrator runs this once at G0 for the models it plans to use. `--probe` without a list is an argument error.
Warns when `CLAUDE_CODE_SUBAGENT_MODEL` or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set, because they can override the
model the Orchestrator picks.

Only the block between the `detect` markers is rewritten. The "Gán model" table below it, the columns "Điểm mạnh" and
"Giới hạn", and the "gọi được" / "không dùng được" result of an earlier probe are kept from the previous run.

    uv run detect_models.py [--workspace DIR] [--probe NAME,NAME] [--web-models ID,ID] [--claude-models A,B]
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ENCODING = "utf-8"
BEGIN = "<!-- BEGIN:detect -->"
END = "<!-- END:detect -->"
TITLE = "# Danh mục model"
ASSIGN_HEADING = "## Gán model"
ASSIGN_TABLE = "| Task | Agent | Model | Ngày |\n| --- | --- | --- | --- |\n"

# Aliases of https://code.claude.com/docs/en/model-config ("Model aliases"). --probe is what tells which really work here.
CLAUDE_ALIASES = ("sonnet", "opus", "haiku", "fable")
CLAUDE_WEB = "có (WebSearch, WebFetch của Claude Code: theo tool của agent, không theo model)"
PROBE_PROMPT = "Trả lời đúng một từ: ok"
PROBE_TIMEOUT = 120

ENV_OVERRIDE = "CLAUDE_CODE_SUBAGENT_MODEL"
ENV_FORCE = "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"
# https://code.claude.com/docs/en/sub-agents#choose-a-model: before this version the env var beat the per-call `model`.
ENV_OVERRIDES_CALL_BEFORE = (2, 1, 251)

# External CLIs. Verified with `agy --help` / `agy models` (Antigravity CLI 1.3.3): `agy models` prints
# "<id>\t<display name>" per line; `agy -p <prompt> --model <id>` runs one prompt without interaction.
EXTERNAL_CLIS = {
    "agy": {
        "title": "Antigravity CLI",
        "list_args": ["models"],
        "call": "agy -p <prompt> --model {model}",
        # Default text of the "Giới hạn" column (a person's own text replaces it): what a CLI call can and cannot do.
        "limits": "chỉ làm thành viên hội đồng qua `call_council_cli.py`, nơi agy chạy bằng agent khóa công cụ (không công cụ, không MCP, thư mục tạm rỗng, kiểm bằng mã xác nhận); "
                  "agy gọi trực tiếp thì KHÔNG cô lập: đủ công cụ, đọc được mọi file, ghi được file kể cả `--mode plan`",
    },
}

COLUMNS = ("Tên", "Loại", "Cách gọi", "Tìm web", "Trạng thái", "Điểm mạnh", "Giới hạn")
STATUS_STATIC = "chưa thử"
STATUS_OK = "gọi được"
STATUS_BAD = "không dùng được"
UNSET = "chưa khai"

Runner = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]


class UnknownModels(ValueError):
    def __init__(self, unknown: list[str], known: list[str]):
        super().__init__(f"model không có trong danh mục: {', '.join(unknown)}. Tên hợp lệ: {', '.join(known)}")


@dataclass
class ModelRow:
    name: str
    kind: str  # "subagent" | "cli"
    how: str
    web: str
    status: str = STATUS_STATIC
    strengths: str = UNSET
    limits: str = UNSET
    # for probing
    command: list[str] | None = None

    @property
    def usable(self) -> bool:
        # Only a model that answered a probe counts; "chưa thử" is not usable.
        return self.status == STATUS_OK


def run_command(argv: list[str], timeout: int) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(argv, capture_output=True, text=True, encoding=ENCODING, errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)


def parse_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(part) for part in match.groups()) if match else None


def claude_version(which: Callable[[str], str | None], run: Runner) -> tuple[str, tuple[int, ...] | None]:
    path = which("claude")
    if not path:
        return "", None
    try:
        result = run([path, "--version"], 30)
    except (OSError, subprocess.SubprocessError):
        return path, None
    return path, parse_version(result.stdout) if result.returncode == 0 else None


def env_warnings(env: dict[str, str], version: tuple[int, ...] | None) -> list[str]:
    warnings = []
    if env.get(ENV_FORCE):
        warnings.append(
            f"`{ENV_FORCE}` đang đặt ({env[ENV_FORCE]!r}): mọi subagent có thể bị ép chạy một model, kể cả khi Orchestrator "
            "truyền `model` lúc gọi. Phân công model khác nhau cho Reviewer và hội đồng sẽ không còn đúng. Bỏ biến này trước khi chạy workflow."
        )
    if env.get(ENV_OVERRIDE):
        if version is not None and version >= ENV_OVERRIDES_CALL_BEFORE:
            note = "Claude Code từ v2.1.251 ưu tiên `model` truyền lúc gọi nên biến này chỉ là mặc định; vẫn nên bỏ để tránh nhầm."
        elif version is None:
            note = "Không đọc được phiên bản Claude Code; trước v2.1.251 biến này ghi đè cả `model` truyền lúc gọi."
        else:
            note = "Claude Code bản này (trước v2.1.251) cho biến này ghi đè cả `model` truyền lúc gọi."
        warnings.append(f"`{ENV_OVERRIDE}` đang đặt ({env[ENV_OVERRIDE]!r}). {note}")
    return warnings


def claude_rows(aliases: list[str], claude_path: str) -> list[ModelRow]:
    return [
        ModelRow(
            name=alias,
            kind="subagent",
            how=f'Agent tool, tham số `model: "{alias}"`',
            web=CLAUDE_WEB,
            command=[claude_path, "-p", PROBE_PROMPT, "--model", alias] if claude_path else None,
        )
        for alias in aliases
    ]


def parse_agy_models(text: str) -> list[tuple[str, str]]:
    """Lines of `agy models` look like `<id>\\t<display name>`; the 'Fetching…' line has no tab."""
    models = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        model_id, _, title = line.partition("\t")
        if model_id.strip():
            models.append((model_id.strip(), title.strip()))
    return models


def external_rows(which: Callable[[str], str | None], run: Runner, web_models: set[str], warnings: list[str]) -> list[ModelRow]:
    rows: list[ModelRow] = []
    for cli, spec in EXTERNAL_CLIS.items():
        path = which(cli)
        if not path:
            warnings.append(f"CLI `{cli}` ({spec['title']}) không có trong PATH: bỏ qua.")
            continue
        try:
            result = run([path, *spec["list_args"]], 60)
        except (OSError, subprocess.SubprocessError) as error:
            warnings.append(f"`{cli} {' '.join(spec['list_args'])}` lỗi: {error}")
            continue
        models = parse_agy_models(result.stdout) if result.returncode == 0 else []
        if not models:
            warnings.append(f"`{cli} {' '.join(spec['list_args'])}` không trả về model nào (mã {result.returncode}).")
            continue
        for model_id, title in models:
            name = f"{cli}:{model_id}"
            rows.append(
                ModelRow(
                    name=name,
                    kind="cli",
                    how=f"{spec['call'].format(model=model_id)} (chỉ qua `call_council_cli.py`, thành viên hội đồng); {title}",
                    web="có" if (name in web_models or model_id in web_models) else "chưa rõ",
                    limits=spec.get("limits", UNSET),
                    command=[path, "-p", PROBE_PROMPT, "--model", model_id],
                )
            )
    return rows


def probe(rows: list[ModelRow], run: Runner, timeout: int) -> None:
    for row in rows:
        if row.command is None:
            row.status = f"{STATUS_BAD}: không có lệnh để thử"
            continue
        try:
            result = run(row.command, timeout)
        except subprocess.TimeoutExpired:
            row.status = f"{STATUS_BAD}: quá {timeout}s"
            continue
        except (OSError, subprocess.SubprocessError) as error:
            row.status = f"{STATUS_BAD}: {error}"
            continue
        if result.returncode == 0 and result.stdout.strip():
            row.status = STATUS_OK
        else:
            detail = (result.stderr or result.stdout).strip().splitlines()
            row.status = f"{STATUS_BAD}: mã {result.returncode}" + (f", {detail[-1][:120]}" if detail else "")


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [part.replace("\\|", "|").strip() for part in cells]


def previous_rows(text: str) -> dict[str, list[str]]:
    """Rows of the old block by name, so manual cells survive a re-run."""
    if BEGIN not in text or END not in text:
        return {}
    block = text[text.index(BEGIN) : text.index(END)]
    rows = {}
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) == len(COLUMNS) and cells[0] not in ("Tên", "---") and not set(cells[0]) <= {"-", " "}:
            rows[cells[0]] = cells
    return rows


def keep_manual(rows: list[ModelRow], old: dict[str, list[str]], probed: set[str]) -> None:
    """Keep manual cells, and the result of an earlier probe for a model that was not probed this time."""
    for row in rows:
        cells = old.get(row.name)
        if not cells:
            continue
        if cells[5] != UNSET:
            row.strengths = cells[5]
        if cells[6] != UNSET:
            row.limits = cells[6]  # a column left at "chưa khai" gets the current default instead
        if row.name not in probed and (cells[4] == STATUS_OK or cells[4].startswith(STATUS_BAD)):
            row.status = cells[4]


def table(rows: list[ModelRow]) -> str:
    out = ["| " + " | ".join(COLUMNS) + " |", "| " + " | ".join("---" for _ in COLUMNS) + " |"]
    for row in rows:
        values = (row.name, row.kind, row.how, row.web, row.status, row.strengths, row.limits)
        out.append("| " + " | ".join(cell(value) for value in values) + " |")
    return "\n".join(out)


def render_block(rows: list[ModelRow], warnings: list[str], version: tuple[int, ...] | None, today: str, probed: list[str]) -> str:
    version_text = ".".join(str(part) for part in version) if version else "không đọc được"
    mode = f"thử gọi: {', '.join(probed)}" if probed else "không thử gọi model nào"
    lines = [
        BEGIN,
        f"Dò bởi `detect_models.py` ngày {today} ({mode}). Claude Code: {version_text}.",
        "Model \"chưa thử\" chưa được coi là dùng được. Script viết lại khối này mỗi lần chạy, giữ cột \"Điểm mạnh\", \"Giới hạn\" và kết quả thử gọi trước.",
        "",
        "### Cảnh báo",
        "",
    ]
    lines += [f"- {w}" for w in warnings] or ["- không có"]
    for title, kind in (("Subagent Claude", "subagent"), ("Qua CLI ngoài", "cli")):
        selected = [row for row in rows if row.kind == kind]
        lines += ["", f"### {title}", ""]
        lines.append(table(selected) if selected else "Không có.")
    lines += ["", END]
    return "\n".join(lines)


def merge_into(existing: str, block: str) -> str:
    """Replace the old block, or add one after the title; make sure the 'Gán model' table is there."""
    if BEGIN in existing and END in existing and existing.index(BEGIN) < existing.index(END):
        start, stop = existing.index(BEGIN), existing.index(END) + len(END)
        text = existing[:start] + block + existing[stop:]
    elif existing.strip():
        lines = existing.splitlines()
        at = 1 if lines and lines[0].startswith("#") else 0
        text = "\n".join(lines[:at] + ([""] if at else []) + block.splitlines() + [""] + lines[at:])
    else:
        text = f"{TITLE}\n\n{block}"
    if ASSIGN_HEADING not in text:
        text = text.rstrip("\n") + f"\n\n{ASSIGN_HEADING}\n\n{ASSIGN_TABLE}"
    return text.rstrip("\n") + "\n"


def detect(
    existing: str,
    env: dict[str, str],
    which: Callable[[str], str | None],
    run: Runner,
    today: str,
    probe_names: list[str] | None = None,
    web_models: set[str] | None = None,
    claude_models: list[str] | None = None,
    probe_timeout: int = PROBE_TIMEOUT,
) -> tuple[str, list[ModelRow], list[str]]:
    claude_path, version = claude_version(which, run)
    warnings = env_warnings(env, version)
    if not claude_path:
        warnings.append("`claude` không có trong PATH: không thể dùng `--probe` cho model Claude (vẫn liệt kê alias để gọi qua Agent tool).")
    rows = claude_rows(claude_models or list(CLAUDE_ALIASES), claude_path)
    rows += external_rows(which, run, web_models or set(), warnings)
    names = probe_names or []
    unknown = [name for name in names if name not in {row.name for row in rows}]
    if unknown:
        raise UnknownModels(unknown, [row.name for row in rows])
    probe([row for row in rows if row.name in names], run, probe_timeout)
    keep_manual(rows, previous_rows(existing), set(names))
    for row in rows:
        if row.status.startswith(STATUS_BAD):
            warnings.append(f"`{row.name}`: {row.status}")
    block = render_block(rows, warnings, version, today, names)
    return merge_into(existing, block), rows, warnings


def write_check(workspace: Path, today: str, message: str) -> Path:
    path = workspace / "checks" / f"models-{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# detect_models {today}\n\n{message}\n", encoding=ENCODING, newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--probe", nargs="?", const="", default=None, metavar="NAME,NAME",
                        help="really call exactly these models once (costs tokens), e.g. sonnet,haiku,agy:<id>; the list is required")
    parser.add_argument("--probe-timeout", type=int, default=PROBE_TIMEOUT, help="seconds per call (default %(default)s)")
    parser.add_argument("--web-models", default="", help="comma-separated CLI model ids known to search the web")
    parser.add_argument("--claude-models", default="", help=f"comma-separated Claude aliases (default {','.join(CLAUDE_ALIASES)})")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    split = lambda value: [part.strip() for part in value.split(",") if part.strip()]  # noqa: E731
    probe_names = split(args.probe or "")
    if args.probe is not None and not probe_names:
        parser.error("--probe cần danh sách model cần thử, ví dụ --probe sonnet,haiku (không có danh sách thì không thử model nào)")
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    target = workspace / "models.md"
    existing = target.read_text(encoding=ENCODING) if target.is_file() else ""
    try:
        text, rows, warnings = detect(
            existing, dict(os.environ), shutil.which, run_command, today, probe_names,
            set(split(args.web_models)), split(args.claude_models) or None, args.probe_timeout,
        )
    except UnknownModels as error:
        parser.error(str(error))
    target.write_text(text, encoding=ENCODING, newline="\n")
    usable = [row for row in rows if row.usable]
    print(f"models.md: {len(rows)} model ({len(usable)} gọi được), {len(warnings)} cảnh báo")
    for warning in warnings:
        print(f"warning: {warning}")
    if probe_names and not usable:
        report = write_check(workspace, today, "Đã thử gọi mà không có model nào dùng được.\n\n" + "\n".join(f"- {w}" for w in warnings))
        print(f"error: đã thử gọi mà không có model nào dùng được; xem {report}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
