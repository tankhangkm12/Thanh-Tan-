# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Release vN: snapshot the workspace into `archive/vN/` and put the entry of vN first in `architecture/CHANGELOG.md`.

It refuses, and says exactly what is missing, unless all of this holds:
- state.md says G10 (and every gate before it) is approved the way rule 2 asks (approvals.py);
- `architecture/` exists (promote_drafts.py --gate G10 made it; this script only adds the changelog entry to it);
- the latest report `checks/promote-<date>.md` that holds a successful G10 run lists the sha256 of every file that run left in
  architecture/, and architecture/ (the changelog left out) still equals it: a file edited, deleted or added since is named and
  refused (a release is exactly what the user approved);
- `archive/vN/` does not exist yet (nothing is ever overwritten) and the changelog has no entry for vN;
- nothing it would read is a symbolic link.
vN is the next number after the highest `archive/vN` (v1 when there is none), or `--version N`.

The snapshot (data/archive.yaml) is state.md, plan/, stack/, capacity/, decisions/, reviews/, risks/ and models.md; it is built in
a temporary folder, read back byte for byte and only then renamed to `archive/vN/`, so a failed run leaves no half snapshot. The
changelog entry has: version, date, level, the decisions the user settled (D-xxx and the option), the risks the user accepted
and, when `inputs/previous-design/` exists, the files added, changed and removed against `architecture/` (sha256, line ends
normalised).

Exit 0 done (or --dry-run fine), 1 refused or the release failed, 2 wrong arguments. The run is appended to
`<workspace>/checks/archive-<date>.md` (not with --dry-run, which writes nothing).

    uv run archive_release.py [--version N] [--workspace DIR] [--architecture DIR] [--dry-run] [--config FILE]
