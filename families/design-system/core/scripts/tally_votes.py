# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Count the council votes of the decisions (`.agent-workspace/decisions/D-*/`), round by round.

Per decision it reads `brief.md` (frontmatter: decision, gate, council_size, criteria, options) and the votes of
`votes/r<round>-<perspective>-<member>.md` (frontmatter as in templates/workspace/vote.md), then:

- rejects a vote (blocking, exit 1) that is malformed: a missing or extra key, a score or exclusion cell missing or extra,
  overreach above the cap (default 20 per option per vote, data/council.yaml), a `choice` other than the option with the highest
  total that this script computes, a tie (totals less than 0.01 apart, unrounded) without `tie_reason`, `choice: none` that is
  neither (a) every option failing an exclusion criterion nor (b) backed by cites and reasons; a missing vote of a perspective;
- total = sum(score x weight) / (5 x sum(weights)) x 100 - overreach points, over the weighted criteria of the brief; an option
  failing an exclusion criterion is out of that vote. Totals are compared unrounded (exact fractions) and rounded to 1 decimal
  only for display;
- counts: more than half of the council is a majority (2/3, 3/5). Round 1 without a majority needs round 2: it writes
  `votes/r1-summary.md` (the verbatim "Lý do" of each round-1 vote, member / model / perspective removed, order shuffled, no
  summarising). Round 2 without a majority is "chưa đạt đồng thuận" with the two leading options. "none" with a majority means
  the Designer redoes the brief.

It writes `tally.md` and ONLY the block between `<!-- BEGIN:council ... -->` and `<!-- END:council -->` of `decision.md` (created
from the template when missing). Nothing is written for a decision that has a blocking error. Needing round 2, no consensus
and "none" are results, not errors (exit 0). The report is also written to `<workspace>/checks/tally-<date>.md`, ending with
the sha256 of the files of every decision counted (checkreport.py).

    uv run tally_votes.py [--workspace DIR] [--gate Gn] [--decision D-xxx-name] [--config FILE]

`--gate` counts only the decisions whose brief says that gate (default: every decision).
"""

import argparse
import datetime
import hashlib
import random
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import yaml

import checkreport as cr
import idlist

IDS = idlist.load()  # the ID prefixes shared with check_links / check_numbers / check_trace: core/data/ids.yaml
ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CORE / "data" / "council.yaml"
DECISION_TEMPLATE = CORE / "templates" / "workspace" / "decision.md"
NONE = "none"
SUMMARY_NAME = "r1-summary.md"
SHOWN = 25

BEGIN_RE = re.compile(r"<!--\s*BEGIN:council\b[^>]*-->")
END_RE = re.compile(r"<!--\s*END:council\s*-->")
DEFAULT_BEGIN = "<!-- BEGIN:council (tally_votes.py sinh, không sửa tay) -->"
END_MARK = "<!-- END:council -->"
VOTE_KEYS = ("decision", "round", "perspective", "member", "model", "via", "choice", "scores", "exclusions", "overreach", "tie_reason", "cites")
BRIEF_KEYS = ("decision", "gate", "council_size", "criteria", "options")
LIST_ITEM_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
H2_RE = re.compile(r"^##\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


# --- data ------------------------------------------------------------------------------------------------------------------

@dataclass
class Config:
    sizes: dict[int, list[str]]
    gates: list[str]
    score_max: int
    max_overreach: int
    tie: Fraction
    vias: list[str]
    cite_kinds: list[str]

    @property
    def perspectives(self) -> list[str]:
        return self.sizes[max(self.sizes)]

    def cite_re(self) -> re.Pattern:
        return IDS.id_re(self.cite_kinds)


@dataclass
class Problem:
    path: str
    code: str
    message: str

    def render(self) -> str:
        return f"{self.path}: [{self.code}] {self.message}"


@dataclass
class Criterion:
    id: str
    kind: str
    weight: int = 0


@dataclass
class Brief:
    decision: str
    gate: str
    size: int
    criteria: list[Criterion]
    options: list[str]
    question: str = ""
    text: str = ""            # the whole brief.md: the only source of the numbers a vote may quote

    @property
    def weighted(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "weighted"]

    @property
    def exclusion(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "exclusion"]


@dataclass
class Vote:
    file: str
    round: int
    perspective: str
    member: str
    model: str
    via: str
    choice: str
    totals: dict[str, Fraction | None]   # None = out of this vote (failed an exclusion criterion)
    failed: dict[str, list[str]]
    overreach: dict[str, int]
    tie_reason: str
    reasons: str                          # the body of "Lý do", verbatim
    risks: list[str]


@dataclass
class Outcome:
    kind: str                 # proposal | none | no-consensus | wait-round-2
    option: str = ""
    leaders: list[str] = field(default_factory=list)
    rounds: int = 1


@dataclass
class Result:
    name: str
    problems: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)
    outcome: Outcome | None = None
    written: list[str] = field(default_factory=list)


# --- config ----------------------------------------------------------------------------------------------------------------

def load_config(path: Path) -> tuple[Config | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    if not isinstance(data, dict):
        return None, [f"{path}: phải là một mapping"]
    errors = []
    sizes = data.get("sizes")
    if not isinstance(sizes, dict) or not sizes or not all(isinstance(k, int) and isinstance(v, list) and v and all(isinstance(p, str) for p in v) for k, v in sizes.items()):
        errors.append("sizes: phải là {số thành viên: [góc nhìn, ...]}")
    elif any(len(v) != k or len(set(v)) != k for k, v in sizes.items()):
        errors.append("sizes: mỗi khóa phải bằng số góc nhìn khác nhau của nó")
    gates = data.get("gates")
    if not isinstance(gates, list) or not all(isinstance(g, str) for g in gates):
        errors.append("gates: phải là danh sách chuỗi")
    for key in ("score_max", "max_overreach"):
        if not isinstance(data.get(key), int) or isinstance(data.get(key), bool) or data[key] < 0:
            errors.append(f"{key}: phải là số nguyên không âm")
    try:
        tie = Fraction(str(data.get("tie_threshold")))
        if tie <= 0:
            raise ValueError
    except (ValueError, ZeroDivisionError):
        errors.append("tie_threshold: phải là số dương (chuỗi, ví dụ \"0.01\")")
        tie = Fraction(0)
    for key in ("vias", "cite_kinds"):
        if not isinstance(data.get(key), list) or not data[key] or not all(isinstance(v, str) for v in data[key]):
            errors.append(f"{key}: phải là danh sách chuỗi không rỗng")
    if not errors and set(data["cite_kinds"]) - set(IDS.kinds):
        errors.append(f"cite_kinds có tiền tố không nằm trong data/ids.yaml: {sorted(set(data['cite_kinds']) - set(IDS.kinds))}")
    if errors:
        return None, errors
    return Config({int(k): list(v) for k, v in sizes.items()}, list(gates), data["score_max"], data["max_overreach"], tie, list(data["vias"]), list(data["cite_kinds"])), []


# --- parsing ---------------------------------------------------------------------------------------------------------------

class StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects a repeated key (a second `choice:` would silently win)."""


