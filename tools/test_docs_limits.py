"""Phase D-guard (D6): the documents state what protects the approval on each CLI, what does not, and what was measured.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = {
    "README": REPO / "README.md",
    "USAGE": REPO / "families" / "software-dev" / "USAGE.md",
    "architecture": REPO / "docs" / "architecture.md",
}
CLAUDE_MODES = {"default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"}


def read(name: str) -> str:
    return DOCS[name].read_text(encoding="utf-8")


def sections(text: str):
    """(heading, body) of every section; a body runs to the next heading of the same or a higher level."""
    found = list(re.finditer(r"^(#{1,6}) +(.+?)\s*$", text, flags=re.M))
    for index, match in enumerate(found):
        level = len(match.group(1))
        end = len(text)
        for later in found[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        yield match.group(2).replace("`", ""), text[match.end() : end]


def find(name: str, *words: str) -> str:
    """The body of the first section whose heading holds every word (case-insensitive)."""
    for heading, body in sections(read(name)):
        if all(word.lower() in heading.lower() for word in words):
            return body
    pytest.fail(f"{name} has no section whose heading mentions {', '.join(words)}")


# ---------------------------------------------------------------- Antigravity limits


@pytest.mark.parametrize("name", DOCS)
def test_every_document_has_a_section_on_the_limits_with_antigravity(name):
    find(name, "Antigravity", "giới hạn")


@pytest.mark.parametrize("name", DOCS)
def test_the_antigravity_section_names_the_layer_that_replaces_an_ask_rule(name):
    body = find(name, "Antigravity", "giới hạn")
    assert "force_ask" in body
    assert "hook" in body.lower()


@pytest.mark.parametrize("name", DOCS)
def test_the_antigravity_section_says_there_is_no_ask_rule_and_what_remains_when_commands_are_auto_approved(name):
    body = find(name, "Antigravity", "giới hạn")
    assert re.search(r"không có.{0,60}quy tắc.{0,60}ask|quy tắc.{0,60}ask.{0,60}không có", body, flags=re.S | re.I)
    assert re.search(r"tự duyệt|bypass|always allow", body, flags=re.I)


@pytest.mark.parametrize("name", DOCS)
def test_the_antigravity_section_lists_the_other_layers_that_still_hold(name):
    body = find(name, "Antigravity", "giới hạn")
    assert "thanhtan commit" in body
    assert re.search(r"\.ThanhTan/", body)
    assert re.search(r"secret|bí mật", body, flags=re.I)


def test_the_readme_no_longer_says_antigravity_has_nothing_like_an_ask_rule():
    text = read("README")
    assert "tài liệu của nó không có cú pháp quy tắc tương đương" not in text


# ------------------------------------------------------------- what the hook does and does not read


def test_the_architecture_lists_the_ways_of_calling_thanhtan_that_the_hook_reads():
    body = find("architecture", "bảo vệ") if _has("architecture", "bảo vệ") else read("architecture")
    for form in ("uv run thanhtan", "python -m thanhtan", "uvx", "timeout", "Start-Process"):
        assert form in body, form


def test_the_architecture_lists_what_the_hook_cannot_read():
    text = read("architecture")
    assert re.search(r"biến|variable", text, flags=re.I) and re.search(r"alias", text, flags=re.I)
    assert re.search(r"script", text, flags=re.I) and "python -c" in text


def test_the_architecture_says_when_a_here_document_is_data_and_when_it_is_scanned():
    text = read("architecture")
    assert re.search(r"here-?doc", text, flags=re.I)
    assert "trình thông dịch" in text
    assert re.search(r"(không đọc được|không quét được).{0,200}hỏi|hỏi.{0,200}(không đọc được|không quét được)", text, flags=re.S)
    assert re.search(r"curl.{0,40}\| *(sh|bash)", text)


def test_the_architecture_says_claude_code_has_no_sandbox_on_native_windows():
    text = read("architecture")
    assert re.search(r"sandbox.{0,200}Windows|Windows.{0,200}sandbox", text, flags=re.S | re.I)


def _has(name: str, *words: str) -> bool:
    return any(all(w.lower() in h.lower() for w in words) for h, _ in sections(read(name)))


# ------------------------------------------------- the real trials of a hook that answers ask


def trial_rows() -> tuple[list[str], list[list[str]]]:
    body = find("architecture", "thử thật", "ask")
    table = [line for line in body.splitlines() if line.strip().startswith("|")]
    assert len(table) >= 4, "the trials are not in a table with a header, a separator and at least two rows"
    cells = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table]
    return cells[0], [row for row in cells[2:]]


def test_the_trials_are_recorded_in_a_table_with_the_permission_mode_of_each_one():
    header, rows = trial_rows()
    lowered = [cell.lower() for cell in header]
    for column in ("cli", "phiên bản", "ngày", "chế độ quyền", "lệnh", "kết quả"):
        assert any(column in cell for cell in lowered), column
    mode = next(i for i, cell in enumerate(lowered) if "chế độ quyền" in cell)
    assert all(len(row) == len(header) and row[mode] for row in rows)


def test_there_is_a_trial_for_each_cli_and_each_names_a_version_and_a_date():
    header, rows = trial_rows()
    lowered = [cell.lower() for cell in header]
    cli, version, date = (next(i for i, cell in enumerate(lowered) if word in cell) for word in ("cli", "phiên bản", "ngày"))
    assert {row[cli].lower().split()[0] for row in rows} >= {"claude", "agy"}
    for row in rows:
        assert re.fullmatch(r"v?\d+\.\d+\.\d+", row[version].strip("` ")), row
        assert re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}", row[date]), row


def test_a_claude_trial_names_one_of_the_real_permission_modes_and_agy_names_its_own():
    header, rows = trial_rows()
    lowered = [cell.lower() for cell in header]
    cli = next(i for i, cell in enumerate(lowered) if "cli" in cell)
    mode = next(i for i, cell in enumerate(lowered) if "chế độ quyền" in cell)
    for row in rows:
        if row[cli].lower().startswith("claude"):
            assert any(name in row[mode] for name in CLAUDE_MODES), row
        else:
            assert row[mode].strip("` -—") , row


def test_the_result_column_says_whether_the_prompt_appeared_or_that_it_was_not_tried():
    header, rows = trial_rows()
    lowered = [cell.lower() for cell in header]
    result = next(i for i, cell in enumerate(lowered) if "kết quả" in cell)
    for row in rows:
        assert re.search(r"hỏi|prompt|chặn|không hỏi|chưa kiểm|chưa thử", row[result], flags=re.I), row
