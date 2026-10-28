"""Every requirement says where it comes from, and the roadmap item shows its goal and documents.

- ``thanhtan roadmap show R2`` (read-only) prints an item with its ``goal`` and ``docs``, so the orchestrator can read the
  documents of the item a task serves.
- The gate ``requirements-sourced`` wants every ``- Y1: ...`` line of the step's report to end with ``(nguồn: <where>)``:
  a document listed under ``## Tài liệu`` (with an optional ``:line``, ``:line-line`` or ``#part``), a file in a listed
  folder, a listed link, or ``người dùng``. A path must exist and a line must be in the file.
"""

import json
from pathlib import Path

import pytest
import yaml
from checklist_helpers import checklist_workflow, open_workspace, write_roadmap
from conftest import git
from sdd_helpers import run, say

from thanhtan.constants import ExitCode, GuardDecision
from thanhtan.docpin import requirement_source_problems
from thanhtan.guard import evaluate
from thanhtan.plan import parse_requirement_texts
from thanhtan.workflow import load_workflow

REAL_WORKFLOW = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core" / "workflow.yaml"
SPEC = "".join(f"line {n}\n" for n in range(1, 51))

DOCS = """## Tài liệu
- docs/spec.md
- docs/design/
- https://example.com/contract
"""


def report(*requirements: str, docs: str = DOCS) -> str:
    lines = "\n".join(f"- {text}" for text in requirements)
    return f"# Confirm\n\n## Yêu cầu\n{lines}\n\n{docs}"


def problems_of(root: Path, *requirements: str, docs: str = DOCS) -> list[str]:
    text = report(*requirements, docs=docs)
    return requirement_source_problems(text, root, parse_requirement_texts(text))


