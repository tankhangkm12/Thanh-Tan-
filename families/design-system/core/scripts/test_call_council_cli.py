"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts

The outside CLI is a fake (a small Python script) so no model is called.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import call_council_cli as cc  # noqa: E402
import detect_models as dm  # noqa: E402
import tally_votes as tv  # noqa: E402
from test_tally_votes import THREE, brief_text, default_vote, put, vote_text  # noqa: E402

SCRIPT = Path(__file__).parent / "call_council_cli.py"
TALLY = Path(__file__).parent / "tally_votes.py"
CORE = Path(__file__).parent.parent
COUNCIL = CORE / "claude" / "agents" / "council"
TODAY = "2026-10-12"
DEC = "D-001-arch"
MODEL = "agy:fake-model-1"
MEMBER = "agy-fake-model-1"

FAKE = r'''
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
mode = os.environ.get("FAKE_MODE", "ok")
log = os.environ.get("FAKE_LOG")
argv = sys.argv[1:]


def record(**kw):
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(kw, ensure_ascii=False) + "\n")


response = open(os.environ["FAKE_RESPONSE"], encoding="utf-8").read() if os.environ.get("FAKE_RESPONSE") else ""
agent = argv[argv.index("--agent") + 1] if "--agent" in argv else None
definition = os.path.join(os.getcwd(), ".agents", "agents", f"{agent}.md") if agent else None
agent_text = open(definition, encoding="utf-8").read() if definition and os.path.isfile(definition) else None
nonce = (re.search(r"NONCE-[0-9a-f]+", agent_text) or [None])[0] if agent_text else None


def answer(prompt):
    # the canary asks for the code that only the agent's system prompt holds; a CLI that ignores --agent ("ghost") cannot know it
    if "Mã xác nhận cấu hình" in prompt:
        return (nonce if nonce and mode != "ghost" else "UNKNOWN"), True
    return ("" if mode == "empty" else response), False


if "--input-format" in argv:
    messages = [json.loads(line) for line in sys.stdin.buffer.read().decode("utf-8").splitlines() if line.strip()]
    prompt = messages[0]["message"]["content"]
    text, canary = answer(prompt)
    record(kind="stream", canary=canary, argv=argv, cwd=os.getcwd(), messages=messages, agent=agent, agent_text=agent_text)
    if mode == "reject_stream":
        print("flag provided but not defined: -input-format", file=sys.stderr)
        sys.exit(2)
    if mode == "hang":
        time.sleep(60)
    print(json.dumps({"event": "init", "init": {"model": "fake", "agent": agent}}))
    if not canary and mode == "no_result":
        sys.exit(0)
    if not canary and mode == "garbage":
        print("not json at all")
        sys.exit(0)
    print(json.dumps({"event": "step_update", "step_update": {"step_index": 0, "state": "DONE", "step_type": "user_input"}}))
    if (mode == "tool_step" and not canary) or (mode == "canary_tool_step" and canary):
        print(json.dumps({"event": "step_update", "step_update": {"step_index": 1, "state": "DONE", "step_type": "tool"}}))
    print(json.dumps({"event": "step_update", "step_update": {"step_index": 2, "state": "DONE", "step_type": "agent_response", "text_delta": text}}))
    failing = not canary and mode in ("error_status", "exit_nonzero")
    body = {"status": "ERROR" if not canary and mode == "error_status" else "SUCCESS", "response": text}
    if body["status"] == "ERROR":
        body["error"] = "model overloaded"
    print(json.dumps({"event": "result", "result": body}, ensure_ascii=False))
    sys.exit(3 if failing else 0)
else:
    prompt = argv[argv.index("-p") + 1]
    text, canary = answer(prompt)
    record(kind="argv", canary=canary, argv=argv, cwd=os.getcwd(), agent=agent, agent_text=agent_text)
    if mode == "argv_fail" and not canary:
        print("boom", file=sys.stderr)
        sys.exit(4)
    print(text)
'''


# --- fixtures --------------------------------------------------------------------------------------------------------------

