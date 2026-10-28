# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check the state of the agent workspace at a gate (`.agent-workspace/`): is everything the gate needs closed, decided and consistent?

Blocking errors (exit 1), for the gate Gn being checked (default: "Giai đoạn hiện tại" of state.md):
- `task-open`: a task of `plan/tasks/` whose Gate is at or before Gn is not `đóng` (a task with no Gate or an unknown status is
  `task-malformed`);
- `decision-open`: a decision of `decisions/decision-log.md` at or before Gn without the user's decision: the status must be
  `đã quyết` (`làm lại` is still open), with the user's verbatim words `D-xxx: chọn <phương án>` and a date, matching the user
  block of `decision.md` (`decision-mismatch`, `decision-choice-*`); a `D-*` folder missing from the log is `decision-not-logged`;
- `risk-unresolved`: a risk of the register with 15 points or more that is neither `đã chấp nhận` nor `đã đóng`: a warning before
  G9, an error from G9;
- `acceptance-*`: the register and `risks/acceptance.md` must agree both ways: a risk of 15+ points marked `đã chấp nhận` has a row
  in acceptance.md (`acceptance-missing`), and every row there has a risk of the same score marked `đã chấp nhận` in the register,
  the user's words `R-xx: chấp nhận` and a date (`acceptance-orphan`, `-score`, `-status`, `-quote`, `-date`);
- `model-untested` / `model-unusable`: a model of the "Gán model" table of `models.md` whose catalogue row says `chưa thử` or
  `không dùng được`. The table is a log: only the rows of tasks that are not closed are checked (a row of a closed task stays as
  history; a task with no file in `plan/tasks/` counts as not closed). A model missing from the catalogue is only a warning;
- `spike-missing` (level XL, from G4): a required layer that has a folder in `stack/layers/` but no spike whose result is `đạt` on the
  current spec. Required layers: `data/spike.yaml` (data, messaging, backend, infrastructure) plus the layers under "Lớp cần spike"
  of `plan/plan.md`; tooling and third-party never. A required layer with no folder is a warning.

The report is also written to `<workspace>/checks/workspace-<date>.md`, ending with the sha256 of the workspace files it judges
(scope in data/gates.yaml). Words and thresholds: data/workspace.yaml.

    uv run check_workspace.py [--workspace DIR] [--gate Gn] [--config FILE]
