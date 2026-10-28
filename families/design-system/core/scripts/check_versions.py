# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check the version matrix of the tech stack (Q5): every technology of `02-tech-stack/README.md` has a row in
`02-tech-stack/versions-features.md` with a pinned version, an end-of-support date and a source link.

Default folder: `.agent-workspace/drafts/`. How the columns are found, what a floating version is and which words label an
end-of-support date is in `core/data/versions.yaml`.

Blocking errors (exit 1):
- a technology of README.md (one per table row, in the "Công nghệ" column) with no row of that name in versions-features.md;
  a name is the text before a role ("PostgreSQL — database quan hệ cho order-db", "PostgreSQL (order-db)");
- the version of README.md differs from the version of the row in versions-features.md;
- a version that is not pinned. Every layer needs major.minor(.patch) ("16", "latest", "mới nhất" fail). Only the third-party
  layer (the README "Lớp" column; layer names in versions.yaml) may also use a date version (YYYY-MM-DD) or "SaaS, không phiên
  bản"; a SaaS row needs no end date but its lifecycle cell must still link its changelog or deprecation policy;
- a row without an end-of-support date (the last date of the lifecycle cell, or the date after a label like "hết hỗ trợ"; the cell
  may say "chưa công bố" instead), an end date not after the release date, an impossible date, or no source link (http/https) in
  the lifecycle cell;
- a version already out of support on the run date (end date <= today);
- a version out of support within `eol_warning_months` (12) whose "Rủi ro" cell has no markdown link to an `R-xx`;
- the same technology and version twice;
- a missing file, no table, or a table without the needed columns.

Warnings (never block): an end-of-support date within `eol_warning_months` (the row also needs the R-xx link above), a row in
versions-features.md for a technology README.md does not list.

The report is also written to `<workspace>/checks/versions-<date>.md`, ending with the sha256 of every file checked (checkreport.py).

    uv run check_versions.py [--workspace DIR] [--root DIR] [--config FILE]