def models_md(rows: list[dm.ModelRow]) -> str:
    return dm.merge_into("", dm.render_block(rows, [], None, TODAY, []))


def cli_row(name="agy:fake-model-1", status=dm.STATUS_OK, kind="cli", how=None) -> dm.ModelRow:
    model_id = name.split(":", 1)[1] if ":" in name else name
    return dm.ModelRow(name=name, kind=kind, how=how or f"agy -p <prompt> --model {model_id} (chỉ qua `call_council_cli.py`, thành viên hội đồng); Fake", web="chưa rõ", status=status)


class Env:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.ws = tmp_path / ".agent-workspace"
        (self.ws / "checks").mkdir(parents=True)
        put(self.ws / "decisions" / DEC / "brief.md", brief_text())
        put(self.ws / "models.md", models_md([cli_row(), cli_row("agy:other-model"), cli_row("agy:untested", status=dm.STATUS_STATIC),
                                              cli_row("agy:broken", status=dm.STATUS_BAD + ": mã 1"),
                                              dm.ModelRow("sonnet", "subagent", 'Agent tool, tham số `model: "sonnet"`', "có", dm.STATUS_OK)]))
        self.fake = tmp_path / "fake_cli.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.log = tmp_path / "fake.log"
        self.response = tmp_path / "response.txt"
        self.set_response("---\nplaceholder\n---\n")
        self.votes = self.ws / "decisions" / DEC / "votes"

    def set_response(self, text: str) -> None:
        self.response.write_text(text, encoding="utf-8", newline="")

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def real_calls(self) -> list[dict]:
        """The calls that carry the vote prompt (the others are the lock check, `canary`)."""
        return [c for c in self.calls() if not c["canary"]]

    def run(self, *extra: str, mode="ok", round_="1", perspective="fit", model=MODEL, decision=DEC, prefix=True):
        args = [sys.executable, str(SCRIPT), "--workspace", str(self.ws), "--date", TODAY, "--decision", decision, "--round", round_,
                "--perspective", perspective, "--model", model]
        if prefix:
            args += ["--cli-prefix", sys.executable, "--cli-prefix", str(self.fake)]
        env = {**os.environ, "FAKE_MODE": mode, "FAKE_LOG": str(self.log), "FAKE_RESPONSE": str(self.response), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([*args, *extra], capture_output=True, text=True, encoding="utf-8", env=env)

    def vote_file(self, perspective="fit", round_=1, member=MEMBER) -> Path:
        return self.votes / f"r{round_}-{perspective}-{member}.md"


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def good_vote(perspective="fit", round_=1, choice="A", member=MEMBER, model="fake-model-1") -> str:
    data = default_vote(perspective, member=member, model=model, choice=choice, round_=round_)
    return vote_text(data)


def prompt_of(env: Env, index=0) -> str:
    return env.real_calls()[index]["messages"][0]["message"]["content"]


# --- the call ------------------------------------------------------------------------------------------------------------

def test_a_vote_is_written_verbatim_with_surrounding_blank_space_trimmed(env):
    answer = good_vote()
    env.set_response("\n\n" + answer + "\n\n\n")
    proc = env.run()
    assert proc.returncode == 0, proc.stdout
    assert env.vote_file().read_text(encoding="utf-8") == answer.strip() + "\n"
    assert "cách gọi: stdin" in proc.stdout


def test_the_prompt_is_the_body_the_brief_and_a_header_and_nothing_else(env):
    env.set_response(good_vote())
    other = put(env.votes / "r1-cost-ops-someone.md", "SECRET-OTHER-VOTE")
    put(env.ws / "decisions" / DEC / "tally.md", "SECRET-TALLY")
    put(env.ws / "decisions" / DEC / "decision.md", "SECRET-DECISION")
    assert env.run().returncode == 0 and other.exists()
    prompt = prompt_of(env)
    for line in ("- decision: D-001", "- round: 1", "- perspective: fit", f"- member: {MEMBER}", "- model: fake-model-1", "- via: cli"):
        assert line in prompt
    body = cc.council_body(COUNCIL / "fit.md")
    assert body in prompt and brief_text().strip() in prompt
    assert "tools: Read, Write" not in prompt and "omitClaudeMd" not in prompt        # frontmatter removed
    assert "Cách giao phiếu (Claude Code)" not in prompt and "Orchestrator truyền" not in prompt  # cut at <!-- body-end -->
    assert "TÓM TẮT VÒNG 1" not in prompt.split("=== HƯỚNG DẪN ===")[0] or "round: 2" in prompt
    for secret in ("SECRET-OTHER-VOTE", "SECRET-TALLY", "SECRET-DECISION"):
        assert secret not in prompt
    assert prompt.index("=== HƯỚNG DẪN ===") < prompt.index("=== BRIEF ===") < prompt.index("=== HẾT ===")


def test_the_cli_gets_the_stdin_flags_the_model_and_runs_in_an_empty_folder(env):
    env.set_response(good_vote())
    assert env.run().returncode == 0
    call = env.real_calls()[0]
    assert call["kind"] == "stream"
    assert call["argv"] == ["--model", "fake-model-1", "--input-format", "stream-json", "--output-format", "stream-json", "-p=", "--agent", "council-member"]
    assert call["messages"][0]["event"] == "user"
    cwd = Path(call["cwd"])
    assert cwd != env.ws and cwd != env.root and not str(cwd).startswith(str(env.ws))
    assert not cwd.exists()  # the temporary folder is removed afterwards


def test_round_two_adds_the_anonymous_summary_and_needs_it(env):
    env.set_response(good_vote(round_=2))
    proc = env.run(round_="2")
    assert proc.returncode == 1 and "r1-summary.md" in proc.stdout and not env.vote_file(round_=2).exists()
    put(env.votes / "r1-summary.md", "# Tóm tắt\n\n## Ý kiến 1\n\nLý do ẩn danh duy nhất XYZ.\n")
    proc = env.run(round_="2")
    assert proc.returncode == 0, proc.stdout
    prompt = prompt_of(env)
    assert "- round: 2" in prompt and "Lý do ẩn danh duy nhất XYZ." in prompt and "=== TÓM TẮT VÒNG 1" in prompt
    assert env.vote_file(round_=2).exists()


def test_round_one_has_no_summary_even_if_the_file_exists(env):
    put(env.votes / "r1-summary.md", "SUMMARY-TOKEN")
    env.set_response(good_vote())
    assert env.run().returncode == 0
    assert "SUMMARY-TOKEN" not in prompt_of(env)


def test_non_ascii_survives_the_trip(env):
    answer = good_vote().replace("A đáp ứng TC-01 tốt hơn", "Phương án A đáp ứng TC-01 tốt hơn — đ ư ơ ạ ệ 漢字")
    env.set_response(answer)
    assert env.run().returncode == 0
    assert "漢字" in env.vote_file().read_text(encoding="utf-8")
    assert "Phù hợp và vừa sức" in prompt_of(env)


def test_the_votes_of_a_fake_council_pass_tally_votes(env):
    for perspective in THREE:
        member = f"agy-model-{perspective}"
        env.set_response(good_vote(perspective, member=member, model=f"model-{perspective}"))
        put(env.ws / "models.md", models_md([cli_row(f"agy:model-{perspective}")]))
        assert env.run(perspective=perspective, model=f"agy:model-{perspective}").returncode == 0
    proc = subprocess.run([sys.executable, str(TALLY), "--workspace", str(env.ws), "--date", TODAY], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout
    assert "đề xuất phương án A" in (env.ws / "decisions" / DEC / "decision.md").read_text(encoding="utf-8")


def test_a_vote_in_the_wrong_format_is_written_and_tally_votes_rejects_it(env):
    env.set_response("Tôi chọn phương án A vì nó tốt hơn.")
    proc = env.run()
    assert proc.returncode == 0 and "tally_votes.py sẽ từ chối" in proc.stdout
    assert env.vote_file().read_text(encoding="utf-8") == "Tôi chọn phương án A vì nó tốt hơn.\n"
    tally = subprocess.run([sys.executable, str(TALLY), "--workspace", str(env.ws), "--date", TODAY], capture_output=True, text=True, encoding="utf-8")
    assert tally.returncode == 1 and "vote-frontmatter" in tally.stdout


def test_a_fenced_vote_is_not_repaired(env):
    env.set_response("```markdown\n" + good_vote() + "```\n")
    assert env.run().returncode == 0
    assert env.vote_file().read_text(encoding="utf-8").startswith("```markdown")


# --- the model ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("model, code", [
    ("agy:untested", 1), ("agy:broken", 1),     # chưa thử / không dùng được: not usable
    ("agy:nope", 2), ("sonnet", 2), ("gpt", 2),  # not in models.md / not a cli row
])
def test_only_a_cli_model_that_passed_its_probe_is_called(env, model, code):
    env.set_response(good_vote())
    proc = env.run(model=model)
    assert proc.returncode == code, proc.stdout + proc.stderr
    assert env.calls() == []
    assert not env.votes.exists() or not list(env.votes.glob("*"))


