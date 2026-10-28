# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Generate the Antigravity agents of design-core (`core/agents/`) from the Claude Code ones (`core/claude/agents/`).

This is a build script, not a check script: it lives outside `core/` (the installed plugin) so that no agent can run it
by accident. `core/scripts/test_gen_antigravity.py` runs `--check`, which fails when `core/agents/` differs from what
this script would write.

    uv run families/design-system/tools/gen_antigravity.py            # write core/agents/
    uv run families/design-system/tools/gen_antigravity.py --check    # exit 1 if core/agents/ is out of date

Mapping (BUILD-PROGRESS.md, "Bản Antigravity"): tools, model and names are the tables below; nothing else is invented.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent / "core"
SOURCE = CORE / "claude" / "agents"
TARGET = CORE / "agents"
BODY_END = "<!-- body-end -->"
CLAUDE_PREFIX = "design-core:"
PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"
PLUGIN_DIR_PLACEHOLDER = "<DESIGN_CORE_DIR>"

# Claude Code agent name -> Antigravity agent name. The one place the names are written.
NAMES = {
    "orchestrator": "design-orchestrator",
    "planner": "design-planner",
    "researcher": "design-researcher",
    "designer": "design-designer",
    "reviewer": "design-reviewer",
    "council-cost-ops": "design-council-cost-ops",
    "council-evolution": "design-council-evolution",
    "council-fit": "design-council-fit",
    "council-numbers-nfr": "design-council-numbers-nfr",
    "council-risk-data": "design-council-risk-data",
}

# Claude Code tool -> Antigravity tools. `Glob` also gives `list_dir`.
TOOL_MAP = {
    "Read": ["view_file"],
    "Glob": ["list_dir", "find_by_name"],
    "Grep": ["grep_search"],
    "Write": ["write_to_file"],
    "Edit": ["replace_file_content"],
    "Bash": ["run_command"],
    "Agent": ["invoke_subagent"],
    "WebSearch": ["search_web"],
    "WebFetch": ["read_url_content"],
}
TOOL_ORDER = [
    "view_file", "list_dir", "find_by_name", "grep_search", "write_to_file", "replace_file_content",
    "run_command", "search_web", "read_url_content", "invoke_subagent",
]
MODELS = {"inherit": "inherit"}  # Claude `model` -> Antigravity `model` (inherit | flash | pro)
SANDBOXED = {"orchestrator", "reviewer"}  # agents with run_command get commandExecutionPolicy: sandbox
MAIN_AGENT = "orchestrator"

# The Claude Code only wording of the council files' last section, made neutral (exact strings, checked).
COUNCIL_EDITS = [
    ("## Cách giao phiếu (Claude Code)", "## Cách giao phiếu"),
    ("chỉ áp dụng khi bạn chạy như subagent Claude Code.", "chỉ áp dụng khi bạn chạy như subagent."),
]

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def read(path: Path) -> str:
    return path.read_bytes().decode(ENCODING).replace("\r\n", "\n")


def source_files() -> list[Path]:
    return sorted([*SOURCE.glob("*.md"), *(SOURCE / "council").glob("*.md")])


def split(text: str, path: Path) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError(f"{path}: no frontmatter")
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return meta, match.group(2)


def tools_for(claude_tools: str, path: Path) -> list[str]:
    result: set[str] = set()
    for tool in (item.strip() for item in claude_tools.split(",") if item.strip()):
        if tool not in TOOL_MAP:
            raise ValueError(f"{path}: no Antigravity tool for {tool!r}")
        result.update(TOOL_MAP[tool])
    return [tool for tool in TOOL_ORDER if tool in result]


def rename_references(body: str) -> str:
    """`design-core:<name>` -> the Antigravity name; `${CLAUDE_PLUGIN_ROOT}` -> a placeholder the agent resolves."""
    for claude_name, agy_name in NAMES.items():
        body = body.replace(CLAUDE_PREFIX + claude_name, agy_name)
    return body.replace(PLUGIN_ROOT_VAR, PLUGIN_DIR_PLACEHOLDER)