def _construct_mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"khóa lặp: {key!r}", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:])
    return None, text


def parse_frontmatter(text: str) -> tuple[dict | None, str, str]:
    """(data, body, error)."""
    raw, body = split_frontmatter(text)
    if raw is None:
        return None, text, "không có frontmatter (file phải bắt đầu bằng dòng ---, không bọc trong khối mã)"
    try:
        data = yaml.load(raw, Loader=StrictLoader)
    except (yaml.YAMLError, TypeError) as error:
        return None, body, f"frontmatter không phải YAML hợp lệ: {str(error).splitlines()[0] if str(error) else error}"
    if not isinstance(data, dict):
        return None, body, "frontmatter phải là một mapping"
    return data, body, ""


def section(body: str, title: str, prefix: bool = False) -> list[str] | None:
    """Lines of the level-2 section called `title` (or starting with it), up to the next `## `; fenced code is not scanned for headings."""
    lines = body.splitlines()
    start = None
    fenced = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        match = H2_RE.match(line) if not fenced else None
        heading = nfc(match.group(1)).casefold() if match else ""
        if match and (heading.startswith(nfc(title).casefold()) if prefix else heading == nfc(title).casefold()):
            start = index + 1
            break
    if start is None:
        return None
    out = []
    fenced = False
    for line in lines[start:]:
        if FENCE_RE.match(line):
            fenced = not fenced
        elif not fenced and H2_RE.match(line):
            break
        out.append(line)
    return out


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def parse_brief(text: str, dir_name: str, rel: str) -> tuple[Brief | None, list[Problem]]:
    problems: list[Problem] = []

    def bad(code: str, message: str) -> None:
        problems.append(Problem(rel, code, message))

    data, body, error = parse_frontmatter(text)
    if data is None:
        bad("brief-frontmatter", error)
        return None, problems
    for key in BRIEF_KEYS:
        if key not in data:
            bad("brief-key-missing", f"thiếu khóa `{key}` trong frontmatter của brief")
    for key in data:
        if key not in BRIEF_KEYS:
            bad("brief-key-unknown", f"khóa lạ `{key}` trong frontmatter của brief")
    if problems:
        return None, problems
    decision, gate, size = data["decision"], data["gate"], data["council_size"]
    if not isinstance(decision, str) or not re.fullmatch(r"D-[A-Za-z0-9_]+", decision):
        bad("brief-decision", f"decision phải có dạng D-<số>, đang là {decision!r}")
    elif dir_name != decision and not dir_name.startswith(decision + "-"):
        bad("brief-decision", f"decision {decision} không khớp tên thư mục {dir_name}")
    if not isinstance(gate, str) or not re.fullmatch(r"G\d+", gate):
        bad("brief-gate", f"gate phải có dạng Gn, đang là {gate!r}")
    if not is_int(size):
        bad("brief-council-size", f"council_size phải là số nguyên, đang là {size!r}")
    options = data["options"]
    if not isinstance(options, list) or not options or not all(isinstance(o, str) and o.strip() for o in options):
        bad("brief-options", "options phải là danh sách ID phương án (chuỗi) không rỗng")
        options = []
    else:
        if len(set(options)) != len(options):
            bad("brief-options", "options có ID trùng")
        if NONE in options:
            bad("brief-options", f"options không được chứa `{NONE}` (luôn có sẵn)")
    criteria: list[Criterion] = []
    raw = data["criteria"]
    if not isinstance(raw, list) or not raw:
        bad("brief-criteria", "criteria phải là danh sách không rỗng")
        raw = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item.get("kind") not in ("weighted", "exclusion"):
            bad("brief-criteria", f"mỗi tiêu chí phải là {{id, kind: weighted|exclusion, weight}}, gặp {item!r}")
            continue
        extra = set(item) - {"id", "kind", "weight"}
        if extra:
            bad("brief-criteria", f"{item['id']}: khóa lạ {sorted(extra)}")
        if item["kind"] == "weighted":
            weight = item.get("weight")
            if not is_int(weight) or weight <= 0:
                bad("brief-criteria", f"{item['id']}: tiêu chí có trọng số cần weight là số nguyên dương, đang là {weight!r}")
                continue
            criteria.append(Criterion(item["id"], "weighted", weight))
        else:
            if "weight" in item:
                bad("brief-criteria", f"{item['id']}: tiêu chí loại trừ không có weight")
            criteria.append(Criterion(item["id"], "exclusion"))
    ids = [c.id for c in criteria]
    if len(set(ids)) != len(ids):
        bad("brief-criteria", "criteria có ID trùng")
    if raw and not any(c.kind == "weighted" for c in criteria):
        bad("brief-criteria", "phải có ít nhất một tiêu chí có trọng số")
    if problems:
        return None, problems
    brief = Brief(decision, gate, size, criteria, list(options), text=text)
    question = section(body, "Câu hỏi")
    brief.question = next((line.strip() for line in question or [] if line.strip() and not line.strip().startswith("<!--")), "")
    problems += check_brief_body(body, brief, rel)
    return (None if problems else brief), problems


