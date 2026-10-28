# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check that the parts of a design trace to each other (default: `.agent-workspace/drafts/`).

Blocking errors (exit 1):
- `fr-without-flow` (from G6): an FR (defined by a heading or a table first cell, as check_links.py reads definitions) that no
  single-flow file `04-flows/FL-*.md` mentions;
- `api-not-in-backend` (from G7): an `API-xx` that a file of `05-frontend/` mentions (a call) but no file of `06-backend/` defines;
- `data-ref-missing` (from G7): a `TBL-`, `BKT-` or `EVT-` ID that a file of `04-flows/` mentions but no file of `07-data/` defines;
- `id-undefined` (from G6; SVC, API, EVT, TBL, BKT from G7, when the backend and data are designed): an ID of data/ids.yaml that a
  file mentions and that is defined nowhere (not in the drafts, not in decisions/decision-log.md for D, questions.md for CH,
  inputs/ui-design/ for SCR). Placeholder names (`FR-xx`) are not IDs. This is the check check_links.py leaves to this script.
No `05-frontend/` (the project profile dropped it) skips the API check; `07-data/` is part of every level. Mentions inside code fences count
(the sequence diagrams of the flows are where tables, buckets and events are named); link targets and file names do not.
Paths, kinds and gates are in data/trace.yaml; the ID prefixes in data/ids.yaml.

The report is also written to `<workspace>/checks/trace-<date>.md`, ending with the sha256 of every file checked (checkreport.py).

    uv run check_trace.py --gate Gn [--workspace DIR] [--root DIR] [--config FILE]
