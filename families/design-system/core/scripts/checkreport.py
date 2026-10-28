"""Shared by the check scripts and promote_drafts.py (a module, not a script): the block every report of `checks/` ends with.

The block says which script ran, whether it was clean, for which gate and in which mode, and lists every file it checked with
the sha256 of its content. promote_drafts.py compares those hashes with the files as they are now, so a report is never trusted
for its age (no mtime): a changed, deleted or newly added file makes it stale. Line endings are normalised (CRLF = LF) before
hashing. The files and rules for each gate are in data/gates.yaml.

    <!-- BEGIN:checked -->
    - Script: check_links.py
    - Kết quả: sạch
    - Gate: G3
    | File | sha256 |
    | `drafts/00-context/a.md` | `<64 hex>` |
    <!-- END:checked -->
"""

import datetime
import hashlib
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

ENCODING = "utf-8"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "data" / "gates.yaml"
BEGIN = "<!-- BEGIN:checked -->"
END = "<!-- END:checked -->"
CLEAN = "sạch"
DIRTY = "có lỗi"
ALL_GATES = "tất cả"
GATE_RE = re.compile(r"G(10|[0-9])")
ROW_RE = re.compile(r"^\|\s*`(?P<path>[^`]+)`\s*\|\s*`(?P<hash>[0-9a-f]{64})`\s*\|\s*$")
FIELD_RE = re.compile(r"^-\s+(?P<key>Script|Kết quả|Gate|Chế độ):\s*(?P<value>.+?)\s*$")
REPORT_NAME = r"{prefix}-(\d{{4}}-\d{{2}}-\d{{2}})\.md"


