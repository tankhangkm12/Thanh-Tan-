"""Checks that every agent file matches permissions.md, PLAN.md and quality-criteria.md.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import json
import re
from pathlib import Path

import pytest
import yaml

CORE = Path(__file__).resolve().parent.parent
PLAN = CORE.parent / "PLAN.md"
AGENTS = CORE / "claude" / "agents"
COUNCIL = AGENTS / "council"
MANIFEST = CORE / ".claude-plugin" / "plugin.json"
PERMISSIONS = CORE / "workflow" / "permissions.md"
CRITERIA = CORE / "workflow" / "quality-criteria.md"
VOTE_TEMPLATE = CORE / "templates" / "workspace" / "vote.md"

SUBAGENTS = ["planner", "researcher", "designer", "reviewer"]
PERSPECTIVES = {
    # slug -> quality criteria it covers (PLAN.md, "Thành phần, mỗi góc nhìn gắn với tiêu chí chất lượng")
    "fit": ["Q8", "Q1"],
    "cost-ops": ["Q2"],
    "numbers-nfr": ["Q4", "Q1"],
    "evolution": ["Q3", "Q5"],
    "risk-data": ["Q6"],
}
KNOWN_TOOLS = {"Read", "Glob", "Grep", "Write", "Edit", "Bash", "PowerShell", "WebSearch", "WebFetch", "Agent"}
BODY_END = "<!-- body-end -->"
FORMULA = "tổng = Σ(điểm × trọng số) / (5 × Σ trọng số) × 100 − điểm trừ làm quá tay"
# Words a council body must not contain: it is handed as is to a CLI that is not Claude Code.
CLAUDE_ONLY_WORDS = ["Claude", "subagent", "Orchestrator", "Read", "Write", "Bash", "Agent"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def split(path: Path) -> tuple[dict, str]:
    text = read(path)
    assert text.startswith("---\n"), f"{path.name}: no frontmatter"
    head, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(head), body


def tools_of(name: str) -> set[str]:
    meta, _ = split(AGENTS / f"{name}.md")
    return {tool.strip() for tool in meta["tools"].split(",")}


def section(body: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    assert match, f"missing section: {title}"
    return match.group(1)


def all_agent_files() -> list[Path]:
    return sorted(AGENTS.glob("*.md")) + sorted(COUNCIL.glob("*.md"))


def block(text: str, start: str, end: str | None = None) -> str:
    begin = text.index(start)
    stop = text.index(end, begin) if end else len(text)
    return text[begin:stop]


# --- every agent -------------------------------------------------------------------------------


@pytest.mark.parametrize("path", all_agent_files(), ids=lambda p: p.stem)
def test_frontmatter_is_valid_yaml_with_known_tools(path: Path):
    meta, body = split(path)
    assert isinstance(meta, dict)
    expected = f"council-{path.stem}" if path.parent == COUNCIL else path.stem
    assert meta["name"] == expected
    assert str(meta["description"]).strip()
    tools = {tool.strip() for tool in meta["tools"].split(",")}
    assert tools <= KNOWN_TOOLS, tools - KNOWN_TOOLS
    assert body.strip()


@pytest.mark.parametrize("path", all_agent_files(), ids=lambda p: p.stem)
def test_only_the_orchestrator_may_spawn_agents(path: Path):
    meta, _ = split(path)
    tools = {tool.strip() for tool in meta["tools"].split(",")}
    assert ("Agent" in tools) == (path.stem == "orchestrator")


@pytest.mark.parametrize("path", [p for p in all_agent_files() if p.stem != "orchestrator"], ids=lambda p: p.stem)
def test_every_subagent_inherits_model_and_skips_claude_md(path: Path):
    meta, _ = split(path)
    assert meta["model"] == "inherit"
    assert meta["omitClaudeMd"] is True


def test_orchestrator_reads_claude_md():
    meta, _ = split(AGENTS / "orchestrator.md")
    assert meta["model"] == "inherit"
    assert "omitClaudeMd" not in meta


@pytest.mark.parametrize("path", [p for p in all_agent_files() if p.stem != "orchestrator"], ids=lambda p: p.stem)
def test_no_subagent_may_record_an_approval(path: Path):
    _, body = split(path)
    forbidden = section(body.split(BODY_END)[0], "Không được làm").lower()
    assert "duyệt" in forbidden or "đã quyết" in forbidden


# --- tools per role (permissions.md) -----------------------------------------------------------


def test_tools_per_role():
    assert tools_of("planner") == {"Read", "Glob", "Grep", "Write", "Edit"}
    assert tools_of("designer") == {"Read", "Glob", "Grep", "Write", "Edit"}
    assert tools_of("researcher") == {"Read", "Glob", "Grep", "Write", "WebSearch", "WebFetch"}
    assert tools_of("reviewer") == {"Read", "Glob", "Grep", "Write", "Bash"}
    # The Orchestrator has Bash for four kinds of command (guard_write.py) and no PowerShell.
    assert tools_of("orchestrator") == {"Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"}
    for slug in PERSPECTIVES:
        meta, _ = split(COUNCIL / f"{slug}.md")
        assert {tool.strip() for tool in meta["tools"].split(",")} == {"Read", "Write"}


def test_reviewer_cannot_edit_and_only_the_researcher_browses():
    assert "Edit" not in tools_of("reviewer")
    for name in ["orchestrator", "planner", "designer", "reviewer"]:
        assert not tools_of(name) & {"WebSearch", "WebFetch"}, name
    for name in ["planner", "researcher", "designer"]:
        assert not tools_of(name) & {"Bash", "PowerShell"}, name


def permission_row(agent: str) -> list[str]:
    for line in read(PERMISSIONS).splitlines():
        if line.startswith(f"| {agent} "):
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"no permissions row for {agent}")


def paths_in(cell: str) -> set[str]:
    return {token for token in re.findall(r"`([^`]+)`", cell) if "/" in token or token.endswith(".md")}


@pytest.mark.parametrize(
    "agent,row",
    [("Orchestrator", "orchestrator"), ("Planner", "planner"), ("Researcher", "researcher"), ("Designer", "designer"), ("Reviewer", "reviewer")],
)
def test_write_zones_in_permissions_md_appear_in_the_agent_file(agent: str, row: str):
    text = read(AGENTS / f"{row}.md")
    # Only the "Được ghi vào" column, with files that are not written by the agent itself left out.
    written = paths_in(permission_row(agent)[2])
    # `*` in permissions.md stands for any folder name (decisions/*/brief.md is decisions/D-xxx-<tên>/brief.md).
    missing = sorted(
        token for token in written if not re.search(re.escape(token).replace(r"\*", r"[^\s`]*"), text)
    )
    assert not missing, f"{row}.md does not mention {missing} (permissions.md)"


def test_agents_never_get_architecture_or_script_zones():
    for name in ["orchestrator", "planner", "researcher", "designer", "reviewer"]:
        _, body = split(AGENTS / f"{name}.md")
        # Rows of the "Được ghi" table only: the paragraph below it lists the places the agent must NOT write.
        # and only its first column (the place), not the description next to it.
        rows = [line.strip("|").split("|")[0] for line in section(body, "Được ghi").splitlines() if line.startswith("|")]
        # (a section written as a paragraph instead of a table is checked whole).
        written = "\n".join(rows) or section(body, "Được ghi")
        assert "architecture/" not in written, name
        assert "tally.md" not in written, name


def test_orchestrator_records_approvals_only_by_id():
    text = read(AGENTS / "orchestrator.md")
    for example in ["G4: duyệt", "D-007: chọn B", "R-04: chấp nhận", "CH-006:"]:
        assert example in text, example
    for phrase in ["nguyên văn", "hỏi lại", "BEGIN:user", "promote_drafts.py"]:
        assert phrase in text, phrase
    # permissions.md row: the only plan/ write is the "Trạng thái" line.
    assert "duy nhất dòng \"Trạng thái\"" in permission_row("Orchestrator")[2]
    assert "duy nhất dòng \"Trạng thái\"" in text


def test_orchestrator_asks_only_through_known_ids_and_batches_questions():
    text = read(AGENTS / "orchestrator.md")
    for phrase in ["Chỉ có năm kiểu ID", "Không tự đặt kiểu ID khác", "mở `CH-xxx`", "một đợt", "gộp vào chính CH đó", "không mở ID mới", "soát lại bản sửa"]:
        assert phrase in text, phrase


def test_orchestrator_delegation_names_every_agent_and_perspective():
    text = read(AGENTS / "orchestrator.md")
    for name in SUBAGENTS:
        assert f"| {name} |" in text
    for slug in PERSPECTIVES:
        assert f"`{slug}`" in text


def test_isolation_rules_are_stated():
    assert "brief.md" in section(split(AGENTS / "researcher.md")[1], "Được đọc")
    assert "brief.md" in section(split(AGENTS / "reviewer.md")[1], "Được đọc")
    assert "votes/" in section(split(AGENTS / "designer.md")[1], "Được đọc")


# --- manifest ----------------------------------------------------------------------------------


def test_manifest_lists_every_claude_agent_file_and_nothing_else():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed = manifest["agents"]
    expected = sorted(f"./claude/agents/{p.relative_to(AGENTS).as_posix()}" for p in all_agent_files())
    assert sorted(listed) == expected
    for entry in listed:
        assert entry.startswith("./") and (CORE / entry).is_file()


def test_antigravity_agents_dir_has_no_claude_format_files():
    # Antigravity discovers <plugin>/agents/*.md on its own; Claude-format files there could hang it (BUILD-PROGRESS.md).
    # core/agents/ holds only the generated Antigravity files (test_gen_antigravity.py keeps them in step).
    for file in (CORE / "agents").glob("*.md"):
        text = file.read_text(encoding="utf-8")
        assert text.replace("\r\n", "\n").startswith("---\nname: design-"), file.name
        assert not re.search(r"^tools:\s*(Read|Write|Glob|Grep|Edit|Bash|Agent|Web)", text, re.M), file.name


# --- council ----------------------------------------------------------------------------------


def council_body(slug: str) -> str:
    text = read(COUNCIL / f"{slug}.md")
    assert text.count(BODY_END) == 1, slug
    return split(COUNCIL / f"{slug}.md")[1].split(BODY_END)[0]


def test_the_five_perspective_files_exist():
    assert sorted(p.stem for p in COUNCIL.glob("*.md")) == sorted(PERSPECTIVES)


@pytest.mark.parametrize("slug", PERSPECTIVES)
def test_council_body_stands_alone(slug: str):
    body = council_body(slug)
    found = [word for word in CLAUDE_ONLY_WORDS if re.search(rf"\b{word}\b", body)]
    assert not found, f"{slug}: Claude Code terms in the body: {found}"
    assert f"perspective: {slug}" in body


@pytest.mark.parametrize(
    "start,end",
    [
        ("Bạn là một", "## Góc nhìn của bạn"),
        ("## Quy tắc chấm", "## Định dạng phiếu"),
        ("## Không được làm", None),
    ],
    ids=["receives", "rules", "must-not"],
)
def test_shared_blocks_are_identical_in_all_five_files(start: str, end: str | None):
    blocks = {slug: block(council_body(slug), start, end) for slug in PERSPECTIVES}
    assert len(set(blocks.values())) == 1, "the shared block differs between files"


def council_q_blocks(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"<!-- BEGIN:council-q (Q\d) -->\n(.*?)\n<!-- END:council-q \1 -->", text, re.S)
    }


def test_quality_criteria_marks_every_q_once():
    text = read(CRITERIA)
    for number in range(1, 9):
        assert text.count(f"<!-- BEGIN:council-q Q{number} -->") == 1
        assert text.count(f"<!-- END:council-q Q{number} -->") == 1
    assert sorted(council_q_blocks(text)) == [f"Q{n}" for n in range(1, 9)]


@pytest.mark.parametrize("slug", PERSPECTIVES)
def test_q_paragraphs_match_quality_criteria_verbatim(slug: str):
    source = council_q_blocks(read(CRITERIA))
    copied = council_q_blocks(council_body(slug))
    assert sorted(copied) == sorted(PERSPECTIVES[slug]), f"{slug}: wrong set of Q"
    for number, text in copied.items():
        assert text == source[number], f"{slug}: {number} differs from quality-criteria.md"


@pytest.mark.parametrize("slug", PERSPECTIVES)
def test_scoring_formula_matches_plan(slug: str):
    assert FORMULA in read(PLAN)
    assert FORMULA in council_body(slug)


@pytest.mark.parametrize("slug", PERSPECTIVES)
def test_vote_skeleton_has_the_keys_of_the_vote_template(slug: str):
    skeleton = re.search(r"```\n---\n(.*?)\n---\n", council_body(slug), re.S).group(1)
    template_head = read(VOTE_TEMPLATE).split("\n---\n", 1)[0].removeprefix("---\n")
    assert set(yaml.safe_load(skeleton)) == set(yaml.safe_load(template_head))