"""

import argparse
import calendar
import datetime
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_links as cl  # noqa: E402
import checkreport as cr  # noqa: E402

ENCODING = "utf-8"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "data" / "versions.yaml"
README = "02-tech-stack/README.md"
VERSIONS = "02-tech-stack/versions-features.md"
SHOWN = 25
ROLE_SPLIT = re.compile(r"\s+[—–-]\s+|\s*\(|\s*:\s")
VERSION = re.compile(r"\d+(?:\.\d+)+")
PINNED = re.compile(r"\d+\.\d+")
DATE_PARTS = r"(?<![\d-])(?P<y>\d{4})-(?P<m>\d{2})(?:-(?P<d>\d{2}))?(?![\d-])"
DATE = re.compile(DATE_PARTS)
LINK = re.compile(r"https?://[^\s)|>\]]+")
FULL_DATE = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
MD_LINK = re.compile(r"\[([^\]]*)\]\(\s*<?([^)\s>]+)[^)]*\)")
RISK_ID = re.compile(r"(?<![A-Za-z0-9_])R-[A-Za-z0-9]+", re.IGNORECASE)


@dataclass
class Config:
    readme_technology: tuple[str, ...]
    readme_version: tuple[str, ...]
    readme_layer: tuple[str, ...]
    versions_technology: tuple[str, ...]
    versions_version: tuple[str, ...]
    versions_lifecycle: tuple[str, ...]
    versions_risk: tuple[str, ...]
    third_party_layers: tuple[str, ...]
    date_versions: bool
    saas_phrases: tuple[str, ...]
    floating: tuple[str, ...]
    eol_labels: tuple[re.Pattern, ...]  # tried in order: "label date", "date (label)", "label ... date"
    no_eol: tuple[str, ...]
    warn_months: int


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
class Row:
    line: int
    name: str  # as written, role removed
    key: str  # normalised for matching
    version: str  # the version cell, cleaned
    lifecycle: str = ""  # the lifecycle cell, raw (links kept)
    layer: str = ""  # README only: the "Lớp" cell
    risk: str | None = None  # versions-features only: the "Rủi ro" cell, raw (None when the table has no such column)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def load_config(path: Path) -> tuple[Config | None, list[str]]:
    if not path.is_file():
        return None, [f"không có file dữ liệu {path}"]
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except yaml.YAMLError as error:
        return None, [f"{path.name}: YAML hỏng ({str(error).splitlines()[0]})"]
    if not isinstance(data, dict):
        return None, [f"{path.name}: gốc phải là mapping"]
    errors = []

    def words(block: dict, key: str, where: str) -> tuple[str, ...]:
        value = block.get(key) if isinstance(block, dict) else None
        if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v.strip() for v in value):
            errors.append(f"{path.name}: {where}{key} phải là danh sách chuỗi không rỗng")
            return ()
        return tuple(nfc(v).casefold() for v in value)

    readme, versions = data.get("readme_columns"), data.get("versions_columns")
    for name, block in (("readme_columns", readme), ("versions_columns", versions)):
        if not isinstance(block, dict):
            errors.append(f"{path.name}: thiếu {name}")
    date_versions = data.get("date_versions")
    if not isinstance(date_versions, bool):
        errors.append(f"{path.name}: date_versions phải là true hoặc false")
    cfg = Config(
        readme_technology=words(readme or {}, "technology", "readme_columns."), readme_version=words(readme or {}, "version", "readme_columns."),
        readme_layer=words(readme or {}, "layer", "readme_columns."),
        versions_technology=words(versions or {}, "technology", "versions_columns."), versions_version=words(versions or {}, "version", "versions_columns."),
        versions_lifecycle=words(versions or {}, "lifecycle", "versions_columns."), versions_risk=words(versions or {}, "risk", "versions_columns."),
        third_party_layers=words(data, "third_party_layers", ""), date_versions=bool(date_versions), saas_phrases=words(data, "saas_phrases", ""),
        floating=words(data, "floating_versions", ""), eol_labels=(), no_eol=words(data, "no_eol_phrases", ""), warn_months=12,
    )
    labels = words(data, "eol_labels", "")
    months = data.get("eol_warning_months")
    if not isinstance(months, int) or isinstance(months, bool) or months < 0:
        errors.append(f"{path.name}: eol_warning_months phải là số nguyên không âm")
    if errors:
        return None, errors
    label = "(?:" + "|".join(re.escape(item) for item in sorted(labels, key=len, reverse=True)) + ")"
    cfg.eol_labels = (
        re.compile(label + r"[\s:=-]{0,6}" + DATE_PARTS, re.IGNORECASE),  # hết hỗ trợ 2028-11-09 / EOL: 2028-11
        re.compile(DATE_PARTS + r"[\s(\[,;:-]{0,6}" + label, re.IGNORECASE),  # 2028-11-09 (hết hỗ trợ)
        re.compile(label + r"\D{0,25}?" + DATE_PARTS, re.IGNORECASE),  # hết hỗ trợ của bản 16 là 2028-11-09
    )
    cfg.warn_months = months
    return cfg, []


# --- reading the tables ---------------------------------------------------------------------------------------------------------

def clean(cell: str) -> str:
    text = cl.LINK_TEXT_RE.sub(r"\1", cell)
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", nfc(text))).strip()


def tech_key(cell: str) -> tuple[str, str]:
    """(name as written, normalised key): the text before a role, markup removed."""
    name = ROLE_SPLIT.split(clean(cell), maxsplit=1)[0].strip()
    return name, name.casefold()


def find_column(header: list[str], words: tuple[str, ...]) -> int | None:
    for index, cell in enumerate(header):
        text = clean(cell).casefold()
        if any(word in text for word in words):
            return index
    return None


def read_tables(text: str) -> list[tuple[list[str], list[tuple[int, list[str]]]]]:
    """(header cells, [(line number, cells)]) of every table that has a header and a separator."""
    lines = cl.mask_fences(nfc(text).splitlines())
    found, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and cl.is_separator(lines[i + 1]):
            header = cl.split_cells(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = cl.split_cells(lines[j])
                if any(c.strip() for c in cells):
                    rows.append((j + 1, cells))
                j += 1
            found.append((header, rows))
            i = j
        else:
            i += 1
    return found


def readme_rows(text: str, cfg: Config, findings: list[Finding]) -> list[Row]:
    rows, any_table = [], False
    for header, body in read_tables(text):
        tech = find_column(header, cfg.readme_technology)
        if tech is None:
            continue
        any_table = True
        version, layer = find_column(header, cfg.readme_version), find_column(header, cfg.readme_layer)
        if version is None:
            findings.append(Finding(README, 1, "readme-column-missing", f"bảng có cột công nghệ nhưng không có cột phiên bản (tiêu đề chứa: {', '.join(cfg.readme_version)})"))
            continue
        for line, cells in body:
            if tech < len(cells) and clean(cells[tech]):
                name, key = tech_key(cells[tech])
                rows.append(Row(line, name, key, clean(cells[version]) if version < len(cells) else "", layer=clean(cells[layer]) if layer is not None and layer < len(cells) else ""))
    if not any_table:
        findings.append(Finding(README, 1, "readme-no-table", f"không có bảng nào có cột công nghệ (tiêu đề chứa: {', '.join(cfg.readme_technology)})"))
    return rows


def versions_rows(text: str, cfg: Config, findings: list[Finding]) -> list[Row]:
    rows, any_table = [], False
    for header, body in read_tables(text):
        tech = find_column(header, cfg.versions_technology)
        if tech is None:
            continue
        any_table = True
        version, life, risk = find_column(header, cfg.versions_version), find_column(header, cfg.versions_lifecycle), find_column(header, cfg.versions_risk)
        missing = [label for label, index in (("phiên bản chốt", version), ("ngày hết hỗ trợ / vòng đời", life)) if index is None]
        if missing:
            findings.append(Finding(VERSIONS, 1, "versions-column-missing", f"bảng thiếu cột: {', '.join(missing)}"))
            continue
        for line, cells in body:
            if tech < len(cells) and clean(cells[tech]):
                name, key = tech_key(cells[tech])
                rows.append(Row(line, name, key, clean(cells[version]) if version < len(cells) else "", cells[life] if life < len(cells) else "",
                                 risk=(cells[risk] if risk < len(cells) else "") if risk is not None else None))
    if not any_table:
        findings.append(Finding(VERSIONS, 1, "versions-no-table", f"không có bảng nào có cột công nghệ (tiêu đề chứa: {', '.join(cfg.versions_technology)})"))
    return rows


# --- the rules ---------------------------------------------------------------------------------------------------------------------

def is_third_party(layers: list[str], cfg: Config) -> bool:
    """True when every README row of the technology sits in a third-party layer (a technology unknown to the README is strict)."""
    return bool(layers) and all(any(word in layer.casefold() for word in cfg.third_party_layers) for layer in layers)


def version_token(version: str, third_party: bool, cfg: Config) -> tuple[str | None, str | None]:
    """(canonical token to compare, problem). Every layer: major.minor(.patch). Third-party layer only: YYYY-MM-DD, "SaaS, không phiên bản"."""
    text = nfc(version).casefold()
    if not version:
        return None, "ô phiên bản trống"
    if any(phrase in text for phrase in cfg.saas_phrases):
        if third_party:
            return "saas", None
        return None, "\"SaaS, không phiên bản\" chỉ được dùng ở lớp third-party (cột Lớp của README); lớp này cần major.minor (ví dụ 16.4)"
    for word in cfg.floating:
        if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text):
            return None, f"\"{word}\" không phải phiên bản đã chốt"
    found = VERSION.search(version)
    if found and PINNED.search(version):
        return found.group(0), None
    date = FULL_DATE.search(version)
    if date and cfg.date_versions:
        if make_date(date.group(1), date.group(2), date.group(3), False) is None:
            return None, f"ngày phiên bản không hợp lệ \"{date.group(0)}\""
        if third_party:
            return date.group(0), None
        return None, "phiên bản theo ngày (YYYY-MM-DD) chỉ được dùng ở lớp third-party; lớp này cần major.minor (ví dụ 16.4)"
    if PINNED.search(version):
        return PINNED.search(version).group(0), None
    return None, "phiên bản phải có dạng major.minor (ví dụ 16.4), không phải chỉ số major" + ("; lớp third-party còn được ghi YYYY-MM-DD hoặc \"SaaS, không phiên bản\"" if third_party else "")


def risk_linked(cell: str | None) -> bool:
    """A markdown link to an R-xx: the link text or its target (anchor) names the risk."""
    return bool(cell) and any(RISK_ID.search(m.group(1)) or RISK_ID.search(m.group(2)) for m in MD_LINK.finditer(nfc(cell)))


def make_date(year: str, month: str, day: str | None, end: bool) -> datetime.date | None:
    """YYYY-MM-DD, or YYYY-MM (first day of the month for a release, last day for an end of support); None when impossible."""
    y, m = int(year), int(month)
    try:
        if day is None:
            return datetime.date(y, m, calendar.monthrange(y, m)[1] if end else 1)
        return datetime.date(y, m, int(day))
    except ValueError:
        return None


def lifecycle(cell: str, cfg: Config) -> tuple[datetime.date | None, datetime.date | None, bool, list[str], bool]:
    """(release, end of support, vendor says no end date, impossible dates, has link)."""
    text = nfc(cell)
    has_link = LINK.search(text) is not None
    plain = LINK.sub(" ", cl.LINK_TEXT_RE.sub(r"\1", text))
    matches = list(DATE.finditer(plain))
    invalid = [m.group(0) for m in matches if make_date(m.group("y"), m.group("m"), m.group("d"), False) is None]
    labelled = next((found for pattern in cfg.eol_labels if (found := pattern.search(plain))), None)
    end = release = None
    if labelled:
        end = make_date(labelled.group("y"), labelled.group("m"), labelled.group("d"), True)
        others = [m for m in matches if m.start("y") != labelled.start("y")]
        release = make_date(others[0].group("y"), others[0].group("m"), others[0].group("d"), False) if others else None
    elif len(matches) >= 2:
        release = make_date(matches[0].group("y"), matches[0].group("m"), matches[0].group("d"), False)
        end = make_date(matches[-1].group("y"), matches[-1].group("m"), matches[-1].group("d"), True)
    no_end = any(phrase in plain.casefold() for phrase in cfg.no_eol)
    return release, end, no_end, invalid, has_link


def months_between(today: datetime.date, later: datetime.date) -> float:
    return (later - today).days / (365 / 12)


def check_versions_rows(rows: list[Row], cfg: Config, today: datetime.date, third_party: set[str] | None = None) -> list[Finding]:
    findings = []
    third_party = third_party or set()
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        party = row.key in third_party
        token, reason = version_token(row.version, party, cfg)
        if reason:
            findings.append(Finding(VERSIONS, row.line, "version-not-pinned", f"{row.name}: {reason}"))
        pair = (row.key, token or row.version.casefold())
        if pair in seen:
            findings.append(Finding(VERSIONS, row.line, "duplicate-row", f"{row.name} {row.version} đã có ở dòng {seen[pair]} (mỗi công nghệ và phiên bản một dòng)"))
        seen.setdefault(pair, row.line)
        release, end, no_end, invalid, has_link = lifecycle(row.lifecycle, cfg)
        for text in invalid:
            findings.append(Finding(VERSIONS, row.line, "date-invalid", f"{row.name}: ngày không hợp lệ \"{text}\" (dùng YYYY-MM-DD hoặc YYYY-MM)"))
        if not has_link:
            what = "link tới changelog hoặc chính sách ngừng hỗ trợ của dịch vụ" if token == "saas" else "link nguồn chính thức (http/https)"
            findings.append(Finding(VERSIONS, row.line, "source-link-missing", f"{row.name}: ô vòng đời không có {what}"))
        if end is None and not no_end and token != "saas":
            if not invalid:
                findings.append(Finding(VERSIONS, row.line, "eol-missing", f"{row.name}: thiếu ngày hết hỗ trợ (ghi \"phát hành YYYY-MM-DD; hết hỗ trợ YYYY-MM-DD\" hoặc \"chưa công bố\")"))
        elif end is not None:
            if release is not None and end <= release:
                findings.append(Finding(VERSIONS, row.line, "eol-before-release", f"{row.name}: ngày hết hỗ trợ {end} không sau ngày phát hành {release}"))
            elif end <= today:
                findings.append(Finding(VERSIONS, row.line, "eol-passed", f"{row.name} {row.version}: đã hết hỗ trợ từ {end} (tính đến {today}); chọn phiên bản còn hỗ trợ"))
            elif months_between(today, end) <= cfg.warn_months:
                findings.append(Finding(VERSIONS, row.line, "eol-soon", f"{row.name} {row.version}: hết hỗ trợ {end}, còn dưới {cfg.warn_months} tháng", blocking=False))
                if not risk_linked(row.risk):
                    findings.append(Finding(VERSIONS, row.line, "eol-soon-without-risk",
                                            f"{row.name} {row.version}: hết hỗ trợ trong {cfg.warn_months} tháng nên cột Rủi ro phải có link tới R-xx (ví dụ [R-05](../11-risks/risk-register.md#r-05))"
                                            + ("" if row.risk is not None else "; bảng không có cột Rủi ro")))
    return findings


def check_matrix(readme: list[Row], versions: list[Row], cfg: Config, third_party: set[str]) -> list[Finding]:
    findings = []
    by_key: dict[str, list[Row]] = {}
    for row in versions:
        by_key.setdefault(row.key, []).append(row)
    for row in readme:
        candidates = by_key.get(row.key)
        if not candidates:
            findings.append(Finding(README, row.line, "tech-missing-from-versions", f"{row.name} không có dòng trong {VERSIONS}"))
            continue
        party = row.key in third_party
        wanted, reason = version_token(row.version, party, cfg)
        if wanted is None:
            findings.append(Finding(README, row.line, "version-not-pinned", f"{row.name}: ô phiên bản của README: {reason}"))
            continue
        have = [token for token in (version_token(c.version, party, cfg)[0] for c in candidates) if token]
        if wanted not in have:
            findings.append(Finding(README, row.line, "version-mismatch", f"{row.name}: README ghi {wanted}, {VERSIONS} ghi {', '.join(have) or 'không có phiên bản hợp lệ'} (dòng {', '.join(str(c.line) for c in candidates)})"))
    listed = {row.key for row in readme}
    for row in versions:
        if row.key not in listed:
            findings.append(Finding(VERSIONS, row.line, "versions-row-not-in-readme", f"{row.name} có trong ma trận phiên bản nhưng {README} không liệt kê", blocking=False))
    return findings


def run(root: Path, cfg: Config, today: datetime.date) -> tuple[list[Finding], dict[str, int]]:
    findings: list[Finding] = []
    stats = {"readme": 0, "versions": 0}
    texts = {}
    for rel in (README, VERSIONS):
        path = root / rel
        if path.is_file():
            texts[rel] = path.read_text(encoding=ENCODING, errors="replace")
        else:
            findings.append(Finding(rel, 1, "file-missing", f"không có {rel} trong {root}"))
    readme = readme_rows(texts[README], cfg, findings) if README in texts else []
    versions = versions_rows(texts[VERSIONS], cfg, findings) if VERSIONS in texts else []
    stats["readme"], stats["versions"] = len(readme), len(versions)
    layers: dict[str, list[str]] = {}
    for row in readme:
        layers.setdefault(row.key, []).append(row.layer)
    third_party = {key for key, names in layers.items() if is_third_party(names, cfg)}
    findings += check_versions_rows(versions, cfg, today, third_party)
    if README in texts and VERSIONS in texts:
        findings += check_matrix(readme, versions, cfg, third_party)
    return findings, stats


def report(root: Path, findings: list[Finding], stats: dict[str, int], today: str) -> str:
    errors = [f for f in findings if f.blocking]
    warnings = [f for f in findings if not f.blocking]
    lines = [f"# check_versions {today}", "", f"Quét `{root}`: {stats['readme']} công nghệ trong README, {stats['versions']} dòng trong ma trận phiên bản; {len(errors)} lỗi chặn, {len(warnings)} cảnh báo.", ""]
    for title, items in (("Lỗi chặn", errors), ("Cảnh báo (không chặn gate)", warnings)):
        lines += [f"## {title}", ""] + ([f"- {f.render()}" for f in items] or ["- không có"]) + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--root", type=Path, help="folder holding 02-tech-stack/ (default: <workspace>/drafts)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="columns, floating versions, EOL labels (default: core/data/versions.yaml)")
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
    today_text = args.date or datetime.date.today().isoformat()
    try:
        today = datetime.date.fromisoformat(today_text)
    except ValueError:
        parser.error("--date phải là YYYY-MM-DD")
    files = cr.hash_files(workspace, [root / README, root / VERSIONS])  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    findings, stats = run(root, cfg, today)
    findings.sort(key=lambda f: (not f.blocking, f.path, f.line, f.code))
    text = report(root, findings, stats, today_text) + cr.render("check_versions.py", not any(f.blocking for f in findings), files)
    target = workspace / "checks" / f"versions-{today_text}.md"
    if workspace.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=ENCODING, newline="\n")
    errors_list = [f for f in findings if f.blocking]
    warnings_list = [f for f in findings if not f.blocking]
    print(f"check_versions: {len(errors_list)} lỗi chặn, {len(warnings_list)} cảnh báo ({stats['readme']} công nghệ, {stats['versions']} dòng phiên bản)" + (f"; báo cáo: {target}" if workspace.is_dir() else ""))
    for finding in errors_list[:SHOWN]:
        print(f"error: {finding.render()}")
    if len(errors_list) > SHOWN:
        print(f"error: … và {len(errors_list) - SHOWN} lỗi nữa (xem báo cáo)")
    for finding in warnings_list[:5]:
        print(f"warning: {finding.render()}")
    return 1 if errors_list else 0


if __name__ == "__main__":
    raise SystemExit(main())