def check_brief_body(body: str, brief: Brief, rel: str) -> list[Problem]:
    """The frontmatter must match the 'Tiêu chí chấm' table and the '### Phương án X:' headings (brief.md says so)."""
    problems = []
    lines = section(body, "Tiêu chí chấm", prefix=True)
    table: dict[str, tuple[str, str]] = {}
    weight_at = exclusion_at = None
    for line in lines or []:
        if not line.lstrip().startswith("|"):
            continue
        cells = split_cells(line)
        folded = [nfc(c).casefold() for c in cells]
        if any("trọng số" in c for c in folded) and any("loại trừ" in c for c in folded):
            weight_at = next(i for i, c in enumerate(folded) if "trọng số" in c)
            exclusion_at = next(i for i, c in enumerate(folded) if "loại trừ" in c)
            continue
        if weight_at is not None and re.fullmatch(r"TC-[A-Za-z0-9_-]+", cells[0]) and len(cells) > max(weight_at, exclusion_at):
            table[cells[0]] = (cells[weight_at], nfc(cells[exclusion_at]).casefold())
    if weight_at is None:
        problems.append(Problem(rel, "brief-table", "không có bảng \"Tiêu chí chấm\" với cột Trọng số và Loại trừ?"))
    else:
        want = {c.id for c in brief.criteria}
        if set(table) != want:
            problems.append(Problem(rel, "brief-table", f"TC trong bảng ({', '.join(sorted(table)) or 'không có'}) khác criteria trong frontmatter ({', '.join(sorted(want))})"))
        for c in brief.criteria:
            if c.id not in table:
                continue
            weight, excluded = table[c.id]
            if c.kind == "exclusion" and excluded != "có":
                problems.append(Problem(rel, "brief-table", f"{c.id}: frontmatter là loại trừ nhưng cột Loại trừ? là \"{excluded}\""))
            if c.kind == "weighted" and (excluded != "không" or weight != str(c.weight)):
                problems.append(Problem(rel, "brief-table", f"{c.id}: frontmatter là trọng số {c.weight}, bảng ghi trọng số \"{weight}\", loại trừ \"{excluded}\""))
    headings = []
    fenced = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
        match = None if fenced else re.match(r"^###\s+Phương án\s+([^\s:]+)\s*:", line)
        if match:
            headings.append(match.group(1))
    if sorted(headings) != sorted(brief.options):
        problems.append(Problem(rel, "brief-options-body", f"mục \"### Phương án X:\" ({', '.join(headings) or 'không có'}) khác options trong frontmatter ({', '.join(brief.options)})"))
    return problems


# --- votes -----------------------------------------------------------------------------------------------------------------

def parse_vote_name(name: str, perspectives: list[str]) -> tuple[int, str, str] | None:
    match = re.fullmatch(r"r([12])-(.+)\.md", name)
    if not match:
        return None
    rest = match.group(2)
    for perspective in sorted(perspectives, key=len, reverse=True):
        if rest.startswith(perspective + "-") and len(rest) > len(perspective) + 1:
            return int(match.group(1)), perspective, rest[len(perspective) + 1:]
    return None


def reason_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        match = LIST_ITEM_RE.match(line)
        if match:
            items.append(match.group(2).strip())
        elif items and line.strip():
            items[-1] += " " + line.strip()
    return items


NUMBER_RE = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")


def number_tokens(text: str) -> list[str]:
    """The numbers written in `text`, in order, without repeats. A number is a run of digits with `.` or `,` between digit groups
    (1.000, 99,5, 16.4), not glued to letters (p99, S3, Q5). The digits of an ID (TC-01, NFR-07, A-03) are not numbers. Compared
    as text: 12 is not 120, and 16.4 is not 16.4.1."""
    masked = IDS.id_re().sub(" ", text)
    return list(dict.fromkeys(NUMBER_RE.findall(masked)))


def risk_items(lines: list[str] | None) -> list[str]:
    out = []
    for line in lines or []:
        match = BULLET_RE.match(line)
        if match and match.group(1).strip() and not nfc(match.group(1)).casefold().startswith("không có"):
            out.append(match.group(1).strip())
    return out


def fmt(value: Fraction) -> str:
    return f"{float(value):.1f}"


