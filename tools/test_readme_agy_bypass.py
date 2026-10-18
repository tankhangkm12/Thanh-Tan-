"""Chặng D-checklist (việc thêm): the README says, where the person installs for Antigravity, never to run `agy` with
`--dangerously-skip-permissions` when using this plugin.

Measured on 18/10/2026 (agy 1.4.0): in that mode the command still ran and `force_ask` did nothing, so every approval
the plugin asks a person for is skipped. (A separate file: `test_docs_limits.py` is locked.)

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")
USAGE = (REPO / "families" / "software-dev" / "USAGE.md").read_text(encoding="utf-8")
FLAG = "--dangerously-skip-permissions"
NEVER = r"(KHÔNG|Không|không|Đừng|đừng|Cấm|cấm)\s+(bao giờ\s+)?(dùng|chạy|bật)"


def sections(text: str):
    found = list(re.finditer(r"^(#{1,6}) +(.+?)\s*$", text, flags=re.M))
    for index, match in enumerate(found):
        end = len(text)
        for later in found[index + 1 :]:
            if len(later.group(1)) <= len(match.group(1)):
                end = later.start()
                break
        yield match.group(2).replace("`", ""), text[match.end() : end]


def body(text: str, *words: str) -> str:
    for heading, content in sections(text):
        if all(word.lower() in heading.lower() for word in words):
            return content
    pytest.fail(f"no section whose heading mentions {', '.join(words)}")


def test_the_install_step_for_antigravity_forbids_the_flag_in_bold():
    text = body(README, "Bước 2b")
    assert FLAG in text
    assert re.search(rf"\*\*[^*\n]*{NEVER}[^*\n]*{re.escape(FLAG)}[^*\n]*\*\*", text), "a bold sentence, not a footnote"


def test_the_install_step_gives_the_reason_the_person_can_check():
    text = body(README, "Bước 2b")
    assert re.search(r"force_ask", text) and re.search(r"18/10/2026|agy 1\.4\.0", text)


def test_the_antigravity_limits_section_of_the_readme_forbids_the_flag_too():
    text = body(README, "Antigravity", "giới hạn")
    assert re.search(rf"{NEVER}.{{0,80}}{re.escape(FLAG)}|{re.escape(FLAG)}.{{0,120}}{NEVER}", text, flags=re.S)


def test_usage_forbids_the_flag_in_its_antigravity_limits():
    text = body(USAGE, "Antigravity", "giới hạn")
    assert FLAG in text
    assert re.search(rf"{NEVER}.{{0,80}}{re.escape(FLAG)}|{re.escape(FLAG)}.{{0,120}}{NEVER}", text, flags=re.S)


def test_the_old_soft_wording_is_gone():
    assert "Đừng bật chế độ đó" not in body(README, "Antigravity", "giới hạn"), "replaced by the explicit prohibition"
