import json
import subprocess
from pathlib import Path

import pytest

from agentflow.constants import (
    GITLEAKS_IMAGE,
    SEMGREP_IMAGE,
    TRIVY_IMAGE,
    ExitCode,
    NetworkMode,
    ResultKind,
    ScanStatus,
)
from agentflow.container import glob_regex, running_engine, select_files, tool_command
from agentflow.errors import AgentflowError
from agentflow.models import CommandResult, StepStatus, Task, TaskStatus
from agentflow.placeholders import expand_args, expand_text, host_url
from agentflow.scan import ScanService, condition_holds, scan_problems
from agentflow.scan_read import parse_findings, read_result
from agentflow.scan_store import ScanStore, suppressed_ids, write_suppression
from agentflow.scan_tools import GITLEAKS_SPEC, SEMGREP_SPEC, TRIVY_SPEC
from agentflow.scan_types import Condition, FileSelection, ResultSpec, ScanContext, ScanFinding, ScanToolSpec
from agentflow.semgrep_rules import default_cache_dir, ensure_rules, ruleset_file

FIXTURES = Path(__file__).parent / "fixtures" / "scans"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


SQUAWK = ResultSpec(
    kind=ResultKind.JSON_FINDINGS, rule_field="rule_name", severity_field="level",
    location_field="file", blocking_severities=("Warning", "Error"), ok_exit_codes=(0, 1),
)


# ------------------------------------------------------------------ reading


def test_semgrep_blocks_on_error_severity_only():
    status, findings = read_result("semgrep", SEMGREP_SPEC.result, 0, fixture("semgrep.json"))
    assert status is ScanStatus.BLOCKED
    assert len(findings) == 8 and sum(f.blocking for f in findings) == 6
    assert {f.severity for f in findings} == {"ERROR", "WARNING"}
    assert all(f.id.startswith("semgrep:rules.python") and f.location == "bad.py" for f in findings)


def test_trivy_blocks_on_high_or_critical_with_a_fix_only():
    status, findings = read_result("trivy", TRIVY_SPEC.result, 0, fixture("trivy.json"))
    assert status is ScanStatus.BLOCKED
    blocking = [f for f in findings if f.blocking]
    assert blocking and all(f.severity in ("HIGH", "CRITICAL") for f in blocking)
    assert len(findings) == 9 and len(blocking) == 4
    unfixed = json.loads(fixture("trivy.json"))
    for result in unfixed["Results"]:
        for vulnerability in result["Vulnerabilities"]:
            vulnerability["FixedVersion"] = ""
    _, none_fixed = read_result("trivy", TRIVY_SPEC.result, 0, json.dumps(unfixed))
    assert not any(f.blocking for f in none_fixed)


def test_gitleaks_any_finding_blocks_and_exit_99_is_a_normal_result():
    status, findings = read_result("gitleaks", GITLEAKS_SPEC.result, 99, fixture("gitleaks.json"))
    assert status is ScanStatus.BLOCKED and findings[0].rule == "github-pat" and findings[0].blocking
    assert read_result("gitleaks", GITLEAKS_SPEC.result, 0, "")[0] is ScanStatus.CLEAN
    with pytest.raises(AgentflowError) as exc:
        read_result("gitleaks", GITLEAKS_SPEC.result, 2, "boom")
    assert exc.value.code == ExitCode.SCAN_FAILED


def test_squawk_levels_are_read_from_the_json():
    status, findings = read_result("squawk", SQUAWK, 1, fixture("squawk.json"))
    assert status is ScanStatus.BLOCKED
    assert {f.rule for f in findings} >= {"adding-required-field", "require-concurrent-index-creation"}


def test_exit_code_kind():
    spec = ResultSpec(kind=ResultKind.EXIT_CODE, fail_exit_codes=(1,))
    assert read_result("st", spec, 0, "")[0] is ScanStatus.CLEAN
    status, findings = read_result("st", spec, 1, "failed")
    assert status is ScanStatus.BLOCKED and findings[0].blocking
    with pytest.raises(AgentflowError):
        read_result("st", spec, 2, "cannot load schema")