def validate_vote(text: str, rel: str, round_no: int, perspective: str, member: str, brief: Brief, cfg: Config) -> tuple[Vote | None, list[Problem], list[Problem]]:
    problems: list[Problem] = []
    warnings: list[Problem] = []

    def bad(code: str, message: str) -> None:
        problems.append(Problem(rel, code, message))

    data, body, error = parse_frontmatter(text)
    if data is None:
        bad("vote-frontmatter", error)
        return None, problems, warnings
    for key in VOTE_KEYS:
        if key not in data:
            bad("vote-key-missing", f"thiếu khóa `{key}`")
    for key in data:
        if key not in VOTE_KEYS:
            bad("vote-key-unknown", f"khóa lạ `{key}`")
    if problems:
        return None, problems, warnings
    if data["decision"] != brief.decision:
        bad("vote-decision", f"decision {data['decision']!r} khác brief ({brief.decision})")
    if data["round"] != round_no or not is_int(data["round"]):
        bad("vote-round", f"round {data['round']!r} khác vòng của tên file ({round_no})")
    if data["perspective"] != perspective:
        bad("vote-perspective", f"perspective {data['perspective']!r} khác góc nhìn của tên file ({perspective})")
    if data["member"] != member:
        bad("vote-member", f"member {data['member']!r} khác phần cuối tên file ({member})")
    if not isinstance(data["model"], str) or not data["model"].strip():
        bad("vote-model", "model phải là chuỗi không rỗng")
    if data["via"] not in cfg.vias:
        bad("vote-via", f"via phải là một trong {', '.join(cfg.vias)}, đang là {data['via']!r}")
    options = brief.options
    choice = data["choice"]
    if not isinstance(choice, str) or choice not in options + [NONE]:
        bad("vote-choice", f"choice phải là {', '.join(options)} hoặc {NONE}, đang là {choice!r}")

    weighted = [c.id for c in brief.weighted]
    scores = data["scores"]
    if not isinstance(scores, dict) or set(scores) != set(options):
        bad("vote-scores", f"scores phải có đúng các phương án {', '.join(options)}")
    else:
        for option in options:
            row = scores[option]
            if not isinstance(row, dict):
                bad("vote-scores", f"scores.{option} phải là {{TC: điểm}}")
                continue
            for tc in weighted:
                if tc not in row:
                    bad("vote-scores-missing", f"scores.{option} thiếu {tc}")
            for tc in row:
                if tc not in weighted:
                    bad("vote-scores-extra", f"scores.{option} có {tc} không phải TC có trọng số của brief")
            for tc, value in row.items():
                if tc in weighted and (not is_int(value) or not 0 <= value <= cfg.score_max):
                    bad("vote-score-range", f"scores.{option}.{tc} phải là số nguyên 0-{cfg.score_max}, đang là {value!r}")

    excl = [c.id for c in brief.exclusion]
    exclusions = data["exclusions"] if data["exclusions"] is not None else {}
    if not isinstance(exclusions, dict):
        bad("vote-exclusions", "exclusions phải là {phương án: {TC: pass|fail}}")
    elif excl:
        if set(exclusions) != set(options):
            bad("vote-exclusions", f"exclusions phải có đúng các phương án {', '.join(options)}")
        else:
            for option in options:
                row = exclusions[option]
                if not isinstance(row, dict):
                    bad("vote-exclusions", f"exclusions.{option} phải là {{TC: pass|fail}}")
                    continue
                for tc in excl:
                    if tc not in row:
                        bad("vote-exclusions-missing", f"exclusions.{option} thiếu {tc}")
                for tc, value in row.items():
                    if tc not in excl:
                        bad("vote-exclusions-extra", f"exclusions.{option} có {tc} không phải TC loại trừ của brief")
                    elif value not in ("pass", "fail"):
                        bad("vote-exclusions-value", f"exclusions.{option}.{tc} phải là pass hoặc fail, đang là {value!r}")
    else:
        for option, row in exclusions.items():
            if row not in (None, {}):
                bad("vote-exclusions-extra", f"brief không có TC loại trừ nhưng exclusions.{option} có nội dung")

    overreach = data["overreach"]
    points: dict[str, int] = {}
    if not isinstance(overreach, dict) or set(overreach) != set(options):
        bad("vote-overreach", f"overreach phải có đúng các phương án {', '.join(options)}")
    else:
        for option in options:
            row = overreach[option]
            if not isinstance(row, dict) or set(row) != {"points", "reason"}:
                bad("vote-overreach", f"overreach.{option} phải là {{points, reason}}")
                continue
            value, reason = row["points"], row["reason"]
            if not is_int(value) or value < 0:
                bad("vote-overreach", f"overreach.{option}.points phải là số nguyên không âm, đang là {value!r}")
                continue
            if value > cfg.max_overreach:
                bad("vote-overreach-over-limit", f"overreach.{option}.points = {value} vượt giới hạn {cfg.max_overreach} mỗi phương án mỗi phiếu: phiếu bị từ chối")
                continue
            if not isinstance(reason, str):
                bad("vote-overreach", f"overreach.{option}.reason phải là chuỗi")
                continue
            if value > 0 and not reason.strip():
                bad("vote-overreach-reason", f"overreach.{option}.points = {value} nhưng reason rỗng")
            points[option] = value

    tie_reason = data["tie_reason"]
    if not isinstance(tie_reason, str):
        bad("vote-tie-reason", "tie_reason phải là chuỗi (\"\" khi không hòa)")
        tie_reason = ""
    cites = data["cites"]
    cite_re = cfg.cite_re()
    if not isinstance(cites, list) or not all(isinstance(c, str) and cite_re.fullmatch(c) for c in cites):
        bad("vote-cites", f"cites phải là danh sách ID {'/'.join(cfg.cite_kinds)}-xx, đang là {cites!r}")
        cites = []

    lines = section(body, "Lý do")
    items = reason_items(lines or [])
    if not items:
        bad("vote-reasons", "thiếu mục \"## Lý do\" hoặc mục không có dòng đánh số (1. ...)")
    else:
        for number, item in enumerate(items, start=1):
            if not cite_re.search(item) and not re.search(r"\d", item):
                bad("vote-reason-uncited", f"lý do {number} không trích TC/NFR/C/R nào và không có giá trị nào: \"{item[:60]}\"")
        mentioned = {m for item in items for m in cite_re.findall(item)}
        missing = sorted(mentioned - set(cites))
        if missing:
            bad("vote-cites-incomplete", f"lý do trích {', '.join(missing)} nhưng cites không có")
        known = number_tokens(brief.text)
        for number, item in enumerate(items, start=1):
            absent = [token for token in number_tokens(item) if token not in known]
            if absent:
                bad("vote-number-not-in-brief", f"lý do {number} dùng số {', '.join(absent[:5])} không xuất hiện nguyên văn trong brief (hội đồng chỉ đọc brief)")
    if problems:
        return None, problems, warnings

    # score
    total_weight = sum(c.weight for c in brief.weighted)
    totals: dict[str, Fraction | None] = {}
    failed: dict[str, list[str]] = {}
    for option in options:
        fails = [tc for tc in excl if exclusions.get(option, {}).get(tc) == "fail"] if excl else []
        failed[option] = fails
        if fails:
            totals[option] = None
            continue
        weighted_sum = sum(scores[option][c.id] * c.weight for c in brief.weighted)
        totals[option] = Fraction(weighted_sum, cfg.score_max * total_weight) * 100 - points[option]
    standing = {o: t for o, t in totals.items() if t is not None}
    tied: list[str] = []
    if choice == NONE:
        if standing and not cites:
            bad("vote-none", "choice: none khi còn phương án không vi phạm loại trừ cần cites không rỗng (điều kiện b)")
    elif not standing:
        bad("vote-choice", f"mọi phương án vi phạm TC loại trừ nên choice phải là {NONE}, đang là {choice}")
    elif choice not in standing:
        bad("vote-choice-excluded", f"choice {choice} vi phạm TC loại trừ ({', '.join(failed[choice])}), không được chọn")
    else:
        top = max(standing.values())
        tied = sorted(o for o, t in standing.items() if top - t < cfg.tie)
        shown = ", ".join(f"{o} {fmt(t)}" for o, t in standing.items())
        if len(tied) > 1:
            if not tie_reason.strip():
                bad("vote-tie-reason", f"{' và '.join(tied)} hòa (chênh dưới {float(cfg.tie):g} điểm, chưa làm tròn) nhưng tie_reason rỗng")
            elif choice not in tied:
                bad("vote-choice-not-top", f"choice {choice} không nằm trong nhóm hòa cao nhất ({', '.join(tied)}); tổng: {shown}")
        elif choice != tied[0]:
            bad("vote-choice-not-top", f"choice {choice} lệch phương án có tổng cao nhất {tied[0]}; tổng: {shown}")
    if len(tied) <= 1 and tie_reason.strip():
        warnings.append(Problem(rel, "vote-tie-reason-unused", "tie_reason có nội dung nhưng không có phương án nào hòa"))
    if problems:
        return None, problems, warnings
    vote = Vote(
        file=rel, round=round_no, perspective=perspective, member=member, model=data["model"].strip(), via=data["via"], choice=choice,
        totals=totals, failed=failed, overreach=points, tie_reason=tie_reason.strip(), reasons="\n".join(lines or []).strip(),
        risks=risk_items(section(body, "Rủi ro mới")),
    )
    return vote, problems, warnings


