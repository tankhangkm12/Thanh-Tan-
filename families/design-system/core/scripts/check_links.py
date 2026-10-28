# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check the links and IDs of the markdown files of a design (default: `.agent-workspace/drafts/`).

Blocking errors (exit 1):
- a markdown link whose file does not exist, or whose `#anchor` is not a heading of the target file;
- an ID defined twice. An ID is `<prefix>-<number or name>` with a prefix of data/ids.yaml (FR NFR C A TC FL SCR SVC API EVT TBL
  BKT R D CH; SVC-order and TBL-orders are valid); it is *defined* by a heading that starts with it, or, only when no heading in any
  file defines it, by the first cell of a table row (so an index table in an overview file never clashes with the file
  that defines the ID in detail). Two headings, or two table cells when there is no heading, make a duplicate;
- an ID defined outside its home file (data/ids.yaml: C-xx in 00-context/constraints.md, A-xx in 00-context/assumptions.md);
- an ID defined outside its home file (data/ids.yaml: C-xx in 00-context/constraints.md, A-xx in 00-context/assumptions.md);
- a file that defines an SVC / TBL / BKT / EVT / API ID but has no "Được dùng bởi" section, or whose section does not link
  every other file that mentions one of those IDs (FR, NFR, TC and R need no back link);
- a stack layer file (`02-tech-stack/layers/`) with no TC reference or a TC that is defined nowhere, and a risk row of
  `11-risks/risk-register.md` whose "Thành phần liên quan" cell has neither an SVC / TBL / BKT / EVT / API ID nor a link to a
  file in `02-tech-stack/`. The risk-row rule applies only once `02-tech-stack/layers/` holds at least one .md file (from G4):
  before that no stack component exists to name, so the rows are not checked (the column itself is still required).

Warnings (never block): an ID that is defined but mentioned in no other file (an orphan).

The report is also written to `<workspace>/checks/links-<date>.md`, ending with the sha256 of every file checked (checkreport.py).

    uv run check_links.py [--workspace DIR] [--root DIR]
"""

import argparse
import datetime
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import checkreport as cr
import idlist

ENCODING = "utf-8"
IDS = idlist.load()  # ID prefixes, back-link kinds and the home file of C / A: core/data/ids.yaml
ID_KINDS = IDS.kinds
BACKLINK_KINDS = IDS.backlink_kinds
BACKLINK_HEADING = "Được dùng bởi"
STACK_DIR = "02-tech-stack/"
LAYERS_DIR = STACK_DIR + "layers/"
RISK_REGISTER = "11-risks/risk-register.md"
RISK_COMPONENTS_COLUMN = "Thành phần liên quan"
SHOWN_ERRORS = 25

ID_RE = IDS.id_re()
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
LINK_TEXT_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str
    blocking: bool = True

    def render(self) -> str:
        return f"`{self.path}:{self.line}` [{self.code}] {self.message}"


@dataclass
class Doc:
    rel: str
    path: Path
    lines: list[str]
    masked: list[str] = field(default_factory=list)  # fenced code blocks blanked


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


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


def load(root: Path) -> list[Doc]:
    docs = []
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        lines = nfc(path.read_text(encoding=ENCODING, errors="replace")).splitlines()
        docs.append(Doc(path.relative_to(root).as_posix(), path, lines, mask_fences(lines)))
    return docs


def slug(heading: str) -> str:
    """GitHub-style anchor of a heading text."""
    text = LINK_TEXT_RE.sub(r"\1", heading)
    text = re.sub(r"[`*_~]", "", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def anchors_of(lines: list[str]) -> set[str]:
    seen: dict[str, int] = {}
    result = set()
    for line in mask_fences(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def is_separator(line: str) -> bool:
    cells = split_cells(line)
    return line.lstrip().startswith("|") and bool(cells) and all(SEPARATOR_CELL_RE.match(c) for c in cells if c)


def leading_id(text: str) -> str | None:
    text = LINK_TEXT_RE.sub(r"\1", text)
    text = re.sub(r"^[\s`*_\[(]+", "", text)
    match = ID_RE.match(text)
    return match.group(1) if match and match.start() == 0 else None


def raw_definitions(doc: Doc) -> list[tuple[str, int, str]]:
    """(ID, line, kind) where kind is "heading" (a heading starting with the ID) or "cell" (first cell of a table body row)."""
    found = []
    lines = doc.masked
    for number, line in enumerate(lines, 1):
        heading = HEADING_RE.match(line)
        if heading:
            ident, kind = leading_id(heading.group(2)), "heading"
        elif line.lstrip().startswith("|") and not is_separator(line):
            following = lines[number] if number < len(lines) else ""
            if is_separator(following):
                continue  # the header row
            cells = split_cells(line)
            ident, kind = (leading_id(cells[0]) if cells else None), "cell"
        else:
            continue
        if ident:
            found.append((ident, number, kind))
    return found


def definitions(doc: Doc) -> list[tuple[str, int]]:
    """Every heading and table-cell definition of one file, before the heading-wins rule."""
    return [(ident, number) for ident, number, _ in raw_definitions(doc)]


def effective_definitions(docs: list[Doc]) -> dict[str, list[tuple[Doc, int]]]:
    """Where each ID is defined. A heading wins: table cells define an ID only when no heading anywhere does, so an
    index table (06-backend/overview.md listing every SVC) never clashes with the file that defines the ID in detail."""
    headings: dict[str, list[tuple[Doc, int]]] = {}
    cells: dict[str, list[tuple[Doc, int]]] = {}
    for doc in docs:
        for ident, number, kind in raw_definitions(doc):
            (headings if kind == "heading" else cells).setdefault(ident, []).append((doc, number))
    return {**cells, **headings}


def mentions(doc: Doc) -> set[str]:
    """Every ID the file's text names, link targets left out."""
    text = "\n".join(LINK_RE.sub(lambda m: m.group(0).split("](")[0] + "]", line) for line in doc.lines)
    return set(ID_RE.findall(text))


