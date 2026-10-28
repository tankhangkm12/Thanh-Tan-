import copy
import io
import json
from pathlib import Path

import pytest
import yaml
from conftest import SAMPLE_WORKFLOW, git, write_workflow

from agentflow import cli
from agentflow.cli import main
from agentflow.constants import ExitCode, GateKind, NetworkMode, ResultKind
from agentflow.errors import AgentflowError
from agentflow.extension import load_extension_file, parse_extension
from agentflow.models import CommandResult
from agentflow.settings import coerce, get_value, set_value

EXTENSION = {
    "schema_version": 1,
    "name": "sample-ext",
    "family": "sample",
    "description": "A made-up extension.",
    "settings": {
        "key": "proj",
        "schema": {
            "type": "object",
            "required": ["secure_dir", "up_cmd", "down_cmd"],
            "properties": {
                "secure_dir": {"type": "string"},
                "up_cmd": {"type": "string"},
                "down_cmd": {"type": "string"},
                "retries": {"type": "integer"},
                "url": {"type": "string"},
            },
        },
    },
    "roles": [{"id": "specialist"}],
    "path_rules": [{"id": "secure-only", "paths": ["${config:proj.secure_dir}/**"], "roles": ["specialist"]}],
    "plan_rules": [
        {
            "id": "both-ways",
            "when_paths": ["${config:proj.secure_dir}/**"],
            "done_when_contains": ["${config:proj.up_cmd}", "${config:proj.down_cmd}"],
        }
    ],
    "scan_tools": [
        {
            "id": "lint",
            "step": "check",
            "image": "example/lint:1.0",
            "args": ["--json", "${files}"],
            "files": {"globs": ["${config:proj.secure_dir}/**/*.sql"]},
            "when": {"config_equals": {"key": "proj.engine", "value": "pg"}},
            "skip_note": "lint is for pg only",
            "result": {"kind": "json_findings", "rule_field": "rule", "severity_field": "level", "blocking_severities": ["Error"]},
        },
        {
            "id": "probe",
            "step": "check",
            "image": "example/probe:2.0",
            "network": "host-gateway",
            "args": ["run", "/repo/${config:proj.spec}", "--url", "${host_url:proj.url}"],
            "when": {"config_present": ["proj.spec", "proj.url"]},
            "result": {"kind": "exit_code", "fail_exit_codes": [1]},
        },
    ],
    "gates": [{"step": "check", "kind": "scans-clean"}],
}


def extension_data(**changes):
    data = copy.deepcopy(EXTENSION)
    data.update(changes)
    return data


# ------------------------------------------------------------------ the contract


def test_a_valid_extension_is_read():
    extension = parse_extension(extension_data(), "x")
    assert extension.name == "sample-ext" and extension.role_ids == ("specialist",)
    lint, probe = extension.scan_tools
    assert lint.result.kind is ResultKind.JSON_FINDINGS and lint.result.ok_exit_codes == (0, 1)
    assert probe.network is NetworkMode.HOST_GATEWAY and probe.result.ok_exit_codes == (0, 1)
    assert extension.gates == (("check", GateKind.SCANS_CLEAN),)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(surprise=1), "surprise"),
        (lambda d: d["scan_tools"][0].update(network="host"), "network"),
        (lambda d: d["scan_tools"][0].update(image="example/lint"), "image"),
        (lambda d: d["scan_tools"][0].update(image="example/lint:latest"), "must be pinned"),
        (lambda d: d["scan_tools"][0]["result"].pop("rule_field"), "rule_field"),
        (lambda d: d["scan_tools"][1]["result"].pop("fail_exit_codes"), "fail_exit_codes"),
        (lambda d: d["gates"][0].update(kind="made-up"), "kind"),
        (lambda d: d["path_rules"][0].update(roles=["ghost"]), "not declared by this extension"),
        (lambda d: d["roles"].append({"id": "specialist"}), "duplicate role"),
        (lambda d: d["scan_tools"][0]["args"].append("${var:rules_dir}"), "not allowed in extensions"),
        (lambda d: d["scan_tools"][0]["args"].append("x${files}"), "whole argument"),
        (lambda d: d["scan_tools"][0]["args"].append("${config:other.key}"), "own key"),
        (lambda d: d["scan_tools"][0]["when"]["config_equals"].update(key="other.key"), "condition key"),
    ],
)
def test_invalid_extensions_are_refused(change, message):
    data = copy.deepcopy(EXTENSION)
    change(data)
    with pytest.raises(AgentflowError, match=message) as exc:
        parse_extension(data, "x")
    assert exc.value.code == ExitCode.EXTENSION_INVALID


