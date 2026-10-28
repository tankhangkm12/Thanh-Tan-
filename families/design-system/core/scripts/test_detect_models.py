"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import detect_models as dm  # noqa: E402

AGY_MODELS = "Fetching available models...\ngemini-3.1-pro-high\tGemini 3.1 Pro (High)\nclaude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)\n"
TODAY = "2026-10-12"
ALL = ["sonnet", "opus", "haiku", "fable", "agy:gemini-3.1-pro-high", "agy:claude-sonnet-4-6"]


def done(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class Fake:
    """Stands in for PATH and subprocess: `tools` = names found, `fail` = substrings of commands that fail."""

    def __init__(self, tools=("claude", "agy"), claude_version="2.1.300 (Claude Code)", fail=(), timeout=()):
        self.tools, self.claude_version, self.fail, self.timeout = set(tools), claude_version, tuple(fail), tuple(timeout)
        self.calls: list[list[str]] = []

    def which(self, name):
        return f"/bin/{name}" if name in self.tools else None

    def run(self, argv, timeout):
        self.calls.append(argv)
        line = " ".join(argv)
        if any(t in line for t in self.timeout):
            raise subprocess.TimeoutExpired(argv, timeout)
        if any(f in line for f in self.fail):
            return done(1, "", "model not found")
        if argv[0].endswith("claude") and argv[1] == "--version":
            return done(0, self.claude_version)
        if argv[0].endswith("agy") and argv[1] == "models":
            return done(0, AGY_MODELS)
        return done(0, "ok")


def detect(fake=None, existing="", env=None, **kwargs):
    fake = fake or Fake()
    return dm.detect(existing, env or {}, fake.which, fake.run, TODAY, **kwargs)


def row(rows, name):
    return next(r for r in rows if r.name == name)


def test_lists_claude_aliases_as_subagent_and_agy_models_as_cli():
    text, rows, warnings = detect()
    assert [r.name for r in rows if r.kind == "subagent"] == ["sonnet", "opus", "haiku", "fable"]
    assert [r.name for r in rows if r.kind == "cli"] == ["agy:gemini-3.1-pro-high", "agy:claude-sonnet-4-6"]
    assert warnings == []
    assert all(r.status == dm.STATUS_STATIC for r in rows)
    assert "### Subagent Claude" in text and "### Qua CLI ngoài" in text
    assert "| sonnet | subagent |" in text and "| agy:gemini-3.1-pro-high | cli |" in text


def test_web_column_follows_tools_for_claude_and_is_unknown_for_cli_unless_declared():
    _, rows, _ = detect(web_models={"gemini-3.1-pro-high"})
    assert "WebSearch" in row(rows, "sonnet").web
    assert row(rows, "agy:gemini-3.1-pro-high").web == "có"
    assert row(rows, "agy:claude-sonnet-4-6").web == "chưa rõ"


@pytest.mark.parametrize("name", [dm.ENV_OVERRIDE, dm.ENV_FORCE])
def test_warns_when_subagent_model_env_is_set(name):
    _, _, warnings = detect(env={name: "haiku"})
    assert len(warnings) == 1 and f"`{name}`" in warnings[0]


def test_no_warning_when_env_is_empty_or_unset():
    assert detect(env={dm.ENV_OVERRIDE: "", dm.ENV_FORCE: ""})[2] == []


def test_override_warning_depends_on_claude_code_version():
    old = detect(Fake(claude_version="2.1.200"), env={dm.ENV_OVERRIDE: "haiku"})[2][0]
    new = detect(Fake(claude_version="2.1.300"), env={dm.ENV_OVERRIDE: "haiku"})[2][0]
    assert "trước v2.1.251" in old and "ghi đè cả `model`" in old
    assert "chỉ là mặc định" in new


def test_missing_cli_is_a_warning_not_a_row():
    _, rows, warnings = detect(Fake(tools=("claude",)))
    assert not [r for r in rows if r.kind == "cli"]
    assert any("`agy`" in w and "PATH" in w for w in warnings)


def test_missing_claude_still_lists_aliases_but_cannot_probe():
    fake = Fake(tools=("agy",))
    _, rows, warnings = detect(fake, probe_names=ALL)
    assert any("`claude`" in w for w in warnings)
    assert row(rows, "sonnet").status.startswith(dm.STATUS_BAD)
    assert row(rows, "agy:gemini-3.1-pro-high").status == dm.STATUS_OK


def test_probe_marks_failures_and_successes():
    fake = Fake(fail=("--model haiku",), timeout=("claude-sonnet-4-6",))
    _, rows, warnings = detect(fake, probe_names=ALL)
    assert row(rows, "sonnet").status == dm.STATUS_OK
    assert row(rows, "haiku").status.startswith(dm.STATUS_BAD) and "model not found" in row(rows, "haiku").status
    assert row(rows, "agy:claude-sonnet-4-6").status.startswith(dm.STATUS_BAD) and "quá" in row(rows, "agy:claude-sonnet-4-6").status
    assert any("`haiku`" in w for w in warnings)


def test_run_without_probe_never_calls_a_model():
    fake = Fake()
    detect(fake)
    assert not [c for c in fake.calls if "-p" in c]


def test_nonzero_exit_with_output_counts_as_failed_probe():
    fake = Fake()
    original = fake.run

    def run(argv, timeout):
        if "-p" in argv and argv[argv.index("--model") + 1] == "opus":
            return done(1, "ok but crashed", "boom")
        return original(argv, timeout)

    _, rows, _ = dm.detect("", {}, fake.which, run, TODAY, probe_names=["opus"])
    assert row(rows, "opus").status.startswith(dm.STATUS_BAD) and "mã 1" in row(rows, "opus").status


def test_empty_output_counts_as_failed_probe():
    fake = Fake()
    original = fake.run

    def run(argv, timeout):
        if "-p" in argv and "--model" in argv and argv[argv.index("--model") + 1] == "opus":
            return done(0, "   ")
        return original(argv, timeout)

    _, rows, _ = dm.detect("", {}, fake.which, run, TODAY, probe_names=["opus"])
    assert row(rows, "opus").status.startswith(dm.STATUS_BAD)


def test_rerun_keeps_manual_cells_gan_model_table_and_unusable_mark():
    text, _, _ = detect()
    text = text.replace("| sonnet | subagent |", "| sonnet | subagent |", 1)
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("| sonnet |"))
    cells = dm.split_row(lines[i])
    cells[4], cells[5], cells[6] = f"{dm.STATUS_BAD}: hết hạn mức", "suy luận dài", "chậm"
    lines[i] = "| " + " | ".join(cells) + " |"
    text = "\n".join(lines) + "\n| T-001 | designer | sonnet | 2026-10-12 |\n"
    again, rows, _ = detect(existing=text)
    sonnet = row(rows, "sonnet")
    assert (sonnet.strengths, sonnet.limits) == ("suy luận dài", "chậm")
    assert sonnet.status == f"{dm.STATUS_BAD}: hết hạn mức"
    assert "| T-001 | designer | sonnet | 2026-10-12 |" in again
    assert again.count(dm.BEGIN) == 1 and again.count(dm.ASSIGN_HEADING) == 1