def link_targets(doc: Doc) -> list[tuple[str, int]]:
    found = []
    for number, line in enumerate(doc.masked, 1):
        stripped = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(stripped):
            found.append((match.group(1), number))
        ref = REF_DEF_RE.match(stripped)
        if ref:
            found.append((ref.group(1), number))
    return found


def resolve(doc: Doc, target: str) -> tuple[Path | None, str]:
    """(file the link points at or None for an external link, anchor)."""
    target = target.strip("<>")
    if SCHEME_RE.match(target) and not re.match(r"^[A-Za-z]:[\\/]", target):
        return None, ""
    path_part, _, anchor = target.partition("#")
    path_part = unquote(path_part)
    if not path_part:
        return doc.path, unquote(anchor)
    return Path(os.path.normpath(doc.path.parent / path_part)), unquote(anchor)


class Anchors:
    def __init__(self, docs: list[Doc]):
        self.cache = {os.path.normcase(os.path.normpath(d.path)): anchors_of(d.lines) for d in docs}

    def of(self, path: Path) -> set[str]:
        key = os.path.normcase(os.path.normpath(path))
        if key not in self.cache:
            try:
                self.cache[key] = anchors_of(nfc(path.read_text(encoding=ENCODING, errors="replace")).splitlines())
            except OSError:
                self.cache[key] = set()
        return self.cache[key]


def check_links(docs: list[Doc], anchors: Anchors) -> list[Finding]:
    findings = []
    for doc in docs:
        for target, number in link_targets(doc):
            resolved, anchor = resolve(doc, target)
            if resolved is None:
                continue
            if not resolved.exists():
                findings.append(Finding(doc.rel, number, "broken-link", f"link tới file không có: {target}"))
            elif anchor and resolved.is_file() and resolved.suffix.lower() == ".md" and nfc(anchor).lower() not in anchors.of(resolved):
                findings.append(Finding(doc.rel, number, "broken-anchor", f"link tới mục không có: {target}"))
    return findings


