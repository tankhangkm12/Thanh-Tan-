import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from thanhtan.constants import SEMGREP_IMAGE, CheckKind, ExitCode, NetworkMode, ScanStatus
from thanhtan.convention_sources import load_effective_conventions, semgrep_rule_files
from thanhtan.errors import ThanhTanError
from thanhtan.models import CommandResult, Workflow
from thanhtan.projectcontext import ProjectContext, RoleSet
from thanhtan.scan import ScanService, all_tools, tools_for_step
from thanhtan.scan_store import ScanStore
from thanhtan.scan_tools import SEMGREP, custom_semgrep_spec
from thanhtan.scan_types import ScanContext

RULE = """rules:
  - id: no-literal-status
    languages: [python]
    severity: ERROR
    message: Use a constant for a status
    pattern: status = "..."
"""

CONVENTIONS = """### PC-01 - No literal status
- check: semgrep
- rule: no-literal-status.yaml
- status: {status}
- source: src/constants.py
- description: Statuses are constants.

### PC-02 - Docstrings
- check: review
- status: confirmed
- source: src
- description: Docstrings.
"""


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "proj" / ".ThanhTan"
    (root / "project").mkdir(parents=True)
    (root / "knowledge" / "semgrep").mkdir(parents=True)
    return root


def conventions(workspace, status="confirmed"):
    (workspace / "project" / "conventions.md").write_text(CONVENTIONS.format(status=status), encoding="utf-8")


def rule_file(workspace, name="no-literal-status.yaml", text=RULE):
    (workspace / "knowledge" / "semgrep" / name).write_text(text, encoding="utf-8")


def found(workspace):
    return semgrep_rule_files(workspace, load_effective_conventions(workspace))


def test_a_confirmed_semgrep_convention_with_its_rule_file_is_listed(workspace):
    conventions(workspace)
    rule_file(workspace)
    rules, problems = found(workspace)
    assert problems == [] and [(code, path.name) for code, path in rules] == [("PC-01", "no-literal-status.yaml")]


def test_an_unconfirmed_convention_is_not_run(workspace):
    conventions(workspace, status="unconfirmed")
    rule_file(workspace)
    assert found(workspace) == ([], [])


def test_a_missing_or_broken_rule_file_is_a_problem_not_silence(workspace):
    conventions(workspace)
    rules, problems = found(workspace)
    assert rules == [] and len(problems) == 1 and "PC-01" in problems[0] and "knowledge pull" in problems[0]
    rule_file(workspace, text="not: [valid")
    assert "not valid YAML" in found(workspace)[1][0]
    rule_file(workspace, text="something: else\n")
    assert "rules" in found(workspace)[1][0]


def test_no_semgrep_conventions_means_nothing_to_do(workspace):
    assert found(workspace) == ([], [])


# ------------------------------------------------------------- the scan tool


@dataclass
class FakeRunner:
    stdout: str = json.dumps({"results": []})
    commands: list = field(default_factory=list)

    def which(self, name):
        return f"/bin/{name}"

    def run(self, args, cwd, timeout):
        self.commands.append(list(args))
        return CommandResult(0, self.stdout, "")


def context(tmp_path, changed=("app.py",)):
    return ScanContext(
        repo=tmp_path / "proj", base="develop", head="abc123", changed_files=list(changed), lookup=lambda key: None,
        cache_dir=tmp_path / "cache", rulesets=(), extra={}, fetcher=None, warn=lambda message: None,
    )  # fmt: skip


def test_the_spec_mounts_only_the_staged_rules_read_only_without_network(workspace, tmp_path):
    conventions(workspace)
    rule_file(workspace)
    rules, _ = found(workspace)
    spec = custom_semgrep_spec(rules, [])
    assert spec.id == f"{SEMGREP}-conventions" and spec.image == SEMGREP_IMAGE and spec.network is NetworkMode.NONE
    runner = FakeRunner()
    outcomes = ScanService(runner, ScanStore(workspace)).run("T-001", [spec], context(tmp_path))
    assert outcomes[0].status is ScanStatus.CLEAN
    command = " ".join(runner.commands[-1])
    assert "--config /custom-rules" in command and ":/custom-rules:ro" in command and "--network none" in command and "app.py" in command
    staged = list((tmp_path / "cache").rglob("PC-01-no-literal-status.yaml"))
    assert len(staged) == 1 and "no-literal-status" in staged[0].read_text(encoding="utf-8")


def test_a_finding_of_a_convention_rule_blocks(workspace, tmp_path):
    conventions(workspace)
    rule_file(workspace)
    result = {"results": [{"check_id": "custom-rules.PC-01-no-literal-status.no-literal-status", "path": "app.py",
                           "extra": {"severity": "ERROR", "message": "Use a constant for a status"}}]}  # fmt: skip
    outcome = ScanService(FakeRunner(json.dumps(result)), ScanStore(workspace)).run(
        "T-001", [custom_semgrep_spec(found(workspace)[0], [])], context(tmp_path)
    )[0]
    assert outcome.status is ScanStatus.BLOCKED and outcome.findings[0].blocking
    assert outcome.findings[0].id.startswith("semgrep-conventions:")


def test_rule_problems_stop_the_scan_loudly(workspace, tmp_path):
    spec = custom_semgrep_spec([], ["PC-01: the rule file is missing"])
    with pytest.raises(ThanhTanError) as exc:
        ScanService(FakeRunner(), ScanStore(workspace)).run("T-001", [spec], context(tmp_path))
    assert exc.value.code is ExitCode.CONVENTIONS_INVALID and "PC-01" in str(exc.value)


# ------------------------------------------------- which step runs the tool


def workflow_with_scans():
    from thanhtan.constants import GateKind
    from thanhtan.models import Step

    return Workflow(1, "f", 2, (Step("security", "Security", "security", gates=(GateKind.SCANS_CLEAN,)),))


def test_the_tool_runs_in_the_step_the_workflow_scans_in(workspace):
    conventions(workspace)
    rule_file(workspace)
    rules, problems = found(workspace)
    project = ProjectContext(RoleSet(frozenset({"security"})), custom_semgrep=tuple(rules), custom_semgrep_problems=tuple(problems))
    workflow = workflow_with_scans()
    ids = [spec.id for spec in tools_for_step("security", workflow, project)]
    assert ids[:3] == ["semgrep", "trivy", "gitleaks"] and f"{SEMGREP}-conventions" in ids
    assert f"{SEMGREP}-conventions" in [spec.id for spec in all_tools(workflow, project)]
    assert f"{SEMGREP}-conventions" not in [spec.id for spec in tools_for_step("security", workflow, ProjectContext(RoleSet(frozenset())))]