def test_unreadable_output_is_an_error_not_an_empty_result():
    with pytest.raises(AgentflowError) as exc:
        parse_findings("squawk", SQUAWK, "Traceback ...")
    assert exc.value.code == ExitCode.SCAN_FAILED


# ----------------------------------------------------------------- placeholders


def test_placeholders():
    values = {"a.b": "x", "api.url": "http://localhost:8000/v1"}
    assert expand_text("${config:a.b}/y", values.get) == "x/y"
    assert expand_args(["run", "${files}", "--url", "${host_url:api.url}"], values.get, ["f1", "f2"]) == [
        "run", "f1", "f2", "--url", "http://host.docker.internal:8000/v1",
    ]
    assert host_url("https://example.com/x") == "https://example.com/x"
    with pytest.raises(AgentflowError) as exc:
        expand_text("${config:missing}", values.get)
    assert exc.value.code == ExitCode.SETTINGS_INVALID and "config set missing" in str(exc.value)
    assert expand_text("${var:range}", values.get, {"range": "a..b"}) == "a..b"


def test_conditions():
    values = {"db.engine": "postgresql", "spec": "x"}
    assert condition_holds(None, values.get)
    assert condition_holds(Condition(config_equals=("db.engine", "postgresql")), values.get)
    assert not condition_holds(Condition(config_equals=("db.engine", "mysql")), values.get)
    assert condition_holds(Condition(config_present=("spec",)), values.get)
    assert not condition_holds(Condition(config_present=("spec", "url")), values.get)


def test_globs():
    files = ["db/migrations/0001.sql", "db/migrations/sub/0002.sql", "src/a.py", "a.sql"]
    assert select_files(files, ["db/migrations/**/*.sql"]) == files[:2]
    assert select_files(files, ["*.sql"]) == ["a.sql"]
    assert select_files(files, []) == files
    assert glob_regex("src/?.py").match("src/a.py")


# ----------------------------------------------------------------- container


def test_command_is_pinned_read_only_and_offline_by_default():
    command = tool_command("docker", SEMGREP_SPEC, Path("/work/repo"), ["semgrep", "scan"], [])
    assert command[:2] == ["docker", "run"] and "--rm" in command
    assert command[command.index("--network") + 1] == "none"
    assert f"{Path('/work/repo')}:/repo:ro" in command and SEMGREP_IMAGE in command
    assert command[-2:] == ["semgrep", "scan"]


def test_trivy_gets_network_and_a_cache_volume_and_schemathesis_the_host():
    from agentflow.scan_types import MountSpec

    command = tool_command("docker", TRIVY_SPEC, Path("/r"), ["fs"], list(TRIVY_SPEC.mounts))
    assert "--network" not in command and "agentflow-trivy-cache:/root/.cache:rw" in command and TRIVY_IMAGE in command
    spec = ScanToolSpec("st", "img:1", ("run",), SQUAWK, network=NetworkMode.HOST_GATEWAY)
    command = tool_command("docker", spec, Path("/r"), ["run"], [MountSpec("/x", "/y")])
    assert "--add-host" in command and "host.docker.internal:host-gateway" in command
    assert "--network" not in command and "network=host" not in " ".join(command)
    assert "/x:/y:ro" in command


def test_gitleaks_spec_is_pinned():
    assert GITLEAKS_SPEC.image == GITLEAKS_IMAGE


class FakeRunner:
    def __init__(self, results=None, engine_up=True):
        self.results = results or {}
        self.engine_up = engine_up
        self.commands = []

    def which(self, name):
        return f"/bin/{name}" if name == "docker" else None

    def run(self, args, cwd, timeout):
        if list(args)[1:] == ["info"]:
            return CommandResult(0 if self.engine_up else 1, "", "")
        self.commands.append(list(args))
        for image, result in self.results.items():
            if image in args:
                return result
        return CommandResult(0, "[]", "")