@pytest.fixture
def root(tmp_path) -> Path:
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "docs" / "design" / "screen.md").write_text("screen\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ the rule


@pytest.mark.parametrize(
    "source",
    [
        "docs/spec.md:42",
        "docs/spec.md:40-45",
        "docs/spec.md",
        "docs/spec.md#Giữ hàng",
        "`docs/spec.md:3`",
        "./docs/spec.md:3",
        "docs\\spec.md:3",
        "docs/design/screen.md",
        "docs/design",
        "https://example.com/contract#reserve",
        "người dùng",
        "docs/spec.md:1; https://example.com/contract",
    ],
)
def test_a_source_in_the_listed_documents_is_accepted(root, source):
    assert problems_of(root, f"Y1: Giữ hàng không âm (nguồn: {source})") == []


def test_the_word_for_source_may_be_written_without_accents_or_in_english(root):
    assert problems_of(root, "Y1: a (nguon: docs/spec.md:1)", "Y2: b (source: user)") == []


def test_a_requirement_without_a_source_is_named(root):
    found = problems_of(root, "Y1: Giữ hàng (nguồn: docs/spec.md:1)", "Y2: Không cho tồn âm")
    assert len(found) == 1 and found[0].startswith("Y2 has no source")


def test_a_source_must_be_at_the_end_of_the_line(root):
    assert problems_of(root, "Y1: (nguồn: docs/spec.md:1) Giữ hàng")[0].startswith("Y1 has no source")


@pytest.mark.parametrize(
    ("source", "words"),
    [
        ("docs/other.md:3", "not one of the documents listed"),
        ("src/stock.py:10", "not one of the documents listed"),
        ("docs/spec.md:51", "a line the document does not have (it has 50)"),
        ("docs/spec.md:0", "a line the document does not have"),
        ("docs/spec.md:9-5", "a line the document does not have"),
        ("docs/design/missing.md", "does not exist"),
        ("docs/design:3", "names a line of a folder"),
        ("https://other.example/x", "not a link listed"),
    ],
)
def test_a_wrong_source_says_why(root, source, words):
    found = problems_of(root, f"Y1: Giữ hàng (nguồn: {source})")
    assert len(found) == 1 and found[0].startswith("Y1:") and words in found[0]


def test_one_bad_source_among_several_is_found(root):
    found = problems_of(root, "Y1: a (nguồn: docs/spec.md:1; docs/nope.md)")
    assert len(found) == 1 and "docs/nope.md" in found[0]


def test_without_documents_only_the_person_can_be_the_source(root):
    none = "## Tài liệu\n- không có\n"
    assert problems_of(root, "Y1: a (nguồn: người dùng)", docs=none) == []
    assert problems_of(root, "Y1: a (nguồn: docs/spec.md:1)", docs=none) != []


def test_a_listed_folder_does_not_let_in_a_sibling_with_the_same_prefix(root):
    (root / "docs" / "design-old.md").write_text("x\n", encoding="utf-8")
    assert problems_of(root, "Y1: a (nguồn: docs/design-old.md)") != []


# ------------------------------------------------------------------ the gate in a workflow


def sourced_workflow(tmp_path: Path) -> Path:
    path = checklist_workflow(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["steps"][0]["gates"] = ["requirements-sourced"]
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    (gitflow_repo / "docs").mkdir()
    (gitflow_repo / "docs" / "spec.md").write_text(SPEC, encoding="utf-8")
    git(gitflow_repo, "add", "-A")
    git(gitflow_repo, "commit", "-q", "-m", "docs")
    open_workspace(gitflow_repo, tmp_path, monkeypatch, capsys, sourced_workflow(tmp_path))
    write_roadmap(gitflow_repo)
    return gitflow_repo


def test_the_confirm_step_cannot_pass_until_every_requirement_has_a_source(repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Orders", "--roadmap", "R1") == ExitCode.OK
    docs = "## Tài liệu\n- docs/spec.md\n"
    assert say(monkeypatch, "report", "--step", "confirm", text=report("Y1: a (nguồn: docs/spec.md:2)", "Y2: b", docs=docs)) == ExitCode.OK
    capsys.readouterr()
    code, _out, err = run(capsys, "task", "advance", "--result", "pass")
    assert code == ExitCode.GATE_FAILED and "[requirements-sourced] Y2 has no source" in err
    assert say(monkeypatch, "report", "--step", "confirm", text=report("Y1: a (nguồn: docs/spec.md:2)", "Y2: b (nguồn: người dùng)", docs=docs)) == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK


def test_a_report_without_requirements_is_not_held_by_the_gate(repo, monkeypatch, capsys):
    assert say(monkeypatch, "task", "new", "Orders") == ExitCode.OK
    assert say(monkeypatch, "report", "--step", "confirm", text="# Confirm\n\nNothing listed.\n") == ExitCode.OK
    assert say(monkeypatch, "task", "advance", "--result", "pass") == ExitCode.OK


def test_the_software_dev_workflow_holds_confirm_to_the_rule():
    steps = {step.id: step for step in load_workflow(REAL_WORKFLOW).steps}
    assert "requirements-sourced" in [str(gate) for gate in steps["confirm"].gates]
    assert any("nguồn" in question for question in steps["confirm"].approval_checklist)


# ------------------------------------------------------------------ roadmap show


def test_roadmap_show_prints_the_goal_and_the_documents_of_an_item(repo, capsys):
    code, out, _err = run(capsys, "roadmap", "show", "R1")
    assert code == ExitCode.OK
    lines = out.splitlines()
    assert lines[0] == "R1 [todo] Đặt món (unconfirmed)"
    assert lines[1] == "goal: Khách đặt được món từ điện thoại."
    assert lines[2] == "docs: docs/vision.md:10"


def test_roadmap_show_refuses_an_unknown_or_malformed_code(repo, capsys):
    assert run(capsys, "roadmap", "show", "R9")[0] == ExitCode.INVALID_INPUT
    assert run(capsys, "roadmap", "show", "nine")[0] == ExitCode.INVALID_INPUT


class _OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


class _Workspaces:
    def __init__(self, root):
        self.root = root

    def has_workspace(self, directory):
        return directory == self.root


def test_an_agent_may_read_the_roadmap_but_not_set_it(repo):
    def verdict(command):
        return evaluate(command, repo, _OnFeature(), _Workspaces(repo)).decision

    assert verdict("thanhtan roadmap show R1") is GuardDecision.ALLOW
    assert verdict("thanhtan roadmap set R1 done") is GuardDecision.DENY
