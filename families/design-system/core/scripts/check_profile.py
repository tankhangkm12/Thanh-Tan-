# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check a design against its project profile and its templates (default: `.agent-workspace/drafts/`).

The profile is `00-context/project-profile.md`: a line `Mức: S|M|L|XL` and a table `| Phần | Áp dụng |` with one row per
part `00-context` ... `12-roadmap` (and, where a part is only partly kept, rows for single files such as
`01-system/containers.md`). Áp dụng is `có`, `rút gọn` or `bỏ`; the most specific row (longest path) decides for a file.

Blocking errors (exit 1):
- the profile is missing or malformed (no level, no table, a part without a row, an unknown row, a bad value, a repeated row);
- a file under a part or file marked `bỏ` exists (an omitted part reappeared);
- a part the gate `--gate Gn` has reached, not marked `bỏ`, is missing: the folder has no markdown file, or, with
  `--templates`, one of the files the templates define for it does not exist (templates whose path has a `{name}`,
  `<name>` or `xxx` placeholder, e.g. `06-backend/services/{service}/scaling.md`, are per instance and are not required to
  exist; `<` and `>` cannot be used in a file name on Windows, so templates written there use `{name}`);
- with `--templates`: a file whose template marks a heading `<!-- required -->` (on the heading line or the next line) lacks
  that heading, has it empty, or has only the template's own placeholder lines under it;
- with `--templates`: an object folder on disk (`06-backend/services/order-service/`, `07-data/databases/order-db/`,
  `05-frontend/web/`) lacks a file that a template with a placeholder folder (`{service}`, `{db}`, `{app}`) defines, for a
  part the gate has reached and the profile keeps;
- no templates found: `--templates` not given and no `design-architecture/templates` beside this plugin (or an empty one).
  That is an error, so a gate run that forgot `--templates` never reads as a pass. `--no-templates` skips the template
  checks on purpose; the report then says "Chưa kiểm mục bắt buộc" at the top.

    uv run check_profile.py --gate G4 [--workspace DIR] [--root DIR] (--templates DIR | --no-templates)