"""

import argparse
import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkreport as cr  # noqa: E402
import detect_models as dm  # noqa: E402
import idlist  # noqa: E402
import run_spike as rs  # noqa: E402
import tally_votes as tv  # noqa: E402

ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CORE / "data" / "workspace.yaml"
IDS = idlist.load()
SHOWN = 25
GATE_RE = re.compile(r"G(10|[0-9])")
USER_BLOCK = re.compile(r"<!--\s*BEGIN:user\b.*?-->(.*?)<!--\s*END:user\s*-->", re.DOTALL)
PLACEHOLDER = re.compile(r"<[^<>]*>")


@dataclass
class Config:
    task_dir: str
    task_statuses: list[str]
    task_closed: str
    decision_log: str
    decision_dir: str
    decision_statuses: list[str]
    decision_resolved: str
    choose_word: str
    risk_register: str
    risk_acceptance: str
    risk_statuses: list[str]
    risk_handled: list[str]
    risk_accepted: str
    risk_threshold: int
    risk_block_from_gate: int
    accept_word: str
    risk_scale: int
    spike_from_gate: int
    spike_level: str
    plan_file: str
    plan_heading: str
    models_file: str
    assign_heading: str


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str
    blocking: bool = True

    def render(self) -> str:
        return f"`{self.path}:{self.line}` [{self.code}] {self.message}" if self.line else f"`{self.path}` [{self.code}] {self.message}"


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if not f.blocking]

    def add(self, path: str, line: int, code: str, message: str, blocking: bool = True) -> None:
        self.findings.append(Finding(path, line, code, message, blocking))


def load_config(path: Path) -> tuple[Config | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    if not isinstance(data, dict):
        return None, [f"{path}: phải là một mapping"]
    errors: list[str] = []

    def get(*keys, kind=str):
        value = data
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else None
        ok = isinstance(value, kind) and not isinstance(value, bool) and (value != "" if kind is str else True) and (len(value) > 0 if kind is list else True)
        if not ok or (kind is list and not all(isinstance(v, str) and v for v in value)):
            errors.append(f"{'.'.join(keys)}: thiếu hoặc sai kiểu")
            return kind()
        return value

    config = Config(
        get("tasks", "dir"), get("tasks", "statuses", kind=list), get("tasks", "closed"),
        get("decisions", "log"), get("decisions", "dir"), get("decisions", "statuses", kind=list), get("decisions", "resolved"), get("decisions", "choose_word"),
        get("risks", "register"), get("risks", "acceptance"), get("risks", "statuses", kind=list), get("risks", "handled", kind=list), get("risks", "accepted"),
        get("risks", "threshold", kind=int), get("risks", "block_from_gate", kind=int), get("risks", "accept_word"), get("risks", "scale", kind=int),
        get("spikes", "from_gate", kind=int), get("spikes", "level"), get("spikes", "plan_file"), get("spikes", "plan_heading"),
        get("models", "file"), get("models", "assign_heading"),
    )
    if not errors:
        if config.task_closed not in config.task_statuses:
            errors.append("tasks.closed phải nằm trong tasks.statuses")
        if config.decision_resolved not in config.decision_statuses:
            errors.append("decisions.resolved phải nằm trong decisions.statuses")
        if not set(config.risk_handled) <= set(config.risk_statuses) or config.risk_accepted not in config.risk_statuses:
            errors.append("risks.handled và risks.accepted phải nằm trong risks.statuses")
        if not 0 < config.risk_threshold <= config.risk_scale ** 2:
            errors.append("risks.threshold phải trong 1..scale²")
    return (None, errors) if errors else (config, [])


# --- reading ---------------------------------------------------------------------------------------------------------------

def norm(text: str) -> str:
    return re.sub(r"[`*_]", "", tv.nfc(text)).strip().casefold()


def clean(text: str) -> str:
    text = tv.nfc(text).strip()
    text = re.sub(r"^[`*]+|[`*]+$", "", text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    return text


def read(path: Path) -> str | None:
    return tv.read_text(path) if path.is_file() else None


def table(text: str, first_column: str = "") -> tuple[list[str], list[tuple[int, list[str]]]]:
    """(header cells, [(line number, cells)]) of the first markdown table whose header starts with `first_column`."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        header = tv.split_cells(line)
        nxt = lines[index + 1] if index + 1 < len(lines) else ""
        if not re.fullmatch(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*", nxt):
            continue
        if first_column and norm(header[0]) != norm(first_column):
            continue
        rows = []
        for number in range(index + 2, len(lines)):
            if not lines[number].lstrip().startswith("|"):
                break
            rows.append((number + 1, tv.split_cells(lines[number])))
        return header, rows
    return [], []


def column(header: list[str], *words: str) -> int | None:
    for index, cell in enumerate(header):
        if any(norm(word) in norm(cell) for word in words):
            return index
    return None


def state_field(state: str, label: str) -> str:
    match = re.search(rf"^\s*[-*]\s+\*\*{re.escape(label)}[^*]*\*\*\s*(.*)$", state, re.MULTILINE)
    return clean(match.group(1)) if match else ""


def user_field(block: str, label: str) -> str:
    return state_field(block, label)


def valid_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text.strip())
        return True
    except ValueError:
        return False


# --- the checks ------------------------------------------------------------------------------------------------------------

def check_tasks(workspace: Path, cfg: Config, gate: int, result: Result) -> None:
    folder = workspace / cfg.task_dir
    files = sorted(folder.glob("T-*.md")) if folder.is_dir() else []
    open_count = 0
    for path in files:
        rel = path.relative_to(workspace).as_posix()
        text = tv.read_text(path)
        gate_match = re.search(r"^\s*[-*]\s+\*\*Gate:?\*\*:?\s*(\S+)", text, re.MULTILINE)
        status = state_field(text, "Trạng thái")
        gate_text = gate_match.group(1).strip("`*") if gate_match else ""
        if not GATE_RE.fullmatch(gate_text):
            result.add(rel, 0, "task-malformed", f"dòng \"Gate:\" thiếu hoặc không phải G0-G10 (đang là \"{gate_text}\")")
            continue
        if norm(status) not in [norm(s) for s in cfg.task_statuses]:
            result.add(rel, 0, "task-malformed", f"dòng \"Trạng thái:\" phải là một trong {', '.join(cfg.task_statuses)} (đang là \"{status}\")")
            continue
        if int(GATE_RE.fullmatch(gate_text).group(1)) <= gate and norm(status) != norm(cfg.task_closed):
            open_count += 1
            result.add(rel, 0, "task-open", f"task của {gate_text} chưa đóng (trạng thái \"{status}\"); gate đang kiểm là G{gate}")
    result.notes.append(f"task: {len(files)} file, {open_count} chưa đóng (gate <= G{gate})")