# --- hashing ---------------------------------------------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rel_path(workspace: Path, path: Path) -> str:
    """Path as written in a report: relative to the workspace (posix) when inside it, else absolute."""
    path = path.resolve()
    try:
        return path.relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(workspace: Path, rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else workspace / rel


def hash_files(workspace: Path, paths: Iterable[Path]) -> dict[str, str]:
    """{path as in a report: sha256}, sorted; what is not a readable file is left out."""
    found: dict[str, str] = {}
    for path in paths:
        try:
            if path.is_file():
                found[rel_path(workspace, path)] = sha256_file(path)
        except OSError:
            continue
    return dict(sorted(found.items()))


def expand(workspace: Path, globs: Iterable[str]) -> list[Path]:
    """Files under the workspace that match the globs (relative to it)."""
    found: dict[Path, None] = {}
    for pattern in globs:
        for path in workspace.glob(pattern):
            if path.is_file():
                found[path] = None
    return sorted(found)


# --- the block -------------------------------------------------------------------------------------------------------------

def escape(rel: str) -> str:
    """Characters that would break the backticks or the line (and `%`, so that the decoding is exact), as %XX."""
    for char in ("%", "`", "\n", "\r"):
        rel = rel.replace(char, f"%{ord(char):02X}")
    return rel


@dataclass
class Block:
    script: str
    clean: bool
    gate: str | None = None
    mode: str | None = None
    files: dict[str, str] = field(default_factory=dict)


def render(script: str, ok: bool, files: dict[str, str], gate: str | None = None, mode: str | None = None) -> str:
    lines = ["", BEGIN, "", "## Đã kiểm (máy đọc: không sửa tay)", "", f"- Script: {script}", f"- Kết quả: {CLEAN if ok else DIRTY}"]
    if gate:
        lines.append(f"- Gate: {gate}")
    if mode:
        lines.append(f"- Chế độ: {mode}")
    lines += [f"- Số file: {len(files)}", "", "| File | sha256 |", "| --- | --- |"]
    lines += [f"| `{escape(rel)}` | `{digest}` |" for rel, digest in sorted(files.items())]
    lines += ["", END, ""]
    return "\n".join(lines)


def parse(text: str) -> Block | None:
    """The last block of a report; None when there is none or it is malformed (a script and a result are required)."""
    start, end = text.rfind(BEGIN), text.rfind(END)
    if start < 0 or end < start:
        return None
    fields: dict[str, str] = {}
    files: dict[str, str] = {}
    for line in text[start + len(BEGIN):end].splitlines():
        row = ROW_RE.match(line.strip())
        if row:
            files[urllib.parse.unquote(row.group("path"))] = row.group("hash")
            continue
        match = FIELD_RE.match(line.strip())
        if match and match.group("key") not in fields:
            fields[match.group("key")] = match.group("value")
    if "Script" not in fields or fields.get("Kết quả") not in (CLEAN, DIRTY):
        return None
    return Block(fields["Script"], fields["Kết quả"] == CLEAN, fields.get("Gate"), fields.get("Chế độ"), files)


def dated_reports(checks_dir: Path, prefix: str) -> list[Path]:
    """The `<prefix>-<date>.md` files, the latest date in the name first (the name, not the modification time)."""
    pattern = re.compile(REPORT_NAME.format(prefix=re.escape(prefix)))
    found: list[tuple[datetime.date, Path]] = []
    for path in checks_dir.glob(f"{prefix}-*.md") if checks_dir.is_dir() else []:
        match = pattern.fullmatch(path.name)
        if not match:
            continue
        try:
            day = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        found.append((day, path))
    return [path for _, path in sorted(found, key=lambda item: item[0], reverse=True)]


def latest_report(checks_dir: Path, prefix: str) -> Path | None:
    """`<prefix>-<date>.md` with the latest date in its name (the name, not the modification time)."""
    found = dated_reports(checks_dir, prefix)
    return found[0] if found else None


# --- the block of a promote run --------------------------------------------------------------------------------------------
# promote_drafts.py ends every run that copied with this block: the sha256 of each file now in architecture/ (path relative to
# architecture/). archive_release.py releases only when architecture/ still equals the latest such block of G10.

PROMOTED_BEGIN = "<!-- BEGIN:promoted -->"
PROMOTED_END = "<!-- END:promoted -->"
PROMOTED_RE = re.compile(re.escape(PROMOTED_BEGIN) + r"(.*?)" + re.escape(PROMOTED_END), re.DOTALL)


@dataclass
class Promoted:
    gate: str
    files: dict[str, str]


def render_promoted(gate: int, files: dict[str, str]) -> str:
    lines = ["", PROMOTED_BEGIN, "", "#### Đã chép (máy đọc: không sửa tay)", "", "- Script: promote_drafts.py", f"- Gate: G{gate}", f"- Số file: {len(files)}", "", "| File | sha256 |", "| --- | --- |"]
    lines += [f"| `{escape(rel)}` | `{digest}` |" for rel, digest in sorted(files.items())]
    lines += ["", PROMOTED_END, ""]
    return "\n".join(lines)


def parse_promoted(text: str) -> list[Promoted]:
    """Every well-formed promoted block of a report, in the order written (one needs a gate and at least one file row)."""
    blocks = []
    for match in PROMOTED_RE.finditer(text):
        fields: dict[str, str] = {}
        files: dict[str, str] = {}
        for line in match.group(1).splitlines():
            row = ROW_RE.match(line.strip())
            if row:
                files[urllib.parse.unquote(row.group("path"))] = row.group("hash")
                continue
            field_match = FIELD_RE.match(line.strip())
            if field_match and field_match.group("key") not in fields:
                fields[field_match.group("key")] = field_match.group("value")
        if GATE_RE.fullmatch(fields.get("Gate", "")) and files:
            blocks.append(Promoted(fields["Gate"], files))
    return blocks


def stale_reasons(workspace: Path, block: Block, scope: Iterable[str]) -> list[str]:
    """Why the report no longer describes the workspace: files changed, deleted, or added within `scope` after the check."""
    reasons = []
    for rel, digest in block.files.items():
        path = resolve(workspace, rel)
        if not path.is_file():
            reasons.append(f"đã xóa sau khi kiểm: {rel}")
            continue
        try:
            changed = sha256_file(path) != digest
        except OSError:
            changed = True
        if changed:
            reasons.append(f"đã đổi sau khi kiểm: {rel}")
    for path in expand(workspace, scope):
        if rel_path(workspace, path) not in block.files:
            reasons.append(f"mới thêm sau khi kiểm (báo cáo không có): {rel_path(workspace, path)}")
    return reasons


# --- data/gates.yaml -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportSpec:
    prefix: str
    gated: bool
    scope: tuple[str, ...]
    modes: dict[str, tuple[str, ...]] | None

    def modes_for(self, gate: int) -> tuple[str, ...] | None:
        if self.modes is None:
            return None
        return self.modes.get(f"G{gate}", self.modes["default"])


@dataclass(frozen=True)
class Gates:
    gates: dict[int, tuple[str, ...]]
    reports: dict[str, ReportSpec]
    non_report: tuple[str, ...]


def _strings(value: object) -> tuple[str, ...] | None:
    return tuple(value) if isinstance(value, list) and all(isinstance(v, str) and v for v in value) else None


def load_config(path: Path = DEFAULT_CONFIG) -> tuple[Gates | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    errors: list[str] = []
    if not isinstance(data, dict) or data.get("version") != 1:
        return None, [f"{path}: cần `version: 1` và các mục gates, reports, non_report_scripts"]
    reports: dict[str, ReportSpec] = {}
    raw_reports = data.get("reports")
    if not isinstance(raw_reports, dict) or not raw_reports:
        errors.append("reports: cần một mục cho mỗi script có báo cáo")
        raw_reports = {}
    for name, entry in raw_reports.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("prefix"), str) or not entry["prefix"]:
            errors.append(f"reports.{name}: cần `prefix`")
            continue
        scope = _strings(entry.get("scope", []))
        modes = entry.get("modes")
        if scope is None:
            errors.append(f"reports.{name}.scope: cần danh sách chuỗi")
            continue
        parsed_modes = None
        if modes is not None:
            if not isinstance(modes, dict) or _strings(modes.get("default")) is None or any(_strings(v) is None for v in modes.values()):
                errors.append(f"reports.{name}.modes: cần `default` và mỗi gate là danh sách chuỗi")
                continue
            parsed_modes = {key: tuple(value) for key, value in modes.items()}
        reports[str(name)] = ReportSpec(entry["prefix"], bool(entry.get("gated", False)), scope, parsed_modes)
    prefixes = [spec.prefix for spec in reports.values()]
    if len(set(prefixes)) != len(prefixes):
        errors.append("reports: hai script dùng chung một prefix")
    non_report = _strings(data.get("non_report_scripts"))
    if non_report is None:
        errors.append("non_report_scripts: cần danh sách chuỗi")
        non_report = ()
    if set(non_report) & set(reports):
        errors.append("non_report_scripts: có script cũng nằm trong reports")
    gates: dict[int, tuple[str, ...]] = {}
    raw_gates = data.get("gates")
    if not isinstance(raw_gates, dict):
        errors.append("gates: cần G0 đến G10")
        raw_gates = {}
    for key, scripts in raw_gates.items():
        match = GATE_RE.fullmatch(str(key))
        names = _strings(scripts)
        if not match or names is None:
            errors.append(f"gates.{key}: tên gate G0-G10 và danh sách script")
            continue
        unknown = [n for n in names if n not in reports]
        if unknown:
            errors.append(f"gates.{key}: script không có trong reports: {', '.join(unknown)}")
        gates[int(match.group(1))] = names
    if sorted(gates) != list(range(11)) and not errors:
        errors.append("gates: thiếu gate (cần đủ G0 đến G10)")
    return (None, errors) if errors else (Gates(gates, reports, non_report), [])


# --- what promote_drafts.py asks of the reports -----------------------------------------------------------------------------

def gate_problems(workspace: Path, gate: int, config: Gates) -> tuple[list[str], list[str]]:
    """(problems, one line per accepted report) for the reports the gate needs."""
    problems: list[str] = []
    accepted: list[str] = []
    checks = workspace / "checks"
    for script in config.gates[gate]:
        spec = config.reports[script]
        label = f"{script}.py"
        path = latest_report(checks, spec.prefix)
        if path is None:
            problems.append(f"{label}: chưa có báo cáo checks/{spec.prefix}-<ngày>.md; chạy nó" + (f" với --gate G{gate}" if spec.gated else ""))
            continue
        try:
            text = path.read_text(encoding=ENCODING, errors="replace")
        except OSError as error:
            problems.append(f"{label}: không đọc được {path.name}: {error}")
            continue
        block = parse(text)
        if block is None or block.script.removesuffix(".py") != script:
            problems.append(f"{label}: {path.name} không có khối \"Đã kiểm\" đúng của script này (báo cáo do bản script cũ ghi, hoặc bị sửa tay): chạy lại")
            continue
        if not block.clean:
            problems.append(f"{label}: báo cáo mới nhất {path.name} ghi \"{DIRTY}\"; sửa lỗi rồi chạy lại")
            continue
        if spec.gated and block.gate not in (f"G{gate}", ALL_GATES):
            problems.append(f"{label}: {path.name} là của {block.gate or 'gate không ghi'}, cần G{gate}; chạy lại với --gate G{gate}")
            continue
        modes = spec.modes_for(gate)
        if modes is not None and block.mode not in modes:
            problems.append(f"{label}: {path.name} chạy ở chế độ \"{block.mode}\", ở G{gate} cần một trong: {', '.join(modes)}")
            continue
        reasons = stale_reasons(workspace, block, spec.scope)
        if reasons:
            shown = "; ".join(reasons[:3]) + (f"; … và {len(reasons) - 3} file nữa" if len(reasons) > 3 else "")
            problems.append(f"{label}: báo cáo {path.name} đã cũ ({shown}); chạy lại")
            continue
        accepted.append(f"{label}: {path.name}, sạch, {len(block.files)} file khớp hash")
    return problems, accepted