def orchestrator_notes() -> str:
    rows = "\n".join(f"| `{claude}` | `{agy}` |" for claude, agy in NAMES.items() if claude != MAIN_AGENT)
    return (
        "## Chạy trên Antigravity\n\n"
        "Bản sinh cho Antigravity CLI; chỗ nào bên dưới nói khác thì theo mục này.\n\n"
        "- Gọi agent con bằng `invoke_subagent`, theo đúng tên ở bảng. Chữ `planner`, `designer`, `fit`... ở các mục dưới "
        "là tên Claude Code.\n"
        f"- `{PLUGIN_DIR_PLACEHOLDER}` là thư mục cài của plugin design-core. Lấy một lần bằng `agy plugin list --json`, "
        "đọc trường `path` của plugin `design-core`, rồi thay vào mọi lệnh có chữ này. Thư mục template cho "
        "`--templates` là trường `path` của plugin `design-architecture` cộng `/templates`.\n"
        "- Agent con không có `run_command` không tự tìm đường dẫn: khi giao việc, ghi đường dẫn đã giải (thư mục "
        "design-core, thư mục template) vào lời giao.\n"
        "- Bản này không có hook `guard_write.py`: quy tắc ai được ghi đâu chỉ nằm trong prompt, Reviewer soát.\n\n"
        "| Tên Claude Code | Tên Antigravity |\n| --- | --- |\n" + rows + "\n\n"
    )


def reviewer_notes() -> str:
    return (
        "## Chạy trên Antigravity\n\n"
        f"- `{PLUGIN_DIR_PLACEHOLDER}` là thư mục cài của plugin design-core. Lấy bằng `agy plugin list --json`, "
        "đọc trường `path` của plugin `design-core`. Template cho `--templates`: trường `path` của plugin "
        "`design-architecture` cộng `/templates`; lời giao đã ghi đường dẫn thì dùng đường dẫn đó.\n"
        "- Bản này không có hook `guard_write.py`: tự giữ đúng quyền ghi ở mục \"Được ghi\".\n\n"
    )


NOTES = {"orchestrator": orchestrator_notes, "reviewer": reviewer_notes}


def render(path: Path) -> tuple[str, str]:
    """Return (file name in core/agents/, content) for one Claude Code agent file."""
    meta, body = split(read(path), path)
    claude_name = meta["name"]
    if claude_name not in NAMES:
        raise ValueError(f"{path}: agent {claude_name!r} is missing from NAMES")
    if meta.get("model") not in MODELS:
        raise ValueError(f"{path}: no Antigravity model for {meta.get('model')!r}")
    is_main = claude_name == MAIN_AGENT
    is_council = claude_name.startswith("council-")
    if is_council:
        before, marker, after = body.partition(BODY_END)
        if not marker:
            raise ValueError(f"{path}: no {BODY_END} line")
        for old, new in COUNCIL_EDITS:
            if old not in after:
                raise ValueError(f"{path}: expected text not found: {old!r}")
            after = after.replace(old, new)
        body = before.rstrip("\n") + "\n" + after
    body = rename_references(body).lstrip("\n")
    tools = tools_for(meta["tools"], path)
    lines = [
        "---",
        f"name: {NAMES[claude_name]}",
        f"description: {json.dumps(meta['description'], ensure_ascii=False)}",
        f"tools: [{', '.join(tools)}]",
        f"model: {MODELS[meta['model']]}",
        f"mainAgent: {str(is_main).lower()}",
        f"subagent: {str(not is_main).lower()}",
    ]
    if not is_main:
        lines += ["inheritMcp: false", "excludeDefaultComponents: true"]
    if claude_name in SANDBOXED:
        lines.append("commandExecutionPolicy: sandbox")
    lines += ["---", ""]
    header = f"<!-- Sinh bởi families/design-system/tools/gen_antigravity.py từ core/claude/agents/{path.relative_to(SOURCE).as_posix()}. Không sửa tay. -->\n\n"
    notes = NOTES.get(claude_name, lambda: "")()
    return f"{NAMES[claude_name]}.md", "\n".join(lines) + header + notes + body


def render_all() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in source_files():
        name, content = render(path)
        if name in result:
            raise ValueError(f"two agents produce {name}")
        result[name] = content
    return result


def problems(expected: dict[str, str], target: Path) -> list[str]:
    found = []
    for name, content in expected.items():
        file = target / name
        if not file.is_file():
            found.append(f"missing: {name}")
        elif read(file) != content:
            found.append(f"out of date: {name}")
    if target.is_dir():
        found += [f"unexpected: {file.name}" for file in sorted(target.iterdir()) if file.name not in expected]
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if core/agents/ is out of date")
    parser.add_argument("--target", type=Path, default=TARGET, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    expected = render_all()
    if args.check:
        found = problems(expected, args.target)
        for line in found:
            print(line)
        print(f"gen_antigravity --check: {len(found)} problem(s), {len(expected)} agent(s)")
        return 1 if found else 0
    args.target.mkdir(parents=True, exist_ok=True)
    for stale in args.target.iterdir():
        if stale.name not in expected:
            stale.unlink()
    for name, content in expected.items():
        (args.target / name).write_bytes(content.encode(ENCODING))
    print(f"gen_antigravity: wrote {len(expected)} agent(s) to {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