"""

import argparse
import datetime
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkreport as cr  # noqa: E402

ENCODING = "utf-8"
PROFILE = "00-context/project-profile.md"
PARTS = (
    "00-context", "01-system", "02-tech-stack", "03-capacity", "04-flows", "05-frontend", "06-backend",
    "07-data", "08-security", "09-infrastructure", "10-process", "11-risks", "12-roadmap",
)
VALUES = ("có", "rút gọn", "bỏ")
OMITTED = "bỏ"
LEVELS = ("S", "M", "L", "XL")
# What each gate adds to architecture/ (stages.md, "File tạo ra"). Entries are parts or single files; a gate needs
# everything the earlier gates added too.
GATE_ENTRIES = {
    0: (PROFILE,),
    1: ("00-context",),
    2: ("02-tech-stack/selection-criteria.md",),
    3: ("01-system",),
    4: ("02-tech-stack",),
    5: ("03-capacity",),
    6: ("04-flows",),
    7: ("05-frontend", "06-backend", "07-data"),
    8: ("08-security", "09-infrastructure", "10-process"),
    9: ("11-risks", "12-roadmap"),
    10: (),
}
REQUIRED_MARK = re.compile(r"<!--\s*required\s*-->", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
LEVEL_RE = re.compile(r"^\s*(?:[-*]\s+)?\*{0,2}Mức:?\*{0,2}:?\s*\**\s*(S|M|L|XL)\b")
PLACEHOLDER_RE = re.compile(r"<[^>]*>|\{[^}]*\}|x{3,}")  # <name> as in PLAN.md; {name} where < > are not allowed in file names (Windows)
MAX_LISTED = 25
NOT_CHECKED = "Chưa kiểm mục bắt buộc và tệp theo template (chạy với --no-templates hoặc không có template)."


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"`{self.path}:{self.line}` [{self.code}] {self.message}"


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def read_lines(path: Path) -> list[str]:
    return nfc(path.read_text(encoding=ENCODING, errors="replace")).splitlines()


def mask_fences(lines: list[str]) -> list[str]:
    out, fence = [], ""
    for line in lines:
        match = FENCE_RE.match(line)
        if fence:
            out.append("")
            if match and match.group(1) == fence:
                fence = ""
        elif match:
            fence = match.group(1)
            out.append("")
        else:
            out.append(line)
    return out


def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def heading_key(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[`*_~]", "", nfc(text)).strip().casefold()


# --- the profile ------------------------------------------------------------------------------------------------------------

def parse_profile(path: Path, rel: str) -> tuple[dict[str, str], list[Finding]]:
    """({row key: value}, errors)."""
    findings: list[Finding] = []
    lines = mask_fences(read_lines(path))
    if not any(LEVEL_RE.match(line) for line in lines):
        findings.append(Finding(rel, 1, "profile-no-level", f"không có dòng \"Mức: {'|'.join(LEVELS)}\""))
    rows: dict[str, str] = {}
    seen: set[str] = set()
    in_table = False
    for number, line in enumerate(lines, 1):
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        cells = split_cells(line)
        if [heading_key(c) for c in cells[:2]] == ["phần", "áp dụng"]:
            in_table = True
            continue
        if not in_table or re.fullmatch(r"[:\-\s|]*", line):
            continue
        key = cells[0].strip("` ").rstrip("/") if cells else ""
        value = heading_key(cells[1]) if len(cells) > 1 else ""
        seen.add(key)
        if value not in VALUES:
            findings.append(Finding(rel, number, "profile-bad-value", f"\"{cells[1] if len(cells) > 1 else ''}\" không phải {' | '.join(VALUES)} (dòng {key!r})"))
            continue
        if key in rows:
            findings.append(Finding(rel, number, "profile-repeated-row", f"{key} có hai dòng"))
            continue
        if not any(key == part or key.startswith(part + "/") for part in PARTS):
            findings.append(Finding(rel, number, "profile-unknown-row", f"{key} không thuộc phần 00-context ... 12-roadmap"))
            continue
        rows[key] = value
    if not seen:
        findings.append(Finding(rel, 1, "profile-no-table", "không có bảng | Phần | Áp dụng |"))
    for part in PARTS:
        if part not in seen and seen:
            findings.append(Finding(rel, 1, "profile-missing-part-row", f"bảng không có dòng cho {part}"))
    return rows, findings


def status_of(rel: str, rows: dict[str, str]) -> str | None:
    """Value of the most specific profile row covering this path, or None."""
    best = None
    for key, value in rows.items():
        if rel == key or rel.startswith(key + "/"):
            if best is None or len(key) > len(best[0]):
                best = (key, value)
    return best[1] if best else None


def gate_entries(gate: int) -> list[str]:
    return [entry for g in range(gate + 1) for entry in GATE_ENTRIES[g]]


# --- templates -------------------------------------------------------------------------------------------------------------

def is_placeholder_path(rel: str) -> bool:
    return bool(PLACEHOLDER_RE.search(rel))


def template_pattern(rel: str) -> re.Pattern:
    parts = []
    for segment in rel.split("/"):
        pieces = PLACEHOLDER_RE.split(segment)
        parts.append("[^/]+".join(re.escape(piece) for piece in pieces))
    return re.compile("/".join(parts) + r"\Z")


def required_headings(lines: list[str]) -> list[str]:
    """Keys of the headings a template marks required (marker on the heading line or on the next non-blank line)."""
    masked = mask_fences(lines)
    found = []
    for index, line in enumerate(masked):
        heading = HEADING_RE.match(COMMENT_RE.sub("", line).rstrip())
        if not heading:
            continue
        marked = REQUIRED_MARK.search(line) is not None
        if not marked:
            following = next((masked[j] for j in range(index + 1, len(masked)) if masked[j].strip()), "")
            marked = REQUIRED_MARK.fullmatch(following.strip()) is not None
        if marked:
            found.append(heading_key(heading.group(2)))
    return found


def sections(lines: list[str]) -> list[tuple[str, int, int, list[str]]]:
    """(heading key, level, line number, body lines) for every heading."""
    masked = mask_fences(lines)
    heads = [(i, HEADING_RE.match(COMMENT_RE.sub("", line))) for i, line in enumerate(masked)]
    heads = [(i, m) for i, m in heads if m]
    result = []
    for n, (i, m) in enumerate(heads):
        level = len(m.group(1))
        stop = len(lines)
        for j, m2 in heads[n + 1 :]:
            if len(m2.group(1)) <= level:
                stop = j
                break
        result.append((heading_key(m.group(2)), level, i + 1, lines[i + 1 : stop]))
    return result


def content_lines(body: list[str]) -> list[str]:
    text = COMMENT_RE.sub("", "\n".join(body))
    return [line.strip() for line in text.splitlines() if line.strip() and not HEADING_RE.match(line)]


def check_required_sections(rel: str, draft: Path, template: Path, template_rel: str) -> list[Finding]:
    template_lines = read_lines(template)
    wanted = required_headings(template_lines)
    if not wanted:
        return []
    template_sections = {key: body for key, _, _, body in sections(template_lines)}
    drafted = {}
    for key, level, number, body in sections(read_lines(draft)):
        drafted.setdefault(key, (number, body))
    findings = []
    for key in wanted:
        if key not in drafted:
            findings.append(Finding(rel, 1, "missing-required-section", f"thiếu mục bắt buộc \"{key}\" (template {template_rel})"))
            continue
        number, body = drafted[key]
        lines = content_lines(body)
        if not lines:
            findings.append(Finding(rel, number, "empty-required-section", f"mục bắt buộc \"{key}\" để trống"))
        elif all(line in set(content_lines(template_sections.get(key, []))) for line in lines):
            findings.append(Finding(rel, number, "unfilled-required-section", f"mục bắt buộc \"{key}\" còn nguyên nội dung mẫu của template"))
    return findings


def match_template(rel: str, templates: list[str]) -> str | None:
    exact = [t for t in templates if t == rel]
    if exact:
        return exact[0]
    matches = [t for t in templates if is_placeholder_path(t) and template_pattern(t).match(rel)]
    return min(matches, key=lambda t: len(PLACEHOLDER_RE.findall(t))) if matches else None


def reached_by_gate(rel: str, gate: int) -> bool:
    return any(rel == entry or rel.startswith(entry + "/") for entry in gate_entries(gate))


def missing_instance_files(root: Path, gate: int, rows: dict[str, str], template_files: list[str]) -> list[Finding]:
    """For each object folder on disk (06-backend/services/order-service/, 07-data/databases/order-db/, 05-frontend/web/), every
    template with a placeholder folder there (`{service}`, `{db}`, `{app}`) must have its file. Only for parts the gate has
    reached and the profile does not omit. A placeholder deeper in the path, or only in the file name, is not an object folder."""
    findings = []
    for template_rel in template_files:
        segments = template_rel.split("/")
        index = next((i for i, segment in enumerate(segments[:-1]) if PLACEHOLDER_RE.search(segment)), None)
        rest = segments[index + 1 :] if index is not None else []
        if index is None or PLACEHOLDER_RE.search("/".join(rest)):
            continue
        parent = root.joinpath(*segments[:index])
        if not parent.is_dir():
            continue
        pattern = template_pattern(segments[index])
        for child in sorted(parent.iterdir()):
            if not child.is_dir() or not pattern.match(child.name):
                continue
            target = "/".join(segments[:index] + [child.name] + rest)
            if reached_by_gate(target, gate) and status_of(target, rows) != OMITTED and not (root / target).is_file():
                findings.append(Finding(target, 1, "instance-file-missing", f"{'/'.join(segments[:index] + [child.name])}/ thiếu {'/'.join(rest)} (template {template_rel})"))
    return findings


# --- the run ----------------------------------------------------------------------------------------------------------------

def run(root: Path, gate: int, templates: Path | None) -> tuple[list[Finding], list[str]]:
    """Findings and notes. `templates` None means the templates were not checked, and the notes say so."""
    notes: list[str] = [] if templates else [NOT_CHECKED]
    profile_path = root / PROFILE
    if not profile_path.is_file():
        return [Finding(PROFILE, 1, "profile-missing", f"không có {PROFILE} trong {root}")], notes
    rows, findings = parse_profile(profile_path, PROFILE)
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.md") if p.is_file())

    for rel in files:
        if status_of(rel, rows) == OMITTED:
            findings.append(Finding(rel, 1, "omitted-part-present", "phần đã bỏ trong hồ sơ dự án nhưng vẫn có file này"))

    template_files = sorted(p.relative_to(templates).as_posix() for p in templates.rglob("*.md")) if templates else []

    for entry in gate_entries(gate):
        if status_of(entry, rows) == OMITTED:
            continue
        if entry.endswith(".md"):
            if not (root / entry).is_file():
                findings.append(Finding(entry, 1, "required-file-missing", f"gate G{gate} cần file này"))
            continue
        under = [f for f in files if f.startswith(entry + "/")]
        if not under:
            findings.append(Finding(entry, 1, "required-part-missing", f"gate G{gate} cần phần {entry} nhưng chưa có file markdown nào"))
        for template_rel in template_files:
            if (template_rel.startswith(entry + "/") and not is_placeholder_path(template_rel)
                    and status_of(template_rel, rows) != OMITTED and not (root / template_rel).is_file()):
                findings.append(Finding(template_rel, 1, "required-file-missing", f"template định nghĩa file này cho phần {entry}; gate G{gate} cần nó"))

    findings += missing_instance_files(root, gate, rows, template_files)

    if templates:
        for rel in files:
            template_rel = match_template(rel, template_files)
            if template_rel:
                findings += check_required_sections(rel, root / rel, templates / template_rel, template_rel)
    return findings, notes


def report(root: Path, gate: int, findings: list[Finding], notes: list[str], today: str) -> str:
    lines = [f"# check_profile {today}", ""]
    lines += [f"**{n}**" for n in notes] + ([""] if notes else [])
    lines += [f"Quét `{root}` ở gate G{gate}: {len(findings)} lỗi chặn.", ""]
    lines += ["## Lỗi chặn", ""] + ([f"- {f.render()}" for f in findings] or ["- không có"]) + [""]
    return "\n".join(lines)


def default_templates(scripts_dir: Path = Path(__file__).resolve().parent) -> Path | None:
    """design-architecture/templates beside design-core (core/scripts -> ../../design-architecture/templates), if it exists."""
    candidate = scripts_dir.parent.parent / "design-architecture" / "templates"
    return candidate if candidate.is_dir() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gate", required=True, help="G0 ... G10: the gate being checked")
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--root", type=Path, help="folder to scan (default: <workspace>/drafts)")
    parser.add_argument("--templates", type=Path, help="templates of design-architecture (same paths as architecture/)")
    parser.add_argument("--no-templates", action="store_true", help="skip the template checks on purpose; the report says they were not done")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    match = re.fullmatch(r"[Gg](\d{1,2})", args.gate)
    if not match or int(match.group(1)) not in GATE_ENTRIES:
        parser.error("--gate phải là G0 ... G10")
    gate = int(match.group(1))
    workspace = args.workspace.resolve()
    root = (args.root or workspace / "drafts").resolve()
    if args.no_templates and args.templates:
        parser.error("--templates và --no-templates không đi cùng nhau")
    templates = None if args.no_templates else (args.templates.resolve() if args.templates else default_templates())
    for folder in (root, templates):
        if folder is not None and not folder.is_dir():
            print(f"not a folder: {folder}", file=sys.stderr)
            return 2
    today = args.date or datetime.date.today().isoformat()
    extra = []
    if templates is None and not args.no_templates:
        extra.append(Finding("(templates)", 1, "templates-not-found", "không tìm thấy template: truyền --templates DIR (design-architecture/templates), hoặc --no-templates nếu cố ý bỏ qua kiểm mục bắt buộc"))
    elif templates is not None and not any(templates.rglob("*.md")):
        extra.append(Finding(str(templates), 1, "templates-empty", "thư mục template không có file .md nào; kiểm --templates trỏ đúng chưa"))
        templates = None
    files = cr.hash_files(workspace, sorted(root.rglob("*.md")))  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    findings, notes = run(root, gate, templates)
    findings += extra
    findings.sort(key=lambda f: (f.path, f.line, f.code))
    text = report(root, gate, findings, notes, today) + cr.render("check_profile.py", not findings, files, f"G{gate}", "no-templates" if templates is None else "templates")
    target = workspace / "checks" / f"profile-{today}.md"
    if workspace.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=ENCODING, newline="\n")
    print(f"check_profile G{gate}: {len(findings)} lỗi chặn" + (f"; báo cáo: {target}" if workspace.is_dir() else ""))
    for finding in findings[:MAX_LISTED]:
        print(f"error: {finding.render()}")
    if len(findings) > MAX_LISTED:
        print(f"error: … và {len(findings) - MAX_LISTED} lỗi nữa (xem báo cáo)")
    for note in notes:
        print(f"note: {note}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