"""

import argparse
import datetime
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import approvals  # noqa: E402
import check_workspace as cw  # noqa: E402
import checkreport as cr  # noqa: E402

CORE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CORE / "data" / "archive.yaml"
VERSION_DIR = re.compile(r"v([0-9]+)")
SHOWN = 25


@dataclass
class Config:
    gate: int
    archive_dir: str
    snapshot: list[str]
    changelog: str
    previous_design: str
    levels: list[str]
    promote_prefix: str


@dataclass
class Release:
    version: int
    files: list[tuple[str, Path]] = field(default_factory=list)     # (path relative to the workspace, source)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def load_config(path: Path) -> tuple[Config | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=cr.ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    if not isinstance(data, dict):
        return None, [f"{path}: phải là một mapping"]
    errors: list[str] = []

    def text(key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}: thiếu hoặc không phải chuỗi")
            return ""
        return value.strip()

    def names(key: str) -> list[str]:
        value = data.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
            errors.append(f"{key}: phải là danh sách chuỗi, không rỗng")
            return []
        return [v.strip() for v in value]

    gate = data.get("gate")
    if not isinstance(gate, int) or isinstance(gate, bool) or not 0 <= gate <= 10:
        errors.append("gate: phải là số 0 đến 10")
        gate = 10
    config = Config(gate, text("archive_dir"), names("snapshot"), text("changelog"), text("previous_design"), names("levels"), text("promote_prefix"))
    for key, value in [("archive_dir", config.archive_dir), ("changelog", config.changelog), ("previous_design", config.previous_design), ("promote_prefix", config.promote_prefix)] + [("snapshot", s) for s in config.snapshot]:
        parts = Path(value).parts
        if Path(value).is_absolute() or ".." in parts or value.startswith(("/", "\\")):
            errors.append(f"{key}: \"{value}\" phải là đường dẫn tương đối, không có `..`")
    if re.search(r"[\\/]", config.promote_prefix):
        errors.append("promote_prefix: là tiền tố tên file, không có dấu gạch chéo")
    if len(set(config.snapshot)) != len(config.snapshot):
        errors.append("snapshot: có mục trùng")
    if any(entry == config.archive_dir or entry.startswith(config.archive_dir + "/") for entry in config.snapshot):
        errors.append("snapshot: không được chụp chính thư mục archive")
    return (None, errors) if errors else (config, [])


# --- version ---------------------------------------------------------------------------------------------------------------

def existing_versions(archive: Path) -> list[int]:
    if not archive.is_dir():
        return []
    return sorted(int(m.group(1)) for p in archive.iterdir() if (m := VERSION_DIR.fullmatch(p.name)))


def parse_version(text: str) -> int | None:
    match = re.fullmatch(r"[vV]?([0-9]+)", text.strip())
    return int(match.group(1)) if match and int(match.group(1)) > 0 else None


def changelog_has(text: str, version: int) -> bool:
    return re.search(rf"^##\s+v{version}(?![0-9A-Za-z])", text, re.MULTILINE) is not None


# --- snapshot --------------------------------------------------------------------------------------------------------------

def plan_snapshot(workspace: Path, cfg: Config, release: Release) -> None:
    seen: dict[str, Path] = {}
    for entry in cfg.snapshot:
        target = workspace / entry
        if target.is_dir() and not target.is_symlink():
            found = sorted(p for p in target.rglob("*") if p.is_file() or p.is_symlink())
        elif target.is_file() and not target.is_symlink():
            found = [target]
        elif target.is_symlink():
            release.problems.append(f"{entry} là liên kết tượng trưng: không chụp (thay bằng thư mục hay file thật)")
            continue
        else:
            release.notes.append(f"không có {entry} trong workspace: không chụp gì")
            continue
        for path in found:
            rel = path.relative_to(workspace).as_posix()
            if path.is_symlink():
                release.problems.append(f"{rel} là liên kết tượng trưng: không chụp (thay bằng file thật)")
                continue
            seen.setdefault(rel, path)
    release.files = sorted(seen.items())


def snapshot_to(release: Release, workspace: Path, archive: Path) -> tuple[Path | None, list[str]]:
    """Copy the files into a temporary folder next to the final one and read each back; (the folder, failures)."""
    final = archive / f"v{release.version}"
    temp = archive / f"v{release.version}.partial"
    failures: list[str] = []
    try:
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True)
        for rel, source in release.files:
            dest = temp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            dest.write_bytes(data)
            if dest.read_bytes() != data:
                failures.append(f"{rel}: đọc lại khác bản vừa chụp")
        if not failures:
            os.replace(temp, final)
            return final, []
    except OSError as error:
        failures.append(str(error))
    shutil.rmtree(temp, ignore_errors=True)
    return None, failures


# --- the changelog entry ---------------------------------------------------------------------------------------------------

def decisions_lines(workspace: Path, wcfg: cw.Config) -> list[str]:
    text = cw.read(workspace / wcfg.decision_log)
    if text is None:
        return []
    header, rows = cw.table(text, "ID")
    cols = {key: cw.column(header, *words) for key, words in (("id", ("ID",)), ("question", ("Câu hỏi",)), ("gate", ("Gate",)), ("status", ("Trạng thái",)), ("quote", ("Người dùng nói",)), ("date", ("Ngày",)))}
    if not header or None in cols.values():
        return []
    d_re = cw.IDS.id_re(["D"])
    lines = []
    for _, cells in rows:
        cells = cells + [""] * (len(header) - len(cells))
        row = {key: cw.clean(cells[index]) for key, index in cols.items()}
        if not d_re.fullmatch(row["id"]) or cw.norm(row["status"]) != cw.norm(wcfg.decision_resolved):
            continue
        choice = re.search(rf"(?<![\w-]){re.escape(row['id'])}(?![\w-])\s*:\s*{re.escape(wcfg.choose_word)}\s+([^\s,;.]+)", row["quote"], re.IGNORECASE)
        lines.append(f"- {row['id']} ({row['gate']}): {row['question']} -> {choice.group(1) if choice else row['quote']}; người dùng nói \"{row['quote']}\", {row['date']}")
    return lines


def accepted_lines(workspace: Path, wcfg: cw.Config) -> list[str]:
    text = cw.read(workspace / wcfg.risk_acceptance)
    if text is None:
        return []
    header, rows = cw.table(text, "ID")
    cols = {key: cw.column(header, *words) for key, words in (("id", ("ID",)), ("score", ("Điểm",)), ("quote", ("Người dùng nói",)), ("date", ("Ngày",)))}
    if not header or None in cols.values():
        return []
    r_re = cw.IDS.id_re(["R"])
    lines = []
    for _, cells in rows:
        cells = cells + [""] * (len(header) - len(cells))
        row = {key: cw.clean(cells[index]) for key, index in cols.items()}
        if r_re.fullmatch(row["id"]) and not cw.PLACEHOLDER.search(row["score"]):
            lines.append(f"- {row['id']} ({row['score']} điểm): người dùng nói \"{row['quote']}\", {row['date']}")
    return lines


def tree(root: Path, skip: str, problems: list[str], label: str) -> dict[str, str]:
    """{path relative to root: sha256} of every file under root, except `skip` at its top (the changelog)."""
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == skip:
            continue
        if path.is_symlink():
            problems.append(f"{label}/{rel} là liên kết tượng trưng: không so sánh (thay bằng file thật)")
        elif path.is_file():
            found[rel] = cr.sha256_file(path)
    return found


def promote_problems(workspace: Path, cfg: Config, current: dict[str, str]) -> list[str]:
    """Why architecture/ is not what the user approved: no report of a successful promote of the gate, or a file of it that was
    edited, deleted or added since (`current` = hashes of architecture/ without the changelog)."""
    gate = f"G{cfg.gate}"
    recorded = None
    source = ""
    for path in cr.dated_reports(workspace / "checks", cfg.promote_prefix):
        blocks = [b for b in cr.parse_promoted(path.read_text(encoding=cr.ENCODING, errors="replace")) if b.gate == gate]
        if blocks:
            recorded, source = blocks[-1], path.name
            break
    if recorded is None:
        return [f"promote: không có báo cáo checks/{cfg.promote_prefix}-<ngày>.md ghi một lần chép {gate} thành công: chạy promote_drafts.py --gate {gate} trước"]
    problems = []
    for rel, digest in sorted(recorded.files.items()):
        if rel not in current:
            problems.append(f"promote: architecture/{rel} có trong lần chép {gate} ({source}) nhưng không còn")
        elif current[rel] != digest:
            problems.append(f"promote: architecture/{rel} khác bản đã chép ở lần chép {gate} ({source}): sửa tay sau khi promote?")
    for rel in sorted(set(current) - set(recorded.files)):
        problems.append(f"promote: architecture/{rel} không thuộc lần chép {gate} ({source}): file thừa")
    return problems


def compare_lines(previous: dict[str, str], current: dict[str, str]) -> list[str]:
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(rel for rel in set(previous) & set(current) if previous[rel] != current[rel])
    same = len(set(previous) & set(current)) - len(changed)
    lines = []
    for title, items in (("Thêm", added), ("Đổi", changed), ("Xóa", removed)):
        lines.append(f"- {title} ({len(items)}):" + ("" if items else " không có"))
        lines += [f"  - `{rel}`" for rel in items]
    return lines + [f"- Không đổi: {same} file"]


def entry_text(version: int, today: str, level: str, quote: str, decisions: list[str], accepted: list[str], comparison: list[str] | None) -> str:
    lines = [f"## v{version} ({today})", "", f"- Mức áp dụng: {level}", f"- Phát hành khi người dùng duyệt: \"{quote}\"", f"- Bản chụp: `archive/v{version}/`", "", "### Quyết định đã chốt", ""]
    lines += decisions or ["- không có"]
    lines += ["", "### Rủi ro đã chấp nhận", ""] + (accepted or ["- không có"])
    if comparison is not None:
        lines += ["", "### So với bản trước (`inputs/previous-design/`)", ""] + comparison
    return "\n".join(lines) + "\n"


def with_entry(existing: str | None, entry: str) -> str:
    """The changelog with `entry` first: before the first `## ` entry, after the title; a new file gets a title."""
    if existing is None or not existing.strip():
        return "# CHANGELOG\n\n" + entry
    eol = "\r\n" if "\r\n" in existing else "\n"
    text = existing.replace("\r\n", "\n")
    match = re.search(r"^## ", text, re.MULTILINE)
    if match:
        text = text[:match.start()] + entry + "\n" + text[match.start():]
    else:
        text = text.rstrip("\n") + "\n\n" + entry
    return text.replace("\n", eol)


def write_changelog(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".partial")
    temp.write_text(text, encoding=cr.ENCODING, newline="")
    os.replace(temp, path)


# --- report ----------------------------------------------------------------------------------------------------------------

def report_lines(version: int, problems: list[str], failures: list[str], release: Release, warnings: list[str], changelog_path: Path, level: str) -> list[str]:
    done = not problems and not failures
    lines = [f"## v{version}: " + ("đã phát hành" if done else "TỪ CHỐI" if problems else "LỖI khi phát hành"), ""]
    lines += ["### Lý do từ chối", ""] + [f"- {p}" for p in problems] + [""] if problems else []
    lines += ["### Lỗi", ""] + [f"- {f}" for f in failures] + [""] if failures else []
    lines += ["### Bản chụp", "", f"`archive/v{version}/`: {len(release.files)} file" + ("" if done else " (kế hoạch, chưa chụp)"), f"Changelog: `{changelog_path}`; mức {level}", ""]
    if warnings or release.notes:
        lines += ["### Ghi chú", ""] + [f"- cảnh báo: {w}" for w in warnings] + [f"- {n}" for n in release.notes] + [""]
    return lines


def append_report(workspace: Path, today: str, lines: list[str]) -> Path:
    target = workspace / "checks" / f"archive-{today}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding=cr.ENCODING, newline="") if target.is_file() else f"# archive_release {today}\n"
    target.write_text(existing.rstrip("\n") + "\n\n" + "\n".join(lines), encoding=cr.ENCODING, newline="")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", help="the version to release, N or vN (default: the next after the highest archive/vN)")
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--architecture", type=Path, help="default: architecture/ next to the workspace")
    parser.add_argument("--dry-run", action="store_true", help="check everything and show what would be done; write nothing")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="what to snapshot (default: core/data/archive.yaml)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    wanted = None
    if args.version is not None:
        wanted = parse_version(args.version)
        if wanted is None:
            parser.error("--version phải là số nguyên dương, N hoặc vN")
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a workspace: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    architecture = (args.architecture or workspace.parent / "architecture").resolve()
    if architecture == workspace or workspace in architecture.parents or architecture in workspace.parents:
        print(f"architecture/ ({architecture}) phải nằm ngoài workspace và không chứa nó", file=sys.stderr)
        return 2
    cfg, config_errors = load_config(args.config.resolve())
    wcfg, wcfg_errors = cw.load_config(cw.DEFAULT_CONFIG)
    if cfg is None or wcfg is None:
        for error in config_errors + wcfg_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()

    archive = workspace / cfg.archive_dir
    version = wanted if wanted is not None else max(existing_versions(archive), default=0) + 1
    release = Release(version)
    problems = release.problems
    state_path = workspace / "state.md"
    state = state_path.read_text(encoding=cr.ENCODING, errors="replace") if state_path.is_file() else ""
    if state_path.is_file():
        problems += [f"duyệt: {p}" for p in approvals.problems_up_to(state, cfg.gate)]
    else:
        problems.append("duyệt: không có state.md")
    if not architecture.is_dir():
        problems.append(f"chưa có architecture/ ({architecture}): chạy promote_drafts.py --gate G{cfg.gate} trước")
    final = archive / f"v{version}"
    if final.exists() or final.is_symlink():
        problems.append(f"{cfg.archive_dir}/v{version} đã có: không ghi đè (bỏ --version để lấy số kế tiếp, hoặc đổi tên bản cũ)")
    changelog_path = architecture / cfg.changelog
    existing_log = None
    if changelog_path.is_file():
        existing_log = changelog_path.read_text(encoding=cr.ENCODING, errors="replace", newline="")
        if changelog_has(existing_log, version):
            problems.append(f"{cfg.changelog} đã có mục v{version}: không thêm trùng")
    elif changelog_path.exists():
        problems.append(f"{changelog_path} có nhưng không phải file")
    plan_snapshot(workspace, cfg, release)

    quote = approvals.clean_quote(approvals.gate_rows(state).get(cfg.gate, {}).get("quote", "")) if state else ""
    level = cw.state_field(state, "Mức áp dụng")
    warnings: list[str] = []
    if level not in cfg.levels:
        warnings.append(f"state.md: Mức áp dụng \"{level}\" không phải {', '.join(cfg.levels)}; changelog ghi \"chưa ghi\"")
        level = "chưa ghi"
    current: dict[str, str] = {}
    if architecture.is_dir():
        current = tree(architecture, cfg.changelog, problems, "architecture")
        problems += promote_problems(workspace, cfg, current)

    comparison = None
    previous = workspace / cfg.previous_design
    if previous.is_dir() and architecture.is_dir():
        comparison = compare_lines(tree(previous, cfg.changelog, problems, cfg.previous_design), current)

    failures: list[str] = []
    if not problems and not args.dry_run:
        entry = entry_text(version, today, level, quote, decisions_lines(workspace, wcfg), accepted_lines(workspace, wcfg), comparison)
        made, failures = snapshot_to(release, workspace, archive)
        if made is not None:
            try:
                write_changelog(changelog_path, with_entry(existing_log, entry))
            except OSError as error:
                failures.append(f"{cfg.changelog}: {error}")
                shutil.rmtree(made, ignore_errors=True)
                changelog_path.with_name(changelog_path.name + ".partial").unlink(missing_ok=True)
    lines = report_lines(version, problems, failures, release, warnings, changelog_path, level)
    target = None if args.dry_run else append_report(workspace, today, lines)

    if problems:
        print(f"archive_release v{version}: TỪ CHỐI, {len(problems)} điều kiện chưa đủ" + (f"; báo cáo: {target}" if target else ""))
        for problem in problems[:SHOWN]:
            print(f"error: {problem}")
        if len(problems) > SHOWN:
            print(f"error: … và {len(problems) - SHOWN} điều kiện nữa (xem báo cáo)")
        return 1
    if failures:
        print(f"archive_release v{version}: LỖI khi phát hành; báo cáo: {target}")
        for failure in failures:
            print(f"error: {failure}")
        return 1
    verb = "sẽ chụp (--dry-run)" if args.dry_run else "đã chụp"
    print(f"archive_release v{version}: {verb} {len(release.files)} file -> {cfg.archive_dir}/v{version}/; {cfg.changelog}: " + ("sẽ thêm" if args.dry_run else "đã thêm") + f" mục v{version}" + (f"; báo cáo: {target}" if target else ""))
    for warning in warnings:
        print(f"warning: {warning}")
    for note in release.notes:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
