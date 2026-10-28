import json
from pathlib import Path

import pytest
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow import cli
from agentflow.cli import main
from agentflow.constants import GITLEAKS_IMAGE, SEMGREP_IMAGE, TRIVY_IMAGE, ExitCode
from agentflow.models import CommandResult

FIXTURES = Path(__file__).parent / "fixtures" / "scans"


class FakeRunner:
    """Pretends to be Docker: answers `info` and returns canned tool output by image."""

    outputs: dict[str, CommandResult] = {}
    commands: list[list[str]] = []

    def which(self, name):
        return f"/bin/{name}" if name == "docker" else None

    def run(self, args, cwd, timeout):
        if list(args)[1:] == ["info"]:
            return CommandResult(0, "", "")
        FakeRunner.commands.append(list(args))
        for image, result in FakeRunner.outputs.items():
            if image in args:
                return result
        return CommandResult(0, "[]", "")


class FakeFetcher:
    def fetch(self, ruleset):
        return "rules: []\n"


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][2]["gates"] = ["scans-clean"]  # "check" plays the security step
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    monkeypatch.setenv("AGENTFLOW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(cli, "SubprocessRunner", FakeRunner)
    monkeypatch.setattr(cli, "HttpRuleFetcher", FakeFetcher)
    FakeRunner.commands = []
    FakeRunner.outputs = {}
    main(["init", "--workflow", str(path)])
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])  # confirm -> build
    (gitflow_repo / "bad.py").write_text("print(1)\n", encoding="utf-8")
    git(gitflow_repo, "add", "bad.py")
    git(gitflow_repo, "commit", "-q", "-m", "work")  # plain git: the guard only works through hooks
    main(["task", "advance", "--result", "pass"])  # build -> check
    capsys.readouterr()
    return gitflow_repo


def canned(**by_image):
    FakeRunner.outputs = {image: CommandResult(*result) for image, result in by_image.items()}


def test_scan_runs_the_three_tools_with_the_documented_arguments(ws, capsys):
    assert main(["scan"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "semgrep: clean" in out and "trivy: clean" in out and "gitleaks: clean" in out
    by_image = {image: next(c for c in FakeRunner.commands if image in c) for image in (SEMGREP_IMAGE, TRIVY_IMAGE, GITLEAKS_IMAGE)}
    semgrep = by_image[SEMGREP_IMAGE]
    assert semgrep[semgrep.index("--network") + 1] == "none" and semgrep[-1] == "bad.py"
    assert any(part.endswith(":/rules:ro") for part in semgrep)
    gitleaks = by_image[GITLEAKS_IMAGE]
    assert any(part.startswith("--log-opts=develop..") for part in gitleaks)


def test_blocking_findings_fail_the_scan_and_the_gate_until_a_person_suppresses_them(ws, capsys):
    canned(**{SEMGREP_IMAGE: (0, (FIXTURES / "semgrep.json").read_text(encoding="utf-8"), "")})
    assert main(["scan"]) == ExitCode.SCAN_BLOCKED
    out = capsys.readouterr().out
    assert "semgrep: blocked" in out
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    assert "scan 'semgrep' blocks" in capsys.readouterr().err

    state = json.loads((ws / ".ThanhTan" / "tasks" / "T-001" / "scans" / "summary.json").read_text(encoding="utf-8"))
    ids = {finding["id"] for outcome in state["outcomes"] for finding in outcome["findings"] if finding["blocking"]}
    assert main(["decide", "--suppress", "semgrep:nope", "--reason", "x"]) == ExitCode.INVALID_INPUT
    for finding_id in ids:
        assert main(["decide", "--suppress", finding_id, "--reason", "false positive, reviewed"]) == ExitCode.OK
    capsys.readouterr()
    assert main(["scan"]) == ExitCode.OK  # same findings, now suppressed
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK


def test_the_gate_wants_fresh_results(ws, capsys):
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    assert "has not run" in capsys.readouterr().err
    assert main(["scan"]) == ExitCode.OK
    git(ws, "commit", "-q", "--allow-empty", "-m", "more work")
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED
    assert "out of date" in capsys.readouterr().err


def test_scan_refuses_a_dirty_tree_and_a_missing_engine(ws, capsys, monkeypatch):
    (ws / "stray.txt").write_text("x", encoding="utf-8")
    assert main(["scan"]) == ExitCode.DIRTY_WORKING_TREE
    (ws / "stray.txt").unlink()

    class Down(FakeRunner):
        def run(self, args, cwd, timeout):
            return CommandResult(1, "", "")

    monkeypatch.setattr(cli, "SubprocessRunner", Down)
    assert main(["scan"]) == ExitCode.ENGINE_NOT_RUNNING


def test_trivy_findings_without_a_fix_do_not_block(ws, capsys):
    data = json.loads((FIXTURES / "trivy.json").read_text(encoding="utf-8"))
    for result in data["Results"]:
        for vulnerability in result["Vulnerabilities"]:
            vulnerability["FixedVersion"] = ""
    canned(**{TRIVY_IMAGE: (0, json.dumps(data), "")})
    assert main(["scan"]) == ExitCode.OK


def test_gitleaks_finding_blocks(ws, capsys):
    canned(**{GITLEAKS_IMAGE: (99, (FIXTURES / "gitleaks.json").read_text(encoding="utf-8"), "")})
    assert main(["scan"]) == ExitCode.SCAN_BLOCKED
    assert "gitleaks: blocked" in capsys.readouterr().out


def test_the_summary_reports_scans_when_the_task_is_sealed(ws, capsys):
    assert main(["scan"]) == ExitCode.OK
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK
    summary = (ws / ".ThanhTan" / "tasks" / "T-001" / "summary.md").read_text(encoding="utf-8")
    assert "semgrep: clean" in summary and "trivy: clean" in summary