def test_unreadable_files(tmp_path):
    with pytest.raises(AgentflowError):
        load_extension_file(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [", encoding="utf-8")
    with pytest.raises(AgentflowError):
        load_extension_file(bad)


# --------------------------------------------------------------------- settings


def test_settings_helpers():
    settings = set_value({}, "proj.retries", 3)
    assert get_value(settings, "proj.retries") == 3 and get_value(settings, "proj.nope") is None
    assert set_value(settings, "proj.a.b", "x")["proj"]["a"] == {"b": "x"}
    extension = parse_extension(extension_data(), "x")
    assert coerce([extension], "proj.retries", "5") == 5
    assert coerce([extension], "proj.up_cmd", "5") == "5"
    assert coerce([], "x.y", "5") == "5"
    with pytest.raises(AgentflowError):
        set_value({}, "a..b", 1)


# ------------------------------------------------------------------- the workspace


class FakeRunner:
    commands: list[list[str]] = []
    outputs: dict[str, CommandResult] = {}

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
    data["steps"][1]["gates"] = ["plan-valid"]
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    monkeypatch.setenv("AGENTFLOW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(cli, "SubprocessRunner", FakeRunner)
    monkeypatch.setattr(cli, "HttpRuleFetcher", FakeFetcher)
    FakeRunner.commands, FakeRunner.outputs = [], {}
    main(["init", "--workflow", str(path)])
    capsys.readouterr()
    return gitflow_repo


@pytest.fixture
def ext_file(tmp_path):
    path = tmp_path / "plugin" / "extension.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(EXTENSION, sort_keys=False), encoding="utf-8")
    return path


def configure(capsys, **settings):
    values = {"secure_dir": "db/secure", "up_cmd": "make up", "down_cmd": "make down", **settings}
    for key, value in values.items():
        assert main(["config", "set", f"proj.{key}", str(value)]) == ExitCode.OK
    capsys.readouterr()


def test_ext_add_list_and_sync(ws, ext_file, capsys):
    assert main(["ext", "add", str(ext_file)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "registered extension 'sample-ext'" in out and "roles: specialist" in out and "example/lint:1.0" in out
    assert "settings still to set" in out
    assert (ws / ".ThanhTan" / "extensions" / "sample-ext.yaml").is_file()
    assert main(["ext", "add", str(ext_file)]) == ExitCode.EXTENSION_INVALID  # already there
    assert main(["ext", "list"]) == ExitCode.OK
    assert "sample-ext: in_sync" in capsys.readouterr().out

    changed = copy.deepcopy(EXTENSION)
    changed["description"] = "changed"
    ext_file.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
    main(["ext", "list"])
    assert "source_changed" in capsys.readouterr().out
    assert main(["ext", "sync"]) == ExitCode.OK
    assert "sample-ext: updated" in capsys.readouterr().out
    assert main(["ext", "sync"]) == ExitCode.OK
    assert "unchanged" in capsys.readouterr().out
    ext_file.unlink()
    main(["ext", "list"])
    assert "source_missing" in capsys.readouterr().out


def test_ext_add_refuses_other_families_conflicts_and_unknown_steps(ws, tmp_path, capsys):
    def write(name, data):
        path = tmp_path / name
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return str(path)

    assert main(["ext", "add", write("a.yaml", extension_data(family="other"))]) == ExitCode.EXTENSION_INVALID
    clash = extension_data(roles=[{"id": "builder"}], path_rules=[], plan_rules=[])
    assert main(["ext", "add", write("b.yaml", clash)]) == ExitCode.EXTENSION_INVALID
    assert "role 'builder' already exists" in capsys.readouterr().err
    tool = copy.deepcopy(EXTENSION["scan_tools"])
    tool[0]["step"] = "nope"
    assert main(["ext", "add", write("c.yaml", extension_data(scan_tools=tool))]) == ExitCode.EXTENSION_INVALID
    assert "no step 'nope'" in capsys.readouterr().err
    builtin_clash = copy.deepcopy(EXTENSION["scan_tools"])
    builtin_clash[0]["id"] = "trivy"
    assert main(["ext", "add", write("d.yaml", extension_data(scan_tools=builtin_clash))]) == ExitCode.EXTENSION_INVALID
    assert main(["ext", "list"]) == ExitCode.OK


def test_config_get_set_check(ws, ext_file, capsys):
    main(["ext", "add", str(ext_file)])
    capsys.readouterr()
    assert main(["config", "check"]) == ExitCode.SETTINGS_INVALID
    assert "secure_dir" in capsys.readouterr().out
    assert main(["config", "get", "proj.secure_dir"]) == ExitCode.SETTINGS_INVALID
    configure(capsys)
    assert main(["config", "check"]) == ExitCode.OK
    capsys.readouterr()
    main(["config", "get", "proj.secure_dir"])
    assert capsys.readouterr().out.strip() == "db/secure"
    main(["config", "set", "proj.retries", "oops"])
    assert main(["config", "check"]) == ExitCode.SETTINGS_INVALID
    main(["config", "set", "proj.retries", "4"])
    main(["config", "get", "proj.retries"])
    assert capsys.readouterr().out.strip().endswith("4")


PLAN = """### C1 - Change the schema
- role: {role}
- files: db/secure/001.sql
- done-when: {done}
- docs: https://docs.example/a

### C2 - Feature
- role: builder
- files: src/a.py
- done-when: `pytest`
- docs: không có — trivial
"""


def check_plan(tmp_path, role="specialist", done="`make up` then `make down`"):
    path = tmp_path / "plan.md"
    path.write_text(PLAN.format(role=role, done=done), encoding="utf-8")
    return main(["plan", "check", "--file", str(path)])


def test_plan_check_knows_extension_roles_and_rules(ws, ext_file, tmp_path, capsys):
    main(["ext", "add", str(ext_file)])
    configure(capsys)
    assert check_plan(tmp_path) == ExitCode.OK
    assert check_plan(tmp_path, role="builder") == ExitCode.PLAN_INVALID
    assert "role 'builder' may not change db/secure/001.sql" in capsys.readouterr().out
    assert check_plan(tmp_path, done="`make up`") == ExitCode.PLAN_INVALID
    assert "done-when must contain `make down`" in capsys.readouterr().out
    assert check_plan(tmp_path, role="ghost") == ExitCode.PLAN_INVALID


def test_every_item_must_list_its_files_once_path_rules_exist(ws, ext_file, tmp_path, capsys):
    main(["ext", "add", str(ext_file)])
    configure(capsys)
    plan = tmp_path / "p.md"
    plan.write_text("### C1 - x\n- role: builder\n- done-when: y\n- docs: https://e.example/\n", encoding="utf-8")
    assert main(["plan", "check", "--file", str(plan)]) == ExitCode.PLAN_INVALID
    assert "missing 'files'" in capsys.readouterr().out


def test_a_folder_entry_counts_as_touching_what_is_below_it(ws, ext_file, tmp_path, capsys):
    main(["ext", "add", str(ext_file)])
    configure(capsys)
    plan = tmp_path / "p.md"
    plan.write_text("### C1 - x\n- role: builder\n- files: db/\n- done-when: y\n- docs: https://e.example/\n", encoding="utf-8")
    assert main(["plan", "check", "--file", str(plan)]) == ExitCode.PLAN_INVALID


def start_build(ws, monkeypatch, capsys, plan):
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])
    monkeypatch.setattr("sys.stdin", io.StringIO(plan))
    main(["report", "--step", "build"])
    capsys.readouterr()


@pytest.fixture(autouse=True)
def _no_gitleaks(monkeypatch):
    from agentflow.models import ScanResult

    class Clean:
        def __init__(self, runner):
            pass

        def scan_staged(self, repo):
            return ScanResult(True, "")

    monkeypatch.setattr(cli, "ContainerGitleaksScanner", Clean)


def test_commits_follow_the_path_rules(ws, ext_file, tmp_path, capsys, monkeypatch):
    main(["ext", "add", str(ext_file)])
    configure(capsys)
    start_build(ws, monkeypatch, capsys, PLAN.format(role="specialist", done="`make up` and `make down`"))
    (ws / "db" / "secure").mkdir(parents=True)
    (ws / "db" / "secure" / "001.sql").write_text("select 1;\n", encoding="utf-8")
    (ws / "src").mkdir()
    (ws / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(ws, "add", "db/secure/001.sql")
    assert main(["commit", "no item"]) == ExitCode.PLAN_INVALID  # guarded path needs an item
    assert main(["commit", "wrong item", "--item", "C2"]) == ExitCode.PLAN_INVALID  # builder may not
    err = capsys.readouterr().err
    assert "only specialist may" in err and "not in the files of item C2" in err
    assert main(["commit", "right item", "--item", "C1"]) == ExitCode.OK
    git(ws, "add", "src/a.py")
    assert main(["commit", "other file under C1", "--item", "C1"]) == ExitCode.PLAN_INVALID
    assert "src/a.py is not in the files of item C1" in capsys.readouterr().err
    assert main(["commit", "feature", "--item", "C2"]) == ExitCode.OK


def test_extension_scan_tools_run_on_their_step_and_gate_it(ws, ext_file, capsys, monkeypatch):
    main(["ext", "add", str(ext_file)])
    configure(capsys, engine="pg", spec="api.yaml", url="http://localhost:8000/v1")
    main(["config", "set", "proj.engine", "pg"])
    start_build(ws, monkeypatch, capsys, PLAN.format(role="specialist", done="`make up` and `make down`"))
    (ws / "db" / "secure").mkdir(parents=True)
    (ws / "db" / "secure" / "001.sql").write_text("select 1;\n", encoding="utf-8")
    git(ws, "add", "db")
    main(["commit", "schema", "--item", "C1"])
    (ws / "src").mkdir()
    (ws / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    git(ws, "add", "src")
    main(["commit", "feature", "--item", "C2"])
    main(["task", "advance", "--result", "pass"])  # build -> check (plan-valid gate: plan is fine)
    capsys.readouterr()
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED  # scans-clean added by the extension
    assert "scan 'lint' has not run" in capsys.readouterr().err

    FakeRunner.outputs = {"example/lint:1.0": CommandResult(1, '[{"rule": "r1", "level": "Error", "file": "db/secure/001.sql"}]', "")}
    assert main(["scan"]) == ExitCode.SCAN_BLOCKED
    out = capsys.readouterr().out
    assert "lint: blocked" in out and "probe: clean" in out
    lint = next(c for c in FakeRunner.commands if "example/lint:1.0" in c)
    assert lint[-3:] == ["--json", "db/secure/001.sql"][-2:] or lint[-1] == "db/secure/001.sql"
    probe = next(c for c in FakeRunner.commands if "example/probe:2.0" in c)
    assert "host.docker.internal:host-gateway" in probe and "--network" not in probe
    assert probe[-3:] == ["/repo/api.yaml", "--url", "http://host.docker.internal:8000/v1"]
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.GATE_FAILED

    state = json.loads((ws / ".ThanhTan" / "tasks" / "T-001" / "scans" / "summary.json").read_text(encoding="utf-8"))
    finding = state["outcomes"][0]["findings"][0]["id"] if state["outcomes"][0]["findings"] else None
    assert finding and main(["decide", "--suppress", finding, "--reason", "known"]) == ExitCode.OK
    capsys.readouterr()
    assert main(["scan"]) == ExitCode.OK
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK


def test_tools_with_unmet_conditions_are_skipped_with_their_note(ws, ext_file, capsys, monkeypatch):
    main(["ext", "add", str(ext_file)])
    configure(capsys, engine="mysql")
    start_build(ws, monkeypatch, capsys, PLAN.format(role="specialist", done="make up make down"))
    (ws / "db" / "secure").mkdir(parents=True)
    (ws / "db" / "secure" / "001.sql").write_text("select 1;\n", encoding="utf-8")
    git(ws, "add", "db")
    main(["commit", "schema", "--item", "C1"])
    main(["task", "advance", "--result", "pass"])
    capsys.readouterr()
    assert main(["scan"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "lint: skipped" in out and "lint is for pg only" in out and "probe: skipped" in out
    assert FakeRunner.commands == []
    assert main(["task", "advance", "--result", "pass"]) == ExitCode.OK
