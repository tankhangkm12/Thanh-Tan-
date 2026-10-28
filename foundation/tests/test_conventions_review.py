import pytest

from agentflow.constants import GateKind
from agentflow.gates import CHECKS, GateContext, plan_report_path
from agentflow.models import Step, StepStatus, Task, TaskStatus, Workflow
from agentflow.projectcontext import ProjectContext, RoleSet

CONVENTIONS = """### PC-01 - Constants
- check: review
- status: confirmed
- source: src/constants.py
- description: Fixed values live in constants.

### PC-02 - Docstrings
- check: review
- status: confirmed
- source: src
- description: Public functions have docstrings.

### PC-03 - Not yet confirmed
- check: review
- status: unconfirmed
- source: src
- description: A suggestion.

### PC-04 - Plan order
- check: plan
- rule: item-order
- status: confirmed
- source: docs
- description: Not for the reviewer.
"""

STEP = Step("review", "Review", "reviewer", gates=(GateKind.CONVENTIONS_REVIEWED,))
TASK = Task("T-001", "t", TaskStatus.OPEN, "review", StepStatus.IN_PROGRESS)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / ".ThanhTan"
    (root / "project").mkdir(parents=True)
    (root / "project" / "conventions.md").write_text(CONVENTIONS, encoding="utf-8")
    return root


def report(workspace, text):
    path = plan_report_path(workspace, TASK.id, STEP.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(workspace):
    context = GateContext(workspace, Workflow(1, "f", 2, (STEP,)), ProjectContext(RoleSet(frozenset({"reviewer"}))))
    return CHECKS[GateKind.CONVENTIONS_REVIEWED](context, TASK, STEP)


def test_every_review_convention_must_be_answered(workspace):
    report(workspace, "# Review\n\nLooks fine.\n")
    problems = check(workspace)
    assert len(problems) == 2 and "PC-01" in problems[0] and "PC-02" in problems[1]
    assert "PC-03" not in " ".join(problems) and "PC-04" not in " ".join(problems)  # unconfirmed and non-review ones are not asked


def test_a_report_that_covers_every_code_passes(workspace):
    report(workspace, "# Review\n\n- PC-01: đạt\n- PC-02: đạt — all public functions documented\n")
    assert check(workspace) == []


@pytest.mark.parametrize("line", ["PC-01: đạt", "- PC-01: đạt", "* `PC-01`: đạt", "PC-01 - đạt", "  PC-01 – Đạt (checked src/)"])
def test_the_ways_to_write_that_a_convention_is_met(workspace, line):
    report(workspace, f"{line}\nPC-02: đạt\n")
    assert check(workspace) == []


def test_a_violation_names_the_place_and_blocks_a_pass(workspace):
    report(workspace, "PC-01: đạt\nvi phạm PC-02 ở src/app/service.py:42\n")
    problems = check(workspace)
    assert len(problems) == 1 and "PC-02" in problems[0] and "src/app/service.py:42" in problems[0] and "fail" in problems[0]


def test_a_violation_without_a_place_does_not_count_as_one_or_as_a_pass(workspace):
    report(workspace, "PC-01: đạt\nvi phạm PC-02\n")
    problems = check(workspace)
    assert len(problems) == 1 and "PC-02" in problems[0] and "file:line" in problems[0]


def test_a_violation_wins_over_a_pass_for_the_same_code(workspace):
    report(workspace, "PC-01: đạt\nPC-02: đạt\nvi phạm PC-01 ở src/a.py:1\n")
    assert "violated" in check(workspace)[0]


def test_a_code_inside_a_longer_one_is_not_a_match(workspace):
    report(workspace, "PC-011: đạt\nPC-02: đạt\n")
    assert len(check(workspace)) == 1


def test_no_report_no_pass(workspace):
    assert "no report" in check(workspace)[0]


def test_nothing_to_review_means_nothing_to_check(tmp_path):
    root = tmp_path / ".ThanhTan"
    root.mkdir()
    assert check(root) == []