def brief_info(directory: Path, workspace: Path) -> tuple[int | None, list[str]]:
    """(gate number, options) read from brief.md; (None, []) when it cannot be read."""
    text = read(directory / "brief.md")
    if text is None:
        return None, []
    data, _, _ = tv.parse_frontmatter(text)
    if not data:
        return None, []
    gate = GATE_RE.fullmatch(str(data.get("gate", "")))
    options = data.get("options")
    return (int(gate.group(1)) if gate else None), ([o for o in options if isinstance(o, str)] if isinstance(options, list) else [])


def check_decisions(workspace: Path, cfg: Config, gate: int, result: Result) -> None:
    log_rel = cfg.decision_log
    text = read(workspace / log_rel)
    d_re = IDS.id_re(["D"])
    logged: dict[str, tuple[int, dict[str, str]]] = {}
    if text is not None:
        header, rows = table(text, "ID")
        cols = {key: column(header, *words) for key, words in (("id", ("ID",)), ("gate", ("Gate",)), ("status", ("Trạng thái",)), ("quote", ("Người dùng nói",)), ("date", ("Ngày",)))}
        if header and None in (cols["id"], cols["gate"], cols["status"], cols["quote"], cols["date"]):
            result.add(log_rel, 0, "decision-log-malformed", "bảng cần các cột ID, Gate, Trạng thái, Người dùng nói (nguyên văn), Ngày")
            rows = []
        for number, cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            ident = clean(cells[cols["id"]])
            if not d_re.fullmatch(ident) or PLACEHOLDER.search(cells[cols["gate"]]):
                continue  # the empty or template row
            logged[ident] = (number, {key: clean(cells[index]) for key, index in cols.items()})
    elif any((workspace / cfg.decision_dir).glob("D-*/")):
        result.add(log_rel, 0, "decision-log-missing", "có thư mục quyết định nhưng không có nhật ký quyết định")

    seen_dirs: dict[str, Path] = {}
    folder = workspace / cfg.decision_dir
    for path in sorted(folder.glob("D-*")) if folder.is_dir() else []:
        match = re.match(r"(D-[A-Za-z0-9_]+)(?:-|$)", path.name)
        if path.is_dir() and match:
            seen_dirs[match.group(1)] = path

    due = 0
    for ident, (number, row) in sorted(logged.items()):
        gate_match = GATE_RE.fullmatch(row["gate"])
        if not gate_match:
            result.add(log_rel, number, "decision-log-malformed", f"{ident}: cột Gate phải là G0-G10 (đang là \"{row['gate']}\")")
            continue
        if int(gate_match.group(1)) > gate:
            continue
        due += 1
        status = norm(row["status"])
        if status not in [norm(s) for s in cfg.decision_statuses]:
            result.add(log_rel, number, "decision-open", f"{ident}: trạng thái \"{row['status']}\" không nằm trong {', '.join(cfg.decision_statuses)}")
            continue
        if status != norm(cfg.decision_resolved):
            hint = ": người dùng yêu cầu làm lại, brief mới chưa có quyết định" if status == norm("làm lại") else ""
            result.add(log_rel, number, "decision-open", f"{ident} chưa có quyết định của người dùng (trạng thái \"{row['status']}\"{hint})")
            continue
        quote_re = re.compile(rf"(?<![\w-]){re.escape(ident)}(?![\w-])\s*:\s*{re.escape(cfg.choose_word)}\s+([^\s,;.]+)", re.IGNORECASE)
        quote = quote_re.search(row["quote"])
        if not quote:
            result.add(log_rel, number, "decision-open", f"{ident} ghi `{cfg.decision_resolved}` nhưng nguyên văn của người dùng không có dạng \"{ident}: {cfg.choose_word} <phương án>\" (đang là \"{row['quote']}\")")
            continue
        if not valid_date(row["date"]):
            result.add(log_rel, number, "decision-open", f"{ident} thiếu ngày hợp lệ (YYYY-MM-DD), đang là \"{row['date']}\"")
        chosen = quote.group(1)
        directory = seen_dirs.get(ident)
        if directory is None:
            result.add(log_rel, number, "decision-mismatch", f"{ident} đã quyết nhưng không có thư mục {cfg.decision_dir}/{ident}-<tên>/")
            continue
        rel_decision = f"{directory.relative_to(workspace).as_posix()}/decision.md"
        decision = read(directory / "decision.md")
        block = USER_BLOCK.search(decision) if decision else None
        if not block:
            result.add(rel_decision, 0, "decision-mismatch", f"{ident} đã quyết ở nhật ký nhưng decision.md không có khối BEGIN:user/END:user")
            continue
        body = block.group(1)
        d_status, d_quote, d_option = user_field(body, "Trạng thái"), user_field(body, "Người dùng nói"), user_field(body, "Phương án được chọn")
        if norm(d_status) != norm(cfg.decision_resolved):
            result.add(rel_decision, 0, "decision-mismatch", f"{ident}: nhật ký ghi `{cfg.decision_resolved}` nhưng khối của người dùng trong decision.md ghi \"{d_status}\"")
        elif clean(d_quote) != row["quote"] and ident not in d_quote:
            result.add(rel_decision, 0, "decision-mismatch", f"{ident}: nguyên văn trong decision.md (\"{d_quote}\") khác nhật ký (\"{row['quote']}\")")
        elif d_option != chosen:
            result.add(rel_decision, 0, "decision-choice-mismatch", f"{ident}: người dùng nói chọn {chosen} nhưng decision.md ghi phương án \"{d_option}\"")
        _, options = brief_info(directory, workspace)
        if options and chosen not in options:
            result.add(rel_decision, 0, "decision-choice-unknown", f"{ident}: phương án {chosen} không có trong brief ({', '.join(options)})")

    for ident, directory in sorted(seen_dirs.items()):
        if ident in logged:
            continue
        brief_gate, _ = brief_info(directory, workspace)
        if brief_gate is None or brief_gate <= gate:
            result.add(directory.relative_to(workspace).as_posix(), 0, "decision-not-logged", f"{ident} có thư mục nhưng không có dòng trong {log_rel}")
    result.notes.append(f"quyết định: {len(logged)} trong nhật ký, {due} tới hạn (gate <= G{gate}), {len(seen_dirs)} thư mục")