def section_links(doc: Doc, heading: str) -> list[Path] | None:
    """Targets of the links in the section with this heading (to the next heading of the same or a higher level)."""
    start = level = None
    for number, line in enumerate(doc.masked):
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is not None and len(match.group(1)) <= level:
            return links_between(doc, start, number)
        if start is None and nfc(match.group(2)).strip("*_` ").casefold() == nfc(heading).casefold():
            start, level = number + 1, len(match.group(1))
    return links_between(doc, start, len(doc.masked)) if start is not None else None


def links_between(doc: Doc, start: int, stop: int) -> list[Path]:
    targets = []
    for line in doc.masked[start:stop]:
        for match in LINK_RE.finditer(INLINE_CODE_RE.sub("", line)):
            resolved, _ = resolve(doc, match.group(1))
            if resolved is not None:
                targets.append(Path(os.path.normcase(resolved)))
    return targets


def check_ids(docs: list[Doc]) -> tuple[list[Finding], list[Finding]]:
    errors, warnings = [], []
    defined = effective_definitions(docs)
    mentioned = {doc.rel: mentions(doc) for doc in docs}

    for ident, places in sorted(defined.items()):
        if len(places) > 1:
            where = ", ".join(f"{d.rel}:{n}" for d, n in places)
            for doc, number in places[1:]:
                errors.append(Finding(doc.rel, number, "duplicate-id", f"{ident} đã được định nghĩa ở {places[0][0].rel}:{places[0][1]} (tất cả: {where})"))
            continue
        doc, number = places[0]
        if not any(ident in ids for rel, ids in mentioned.items() if rel != doc.rel):
            warnings.append(Finding(doc.rel, number, "orphan-id", f"{ident} không được file nào khác nhắc tới", blocking=False))

    for doc in docs:
        mine = {i: n for i, places in defined.items() if len(places) == 1 for d, n in places if d is doc}
        own = sorted(i for i in mine if i.split("-")[0] in BACKLINK_KINDS)
        if not own:
            continue
        first_line = mine[own[0]]
        links = section_links(doc, BACKLINK_HEADING)
        if links is None:
            errors.append(Finding(doc.rel, first_line, "missing-backlink-section", f"file định nghĩa {', '.join(own[:3])}{'…' if len(own) > 3 else ''} nhưng không có mục \"{BACKLINK_HEADING}\""))
            continue
        linked = set(links)
        for other in docs:
            if other.rel == doc.rel:
                continue
            hit = next((i for i in own if i in mentioned[other.rel]), None)
            if hit and Path(os.path.normcase(other.path)) not in linked:
                errors.append(Finding(doc.rel, first_line, "missing-backlink", f"{other.rel} nhắc {hit} nhưng mục \"{BACKLINK_HEADING}\" không link tới nó"))
    return errors, warnings


def check_homes(docs: list[Doc]) -> list[Finding]:
    """An ID whose kind has a home file (C, A) may be defined only there."""
    findings = []
    for ident, places in sorted(effective_definitions(docs).items()):
        home = IDS.homes.get(IDS.kind_of(ident))
        for doc, number in places:
            if home and doc.rel != home:
                findings.append(Finding(doc.rel, number, "id-outside-home", f"{ident} phải được định nghĩa ở {home}, không phải ở {doc.rel}"))
    return findings


def check_layers(docs: list[Doc]) -> list[Finding]:
    """Q5: each stack layer traces back to the TC it was chosen by."""
    defined_tc = {i for i in effective_definitions(docs) if i.startswith("TC-")}
    findings = []
    for doc in docs:
        if not doc.rel.startswith(LAYERS_DIR):
            continue
        used = sorted({i for i in mentions(doc) if i.startswith("TC-")})
        if not used:
            findings.append(Finding(doc.rel, 1, "layer-without-tc", "lớp stack không truy về TC-xx nào"))
        for ident in used:
            if ident not in defined_tc:
                findings.append(Finding(doc.rel, 1, "layer-unknown-tc", f"{ident} không được định nghĩa ở đâu (selection-criteria.md)"))
    return findings


