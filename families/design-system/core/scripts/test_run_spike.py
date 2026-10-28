"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts

The container engine is a fake (a small Python script) so no container is started.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import run_spike as rs  # noqa: E402
import tally_votes as tv  # noqa: E402

SCRIPT = Path(__file__).parent / "run_spike.py"
CORE = Path(__file__).parent.parent
TODAY = "2026-10-12"
CFG, _ = rs.load_config(rs.DEFAULT_CONFIG)

FAKE_ENGINE = r'''
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
argv = sys.argv[1:]
mode = os.environ.get("FAKE_MODE", "ok")
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(argv, ensure_ascii=False) + "\n")
verb = argv[0] if argv else ""
if verb == "info":
    if mode == "info_fail":
        print("Cannot connect to the Docker daemon", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
if verb == "image" and argv[1] == "inspect":
    sys.exit(0 if os.environ.get("FAKE_IMAGE") == "present" else 1)
if verb == "pull":
    if mode == "pull_fail":
        print("manifest unknown", file=sys.stderr)
        sys.exit(1)
    print("pulled")
    sys.exit(0)
if verb == "rm":
    sys.exit(0)
if verb == "run":
    if mode == "hang":
        time.sleep(60)
    output = open(os.environ["FAKE_OUTPUT"], encoding="utf-8").read() if os.environ.get("FAKE_OUTPUT") else ""
    sys.stdout.write(output)
    sys.exit(int(os.environ.get("FAKE_CODE", "0")))
sys.exit(3)
'''


# --- builders --------------------------------------------------------------------------------------------------------------

def spec_text(**overrides) -> str:
    front = {
        "spike": "S-02", "layer": "data", "image": "postgres:16.4", "network": "none", "timeout": 60, "memory": "512m", "cpus": 1,
        "commands": ["psql --version", "echo done"],
        "expect": {"exit_code": 0, "output_contains": ["16.4"], "output_not_contains": ["ERROR"]},
    }
    for key, value in overrides.items():
        if value is None:
            front.pop(key, None)
        else:
            front[key] = value
    body = ("# Spike S-02: PostgreSQL 16.4 có trong image\n\n## Mục tiêu\n\nKiểm phiên bản đúng với NFR-01.\n\n## Lệnh\n\nIn phiên bản.\n\n"
            "## Kết quả mong đợi\n\nĐầu ra có 16.4.\n")
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def state_text(rows: list[tuple[str, str, str, str]] | None, heading="Spike được duyệt chạy") -> str:
    text = "# Trạng thái\n\n## Gate\n\n| Gate | Trạng thái |\n| --- | --- |\n| G4 | đang làm |\n\n"
    if rows is not None:
        text += f"## {heading}\n\n| ID | Người dùng nói (nguyên văn) | Ngày | sha256 đề bài |\n| --- | --- | --- | --- |\n"
        text += "".join(f"| {a} | {b} | {c} | {d} |\n" for a, b, c, d in rows)
    return text + "\n## Việc tiếp theo\n\n1. x\n"