def score_of(cell: str, scale: int) -> tuple[int | None, str]:
    """(points, problem). `4 × 4 = 16`, `4×4` and a bare `16` are accepted."""
    numbers = [int(n) for n in re.findall(r"\d+", cell)]
    if len(numbers) >= 2:
        likelihood, impact = numbers[0], numbers[1]
        if not (1 <= likelihood <= scale and 1 <= impact <= scale):
            return None, f"khả năng và tác động phải là 1-{scale}: \"{cell}\""
        if len(numbers) >= 3 and numbers[2] != likelihood * impact:
            return None, f"điểm {numbers[2]} không bằng {likelihood} × {impact}"
        return likelihood * impact, ""
    if len(numbers) == 1 and 1 <= numbers[0] <= scale ** 2:
        return numbers[0], ""
    return None, f"không đọc ra điểm từ \"{cell}\""


def check_risks(workspace: Path, cfg: Config, gate: int, result: Result) -> None:
    register_rel, acceptance_rel = cfg.risk_register, cfg.risk_acceptance
    r_re = IDS.id_re(["R"])
    register: dict[str, tuple[int, int, str]] = {}   # id -> (line, points, status)
    text = read(workspace / register_rel)
    if text is not None:
        header, rows = table(text)
        cid, cscore, cstatus = column(header, "ID"), column(header, "Khả năng", "Điểm"), column(header, "Trạng thái")
        if None in (cid, cscore, cstatus):
            result.add(register_rel, 0, "risk-register-malformed", "bảng rủi ro cần các cột ID, \"Khả năng × Tác động\", Trạng thái")
            rows = []
        statuses = [norm(s) for s in cfg.risk_statuses]
        for number, cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            ident = clean(cells[cid])
            if not r_re.fullmatch(ident) or IDS.is_placeholder(ident):
                continue
            points, problem = score_of(cells[cscore], cfg.risk_scale)
            status = clean(cells[cstatus])
            if points is None:
                result.add(register_rel, number, "risk-score", f"{ident}: {problem}")
                continue
            if norm(status) not in statuses:
                result.add(register_rel, number, "risk-status", f"{ident}: trạng thái phải là một trong {', '.join(cfg.risk_statuses)} (đang là \"{status}\")")
                continue
            register[ident] = (number, points, norm(status))
    blocking = gate >= cfg.risk_block_from_gate
    unresolved = 0
    handled = {norm(s) for s in cfg.risk_handled}
    for ident, (number, points, status) in sorted(register.items()):
        if points >= cfg.risk_threshold and status not in handled:
            unresolved += 1
            result.add(register_rel, number, "risk-unresolved",
                       f"{ident} có {points} điểm (>= {cfg.risk_threshold}) mà chưa được chấp nhận hay đóng (trạng thái \"{status}\")" + ("" if blocking else f"; chỉ cảnh báo trước G{cfg.risk_block_from_gate}"), blocking)

    accepted = norm(cfg.risk_accepted)
    rows_by_id: dict[str, tuple[int, list[str]]] = {}
    acceptance = read(workspace / acceptance_rel)
    if acceptance is not None:
        header, rows = table(acceptance, "ID")
        cid, cscore, cquote, cdate = column(header, "ID"), column(header, "Điểm"), column(header, "Người dùng nói"), column(header, "Ngày")
        if header and None in (cid, cscore, cquote, cdate):
            result.add(acceptance_rel, 0, "acceptance-malformed", "bảng cần các cột ID, Điểm, Người dùng nói (nguyên văn), Ngày")
            rows = []
        for number, cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            ident = clean(cells[cid])
            if not r_re.fullmatch(ident) or IDS.is_placeholder(ident) or PLACEHOLDER.search(cells[cscore]):
                continue
            rows_by_id[ident] = (number, [clean(cells[cscore]), clean(cells[cquote]), clean(cells[cdate])])
            score_cell, quote, date = rows_by_id[ident][1]
            quote_re = re.compile(rf"(?<![\w-]){re.escape(ident)}(?![\w-])\s*:\s*{re.escape(cfg.accept_word)}", re.IGNORECASE)
            if ident not in register:
                result.add(acceptance_rel, number, "acceptance-orphan", f"{ident} có dòng chấp nhận nhưng sổ rủi ro ({register_rel}) không có rủi ro này")
            else:
                _, points, status = register[ident]
                if points < cfg.risk_threshold:
                    result.add(acceptance_rel, number, "acceptance-orphan", f"{ident} chỉ {points} điểm (< {cfg.risk_threshold}): không thuộc danh sách chấp nhận")
                elif status != accepted:
                    result.add(acceptance_rel, number, "acceptance-status", f"{ident} có dòng chấp nhận nhưng sổ rủi ro ghi trạng thái \"{status}\", không phải \"{cfg.risk_accepted}\"")
                if not re.fullmatch(r"\d+", score_cell) or int(score_cell) != points:
                    result.add(acceptance_rel, number, "acceptance-score", f"{ident}: điểm \"{score_cell}\" khác điểm của sổ rủi ro ({points})")
            if not quote_re.search(quote):
                result.add(acceptance_rel, number, "acceptance-quote", f"{ident}: nguyên văn người dùng phải có dạng \"{ident}: {cfg.accept_word}\" (đang là \"{quote}\")")
            if not valid_date(date):
                result.add(acceptance_rel, number, "acceptance-date", f"{ident}: ngày không hợp lệ \"{date}\" (YYYY-MM-DD)")
    for ident, (number, points, status) in sorted(register.items()):
        if points >= cfg.risk_threshold and status == accepted and ident not in rows_by_id:
            result.add(register_rel, number, "acceptance-missing", f"{ident} ({points} điểm) ghi \"{cfg.risk_accepted}\" nhưng {acceptance_rel} không có dòng của người dùng cho nó")
    result.notes.append(f"rủi ro: {len(register)} trong sổ, {unresolved} từ {cfg.risk_threshold} điểm chưa xử lý, {len(rows_by_id)} dòng chấp nhận")


