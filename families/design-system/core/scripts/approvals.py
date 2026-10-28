"""Gate approvals in state.md, read the way rule 2 writes them (a module, not a script): shared by promote_drafts.py and archive_release.py.

A gate counts as approved when its row of the "Gate" table has the status `đã duyệt`, the user's verbatim words contain
`Gn: duyệt` for that exact gate (G1 does not match G10) and a real date. Every gate before it must be approved too.
"""

import datetime
import re

GATE_RE = re.compile(r"G(10|[0-9])")
APPROVED = "đã duyệt"
WORD = "duyệt"
HEADING_RE = re.compile(r"^##\s+Gate\s*$", re.MULTILINE)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip("`*").strip()).casefold()


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def gate_rows(state_text: str) -> dict[int, dict[str, str]]:
    """{gate number: {status, quote, date}} from the table under `## Gate` (the first row of a gate wins)."""
    match = HEADING_RE.search(state_text)
    if not match:
        return {}
    rest = state_text[match.end():]
    end = re.search(r"^##\s", rest, re.MULTILINE)
    lines = (rest[:end.start()] if end else rest).splitlines()
    header = None
    rows: dict[int, dict[str, str]] = {}
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        row = cells(line)
        if header is None:
            names = [norm(c) for c in row]
            if "gate" in names and "trạng thái" in names:
                header = {name: index for index, name in enumerate(names)}
            continue
        if set("".join(row)) <= set("-: "):
            continue
        row += [""] * (len(header) - len(row))
        gate = GATE_RE.fullmatch(row[header["gate"]].strip("`* "))
        if not gate or int(gate.group(1)) in rows:
            continue

        def pick(*names: str) -> str:
            for name in names:
                for key, index in header.items():
                    if key.startswith(name):
                        return row[index]
            return ""

        rows[int(gate.group(1))] = {"status": pick("trạng thái"), "quote": pick("người dùng nói"), "date": pick("ngày")}
    return rows


def valid_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text.strip().strip("`*").strip())
        return True
    except ValueError:
        return False


def clean_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip("`*").strip().strip("\"'“”‘’").strip())


def problem(rows: dict[int, dict[str, str]], gate: int) -> str | None:
    """Why G<gate> is not approved the way rule 2 asks, or None."""
    row = rows.get(gate)
    if row is None:
        return f"G{gate}: không có dòng trong bảng Gate của state.md"
    if norm(row["status"]) != APPROVED:
        return f"G{gate}: trạng thái \"{row['status'] or 'trống'}\", chưa \"{APPROVED}\""
    pattern = re.compile(rf"(?<![\w-])G{gate}(?![\w-])\s*:\s*{WORD}(?!\w)", re.IGNORECASE)
    if not pattern.search(clean_quote(row["quote"])):
        return f"G{gate}: \"đã duyệt\" nhưng nguyên văn của người dùng (\"{clean_quote(row['quote'])}\") không có \"G{gate}: {WORD}\""
    if not valid_date(row["date"]):
        return f"G{gate}: ngày duyệt không hợp lệ (\"{row['date']}\", cần YYYY-MM-DD)"
    return None


def problems_up_to(state_text: str, gate: int) -> list[str]:
    """Problems of G0 to G<gate>; empty when the user approved every one of them."""
    rows = gate_rows(state_text)
    if not rows:
        return ["state.md: không thấy bảng Gate (mục \"## Gate\" với cột Gate, Trạng thái, Người dùng nói, Ngày)"]
    return [p for g in range(gate + 1) if (p := problem(rows, g))]