# --- rounds ----------------------------------------------------------------------------------------------------------------

def majority(count: int, size: int) -> bool:
    return 2 * count > size


def needed(size: int) -> str:
    return f"{size // 2 + 1}/{size}"


def counts_of(votes: list[Vote], options: list[str]) -> Counter:
    counter = Counter({o: 0 for o in options + [NONE]})
    counter.update(v.choice for v in votes)
    return counter


def winner(votes: list[Vote], options: list[str], size: int) -> str | None:
    for key, count in counts_of(votes, options).items():
        if majority(count, size):
            return key
    return None


def leaders(votes: list[Vote], options: list[str]) -> list[str]:
    """Two leading options: most votes, then highest mean total (unrounded), then ID."""
    counter = counts_of(votes, options)

    def mean(option: str) -> Fraction:
        values = [v.totals[option] for v in votes if v.totals[option] is not None]
        return sum(values, Fraction(0)) / len(values) if values else Fraction(-10**9)

    ranked = sorted(options, key=lambda o: (-counter[o], -mean(o), o))
    return ranked[:2]


def summary_text(decision: str, round1: list[Vote]) -> str:
    bodies = sorted(v.reasons for v in round1)
    seed = int(hashlib.sha256("\n\x00".join(bodies).encode(ENCODING)).hexdigest()[:16], 16)
    random.Random(seed).shuffle(bodies)
    lines = [
        f"# Tóm tắt vòng 1 (ẩn danh): {decision}",
        "",
        "> `tally_votes.py` sinh file này, không phải model tóm tắt. Mỗi mục là nguyên văn phần \"Lý do\" của một phiếu vòng 1; "
        "tên thành viên, model và góc nhìn đã bỏ; thứ tự đã xáo. Đọc lập luận rồi bỏ phiếu lại độc lập, không bắt buộc đổi.",
        "",
    ]
    for number, body in enumerate(bodies, start=1):
        lines += [f"## Ý kiến {number}", "", body, ""]
    return "\n".join(lines)


def diversity(votes: list[Vote]) -> str:
    by_model: dict[str, list[str]] = {}
    for vote in votes:
        by_model.setdefault(vote.model.casefold(), []).append(vote.perspective)
    shared = {m: p for m, p in by_model.items() if len(p) > 1}
    if not shared:
        return "đủ: mỗi thành viên một model khác nhau"
    parts = [f"dùng chung model {next(v.model for v in votes if v.model.casefold() == m)} cho {', '.join(p)}" for m, p in shared.items()]
    return "giảm: " + "; ".join(parts)