def names_a_component(doc: Doc, cell: str) -> bool:
    """An SVC/TBL/BKT/EVT/API ID, or a link to a file in 02-tech-stack/ (a technology of the stack)."""
    if any(i.split("-")[0] in BACKLINK_KINDS for i in ID_RE.findall(LINK_TEXT_RE.sub(r"\1", cell))):
        return True
    root = doc.path
    for _ in doc.rel.split("/"):
        root = root.parent
    for match in LINK_RE.finditer(cell):
        resolved, _ = resolve(doc, match.group(1))
        if resolved is None:
            continue
        try:
            relative = Path(os.path.normpath(resolved)).relative_to(os.path.normpath(root)).as_posix()
        except ValueError:
            continue
        if relative.startswith(STACK_DIR):
            return True
    return False


def check_risk_register(docs: list[Doc]) -> list[Finding]:
    """Q6: each risk row names the components it touches (see names_a_component), once the stack layers exist (from G4)."""
    findings = []
    stack_built = any(doc.rel.startswith(LAYERS_DIR) for doc in docs)
    for doc in docs:
        if doc.rel != RISK_REGISTER:
            continue
        column = None
        for number, line in enumerate(doc.masked, 1):
            if not line.lstrip().startswith("|") or is_separator(line):
                continue
            cells = split_cells(line)
            following = doc.masked[number] if number < len(doc.masked) else ""
            if is_separator(following):
                header = [nfc(c).casefold() for c in cells]
                column = header.index(RISK_COMPONENTS_COLUMN.casefold()) if RISK_COMPONENTS_COLUMN.casefold() in header else None
                if column is None:
                    findings.append(Finding(doc.rel, number, "risk-without-components-column", f"bảng rủi ro không có cột \"{RISK_COMPONENTS_COLUMN}\""))
                continue
            ident = leading_id(cells[0]) if cells else None
            if not ident or not ident.startswith("R-") or column is None:
                continue
            cell = cells[column] if column < len(cells) else ""
            if stack_built and not names_a_component(doc, cell):
                findings.append(Finding(doc.rel, number, "risk-without-components", f"{ident}: cột \"{RISK_COMPONENTS_COLUMN}\" không có ID SVC/TBL/BKT/EVT/API hay link tới file trong {STACK_DIR}"))
    return findings


def run(root: Path) -> tuple[list[Finding], list[Finding], int]:
    docs = load(root)
    errors = check_links(docs, Anchors(docs))
    id_errors, warnings = check_ids(docs)
    errors += id_errors + check_homes(docs) + check_layers(docs) + check_risk_register(docs)
    errors.sort(key=lambda f: (f.path, f.line, f.code))
    warnings.sort(key=lambda f: (f.path, f.line, f.code))
    return errors, warnings, len(docs)


def report(root: Path, errors: list[Finding], warnings: list[Finding], count: int, today: str) -> str:
    lines = [f"# check_links {today}", "", f"Quét `{root}`: {count} file, {len(errors)} lỗi chặn, {len(warnings)} cảnh báo.", ""]
    for title, items in (("Lỗi chặn", errors), ("Cảnh báo (không chặn gate)", warnings)):
        lines += [f"## {title}", ""] + ([f"- {f.render()}" for f in items] or ["- không có"]) + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--root", type=Path, help="folder to scan (default: <workspace>/drafts)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    root = (args.root or workspace / "drafts").resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    files = cr.hash_files(workspace, sorted(root.rglob("*.md")))  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    errors, warnings, count = run(root)
    text = report(root, errors, warnings, count, today) + cr.render("check_links.py", not errors, files)
    target = workspace / "checks" / f"links-{today}.md"
    if workspace.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=ENCODING, newline="\n")
    print(f"check_links: {count} file, {len(errors)} lỗi chặn, {len(warnings)} cảnh báo" + (f"; báo cáo: {target}" if workspace.is_dir() else ""))
    for finding in errors[:SHOWN_ERRORS]:
        print(f"error: {finding.render()}")
    if len(errors) > SHOWN_ERRORS:
        print(f"error: … và {len(errors) - SHOWN_ERRORS} lỗi nữa (xem báo cáo)")
    for finding in warnings[:5]:
        print(f"warning: {finding.render()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