"""

import argparse
import datetime
import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_links as cl  # noqa: E402
import checkreport as cr  # noqa: E402
import idlist  # noqa: E402

ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CORE / "data" / "trace.yaml"
IDS = idlist.load()
ID_RE = IDS.id_re()
SHOWN_ERRORS = 25


@dataclass
class Config:
    requirement_kind: str
    flows_dir: str
    flow_files: str
    frontend_dir: str
    backend_dir: str
    api_kind: str
    data_dir: str
    data_kinds: list[str]
    requirement_from_gate: int
    cross_from_gate: int
    undefined_from_gate: dict[str, int]
    sources: list[tuple[str, list[str]]]


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"`{self.path}:{self.line}` [{self.code}] {self.message}"


@dataclass
class Result:
    errors: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_config(path: Path) -> tuple[Config | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    if not isinstance(data, dict):
        return None, [f"{path}: phải là một mapping"]
    errors: list[str] = []

    def text(key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.split("/"):
            errors.append(f"{key}: phải là chuỗi (đường dẫn tương đối) không rỗng")
            return ""
        return value.strip("/")

    def number(key: str, source=None) -> int:
        value = (source if source is not None else data).get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
            errors.append(f"{key}: phải là số gate 0-10")
            return 0
        return value

    def kind(key: str) -> str:
        value = data.get(key)
        if value not in IDS.kinds:
            errors.append(f"{key}: {value!r} không có trong data/ids.yaml")
            return ""
        return value

    requirement_kind, api_kind = kind("requirement_kind"), kind("api_kind")
    data_kinds = data.get("data_kinds")
    if not isinstance(data_kinds, list) or not data_kinds or any(k not in IDS.kinds for k in data_kinds):
        errors.append("data_kinds: phải là danh sách tiền tố có trong data/ids.yaml")
        data_kinds = []
    undefined = data.get("undefined_from_gate")
    gates: dict[str, int] = {}
    if not isinstance(undefined, dict) or "default" not in undefined:
        errors.append("undefined_from_gate: phải có khóa default")
    else:
        for key in undefined:
            if key != "default" and key not in IDS.kinds:
                errors.append(f"undefined_from_gate.{key}: không có trong data/ids.yaml")
            gates[key] = number(key, undefined)
    sources: list[tuple[str, list[str]]] = []
    raw = data.get("sources")
    if not isinstance(raw, list):
        errors.append("sources: phải là danh sách")
        raw = []
    for item in raw:
        ok = (isinstance(item, dict) and isinstance(item.get("path"), str) and not item["path"].startswith("/") and ".." not in item["path"].split("/")
              and isinstance(item.get("kinds"), list) and item["kinds"] and all(k in IDS.kinds for k in item["kinds"]))
        if not ok:
            errors.append(f"sources: mỗi mục phải là {{path (tương đối), kinds (có trong data/ids.yaml)}}, gặp {item!r}")
        else:
            sources.append((item["path"].strip("/"), list(item["kinds"])))
    config = Config(
        requirement_kind, text("flows_dir"), text("flow_files"), text("frontend_dir"), text("backend_dir"), api_kind, text("data_dir"), list(data_kinds),
        number("requirement_from_gate"), number("cross_from_gate"), gates, sources,
    )
    return (None, errors) if errors else (config, [])


# --- reading ---------------------------------------------------------------------------------------------------------------

def mention_lines(doc: cl.Doc) -> dict[str, int]:
    """First line of every real ID the file mentions (link targets removed: a link to FL-001-x.md is not a mention of FL-001-x)."""
    found: dict[str, int] = {}
    for number, line in enumerate(doc.lines, start=1):
        stripped = cl.LINK_RE.sub(lambda m: m.group(0).split("](")[0] + "]", line)
        for ident in ID_RE.findall(stripped):
            if not IDS.is_placeholder(ident):
                found.setdefault(ident, number)
    return found


def under(doc: cl.Doc, folder: str) -> bool:
    return doc.rel == folder or doc.rel.startswith(folder + "/")


def defined_in(definitions: dict, ident: str, folder: str) -> bool:
    return any(under(doc, folder) for doc, _ in definitions.get(ident, []))


def source_files(workspace: Path, config: Config) -> list[Path]:
    """The files of `sources`: a folder means every file inside it."""
    found = []
    for rel, _ in config.sources:
        target = workspace / rel
        found += sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else ([target] if target.is_file() else [])
    return found


def external_definitions(workspace: Path | None, config: Config) -> set[str]:
    """IDs the files listed under `sources` define by mentioning them."""
    found: set[str] = set()
    if workspace is None:
        return found
    for rel, kinds in config.sources:
        target = workspace / rel
        files = sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else ([target] if target.is_file() else [])
        wanted = IDS.id_re(kinds)
        for path in files:
            found.update(i for i in wanted.findall(path.read_text(encoding=ENCODING, errors="replace")) if not IDS.is_placeholder(i))
    return found


# --- the checks ------------------------------------------------------------------------------------------------------------

def check(docs: list[cl.Doc], config: Config, gate: int, workspace: Path | None) -> Result:
    result = Result()
    reported: set[str] = set()  # IDs a more specific check already reports: not repeated as undefined
    definitions = {i: places for i, places in cl.effective_definitions(docs).items() if not IDS.is_placeholder(i)}
    mentions = {doc.rel: mention_lines(doc) for doc in docs}

    if gate >= config.requirement_from_gate:
        requirements = sorted(i for i in definitions if IDS.kind_of(i) == config.requirement_kind)
        flows = [d for d in docs if under(d, config.flows_dir) and fnmatch.fnmatch(Path(d.rel).name, config.flow_files)]
        if not requirements:
            result.errors.append(Finding(config.flows_dir, 1, "no-requirements", f"không có {config.requirement_kind}-xx nào được định nghĩa (heading hoặc ô đầu dòng bảng) trong bản nháp: không truy vết được"))
        for ident in requirements:
            if not any(ident in mentions[f.rel] for f in flows):
                doc, number = definitions[ident][0]
                result.errors.append(Finding(doc.rel, number, "fr-without-flow", f"{ident} không có luồng: không file {config.flows_dir}/{config.flow_files} nào nhắc tới"))
        result.notes.append(f"{config.requirement_kind}: {len(requirements)} định nghĩa, {sum(1 for i in requirements if any(i in mentions[f.rel] for f in flows))} có luồng ({len(flows)} file luồng)")

    if gate >= config.cross_from_gate:
        frontend = [d for d in docs if under(d, config.frontend_dir)]
        if frontend:
            calls = {}
            for doc in frontend:
                for ident, number in mentions[doc.rel].items():
                    if IDS.kind_of(ident) == config.api_kind:
                        calls.setdefault(ident, (doc.rel, number))
            for ident, (rel, number) in sorted(calls.items()):
                if not defined_in(definitions, ident, config.backend_dir):
                    elsewhere = [d.rel for d, _ in definitions.get(ident, [])]
                    where = f" (chỉ định nghĩa ở {', '.join(elsewhere)})" if elsewhere else ""
                    reported.add(ident)
                    result.errors.append(Finding(rel, number, "api-not-in-backend", f"frontend gọi {ident} nhưng {config.backend_dir}/ không định nghĩa nó{where}"))
            result.notes.append(f"{config.api_kind} frontend gọi: {len(calls)}")
        else:
            result.notes.append(f"bỏ qua kiểm API: không có thư mục {config.frontend_dir}/")
        seen = {}
        for doc in (d for d in docs if under(d, config.flows_dir)):
            for ident, number in mentions[doc.rel].items():
                if IDS.kind_of(ident) in config.data_kinds:
                    seen.setdefault(ident, (doc.rel, number))
        for ident, (rel, number) in sorted(seen.items()):
            if not defined_in(definitions, ident, config.data_dir):
                elsewhere = [d.rel for d, _ in definitions.get(ident, [])]
                where = f" (chỉ định nghĩa ở {', '.join(elsewhere)})" if elsewhere else ""
                reported.add(ident)
                result.errors.append(Finding(rel, number, "data-ref-missing", f"luồng nhắc {ident} nhưng {config.data_dir}/ không định nghĩa nó{where}"))
        result.notes.append(f"{'/'.join(config.data_kinds)} luồng nhắc: {len(seen)}")

    external = external_definitions(workspace, config)
    first: dict[str, tuple[str, int]] = {}
    files: dict[str, int] = {}
    for doc in docs:
        for ident, number in mentions[doc.rel].items():
            first.setdefault(ident, (doc.rel, number))
            files[ident] = files.get(ident, 0) + 1
    undefined = 0
    for ident in sorted(first):
        kind = IDS.kind_of(ident)
        if gate < config.undefined_from_gate.get(kind, config.undefined_from_gate["default"]):
            continue
        if ident in definitions or ident in external or ident in reported:
            continue
        undefined += 1
        rel, number = first[ident]
        extra = f", và {files[ident] - 1} file khác" if files[ident] > 1 else ""
        result.errors.append(Finding(rel, number, "id-undefined", f"{ident} được nhắc tới (từ đây{extra}) mà không được định nghĩa ở đâu"))
    result.notes.append(f"ID được nhắc: {len(first)}, chưa định nghĩa: {undefined}")
    result.errors.sort(key=lambda f: (f.code, f.path, f.line))
    return result


def report(root: Path, gate: int, result: Result, count: int, today: str) -> str:
    lines = [f"# check_trace {today}", "", f"Quét `{root}` ở G{gate}: {count} file, {len(result.errors)} lỗi chặn.", ""]
    lines += ["## Số liệu", ""] + [f"- {note}" for note in result.notes] + [""]
    lines += ["## Lỗi chặn", ""] + ([f"- {f.render()}" for f in result.errors] or ["- không có"]) + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--root", type=Path, help="folder to scan (default: <workspace>/drafts)")
    parser.add_argument("--gate", required=True, help="the gate being checked, G0-G10: decides which checks run")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="paths, kinds, gates (default: core/data/trace.yaml)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    match = re.fullmatch(r"G(\d{1,2})", args.gate)
    if not match or int(match.group(1)) > 10:
        parser.error("--gate phải có dạng G0 đến G10")
    gate = int(match.group(1))
    workspace = args.workspace.resolve()
    root = (args.root or workspace / "drafts").resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    config, config_errors = load_config(args.config.resolve())
    if config is None:
        for error in config_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    docs = cl.load(root)
    files = cr.hash_files(workspace, [*sorted(root.rglob("*.md")), *(source_files(workspace, config) if workspace.is_dir() else [])])  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    result = check(docs, config, gate, workspace if workspace.is_dir() else None)
    text = report(root, gate, result, len(docs), today) + cr.render("check_trace.py", not result.errors, files, f"G{gate}")
    target = workspace / "checks" / f"trace-{today}.md"
    if workspace.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=ENCODING, newline="\n")
    print(f"check_trace G{gate}: {len(docs)} file, {len(result.errors)} lỗi chặn" + (f"; báo cáo: {target}" if workspace.is_dir() else ""))
    for note in result.notes:
        print(f"  {note}")
    for finding in result.errors[:SHOWN_ERRORS]:
        print(f"error: {finding.render()}")
    if len(result.errors) > SHOWN_ERRORS:
        print(f"error: … và {len(result.errors) - SHOWN_ERRORS} lỗi nữa (xem báo cáo)")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