class Env:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.ws = tmp_path / ".agent-workspace"
        (self.ws / "checks").mkdir(parents=True)
        self.spec = put(self.ws / "stack" / "layers" / "data" / "spikes" / "S-02-pg-version.md", spec_text())
        self.fake = tmp_path / "fake_engine.py"
        self.fake.write_text(FAKE_ENGINE, encoding="utf-8")
        self.log = tmp_path / "engine.log"
        self.output = tmp_path / "output.txt"
        self.output.write_text("psql (PostgreSQL) 16.4\ndone\n", encoding="utf-8")
        self.approve()

    @property
    def sha(self) -> str:
        return rs.spec_hash(self.spec.read_text(encoding="utf-8"))

    def approve(self, quote="S-02: chạy", date=TODAY, sha=None, spike="S-02") -> None:
        put(self.ws / "state.md", state_text([(spike, quote, date, self.sha if sha is None else sha)]))

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def verbs(self) -> list[str]:
        return [c[0] if c[0] != "image" else "image-inspect" for c in self.calls()]

    def run(self, *extra: str, mode="ok", code="0", image="present", spike="S-02", engine=True):
        args = [sys.executable, str(SCRIPT), "--workspace", str(self.ws), "--date", TODAY, "--spike", spike]
        if engine:
            args += ["--engine-prefix", sys.executable, "--engine-prefix", str(self.fake)]
        env = {**os.environ, "FAKE_MODE": mode, "FAKE_LOG": str(self.log), "FAKE_OUTPUT": str(self.output), "FAKE_CODE": code, "FAKE_IMAGE": image, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([*args, *extra], capture_output=True, text=True, encoding="utf-8", env=env)

    @property
    def result(self) -> Path:
        return self.ws / "stack" / "layers" / "data" / "spikes" / "S-02-pg-version.result.md"

    def result_front(self) -> dict:
        return tv.parse_frontmatter(self.result.read_text(encoding="utf-8"))[0]

    def report(self) -> str:
        return (self.ws / "checks" / f"spike-{TODAY}.md").read_text(encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def run_argv(env: Env) -> list[str]:
    return next(c for c in env.calls() if c[0] == "run")


# --- a passing run ---------------------------------------------------------------------------------------------------------

def test_a_spike_that_meets_its_expectations_passes(env):
    proc = env.run()
    assert proc.returncode == 0, proc.stdout
    front = env.result_front()
    assert front["result"] == "đạt" and front["spike"] == "S-02" and front["layer"] == "data" and front["image"] == "postgres:16.4"
    assert front["spec_sha256"] == env.sha and front["exit_code"] == 0 and front["ran_at"] == TODAY and front["network"] == "none"
    text = env.result.read_text(encoding="utf-8")
    assert "- [x] exit_code = 0 (thực tế 0)" in text and "- [x] đầu ra có \"16.4\"" in text and "- [x] đầu ra không có \"ERROR\"" in text
    assert "psql (PostgreSQL) 16.4" in text
    assert "đạt" in env.report()


def test_the_container_gets_no_host_access_and_has_limits(env):
    env.run()
    argv = run_argv(env)
    assert argv[:2] == ["run", "--rm"]
    pairs = {argv[i]: argv[i + 1] for i, a in enumerate(argv) if a.startswith("--") and i + 1 < len(argv)}
    assert pairs["--network"] == "none" and pairs["--memory"] == "512m" and pairs["--cpus"] == "1" and pairs["--pids-limit"] == "256"
    assert pairs["--security-opt"] == "no-new-privileges" and pairs["--entrypoint"] == "sh"
    assert argv[-4:-1] == ["postgres:16.4", "-ec", "psql --version\necho done"] or argv[-3:] == ["postgres:16.4", "-ec", "psql --version\necho done"]
    for forbidden in ("-v", "--volume", "--mount", "--privileged", "--cap-add", "--device", "--pid", "--ipc", "--userns", "--net", "-p", "--publish", "-e", "--env", "--env-file"):
        assert forbidden not in argv, forbidden


def test_the_network_comes_from_the_spec(env):
    put(env.spec, spec_text(network="bridge"))
    env.approve()
    assert env.run().returncode == 0
    argv = run_argv(env)
    assert argv[argv.index("--network") + 1] == "bridge"
    assert env.result_front()["network"] == "bridge"


def test_the_commands_run_in_one_container_one_per_line(env):
    put(env.spec, spec_text(commands=["echo 1", "echo 2 && echo 3", "false"]))
    env.approve()
    env.run()
    assert run_argv(env)[-1] == "echo 1\necho 2 && echo 3\nfalse" and run_argv(env)[-2] == "-ec"
    assert sum(1 for v in env.verbs() if v == "run") == 1


def test_an_image_that_is_present_is_not_pulled_and_a_missing_one_is(env):
    assert env.run(image="present").returncode == 0
    assert "pull" not in env.verbs()
    env.log.unlink()
    proc = env.run(image="absent")
    assert proc.returncode == 0 and env.verbs() == ["info", "image-inspect", "pull", "run"] or env.verbs()[-3:] == ["image-inspect", "pull", "run"]
    assert "đã kéo image postgres:16.4" in env.result.read_text(encoding="utf-8")


# --- a spike that does not pass --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("output, code, unchecked", [
    ("psql (PostgreSQL) 15.2\n", "0", "đầu ra có \"16.4\""),            # an expected string is missing
    ("psql (PostgreSQL) 16.4\nERROR: boom\n", "0", "đầu ra không có \"ERROR\""),  # a forbidden string is present
    ("psql (PostgreSQL) 16.4\n", "1", "exit_code = 0 (thực tế 1)"),      # the container exits with the wrong code
])
def test_unmet_expectations_make_the_spike_fail(env, output, code, unchecked):
    env.output.write_text(output, encoding="utf-8")
    proc = env.run(code=code)
    assert proc.returncode == 1 and "không đạt" in proc.stdout
    assert env.result_front()["result"] == "không đạt"
    assert f"- [ ] {unchecked}" in env.result.read_text(encoding="utf-8")