def test_probe_replaces_old_unusable_mark():
    text, _, _ = detect()
    text = text.replace(dm.STATUS_STATIC, dm.STATUS_BAD + ": cũ", 1)
    _, rows, _ = detect(existing=text, probe_names=ALL)
    assert all(r.status == dm.STATUS_OK for r in rows)


def test_rerun_is_stable():
    first, _, _ = detect()
    second, _, _ = detect(existing=first)
    assert first == second


def test_hand_written_file_without_markers_is_kept_and_block_added():
    existing = "# Danh mục model\n\nKhai tay, chưa dò:\n- sonnet\n"
    text, _, _ = detect(existing=existing)
    assert "Khai tay, chưa dò:" in text and dm.BEGIN in text
    assert text.index(dm.BEGIN) < text.index("Khai tay")


def test_pipe_in_cell_is_escaped():
    assert dm.cell("a | b\nc") == "a \\| b c"
    assert dm.split_row("| a \\| b | c |") == ["a | b", "c"]


def test_parse_agy_models_skips_header():
    assert dm.parse_agy_models(AGY_MODELS) == [("gemini-3.1-pro-high", "Gemini 3.1 Pro (High)"), ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)")]


def probed_calls(fake):
    return [c for c in fake.calls if "-p" in c]


def test_probe_calls_only_the_listed_models():
    fake = Fake()
    _, rows, _ = detect(fake, probe_names=["sonnet", "agy:claude-sonnet-4-6"])
    assert [c[c.index("--model") + 1] for c in probed_calls(fake)] == ["sonnet", "claude-sonnet-4-6"]
    assert row(rows, "sonnet").status == dm.STATUS_OK and row(rows, "agy:claude-sonnet-4-6").status == dm.STATUS_OK
    for name in ("opus", "haiku", "fable", "agy:gemini-3.1-pro-high"):
        assert row(rows, name).status == dm.STATUS_STATIC


def test_model_not_probed_is_not_usable_until_probed():
    _, rows, _ = detect()
    assert not any(r.usable for r in rows)
    _, rows, _ = detect(probe_names=["haiku"])
    assert [r.name for r in rows if r.usable] == ["haiku"]