def closed_tasks(workspace: Path, cfg: Config) -> set[str]:
    """IDs (`T-001`) of the tasks of `plan/tasks/` whose status is `đóng`."""
    folder = workspace / cfg.task_dir
    closed = set()
    for path in sorted(folder.glob("T-*.md")) if folder.is_dir() else []:
        match = re.match(r"T-\d+", path.name)
        if match and norm(state_field(tv.read_text(path), "Trạng thái")) == norm(cfg.task_closed):
            closed.add(match.group(0))
    return closed


def check_models(workspace: Path, cfg: Config, result: Result) -> None:
    rel = cfg.models_file
    text = read(workspace / rel)
    if text is None:
        result.notes.append(f"model: không có {rel}")
        return
    catalogue = {norm(name): cells for name, cells in dm.previous_rows(text).items()}
    section = tv.section(text, cfg.assign_heading) or []
    header, rows = table("\n".join(section), "Task")
    cmodel, ctask = column(header, "Model"), column(header, "Task")
    used = skipped = 0
    closed = closed_tasks(workspace, cfg)
    if header and cmodel is not None:
        for number, cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            cell = clean(cells[cmodel])
            if not cell or PLACEHOLDER.search(cell):
                continue
            task_id = re.match(r"T-\d+", clean(cells[ctask])) if ctask is not None else None
            if task_id and task_id.group(0) in closed:
                skipped += 1
                continue
            used += 1
            first = cell.split()[0] if cell.split() else cell
            row = catalogue.get(norm(cell)) or catalogue.get(norm(first))
            task = clean(cells[ctask]) if ctask is not None else "?"
            line = next((i + 1 for i, text_line in enumerate(text.splitlines()) if cell in text_line and "|" in text_line and task in text_line), 0)
            if row is None:
                result.add(rel, line, "model-unknown", f"task {task} dùng \"{cell}\" nhưng danh mục model không có dòng này", False)
                continue
            status = norm(row[4])
            if status == norm(dm.STATUS_STATIC):
                result.add(rel, line, "model-untested", f"task {task} dùng {cell} nhưng danh mục ghi \"{row[4]}\": model chưa thử chưa được dùng")
            elif status.startswith(norm(dm.STATUS_BAD)):
                result.add(rel, line, "model-unusable", f"task {task} dùng {cell} nhưng danh mục ghi \"{row[4]}\"; thêm dòng gán mới cho task này với model thay thế")
    result.notes.append(f"model: {used} dòng gán của task chưa đóng được kiểm, {skipped} dòng của task đã đóng giữ làm lịch sử")