def test_a_non_zero_exit_code_can_be_the_expected_one(env):
    put(env.spec, spec_text(expect={"exit_code": 3, "output_contains": []}))
    env.approve()
    assert env.run(code="3").returncode == 0
    assert env.run(code="0").returncode == 1


def test_an_engine_failure_is_an_error_not_a_failed_expectation(env):
    env.output.write_text("docker: Error response from daemon: no such image\n", encoding="utf-8")
    proc = env.run(code="125")
    assert proc.returncode == 1
    assert env.result_front()["result"] == "lỗi" and "mã 125" in env.result.read_text(encoding="utf-8")


def test_a_failed_pull_is_an_error(env):
    proc = env.run(mode="pull_fail", image="absent")
    assert proc.returncode == 1 and env.result_front()["result"] == "lỗi"
    assert "manifest unknown" in env.result.read_text(encoding="utf-8") and "run" not in env.verbs()


def test_a_timeout_stops_the_container_and_is_an_error(env):
    put(env.spec, spec_text(timeout=1))
    env.approve()
    proc = env.run(mode="hang")
    assert proc.returncode == 1 and env.result_front()["result"] == "lỗi" and "quá 1s" in env.result.read_text(encoding="utf-8")
    removal = [c for c in env.calls() if c[0] == "rm"]
    assert removal and removal[0][1] == "-f" and removal[0][2].startswith("spike-s-02-") and removal[0][2] == run_argv(env)[run_argv(env).index("--name") + 1]


def test_without_a_working_engine_nothing_is_written_and_an_earlier_result_stays(env):
    assert env.run().returncode == 0
    proc = env.run(mode="info_fail")
    # --engine-prefix skips the search, so this is a normal run that rewrites the result (seconds differ): take "before" after it, right
    # before the one call that must not write
    assert proc.returncode in (0, 1)
    before = env.result.read_bytes()
    mtime = env.result.stat().st_mtime_ns
    proc = env.run("--engine", "podman", engine=False)  # no --engine-prefix: look for a real podman
    if "không có Docker hay Podman chạy được" in proc.stdout:
        assert proc.returncode == 1 and env.result.read_bytes() == before and env.result.stat().st_mtime_ns == mtime
        assert "LỖI (không chạy)" in env.report()


def test_the_engine_search_reports_every_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(rs.shutil, "which", lambda name: None)
    with pytest.raises(LookupError) as error:
        rs.find_engine(CFG, "auto", None)
    assert "docker: không có trong PATH" in str(error.value) and "podman: không có trong PATH" in str(error.value)