def test_engine_not_running_is_a_hard_error():
    with pytest.raises(AgentflowError) as exc:
        running_engine(FakeRunner(engine_up=False))
    assert exc.value.code == ExitCode.ENGINE_NOT_RUNNING


def context(tmp_path, files=("a.py",), lookup=lambda key: None):
    return ScanContext(
        repo=tmp_path, base="develop", head="abc", changed_files=list(files), lookup=lookup,
        extra={"range": "develop..abc", "rules_dir": str(tmp_path / "rules")},
    )


def trivial(spec_id="t", **kwargs):
    return ScanToolSpec(spec_id, f"img/{spec_id}:1", ("go", "${files}"), SQUAWK, **kwargs)


def test_service_runs_stores_and_skips(tmp_path):
    store = ScanStore(tmp_path / "ws")
    runner = FakeRunner({"img/t:1": CommandResult(1, fixture("squawk.json"), "")})
    specs = [
        trivial("t", files=FileSelection(globs=("*.py",))),
        trivial("none", files=FileSelection(globs=("*.sql",)), skip_note="nothing to lint"),
        trivial("off", when=Condition(config_equals=("db", "pg")), skip_note="pg only"),
    ]
    outcomes = ScanService(runner, store).run("T-001", specs, context(tmp_path))
    by_tool = {o.tool: o for o in outcomes}
    assert by_tool["t"].status is ScanStatus.BLOCKED and by_tool["t"].blocking
    assert by_tool["none"].status is ScanStatus.SKIPPED and by_tool["none"].note == "nothing to lint"
    assert by_tool["off"].note == "pg only"
    assert len(runner.commands) == 1 and runner.commands[0][-2:] == ["go", "a.py"]
    stored = store.load("T-001")
    assert set(stored) == {"t", "none", "off"} and stored["t"].commit == "abc"
    assert (store.scans_dir("T-001") / "t.json").read_text(encoding="utf-8").strip().startswith("[")


def test_service_needs_a_running_engine_only_when_something_runs(tmp_path):
    store = ScanStore(tmp_path / "ws")
    down = FakeRunner(engine_up=False)
    skipped = ScanService(down, store).run("T-001", [trivial(when=Condition(config_present=("x",)))], context(tmp_path))
    assert skipped[0].status is ScanStatus.SKIPPED
    with pytest.raises(AgentflowError) as exc:
        ScanService(down, store).run("T-001", [trivial()], context(tmp_path))
    assert exc.value.code == ExitCode.ENGINE_NOT_RUNNING
    assert store.load("T-002") == {}


def test_service_stores_nothing_when_a_tool_cannot_run(tmp_path):
    store = ScanStore(tmp_path / "ws")
    runner = FakeRunner({"img/t:1": CommandResult(125, "", "no such image")})
    with pytest.raises(AgentflowError):
        ScanService(runner, store).run("T-001", [trivial()], context(tmp_path))
    assert store.load("T-001") == {}


# ---------------------------------------------------------- gate and decisions

TASK = Task("T-001", "x", TaskStatus.OPEN, "security", StepStatus.IN_PROGRESS)


def run_scan(tmp_path, output):
    store = ScanStore(tmp_path / "ws")
    runner = FakeRunner({"img/t:1": CommandResult(1, output, "")})
    spec = trivial("t", files=FileSelection())
    ScanService(runner, store).run("T-001", [spec], context(tmp_path))
    return store, spec