def plan_layers(workspace: Path, cfg: Config) -> list[str]:
    text = read(workspace / cfg.plan_file)
    lines = tv.section(text, cfg.plan_heading) if text else None
    layers = []
    for line in lines or []:
        match = re.match(r"^\s*[-*]\s+`?([A-Za-z0-9_-]+)`?", line)
        if match:
            layers.append(match.group(1).casefold())
    return layers


def check_spikes(workspace: Path, cfg: Config, gate: int, level: str, result: Result) -> None:
    if norm(level) != norm(cfg.spike_level):
        result.notes.append(f"spike: mức {level or 'chưa duyệt'}, chỉ bắt buộc ở mức {cfg.spike_level}")
        return
    if gate < cfg.spike_from_gate:
        result.notes.append(f"spike: kiểm từ G{cfg.spike_from_gate}")
        return
    spike_cfg, errors = rs.load_config(rs.DEFAULT_CONFIG)
    if spike_cfg is None:
        result.add("data/spike.yaml", 0, "spike-config", "; ".join(errors))
        return
    required = list(dict.fromkeys([*spike_cfg.xl_required_layers, *plan_layers(workspace, cfg)]))
    required = [layer for layer in required if layer not in spike_cfg.optional_layers]
    layers_dir = workspace / "stack" / "layers"
    present = {p.name.casefold(): p for p in layers_dir.iterdir() if p.is_dir()} if layers_dir.is_dir() else {}
    ok = 0
    for layer in required:
        folder = present.get(layer)
        if folder is None:
            result.add(f"stack/layers/{layer}", 0, "spike-layer-absent", f"lớp bắt buộc {layer} chưa có thư mục stack/layers/{layer}/ (chưa làm stack của lớp này?)", False)
            continue
        specs = sorted(p for p in (folder / "spikes").glob("S-*.md") if p.is_file() and not p.name.endswith(spike_cfg.suffix)) if (folder / "spikes").is_dir() else []
        states = {p.name: rs.current_result(p, spike_cfg) for p in specs}
        if any(state == spike_cfg.ok for state in states.values()):
            ok += 1
            continue
        if not specs:
            why = "chưa có đề bài spike nào"
        else:
            parts = [f"{name}: " + (state if state else "chưa chạy hoặc kết quả cũ hơn đề bài hiện tại") for name, state in states.items()]
            why = "chưa có spike nào đạt (" + "; ".join(parts) + ")"
        result.add(f"stack/layers/{layer}/spikes", 0, "spike-missing", f"mức {cfg.spike_level}: lớp {layer} {why}")
    result.notes.append(f"spike ({cfg.spike_level}, từ G{cfg.spike_from_gate}): {ok}/{len(required)} lớp bắt buộc có spike đạt ({', '.join(required)})")