def test_the_engine_search_takes_the_first_that_answers(tmp_path, monkeypatch):
    calls = []

    class Done:
        def __init__(self, code):
            self.returncode, self.stdout = code, b"daemon not running\n" if code else b""

    monkeypatch.setattr(rs.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(rs, "run_command", lambda argv, timeout: calls.append(argv[0]) or Done(1 if argv[0].endswith("docker") else 0))
    assert rs.find_engine(CFG, "auto", None) == ("podman", ["/bin/podman"])
    assert calls == ["/bin/docker", "/bin/podman"]
    with pytest.raises(LookupError, match="docker: `docker info` lỗi"):
        rs.find_engine(CFG, "docker", None)


def test_long_output_keeps_the_head_and_the_tail(env):
    env.output.write_text("HEAD-LINE\n" + "x" * 200000 + "\nTAIL-LINE\n", encoding="utf-8")
    assert env.run().returncode == 1  # 16.4 is not in what is kept
    text = env.result.read_text(encoding="utf-8")
    assert "HEAD-LINE" in text and "TAIL-LINE" in text and "cắt " in text and len(text) < 100000


def test_output_with_code_fences_cannot_break_the_result_file(env):
    env.output.write_text("psql 16.4\n```\n## Kiểm\n- [x] giả\n````\n", encoding="utf-8")
    assert env.run().returncode == 0
    text = env.result.read_text(encoding="utf-8")
    assert "`````text" in text and text.rstrip().endswith("`````")
    assert tv.parse_frontmatter(text)[0]["result"] == "đạt"


# --- approval --------------------------------------------------------------------------------------------------------------

def refused(env, needle):
    proc = env.run()
    assert proc.returncode == 1 and needle in proc.stdout, proc.stdout
    assert env.calls() == [], "the engine must not be touched without approval"
    assert not env.result.exists()
    assert "TỪ CHỐI" in env.report()


def test_no_state_section_means_no_run(env):
    put(env.ws / "state.md", state_text(None))
    refused(env, "không có mục \"Spike được duyệt chạy\"")


def test_no_state_file_means_no_run(env):
    (env.ws / "state.md").unlink()
    refused(env, "state.md")


def test_no_row_for_the_spike_means_no_run(env):
    put(env.ws / "state.md", state_text([]))
    refused(env, "chưa có dòng người dùng đồng ý cho S-02")


def test_a_row_for_another_spike_does_not_approve_this_one(env):
    env.approve(spike="S-20", quote="S-20: chạy")
    refused(env, "chưa có dòng người dùng đồng ý cho S-02")


@pytest.mark.parametrize("quote", ["ok", "được", "duyệt đi", "S-02: duyệt", "S-02 chạy đi", "chạy", "S-020: chạy", "S-2: chạy", "G4: duyệt", "", "S-02: không chạy", "XS-02: chạy", "G4-S-02: chạy", "NFR-S-02: chạy"])
def test_only_the_users_exact_words_for_this_id_approve(env, quote):
    env.approve(quote=quote)
    refused(env, "không có lời người dùng dạng \"S-02: chạy\"")


@pytest.mark.parametrize("quote", ["S-02: chạy", "Được, S-02: chạy nhé", "s-02:chạy", "S-02 : chạy", "Các spike: S-01: chạy, S-02: chạy"])
def test_the_words_may_sit_in_a_longer_message(env, quote):
    env.approve(quote=quote)
    assert env.run().returncode == 0


@pytest.mark.parametrize("date", ["", "hôm nay", "2026-13-40", "12/10/2026"])
def test_the_approval_needs_a_real_date(env, date):
    env.approve(date=date)
    refused(env, "ngày hợp lệ")


@pytest.mark.parametrize("sha", ["", "abc", "0" * 64, "z" * 64])
def test_the_approval_must_carry_the_hash_of_the_spec(env, sha):
    env.approve(sha=sha)
    refused(env, "sha256 đề bài")


def test_a_spec_edited_after_the_approval_needs_a_new_one(env):
    assert env.run().returncode == 0
    env.log.unlink()
    before = env.result.read_text(encoding="utf-8")
    put(env.spec, spec_text(commands=["rm -rf /data", "psql --version"]))
    proc = env.run()
    assert proc.returncode == 1 and "đề bài đã đổi sau khi người dùng đồng ý" in proc.stdout
    assert env.calls() == [] and env.result.read_text(encoding="utf-8") == before and "TỪ CHỐI" in env.report()


def test_the_hash_ignores_line_endings_and_may_be_upper_case(env):
    env.spec.write_bytes(env.spec.read_bytes().replace(b"\n", b"\r\n"))
    env.approve(sha=env.sha.upper())
    assert env.sha == rs.spec_hash(env.spec.read_text(encoding="utf-8").replace("\r\n", "\n"))
    assert env.run().returncode == 0


def test_the_last_row_of_an_id_counts(env):
    put(env.ws / "state.md", state_text([("S-02", "S-02: chạy", TODAY, "0" * 64), ("S-02", "S-02: chạy", TODAY, env.sha)]))
    assert env.run().returncode == 0
    put(env.ws / "state.md", state_text([("S-02", "S-02: chạy", TODAY, env.sha), ("S-02", "ok", TODAY, env.sha)]))
    refused_env = env
    proc = refused_env.run()
    assert proc.returncode == 1


def test_show_prints_what_would_run_and_runs_nothing(env):
    proc = env.run("--show")
    assert proc.returncode == 0
    for needle in ("S-02", "postgres:16.4", "network: none", "psql --version", f"sha256 đề bài: {env.sha}", "đã có dòng hợp lệ"):
        assert needle in proc.stdout, needle
    assert env.calls() == [] and not env.result.exists()


def test_show_works_before_any_approval_and_says_so(env):
    put(env.ws / "state.md", state_text([]))
    proc = env.run("--show")
    assert proc.returncode == 0 and "CHƯA:" in proc.stdout and env.sha in proc.stdout


# --- the spec --------------------------------------------------------------------------------------------------------------

def show(env, text=None, name=None):
    if text is not None:
        put(name or env.spec, text)
    return env.run("--show")


@pytest.mark.parametrize("override, code", [
    ({"spike": None}, "spec-key-missing"), ({"image": None}, "spec-key-missing"), ({"commands": None}, "spec-key-missing"), ({"expect": None}, "spec-key-missing"),
    ({"layer": None}, "spec-key-missing"), ({"extra": 1}, "spec-key-unknown"), ({"spike": "S-09"}, "spec-id"), ({"layer": "backend"}, "spec-layer"),
    ({"image": "postgres"}, "spec-image-unpinned"), ({"image": "postgres:latest"}, "spec-image-unpinned"), ({"image": "registry.local:5000/pg"}, "spec-image-unpinned"),
    ({"image": "-v/:/host:x"}, "spec-image"), ({"image": "pg 16"}, "spec-image"), ({"image": "pg:16;rm"}, "spec-image"), ({"image": "pg@sha256:abc"}, "spec-image"), ({"image": ""}, "spec-image"),
    ({"network": "host"}, "spec-network"), ({"network": "container:other"}, "spec-network"),
    ({"timeout": 0}, "spec-timeout"), ({"timeout": 1801}, "spec-timeout"), ({"timeout": "60"}, "spec-timeout"), ({"timeout": True}, "spec-timeout"),
    ({"memory": "0m"}, "spec-memory"), ({"memory": "9g"}, "spec-memory"), ({"memory": "1gb"}, "spec-memory"), ({"memory": "-1g"}, "spec-memory"), ({"memory": 512}, "spec-memory"),
    ({"cpus": 0}, "spec-cpus"), ({"cpus": 9}, "spec-cpus"), ({"cpus": "2"}, "spec-cpus"), ({"cpus": True}, "spec-cpus"),
    ({"commands": []}, "spec-commands"), ({"commands": [""]}, "spec-commands"), ({"commands": [1]}, "spec-commands"), ({"commands": "echo hi"}, "spec-commands"),
    ({"commands": ["echo"] * 21}, "spec-commands"), ({"commands": ["x" * 4001]}, "spec-commands"),
    ({"expect": {"exit_code": 256}}, "spec-expect"), ({"expect": {"exit_code": "0"}}, "spec-expect"), ({"expect": {"nope": 1}}, "spec-expect"),
    ({"expect": {"output_contains": "16.4"}}, "spec-expect"), ({"expect": {"output_contains": [""]}}, "spec-expect"), ({"expect": []}, "spec-expect"),
])
def test_an_invalid_spec_is_refused(env, override, code):
    proc = show(env, spec_text(**override))
    assert proc.returncode == 1 and f"[{code}]" in proc.stdout, proc.stdout
    assert env.calls() == []


@pytest.mark.parametrize("override", [
    {"image": "postgres:16.4"}, {"image": "ghcr.io/org/app:1.2"}, {"image": "registry.local:5000/team/pg:16"}, {"image": "pg@sha256:" + "a" * 64},
    {"image": "pg:16@sha256:" + "b" * 64}, {"network": "bridge"}, {"timeout": 1800}, {"memory": "8g"}, {"memory": "256M"}, {"cpus": 0.5}, {"cpus": 8},
    {"commands": ["echo hi"] * 20}, {"expect": {}}, {"expect": {"exit_code": 255}}, {"timeout": None, "memory": None, "cpus": None, "network": None},
])
def test_a_valid_spec_is_accepted(env, override):
    proc = show(env, spec_text(**override))
    assert proc.returncode == 0, proc.stdout


@pytest.mark.parametrize("title", ["Mục tiêu", "Lệnh", "Kết quả mong đợi"])
def test_each_section_is_needed_and_must_be_filled(env, title):
    text = spec_text()
    without = re.sub(rf"## {title}\n\n.*?\n\n", "", text + "\n", count=1, flags=re.S) if title != "Kết quả mong đợi" else text.split("## Kết quả mong đợi")[0]
    proc = show(env, without)
    assert proc.returncode == 1 and "spec-section" in proc.stdout and title in proc.stdout
    empty = text.replace(f"## {title}\n\n", f"## {title}\n\n<chỗ trống của template>\n\n", 1)
    empty = re.sub(rf"(## {title}\n\n<chỗ trống của template>\n\n).*?(\n\n|\Z)", r"\1", empty, count=1, flags=re.S)
    assert "spec-section" in show(env, empty).stdout


def test_a_spec_with_no_frontmatter_a_duplicate_key_or_a_bad_name(env):
    assert "spec-frontmatter" in show(env, "# Spike\n\n## Mục tiêu\n\nx\n").stdout
    dup = spec_text().replace("image: postgres:16.4\n", "image: postgres:16.4\nimage: postgres:latest\n")
    proc = show(env, dup)
    assert proc.returncode == 1 and "spec-frontmatter" in proc.stdout and "lặp" in proc.stdout


def test_a_spec_outside_the_spikes_folder_is_refused(env):
    other = put(env.ws / "stack" / "layers" / "data" / "S-05-misplaced.md", spec_text(spike="S-05"))
    proc = env.run("--show", spike="S-05")
    assert proc.returncode == 2  # not found where specs live: stack/layers/*/spikes/
    assert other.exists()


# --- arguments -------------------------------------------------------------------------------------------------------------

def test_unknown_and_ambiguous_spikes_and_bad_arguments_exit_two(env):
    assert env.run(spike="S-99").returncode == 2
    assert env.run(spike="spike2").returncode == 2
    assert env.run(spike="S-").returncode == 2
    put(env.ws / "stack" / "layers" / "backend" / "spikes" / "S-02-other.md", spec_text(layer="backend"))
    proc = env.run()
    assert proc.returncode == 2 and "2 đề bài" in proc.stderr
    missing = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(env.root / "nope"), "--spike", "S-02"], capture_output=True, text=True, encoding="utf-8")
    assert missing.returncode == 2
    bad = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(env.ws), "--spike", "S-02", "--config", str(env.root / "none.yaml")], capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2
    assert env.calls() == []