def test_models_md_missing_is_an_error(env):
    (env.ws / "models.md").unlink()
    proc = env.run()
    assert proc.returncode == 1 and "detect_models.py" in proc.stdout


def test_the_command_cell_must_name_the_prompt_and_the_model(env):
    put(env.ws / "models.md", models_md([cli_row(how="agy --model fake-model-1 (chỉ qua `call_council_cli.py`); x")]))
    proc = env.run()
    assert proc.returncode == 1 and "<prompt>" in proc.stdout
    put(env.ws / "models.md", models_md([cli_row(how="agy -p <prompt> --model other-id (chỉ qua `call_council_cli.py`); x")]))
    proc = env.run()
    assert proc.returncode == 1 and "không khớp" in proc.stdout


def test_member_name_is_a_slug_of_the_model_name():
    assert cc.slug("agy:gemini-3.8-flash-low") == "agy-gemini-3.8-flash-low"
    assert cc.slug("agy:Claude Sonnet_4.6 (Thinking)") == "agy-claude-sonnet-4.6-thinking"


# --- CLI failures --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("mode, needle", [
    ("error_status", "model overloaded"),
    ("exit_nonzero", "mã 3"),
    ("empty", "rỗng"),
    ("no_result", "result"),
    ("garbage", "không in sự kiện"),
])
def test_a_failing_cli_writes_no_vote(env, mode, needle):
    env.set_response(good_vote())
    proc = env.run(mode=mode)
    assert proc.returncode == 1 and needle in proc.stdout, proc.stdout
    assert not env.vote_file().exists()
    assert "LỖI" in (env.ws / "checks" / f"council-cli-{TODAY}.md").read_text(encoding="utf-8")


