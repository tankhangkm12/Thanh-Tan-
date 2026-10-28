# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Compute the numbers of the design (load, data, objects, instances, cost) from `capacity/*.yaml` and write them.

Nothing here is a constant of a database or a price: row header, alignment, page size, fill factors come from
`capacity/db-constants/<engine>-<major>.yaml` (a `value` with a `source` link each), prices from `pricing.yaml` (a `source`
link and the date looked up each). A constant, price or benchmark without a source is an error, and so is a missing file.

Reads  (`<workspace>/capacity/`): assumptions.yaml, tables.yaml, storage.yaml (optional: none, or `buckets: {}`, means no object storage),
        compute.yaml, pricing.yaml, db-constants/
Writes (`<workspace>/drafts/`): 03-capacity/{workload-model,data-sizing,storage-sizing,compute-sizing,cost-model}.md,
        00-context/assumptions.md, and the numbers of each table in 07-data/databases/<db>/tables.md, only between
        `<!-- BEGIN:calc:<table> -->` and `<!-- END:calc:<table> -->` (the Designer puts an empty pair, "chờ script", in the file).
`--check` writes none of these: it recomputes and compares with what is on disk (what the Reviewer runs).

Milestones (assumptions.yaml `milestones`) must cover the project level of `00-context/project-profile.md`:
S launch, 1y; M + 3y; L + 5y; XL + peak. 1 year = 365 days, 1 month = 365/12 days, 1 day = 86,400 s.

    uv run calc_capacity.py [--workspace DIR] [--constants-dir DIR] [--check]