def test_scan_problems_missing_stale_blocking_and_suppressed(tmp_path):
    ws = tmp_path / "ws"
    store, spec = run_scan(tmp_path, fixture("squawk.json"))
    nothing = scan_problems(ScanStore(tmp_path / "other"), ws, TASK, [spec], "abc", lambda k: None)
    assert "has not run" in nothing[0]
    assert "out of date" in scan_problems(store, ws, TASK, [spec], "new", lambda k: None)[0]
    blocked = scan_problems(store, ws, TASK, [spec], "abc", lambda k: None)
    assert "blocks with 7 finding(s)" in blocked[0]
    for finding in store.load("T-001")["t"].findings:
        write_suppression(ws, "T-001", finding, "reviewed, accepted", "2026-10-10T00:00:00Z")
    assert scan_problems(store, ws, TASK, [spec], "abc", lambda k: None) == []
    assert len(suppressed_ids(ws, "T-001")) == 6 and suppressed_ids(ws, "T-002") == set()


def test_a_suppression_needs_a_reason(tmp_path):
    finding = ScanFinding("t:r:l", "r", "ERROR", "l", "m", True)
    with pytest.raises(AgentflowError):
        write_suppression(tmp_path, "T-001", finding, "  ", "2026")


def test_conditions_that_do_not_hold_need_no_result(tmp_path):
    spec = trivial("t", when=Condition(config_present=("x",)))
    assert scan_problems(ScanStore(tmp_path), tmp_path, TASK, [spec], "abc", lambda k: None) == []


# ------------------------------------------------------------ semgrep rules


class Fetcher:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def fetch(self, ruleset):
        self.calls.append(ruleset)
        if self.fail:
            raise OSError("offline")
        return f"rules: []  # {ruleset}\n"


def test_rules_are_fetched_once_and_cached_outside_the_repo(tmp_path):
    repo, cache = tmp_path / "repo", tmp_path / "cache"
    repo.mkdir()
    fetcher = Fetcher()
    folder = ensure_rules(cache, ["p/default"], repo, fetcher, now=1_000.0)
    assert (folder / "p_default.yaml").read_text(encoding="utf-8").startswith("rules:")
    ensure_rules(cache, ["p/default"], repo, fetcher)  # fresh: no second download
    assert fetcher.calls == ["p/default"]
    assert ruleset_file(folder, "p/default").name == "p_default.yaml"


def test_stale_rules_are_refreshed_and_fall_back_to_the_cache_offline(tmp_path):
    repo, cache = tmp_path / "repo", tmp_path / "cache"
    repo.mkdir()
    ensure_rules(cache, ["p/default"], repo, Fetcher())
    far_future = 10**11
    warnings = []
    ensure_rules(cache, ["p/default"], repo, Fetcher(fail=True), now=far_future, warn=warnings.append)
    assert warnings and "cached copy" in warnings[0]
    with pytest.raises(AgentflowError) as exc:
        ensure_rules(tmp_path / "empty", ["p/default"], repo, Fetcher(fail=True))
    assert exc.value.code == ExitCode.SCAN_FAILED


def test_rule_cache_inside_the_repository_is_refused(tmp_path):
    with pytest.raises(AgentflowError):
        ensure_rules(tmp_path / "repo" / ".cache", ["p/default"], tmp_path / "repo", Fetcher())


def test_cache_dir_locations():
    assert default_cache_dir({"AGENTFLOW_CACHE_DIR": "/c"}) == Path("/c")
    assert default_cache_dir({"LOCALAPPDATA": "C:/L"}, windows=True) == Path("C:/L/agentflow/cache")
    assert default_cache_dir({"XDG_CACHE_HOME": "/x"}, windows=False) == Path("/x/agentflow")


def test_no_semgrep_registry_rules_are_tracked_in_this_repository():
    root = Path(__file__).resolve().parents[2]
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=False).stdout.split()
    assert not [path for path in tracked if "semgrep-rules" in path or path.endswith("p_default.yaml")]
    yaml_files = [root / path for path in tracked if path.endswith((".yaml", ".yml"))]
    for path in yaml_files:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
        assert "semgrep.dev/r/" not in head and "check_id" not in head, path