def test_a_timeout_writes_no_vote(env):
    env.set_response(good_vote())
    proc = env.run("--timeout", "2", mode="hang")
    assert proc.returncode == 1 and "quá 2s" in proc.stdout and not env.vote_file().exists()


def test_a_missing_executable_is_an_error(env):
    env.set_response(good_vote())
    proc = env.run("--cli-prefix", "no-such-executable-xyz", prefix=False)
    assert proc.returncode == 1 and "không chạy được" in proc.stdout and not env.vote_file().exists()


def test_existing_vote_is_not_overwritten_without_the_flag(env):
    env.set_response(good_vote())
    assert env.run().returncode == 0
    first = env.vote_file().read_text(encoding="utf-8")
    env.set_response(good_vote(choice="B"))
    proc = env.run()
    assert proc.returncode == 1 and "--overwrite" in proc.stdout
    assert env.vote_file().read_text(encoding="utf-8") == first
    assert env.run("--overwrite").returncode == 0
    assert env.vote_file().read_text(encoding="utf-8") != first


# --- stdin first, argument as the fallback ------------------------------------------------------------------------------

def test_auto_falls_back_to_the_argument_when_the_cli_rejects_the_stdin_flags(env):
    env.set_response(good_vote())
    proc = env.run(mode="reject_stream")
    assert proc.returncode == 0, proc.stdout
    assert "cách gọi: argv" in proc.stdout
    kinds = [c["kind"] for c in env.calls()]
    assert kinds == ["stream", "argv", "argv"]  # the stdin flags are refused on the lock check, so lock check and vote both go by argument
    argv = env.real_calls()[0]["argv"]
    assert argv[0] == "-p" and argv[2:] == ["--model", "fake-model-1", "--agent", "council-member"] and "=== BRIEF ===" in argv[1]


