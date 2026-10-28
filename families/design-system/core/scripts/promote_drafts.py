# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Copy the drafts of a gate the user approved from `.agent-workspace/drafts/` to `architecture/` (the only writer of architecture/).

It refuses, and says exactly what is missing, unless all of this holds:
- state.md says the gate is approved the way rule 2 asks (status `đã duyệt`, the user's words `Gn: duyệt`, a date) and so is every
  gate before it (approvals.py);
- every script the gate needs (data/gates.yaml, equal to the "Script" line of the gate in stages.md) left a report in `checks/`
  that is the latest one, says it was clean, is for this gate (and, for calc_capacity.py, a mode that counts), and is not stale:
  the sha256 of every file the report lists must equal the file now, and no file in its scope may have appeared since
  (checkreport.py; the age of the report is never looked at).

What is copied is the entries of the gate in `GATE_ENTRIES` of check_profile.py (a part is copied whole, a file alone; an entry
the project profile dropped is not there to copy). G10 copies every part again plus `drafts/README.md`: whatever changed since
the gate of its part is updated, so architecture/ ends equal to the released drafts. A file that exists in architecture/ but no
longer in the drafts is only reported (never deleted). `architecture/` is next to the workspace by default.

Exit 0 done (or --dry-run fine), 1 refused or a copy failed, 2 wrong arguments. The run is appended to
`<workspace>/checks/promote-<date>.md` (not with --dry-run, which writes nothing); a run that copied ends with a block listing the
sha256 of every file architecture/ holds for the gate, which archive_release.py compares with architecture/ before it releases.

    uv run promote_drafts.py --gate Gn [--workspace DIR] [--architecture DIR] [--dry-run] [--config FILE]
"""

import argparse
import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import approvals  # noqa: E402
import checkreport as cr  # noqa: E402
import check_profile as cp  # noqa: E402

README = "README.md"
SHOWN = 25


@dataclass
class Plan:
    files: list[tuple[str, Path]] = field(default_factory=list)      # (path relative to drafts/, source)
    folders: list[str] = field(default_factory=list)                 # entries that are folders (for the orphan scan)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def entries_of(gate: int) -> tuple[str, ...]:
    """What the gate copies: its entries, or at G10 every entry of G0-G9 and the README."""
    if gate < 10:
        return cp.GATE_ENTRIES[gate]
    return tuple(dict.fromkeys(entry for g in range(10) for entry in cp.GATE_ENTRIES[g])) + (README,)


def gate_of(rel: str) -> int | None:
    """The gate whose entries cover this path (the earliest), None when no entry does."""
    for gate in range(10):
        if any(rel == entry or rel.startswith(entry + "/") for entry in cp.GATE_ENTRIES[gate]):
            return gate
    return None


def plan_files(drafts: Path, gate: int) -> Plan:
    plan = Plan()
    seen: dict[str, Path] = {}
    for entry in entries_of(gate):
        target = drafts / entry
        if target.is_dir():
            plan.folders.append(entry)
            found = sorted(p for p in target.rglob("*") if p.is_file() or p.is_symlink())
        elif target.is_file() or target.is_symlink():
            found = [target]
        else:
            if entry == README:
                plan.problems.append(f"thiếu drafts/{README} (mục lục, phiên bản, mức áp dụng): G10 phát hành kèm nó")
            else:
                plan.notes.append(f"không có {entry} trong drafts/ (phần bỏ theo hồ sơ dự án, hoặc chưa viết): không chép gì")
            continue
        for path in found:
            rel = path.relative_to(drafts).as_posix()
            if path.is_symlink():
                plan.problems.append(f"drafts/{rel} là liên kết tượng trưng: không chép (thay bằng file thật)")
                continue
            seen.setdefault(rel, path)
    plan.files = sorted(seen.items())
    if not plan.files and not plan.problems:
        plan.notes.append("không có file nào để chép ở gate này")
    return plan


def orphans(plan: Plan, architecture: Path) -> list[str]:
    """Files in architecture/ under a copied folder that the drafts no longer have."""
    wanted = {rel for rel, _ in plan.files}
    found = []
    for entry in plan.folders:
        folder = architecture / entry
        for path in sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []:
            rel = path.relative_to(architecture).as_posix()
            if rel not in wanted:
                found.append(rel)
    return found


def classify(plan: Plan, architecture: Path, gate: int) -> list[tuple[str, str, Path]]:
    """(rel, action, source): `mới`, `ghi đè` (the destination differs) or `không đổi`."""
    rows = []
    for rel, source in plan.files:
        dest = architecture / rel
        if not dest.is_file():
            action = "mới"
        elif cr.sha256_file(dest) == cr.sha256_file(source):
            action = "không đổi"
        else:
            earlier = gate_of(rel)
            action = "ghi đè" + (f" (phần của G{earlier}, đổi sau khi gate đó qua)" if gate == 10 and earlier is not None else "")
        rows.append((rel, action, source))
    return rows


def copy_all(rows: list[tuple[str, str, Path]], architecture: Path) -> list[str]:
    """Copy what is new or different and read it back; the failures."""
    failures = []
    for rel, action, source in rows:
        if action == "không đổi":
            continue
        dest = architecture / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            dest.write_bytes(data)
            if dest.read_bytes() != data:
                failures.append(f"{rel}: đọc lại khác bản vừa ghi")
        except OSError as error:
            failures.append(f"{rel}: {error}")
    return failures


def report_lines(gate: int, accepted: list[str], rows: list[tuple[str, str, Path]], problems: list[str], failures: list[str], warnings: list[str], notes: list[str], architecture: Path, promoted: dict[str, str] | None = None) -> list[str]:
    done = not problems and not failures
    lines = [f"## G{gate}: " + ("đã chép" if done else "TỪ CHỐI" if problems else "LỖI khi chép"), "", f"Đích: `{architecture}`", ""]
    lines += ["### Lý do từ chối", ""] + [f"- {p}" for p in problems] + [""] if problems else []
    lines += ["### Lỗi khi chép", ""] + [f"- {f}" for f in failures] + [""] if failures else []
    lines += ["### Báo cáo được chấp nhận", ""] + ([f"- {a}" for a in accepted] or ["- không có"]) + [""]
    counts = {kind: sum(1 for _, a, _ in rows if a.startswith(kind)) for kind in ("mới", "ghi đè", "không đổi")}
    lines += ["### File", "", f"{len(rows)} file: {counts['mới']} mới, {counts['ghi đè']} ghi đè, {counts['không đổi']} không đổi" + ("" if done else " (kế hoạch, chưa chép)"), ""]
    lines += [f"- `{rel}`: {action}" for rel, action, _ in rows if action != "không đổi"] or ["- không có file đổi"]
    if warnings or notes:
        lines += ["", "### Ghi chú", ""] + [f"- cảnh báo: {w}" for w in warnings] + [f"- {n}" for n in notes]
    if promoted:
        lines += cr.render_promoted(gate, promoted).split("\n")
    return lines + [""]


def append_report(workspace: Path, today: str, lines: list[str]) -> Path:
    target = workspace / "checks" / f"promote-{today}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding=cr.ENCODING, newline="") if target.is_file() else f"# promote_drafts {today}\n"
    target.write_text(existing.rstrip("\n") + "\n\n" + "\n".join(lines), encoding=cr.ENCODING, newline="")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gate", required=True, help="the approved gate to copy, G0 ... G10")
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--architecture", type=Path, help="default: architecture/ next to the workspace")
    parser.add_argument("--dry-run", action="store_true", help="check everything and show what would be copied; write nothing")
    parser.add_argument("--config", type=Path, default=cr.DEFAULT_CONFIG, help="scripts each gate needs (default: core/data/gates.yaml)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    match = re.fullmatch(r"[Gg](10|[0-9])", args.gate)
    if not match:
        parser.error("--gate phải có dạng G0 đến G10")
    gate = int(match.group(1))
    workspace = args.workspace.resolve()
    drafts = workspace / "drafts"
    if not workspace.is_dir() or not drafts.is_dir():
        print(f"not a workspace with drafts/: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    architecture = (args.architecture or workspace.parent / "architecture").resolve()
    if architecture == workspace or workspace in architecture.parents or architecture in workspace.parents:
        print(f"architecture/ ({architecture}) phải nằm ngoài workspace và không chứa nó", file=sys.stderr)
        return 2
    config, config_errors = cr.load_config(args.config.resolve())
    if config is None:
        for error in config_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()

    problems: list[str] = []
    state = workspace / "state.md"
    if state.is_file():
        problems += [f"duyệt: {p}" for p in approvals.problems_up_to(state.read_text(encoding=cr.ENCODING, errors="replace"), gate)]
    else:
        problems.append("duyệt: không có state.md")
    report_problems, accepted = cr.gate_problems(workspace, gate, config)
    problems += report_problems
    plan = plan_files(drafts, gate)
    problems += plan.problems
    rows = classify(plan, architecture, gate)
    warnings = [f"{rel} có ở architecture/ nhưng không còn ở drafts/ (không xóa; xem có nên bỏ)" for rel in orphans(plan, architecture)]

    failures: list[str] = []
    if not problems and not args.dry_run:
        failures = copy_all(rows, architecture)
    promoted: dict[str, str] = {}
    if not problems and not failures and not args.dry_run:
        try:
            promoted = {rel: cr.sha256_file(architecture / rel) for rel, _, _ in rows}  # what architecture/ holds now: archive_release.py compares against it
        except OSError as error:
            failures.append(f"đọc lại architecture/ để ghi hash: {error}")
    lines = report_lines(gate, accepted, rows, problems, failures, warnings, plan.notes, architecture, promoted)
    target = None if args.dry_run else append_report(workspace, today, lines)

    changed = [(rel, action) for rel, action, _ in rows if action != "không đổi"]
    if problems:
        print(f"promote_drafts G{gate}: TỪ CHỐI, {len(problems)} điều kiện chưa đủ" + (f"; báo cáo: {target}" if target else ""))
        for problem in problems[:SHOWN]:
            print(f"error: {problem}")
        if len(problems) > SHOWN:
            print(f"error: … và {len(problems) - SHOWN} điều kiện nữa (xem báo cáo)")
        return 1
    verb = "sẽ chép (--dry-run)" if args.dry_run else "đã chép"
    print(f"promote_drafts G{gate}: {verb} {len(changed)} file ({sum(1 for _, a in changed if a == 'mới')} mới, {sum(1 for _, a in changed if a.startswith('ghi đè'))} ghi đè), {len(rows) - len(changed)} không đổi -> {architecture}" + (f"; báo cáo: {target}" if target else ""))
    for rel, action in changed[:SHOWN]:
        print(f"  {action}: {rel}")
    if len(changed) > SHOWN:
        print(f"  … và {len(changed) - SHOWN} file nữa")
    for warning in warnings[:SHOWN]:
        print(f"warning: {warning}")
    for note in plan.notes:
        print(f"note: {note}")
    for failure in failures:
        print(f"error: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