def result_line(outcome: Outcome) -> str:
    if outcome.kind == "proposal":
        return f"đề xuất phương án {outcome.option}"
    if outcome.kind == "none":
        return "\"không phương án nào phù hợp\": Designer làm lại brief"
    if outcome.kind == "no-consensus":
        return "chưa đạt đồng thuận, hai phương án dẫn đầu: " + " và ".join(outcome.leaders)
    return "chưa quá bán ở vòng 1: chờ vòng 2 (mỗi thành viên đọc votes/r1-summary.md rồi bỏ phiếu lại)"


def vote_totals_line(vote: Vote, options: list[str]) -> str:
    parts = []
    for option in options:
        total = vote.totals[option]
        parts.append(f"{option} loại ({', '.join(vote.failed[option])})" if total is None else f"{option} {fmt(total)}")
    return " · ".join(parts)


def quote(text: str) -> list[str]:
    return [f"> {line}" if line.strip() else ">" for line in text.splitlines()]


def minority(final: list[Vote], outcome: Outcome, options: list[str]) -> list[Vote]:
    if outcome.kind == "wait-round-2":
        return []
    if outcome.kind == "proposal":
        reference = outcome.option
    elif outcome.kind == "none":
        reference = NONE
    else:
        reference = outcome.leaders[0] if outcome.leaders else NONE
    return [v for v in final if v.choice != reference]


def council_block(begin: str, brief: Brief, outcome: Outcome, r1: list[Vote], r2: list[Vote]) -> str:
    final = r2 if r2 else r1
    options = brief.options
    c1 = counts_of(r1, options)
    c2 = counts_of(r2, options) if r2 else None
    lines = [
        begin, "", "## Hội đồng", "",
        f"- **Kết quả:** {result_line(outcome)}",
        f"- **Số vòng:** {2 if r2 else 1}" + (" (đang chờ vòng 2)" if outcome.kind == "wait-round-2" else ""),
        f"- **Quá bán cần:** {needed(brief.size)}",
        f"- **Độ đa dạng model:** {diversity(final)}",
        "", "### Tỉ lệ phiếu", "",
        "| Phương án | Vòng 1 | Vòng 2 |", "| --- | --- | --- |",
    ]
    for key in options + [NONE]:
        lines.append(f"| {key} | {c1[key]}/{brief.size} | {f'{c2[key]}/{brief.size}' if c2 is not None else '—'} |")
    lines += ["", "### Ý kiến thiểu số", ""]
    if outcome.kind == "wait-round-2":
        lines.append("- chưa xác định: chờ vòng 2")
    else:
        others = minority(final, outcome, options)
        if not others:
            lines.append("- không có")
        for vote in others:
            lines.append(f"- **{vote.perspective}** · {vote.model} · chọn {vote.choice} · tổng: {vote_totals_line(vote, options)}")
            if vote.tie_reason:
                lines.append(f"  - hòa, lý do chọn: {vote.tie_reason}")
            lines += [f"  {line}" for line in quote(vote.reasons)]
    lines += ["", "### Rủi ro mới sinh ra", ""]
    seen: dict[str, list[str]] = {}
    for vote in r1 + r2:
        for risk in vote.risks:
            owners = seen.setdefault(risk, [])
            if vote.perspective not in owners:
                owners.append(vote.perspective)
    lines += [f"- {risk} · nêu bởi {', '.join(owners)}" for risk, owners in seen.items()] or ["- không có"]
    lines += ["", END_MARK]
    return "\n".join(lines)


def tally_text(brief: Brief, outcome: Outcome, rounds: list[list[Vote]], today: str, cfg: Config) -> str:
    options = brief.options
    lines = [
        f"# Đếm phiếu {brief.decision}", "",
        f"`tally_votes.py` sinh ngày {today}, không sửa tay. Tổng = Σ(điểm × trọng số) / ({cfg.score_max} × Σ trọng số) × 100 − điểm làm quá tay; "
        f"so sánh bằng giá trị chưa làm tròn, làm tròn 1 chữ số thập phân khi hiển thị; hai tổng chênh dưới {float(cfg.tie):g} là hòa.", "",
        f"- Hội đồng: {brief.size} thành viên, quá bán cần {needed(brief.size)}",
        f"- Tiêu chí có trọng số: " + ", ".join(f"{c.id} ({c.weight})" for c in brief.weighted),
        f"- Tiêu chí loại trừ: " + (", ".join(c.id for c in brief.exclusion) or "không có"),
        f"- Kết quả: {result_line(outcome)}", "",
    ]
    for number, votes in enumerate(rounds, start=1):
        if not votes:
            continue
        lines += [f"## Vòng {number}", "", "| Góc nhìn | Thành viên | Model | via | Chọn |", "| --- | --- | --- | --- | --- |"]
        lines += [f"| {v.perspective} | {v.member} | {v.model} | {v.via} | {v.choice} |" for v in votes]
        lines += ["", "Tổng điểm mỗi phiếu (loại = vi phạm TC loại trừ, không tính):", "", "| Góc nhìn | " + " | ".join(options) + " | Làm quá tay | Hòa |", "| --- |" + " --- |" * (len(options) + 2)]
        for v in votes:
            cells = [f"loại ({', '.join(v.failed[o])})" if v.totals[o] is None else fmt(v.totals[o]) for o in options]
            over = ", ".join(f"{o}: −{p}" for o, p in v.overreach.items() if p) or "—"
            lines.append(f"| {v.perspective} | " + " | ".join(cells) + f" | {over} | {v.tie_reason or '—'} |")
        counter = counts_of(votes, options)
        lines += ["", "| Phương án | Số phiếu |", "| --- | --- |"] + [f"| {k} | {counter[k]}/{brief.size} |" for k in options + [NONE]] + [""]
    return "\n".join(lines)


