"""Phase A3: a review cannot pass without saying whether the project documents must change.

The review report needs a `## Đề xuất cập nhật hồ sơ` section holding either `không có` or bullets
`- <profile|mission|architecture|conventions|roadmap>: <proposal>`. The check is the `drift-reviewed` gate.
The gate name is spelled as a string here on purpose: these tests describe behaviour seen through the CLI.
"""

import copy
import io
from pathlib import Path

import pytest
import yaml
from conftest import SAMPLE_WORKFLOW, write_workflow

from thanhtan.cli import main
from thanhtan.constants import ExitCode
from thanhtan.workflow import parse_workflow

REPO = Path(__file__).resolve().parents[2]
HEADING = "## Đề xuất cập nhật hồ sơ"
GATE = "drift-reviewed"


def workflow(with_gate: bool = True) -> dict:
    data = copy.deepcopy(SAMPLE_WORKFLOW)
    data["steps"] = [
        {"id": "build", "name": "Build", "role": "builder"},
        {"id": "review", "name": "Review", "role": "reviewer", "requires_approval": True, "on_fail": "build"},
    ]
    if with_gate:
        data["steps"][1]["gates"] = [GATE]
    return data


def start(gitflow_repo, tmp_path, monkeypatch, capsys, with_gate: bool = True) -> None:
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", workflow(with_gate))
    monkeypatch.chdir(gitflow_repo)
    # Nothing is asserted here: a workflow the engine refuses shows up as a failure of the test that needed it.
    main(["init", "--workflow", str(path)])
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])  # build passed; the review is in progress
    capsys.readouterr()


@pytest.fixture
def at_review(gitflow_repo, tmp_path, monkeypatch, capsys):
    start(gitflow_repo, tmp_path, monkeypatch, capsys)
    return monkeypatch


def save_review(monkeypatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert main(["report", "--step", "review"]) == ExitCode.OK


def review_with(section: str) -> str:
    return f"# Review\n\nVerdict: no must-fix items.\n\n{section}"


def try_pass(capsys):
    code = main(["task", "advance", "--result", "pass"])
    return code, capsys.readouterr().err


# ------------------------------------------------------------------ passes

ACCEPTED = [
    HEADING + "\n\nkhông có\n",
    HEADING + "\n\nKhông có.\n",
    HEADING + "\nkhông có\n\n## Bài học đề xuất\n\n### L1 - x\ntext\n",
    HEADING + "\n\n- profile: thêm lệnh build mới\n",
    HEADING + "\n\n- mission: phạm vi mở rộng sang báo cáo\n",
    HEADING + "\n\n- architecture: thêm module thanh toán\n",
    HEADING + "\n\n- conventions: PC-03 cần sửa lại\n",
    HEADING + "\n\n- roadmap: R2 xong, thêm R5\n",
    HEADING + "\n\n- profile: a\n- architecture: b\n- roadmap: c\n",
]


@pytest.mark.parametrize("section", ACCEPTED, ids=lambda s: s.splitlines()[-1][:40] or "section")
def test_a_review_with_a_well_formed_section_may_pass(at_review, capsys, section):
    save_review(at_review, review_with(section))
    code, err = try_pass(capsys)
    assert code == ExitCode.OK, err


# ----------------------------------------------------------------- refusals

REFUSED = {
    "no section at all": "## Kết luận\n\nổn\n",
    "heading with nothing under it at the end of the report": HEADING + "\n\n",
    "heading with nothing under it before another heading": HEADING + "\n\n## Bài học đề xuất\n\nkhông có\n",
    "none and a proposal together": HEADING + "\n\nkhông có\n- profile: x\n",
    "a document that is not a project document": HEADING + "\n\n- readme: sửa lại\n",
    "a bullet without a document": HEADING + "\n\n- cần sửa architecture\n",
    "a proposal that is empty": HEADING + "\n\n- profile:\n",
    "free text instead of bullets": HEADING + "\n\nHồ sơ cần cập nhật nhưng chưa rõ chỗ nào.\n",
    "heading only inside a code fence": "```\n" + HEADING + "\nkhông có\n```\n",
    "heading only inside an HTML comment": "<!--\n" + HEADING + "\nkhông có\n-->\n",
    "heading at the wrong level": "### Đề xuất cập nhật hồ sơ\n\nkhông có\n",
    "a different heading that starts the same": "## Đề xuất cập nhật hồ sơ dự án\n\nkhông có\n",
    "the heading twice": HEADING + "\n\nkhông có\n\n" + HEADING + "\n\n- profile: x\n",
}


@pytest.mark.parametrize("section", REFUSED.values(), ids=REFUSED.keys())
def test_a_review_without_a_well_formed_section_cannot_pass(at_review, capsys, section):
    save_review(at_review, review_with(section))
    code, err = try_pass(capsys)
    assert code == ExitCode.GATE_FAILED, err
    assert f"[{GATE}]" in err and "Đề xuất cập nhật hồ sơ" in err


def test_the_refusal_names_the_document_that_is_not_allowed(at_review, capsys):
    save_review(at_review, review_with(HEADING + "\n\n- readme: sửa lại\n"))
    _, err = try_pass(capsys)
    assert "readme" in err


def test_a_review_with_no_report_cannot_pass(at_review, capsys):
    code, err = try_pass(capsys)
    assert code == ExitCode.GATE_FAILED
    assert f"[{GATE}]" in err


def test_failing_a_review_does_not_need_the_section(at_review, capsys):
    save_review(at_review, "# Review\n\nMust fix: C1 is wrong.\n")
    assert main(["task", "advance", "--result", "fail"]) == ExitCode.OK


def test_a_refused_pass_leaves_the_step_in_progress(at_review, capsys):
    save_review(at_review, review_with("## Kết luận\n\nổn\n"))
    try_pass(capsys)
    main(["status"])
    assert "in_progress" in capsys.readouterr().out


def test_the_section_added_later_lets_the_same_review_pass(at_review, capsys):
    save_review(at_review, review_with("## Kết luận\n\nổn\n"))
    assert try_pass(capsys)[0] == ExitCode.GATE_FAILED
    save_review(at_review, review_with(HEADING + "\n\nkhông có\n"))
    assert try_pass(capsys)[0] == ExitCode.OK


def test_a_workflow_that_does_not_use_the_gate_is_unaffected(gitflow_repo, tmp_path, monkeypatch, capsys):
    """Regression: green before the change; workflows without the gate must keep working."""
    start(gitflow_repo, tmp_path, monkeypatch, capsys, with_gate=False)
    save_review(monkeypatch, "# Review\n\nno drift section here\n")
    assert try_pass(capsys)[0] == ExitCode.OK


# -------------------------------------------------------------- the contract


def test_the_workflow_schema_knows_the_gate():
    parse_workflow(workflow(), "w")


def test_the_workflow_schema_still_refuses_an_unknown_gate():
    """Regression: green before the change; adding one gate must not open the enum."""
    data = workflow()
    data["steps"][1]["gates"] = ["drift"]
    with pytest.raises(Exception, match="invalid workflow"):
        parse_workflow(data, "w")


def test_the_software_dev_workflow_runs_the_gate_on_the_review_step():
    data = yaml.safe_load((REPO / "families" / "software-dev" / "core" / "workflow.yaml").read_text(encoding="utf-8"))
    review = next(step for step in data["steps"] if step["id"] == "review")
    assert GATE in review["gates"] and "conventions-reviewed" in review["gates"]
