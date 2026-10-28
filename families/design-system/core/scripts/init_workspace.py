"""Create `.agent-workspace/` in a project for the design-system family, safely and repeatably.

What it does (and never overwrites anything that already exists):

- creates the `.agent-workspace/` folders of PLAN.md ("Cấu trúc .agent-workspace/") and copies the templates
  `state.md`, `questions.md`, `decisions/decision-log.md` and `risks/acceptance.md` into it;
- adds `.agent-workspace/` to the project's `.gitignore`;
- writes the one rule "read `.agent-workspace/state.md` before anything else" into the instruction file each CLI reads
  on its own: `CLAUDE.md` (Claude Code) and `GEMINI.md` (Antigravity CLI, which reads `AGENTS.md` too).
  An instruction file that already exists is left as it is, except for one marked block (added once, kept up to date,
  and only the text between its two markers is ever changed), and is not put in `.gitignore`.
  A file that does not exist is created and put in `.gitignore`.

    uv run init_workspace.py [PROJECT_DIR]
"""

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENCODING = "utf-8"
WORKSPACE = ".agent-workspace"
GITIGNORE = ".gitignore"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "workspace"

# Folders of the workspace tree. Files other than the templates are made later by the agents and scripts that own them.
DIRECTORIES = (
    "inputs/ba",
    "inputs/ui-design",
    "inputs/previous-design",
    "plan/tasks",
    "stack/layers",
    "capacity",
    "decisions",
    "risks",
    "drafts",
    "reviews",
    "checks",
    "archive",
)
# Template file -> path inside the workspace.
TEMPLATES = {
    "state.md": "state.md",
    "questions.md": "questions.md",
    "decision-log.md": "decisions/decision-log.md",
    "acceptance.md": "risks/acceptance.md",
}

CLAUDE_FILE = "CLAUDE.md"
CLAUDE_DIR_FILE = ".claude/CLAUDE.md"
GEMINI_FILE = "GEMINI.md"
AGENTS_FILE = "AGENTS.md"
AGENTS_IMPORT = "@AGENTS.md"

BEGIN = "<!-- design-system:agent-workspace:begin -->"
END = "<!-- design-system:agent-workspace:end -->"
RULE = f"Đọc `{WORKSPACE}/state.md` trước khi làm gì khác."
BLOCK = f"{BEGIN}\n{RULE}\n{END}\n"
NEW_FILE_TITLE = "# Hướng dẫn cho agent\n\n"


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def read(path: Path) -> str:
    # newline="" keeps the file's own line endings, so an edit never rewrites the lines we did not touch.
    with path.open(encoding=ENCODING, newline="") as handle:
        return handle.read()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=ENCODING, newline="") as handle:
        handle.write(text)


def make_workspace(project: Path, report: Report) -> None:
    root = project / WORKSPACE
    for relative in DIRECTORIES:
        folder = root / relative
        if folder.is_dir():
            continue
        folder.mkdir(parents=True)
        report.created.append(f"{WORKSPACE}/{relative}/")
    for name, target in TEMPLATES.items():
        destination = root / target
        label = f"{WORKSPACE}/{target}"
        if destination.exists():
            report.kept.append(label)
            continue
        source = TEMPLATES_DIR / name
        if not source.is_file():
            report.warnings.append(f"template missing: {source}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        report.created.append(label)


def ignored_entries(project: Path) -> set[str]:
    path = project / GITIGNORE
    if not path.is_file():
        return set()
    return {line.strip().rstrip("/") for line in read(path).splitlines()}


def add_to_gitignore(project: Path, entry: str, report: Report) -> None:
    """Append ``entry`` unless the .gitignore already lists it. Never removes or reorders anything."""
    if entry.rstrip("/") in ignored_entries(project):
        return
    path = project / GITIGNORE
    existed = path.is_file()
    text = read(path) if existed else ""
    eol = newline_of(text)
    if text and not text.endswith(("\n", "\r")):
        text += eol
    write(path, text + entry + eol)
    (report.updated if existed else report.created).append(f"{GITIGNORE} (+ {entry})")


def block_state(text: str) -> str:
    """'present' when our block is there, 'broken' when only one marker is, else 'absent'."""
    has_begin, has_end = BEGIN in text, END in text
    if has_begin and has_end and text.index(BEGIN) < text.index(END):
        return "present"
    return "broken" if has_begin or has_end else "absent"


def update_block(path: Path, text: str, label: str, report: Report) -> None:
    """Make the text between our two markers the current rule; nothing outside the markers is touched."""
    eol = newline_of(text)
    start = text.index(BEGIN) + len(BEGIN)
    stop = text.index(END)
    wanted = eol + RULE + eol
    if text[start:stop] == wanted:
        report.kept.append(f"{label} (block up to date)")
        return
    write(path, text[:start] + wanted + text[stop:])
    report.updated.append(f"{label} (block updated)")


def insert_block(path: Path, label: str, report: Report) -> None:
    """Add our marked block to an existing instruction file, once."""
    text = read(path)
    state = block_state(text)
    if state == "present":
        update_block(path, text, label, report)
        return
    if state == "broken":
        report.warnings.append(f"{label}: has one design-system marker but not a begin/end pair; left untouched")
        return
    eol = newline_of(text)
    if not text:
        separator = ""
    elif text.endswith(("\n", "\r")):
        separator = eol
    else:
        separator = eol * 2
    write(path, text + separator + BLOCK.replace("\n", eol))
    report.updated.append(f"{label} (+ block)")


def create_instruction_file(project: Path, name: str, report: Report, leading: str = "") -> None:
    """Create a new instruction file with the block and keep it out of git."""
    write(project / name, NEW_FILE_TITLE + leading + BLOCK)
    report.created.append(name)
    add_to_gitignore(project, name, report)


def claude_instructions(project: Path, report: Report) -> None:
    """Claude Code reads ./CLAUDE.md or ./.claude/CLAUDE.md, and AGENTS.md only when neither exists."""
    for name in (CLAUDE_FILE, CLAUDE_DIR_FILE):
        if (project / name).is_file():
            insert_block(project / name, name, report)
            return
    if (project / AGENTS_FILE).is_file():
        # A new CLAUDE.md would hide the project's AGENTS.md from Claude Code, so it imports it.
        create_instruction_file(project, CLAUDE_FILE, report, leading=f"{AGENTS_IMPORT}\n\n")
        report.warnings.append(f"{CLAUDE_FILE} created with `{AGENTS_IMPORT}` so Claude Code still reads the project's {AGENTS_FILE}")
        return
    create_instruction_file(project, CLAUDE_FILE, report)


def antigravity_instructions(project: Path, report: Report) -> None:
    """Antigravity CLI reads AGENTS.md and GEMINI.md at the project root (the docs rank neither above the other)."""
    for name in (GEMINI_FILE, AGENTS_FILE):
        if (project / name).is_file():
            insert_block(project / name, name, report)
            return
    create_instruction_file(project, GEMINI_FILE, report)


def init(project: Path) -> Report:
    report = Report()
    make_workspace(project, report)
    add_to_gitignore(project, f"{WORKSPACE}/", report)
    claude_instructions(project, report)
    antigravity_instructions(project, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd(), help="project folder (default: current folder)")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not project.is_dir():
        print(f"not a folder: {project}", file=sys.stderr)
        return 2
    report = init(project)
    for title, items in (("created", report.created), ("updated", report.updated), ("kept", report.kept), ("warning", report.warnings)):
        for item in items:
            print(f"{title}: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