# --- decision.md -----------------------------------------------------------------------------------------------------------

def splice_council(text: str, block_for) -> tuple[str | None, str]:
    """Replace only the council block. `block_for(begin_marker)` returns the new block. (new_text, error)."""
    begins, ends = list(BEGIN_RE.finditer(text)), list(END_RE.finditer(text))
    if len(begins) != 1 or len(ends) != 1:
        return None, f"cần đúng một cặp BEGIN:council / END:council, thấy {len(begins)} BEGIN và {len(ends)} END"
    begin, end = begins[0], ends[0]
    if end.start() < begin.end():
        return None, "END:council đứng trước BEGIN:council"
    block = block_for(begin.group(0))
    if "\r\n" in text:
        block = block.replace("\r\n", "\n").replace("\n", "\r\n")
    return text[: begin.start()] + block + text[end.end():], ""


def new_decision_text(brief: Brief, template: str) -> str:
    replacements = {
        "# Quyết định D-<xxx>: <câu hỏi>": f"# Quyết định {brief.decision}: {brief.question or '(xem brief.md)'}",
        "- **Gate:** <G3 | G4 | G7>": f"- **Gate:** {brief.gate}",
        "- **Trạng thái:** <chờ người dùng | đã quyết | làm lại>": "- **Trạng thái:** chờ người dùng",
        "- **Người dùng nói (nguyên văn):** <\"D-007: chọn B\">": "- **Người dùng nói (nguyên văn):** —",
        "- **Ngày:** <YYYY-MM-DD>": "- **Ngày:** —",
        "- **Phương án được chọn:** <A | B | ... | làm lại brief>": "- **Phương án được chọn:** —",
        "- **Rủi ro đã khai vào sổ:** <R-xx, R-yy, hoặc: chưa>": "- **Rủi ro đã khai vào sổ:** chưa",
    }
    out = []
    for line in template.splitlines():
        out.append(replacements.get(line.rstrip(), line))
    return "\n".join(out) + "\n"


def read_text(path: Path) -> str:
    with open(path, encoding=ENCODING, newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=ENCODING, newline="") as handle:
        handle.write(text)


# --- one decision ----------------------------------------------------------------------------------------------------------

def tally_decision(workspace: Path, directory: Path, cfg: Config, today: str, gate_filter: str | None, template: Path) -> Result | None:
    rel_dir = directory.relative_to(workspace).as_posix()
    result = Result(directory.name)
    brief_path = directory / "brief.md"
    if not brief_path.is_file():
        result.problems.append(Problem(f"{rel_dir}/brief.md", "brief-missing", "không có brief.md"))
        return result
    brief, problems = parse_brief(read_text(brief_path), directory.name, f"{rel_dir}/brief.md")
    if brief is None:
        result.problems += problems
        return result
    if gate_filter and brief.gate != gate_filter:
        return None
    if brief.size not in cfg.sizes:
        result.problems.append(Problem(f"{rel_dir}/brief.md", "brief-council-size", f"council_size {brief.size} không có trong {sorted(cfg.sizes)}"))
        return result
    if brief.gate not in cfg.gates:
        result.warnings.append(Problem(f"{rel_dir}/brief.md", "brief-gate", f"gate {brief.gate} không nằm trong {', '.join(cfg.gates)} (gate có hội đồng)"))
    if len(brief.options) < 1:
        return result
    expected = cfg.sizes[brief.size]
    votes_dir = directory / "votes"
    found: dict[tuple[int, str], list[Path]] = {}
    if votes_dir.is_dir():
        for path in sorted(votes_dir.iterdir()):
            if not path.is_file() or path.name.startswith(".") or path.suffix != ".md" or path.name == SUMMARY_NAME:
                continue
            parsed = parse_vote_name(path.name, cfg.perspectives)
            if parsed is None:
                result.problems.append(Problem(f"{rel_dir}/votes/{path.name}", "vote-file-name", "tên file phiếu phải là r<1|2>-<góc-nhìn>-<member>.md (góc nhìn: " + ", ".join(cfg.perspectives) + ")"))
            else:
                found.setdefault((parsed[0], parsed[1]), []).append(path)

    def collect(round_no: int) -> tuple[list[Vote], bool]:
        present = any(r == round_no for r, _ in found)
        votes: list[Vote] = []
        for (r, perspective), paths in sorted(found.items()):
            if r == round_no and perspective not in expected:
                result.problems.append(Problem(f"{rel_dir}/votes/{paths[0].name}", "vote-perspective-unexpected", f"hội đồng {brief.size} thành viên không có góc nhìn {perspective}"))
        for perspective in expected:
            paths = found.get((round_no, perspective), [])
            if not paths:
                result.problems.append(Problem(f"{rel_dir}/votes", "vote-missing", f"thiếu phiếu vòng {round_no} của góc nhìn {perspective}"))
            elif len(paths) > 1:
                result.problems.append(Problem(f"{rel_dir}/votes", "vote-duplicate", f"vòng {round_no} góc nhìn {perspective} có {len(paths)} phiếu: {', '.join(p.name for p in paths)}"))
            else:
                path = paths[0]
                _, _, member = parse_vote_name(path.name, cfg.perspectives)  # type: ignore[misc]
                vote, errors, warns = validate_vote(read_text(path), f"{rel_dir}/votes/{path.name}", round_no, perspective, member, brief, cfg)
                result.problems += errors
                result.warnings += warns
                if vote:
                    votes.append(vote)
        return votes, present

    r1, _ = collect(1)
    r2: list[Vote] = []
    r2_present = any(r == 2 for r, _ in found)
    if not any(r == 1 for r, _ in found):
        pass  # collect(1) already reported every missing vote
    elif r2_present:
        r2, _ = collect(2)
    if result.problems:
        return result

    first = winner(r1, brief.options, brief.size)
    if first is not None:
        if r2_present:
            result.problems.append(Problem(f"{rel_dir}/votes", "vote-round2-unneeded", f"vòng 1 đã quá bán ({first}) nên không có vòng 2"))
            return result
        outcome = Outcome("none" if first == NONE else "proposal", option="" if first == NONE else first, rounds=1)
    elif not r2_present:
        outcome = Outcome("wait-round-2", rounds=1)
    else:
        second = winner(r2, brief.options, brief.size)
        if second == NONE:
            outcome = Outcome("none", rounds=2)
        elif second:
            outcome = Outcome("proposal", option=second, rounds=2)
        else:
            outcome = Outcome("no-consensus", leaders=leaders(r2, brief.options), rounds=2)
    result.outcome = outcome

    summary_path = votes_dir / SUMMARY_NAME
    if outcome.kind in ("wait-round-2",) or r2_present:
        text = summary_text(brief.decision, r1)
        if not summary_path.is_file() or read_text(summary_path) != text:
            write_text(summary_path, text)
            result.written.append(f"{rel_dir}/votes/{SUMMARY_NAME}")
    elif summary_path.is_file():
        result.warnings.append(Problem(f"{rel_dir}/votes/{SUMMARY_NAME}", "summary-unneeded", "vòng 1 đã quá bán, r1-summary.md không còn cần"))

    write_text(directory / "tally.md", tally_text(brief, outcome, [r1, r2], today, cfg))
    result.written.append(f"{rel_dir}/tally.md")

    decision_path = directory / "decision.md"
    if decision_path.is_file():
        old = read_text(decision_path)
    else:
        if not template.is_file():
            result.problems.append(Problem(f"{rel_dir}/decision.md", "decision-template", f"không có decision.md và không tìm thấy template {template}"))
            return result
        old = new_decision_text(brief, read_text(template))
    new, error = splice_council(old, lambda begin: council_block(begin, brief, outcome, r1, r2))
    if new is None:
        result.problems.append(Problem(f"{rel_dir}/decision.md", "decision-markers", error + "; không sửa file"))
        return result
    write_text(decision_path, new)
    result.written.append(f"{rel_dir}/decision.md")
    return result