def test_mode_stdin_does_not_fall_back(env):
    env.set_response(good_vote())
    proc = env.run("--mode", "stdin", mode="reject_stream")
    assert proc.returncode == 1 and [c["kind"] for c in env.calls()] == ["stream"]


def test_mode_argv_uses_the_row_command(env):
    env.set_response(good_vote())
    proc = env.run("--mode", "argv")
    assert proc.returncode == 0 and [c["kind"] for c in env.calls()] == ["argv", "argv"]
    assert "cách gọi: argv" in proc.stdout


def test_argument_failure_is_an_error(env):
    env.set_response(good_vote())
    proc = env.run("--mode", "argv", mode="argv_fail")
    assert proc.returncode == 1 and "mã 4" in proc.stdout and not env.vote_file().exists()


def test_an_argument_over_the_limit_is_an_error_not_a_cut(env, tmp_path):
    config = yaml.safe_load(cc.DEFAULT_CLI_CONFIG.read_text(encoding="utf-8"))
    config["clis"]["agy"]["argv_limit"] = {"windows": 900, "other": 900}
    path = tmp_path / "cli.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    env.set_response(good_vote())
    proc = env.run("--mode", "argv", "--cli-config", str(path))
    assert proc.returncode == 1 and "quá giới hạn dòng lệnh 900" in proc.stdout and "không cắt" in proc.stdout
    assert env.real_calls() == []
    proc = env.run("--cli-config", str(path), mode="reject_stream")  # auto: stdin is rejected, the fallback is too long
    assert proc.returncode == 1 and "quá giới hạn" in proc.stdout


def test_a_cli_without_a_stdin_recipe_uses_the_argument(env, tmp_path):
    config = yaml.safe_load(cc.DEFAULT_CLI_CONFIG.read_text(encoding="utf-8"))
    config["clis"] = {"agy": {"argv_limit": {"windows": 30000, "other": 120000}, "lock": config["clis"]["agy"]["lock"]}}
    path = tmp_path / "cli.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    env.set_response(good_vote())
    proc = env.run("--cli-config", str(path))
    assert proc.returncode == 0 and "cách gọi: argv" in proc.stdout
    assert env.run("--cli-config", str(path), "--mode", "stdin", "--overwrite").returncode == 1


# --- arguments ----------------------------------------------------------------------------------------------------------

def test_bad_arguments_exit_two(env):
    env.set_response(good_vote())
    assert env.run(perspective="nonsense").returncode == 2
    assert env.run(perspective="evolution").returncode == 2           # a 3-member council has no evolution
    assert env.run(round_="3").returncode == 2
    assert env.run(decision="D-009-none").returncode == 2
    assert env.run("--timeout", "0").returncode == 2
    missing = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(env.root / "nope"), "--decision", DEC, "--round", "1", "--perspective", "fit", "--model", MODEL],
                             capture_output=True, text=True, encoding="utf-8")
    assert missing.returncode == 2
    assert env.calls() == []


def test_an_invalid_brief_is_an_error(env):
    put(env.ws / "decisions" / DEC / "brief.md", "# không có frontmatter\n")
    proc = env.run()
    assert proc.returncode == 1 and "brief không hợp lệ" in proc.stdout and env.calls() == []


def test_a_five_member_council_accepts_evolution(env):
    put(env.ws / "decisions" / DEC / "brief.md", brief_text(size=5))
    env.set_response(good_vote("evolution"))
    assert env.run(perspective="evolution").returncode == 0
    assert "- perspective: evolution" in prompt_of(env)


