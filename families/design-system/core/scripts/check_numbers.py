# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check the numbers of a design (default: `.agent-workspace/drafts/`) against the rules of PLAN.md, "Quy tắc số liệu và sizing".

Blocking errors (exit 1):
- a number with a unit ("292 MB", "300 ms", "70%", "10.000 người dùng") with no formula, no assumption and no source next to it.
  "Next to" is the sentence of a paragraph, the whole list item or heading, or the table row. Evidence is a formula
  (`=`, `×`, `÷`, `⌈⌊`, the words "công thức"), an assumption `A-xx` that capacity/assumptions.yaml declares, or a source (a
  link, a URL, a path under `inputs/`). A table row also passes when a column named like "Nguồn", "Giả định" or "Công thức"
  is filled in that row. Numbers in fenced code and in HTML comments are not checked. Numbers in what `calc_capacity.py` writes
  are not checked either, but only when that is *proven*: the file is one of the six documents `calc_capacity.py` writes, at its
  own path, and its text equals what `calc_capacity.py` computes again from `capacity/*.yaml`; a `BEGIN:calc` / `END:calc` block
  is skipped only in the same way (right file, same text as recomputed) or when it holds just "chờ script". A line saying
  "Sinh bởi calc_capacity.py" proves nothing: such a file at another path, or a generated file that was edited by hand, is
  checked like any other file and reported ("file sinh bị sửa tay").
- a vague word with no number next to it in the same sentence, list item, heading or table row ("nhanh", "lớn", "đủ dùng",
  "scale tốt", ...). The list of words, of units and of evidence columns is in `core/data/numbers.yaml`, not in this script.
- `00-context/assumptions.md` differs from what `capacity/assumptions.yaml` generates (or one of the two is missing or invalid).

The report is also written to `<workspace>/checks/numbers-<date>.md`, ending with the sha256 of every file checked (checkreport.py).

    uv run check_numbers.py [--workspace DIR] [--root DIR] [--config FILE] [--constants-dir DIR]