"""

import argparse
import datetime
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkreport as cr  # noqa: E402
from check_profile import LEVEL_RE  # noqa: E402

ENCODING = "utf-8"
SECONDS_PER_DAY = 86_400
DAYS_PER_YEAR = 365
DAYS_PER_MONTH = DAYS_PER_YEAR / 12
MILESTONES = {"launch": ("Ra mắt", 0), "1y": ("1 năm", 12), "3y": ("3 năm", 36), "5y": ("5 năm", 60), "peak": ("Đỉnh tải", None)}
LEVEL_MILESTONES = {
    "S": ("launch", "1y"),
    "M": ("launch", "1y", "3y"),
    "L": ("launch", "1y", "3y", "5y"),
    "XL": ("launch", "1y", "3y", "5y", "peak"),
}
MODEL = "postgresql-heap"
REQUIRED_CONSTANTS = (
    "page_size_bytes", "page_header_bytes", "item_pointer_bytes", "tuple_header_bytes",
    "null_bitmap_bits_per_column", "heap_fillfactor", "varlena_short_header_bytes", "varlena_long_header_bytes",
    "varlena_short_max_bytes", "index_tuple_header_bytes", "btree_leaf_fillfactor", "btree_page_special_bytes",
)
PLATFORMS = ("x86_64", "arm64")
# Links into a source repository must name a release TAG (or a commit), never a branch that moves.
SOURCE_REF = (
    re.compile(r"^https?://github\.com/[^/]+/[^/]+/(?:blob|tree|raw|blame|commits)/(?P<ref>[^/#?]+)/"),
    re.compile(r"^https?://raw\.githubusercontent\.com/[^/]+/[^/]+/(?P<ref>[^/#?]+)/"),
    re.compile(r"^https?://gitlab\.com/.+?/-/(?:blob|tree|raw|blame)/(?P<ref>[^/#?]+)/"),
)
GITWEB_REF = re.compile(r"[?;&](?:hb|h)=(?P<ref>[^;&#]+)")  # git.postgresql.org (gitweb, cgit) and other git.* hosts
BRANCH_NAMES = ("master", "main", "trunk", "develop", "development", "dev", "devel", "head")
PRICE_UNITS = {"compute": "instance-month", "db": "GB-month", "object": "GB-month", "egress": "GB"}
UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
CALC_BLOCK = re.compile(r"(<!--\s*BEGIN:calc:(\S+?)\s*-->)(.*?)(<!--\s*END:calc:\2\s*-->)", re.DOTALL)
PENDING = "chờ script"
ASSUMPTION_ID = re.compile(r"A-[A-Za-z0-9][A-Za-z0-9_-]*")
URL = re.compile(r"https?://\S+")
# The six documents calc_capacity.py writes in full (relative to drafts/ or architecture/); the rest it writes only between calc markers.
OUTPUT_FILES = (
    "00-context/assumptions.md", "03-capacity/workload-model.md", "03-capacity/data-sizing.md", "03-capacity/storage-sizing.md",
    "03-capacity/compute-sizing.md", "03-capacity/cost-model.md",
)
GENERATED = "<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->"


# --- small helpers ------------------------------------------------------------------------------------------------------------

def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def is_url(x) -> bool:
    return isinstance(x, str) and URL.fullmatch(x.strip()) is not None


def is_date(x) -> bool:
    if isinstance(x, datetime.date):
        return True
    try:
        datetime.date.fromisoformat(str(x))
        return isinstance(x, str)
    except ValueError:
        return False


def source_ref(url: str) -> str | None:
    """The branch, tag or commit a link into a source repository points at; None for any other link."""
    for pattern in SOURCE_REF:
        match = pattern.match(url)
        if match:
            return match.group("ref")
    if re.match(r"^https?://git\.[^/]+/", url):
        match = GITWEB_REF.search(url)
        if match:
            return match.group("ref")
    return None


def is_pinned_ref(ref: str) -> bool:
    """A release tag (REL_16_4, v1.2.3) or a full commit id. REL_16_STABLE, master, main are branches."""
    if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        return True
    low = ref.lower()
    if low in BRANCH_NAMES or "stable" in low or "branch" in low:
        return False
    return re.search(r"\d+[._]\d+(?:[._]\d+)*$", ref) is not None


def check_source_link(url: str, where: str, problems: "Problems") -> None:
    ref = source_ref(url)
    if ref is not None and not is_pinned_ref(ref):
        problems.add(where, f"link mã nguồn trỏ nhánh/ref {ref!r}, không phải tag phát hành: dùng tag cố định (ví dụ REL_16_4) hoặc commit để số không đổi theo thời gian ({url})")


def align_up(value: int, alignment: int) -> int:
    return -(-value // alignment) * alignment


def num(x, digits: int = 0) -> str:
    """Thousands separated; a whole number shows without decimals, any other with 2 unless `digits` says otherwise."""
    if digits == 0:
        return f"{round(x):,}" if abs(x - round(x)) < 1e-9 else f"{x:,.2f}"
    return f"{x:,.{digits}f}"


def plain(x) -> str:
    """A value as the author wrote it: 1000 -> 1,000; 0.115 -> 0.115."""
    return f"{int(x):,}" if float(x).is_integer() else f"{x:,}"


def size(nbytes: float) -> str:
    value, unit = float(nbytes), 0
    while value >= 1024 and unit < len(UNITS) - 1:
        value, unit = value / 1024, unit + 1
    return f"{value:,.2f} {UNITS[unit]}"


def with_bytes(nbytes: float) -> str:
    return f"{size(nbytes)} ({nbytes:,.0f} byte)"


def link(url: str) -> str:
    return f"[nguồn]({url})"


class Problems:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")

    def __bool__(self) -> bool:
        return bool(self.items)


def load_yaml(path: Path, problems: Problems, name: str):
    if not path.is_file():
        problems.add(name, f"không có file {path}")
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except yaml.YAMLError as error:
        problems.add(name, f"YAML hỏng: {str(error).splitlines()[0] if str(error) else error}")
        return None
    if not isinstance(data, dict):
        problems.add(name, "gốc của file phải là một mapping")
        return None
    return data


# --- assumptions --------------------------------------------------------------------------------------------------------------

@dataclass
class Assumption:
    id: str
    description: str
    unit: str
    source: str
    value: float | None
    by_milestone: dict[str, float]
    reason: str = ""
    platform: str = ""
    factors: tuple[str, ...] = ()  # derived assumption: value(s) are the product of these A-xx (already resolved into value/by_milestone)


@dataclass
class Assumptions:
    milestones: list[str]
    items: dict[str, Assumption]
    workload: dict[str, str]

    def at(self, ident: str, milestone: str) -> float:
        item = self.items[ident]
        return item.value if item.value is not None else item.by_milestone[milestone]

    def get(self, ident: str, milestone: str, default: float = 0.0) -> float:
        """Like `at`, but a milestone the assumption does not cover gives `default` (e.g. a rate at launch)."""
        item = self.items[ident]
        return item.value if item.value is not None else item.by_milestone.get(milestone, default)


def parse_derived(raw, where: str, problems: Problems) -> tuple[str, ...]:
    """`derived: {product: [A-xx, A-yy, ...]}`: the only form. Every factor is a declared A-xx (checked later), never a bare number."""
    if not isinstance(raw, dict) or set(raw) != {"product"}:
        problems.add(where, "derived phải là {product: [A-xx, A-yy, ...]} (chỉ có product, không có biểu thức khác)")
        return ()
    factors = raw["product"]
    if not isinstance(factors, list) or len(factors) < 2:
        problems.add(where, "derived.product phải là danh sách từ 2 giả định A-xx trở lên")
        return ()
    bad = [f for f in factors if not isinstance(f, str) or not ASSUMPTION_ID.fullmatch(f)]
    if bad:
        problems.add(where, f"derived.product chỉ nhận ID giả định A-xx đã khai, không nhận {', '.join(repr(f) for f in bad)}"
                     + " (hằng số phải khai thành giả định A-xx riêng, có source)")
        return ()
    return tuple(factors)


def resolve_derived(items: dict[str, Assumption], milestones: list[str], name: str, problems: Problems) -> None:
    """Fill value / by_milestone of every derived assumption with the product of its factors (no rounding), nested allowed, no cycles."""
    state: dict[str, str] = {}  # ident -> "busy" | "done"

    def visit(ident: str, trail: list[str]) -> bool:
        item = items[ident]
        if not item.factors or state.get(ident) == "done":
            return True
        if state.get(ident) == "busy":
            problems.add(f"{name}: {ident}", "vòng tham chiếu giữa các giả định dẫn xuất: " + " → ".join(trail + [ident]))
            return False
        state[ident] = "busy"
        ok = True
        for f in item.factors:
            if f not in items:
                problems.add(f"{name}: {ident}", f"derived.product: {f!r} không phải giả định đã khai")
                ok = False
            elif f == ident:
                problems.add(f"{name}: {ident}", "giả định dẫn xuất không được dùng chính nó làm thừa số")
                ok = False
            elif not visit(f, trail + [ident]):
                ok = False
        state[ident] = "done"
        if not ok:
            return False
        parts = [items[f] for f in item.factors]
        if all(p.value is not None for p in parts):
            item.value = math.prod(p.value for p in parts)
        else:
            covered = [m for m in milestones if all(p.value is not None or m in p.by_milestone for p in parts)]
            item.by_milestone = {m: math.prod(p.value if p.value is not None else p.by_milestone[m] for p in parts) for m in covered}
        return True

    for ident in list(items):
        visit(ident, [])


def parse_assumptions(data: dict, level: str | None, problems: Problems) -> Assumptions | None:
    name = "assumptions.yaml"
    start = len(problems.items)
    listed = data.get("milestones")
    if not isinstance(listed, list) or not listed or any(m not in MILESTONES for m in listed) or len(set(listed)) != len(listed):
        problems.add(name, f"milestones phải là danh sách không trùng gồm {', '.join(MILESTONES)}")
        listed = []
    elif "launch" not in listed:
        problems.add(name, "milestones phải có launch")
    else:
        listed = sorted(listed, key=lambda m: list(MILESTONES).index(m))
    if level and listed:
        missing = [m for m in LEVEL_MILESTONES[level] if m not in listed]
        if missing:
            problems.add(name, f"mức {level} cần các mốc {', '.join(LEVEL_MILESTONES[level])}; thiếu {', '.join(missing)}")
    items: dict[str, Assumption] = {}
    raw = data.get("assumptions")
    if not isinstance(raw, list) or not raw:
        problems.add(name, "assumptions phải là danh sách không rỗng")
        raw = []
    for index, entry in enumerate(raw):
        where = f"{name}: assumptions[{index}]"
        if not isinstance(entry, dict):
            problems.add(where, "phải là mapping")
            continue
        ident = entry.get("id")
        if not isinstance(ident, str) or not ASSUMPTION_ID.fullmatch(ident):
            problems.add(where, f"id phải dạng A-<tên>, không phải {ident!r}")
            continue
        where = f"{name}: {ident}"
        if ident in items:
            problems.add(where, "id trùng")
            continue
        for key in ("description", "unit", "source"):
            if key == "source" and "derived" in entry:
                continue
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                problems.add(where, f"thiếu {key}" + (" (nguồn của giả định)" if key == "source" else ""))
        has_value, has_by, has_derived = "value" in entry, "by_milestone" in entry, "derived" in entry
        if has_value + has_by + has_derived != 1:
            problems.add(where, "phải có đúng một trong value, by_milestone hoặc derived")
            continue
        value, by = None, {}
        if has_derived:
            factors = parse_derived(entry["derived"], where, problems)
            if "source" not in entry:  # the formula is the source; a free-text `source` is only a note
                entry = {**entry, "source": ""}
            items[ident] = Assumption(ident, str(entry.get("description", "")), str(entry.get("unit", "")), str(entry["source"]).strip() if isinstance(entry["source"], str) else "",
                                      None, {}, "", "", factors)
            continue
        if has_value:
            if not is_number(entry["value"]) or entry["value"] < 0:
                problems.add(where, "value phải là số không âm")
                continue
            value = entry["value"]
        else:
            mapping = entry["by_milestone"]
            if not isinstance(mapping, dict) or not mapping:
                problems.add(where, "by_milestone phải là mapping không rỗng")
                continue
            for key, v in mapping.items():
                if key not in listed:
                    problems.add(where, f"by_milestone có mốc {key!r} không nằm trong milestones")
                elif not is_number(v) or v < 0:
                    problems.add(where, f"giá trị mốc {key} phải là số không âm")
            by = {k: v for k, v in mapping.items() if k in listed and is_number(v) and v >= 0}
        for key in ("reason", "platform"):
            if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
                problems.add(where, f"{key} phải là chuỗi không rỗng")
        if "platform" in entry and entry["platform"] not in PLATFORMS:
            problems.add(where, f"platform phải là một trong {', '.join(PLATFORMS)}")
        items[ident] = Assumption(ident, str(entry.get("description", "")), str(entry.get("unit", "")), str(entry.get("source", "")), value, by,
                                  str(entry.get("reason", "")).strip(), str(entry.get("platform", "")).strip())
    resolve_derived(items, listed, name, problems)
    workload = data.get("workload")
    wanted = ("dau", "requests_per_user_per_day", "peak_factor", "safety_margin")
    if not isinstance(workload, dict) or any(k not in workload for k in wanted):
        problems.add(name, f"workload phải có {', '.join(wanted)} (mỗi khóa là ID giả định)")
        workload = {}
    else:
        for key in wanted:
            if workload[key] not in items:
                problems.add(name, f"workload.{key}: {workload[key]!r} không phải giả định đã khai")
    if len(problems.items) > start:
        return None
    return Assumptions(listed, items, {k: workload[k] for k in wanted})


# Assumptions every database must declare (assumptions.yaml `database_assumptions.<db>`), because the script does not model
# them: (key, what it is, lowest value, the value that needs a stated reason, whole number, may change by milestone)
DB_ASSUMPTIONS = (
    ("heap_bloat_factor", "hệ số phình của heap (dòng chết, chưa vacuum): dung lượng thực = logic × hệ số", 1, 1, False, True),
    ("index_bloat_factor", "hệ số phình của index", 1, 1, False, True),
    ("wal_bytes", "dung lượng WAL giữ lại (byte)", 0, 0, False, True),
    ("replicas", "số bản sao (replica), mỗi bản giữ đủ dữ liệu và WAL", 0, 0, True, True),
    ("backups", "số bản backup giữ lại, mỗi bản bằng dung lượng dữ liệu thực", 0, 0, True, True),
    ("toast_column_ratio", "tỉ lệ cột độ dài thay đổi vượt ngưỡng TOAST (script chưa mô hình TOAST)", 0, 0, False, False),
    ("maxalign", "MAXALIGN của nền tảng triển khai (byte), phải có trường platform", 1, None, True, False),
)


def parse_database_assumptions(data: dict, assumptions: Assumptions, databases: list["Database"], problems: Problems) -> None:
    """Check `database_assumptions` against the databases of tables.yaml and attach the IDs to each Database."""
    name = "assumptions.yaml"
    block = data.get("database_assumptions")
    names = [db.name for db in databases]
    if not isinstance(block, dict):
        problems.add(name, f"thiếu database_assumptions: mỗi database ({', '.join(names)}) phải khai " + ", ".join(k for k, *_ in DB_ASSUMPTIONS))
        return
    for extra in [k for k in block if k not in names]:
        problems.add(name, f"database_assumptions.{extra} không có trong tables.yaml")
    time_ms = time_milestones(assumptions)
    for db in databases:
        entry = block.get(db.name)
        where = f"{name}: database_assumptions.{db.name}"
        if not isinstance(entry, dict):
            problems.add(where, "thiếu: " + ", ".join(k for k, *_ in DB_ASSUMPTIONS))
            continue
        for key, _, low, zero, whole, by_ms in DB_ASSUMPTIONS:
            ident = entry.get(key)
            kw = f"{where}.{key}"
            if not isinstance(ident, str):
                problems.add(kw, "thiếu (ID giả định, ví dụ A-" + key.replace("_", "-") + ")")
                continue
            if not need_coverage(assumptions, ident, time_ms, kw, problems):
                continue
            item = assumptions.items[ident]
            if item.factors:
                problems.add(kw, f"{ident} là giả định dẫn xuất (derived); giả định của database phải khai bằng value hoặc by_milestone")
                continue
            if item.value is None and not by_ms:
                problems.add(kw, f"{ident} phải là giả định hằng (value), không đổi theo mốc")
                continue
            values = [item.value] if item.value is not None else [item.by_milestone[m] for m in time_ms]
            if any(v < low for v in values) or (whole and any(float(v) != int(v) for v in values)):
                problems.add(kw, f"{ident}: giá trị phải {'là số nguyên ' if whole else ''}từ {low}" + (" trở lên" if key != "toast_column_ratio" else " đến 1"))
            if key == "toast_column_ratio" and any(v > 1 for v in values):
                problems.add(kw, f"{ident}: tỉ lệ phải từ 0 đến 1")
            if zero is not None and any(v == zero for v in values) and not item.reason:
                problems.add(kw, f"{ident} có giá trị {zero:g}: phải có trường reason (lý do) vì đây là giả định \"không có\"")
            if key == "maxalign":
                if item.platform not in PLATFORMS:
                    problems.add(kw, f"{ident}: thiếu platform ({' | '.join(PLATFORMS)})")
                if values and (int(values[0]) <= 0 or int(values[0]) & (int(values[0]) - 1) or values[0] > 64):
                    problems.add(kw, f"{ident}: MAXALIGN phải là lũy thừa của 2, từ 1 đến 64")
        db.refs = {key: entry[key] for key, *_ in DB_ASSUMPTIONS if isinstance(entry.get(key), str)}


def need_coverage(assumptions: Assumptions, ident: str, milestones: list[str], where: str, problems: Problems) -> bool:
    if ident not in assumptions.items:
        problems.add(where, f"{ident!r} không phải giả định đã khai trong assumptions.yaml")
        return False
    item = assumptions.items[ident]
    missing = [m for m in milestones if item.value is None and m not in item.by_milestone]
    if missing:
        problems.add(where, f"giả định {ident} không có giá trị cho mốc {', '.join(missing)}")
        return False
    return True


# --- database constants -------------------------------------------------------------------------------------------------------

@dataclass
class Constants:
    engine: str
    major: int
    looked_up: str
    values: dict[str, dict]
    types: dict[str, dict]

    def v(self, key: str):
        return self.values[key]["value"]


def parse_constants(path: Path, engine: str, major, problems: Problems) -> Constants | None:
    name = f"db-constants/{engine}-{major}.yaml"
    data = load_yaml(path, problems, name)
    if data is None:
        return None
    start = len(problems.items)
    if data.get("db") != engine or str(data.get("major")) != str(major):
        problems.add(name, f"db/major trong file ({data.get('db')!r}/{data.get('major')!r}) không khớp {engine}/{major}")
    if data.get("model") != MODEL:
        problems.add(name, f"model {data.get('model')!r} chưa được hỗ trợ (chỉ có {MODEL})")
    if not is_date(data.get("looked_up")):
        problems.add(name, "thiếu looked_up (ngày tra cứu, YYYY-MM-DD)")
    consts = data.get("constants")
    if not isinstance(consts, dict):
        problems.add(name, "thiếu mục constants")
        consts = {}
    for key in REQUIRED_CONSTANTS:
        entry = consts.get(key)
        if not isinstance(entry, dict) or "value" not in entry:
            problems.add(name, f"thiếu hằng số {key}")
        elif not is_number(entry["value"]) or entry["value"] <= 0:
            problems.add(name, f"hằng số {key}: value phải là số dương")
        elif not is_url(entry.get("source")):
            problems.add(name, f"hằng số {key} thiếu link nguồn (source: https://...)")
        else:
            check_source_link(entry["source"], f"{name}: constants.{key}", problems)
    if "maxalign_bytes" in consts:
        problems.add(name, "maxalign_bytes không là hằng số của DB: MAXALIGN phụ thuộc nền tảng, khai ở assumptions.yaml (database_assumptions.<db>.maxalign, kèm platform và nguồn) rồi xóa khỏi file này")
    types = data.get("types")
    if not isinstance(types, dict) or not types:
        problems.add(name, "thiếu mục types")
        types = {}
    for tname, entry in types.items():
        where = f"{name}: types.{tname}"
        if not isinstance(entry, dict):
            problems.add(where, "phải là mapping")
            continue
        for field_name, label in (("source", "kích thước (source)"), ("align_source", "căn lề (align_source)")):
            if not is_url(entry.get(field_name)):
                problems.add(where, f"thiếu link nguồn cho {label}")
            else:
                check_source_link(entry[field_name], f"{where}.{field_name}", problems)
        if not is_number(entry.get("align")) or entry["align"] < 1:
            problems.add(where, "thiếu align (byte căn lề)")
        if entry.get("variable") is True:
            continue
        if not is_number(entry.get("bytes")) or entry["bytes"] < 1:
            problems.add(where, "thiếu bytes (hoặc variable: true)")
        if "max" in entry and not is_number(entry["max"]):
            problems.add(where, "max phải là số")
    if len(problems.items) > start:
        return None
    return Constants(engine, int(major), str(data["looked_up"]), consts, types)


# --- row and index layout (postgresql-heap) -----------------------------------------------------------------------------------

@dataclass
class Column:
    name: str
    type: str
    nullable: bool
    avg_ref: str | None
    reason: str
    counter: bool


@dataclass
class Index:
    name: str
    columns: list[str]


@dataclass
class Table:
    name: str
    id: str
    rate: str
    initial_rows: int
    retention_days: int | None
    columns: list[Column]
    indexes: list[Index]


@dataclass
class Database:
    name: str
    engine: str
    major: int
    price_item: str
    tables: list[Table]
    refs: dict[str, str] = field(default_factory=dict)  # database_assumptions of assumptions.yaml: key -> assumption ID


@dataclass
class Placed:
    name: str
    type: str
    size: float
    align: int
    pad: int
    reason: str
    note: str = ""


def place(columns: list[tuple[str, str, float | None, str, str]], consts: Constants, start_offset: int = 0) -> tuple[list[Placed], int]:
    """Lay columns out one after another, padding each to its alignment. (name, type, avg bytes, reason, note) -> placed, end offset."""
    placed, offset = [], start_offset
    short_max, short_header, long_header = consts.v("varlena_short_max_bytes"), consts.v("varlena_short_header_bytes"), consts.v("varlena_long_header_bytes")
    for name, tname, avg, reason, note in columns:
        t = consts.types[tname]
        if t.get("variable"):
            short = avg <= short_max
            nbytes, alignment = (short_header if short else long_header) + avg, (1 if short else int(t["align"]))
        else:
            nbytes, alignment = t["bytes"], int(t["align"])
        pad = (-offset) % alignment
        offset += pad + nbytes
        placed.append(Placed(name, tname, nbytes, alignment, pad, reason, note))
    return placed, offset


@dataclass
class RowLayout:
    columns: list[Placed]
    bitmap_bytes: int
    header_bytes: int
    t_hoff: int
    data_bytes: float
    tail_pad: float
    tuple_bytes: float
    row_bytes: float
    rows_per_page: int
    maxalign: int = 8


def row_layout(table: Table, avg: dict[str, float], consts: Constants, maxalign: int) -> RowLayout:
    bitmap = math.ceil(len(table.columns) * consts.v("null_bitmap_bits_per_column") / 8) if any(c.nullable for c in table.columns) else 0
    t_hoff = align_up(int(consts.v("tuple_header_bytes")) + bitmap, maxalign)
    cols = [(c.name, c.type, avg.get(c.name), c.reason, "") for c in table.columns]
    placed, end = place(cols, consts)
    tuple_bytes = align_up(math.ceil(t_hoff + end), maxalign)
    row_bytes = tuple_bytes + consts.v("item_pointer_bytes")
    usable = (consts.v("page_size_bytes") - consts.v("page_header_bytes")) * consts.v("heap_fillfactor")
    return RowLayout(placed, bitmap, int(consts.v("tuple_header_bytes")), t_hoff, end, tuple_bytes - t_hoff - end, tuple_bytes, row_bytes, max(1, int(usable // row_bytes)), maxalign)


@dataclass
class IndexLayout:
    name: str
    columns: list[str]
    entry_bytes: float
    entries_per_page: int


def index_layout(index: Index, table: Table, avg: dict[str, float], consts: Constants, maxalign: int) -> IndexLayout:
    by_name = {c.name: c for c in table.columns}
    cols = [(n, by_name[n].type, avg.get(n), "", "") for n in index.columns]
    _, end = place(cols, consts)
    entry = align_up(math.ceil(consts.v("index_tuple_header_bytes") + end), maxalign) + consts.v("item_pointer_bytes")
    usable = (consts.v("page_size_bytes") - consts.v("page_header_bytes") - consts.v("btree_page_special_bytes")) * consts.v("btree_leaf_fillfactor")
    return IndexLayout(index.name, index.columns, entry, max(1, int(usable // entry)))


# --- inputs -------------------------------------------------------------------------------------------------------------------

@dataclass
class Bucket:
    name: str
    id: str
    files: str
    avg_bytes: str
    retention_days: int | None
    views: str | None
    storage_price: str
    egress_price: str | None


@dataclass
class Service:
    name: str
    id: str
    share: float
    capacity: float
    capacity_source: str
    utilization: float
    min_instances: int
    price_item: str


@dataclass
class Pricing:
    currency: str
    gb_bytes: float
    gb_source: str
    items: dict[str, dict]


@dataclass
class Inputs:
    level: str | None
    assumptions: Assumptions
    databases: list[Database]
    constants: dict[tuple[str, int], Constants]
    buckets: list[Bucket]
    services: list[Service]
    pricing: Pricing


def require_str(entry: dict, key: str, where: str, problems: Problems) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.add(where, f"thiếu {key}")
        return ""
    return value


def optional_days(entry: dict, where: str, problems: Problems) -> int | None:
    value = entry.get("retention_days")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        problems.add(where, "retention_days phải là số nguyên dương")
        return None
    return value


def parse_tables(data: dict, assumptions: Assumptions, constants_dir: Path, problems: Problems):
    name = "tables.yaml"
    databases, constants = [], {}
    time_ms = [m for m in assumptions.milestones if MILESTONES[m][1] is not None]
    raw = data.get("databases")
    if not isinstance(raw, dict) or not raw:
        problems.add(name, "databases phải là mapping không rỗng")
        return databases, constants
    seen_ids: set[str] = set()
    for db_name, db in raw.items():
        where = f"{name}: databases.{db_name}"
        if not isinstance(db, dict):
            problems.add(where, "phải là mapping")
            continue
        engine, major = db.get("engine"), db.get("major")
        price_item = require_str(db, "price_item", where, problems)
        if not isinstance(engine, str) or not isinstance(major, int) or isinstance(major, bool):
            problems.add(where, "thiếu engine (chuỗi) hoặc major (số nguyên)")
            continue
        key = (engine, major)
        if key not in constants:
            consts = parse_constants(constants_dir / f"{engine}-{major}.yaml", engine, major, problems)
            if consts is None:
                continue
            constants[key] = consts
        consts = constants[key]
        tables = []
        raw_tables = db.get("tables")
        if not isinstance(raw_tables, dict) or not raw_tables:
            problems.add(where, "tables phải là mapping không rỗng")
            continue
        for t_name, t in raw_tables.items():
            tw = f"{where}.tables.{t_name}"
            if not isinstance(t, dict):
                problems.add(tw, "phải là mapping")
                continue
            t_id = require_str(t, "id", tw, problems)
            if t_id and not re.fullmatch(r"TBL-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*", t_id):
                problems.add(tw, f"id phải dạng TBL-<tên>, không phải {t_id!r}")
            if t_id in seen_ids:
                problems.add(tw, f"id {t_id} trùng")
            seen_ids.add(t_id)
            rate = require_str(t, "rows_per_day", tw, problems)
            if rate:
                need_coverage(assumptions, rate, time_ms[1:], f"{tw}.rows_per_day", problems)
            initial = t.get("initial_rows", 0)
            if not isinstance(initial, int) or isinstance(initial, bool) or initial < 0:
                problems.add(tw, "initial_rows phải là số nguyên không âm")
                initial = 0
            cols, col_names = [], set()
            raw_cols = t.get("columns")
            if not isinstance(raw_cols, list) or not raw_cols:
                problems.add(tw, "columns phải là danh sách không rỗng")
                continue
            for i, c in enumerate(raw_cols):
                cw = f"{tw}.columns[{i}]"
                if not isinstance(c, dict):
                    problems.add(cw, "phải là mapping")
                    continue
                c_name, c_type = require_str(c, "name", cw, problems), require_str(c, "type", cw, problems)
                reason = require_str(c, "reason", cw, problems)
                if c_name in col_names:
                    problems.add(cw, f"cột {c_name} trùng")
                col_names.add(c_name)
                if c_type and c_type not in consts.types:
                    problems.add(cw, f"kiểu {c_type!r} không có trong db-constants/{engine}-{major}.yaml")
                    continue
                avg_ref = c.get("avg_bytes")
                is_var = bool(c_type) and bool(consts.types[c_type].get("variable"))
                if is_var:
                    if not isinstance(avg_ref, str):
                        problems.add(cw, f"kiểu {c_type} độ dài thay đổi cần avg_bytes (ID giả định)")
                        continue
                    if not need_coverage(assumptions, avg_ref, time_ms, f"{cw}.avg_bytes", problems):
                        continue
                    if assumptions.items[avg_ref].value is None:
                        problems.add(cw, f"avg_bytes {avg_ref} phải là giả định hằng (value), không đổi theo mốc")
                        continue
                elif avg_ref is not None:
                    problems.add(cw, f"avg_bytes chỉ dùng cho kiểu độ dài thay đổi, không phải {c_type}")
                counter = c.get("counter") is True
                if counter and "max" not in consts.types.get(c_type, {}):
                    problems.add(cw, f"counter: true cần kiểu có max trong db-constants (kiểu {c_type} không có)")
                    continue
                cols.append(Column(c_name, c_type, c.get("nullable") is True, avg_ref, reason, counter))
            indexes = []
            for i, ix in enumerate(t.get("indexes") or []):
                iw = f"{tw}.indexes[{i}]"
                if not isinstance(ix, dict) or not require_str(ix, "name", iw, problems) or not isinstance(ix.get("columns"), list) or not ix["columns"]:
                    problems.add(iw, "cần name và columns (danh sách)")
                    continue
                unknown = [n for n in ix["columns"] if n not in col_names]
                if unknown:
                    problems.add(iw, f"cột không có trong bảng: {', '.join(map(str, unknown))}")
                    continue
                indexes.append(Index(ix["name"], list(ix["columns"])))
            tables.append(Table(str(t_name), t_id, rate, initial, optional_days(t, tw, problems), cols, indexes))
        databases.append(Database(str(db_name), engine, major, price_item, tables))
    return databases, constants


def parse_storage(data: dict, assumptions: Assumptions, problems: Problems) -> list[Bucket]:
    name = "storage.yaml"
    time_ms = [m for m in assumptions.milestones if MILESTONES[m][1] is not None]
    buckets = []
    if "buckets" not in data:
        problems.add(name, "thiếu khóa buckets (không có object storage thì ghi `buckets: {}` hoặc bỏ cả file storage.yaml)")
        return buckets
    raw = data["buckets"]
    if raw is None or raw == {}:
        return buckets  # no object storage: storage-sizing.md says so, and the object storage and egress costs are 0
    if not isinstance(raw, dict):
        problems.add(name, "buckets phải là mapping (rỗng nếu không có object storage)")
        return buckets
    for b_name, b in raw.items():
        where = f"{name}: buckets.{b_name}"
        if not isinstance(b, dict):
            problems.add(where, "phải là mapping")
            continue
        b_id = require_str(b, "id", where, problems)
        if b_id and not re.fullmatch(r"BKT-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*", b_id):
            problems.add(where, f"id phải dạng BKT-<tên>, không phải {b_id!r}")
        files, avg = require_str(b, "files_per_day", where, problems), require_str(b, "avg_file_bytes", where, problems)
        if files:
            need_coverage(assumptions, files, time_ms[1:], f"{where}.files_per_day", problems)
        if avg:
            need_coverage(assumptions, avg, time_ms, f"{where}.avg_file_bytes", problems)
        views = b.get("views_per_day")
        if views is not None:
            need_coverage(assumptions, views, time_ms[1:], f"{where}.views_per_day", problems)
        price = require_str(b, "storage_price_item", where, problems)
        egress = b.get("egress_price_item")
        if views is not None and not egress:
            problems.add(where, "có views_per_day thì cần egress_price_item")
        buckets.append(Bucket(str(b_name), b_id, files, avg, optional_days(b, where, problems), views, price, egress))
    return buckets


def parse_compute(data: dict, problems: Problems) -> list[Service]:
    name = "compute.yaml"
    services = []
    raw = data.get("services")
    if not isinstance(raw, dict) or not raw:
        problems.add(name, "services phải là mapping không rỗng")
        return services
    for s_name, s in raw.items():
        where = f"{name}: services.{s_name}"
        if not isinstance(s, dict):
            problems.add(where, "phải là mapping")
            continue
        s_id = require_str(s, "id", where, problems)
        if s_id and not re.fullmatch(r"SVC-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*", s_id):
            problems.add(where, f"id phải dạng SVC-<tên>, không phải {s_id!r}")
        share, util, minimum = s.get("traffic_share"), s.get("target_utilization"), s.get("min_instances")
        if not is_number(share) or not 0 < share <= 1:
            problems.add(where, "traffic_share phải trong (0, 1]")
        if not is_number(util) or not 0 < util <= 1:
            problems.add(where, "target_utilization phải trong (0, 1]")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            problems.add(where, "min_instances phải là số nguyên từ 1")
        cap = s.get("requests_per_second_per_instance")
        if not isinstance(cap, dict) or not is_number(cap.get("value")) or cap["value"] <= 0:
            problems.add(where, "requests_per_second_per_instance cần value là số dương")
            cap = {}
        elif not (is_url(cap.get("source")) or (isinstance(cap.get("source"), str) and cap["source"].strip())):
            problems.add(where, "requests_per_second_per_instance thiếu source (link benchmark hoặc tài liệu)")
        price = require_str(s, "price_item", where, problems)
        services.append(Service(str(s_name), s_id, share if is_number(share) else 0, cap.get("value", 0), str(cap.get("source", "")), util if is_number(util) else 0, minimum if isinstance(minimum, int) else 0, price))
    return services


def parse_pricing(data: dict, problems: Problems) -> Pricing | None:
    name = "pricing.yaml"
    start = len(problems.items)
    gb = data.get("gb_bytes")
    if not isinstance(gb, dict) or not is_number(gb.get("value")) or gb["value"] <= 0 or not is_url(gb.get("source")):
        problems.add(name, "gb_bytes cần value (số byte của 1 GB trong bảng giá) và source (link)")
        gb = {}
    items = data.get("items")
    if not isinstance(items, dict) or not items:
        problems.add(name, "items phải là mapping không rỗng")
        items = {}
    for key, item in items.items():
        where = f"{name}: items.{key}"
        if not isinstance(item, dict):
            problems.add(where, "phải là mapping")
            continue
        if not is_number(item.get("unit_price")) or item["unit_price"] < 0:
            problems.add(where, "unit_price phải là số không âm")
        if not isinstance(item.get("unit"), str):
            problems.add(where, "thiếu unit")
        if not is_url(item.get("source")):
            problems.add(where, "thiếu link nguồn của đơn giá (source: https://...)")
        if not is_date(item.get("looked_up")):
            problems.add(where, "thiếu looked_up (ngày tra cứu giá, YYYY-MM-DD)")
    currency = data.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        problems.add(name, "thiếu currency")
    if len(problems.items) > start:
        return None
    return Pricing(currency, gb["value"], gb["source"], items)


def check_price(pricing: Pricing, ident: str, kind: str, where: str, problems: Problems) -> None:
    item = pricing.items.get(ident)
    if item is None:
        problems.add(where, f"đơn giá {ident!r} không có trong pricing.yaml")
    elif item.get("unit") != PRICE_UNITS[kind]:
        problems.add(where, f"đơn giá {ident} có unit {item.get('unit')!r}, cần {PRICE_UNITS[kind]!r}")


def read_level(drafts: Path) -> str | None:
    profile = drafts / "00-context" / "project-profile.md"
    if profile.is_file():
        for line in profile.read_text(encoding=ENCODING, errors="replace").splitlines():
            match = LEVEL_RE.match(line)
            if match:
                return match.group(1)
    return None


def load_inputs(workspace: Path, constants_dir: Path, problems: Problems, drafts: Path | None = None) -> Inputs | None:
    """`drafts` is where 00-context/project-profile.md is read from (default <workspace>/drafts)."""
    capacity, drafts = workspace / "capacity", drafts or workspace / "drafts"
    level = read_level(drafts)
    raw = {n: load_yaml(capacity / f"{n}.yaml", problems, f"{n}.yaml") for n in ("assumptions", "tables", "compute", "pricing")}
    # storage.yaml is optional: a project with no object storage has no such file (or has `buckets: {}`)
    raw["storage"] = load_yaml(capacity / "storage.yaml", problems, "storage.yaml") if (capacity / "storage.yaml").is_file() else {"buckets": {}}
    # Check everything that can be checked, so one run lists all the problems.
    assumptions = parse_assumptions(raw["assumptions"], level, problems) if raw["assumptions"] is not None else None
    pricing = parse_pricing(raw["pricing"], problems) if raw["pricing"] is not None else None
    services = parse_compute(raw["compute"], problems) if raw["compute"] is not None else []
    databases, constants, buckets = [], {}, []
    if assumptions is not None:
        for key, ident in assumptions.workload.items():
            need_coverage(assumptions, ident, assumptions.milestones, f"assumptions.yaml: workload.{key}", problems)
        if raw["tables"] is not None:
            databases, constants = parse_tables(raw["tables"], assumptions, constants_dir, problems)
        if raw["storage"] is not None:
            buckets = parse_storage(raw["storage"], assumptions, problems)
        if databases:
            parse_database_assumptions(raw["assumptions"], assumptions, databases, problems)
    if pricing is not None:
        for db in databases:
            check_price(pricing, db.price_item, "db", f"tables.yaml: databases.{db.name}.price_item", problems)
        for b in buckets:
            check_price(pricing, b.storage_price, "object", f"storage.yaml: buckets.{b.name}.storage_price_item", problems)
            if b.egress_price:
                check_price(pricing, b.egress_price, "egress", f"storage.yaml: buckets.{b.name}.egress_price_item", problems)
        for s in services:
            check_price(pricing, s.price_item, "compute", f"compute.yaml: services.{s.name}.price_item", problems)
    if sum(s.share for s in services) > 1 + 1e-9:
        problems.add("compute.yaml", f"tổng traffic_share của các service là {sum(s.share for s in services):g}, vượt 1")
    if problems:
        return None
    return Inputs(level, assumptions, databases, constants, buckets, services, pricing)


# --- computing ----------------------------------------------------------------------------------------------------------------

def days_of(milestone: str) -> int:
    return MILESTONES[milestone][1] * DAYS_PER_YEAR // 12


def time_milestones(a: Assumptions) -> list[str]:
    return [m for m in a.milestones if MILESTONES[m][1] is not None]


def series(a: Assumptions, rate_id: str, initial: int, retention: int | None, ms: list[str]) -> dict[str, dict]:
    """Rows (or files) at each milestone. A rate is the average per day over the period that ends at its milestone."""
    out, cumulative = {}, float(initial)
    for index, m in enumerate(ms):
        rate = a.at(rate_id, m) if index else 0
        if index:
            cumulative += rate * (days_of(m) - days_of(ms[index - 1]))
        live = cumulative if retention is None else min(cumulative, initial + rate * retention)
        out[m] = {"rate": rate, "inserted": cumulative, "live": live}
    return out


def compute_workload(a: Assumptions) -> dict[str, dict]:
    w, out = a.workload, {}
    for m in a.milestones:
        dau, rpu = a.at(w["dau"], m), a.at(w["requests_per_user_per_day"], m)
        peak, margin = a.at(w["peak_factor"], m), a.at(w["safety_margin"], m)
        per_day = dau * rpu
        avg = per_day / SECONDS_PER_DAY
        out[m] = {"dau": dau, "rpu": rpu, "per_day": per_day, "avg_rps": avg, "peak_factor": peak, "peak_rps": avg * peak,
                  "margin": margin, "peak_rps_margin": avg * peak * (1 + margin)}
    return out


def compute_tables(inputs: Inputs, problems: Problems) -> dict[tuple[str, str], dict]:
    a, ms = inputs.assumptions, time_milestones(inputs.assumptions)
    results = {}
    for db in inputs.databases:
        consts = inputs.constants[(db.engine, db.major)]
        maxalign = int(a.at(db.refs["maxalign"], ms[0]))
        for t in db.tables:
            avg = {c.name: a.at(c.avg_ref, ms[0]) for c in t.columns if c.avg_ref}
            layout = row_layout(t, avg, consts, maxalign)
            indexes = [index_layout(ix, t, avg, consts, maxalign) for ix in t.indexes]
            rows = series(a, t.rate, t.initial_rows, t.retention_days, ms)
            page = consts.v("page_size_bytes")
            by_ms = {}
            for m in ms:
                live = math.ceil(rows[m]["live"])
                heap = math.ceil(live / layout.rows_per_page) * page if live else 0
                idx = [math.ceil(live / il.entries_per_page) * page if live else 0 for il in indexes]
                heap_factor, index_factor = a.at(db.refs["heap_bloat_factor"], m), a.at(db.refs["index_bloat_factor"], m)
                by_ms[m] = {**rows[m], "live_rows": live, "heap_pages": heap // page, "heap_bytes": heap, "index_bytes": idx, "total_bytes": heap + sum(idx),
                            "bloated_bytes": heap * heap_factor + sum(idx) * index_factor}
            counters = []
            far = ms[-1]
            for c in t.columns:
                if not c.counter:
                    continue
                tp = consts.types[c.type]
                inserted = rows[far]["inserted"]
                margin = a.at(a.workload["safety_margin"], far)
                need = inserted * (1 + margin)
                rate = rows[far]["rate"]
                left_years = (tp["max"] - inserted) / (rate * DAYS_PER_YEAR) if rate > 0 else math.inf
                family = sorted((n for n, x in consts.types.items() if x.get("family") == tp.get("family") and "max" in x), key=lambda n: consts.types[n]["max"])
                smallest = next((n for n in family if consts.types[n]["max"] >= need), None)
                ok = need <= tp["max"]
                if not ok:
                    problems.add(f"tables.yaml: {db.name}.{t.name}.{c.name}", f"kiểu {c.type} (tối đa {tp['max']:,}) không đủ: cần {need:,.0f} giá trị ở mốc {far} (đã cộng biên an toàn {margin:g})"
                                 + (f"; kiểu nhỏ nhất đủ là {smallest}" if smallest else ""))
                counters.append({"column": c.name, "type": c.type, "max": tp["max"], "inserted": inserted, "need": need, "margin": margin, "left_years": left_years, "ok": ok,
                                 "smallest": smallest, "milestone": far})
            results[(db.name, t.name)] = {"layout": layout, "indexes": indexes, "by_ms": by_ms, "counters": counters, "avg": avg}
    return results


def compute_provisioned(inputs: Inputs, tables: dict) -> dict[str, dict[str, dict]]:
    """Storage to provision per database and milestone: (data after bloat + WAL) x (1 + replicas) + backups x data after bloat."""
    a, ms = inputs.assumptions, time_milestones(inputs.assumptions)
    out = {}
    for db in inputs.databases:
        per_ms = {}
        for m in ms:
            heap = sum(tables[(db.name, t.name)]["by_ms"][m]["heap_bytes"] for t in db.tables)
            index = sum(sum(tables[(db.name, t.name)]["by_ms"][m]["index_bytes"]) for t in db.tables)
            heap_factor, index_factor = a.at(db.refs["heap_bloat_factor"], m), a.at(db.refs["index_bloat_factor"], m)
            wal, replicas, backups = a.at(db.refs["wal_bytes"], m), int(a.at(db.refs["replicas"], m)), int(a.at(db.refs["backups"], m))
            data = heap * heap_factor + index * index_factor
            primary = data + wal
            per_ms[m] = {"logical": heap + index, "heap_factor": heap_factor, "index_factor": index_factor, "data": data, "wal": wal, "primary": primary,
                         "replicas": replicas, "cluster": primary * (1 + replicas), "backups": backups, "backup_bytes": backups * data,
                         "total": primary * (1 + replicas) + backups * data}
        out[db.name] = per_ms
    return out


def compute_storage(inputs: Inputs) -> dict[str, dict]:
    a, ms = inputs.assumptions, time_milestones(inputs.assumptions)
    out = {}
    for b in inputs.buckets:
        files = series(a, b.files, 0, b.retention_days, ms)
        by_ms = {}
        for m in ms:
            avg = a.at(b.avg_bytes, m)
            views = a.get(b.views, m) if b.views else 0
            by_ms[m] = {**files[m], "avg_bytes": avg, "stored_bytes": files[m]["live"] * avg, "views_per_day": views,
                        "egress_month": views * avg * DAYS_PER_MONTH}
        out[b.name] = by_ms
    return out


def compute_instances(inputs: Inputs, workload: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for s in inputs.services:
        per_ms = {}
        for m in inputs.assumptions.milestones:
            rps = workload[m]["peak_rps_margin"] * s.share
            effective = s.capacity * s.utilization
            needed = math.ceil(rps / effective) if rps > 0 else 0
            per_ms[m] = {"rps": rps, "effective": effective, "needed": needed, "instances": max(s.min_instances, needed)}
        out[s.name] = per_ms
    return out


def compute_cost(inputs: Inputs, provisioned: dict, storage: dict, instances: dict) -> dict[str, dict]:
    a, pricing = inputs.assumptions, inputs.pricing
    price = lambda ident: pricing.items[ident]["unit_price"]  # noqa: E731
    out = {}
    for m in a.milestones:
        parts, timed = {}, MILESTONES[m][1] is not None
        parts["compute"] = sum(instances[s.name][m]["instances"] * price(s.price_item) for s in inputs.services)
        if timed:
            parts["db"] = sum(provisioned[db.name][m]["total"] / pricing.gb_bytes * price(db.price_item) for db in inputs.databases)
            parts["object"] = sum(storage[b.name][m]["stored_bytes"] / pricing.gb_bytes * price(b.storage_price) for b in inputs.buckets)
            parts["egress"] = sum(storage[b.name][m]["egress_month"] / pricing.gb_bytes * price(b.egress_price) for b in inputs.buckets if b.egress_price)
        out[m] = {**parts, "total": sum(parts.values())}
    return out


# --- writing the documents ----------------------------------------------------------------------------------------------------

def table_md(header: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"] + ["| " + " | ".join(r) + " |" for r in rows]


def head(title: str, inputs: Inputs, *intro: str) -> list[str]:
    level = f"Mức dự án: {inputs.level}. " if inputs.level else ""
    labels = ", ".join(f"{MILESTONES[m][0]} ({m})" for m in inputs.assumptions.milestones)
    return [f"# {title}", "", GENERATED, "", f"{level}Mốc: {labels}. 1 năm = {DAYS_PER_YEAR} ngày, 1 tháng = {DAYS_PER_YEAR}/12 ngày, 1 ngày = {SECONDS_PER_DAY:,} giây.", "", *intro]


def render_assumptions(a: Assumptions, level: str | None) -> str:
    cols = a.milestones
    rows = []
    has_formula = any(item.factors for item in a.items.values())  # the "Công thức" column exists only when something is derived
    for item in a.items.values():
        values = [item.value if item.value is not None else item.by_milestone.get(m) for m in cols]
        description = item.description + (f" (nền tảng: {item.platform})" if item.platform else "")
        source = item.source + (f"; lý do: {item.reason}" if item.reason else "")
        if has_formula:
            rows.append([item.id, description, item.unit, *["—" if v is None else plain(v) for v in values],
                         " × ".join(item.factors) if item.factors else "—", source or "—"])
        else:
            rows.append([item.id, description, item.unit, *["—" if v is None else plain(v) for v in values], source])
    lines = ["# Giả định", "", GENERATED, "", (f"Mức dự án: {level}. " if level else "") + "Mốc: " + ", ".join(f"{MILESTONES[m][0]} ({m})" for m in cols) + ".", ""]
    lines += table_md(["ID", "Mô tả", "Đơn vị", *[MILESTONES[m][0] for m in cols], *(["Công thức"] if has_formula else []), "Nguồn"], rows)
    return "\n".join(lines) + "\n"


def milestone_header(a: Assumptions) -> list[str]:
    return [MILESTONES[m][0] for m in a.milestones]


def render_workload(inputs: Inputs, w: dict[str, dict]) -> str:
    a = inputs.assumptions
    ids = a.workload
    lines = head("Mô hình tải", inputs,
                 "Công thức: `req/s đỉnh = DAU × request/người/ngày ÷ 86,400 × hệ số đỉnh`; có biên an toàn: `× (1 + biên an toàn)`.",
                 f"Giả định (xem [assumptions.md](../00-context/assumptions.md)): {', '.join(f'{ids[k]}' for k in ids)}.", "")
    f = lambda key, d=0: [num(w[m][key], d) for m in a.milestones]  # noqa: E731
    rows = [
        [f"DAU ({ids['dau']})", "giả định", *f("dau")],
        [f"Request/người/ngày ({ids['requests_per_user_per_day']})", "giả định", *f("rpu")],
        ["Request/ngày", "DAU × request/người/ngày", *f("per_day")],
        ["req/s trung bình", f"request/ngày ÷ {SECONDS_PER_DAY:,}", *f("avg_rps", 2)],
        [f"Hệ số đỉnh ({ids['peak_factor']})", "giả định", *f("peak_factor", 2)],
        ["req/s đỉnh", "req/s trung bình × hệ số đỉnh", *f("peak_rps", 2)],
        [f"Biên an toàn ({ids['safety_margin']})", "giả định", *f("margin", 2)],
        ["req/s đỉnh có biên an toàn", "req/s đỉnh × (1 + biên an toàn)", *f("peak_rps_margin", 2)],
    ]
    return "\n".join(lines + table_md(["Đại lượng", "Công thức", *milestone_header(a)], rows)) + "\n"


def constants_section(consts: Constants, used_types: set[str]) -> list[str]:
    lines = [f"Hằng số của {consts.engine} {consts.major} (file `db-constants/{consts.engine}-{consts.major}.yaml`, tra cứu {consts.looked_up}):", ""]
    rows = [[f"`{k}`", plain(consts.values[k]["value"]), link(consts.values[k]["source"])] for k in REQUIRED_CONSTANTS]
    lines += table_md(["Hằng số", "Giá trị", "Nguồn"], rows) + [""]
    trows = []
    for n in sorted(used_types):
        t = consts.types[n]
        trows.append([f"`{n}`", "thay đổi" if t.get("variable") else f"{t['bytes']} byte", f"{int(t['align'])}", f"{link(t['source'])}, căn lề: {link(t['align_source'])}"])
    return lines + table_md(["Kiểu", "Kích thước", "Căn lề (byte)", "Nguồn"], trows) + [""]


def layout_rows(layout: RowLayout) -> list[list[str]]:
    return [[str(i), p.name, f"`{p.type}`", num(p.size, 0 if float(p.size).is_integer() else 1), str(p.align), str(p.pad), p.reason] for i, p in enumerate(layout.columns, 1)]


def maxalign_text(a: Assumptions, db: Database) -> str:
    ident = db.refs["maxalign"]
    return f"{int(a.items[ident].value)} (giả định {ident}, nền tảng {a.items[ident].platform})"


def layout_summary(layout: RowLayout, consts: Constants, maxalign: str) -> list[str]:
    return [
        f"- Đầu dòng: {layout.header_bytes} byte (`tuple_header_bytes`) + null bitmap {layout.bitmap_bytes} byte, căn lên bội số MAXALIGN {maxalign} → vị trí dữ liệu {layout.t_hoff} byte.",
        f"- Dữ liệu các cột (kể cả đệm căn lề): {layout.data_bytes:,.0f} byte; đệm cuối dòng {layout.tail_pad:,.0f} byte (tuple căn lên bội số MAXALIGN).",
        f"- Độ dài tuple: {layout.tuple_bytes:,.0f} byte; + con trỏ dòng {int(consts.v('item_pointer_bytes'))} byte = **{layout.row_bytes:,.0f} byte/dòng**.",
        f"- Dòng trên một trang: ⌊({int(consts.v('page_size_bytes'))} − {int(consts.v('page_header_bytes'))}) × fillfactor {consts.v('heap_fillfactor'):g} ÷ {layout.row_bytes:,.0f}⌋ = **{layout.rows_per_page}**.",
    ]


def milestone_rows(a: Assumptions, tr: dict, indexes: list[IndexLayout]) -> list[list[str]]:
    rows = []
    for m in time_milestones(a):
        r = tr["by_ms"][m]
        rows.append([MILESTONES[m][0], num(r["rate"], 0 if float(r["rate"]).is_integer() else 2), num(r["inserted"]), num(r["live_rows"]), num(r["heap_pages"]), size(r["heap_bytes"]),
                     ", ".join(f"{il.name}: {size(b)}" for il, b in zip(indexes, r["index_bytes"])) or "—", with_bytes(r["total_bytes"]), with_bytes(r["bloated_bytes"])])
    return rows


MILESTONE_HEADER = ["Mốc", "Dòng/ngày (giai đoạn)", "Dòng đã chèn (tích lũy)", "Dòng đang giữ", "Trang heap", "Heap", "Index", "Tổng logic (heap + index)", "Sau phình (bloat)"]


def counter_lines(tr: dict) -> list[str]:
    lines = []
    for c in tr["counters"]:
        left = "không tăng" if math.isinf(c["left_years"]) else f"còn đủ khoảng {c['left_years']:,.1f} năm sau mốc {c['milestone']}"
        verdict = "ĐỦ" if c["ok"] else "KHÔNG ĐỦ"
        smaller = f"; kiểu nhỏ nhất đủ: `{c['smallest']}`" if c["smallest"] else ""
        lines.append(f"- Cột `{c['column']}` kiểu `{c['type']}` (tối đa {c['max']:,}): cần {c['need']:,.0f} giá trị ở mốc {c['milestone']} "
                     f"(đã chèn {c['inserted']:,.0f} × (1 + biên an toàn {c['margin']:g})); {left} → **{verdict}**{smaller}.")
    return lines


LIMITS = ("Ước lượng theo giá trị trung bình. Hai con số: **dung lượng logic** (heap + index như tính từ dòng và trang) và **dung lượng cần cấp** "
          "(logic × hệ số phình + WAL, nhân bản sao, cộng backup; xem từng database). Chưa mô hình: TOAST (chỉ ghi tỉ lệ đã khai), "
          "bản đồ không gian trống và visibility map, các tầng trong của B-tree, bitmap null của khóa index.")


def render_provisioned(inputs: Inputs, db: Database, prov: dict) -> list[str]:
    a, refs = inputs.assumptions, db.refs
    lines = [f"## {db.name} · dung lượng cần cấp", "",
             "Công thức: `cần cấp = (heap × hệ số phình heap + index × hệ số phình index + WAL) × (1 + số bản sao) + số backup × (heap × hệ số phình heap + index × hệ số phình index)`. "
             "Mỗi bản backup bằng dung lượng dữ liệu sau phình, chưa nén.",
             f"Giả định: hệ số phình heap {refs['heap_bloat_factor']}, hệ số phình index {refs['index_bloat_factor']}, WAL {refs['wal_bytes']}, bản sao {refs['replicas']}, backup {refs['backups']} (xem [assumptions.md](../00-context/assumptions.md)).", ""]
    rows = []
    for m in time_milestones(a):
        p = prov[m]
        rows.append([MILESTONES[m][0], with_bytes(p["logical"]), f"{p['heap_factor']:g} / {p['index_factor']:g}", with_bytes(p["data"]), with_bytes(p["wal"]), str(p["replicas"]),
                     with_bytes(p["cluster"]), str(p["backups"]), with_bytes(p["backup_bytes"]), f"**{with_bytes(p['total'])}**"])
    lines += table_md(["Mốc", "Dung lượng logic", "Hệ số phình heap / index", "Dữ liệu sau phình", "WAL", "Bản sao", "Primary + bản sao", "Backup", "Dung lượng backup", "Cần cấp"], rows) + [""]
    ratio = a.items[refs["toast_column_ratio"]]
    value = ratio.value
    lines += [f"### TOAST (chưa mô hình)", "",
              f"Tỉ lệ cột độ dài thay đổi vượt ngưỡng TOAST đã khai: {value:g} ({refs['toast_column_ratio']}"
              + (f", lý do: {ratio.reason}" if ratio.reason else "") + "). "
              + ("Script chưa mô hình TOAST: phần dữ liệu vượt ngưỡng được nén hoặc lưu ngoài dòng nên số logic ở trên có thể sai ở các cột đó; đo bằng dữ liệu thật trước khi chốt." if value > 0
                 else "Đã khai không có cột vượt ngưỡng, nên không có phần nào chưa được tính."), ""]
    return lines


def render_data(inputs: Inputs, tables: dict, provisioned: dict) -> str:
    a = inputs.assumptions
    lines = head("Dung lượng dữ liệu", inputs,
                 "Công thức: `dung lượng logic = số trang × kích thước trang`; `số trang = ⌈số dòng ÷ dòng trên trang⌉`; `byte/dòng = tuple (đầu dòng + dữ liệu có đệm căn lề, căn lên MAXALIGN) + con trỏ dòng`; index tính theo mục B-tree. MAXALIGN là giả định theo nền tảng, không phải hằng số của DB.",
                 LIMITS, f"Giả định xem [assumptions.md](../00-context/assumptions.md).", "")
    shown: set = set()
    for db in inputs.databases:
        consts = inputs.constants[(db.engine, db.major)]
        used = {c.type for d in inputs.databases if (d.engine, d.major) == (db.engine, db.major) for t in d.tables for c in t.columns}
        if (db.engine, db.major) not in shown:
            shown.add((db.engine, db.major))
            lines += ["## Hằng số đã dùng", ""] + constants_section(consts, used)
        for t in db.tables:
            tr = tables[(db.name, t.name)]
            lines += [f"## {db.name} · {t.name} ({t.id})", "", f"Dòng mới mỗi ngày: {t.rate}; dòng ban đầu: {t.initial_rows:,}; giữ lại: {'mãi mãi' if t.retention_days is None else f'{t.retention_days} ngày'}.", "", "### Bố cục dòng", ""]
            lines += table_md(["#", "Cột", "Kiểu", "Byte", "Căn lề", "Đệm trước", "Lý do"], layout_rows(tr["layout"])) + [""] + layout_summary(tr["layout"], consts, maxalign_text(a, db)) + [""]
            if tr["indexes"]:
                lines += ["### Index (B-tree)", ""] + table_md(["Index", "Cột", "Byte/mục", "Mục/trang"], [[il.name, ", ".join(il.columns), f"{il.entry_bytes:,.0f}", str(il.entries_per_page)] for il in tr["indexes"]]) + [""]
            lines += ["### Theo mốc", ""] + table_md(MILESTONE_HEADER, milestone_rows(a, tr, tr["indexes"])) + [""]
            if tr["counters"]:
                lines += ["### Cột tăng dần", ""] + counter_lines(tr) + [""]
        lines += render_provisioned(inputs, db, provisioned[db.name])
    return "\n".join(lines).rstrip("\n") + "\n"


def render_table_block(inputs: Inputs, db: Database, t: Table, tr: dict) -> str:
    consts = inputs.constants[(db.engine, db.major)]
    a = inputs.assumptions
    lines = ["Tính bởi `calc_capacity.py` (chi tiết và nguồn hằng số: [data-sizing.md](../../../03-capacity/data-sizing.md)). Không sửa tay.", ""]
    lines += table_md(["#", "Cột", "Kiểu", "Byte", "Căn lề", "Đệm trước", "Lý do"], layout_rows(tr["layout"])) + [""] + layout_summary(tr["layout"], consts, maxalign_text(a, db)) + [""]
    if tr["indexes"]:
        lines += table_md(["Index", "Cột", "Byte/mục", "Mục/trang"], [[il.name, ", ".join(il.columns), f"{il.entry_bytes:,.0f}", str(il.entries_per_page)] for il in tr["indexes"]]) + [""]
    lines += table_md(MILESTONE_HEADER, milestone_rows(a, tr, tr["indexes"]))
    if tr["counters"]:
        lines += [""] + counter_lines(tr)
    return "\n".join(lines)


def render_storage(inputs: Inputs, storage: dict) -> str:
    a = inputs.assumptions
    lines = head("Dung lượng object storage", inputs,
                 "Công thức: `file đang giữ = min(file đã tải lên, file/ngày × số ngày giữ)`; `dung lượng = file đang giữ × kích thước trung bình`; `băng thông ra/tháng = lượt xem/ngày × kích thước × (365/12)`.",
                 "Giả định xem [assumptions.md](../00-context/assumptions.md).", "")
    if not inputs.buckets:
        lines += ["Không có object storage: `storage.yaml` không khai bucket nào (hoặc không có file). Dung lượng lưu, băng thông ra và chi phí của chúng bằng 0.", ""]
    for b in inputs.buckets:
        lines += [f"## {b.name} ({b.id})", "", f"File/ngày: {b.files}; kích thước trung bình: {b.avg_bytes}; giữ lại: {'mãi mãi' if b.retention_days is None else f'{b.retention_days} ngày'}; lượt xem/ngày: {b.views or 'không có'}.", ""]
        rows = []
        for m in time_milestones(a):
            r = storage[b.name][m]
            rows.append([MILESTONES[m][0], num(r["rate"]), num(r["inserted"]), num(r["live"]), with_bytes(r["avg_bytes"]), with_bytes(r["stored_bytes"]), num(r["views_per_day"]), with_bytes(r["egress_month"])])
        lines += table_md(["Mốc", "File/ngày (giai đoạn)", "File đã tải lên", "File đang giữ", "Kích thước TB", "Dung lượng lưu", "Lượt xem/ngày", "Băng thông ra/tháng"], rows) + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_compute(inputs: Inputs, instances: dict, workload: dict) -> str:
    a = inputs.assumptions
    lines = head("Năng lực tính toán", inputs,
                 "Công thức: `instance = max(min_instances, ⌈req/s đỉnh có biên an toàn × tỉ lệ lưu lượng ÷ (req/s mỗi instance × mức dùng mục tiêu)⌉)`.",
                 "Tải lấy từ [workload-model.md](workload-model.md); giả định xem [assumptions.md](../00-context/assumptions.md).", "")
    for s in inputs.services:
        origin = link(s.capacity_source) if is_url(s.capacity_source) else f"nguồn: {s.capacity_source}"
        lines += [f"## {s.name} ({s.id})", "", f"Tỉ lệ lưu lượng {s.share:g}; năng lực mỗi instance {s.capacity:g} req/s ({origin}); mức dùng mục tiêu {s.utilization:g}; tối thiểu {s.min_instances} instance.", ""]
        rows = [[MILESTONES[m][0], num(instances[s.name][m]["rps"], 2), num(instances[s.name][m]["effective"], 2), str(instances[s.name][m]["needed"]), f"**{instances[s.name][m]['instances']}**"] for m in a.milestones]
        lines += table_md(["Mốc", "req/s phần của service", "req/s hiệu dụng/instance", "Instance theo tải", "Instance"], rows) + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_cost(inputs: Inputs, cost: dict) -> str:
    a, p = inputs.assumptions, inputs.pricing
    lines = head("Mô hình chi phí", inputs,
                 f"Chi phí theo tháng, đơn vị {p.currency}. Đơn giá lấy từ `pricing.yaml` (1 GB = {int(p.gb_bytes):,} byte, {link(p.gb_source)}); lượng lấy từ [data-sizing.md](data-sizing.md), [storage-sizing.md](storage-sizing.md), [compute-sizing.md](compute-sizing.md).",
                 "Lưu trữ database tính theo **dung lượng cần cấp** (sau phình, cộng WAL, bản sao và backup) với đơn giá lưu trữ của database. Mốc đỉnh tải chỉ tính phần compute.", "", "## Đơn giá", "")
    lines += table_md(["Mục", "Mô tả", "Đơn vị", "Đơn giá", "Nguồn", "Ngày tra cứu"],
                      [[k, v.get("description", ""), v["unit"], f"{v['unit_price']:g}", link(v["source"]), str(v["looked_up"])] for k, v in p.items.items()]) + ["", "## Chi phí mỗi tháng", ""]
    names = [("compute", "Compute (instance × đơn giá)"), ("db", "Lưu trữ database (GB cần cấp × đơn giá)"), ("object", "Object storage (GB × đơn giá)"), ("egress", "Băng thông ra (GB × đơn giá)"), ("total", "**Tổng**")]
    rows = [[label, *[(f"{cost[m][key]:,.2f}" if key in cost[m] else "—") for m in a.milestones]] for key, label in names]
    lines += table_md(["Khoản", *milestone_header(a)], rows) + [""]
    if not inputs.buckets:
        lines += ["Không có object storage: khoản object storage và băng thông ra bằng 0.", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


@dataclass
class Outputs:
    files: dict[str, str] = field(default_factory=dict)  # path relative to drafts/ -> text
    blocks: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)  # (db, table) -> (tables.md path, block text)
    ids: dict[tuple[str, str], str] = field(default_factory=dict)  # (db, table) -> TBL-xx of tables.yaml


def render_all(inputs: Inputs, problems: Problems) -> Outputs:
    a = inputs.assumptions
    workload = compute_workload(a)
    tables = compute_tables(inputs, problems)
    storage = compute_storage(inputs)
    instances = compute_instances(inputs, workload)
    provisioned = compute_provisioned(inputs, tables)
    cost = compute_cost(inputs, provisioned, storage, instances)
    out = Outputs()
    out.files["00-context/assumptions.md"] = render_assumptions(a, inputs.level)
    out.files["03-capacity/workload-model.md"] = render_workload(inputs, workload)
    out.files["03-capacity/data-sizing.md"] = render_data(inputs, tables, provisioned)
    out.files["03-capacity/storage-sizing.md"] = render_storage(inputs, storage)
    out.files["03-capacity/compute-sizing.md"] = render_compute(inputs, instances, workload)
    out.files["03-capacity/cost-model.md"] = render_cost(inputs, cost)
    for db in inputs.databases:
        for t in db.tables:
            out.blocks[(db.name, t.name)] = (f"07-data/databases/{db.name}/tables.md", render_table_block(inputs, db, t, tables[(db.name, t.name)]))
            out.ids[(db.name, t.name)] = t.id
    return out


TBL_HEADING = re.compile(r"^#{1,6}[ 	]+(TBL-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)", re.MULTILINE)


def heading_problems(text: str, table: str, table_id: str) -> str | None:
    """A tables.md that has `### TBL-xx` headings must have the heading of this table's `id`, with its calc pair under it (before the next
    TBL heading). A file with no TBL heading at all is left to the other checks. Returns the problem text or None."""
    headings = list(TBL_HEADING.finditer(text))
    if not headings:
        return None
    mine = [h for h in headings if h.group(1) == table_id]
    if len(mine) != 1:
        return f"tables.yaml đặt id {table_id} cho bảng {table}, nhưng tables.md có {len(mine)} heading `### {table_id}` (cần đúng một; id ở heading phải trùng id trong tables.yaml)"
    start = mine[0].end()
    following = [h.start() for h in headings if h.start() > start]
    end = min(following) if following else len(text)
    if not any(m.group(2) == table and start <= m.start() < end for m in CALC_BLOCK.finditer(text)):
        return f"cặp dấu calc:{table} không nằm dưới heading `### {table_id}` (đặt cặp dấu của bảng ngay dưới heading của chính bảng đó)"
    return None


# --- files --------------------------------------------------------------------------------------------------------------------

def normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def read_text(path: Path) -> str | None:
    return normalize(read_raw(path)) if path.is_file() else None


def read_raw(path: Path) -> str | None:
    """The file exactly as it is, line endings included."""
    if not path.is_file():
        return None
    with path.open(encoding=ENCODING, newline="") as handle:
        return handle.read()


def fill_block(text: str, name: str, content: str) -> tuple[str | None, bool]:
    """Replace what is between the calc markers of `name`. -> (new text or None when the pair is missing, changed)."""
    matches = [m for m in CALC_BLOCK.finditer(text) if m.group(2) == name]
    if len(matches) != 1:
        return None, False
    m = matches[0]
    eol = "\r\n" if "\r\n" in text else "\n"
    new = m.group(1) + eol + content.replace("\n", eol) + eol + m.group(4)
    updated = text[: m.start()] + new + text[m.end() :]
    return updated, updated != text


def apply(outputs: Outputs, drafts: Path, check: bool, problems: Problems) -> tuple[list[str], list[str], list[str]]:
    """Write (or, with check, only compare). -> (written/different files, unchanged files, notes)."""
    changed, same, notes = [], [], []
    for rel, text in outputs.files.items():
        path = drafts / rel
        current = read_text(path)
        if current == text:
            same.append(rel)
            continue
        changed.append(rel)
        if check:
            problems.add(f"drafts/{rel}", "khác kết quả tính lại" if current is not None else "chưa có file")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding=ENCODING, newline="\n")
    pending: dict[str, list[tuple[str, str]]] = {}
    for (db, table), (rel, block) in outputs.blocks.items():
        pending.setdefault(rel, []).append((table, block))
    for rel, items in pending.items():
        path = drafts / rel
        current = read_raw(path)
        if current is None:
            notes.append(f"{rel} chưa có: bỏ qua khối bảng số của {', '.join(t for t, _ in items)} (Designer tạo file rồi đặt cặp dấu).")
            continue
        text, dirty, broken = current, False, False
        for table, block in items:
            db_of = next(db for (db, t), (r, _) in outputs.blocks.items() if t == table and r == rel)
            bad = heading_problems(current, table, outputs.ids[(db_of, table)])
            if bad:
                problems.add(f"drafts/{rel}", bad + "; không ghi khối nào của file này")
                broken = True
                continue
            updated, changed_now = fill_block(text, table, block)
            if updated is None:
                found = sum(1 for m in CALC_BLOCK.finditer(text) if m.group(2) == table)
                problems.add(f"drafts/{rel}", f"cần đúng một cặp dấu <!-- BEGIN:calc:{table} --> ... <!-- END:calc:{table} --> cho bảng {table}, thấy {found}; không ghi khối nào của file này")
                broken = True
                continue
            text, dirty = updated, dirty or changed_now
        if broken:
            continue
        for m in CALC_BLOCK.finditer(current):
            if m.group(2) not in {t for t, _ in items}:
                notes.append(f"{rel}: khối calc:{m.group(2)} không có trong tables.yaml")
        label = f"{rel} (khối calc)"
        if dirty:
            changed.append(label)
            if check:
                problems.add(f"drafts/{rel}", "các khối calc khác kết quả tính lại")
            else:
                with path.open("w", encoding=ENCODING, newline="") as handle:
                    handle.write(text)
        else:
            same.append(label)
    return changed, same, notes


def write_report(workspace: Path, today: str, problems: Problems, changed: list[str], same: list[str], notes: list[str], check: bool, block: str = "") -> Path:
    lines = [f"# calc_capacity {today}", "", f"Chế độ: {'--check (chỉ so sánh, không ghi)' if check else 'ghi'}. {len(problems.items)} lỗi chặn.", "", "## Lỗi chặn", ""]
    lines += [f"- {p}" for p in problems.items] or ["- không có"]
    lines += ["", "## " + ("Khác kết quả tính lại" if check else "Đã ghi"), ""] + ([f"- `{c}`" for c in changed] or ["- không có"])
    lines += ["", "## Không đổi", ""] + ([f"- `{c}`" for c in same] or ["- không có"])
    if notes:
        lines += ["", "## Ghi chú", ""] + [f"- {n}" for n in notes]
    path = workspace / "checks" / f"capacity-{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" + block, encoding=ENCODING, newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--constants-dir", type=Path, help="default: <workspace>/capacity/db-constants")
    parser.add_argument("--check", action="store_true", help="recompute and compare with the files on disk; write nothing but the report")
    parser.add_argument("--assumptions-only", action="store_true", help="only generate 00-context/assumptions.md (G1, before the other yaml exist)")
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    constants_dir = (args.constants_dir or workspace / "capacity" / "db-constants").resolve()
    today = args.date or datetime.date.today().isoformat()
    problems, notes, changed, same = Problems(), [], [], []
    drafts = workspace / "drafts"
    inputs = cr.expand(workspace, ["capacity/**/*"]) + ([p for p in constants_dir.rglob("*") if p.is_file()] if constants_dir.is_dir() else [])
    input_hashes = cr.hash_files(workspace, inputs)  # hashed before the run: an edit during or after it makes the report stale (promote_drafts.py)
    outputs = None
    if args.assumptions_only:
        data = load_yaml(workspace / "capacity" / "assumptions.yaml", problems, "assumptions.yaml")
        parsed = parse_assumptions(data, read_level(drafts), problems) if data is not None else None
        if parsed is not None:
            outputs = Outputs({"00-context/assumptions.md": render_assumptions(parsed, read_level(drafts))})
    else:
        inputs = load_inputs(workspace, constants_dir, problems)
        if inputs is not None:
            if inputs.level is None:
                notes.append("Không đọc được Mức từ 00-context/project-profile.md: chưa kiểm các mốc theo mức dự án.")
            outputs = render_all(inputs, problems)
    if outputs is not None:
        changed, same, extra = apply(outputs, drafts, args.check, problems)
        notes += extra
    outputs_written = [drafts / rel.removesuffix(" (khối calc)") for rel in [*changed, *same]]
    mode = "assumptions-only" if args.assumptions_only else ("check" if args.check else "write")
    files = {**cr.hash_files(workspace, outputs_written), **input_hashes}  # outputs after the write, inputs from before
    report = write_report(workspace, today, problems, changed, same, notes, args.check, cr.render("calc_capacity.py", not problems.items, files, None, mode))
    print(f"calc_capacity: {len(problems.items)} lỗi chặn; {len(changed)} file {'khác' if args.check else 'đã ghi'}, {len(same)} không đổi; báo cáo: {report}")
    for item in problems.items[:25]:
        print(f"error: {item}")
    if len(problems.items) > 25:
        print(f"error: … và {len(problems.items) - 25} lỗi nữa (xem báo cáo)")
    for note in notes:
        print(f"note: {note}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