def test_the_report_collects_every_call(env):
    env.set_response(good_vote())
    env.run()
    env.run(perspective="cost-ops", mode="error_status")
    report = (env.ws / "checks" / f"council-cli-{TODAY}.md").read_text(encoding="utf-8")
    assert report.count("## D-001-arch") == 2 and "Đã ghi: " in report and "LỖI" in report


# --- the perspective files and the data ------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", sorted(COUNCIL.glob("*.md")), ids=lambda p: p.stem)
def test_every_council_file_gives_a_self_contained_body(path):
    body = cc.council_body(path)
    assert body.startswith("# Thành viên hội đồng")
    assert "## Định dạng phiếu" in body and "## Không được làm" in body
    assert "Cách giao phiếu (Claude Code)" not in body and "tools:" not in body.split("\n")[0]
    assert "Orchestrator truyền" not in body


def test_a_council_file_without_the_cut_marker_is_refused(tmp_path):
    path = tmp_path / "fit.md"
    path.write_text("---\nname: x\n---\n\n# Thân\n", encoding="utf-8")
    with pytest.raises(cc.CallError, match="body-end"):
        cc.council_body(path)
    path.write_text("---\nname: x\n---\n\n# Thân\n<!-- body-end -->\n<!-- body-end -->\n", encoding="utf-8")
    with pytest.raises(cc.CallError, match="body-end"):
        cc.council_body(path)


def test_cli_data_is_valid_and_matches_what_detect_models_writes():
    clis = cc.load_cli_config(cc.DEFAULT_CLI_CONFIG)
    assert set(clis) == set(dm.EXTERNAL_CLIS)
    call = dm.EXTERNAL_CLIS["agy"]["call"].format(model="m")
    assert call.startswith("agy ") and "<prompt>" in call and "--model m" in call   # the row command call_council_cli.py parses


def test_cli_data_errors_are_refused(tmp_path):
    good = yaml.safe_load(cc.DEFAULT_CLI_CONFIG.read_text(encoding="utf-8"))
    for mutate in (lambda c: c.pop("clis"), lambda c: c["clis"]["agy"]["stdin"].pop("message"),
                   lambda c: c["clis"]["agy"]["stdin"]["result"].pop("ok"), lambda c: c["clis"]["agy"].pop("argv_limit")):
        data = json.loads(json.dumps(good))
        mutate(data)
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError):
            cc.load_cli_config(path)


def test_the_documents_describe_the_stdin_way():
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    row = next(line for line in plan.splitlines() if line.startswith("| `call_council_cli.py"))
    assert "stdin" in row and "data/cli.yaml" in row


# --- the tool lock ----------------------------------------------------------------------------------------------------

def test_the_cli_runs_as_a_locked_agent_that_has_no_tools(env):
    env.set_response(good_vote())
    assert env.run().returncode == 0
    canary, real = env.calls()
    assert canary["canary"] and not real["canary"]
    for call in (canary, real):
        assert call["agent"] == "council-member" and call["argv"][-2:] == ["--agent", "council-member"]
    text = real["agent_text"]
    front = yaml.safe_load(text.split("---")[1])
    assert front["name"] == "council-member" and front["mainAgent"] is True and front["subagent"] is False
    assert front["excludeDefaultComponents"] is True and front["inheritMcp"] is False and front["tools"] == []
    assert real["agent_text"] == canary["agent_text"]
    assert "Bạn không có công cụ nào" in text


def test_the_lock_is_checked_with_a_secret_code_before_the_brief_is_sent(env):
    env.set_response(good_vote())
    assert env.run().returncode == 0
    canary, real = env.calls()
    asked = canary["messages"][0]["message"]["content"]
    assert "Mã xác nhận cấu hình" in asked and "=== BRIEF ===" not in asked and "Lời giao" not in asked
    nonce = [part for part in canary["agent_text"].split() if part.startswith("NONCE-")][0]
    assert nonce in canary["agent_text"] and nonce not in asked and nonce not in prompt_of(env)
    env.run("--overwrite")
    assert [c["agent_text"] for c in env.calls()[2:]][0] != canary["agent_text"]  # a new code for every call