def test_a_result_file_is_never_taken_for_a_spec(env):
    assert env.run().returncode == 0
    assert rs.find_specs(env.ws, "S-02", CFG) == [env.spec]


# --- the result as a fact for check_workspace.py -----------------------------------------------------------------------------

def test_current_result_is_the_state_only_while_the_spec_is_unchanged(env):
    assert rs.current_result(env.spec, CFG) is None  # nothing run yet
    assert env.run().returncode == 0
    assert rs.current_result(env.spec, CFG) == "đạt"
    put(env.spec, spec_text(commands=["echo changed"]))
    assert rs.current_result(env.spec, CFG) is None   # the result belongs to an older spec
    env.approve()
    env.output.write_text("nothing\n", encoding="utf-8")
    env.run()
    assert rs.current_result(env.spec, CFG) == "không đạt"


def test_a_result_that_was_edited_to_say_pass_still_carries_the_old_hash(env):
    env.output.write_text("nothing\n", encoding="utf-8")
    env.run()
    text = env.result.read_text(encoding="utf-8").replace("result: không đạt", "result: đạt")
    put(env.result, text)
    put(env.spec, spec_text(commands=["echo changed"]))
    assert rs.current_result(env.spec, CFG) is None


def test_rerun_replaces_the_result(env):
    env.output.write_text("nothing\n", encoding="utf-8")
    assert env.run().returncode == 1
    env.output.write_text("psql 16.4\n", encoding="utf-8")
    assert env.run().returncode == 0
    assert env.result_front()["result"] == "đạt"


