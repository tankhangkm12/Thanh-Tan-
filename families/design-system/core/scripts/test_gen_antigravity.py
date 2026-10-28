"""Keeps `core/agents/` (Antigravity) in step with `core/claude/agents/` (Claude Code), through the build script
`families/design-system/tools/gen_antigravity.py`.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest
import yaml

CORE = Path(__file__).resolve().parent.parent
GEN_PATH = CORE.parent / "tools" / "gen_antigravity.py"
AGENTS = CORE / "agents"

spec = importlib.util.spec_from_file_location("gen_antigravity", GEN_PATH)
gen = importlib.util.module_from_spec(spec)
sys.modules["gen_antigravity"] = gen
spec.loader.exec_module(gen)

# Written here on purpose, independent of the mapping tables in the script (BUILD-PROGRESS.md, "Bản Antigravity").
READ = ["view_file", "list_dir", "find_by_name", "grep_search"]
EXPECTED_TOOLS = {
    "design-orchestrator": [*READ, "write_to_file", "replace_file_content", "run_command", "invoke_subagent"],
    "design-planner": [*READ, "write_to_file", "replace_file_content"],
    "design-designer": [*READ, "write_to_file", "replace_file_content"],
    "design-researcher": [*READ, "write_to_file", "search_web", "read_url_content"],
    "design-reviewer": [*READ, "write_to_file", "run_command"],
    **{f"design-council-{slug}": ["view_file", "write_to_file"] for slug in ("fit", "cost-ops", "numbers-nfr", "evolution", "risk-data")},
}
SANDBOXED = {"design-orchestrator", "design-reviewer"}
AGENT_NAME = re.compile(r"design-(?:orchestrator|planner|researcher|designer|reviewer|council-[a-z-]+)")


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def parse(path: Path) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", read(path), re.S)
    assert match, path.name
    return yaml.safe_load(match.group(1)), match.group(2)


@pytest.fixture
def mirror(tmp_path, monkeypatch):
    """A copy of the Claude Code sources and of core/agents/ that the script reads and compares."""
    source = tmp_path / "claude-agents"
    shutil.copytree(CORE / "claude" / "agents", source)
    target = tmp_path / "agents"
    shutil.copytree(AGENTS, target)
    monkeypatch.setattr(gen, "SOURCE", source)
    monkeypatch.setattr(gen, "TARGET", target)
    return source, target


def test_core_agents_are_what_the_script_generates():
    assert gen.problems(gen.render_all(), AGENTS) == []


def test_check_exit_codes(mirror, capsys):
    source, target = mirror
    assert gen.main(["--check", "--target", str(target)]) == 0
    (source / "planner.md").write_text(read(source / "planner.md").replace("Planner", "Planer", 1), encoding="utf-8")
    assert gen.main(["--check", "--target", str(target)]) == 1
    assert "out of date: design-planner.md" in capsys.readouterr().out


def test_changing_one_word_of_a_claude_agent_without_regenerating_fails(mirror):
    source, target = mirror
    council = source / "council" / "fit.md"
    text = read(council)
    assert "độc lập" in text
    council.write_text(text.replace("độc lập", "độc  lập", 1), encoding="utf-8")
    assert gen.problems(gen.render_all(), target) == ["out of date: design-council-fit.md"]


def test_editing_a_generated_file_by_hand_fails(mirror):
    _, target = mirror
    file = target / "design-reviewer.md"
    file.write_text(read(file) + "x\n", encoding="utf-8")
    assert gen.problems(gen.render_all(), target) == ["out of date: design-reviewer.md"]


def test_missing_and_unexpected_files_fail(mirror):
    _, target = mirror
    (target / "design-planner.md").unlink()
    (target / "extra.md").write_text("x", encoding="utf-8")
    assert gen.problems(gen.render_all(), target) == ["missing: design-planner.md", "unexpected: extra.md"]


def test_writing_restores_a_broken_target(mirror):
    _, target = mirror
    (target / "design-planner.md").write_text("broken", encoding="utf-8")
    (target / "extra.md").write_text("x", encoding="utf-8")
    assert gen.main(["--target", str(target)]) == 0
    assert gen.problems(gen.render_all(), target) == []


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_line_endings_do_not_matter(mirror, ending):
    """Whatever the checkout wrote (LF, or CRLF with autocrlf), the sources and the target are compared the same way."""
    source, target = mirror
    for file in [*source.glob("*.md"), *(source / "council").glob("*.md"), *target.glob("*.md")]:
        file.write_bytes(file.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", ending))
    assert gen.problems(gen.render_all(), target) == []


def test_the_name_table_covers_every_claude_agent_and_nothing_else():
    claude = {yaml.safe_load(read(path).split("---\n")[1])["name"] for path in gen.source_files()}
    assert set(gen.NAMES) == claude
    assert sorted(gen.NAMES.values()) == sorted(path.stem for path in AGENTS.glob("*.md"))
    assert sorted(EXPECTED_TOOLS) == sorted(path.stem for path in AGENTS.glob("*.md"))


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_frontmatter_per_role(name):
    meta, body = parse(AGENTS / f"{name}.md")
    assert meta["name"] == name
    assert meta["tools"] == EXPECTED_TOOLS[name]
    assert meta["model"] == "inherit"
    assert meta["mainAgent"] is (name == "design-orchestrator")
    assert meta["subagent"] is (name != "design-orchestrator")
    assert meta.get("commandExecutionPolicy") == ("sandbox" if name in SANDBOXED else None)
    if name == "design-orchestrator":
        assert "inheritMcp" not in meta and "excludeDefaultComponents" not in meta
    else:
        assert meta["inheritMcp"] is False and meta["excludeDefaultComponents"] is True


def test_only_the_sandboxed_agents_can_run_commands():
    with_commands = {name for name in EXPECTED_TOOLS if "run_command" in parse(AGENTS / f"{name}.md")[0]["tools"]}
    assert with_commands == SANDBOXED


def test_descriptions_are_the_claude_ones():
    for path in gen.source_files():
        claude, _ = parse(path)
        agy, _ = parse(AGENTS / f"{gen.NAMES[claude['name']]}.md")
        assert agy["description"] == claude["description"]


def test_generated_files_have_no_claude_references():
    for file in AGENTS.glob("*.md"):
        text = read(file)
        assert "design-core:" not in text, file.name
        assert "CLAUDE_PLUGIN_ROOT" not in text, file.name
        assert gen.BODY_END not in text, file.name
    for name in ("design-council-fit", "design-council-cost-ops", "design-council-numbers-nfr", "design-council-evolution", "design-council-risk-data"):
        assert "Claude Code" not in read(AGENTS / f"{name}.md"), name


def test_design_core_references_are_renamed():
    text = "gọi design-core:planner và design-core:council-fit; chạy ${CLAUDE_PLUGIN_ROOT}/scripts/x.py"
    assert gen.rename_references(text) == "gọi design-planner và design-council-fit; chạy <DESIGN_CORE_DIR>/scripts/x.py"


def test_every_agent_named_in_the_orchestrator_has_a_file():
    _, body = parse(AGENTS / "design-orchestrator.md")
    mentioned = set(AGENT_NAME.findall(body))
    files = {path.stem for path in AGENTS.glob("*.md")}
    assert mentioned <= files
    assert files - {"design-orchestrator"} <= mentioned  # the table names every agent it can call


def test_the_orchestrator_script_paths_use_the_placeholder_it_explains():
    _, body = parse(AGENTS / "design-orchestrator.md")
    assert "<DESIGN_CORE_DIR>/scripts/init_workspace.py" in body
    assert "agy plugin list --json" in body


def test_a_claude_tool_without_a_mapping_is_an_error(mirror):
    source, _ = mirror
    file = source / "planner.md"
    file.write_text(read(file).replace("tools: Read,", "tools: Read, Telepathy,", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="Telepathy"):
        gen.render_all()


def test_an_agent_missing_from_the_name_table_is_an_error(mirror):
    source, _ = mirror
    file = source / "planner.md"
    file.write_text(read(file).replace("name: planner", "name: planner2", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="planner2"):
        gen.render_all()


def test_agents_without_run_command_never_look_up_paths_themselves():
    for name in EXPECTED_TOOLS:
        meta, body = parse(AGENTS / f"{name}.md")
        if "run_command" in meta["tools"]:
            continue
        assert "agy plugin list" not in body, name
        assert "DESIGN_CORE_DIR" not in body, name


def test_the_orchestrator_passes_resolved_paths_to_agents_that_cannot_run_commands():
    _, body = parse(AGENTS / "design-orchestrator.md")
    assert "ghi đường dẫn đã giải" in body
    assert "design-architecture" in body and "/templates" in body