# --- main ------------------------------------------------------------------------------------------------------------------

def run(workspace: Path, cfg: Config, gate: int, level: str) -> Result:
    result = Result()
    check_tasks(workspace, cfg, gate, result)
    check_decisions(workspace, cfg, gate, result)
    check_risks(workspace, cfg, gate, result)
    check_models(workspace, cfg, result)
    check_spikes(workspace, cfg, gate, level, result)
    result.findings.sort(key=lambda f: (not f.blocking, f.code, f.path, f.line))
    return result


def report(workspace: Path, gate: int, level: str, result: Result, today: str) -> str:
    lines = [f"# check_workspace {today}", "", f"Gate G{gate}, mức {level or 'chưa duyệt'}: {len(result.errors)} lỗi chặn, {len(result.warnings)} cảnh báo.", "", "## Số liệu", ""]
    lines += [f"- {note}" for note in result.notes] + [""]
    for title, items in (("Lỗi chặn", result.errors), ("Cảnh báo (không chặn gate)", result.warnings)):
        lines += [f"## {title}", ""] + ([f"- {f.render()}" for f in items] or ["- không có"]) + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--gate", help="the gate being checked, G0-G10 (default: \"Giai đoạn hiện tại\" of state.md)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="words and thresholds (default: core/data/workspace.yaml)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.gate is not None and not GATE_RE.fullmatch(args.gate):
        parser.error("--gate phải có dạng G0 đến G10")
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    cfg, config_errors = load_config(args.config.resolve())
    if cfg is None:
        for error in config_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    state = read(workspace / "state.md") or ""
    level = state_field(state, "Mức áp dụng")
    if args.gate is not None:
        gate = int(args.gate[1:])
    else:
        match = GATE_RE.search(state_field(state, "Giai đoạn hiện tại"))
        if not match:
            print("không có --gate và state.md không có dòng \"Giai đoạn hiện tại: Gn\"", file=sys.stderr)
            return 2
        gate = int(match.group(1))
    gates, gate_errors = cr.load_config()
    if gates is None:
        for error in gate_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    files = cr.hash_files(workspace, cr.expand(workspace, gates.reports["check_workspace"].scope))  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    result = run(workspace, cfg, gate, level)
    target = workspace / "checks" / f"workspace-{today}.md"
    tv.write_text(target, report(workspace, gate, level, result, today) + cr.render("check_workspace.py", not result.errors, files, f"G{gate}"))
    print(f"check_workspace G{gate}: {len(result.errors)} lỗi chặn, {len(result.warnings)} cảnh báo; báo cáo: {target}")
    for note in result.notes:
        print(f"  {note}")
    for finding in result.errors[:SHOWN]:
        print(f"error: {finding.render()}")
    if len(result.errors) > SHOWN:
        print(f"error: … và {len(result.errors) - SHOWN} lỗi nữa (xem báo cáo)")
    for finding in result.warnings[:5]:
        print(f"warning: {finding.render()}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