"""

import argparse
import datetime
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calc_capacity as cc  # noqa: E402
import check_links as cl  # noqa: E402
import checkreport as cr  # noqa: E402
import idlist  # noqa: E402

IDS = idlist.load()  # the ID prefixes shared with check_links / tally_votes / check_trace: core/data/ids.yaml

ENCODING = "utf-8"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "data" / "numbers.yaml"
SHOWN = 25
ASSUMPTIONS_MD = "00-context/assumptions.md"
PENDING = re.compile(r"(?:<!--\s*)?chờ script(?:\s*-->)?", re.IGNORECASE)  # an empty calc block the Designer placed

CALC_BLOCK = re.compile(r"(<!--\s*BEGIN:calc:(\S+?)\s*-->)(.*?)(<!--\s*END:calc:\2\s*-->)", re.DOTALL)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING = re.compile(r"^#{1,6}\s+")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|")
SEPARATOR = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
# Text whose digits are not quantities: IDs (FR-001, TC-03), dates, link targets, bare URLs. Masked with spaces (same length).
MASKS = (
    IDS.id_re(),  # every ID of data/ids.yaml (SVC-api2, NFR-p95, C-01 ...)
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*-\d[\w-]*"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"(?<=\]\()[^)]*(?=\))"),
    re.compile(r"https?://\S+"),
)
LINK_EVIDENCE = re.compile(r"\]\(|https?://")
FORMULA_EVIDENCE = re.compile(r"[=×÷⌈⌉⌊⌋]|công thức", re.IGNORECASE)
ASSUMPTION_REF = IDS.id_re(["A"])  # A-xx
NUMBER = r"\d[\d.,]*\d|\d"


NEVER = re.compile(r"(?!x)x")  # matches nothing


@dataclass
class Config:
    vague: re.Pattern
    units: re.Pattern
    prefixed: re.Pattern
    evidence_columns: tuple[str, ...]
    source_markers: tuple[str, ...]
    empty_cells: frozenset[str]
    vague_words: tuple[str, ...]
    exempt: re.Pattern = NEVER  # exact phrases that contain a vague word ("ít nhất")
    evidence_id: re.Pattern = NEVER  # an ID of these kinds, defined in the drafts, is evidence in its sentence / item / row
    basis_columns: tuple[str, ...] = ()  # a filled cell of such a column is evidence only with a link or a basis_id
    basis_id: re.Pattern = NEVER
    basis_id_kinds: tuple[str, ...] = ()


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"`{self.path}:{self.line}` [{self.code}] {self.message}"


@dataclass
class Stats:
    files: int = 0
    generated_files: int = 0
    numbers: int = 0
    numbers_with_evidence: int = 0
    vague_words: int = 0


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


# --- the data file ------------------------------------------------------------------------------------------------------------

def load_config(path: Path) -> tuple[Config | None, list[str]]:
    if not path.is_file():
        return None, [f"không có file dữ liệu {path}"]
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except yaml.YAMLError as error:
        return None, [f"{path.name}: YAML hỏng ({str(error).splitlines()[0]})"]
    errors = []
    if not isinstance(data, dict):
        return None, [f"{path.name}: gốc phải là mapping"]
    lists: dict[str, list[str]] = {}
    optional = ("unit_prefixes", "source_markers", "empty_cells", "exempt_phrases", "evidence_id_kinds", "basis_columns", "basis_id_kinds")
    for key, required in (("vague_words", True), ("units", True), ("evidence_columns", True), *((k, False) for k in optional)):
        value = data.get(key, [] if not required else None)
        if not isinstance(value, list) or (required and not value) or any(not isinstance(v, str) for v in value):
            errors.append(f"{path.name}: {key} phải là danh sách chuỗi" + (" không rỗng" if required else ""))
            continue
        if required and any(not v.strip() for v in value):
            errors.append(f"{path.name}: {key} có phần tử rỗng")
        lists[key] = [nfc(v) for v in value]
    for key in ("evidence_id_kinds", "basis_id_kinds"):
        unknown = [k for k in lists.get(key, []) if k not in IDS.kinds]
        if unknown:
            errors.append(f"{path.name}: {key} có tiền tố không có trong ids.yaml: {', '.join(unknown)}")
    if errors:
        return None, errors

    def alternation(items: list[str]) -> str:
        return "|".join(r"\s+".join(re.escape(part) for part in item.split()) for item in sorted(items, key=len, reverse=True))

    prefixes = lists["unit_prefixes"]
    config = Config(
        vague=re.compile(r"(?<!\w)(?:" + alternation(lists["vague_words"]) + r")(?!\w)", re.IGNORECASE),
        units=re.compile(r"(?<![\w.,/])(?P<num>" + NUMBER + r")\s*(?P<unit>" + alternation(lists["units"]) + r")(?!\w)", re.IGNORECASE),
        prefixed=re.compile(r"(?P<unit>" + alternation(prefixes) + r")\s*(?P<num>" + NUMBER + r")(?!\w)", re.IGNORECASE) if prefixes else re.compile(r"(?!x)x"),
        evidence_columns=tuple(v.casefold() for v in lists["evidence_columns"]),
        source_markers=tuple(lists["source_markers"]),
        empty_cells=frozenset(v.casefold() for v in lists["empty_cells"]) | {""},
        vague_words=tuple(lists["vague_words"]),
        exempt=re.compile(r"(?<!\w)(?:" + alternation(lists["exempt_phrases"]) + r")(?!\w)", re.IGNORECASE) if lists["exempt_phrases"] else NEVER,
        evidence_id=IDS.id_re(lists["evidence_id_kinds"]) if lists["evidence_id_kinds"] else NEVER,
        basis_columns=tuple(v.casefold() for v in lists["basis_columns"]),
        basis_id=IDS.id_re(lists["basis_id_kinds"]) if lists["basis_id_kinds"] else NEVER,
        basis_id_kinds=tuple(lists["basis_id_kinds"]),
    )
    return config, []


# --- reading a document into contexts -------------------------------------------------------------------------------------------

def mask(text: str) -> str:
    for pattern in MASKS:
        text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return text


def prepare(text: str, blocks: dict[str, str] | None = None, found: list[tuple[str, int, bool]] | None = None) -> list[str]:
    """Lines with the proven calc blocks emptied and HTML comments blanked, line count kept.

    A calc block is emptied when it holds just "chờ script" or equals the block `calc_capacity.py` computes (`blocks`: name -> text,
    None when that cannot be computed). Any other block stays in the text, is checked like the rest, and is added to `found` as
    (name, line, verifiable)."""
    text = nfc(text)

    def block(m: re.Match) -> str:
        inner = m.group(3).replace("\r\n", "\n").strip()
        if PENDING.fullmatch(inner) or (blocks is not None and nfc(blocks.get(m.group(2), "")).strip() == inner and inner):
            return re.sub(r"[^\n]", "", m.group(0))
        if found is not None:
            found.append((m.group(2), text[: m.start()].count("\n") + 1, blocks is not None))
        return m.group(1) + m.group(3) + m.group(4)

    text = CALC_BLOCK.sub(block, text)
    text = COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    return text.splitlines()


def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


@dataclass
class Context:
    kind: str  # paragraph | item | heading | row
    lines: list[tuple[int, str]]
    evidence_cell: bool = False  # a table row whose evidence column is filled


def contexts(lines: list[str], cfg: Config, defined: set[str] | None = None, known: set[str] | None = None) -> list[Context]:
    out: list[Context] = []
    paragraph: list[tuple[int, str]] = []
    item: list[tuple[int, str]] = []
    table: list[tuple[int, str]] = []
    fence = ""

    def flush_text() -> None:
        nonlocal paragraph, item
        if paragraph:
            out.append(Context("paragraph", paragraph))
        if item:
            out.append(Context("item", item))
        paragraph, item = [], []

    def flush_table() -> None:
        nonlocal table
        if table:
            out.extend(table_contexts(table, cfg, defined, known))
        table = []

    for number, line in enumerate(lines, 1):
        match = FENCE.match(line)
        if fence:
            if match and match.group(1) == fence:
                fence = ""
            continue
        if match:
            flush_text()
            flush_table()
            fence = match.group(1)
            continue
        if TABLE_ROW.match(line):
            flush_text()
            table.append((number, line))
            continue
        flush_table()
        stripped = line.lstrip("> ").rstrip() if line.lstrip().startswith(">") else line.rstrip()
        if not stripped.strip():
            flush_text()
        elif HEADING.match(stripped):
            flush_text()
            out.append(Context("heading", [(number, stripped)]))
        elif LIST_ITEM.match(stripped):
            flush_text()
            item = [(number, stripped)]
        elif item:
            item.append((number, stripped.strip()))
        else:
            paragraph.append((number, stripped.strip()))
    flush_text()
    flush_table()
    return out


def basis_holds(cell: str, cfg: Config, defined: set[str] | None, known: set[str] | None) -> bool:
    """A "Cơ sở" cell is evidence only with a link or an ID of basis_id_kinds. An A-xx must be declared in assumptions.yaml and an
    NFR / C / TC / R must be defined in the drafts (when those sets are known); a D-xx is defined outside the drafts (decision-log.md),
    so its shape is enough here and check_trace.py reports it when it is defined nowhere."""
    if LINK_EVIDENCE.search(cell):
        return True
    for m in cfg.basis_id.finditer(cell):
        kind = IDS.kind_of(m.group(1))
        if kind == "D" or (kind == "A" and (defined is None or m.group(1) in defined)) or (kind not in ("A", "D") and (known is None or m.group(1) in known)):
            return True
    return False


def table_contexts(rows: list[tuple[int, str]], cfg: Config, defined: set[str] | None = None, known: set[str] | None = None) -> list[Context]:
    header_at = next((i for i in range(len(rows) - 1) if SEPARATOR.match(rows[i + 1][1])), None)
    if header_at is None:
        return [Context("row", [row]) for row in rows if not SEPARATOR.match(row[1])]
    header = [re.sub(r"[`*_]", "", cell).casefold() for cell in split_cells(rows[header_at][1])]
    basis_at = [i for i, cell in enumerate(header) if any(word in cell for word in cfg.basis_columns)]
    evidence_at = [i for i, cell in enumerate(header) if i not in basis_at and any(word in cell for word in cfg.evidence_columns)]
    result = []
    for number, line in rows[header_at + 2 :]:
        cells = split_cells(line)
        filled = any(i < len(cells) and re.sub(r"[`*_]", "", cells[i]).strip().casefold() not in cfg.empty_cells for i in evidence_at)
        filled = filled or any(i < len(cells) and basis_holds(cells[i], cfg, defined, known) for i in basis_at)
        result.append(Context("row", [(number, line)], evidence_cell=filled))
    return result


def spans(context: Context) -> list[tuple[str, int]]:
    """The pieces evidence is looked for in: sentences of a paragraph, otherwise the whole context. -> (raw text, first line)."""
    if context.kind != "paragraph":
        return [(" ".join(text for _, text in context.lines), context.lines[0][0])]
    pieces, starts, offset = [], [], 0
    joined = ""
    for number, text in context.lines:
        starts.append((offset, number))
        joined += text + " "
        offset += len(text) + 1
    result, cursor = [], 0
    for part in SENTENCE_END.split(joined):
        index = joined.index(part, cursor)
        cursor = index + len(part)
        line = next(n for start, n in reversed(starts) if start <= index)
        if part.strip():
            result.append((part, line))
    return result or [(joined, context.lines[0][0])]


# --- the rules ----------------------------------------------------------------------------------------------------------------------

def has_evidence(raw: str, cfg: Config, defined: set[str] | None, known: set[str] | None = None) -> bool:
    if LINK_EVIDENCE.search(raw) or FORMULA_EVIDENCE.search(raw) or any(marker in raw for marker in cfg.source_markers):
        return True
    if any(known is None or m.group(1) in known for m in cfg.evidence_id.finditer(raw)):  # NFR-xx / C-xx: their definition carries the source
        return True
    return any(defined is None or m.group(0) in defined for m in ASSUMPTION_REF.finditer(raw))


def check_text(rel: str, text: str, cfg: Config, defined: set[str] | None, stats: Stats, blocks: dict[str, str] | None = None,
               known: set[str] | None = None) -> list[Finding]:
    """`defined`: the A-xx declared in assumptions.yaml (None: unknown, any A-xx counts). `known`: every ID defined in the drafts
    (None: unknown, any NFR / C / TC / R counts)."""
    findings: list[Finding] = []
    unproven: list[tuple[str, int, bool]] = []
    lines = prepare(text, blocks, unproven)
    for name, line, verifiable in unproven:
        findings.append(Finding(rel, line, "calc-block-edited" if verifiable else "calc-block-unverified",
                                f"khối calc:{name} " + ("không khớp kết quả calc_capacity.py tính lại (khối sinh bị sửa tay, hoặc không phải khối script sinh); nội dung được kiểm như văn bản thường"
                                                          if verifiable else "không xác minh được vì calc_capacity.py không tính lại được (xem lỗi của nó); nội dung được kiểm như văn bản thường")))
    for context in contexts(lines, cfg, defined, known):
        for raw, line in spans(context):
            masked = mask(raw)
            found = [m for pattern in (cfg.units, cfg.prefixed) for m in pattern.finditer(masked)]
            if found:
                stats.numbers += len(found)
                if context.evidence_cell or has_evidence(raw, cfg, defined, known):
                    stats.numbers_with_evidence += len(found)
                else:
                    shown = ", ".join(dict.fromkeys(f"{m.group('num')} {m.group('unit')}".strip() for m in sorted(found, key=lambda m: m.start())))
                    findings.append(Finding(rel, line, "number-without-evidence",
                                            f"số có đơn vị ({shown}) không có công thức, giả định (A-xx đã khai) hay nguồn (link, inputs/) trong cùng câu / mục / dòng bảng"))
            vague_text = cfg.exempt.sub(lambda m: " " * len(m.group(0)), masked)  # "ít nhất", "lớn nhất": exact, not vague
            words = sorted({nfc(m.group(0)).casefold() for m in cfg.vague.finditer(vague_text)})
            if words:
                stats.vague_words += len(words)
                if not re.search(r"\d", masked):
                    findings.append(Finding(rel, line, "vague-word", f"từ mơ hồ không kèm số: {', '.join(repr(w) for w in words)} (viết thành con số có đơn vị)"))
    return findings


def check_assumptions(workspace: Path, root: Path) -> tuple[list[Finding], set[str] | None, str | None]:
    """assumptions.md must be exactly what assumptions.yaml generates. -> (findings, declared IDs or None when unknown, expected text or None)."""
    findings: list[Finding] = []
    yaml_path, md_path = workspace / "capacity" / "assumptions.yaml", root / ASSUMPTIONS_MD
    problems = cc.Problems()
    data = cc.load_yaml(yaml_path, problems, "assumptions.yaml") if yaml_path.is_file() else None
    if not yaml_path.is_file():
        findings.append(Finding("capacity/assumptions.yaml", 1, "assumptions-yaml-missing", f"không có {yaml_path}: nguồn duy nhất của giả định"))
    if data is None:
        findings += [Finding("capacity/assumptions.yaml", 1, "assumptions-yaml-invalid", p) for p in problems.items]
        return findings, None, None
    parsed = cc.parse_assumptions(data, cc.read_level(root), problems)
    if parsed is None:
        findings += [Finding("capacity/assumptions.yaml", 1, "assumptions-yaml-invalid", p) for p in problems.items]
        ids = {a.get("id") for a in data.get("assumptions", []) if isinstance(a, dict) and isinstance(a.get("id"), str)} if isinstance(data.get("assumptions"), list) else None
        return findings, ids, None
    expected = cc.render_assumptions(parsed, cc.read_level(root))
    actual = cc.read_text(md_path)
    if actual is None:
        findings.append(Finding(ASSUMPTIONS_MD, 1, "assumptions-md-missing", "chưa có file; sinh bằng `calc_capacity.py` (G1: --assumptions-only)"))
    elif actual.rstrip("\n") != expected.rstrip("\n"):
        want, have = expected.rstrip("\n").splitlines(), actual.rstrip("\n").splitlines()
        missing = [line for line in want if line not in have]
        extra = [line for line in have if line not in want]
        detail = []
        for label, items in (("thiếu hoặc khác so với yaml", missing), ("không có trong yaml", extra)):
            if items:
                detail.append(f"{label}: " + " ⏎ ".join(item[:90] for item in items[:3]) + (f" (+{len(items) - 3})" if len(items) > 3 else ""))
        first = next((i for i, (w, h) in enumerate(zip(want, have), 1) if w != h), min(len(want), len(have)) + 1)
        findings.append(Finding(ASSUMPTIONS_MD, first, "assumptions-md-mismatch", "lệch capacity/assumptions.yaml (file sinh bị sửa tay, hoặc yaml đã đổi sau lần sinh): " + ("; ".join(detail) or "khác thứ tự hoặc số dòng") + ". Sinh lại bằng `calc_capacity.py`, không sửa tay"))
    return findings, set(parsed.items), expected


def regenerate(workspace: Path, root: Path, constants_dir: Path) -> tuple[dict[str, str] | None, dict[str, dict[str, str]] | None]:
    """What calc_capacity.py computes now: ({path: text of each file}, {path: {block name: text}}), or (None, None) when it cannot."""
    problems = cc.Problems()
    inputs = cc.load_inputs(workspace, constants_dir, problems, drafts=root)
    if inputs is None:
        return None, None
    outputs = cc.render_all(inputs, cc.Problems())
    blocks: dict[str, dict[str, str]] = {}
    for (_, table), (rel, text) in outputs.blocks.items():
        blocks.setdefault(rel, {})[table] = text
    return {rel: cc.normalize(text) for rel, text in outputs.files.items()}, blocks


def run(root: Path, workspace: Path, cfg: Config, constants_dir: Path | None = None) -> tuple[list[Finding], Stats]:
    findings, defined, expected_assumptions = check_assumptions(workspace, root)
    files, blocks = regenerate(workspace, root, constants_dir or workspace / "capacity" / "db-constants")
    if files is None and expected_assumptions is not None:
        files = {ASSUMPTIONS_MD: cc.normalize(expected_assumptions)}
    stats = Stats()
    known = set(cl.effective_definitions(cl.load(root)))  # every ID the drafts define
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        raw = path.read_text(encoding=ENCODING, errors="replace")
        rel = path.relative_to(root).as_posix()
        if rel in cc.OUTPUT_FILES:
            want = None if files is None else files.get(rel)
            if want is not None and cc.normalize(raw) == want:
                stats.generated_files += 1
                continue
            if rel != ASSUMPTIONS_MD:  # assumptions.md has its own, more detailed finding
                findings.append(Finding(rel, 1, "generated-file-edited" if want is not None else "generated-file-unverified",
                                        "file sinh bị sửa tay: khác kết quả calc_capacity.py tính lại; được kiểm như file thường. Sinh lại bằng `calc_capacity.py`" if want is not None
                                        else "không xác minh được file do calc_capacity.py sinh vì không tính lại được (xem lỗi của nó); được kiểm như file thường"))
        stats.files += 1
        findings += check_text(rel, raw, cfg, defined, stats, None if blocks is None else blocks.get(rel, {}), known)
    return findings, stats


def report(root: Path, findings: list[Finding], stats: Stats, today: str) -> str:
    lines = [f"# check_numbers {today}", "",
             f"Quét `{root}`: {stats.files} file ({stats.generated_files} file do calc_capacity.py sinh và khớp bản tính lại được bỏ qua), {stats.numbers} số có đơn vị "
             f"({stats.numbers_with_evidence} có công thức / giả định / nguồn), {stats.vague_words} từ mơ hồ gặp; {len(findings)} lỗi chặn.", "", "## Lỗi chặn", ""]
    return "\n".join(lines + ([f"- {f.render()}" for f in findings] or ["- không có"]) + [""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--root", type=Path, help="folder to scan (default: <workspace>/drafts)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="vague words, units, evidence columns (default: core/data/numbers.yaml)")
    parser.add_argument("--constants-dir", type=Path, help="db-constants folder used to recompute what calc_capacity.py wrote (default: <workspace>/capacity/db-constants)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    root = (args.root or workspace / "drafts").resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    cfg, errors = load_config(args.config.resolve())
    if cfg is None:
        for error in errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    # the drafts and the capacity inputs it recomputes from; hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    inputs = cr.expand(workspace, ["capacity/**/*"]) + ([p for p in args.constants_dir.resolve().rglob("*") if p.is_file()] if args.constants_dir else [])
    files = cr.hash_files(workspace, [*sorted(root.rglob("*.md")), *inputs])
    findings, stats = run(root, workspace, cfg, args.constants_dir.resolve() if args.constants_dir else None)
    findings.sort(key=lambda f: (f.path, f.line, f.code))
    text = report(root, findings, stats, today) + cr.render("check_numbers.py", not findings, files)
    target = workspace / "checks" / f"numbers-{today}.md"
    if workspace.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=ENCODING, newline="\n")
    print(f"check_numbers: {len(findings)} lỗi chặn ({stats.numbers} số có đơn vị, {stats.vague_words} từ mơ hồ)" + (f"; báo cáo: {target}" if workspace.is_dir() else ""))
    for finding in findings[:SHOWN]:
        print(f"error: {finding.render()}")
    if len(findings) > SHOWN:
        print(f"error: … và {len(findings) - SHOWN} lỗi nữa (xem báo cáo)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