# --- data and documents ----------------------------------------------------------------------------------------------------

def test_the_data_file_is_valid_and_says_which_layers_need_a_spike_at_xl():
    cfg, errors = rs.load_config(rs.DEFAULT_CONFIG)
    assert not errors and cfg is not None
    assert cfg.xl_required_layers == ["data", "messaging", "backend", "infrastructure"] and cfg.optional_layers == ["tooling", "third-party"]
    assert cfg.default_network == "none" and "latest" in cfg.forbidden_tags and cfg.engines == ["docker", "podman"]
    assert set(cfg.xl_required_layers).isdisjoint(cfg.optional_layers)


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("engines"), lambda d: d.update(default_network="host"), lambda d: d["timeout"].update(max=0), lambda d: d["approval"].update(phrase="chạy"),
    lambda d: d.update(id_pattern="("), lambda d: d["memory"].update(default="lots"), lambda d: d.pop("states"), lambda d: d.update(networks=[]),
])
def test_a_bad_data_file_is_refused(tmp_path, mutate):
    data = yaml.safe_load(rs.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "spike.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    cfg, errors = rs.load_config(path)
    assert cfg is None and errors


def test_the_template_has_the_keys_the_script_reads():
    text = (CORE / "templates" / "workspace" / "spike.md").read_text(encoding="utf-8")
    front = text.split("---")[1]
    assert tuple(re.findall(r"^([a-z_]+):", front, re.MULTILINE)) == rs.SPEC_KEYS
    for title in rs.SECTIONS:
        assert f"## {title}" in text


def test_the_state_template_has_the_approval_table_the_script_reads():
    text = (CORE / "templates" / "workspace" / "state.md").read_text(encoding="utf-8")
    lines = tv.section(text, CFG.section)
    assert lines is not None
    header = next(line for line in lines if line.lstrip().startswith("|"))
    assert tv.split_cells(header) == ["ID", "Người dùng nói (nguyên văn)", "Ngày", "sha256 đề bài"]
    assert "S-02: chạy" in "\n".join(lines)


def test_the_documents_describe_the_spike_flow():
    stages = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")
    g4 = stages.split("## G4.")[1].split("## G5.")[0]
    assert "run_spike.py" in g4 and "XL" in g4 and "S-xx: chạy" in g4 and ".result.md" in g4
    for layer in CFG.xl_required_layers:
        assert layer in g4, layer
    permissions = (CORE / "workflow" / "permissions.md").read_text(encoding="utf-8")
    assert ".result.md" in permissions and "run_spike.py" in permissions and "S-xx: chạy" in permissions
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    assert "run_spike.py" in plan and "spike.yaml" in plan