def test_a_cli_that_ignores_the_agent_flag_never_gets_the_brief(env):
    env.set_response(good_vote())
    proc = env.run(mode="ghost")  # the fake answers UNKNOWN to the check, like agy does for a name it does not know
    assert proc.returncode == 1 and "không nạp agent khóa công cụ" in proc.stdout
    assert [c["canary"] for c in env.calls()] == [True] and not env.vote_file().exists()
    assert "=== BRIEF ===" not in json.dumps(env.calls())


def test_a_tool_step_in_the_answer_voids_the_vote(env):
    env.set_response(good_vote())
    proc = env.run(mode="tool_step")
    assert proc.returncode == 1 and "gọi công cụ" in proc.stdout and "tool" in proc.stdout
    assert not env.vote_file().exists()


def test_a_tool_step_during_the_lock_check_stops_the_call(env):
    env.set_response(good_vote())
    proc = env.run(mode="canary_tool_step")
    assert proc.returncode == 1 and "bước kiểm khóa" in proc.stdout and not env.real_calls()


def test_a_cli_with_no_lock_recipe_is_refused_and_gets_nothing(env, tmp_path):
    config = yaml.safe_load(cc.DEFAULT_CLI_CONFIG.read_text(encoding="utf-8"))
    del config["clis"]["agy"]["lock"]
    path = tmp_path / "cli.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    env.set_response(good_vote())
    proc = env.run("--cli-config", str(path))
    assert proc.returncode == 1 and "chưa cô lập được công cụ" in proc.stdout
    assert env.calls() == [] and not env.vote_file().exists()


def test_the_report_says_the_lock_held(env):
    env.set_response(good_vote())
    assert env.run().returncode == 0
    report = (env.ws / "checks" / f"council-cli-{TODAY}.md").read_text(encoding="utf-8")
    assert "khóa công cụ: agent `council-member`" in report and "bước công cụ trong câu trả lời: 0" in report


def test_the_lock_recipe_is_validated(tmp_path):
    good = yaml.safe_load(cc.DEFAULT_CLI_CONFIG.read_text(encoding="utf-8"))
    mutations = [
        lambda c: c["clis"]["agy"]["lock"].pop("canary_prompt"),
        lambda c: c["clis"]["agy"]["lock"].update(text="no secret here"),                       # the text must carry {nonce}
        lambda c: c["clis"]["agy"]["lock"].update(flags=["--agent", "fixed"]),                  # the flags must carry {agent}
        lambda c: c["clis"]["agy"]["lock"].update(forbidden_steps=[]),
        lambda c: c["clis"]["agy"]["lock"]["steps"].pop("type_key"),
    ]
    for mutate in mutations:
        data = json.loads(json.dumps(good))
        mutate(data)
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError, match="lock"):
            cc.load_cli_config(path)


def test_the_default_recipe_locks_agy_the_way_the_trials_found():
    lock = cc.load_cli_config(cc.DEFAULT_CLI_CONFIG)["agy"]["lock"]
    front = yaml.safe_load(lock["text"].split("---")[1].replace("{agent}", "x"))
    assert front["excludeDefaultComponents"] is True and front["inheritMcp"] is False and front["tools"] == [] and front["mainAgent"] is True
    assert lock["flags"] == ["--agent", "{agent}"] and lock["forbidden_steps"] == ["tool"]
    assert "UNKNOWN" in lock["canary_prompt"] and "{nonce}" in lock["text"]


def test_the_docs_name_the_lock():
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    row = next(line for line in plan.splitlines() if line.startswith("| `call_council_cli.py"))
    assert "khóa công cụ" in row and "mã xác nhận" in row
    orchestrator = (CORE / "claude" / "agents" / "orchestrator.md").read_text(encoding="utf-8")
    assert "khóa công cụ" in orchestrator and "không gọi `agy` trực tiếp" in orchestrator