def test_static_rerun_keeps_an_earlier_probe_result():
    first, _, _ = detect(probe_names=["sonnet"])
    _, rows, _ = detect(existing=first)
    assert row(rows, "sonnet").status == dm.STATUS_OK and row(rows, "opus").status == dm.STATUS_STATIC


def test_probe_name_outside_the_catalog_is_an_error():
    with pytest.raises(dm.UnknownModels) as error:
        detect(probe_names=["sonet"])
    assert "sonet" in str(error.value) and "sonnet" in str(error.value)


@pytest.fixture
def cli(tmp_path: Path, monkeypatch):
    workspace = tmp_path / ".agent-workspace"
    workspace.mkdir()
    fake = Fake(tools=("claude",))
    monkeypatch.setattr(dm.shutil, "which", fake.which)
    monkeypatch.setattr(dm, "run_command", fake.run)
    monkeypatch.setattr(dm.os, "environ", {})
    return workspace, fake


def test_main_probe_without_a_list_is_an_argument_error_and_probes_nothing(cli, capsys):
    workspace, fake = cli
    for argv in (["--probe"], ["--probe", ""], ["--probe", " , "]):
        with pytest.raises(SystemExit) as stop:
            dm.main(["--workspace", str(workspace), *argv])
        assert stop.value.code == 2
    assert fake.calls == [] and not (workspace / "models.md").exists()
    assert "--probe cần danh sách" in capsys.readouterr().err


def test_main_unknown_probe_name_is_an_argument_error_and_writes_nothing(cli):
    workspace, fake = cli
    with pytest.raises(SystemExit) as stop:
        dm.main(["--workspace", str(workspace), "--probe", "sonnet,nope"])
    assert stop.value.code == 2
    assert probed_calls(fake) == [] and not (workspace / "models.md").exists()


def test_main_probe_list_calls_only_those_models(cli):
    workspace, fake = cli
    assert dm.main(["--workspace", str(workspace), "--probe", "sonnet,haiku", "--date", TODAY]) == 0
    assert [c[c.index("--model") + 1] for c in probed_calls(fake)] == ["sonnet", "haiku"]
    text = (workspace / "models.md").read_text(encoding="utf-8")
    assert "thử gọi: sonnet, haiku" in text


def test_main_exit_codes_and_report(cli):
    workspace, fake = cli
    assert dm.main(["--workspace", str(workspace / "missing")]) == 2  # no workspace
    assert dm.main(["--workspace", str(workspace), "--date", TODAY]) == 0  # nothing probed is not an error
    fake.fail = ("-p",)
    assert dm.main(["--workspace", str(workspace), "--probe", "sonnet,opus", "--date", TODAY]) == 1  # every probed model failed
    assert "không có model nào dùng được" in (workspace / "checks" / f"models-{TODAY}.md").read_text(encoding="utf-8")
    fake.fail = ()
    assert dm.main(["--workspace", str(workspace), "--probe", "sonnet", "--date", TODAY]) == 0


def test_cli_rows_say_in_the_limits_column_that_only_the_locked_call_is_isolated():
    text, rows, _ = detect()
    limits = row(rows, "agy:gemini-3.1-pro-high").limits
    assert "call_council_cli.py" in limits and "agent khóa công cụ" in limits and "KHÔNG cô lập" in limits
    assert row(rows, "sonnet").limits == dm.UNSET   # a Claude subagent has the tools its agent file grants
    assert "KHÔNG cô lập" in text


def edit_row(text: str, name: str, old: str, new: str) -> str:
    lines = text.split("\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(f"| {name} |"))
    assert old in lines[index]
    lines[index] = lines[index].replace(old, new)
    return "\n".join(lines)


def test_a_limits_cell_written_by_a_person_wins_and_an_unset_one_gets_the_default():
    text, rows, _ = detect()
    default = row(rows, "agy:gemini-3.1-pro-high").limits
    mine = edit_row(text, "agy:claude-sonnet-4-6", default, "giới hạn tay của tôi")
    _, rows, _ = detect(existing=mine)
    assert row(rows, "agy:claude-sonnet-4-6").limits == "giới hạn tay của tôi"
    assert "KHÔNG cô lập" in row(rows, "agy:gemini-3.1-pro-high").limits
    # a file written before the default existed has "chưa khai" in the cell: the next run fills it in
    old = edit_row(text, "agy:gemini-3.1-pro-high", default, dm.UNSET)
    assert row(detect(existing=old)[1], "agy:gemini-3.1-pro-high").limits == default
