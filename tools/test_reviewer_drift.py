"""Phase A3 (prompts, schema and documents): the reviewer writes `## Đề xuất cập nhật hồ sơ`, and everything agrees on it.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / build.DEFAULT_PLUGIN
FOUNDATION = REPO / "foundation" / "src" / "thanhtan"
USAGE = REPO / "families" / "software-dev" / "USAGE.md"
ARCHITECTURE = REPO / "docs" / "architecture.md"
SOFTWARE_DEV_README = REPO / "families" / "software-dev" / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"

HEADING = "## Đề xuất cập nhật hồ sơ"
DOCUMENTS = ("profile", "mission", "architecture", "conventions", "roadmap")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def reviewer_source() -> str:
    return read(CORE / build.ROLES_DIR / "reviewer.md")


# ------------------------------------------------------- foundation constants


def test_the_foundation_constant_holds_the_same_heading_the_prompt_uses():
    found = re.search(r'^DRIFT_HEADING\s*=\s*"([^"]+)"', read(FOUNDATION / "constants.py"), re.M)
    assert found, "constants.py has no DRIFT_HEADING"
    assert f"## {found.group(1)}" == HEADING


def test_the_gate_kind_is_named_drift_reviewed():
    assert re.search(r'DRIFT_REVIEWED\s*=\s*"drift-reviewed"', read(FOUNDATION / "constants.py"))


def test_the_workflow_schema_lists_the_gate():
    schema = json.loads(read(FOUNDATION / "schemas" / "workflow.schema.json"))
    assert "drift-reviewed" in schema["$defs"]["step"]["properties"]["gates"]["items"]["enum"]


def test_the_software_dev_workflow_gates_the_review_step_on_it():
    workflow = yaml.safe_load(read(CORE / "workflow.yaml"))
    review = next(step for step in workflow["steps"] if step["id"] == "review")
    assert "drift-reviewed" in review["gates"]


# ----------------------------------------------------------------- the prompt


def test_the_reviewer_is_told_to_write_the_section():
    body = reviewer_source()
    assert HEADING in body
    assert "không có" in body


def test_the_reviewer_is_told_which_documents_a_proposal_may_name():
    body = reviewer_source()
    for name in DOCUMENTS:
        assert f"`{name}`" in body, name


def test_the_reviewer_only_proposes_and_never_edits_the_documents():
    body = reviewer_source().lower()
    assert "propos" in body
    assert "never" in body and "project documents" in body


@pytest.mark.parametrize("path", ["claude/agents/reviewer.md", "agents/reviewer.md"])
def test_the_generated_reviewer_agents_carry_the_section(path):
    assert HEADING in read(CORE / path)
    assert build.check(CORE) == []


# ------------------------------------------------------------------ documents


def test_the_review_checklist_asks_the_person_to_read_the_proposals():
    usage = read(USAGE)
    review = usage.split("**Review —", 1)[1].split("\n\n## ", 1)[0]
    assert "Đề xuất cập nhật hồ sơ" in review


def test_the_architecture_document_describes_the_gate_and_says_it_checks_form_only():
    lines = [line for line in read(ARCHITECTURE).splitlines() if "drift-reviewed" in line]
    assert lines, "docs/architecture.md does not mention the gate"
    assert any("hình thức" in line for line in lines), "the gate's limit (form only) is not stated"


def test_the_review_checklist_leaves_the_correctness_of_the_proposals_to_the_person():
    review = read(USAGE).split("**Review —", 1)[1].split("\n\n## ", 1)[0]
    mentions = [line for line in review.splitlines() if "Đề xuất cập nhật hồ sơ" in line]
    assert mentions and any("hình thức" in line for line in mentions)


def test_the_software_dev_readme_lists_the_gate_next_to_the_other_review_gate():
    text = read(SOFTWARE_DEV_README)
    assert "drift-reviewed" in text and "conventions-reviewed" in text


def test_the_changelog_announces_the_gate_under_unreleased():
    unreleased = read(CHANGELOG).split("## [Unreleased]", 1)[1]
    assert "drift-reviewed" in unreleased