# --- run -------------------------------------------------------------------------------------------------------------------

def discover(workspace: Path, only: str | None) -> list[Path]:
    root = workspace / "decisions"
    if only:
        for path in (Path(only), root / only):
            if path.is_dir() and (path / "brief.md").is_file():
                return [path.resolve()]
        return []
    return sorted(p for p in root.glob("D-*") if p.is_dir()) if root.is_dir() else []


def report(results: list[Result], today: str, gate: str | None) -> str:
    errors = sum(len(r.problems) for r in results)
    lines = [f"# tally_votes {today}", "", f"Gate: {gate or 'tất cả'}. {len(results)} quyết định, {errors} lỗi chặn.", ""]
    for result in results:
        state = result_line(result.outcome) if result.outcome else "không đếm được"
        lines += [f"## {result.name}", "", f"- Kết quả: {state}"]
        lines += [f"- Đã ghi: {path}" for path in result.written]
        lines += [f"- LỖI {p.render()}" for p in result.problems]
        lines += [f"- cảnh báo {p.render()}" for p in result.warnings]
        lines.append("")
    if not results:
        lines += ["Không có quyết định nào để đếm.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--gate", help="count only the decisions of this gate (G3, G4, G7)")
    parser.add_argument("--decision", help="count one decision: its folder name (D-007-name) or path")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="council sizes and limits (default: core/data/council.yaml)")
    parser.add_argument("--template", type=Path, default=DECISION_TEMPLATE, help=argparse.SUPPRESS)
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.gate and not re.fullmatch(r"G\d+", args.gate):
        parser.error("--gate phải có dạng Gn, ví dụ G4")
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    cfg, config_errors = load_config(args.config.resolve())
    if cfg is None:
        for error in config_errors:
            print(f"config error: {error}", file=sys.stderr)
        return 2
    directories = discover(workspace, args.decision)
    if args.decision and not directories:
        print(f"not a decision folder: {args.decision}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    results = []
    for directory in directories:
        result = tally_decision(workspace, directory, cfg, today, args.gate, args.template.resolve())
        if result is not None:
            results.append(result)
    target = workspace / "checks" / f"tally-{today}.md"
    folders = {d.name: d for d in directories}
    files = cr.hash_files(workspace, [p for r in results if r.name in folders for p in sorted(folders[r.name].rglob("*"))])  # after the tally wrote its files
    write_text(target, report(results, today, args.gate) + cr.render("tally_votes.py", not any(r.problems for r in results), files, args.gate or cr.ALL_GATES))
    errors = [(r.name, p) for r in results for p in r.problems]
    print(f"tally_votes: {len(results)} quyết định, {len(errors)} lỗi chặn; báo cáo: {target}")
    for result in results:
        print(f"{result.name}: " + (result_line(result.outcome) if result.outcome else "không đếm được"))
    for name, problem in errors[:SHOWN]:
        print(f"error: {problem.render()}")
    if len(errors) > SHOWN:
        print(f"error: … và {len(errors) - SHOWN} lỗi nữa (xem báo cáo)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
