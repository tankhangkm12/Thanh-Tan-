"""Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts"""

import copy
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import tally_votes as tv  # noqa: E402

SCRIPT = Path(__file__).parent / "tally_votes.py"
CORE = Path(__file__).parent.parent
TODAY = "2026-10-12"
DEC = "D-001-arch"
THREE = ["fit", "cost-ops", "numbers-nfr"]
FIVE = THREE + ["evolution", "risk-data"]
WEIGHTS = (("TC-01", 5), ("TC-02", 3), ("TC-03", 2))


# --- builders --------------------------------------------------------------------------------------------------------------

def brief_text(size=3, weights=WEIGHTS, exclusion=("TC-05",), options=("A", "B"), table_weights=None, table_options=None, gate="G3", table=True) -> str:
    criteria = [f"  - {{id: {tc}, kind: weighted, weight: {w}}}" for tc, w in weights] + [f"  - {{id: {tc}, kind: exclusion}}" for tc in exclusion]
    rows = [f"| {tc} | tiêu chí | NFR-01 | {(table_weights or dict(weights))[tc]} | không |" for tc, _ in weights] + [f"| {tc} | loại trừ | C-01 | — | có |" for tc in exclusion]
    text = [
        "---", "decision: D-001", f"gate: {gate}", f"council_size: {size}", "criteria:", *criteria,
        f"options: [{', '.join(options)}]", "---", "", "# Brief D-001: Chọn kiểu kiến trúc", "",
        "## Câu hỏi", "", "Chọn kiểu kiến trúc cho hệ thống đặt hàng?", "",
        "## Bối cảnh trích", "", "- **Số liệu capacity liên quan:** 120 USD mỗi tháng; 99 ms; 40 USD; 0, 1, 2, 3, 4; 10, 11, 12, 13, 14; PostgreSQL 16.4.1; 1.000 người dùng", "",
    ]
    if table:
        text += ["## Tiêu chí chấm (TC đã duyệt ở G2)", "", "| TC | Tiêu chí | Truy về | Trọng số | Loại trừ? |", "| --- | --- | --- | --- | --- |", *rows, ""]
    text += ["## Phương án", ""]
    for option in table_options or options:
        text += [f"### Phương án {option}: tên {option}", "", "- **Mô tả:** x", ""]
    return "\n".join(text) + "\n"


def default_vote(perspective="fit", member=None, model=None, choice="A", round_=1, options=("A", "B"), weights=WEIGHTS, exclusion=("TC-05",)) -> dict:
    scores = {"A": {"TC-01": 5, "TC-02": 4, "TC-03": 3}, "B": {"TC-01": 2, "TC-02": 3, "TC-03": 4}}
    return {
        "decision": "D-001", "round": round_, "perspective": perspective, "member": member or f"m-{perspective}", "model": model or f"Model {perspective}",
        "via": "subagent", "choice": choice,
        "scores": {o: {tc: scores.get(o, scores["B"]).get(tc, 3) for tc, _ in weights} for o in options},
        "exclusions": {o: {tc: "pass" for tc in exclusion} for o in options} if exclusion else {},
        "overreach": {o: {"points": 0, "reason": ""} for o in options},
        "tie_reason": "", "cites": ["TC-01"],
    }


def vote_text(data: dict, reasons="1. A đáp ứng TC-01 tốt hơn — TC-01", risks="không có", overreach_body="không có") -> str:
    front = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n\n# Phiếu D-001\n\n## Lý do\n\n{reasons}\n\n## Làm quá tay\n\n- {overreach_body}\n\n## Rủi ro mới\n\n- {risks}\n"


def vote_name(data: dict) -> str:
    return f"r{data['round']}-{data['perspective']}-{data['member']}.md"


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def workspace(tmp_path: Path, brief: str | None = None, name: str = DEC) -> Path:
    ws = tmp_path / ".agent-workspace"
    (ws / "checks").mkdir(parents=True, exist_ok=True)
    put(ws / "decisions" / name / "brief.md", brief if brief is not None else brief_text())
    return ws


def cast(ws: Path, votes: list[dict], name: str = DEC, names: list[str] | None = None, **kwargs) -> None:
    for index, data in enumerate(votes):
        put(ws / "decisions" / name / "votes" / (names[index] if names else vote_name(data)), vote_text(data, **kwargs))


def unanimous(choice="A", round_=1, perspectives=THREE) -> list[dict]:
    return [default_vote(p, choice=choice, round_=round_) for p in perspectives]


def run(ws: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(ws), "--date", TODAY, *extra], capture_output=True, text=True, encoding="utf-8")


def codes(proc: subprocess.CompletedProcess) -> list[str]:
    return re.findall(r"\[([a-z0-9-]+)\]", proc.stdout)


def decision_dir(ws: Path) -> Path:
    return ws / "decisions" / DEC


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- happy path and formula ------------------------------------------------------------------------------------------------

def test_unanimous_round_one_proposes_and_writes_files(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    d = decision_dir(ws)
    assert "đề xuất phương án A" in read(d / "decision.md")
    assert "| A | 3/3 | — |" in read(d / "decision.md")
    assert "Quá bán cần:** 2/3" in read(d / "decision.md")
    assert (d / "tally.md").is_file()
    assert not (d / "votes" / "r1-summary.md").exists()
    assert (ws / "checks" / f"tally-{TODAY}.md").is_file()


def test_total_uses_weights_and_rounds_only_for_display(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    run(ws)
    table = read(decision_dir(ws) / "tally.md")
    # A: (5*5+4*3+3*2)/(5*10)*100 = 86 ; B: (2*5+3*3+4*2)/50*100 = 54
    assert "| fit | 86.0 | 54.0 |" in table


def test_overreach_points_are_subtracted(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    for v in votes:
        v["overreach"]["A"] = {"points": 10, "reason": "thêm một tầng cache mà NFR-01 không đòi"}
    cast(ws, votes)
    assert run(ws).returncode == 0
    assert "| fit | 76.0 | 54.0 |" in read(decision_dir(ws) / "tally.md")


def test_overreach_can_flip_the_best_option(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    for v in votes:
        v["overreach"]["A"] = {"points": 20, "reason": "vượt xa nhu cầu theo TC-01"}  # 86 - 20 = 66 > 54, still A
    cast(ws, votes)
    assert run(ws).returncode == 0
    votes = unanimous("A")
    for v in votes:
        v["scores"]["A"] = {"TC-01": 3, "TC-02": 3, "TC-03": 3}  # 60 - 20 = 40 < 54
        v["overreach"]["A"] = {"points": 20, "reason": "vượt xa nhu cầu theo TC-01"}
    cast(ws, votes)
    proc = run(ws)
    assert proc.returncode == 1 and "vote-choice-not-top" in codes(proc)


def test_exact_fractions_the_formula_in_code():
    cfg, _ = tv.load_config(tv.DEFAULT_CONFIG)
    assert cfg.max_overreach == 20 and cfg.tie == Fraction(1, 100)
    assert tv.fmt(Fraction(8605, 100)) == "86.0"


# --- vote rejected ---------------------------------------------------------------------------------------------------------

def mutate(tmp_path, change, **cast_kwargs):
    ws = workspace(tmp_path)
    votes = unanimous()
    names = [vote_name(v) for v in votes]
    change(votes[0])
    cast(ws, votes, names=names, **cast_kwargs)
    return ws, run(ws)


def test_choice_that_is_not_the_top_option_is_rejected(tmp_path):
    ws, proc = mutate(tmp_path, lambda v: v.update(choice="B"))
    assert proc.returncode == 1 and "vote-choice-not-top" in codes(proc)
    assert not (decision_dir(ws) / "tally.md").exists() and not (decision_dir(ws) / "decision.md").exists()


def test_overreach_above_the_cap_rejects_the_vote(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["overreach"].update(B={"points": 21, "reason": "vượt xa theo TC-01"}))
    assert proc.returncode == 1 and "vote-overreach-over-limit" in codes(proc)


def test_overreach_at_the_cap_is_accepted(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["overreach"].update(B={"points": 20, "reason": "vượt xa theo TC-01"}))
    assert proc.returncode == 0, proc.stdout


def test_overreach_points_need_a_reason(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["overreach"].update(B={"points": 5, "reason": " "}))
    assert proc.returncode == 1 and "vote-overreach-reason" in codes(proc)


@pytest.mark.parametrize("value", [-1, 1.5, "3", True])
def test_overreach_points_must_be_a_non_negative_integer(tmp_path, value):
    _, proc = mutate(tmp_path, lambda v: v["overreach"].update(B={"points": value, "reason": "x"}))
    assert proc.returncode == 1 and "vote-overreach" in codes(proc)


def test_missing_score_cell(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["scores"]["A"].pop("TC-02"))
    assert proc.returncode == 1 and "vote-scores-missing" in codes(proc)


def test_extra_score_cell(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["scores"]["A"].update({"TC-09": 3}))
    assert proc.returncode == 1 and "vote-scores-extra" in codes(proc)


def test_exclusion_criterion_in_scores_is_extra(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["scores"]["A"].update({"TC-05": 3}))
    assert proc.returncode == 1 and "vote-scores-extra" in codes(proc)


def test_missing_option_in_scores(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["scores"].pop("B"))
    assert proc.returncode == 1 and "vote-scores" in codes(proc)


@pytest.mark.parametrize("value", [6, -1, 2.5, "4", True])
def test_score_must_be_an_integer_in_range(tmp_path, value):
    _, proc = mutate(tmp_path, lambda v: v["scores"]["A"].update({"TC-01": value}))
    assert proc.returncode == 1 and "vote-score-range" in codes(proc)


def test_missing_exclusion_cell(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["exclusions"]["A"].pop("TC-05"))
    assert proc.returncode == 1 and "vote-exclusions-missing" in codes(proc)


def test_exclusion_value_must_be_pass_or_fail(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v["exclusions"]["A"].update({"TC-05": "ok"}))
    assert proc.returncode == 1 and "vote-exclusions-value" in codes(proc)


@pytest.mark.parametrize("key", list(default_vote()))
def test_every_key_is_required(tmp_path, key):
    _, proc = mutate(tmp_path, lambda v: v.pop(key))
    assert proc.returncode == 1 and "vote-key-missing" in codes(proc)


def test_unknown_key(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v.update(total=86))
    assert proc.returncode == 1 and "vote-key-unknown" in codes(proc)


def test_choice_must_be_an_option_or_none(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v.update(choice="C"))
    assert proc.returncode == 1 and "vote-choice" in codes(proc)


def test_member_and_perspective_and_round_must_match_the_file_name(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    path = decision_dir(ws) / "votes" / vote_name(votes[0])
    for field, value, code in (("member", "other", "vote-member"), ("perspective", "cost-ops", "vote-perspective"), ("round", 2, "vote-round"), ("decision", "D-002", "vote-decision")):
        broken = copy.deepcopy(votes[0])
        broken[field] = value
        put(path, vote_text(broken))
        proc = run(ws)
        assert proc.returncode == 1 and code in codes(proc), field
    put(path, vote_text(votes[0]))
    assert run(ws).returncode == 0


def test_via_must_be_known(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v.update(via="telepathy"))
    assert proc.returncode == 1 and "vote-via" in codes(proc)


def test_duplicate_yaml_key_is_rejected(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    path = decision_dir(ws) / "votes" / vote_name(votes[0])
    put(path, read(path).replace("choice: A\n", "choice: A\nchoice: B\n", 1))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-frontmatter" in codes(proc) and "lặp" in proc.stdout


def test_vote_wrapped_in_a_code_fence_is_rejected(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    path = decision_dir(ws) / "votes" / vote_name(votes[0])
    put(path, "```markdown\n" + read(path) + "```\n")
    proc = run(ws)
    assert proc.returncode == 1 and "vote-frontmatter" in codes(proc)


def test_reasons_are_required_and_must_cite(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    path = decision_dir(ws) / "votes" / vote_name(votes[0])
    put(path, vote_text(votes[0], reasons="Đây là chuẩn ngành và đang phổ biến."))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-reasons" in codes(proc)
    put(path, vote_text(votes[0], reasons="1. Đây là chuẩn ngành và đang phổ biến."))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-reason-uncited" in codes(proc)
    put(path, vote_text(votes[0], reasons="1. Chi phí 120 USD mỗi tháng thấp hơn."))
    assert run(ws).returncode == 0


def test_cites_must_list_every_id_the_reasons_cite(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    path = decision_dir(ws) / "votes" / vote_name(votes[0])
    put(path, vote_text(votes[0], reasons="1. Đáp ứng NFR-07 và R-02."))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-cites-incomplete" in codes(proc) and "NFR-07" in proc.stdout


def test_cites_must_be_ids(tmp_path):
    _, proc = mutate(tmp_path, lambda v: v.update(cites=["chuẩn ngành"]))
    assert proc.returncode == 1 and "vote-cites" in codes(proc)


# --- ties ------------------------------------------------------------------------------------------------------------------

def tie_workspace(tmp_path, big, diff_scores, tie_reason="", choice="A"):
    weights = (("TC-01", big), ("TC-02", 1))
    ws = workspace(tmp_path, brief_text(weights=weights, exclusion=()))
    votes = []
    for p in THREE:
        v = default_vote(p, choice=choice, weights=weights, exclusion=())
        v["scores"] = {"A": {"TC-01": 3, "TC-02": diff_scores[0]}, "B": {"TC-01": 3, "TC-02": diff_scores[1]}}
        v["tie_reason"] = tie_reason
        votes.append(v)
    cast(ws, votes)
    return ws


def test_a_gap_under_one_hundredth_is_a_tie_and_needs_a_reason(tmp_path):
    # 100 / (5 * 3001) = 0.0067 < 0.01
    ws = tie_workspace(tmp_path, 3000, (4, 3))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-tie-reason" in codes(proc)
    ws = tie_workspace(tmp_path, 3000, (4, 3), tie_reason="TC-02 quan trọng hơn theo NFR-01")
    assert run(ws).returncode == 0


def test_in_a_tie_either_option_may_be_chosen(tmp_path):
    ws = tie_workspace(tmp_path, 3000, (4, 3), tie_reason="theo TC-02", choice="B")
    assert run(ws).returncode == 0


def test_a_gap_of_exactly_one_hundredth_is_not_a_tie(tmp_path):
    # 100 / (5 * 2000) = 0.01 exactly: not below 0.01
    ws = tie_workspace(tmp_path, 1999, (4, 3), tie_reason="")
    assert run(ws).returncode == 0
    ws = tie_workspace(tmp_path, 1999, (4, 3), choice="B")
    proc = run(ws)
    assert proc.returncode == 1 and "vote-choice-not-top" in codes(proc)


def test_equal_totals_are_a_tie(tmp_path):
    ws = tie_workspace(tmp_path, 5, (3, 3))
    assert "vote-tie-reason" in codes(run(ws))


def test_tie_reason_without_a_tie_is_only_a_warning(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    votes[0]["tie_reason"] = "không cần"
    cast(ws, votes)
    proc = run(ws)
    assert proc.returncode == 0
    assert "vote-tie-reason-unused" in read(ws / "checks" / f"tally-{TODAY}.md")


# --- exclusion and none ----------------------------------------------------------------------------------------------------

def test_option_failing_an_exclusion_cannot_be_chosen(tmp_path):
    def change(v):
        v["exclusions"]["A"]["TC-05"] = "fail"  # A would win on score, but is out; B is the top of what is left
    _, proc = mutate(tmp_path, change)
    assert proc.returncode == 1 and "vote-choice-excluded" in codes(proc)


def test_option_failing_an_exclusion_is_out_of_the_vote(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous(choice="B")
    for v in votes:
        v["exclusions"]["A"]["TC-05"] = "fail"
    cast(ws, votes)
    assert run(ws).returncode == 0
    assert "loại (TC-05)" in read(decision_dir(ws) / "tally.md")
    assert "đề xuất phương án B" in read(decision_dir(ws) / "decision.md")


def test_none_is_valid_when_every_option_fails_an_exclusion(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous(choice="none")
    for v in votes:
        v["cites"] = []
        for o in ("A", "B"):
            v["exclusions"][o]["TC-05"] = "fail"
    cast(ws, votes, reasons="1. Cả hai phương án vi phạm loại trừ, mức 3 điểm.")
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    assert "không phương án nào phù hợp" in read(decision_dir(ws) / "decision.md")


def test_choice_must_be_none_when_every_option_fails_an_exclusion(tmp_path):
    def change(v):
        for o in ("A", "B"):
            v["exclusions"][o]["TC-05"] = "fail"
    _, proc = mutate(tmp_path, change)
    assert proc.returncode == 1 and "vote-choice" in codes(proc)


def test_none_with_cites_and_reasons_is_valid(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous(choice="none")
    for v in votes:
        v["cites"] = ["TC-01", "NFR-01"]
    cast(ws, votes, reasons="1. Không phương án nào đạt NFR-01 vì TC-01 thấp.")
    assert run(ws).returncode == 0


def test_none_without_cites_is_rejected_when_an_option_stands(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous(choice="none")
    for v in votes:
        v["cites"] = []
    cast(ws, votes, reasons="1. Chi phí 120 USD mỗi tháng là quá cao.")
    proc = run(ws)
    assert proc.returncode == 1 and "vote-none" in codes(proc)


# --- the votes of the council ----------------------------------------------------------------------------------------------

def test_missing_vote_blocks(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous()[:2])
    proc = run(ws)
    assert proc.returncode == 1 and "vote-missing" in codes(proc) and "numbers-nfr" in proc.stdout
    assert not (decision_dir(ws) / "tally.md").exists()


def test_no_votes_at_all_blocks(tmp_path):
    ws = workspace(tmp_path)
    proc = run(ws)
    assert proc.returncode == 1 and codes(proc).count("vote-missing") == 3


def test_duplicate_vote_for_a_perspective(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    cast(ws, votes)
    twin = copy.deepcopy(votes[0])
    twin["member"] = "m-other"
    cast(ws, [twin])
    proc = run(ws)
    assert proc.returncode == 1 and "vote-duplicate" in codes(proc)


def test_vote_file_with_a_wrong_name(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    put(decision_dir(ws) / "votes" / "r1-nonsense-x.md", "x")
    put(decision_dir(ws) / "votes" / "vote.md", "x")
    proc = run(ws)
    assert proc.returncode == 1 and codes(proc).count("vote-file-name") == 2


def test_three_member_council_does_not_accept_a_fourth_perspective(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous(perspectives=THREE + ["evolution"]))
    proc = run(ws)
    assert proc.returncode == 1 and "vote-perspective-unexpected" in codes(proc)


def test_five_member_council_needs_all_five_and_three_is_not_a_majority_of_two(tmp_path):
    ws = workspace(tmp_path, brief_text(size=5))
    cast(ws, unanimous(perspectives=THREE))
    proc = run(ws)
    assert proc.returncode == 1 and codes(proc).count("vote-missing") == 2


def test_two_of_three_is_a_majority(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    votes[2]["choice"] = "B"
    votes[2]["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
    cast(ws, votes)
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    assert "đề xuất phương án A" in read(decision_dir(ws) / "decision.md")


def test_two_of_five_is_not_a_majority_and_three_is(tmp_path):
    assert not tv.majority(2, 5) and tv.majority(3, 5) and not tv.majority(1, 3) and tv.majority(2, 3)
    assert not tv.majority(2, 4) and tv.majority(3, 4)  # exactly half is not "hơn 50%"
    assert tv.needed(3) == "2/3" and tv.needed(5) == "3/5"


def test_no_majority_in_round_one_waits_for_round_two_and_writes_the_anonymous_summary(tmp_path):
    ws = workspace(tmp_path)
    a, b, n = default_vote("fit", choice="A"), default_vote("cost-ops", choice="B"), default_vote("numbers-nfr", choice="none")
    b["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
    reasons = {"fit": "1. Lý do độc nhất của fit về TC-01.", "cost-ops": "1. Lý do độc nhất của cost về TC-01.", "numbers-nfr": "1. Lý do độc nhất của numbers về TC-01."}
    for data in (a, b, n):
        put(decision_dir(ws) / "votes" / vote_name(data), vote_text(data, reasons=reasons[data["perspective"]]))
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    summary = read(decision_dir(ws) / "votes" / "r1-summary.md")
    for text in reasons.values():
        assert text.removeprefix("1. ") in summary or text in summary
    for secret in ("m-fit", "m-cost-ops", "Model fit", "Model cost-ops", "numbers-nfr", "perspective", "member", "model:"):
        assert secret not in summary, secret
    decision = read(decision_dir(ws) / "decision.md")
    assert "chờ vòng 2" in decision and "đề xuất phương án" not in decision


def test_summary_is_verbatim_not_summarised(tmp_path):
    ws = workspace(tmp_path)
    long_reason = "1. Dòng một có NFR-01.\n   Dòng hai nối tiếp với 99 ms.\n2. Ý thứ hai trích TC-01 và R-02.\n\n   Đoạn mới."
    a = default_vote("fit", choice="A")
    a["cites"] = ["NFR-01", "TC-01", "R-02"]
    b = default_vote("cost-ops", choice="B")
    b["cites"] = list(a["cites"])
    b["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
    n = default_vote("numbers-nfr", choice="none")
    n["cites"] = list(a["cites"])
    for data in (a, b, n):
        put(decision_dir(ws) / "votes" / vote_name(data), vote_text(data, reasons=long_reason))
    assert run(ws).returncode == 0
    assert long_reason in read(decision_dir(ws) / "votes" / "r1-summary.md")


def test_summary_is_the_same_on_every_run_and_is_a_permutation(tmp_path):
    ws = workspace(tmp_path, brief_text(size=5))
    perspectives = FIVE
    votes = []
    for index, p in enumerate(perspectives):
        v = default_vote(p, choice="A" if index % 2 == 0 else "B")
        if index % 2:
            v["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
        votes.append(v)
    votes[4]["choice"] = "none"
    cast_votes = {p: f"1. Ý kiến số {i} về TC-01 với 1{i} ms." for i, p in enumerate(perspectives)}
    for v in votes:
        put(decision_dir(ws) / "votes" / vote_name(v), vote_text(v, reasons=cast_votes[v["perspective"]]))
    run(ws)
    first = read(decision_dir(ws) / "votes" / "r1-summary.md")
    run(ws)
    assert read(decision_dir(ws) / "votes" / "r1-summary.md") == first
    assert sorted(re.findall(r"Ý kiến số (\d)", first)) == ["0", "1", "2", "3", "4"]
    assert len(re.findall(r"^## Ý kiến \d$", first, re.MULTILINE)) == 5


def test_summary_order_is_shuffled_not_the_perspective_order():
    orders = set()
    for salt in range(6):
        votes = [tv.Vote(file="x", round=1, perspective=p, member="m", model="m", via="cli", choice="A", totals={}, failed={}, overreach={}, tie_reason="", reasons=f"Ý {salt}-{i}", risks=[]) for i, p in enumerate(FIVE)]
        text = tv.summary_text("D-001", votes)
        orders.add(tuple(re.findall(r"Ý \d-(\d)", text)))
    assert any(order != ("0", "1", "2", "3", "4") for order in orders)
    assert all(sorted(order) == ["0", "1", "2", "3", "4"] for order in orders)


def round_two(ws, choices):
    votes = []
    for p, c in zip(THREE, choices):
        v = default_vote(p, choice=c, round_=2)
        if c == "B":
            v["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
        if c == "none":
            v["cites"] = ["TC-01"]
        votes.append(v)
    cast(ws, votes, reasons="1. Sau khi đọc tóm tắt, TC-01 quyết định.")


def round_one_split(ws):
    a, b, n = default_vote("fit", choice="A"), default_vote("cost-ops", choice="B"), default_vote("numbers-nfr", choice="none")
    b["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
    cast(ws, [a, b, n], reasons="1. Ý kiến về TC-01.")


def test_round_two_majority_proposes(tmp_path):
    ws = workspace(tmp_path)
    round_one_split(ws)
    round_two(ws, ["B", "B", "A"])
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    text = read(decision_dir(ws) / "decision.md")
    assert "đề xuất phương án B" in text and "**Số vòng:** 2" in text
    assert re.search(r"\| B \| 1/3 \| 2/3 \|", text)


def test_round_two_without_majority_shows_the_two_leaders(tmp_path):
    ws = workspace(tmp_path)
    round_one_split(ws)
    round_two(ws, ["A", "B", "none"])
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    text = read(decision_dir(ws) / "decision.md")
    match = re.search(r"chưa đạt đồng thuận, hai phương án dẫn đầu: (\w) và (\w)", text)
    assert match and {match.group(1), match.group(2)} == {"A", "B"}


def test_round_two_leaders_break_a_vote_tie_by_mean_total(tmp_path):
    cfg, _ = tv.load_config(tv.DEFAULT_CONFIG)
    def v(choice, a, b):
        return tv.Vote("f", 2, "fit", "m", "m", "cli", choice, {"A": Fraction(a), "B": Fraction(b), "C": Fraction(50)}, {}, {}, "", "", [])
    votes = [v("A", 40, 60), v("B", 40, 60), v("C", 40, 60)]
    assert tv.leaders(votes, ["A", "B", "C"]) == ["B", "C"]  # one vote each: highest mean total first, then ID


def test_round_two_none_majority_means_redo(tmp_path):
    ws = workspace(tmp_path)
    round_one_split(ws)
    round_two(ws, ["none", "none", "A"])
    assert run(ws).returncode == 0
    assert "Designer làm lại brief" in read(decision_dir(ws) / "decision.md")


def test_round_one_none_majority_ends_without_round_two(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous(choice="none")
    cast(ws, votes, reasons="1. Không phương án nào đạt TC-01.")
    proc = run(ws)
    assert proc.returncode == 0, proc.stdout
    assert "Designer làm lại brief" in read(decision_dir(ws) / "decision.md")
    assert not (decision_dir(ws) / "votes" / "r1-summary.md").exists()


def test_round_two_votes_after_a_round_one_majority_are_an_error(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    round_two(ws, ["A", "A", "A"])
    proc = run(ws)
    assert proc.returncode == 1 and "vote-round2-unneeded" in codes(proc)


def test_incomplete_round_two_is_an_error(tmp_path):
    ws = workspace(tmp_path)
    round_one_split(ws)
    round_two(ws, ["A", "A", "A"])
    (decision_dir(ws) / "votes" / "r2-fit-m-fit.md").unlink()
    proc = run(ws)
    assert proc.returncode == 1 and "vote-missing" in codes(proc) and "vòng 2" in proc.stdout


def test_summary_survives_when_round_two_is_cast(tmp_path):
    ws = workspace(tmp_path)
    round_one_split(ws)
    run(ws)
    before = read(decision_dir(ws) / "votes" / "r1-summary.md")
    round_two(ws, ["B", "B", "B"])
    assert run(ws).returncode == 0
    assert read(decision_dir(ws) / "votes" / "r1-summary.md") == before


# --- decision.md -----------------------------------------------------------------------------------------------------------

def test_decision_is_created_from_the_template(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    run(ws)
    text = read(decision_dir(ws) / "decision.md")
    assert text.startswith("# Quyết định D-001: Chọn kiểu kiến trúc cho hệ thống đặt hàng?")
    assert "- **Gate:** G3" in text
    assert "BEGIN:user" in text and "- **Trạng thái:** chờ người dùng" in text
    assert "<" not in text.split("BEGIN:user")[1].split("END:user")[0].replace("<!--", "").replace("-->", "")


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_only_the_council_block_changes(tmp_path, newline):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    before = (
        "# Quyết định D-001: x\n\nGhi chú tay của người dùng.\n\n<!-- BEGIN:council (tally_votes.py sinh, không sửa tay) -->\nCŨ\n<!-- END:council -->\n\n"
        "<!-- BEGIN:user (Orchestrator) -->\n- **Trạng thái:** đã quyết\n- **Người dùng nói (nguyên văn):** \"D-001: chọn A\"\n<!-- END:user -->\nĐuôi.\n"
    ).replace("\n", newline)
    path = put(decision_dir(ws) / "decision.md", before)
    assert run(ws).returncode == 0
    after = path.read_bytes().decode("utf-8")
    start = before.index("<!-- BEGIN:council")
    stop = before.index("<!-- END:council -->") + len("<!-- END:council -->")
    assert after[:start] == before[:start]
    assert after.endswith(before[stop:])
    assert "CŨ" not in after and "đề xuất phương án A" in after
    if newline == "\r\n":
        assert "\n" not in after.replace("\r\n", "")


def test_decision_without_markers_is_left_alone(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    path = put(decision_dir(ws) / "decision.md", "# Quyết định\n\nKhông có dấu.\n")
    proc = run(ws)
    assert proc.returncode == 1 and "decision-markers" in codes(proc)
    assert read(path) == "# Quyết định\n\nKhông có dấu.\n"


def test_decision_with_two_begin_markers_is_left_alone(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    text = "<!-- BEGIN:council -->\na\n<!-- BEGIN:council -->\n<!-- END:council -->\n"
    path = put(decision_dir(ws) / "decision.md", text)
    proc = run(ws)
    assert proc.returncode == 1 and "decision-markers" in codes(proc) and read(path) == text


def test_minority_is_shown_verbatim_with_perspective_model_and_scores(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    votes[2]["choice"] = "B"
    votes[2]["scores"] = {"A": {"TC-01": 1, "TC-02": 1, "TC-03": 1}, "B": {"TC-01": 5, "TC-02": 5, "TC-03": 5}}
    votes[2]["cites"] = ["TC-01"]
    cast(ws, votes[:2])
    put(decision_dir(ws) / "votes" / vote_name(votes[2]), vote_text(votes[2], reasons="1. B rẻ hơn 40 USD mỗi tháng — TC-01"))
    assert run(ws).returncode == 0
    text = read(decision_dir(ws) / "decision.md")
    minority = text.split("### Ý kiến thiểu số")[1].split("### Rủi ro")[0]
    assert "numbers-nfr" in minority and "Model numbers-nfr" in minority and "chọn B" in minority
    assert "> 1. B rẻ hơn 40 USD mỗi tháng — TC-01" in minority
    assert "A 20.0" in minority and "B 100.0" in minority


def test_no_minority_when_unanimous(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    run(ws)
    assert "- không có" in read(decision_dir(ws) / "decision.md").split("### Ý kiến thiểu số")[1].split("###")[0]


def test_new_risks_are_collected_without_duplicates(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    for v in votes[:2]:
        put(decision_dir(ws) / "votes" / vote_name(v), vote_text(v, risks="Khóa vendor, khả năng 3, tác động 4"))
    put(decision_dir(ws) / "votes" / vote_name(votes[2]), vote_text(votes[2], risks="Thiếu người vận hành"))
    run(ws)
    block = read(decision_dir(ws) / "decision.md").split("### Rủi ro mới sinh ra")[1]
    assert block.count("Khóa vendor") == 1 and "fit, cost-ops" in block and "Thiếu người vận hành" in block


def test_diversity_is_reported(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous())
    run(ws)
    assert "đủ: mỗi thành viên một model khác nhau" in read(decision_dir(ws) / "decision.md")
    votes = unanimous()
    votes[1]["model"] = votes[0]["model"]
    cast(ws, votes)
    run(ws)
    assert "giảm: dùng chung model Model fit cho fit, cost-ops" in read(decision_dir(ws) / "decision.md")


# --- brief -----------------------------------------------------------------------------------------------------------------

def test_brief_table_must_match_the_frontmatter(tmp_path):
    ws = workspace(tmp_path, brief_text(table_weights={"TC-01": 4, "TC-02": 3, "TC-03": 2}))
    cast(ws, unanimous())
    proc = run(ws)
    assert proc.returncode == 1 and "brief-table" in codes(proc)


@pytest.mark.parametrize("old, new", [
    ("| TC-03 |", "| TC-09 |"),                 # a TC of the table is not in the frontmatter (and one of the frontmatter is not in the table)
    ("| C-01 | — | có |", "| C-01 | — | không |"),   # exclusion in the frontmatter, not in the table
    ("| NFR-01 | 3 | không |", "| NFR-01 | 3 | có |"),  # weighted in the frontmatter, exclusion in the table
])
def test_brief_table_rows_must_match_the_frontmatter(tmp_path, old, new):
    text = brief_text()
    assert old in text
    ws = workspace(tmp_path, text.replace(old, new, 1))
    cast(ws, unanimous())
    proc = run(ws)
    assert proc.returncode == 1 and "brief-table" in codes(proc)


def test_brief_without_the_criteria_table(tmp_path):
    ws = workspace(tmp_path, brief_text(table=False))
    proc = run(ws)
    assert proc.returncode == 1 and "brief-table" in codes(proc)


def test_brief_option_headings_must_match(tmp_path):
    ws = workspace(tmp_path, brief_text(table_options=("A", "C")))
    proc = run(ws)
    assert proc.returncode == 1 and "brief-options-body" in codes(proc)


@pytest.mark.parametrize("old, new, code", [
    ("council_size: 3", "council_size: 4", "brief-council-size"),
    ("weight: 5", "weight: 0", "brief-criteria"),
    ("decision: D-001", "decision: D-002", "brief-decision"),
    ("gate: G3", "gate: X", "brief-gate"),
    ("options: [A, B]", "options: [A, A]", "brief-options"),
    ("options: [A, B]", "options: [A, none]", "brief-options"),
])
def test_brief_frontmatter_is_validated(tmp_path, old, new, code):
    ws = workspace(tmp_path, brief_text().replace(old, new, 1))
    proc = run(ws)
    assert proc.returncode == 1 and code in codes(proc)


def test_brief_without_frontmatter(tmp_path):
    ws = workspace(tmp_path, "# Brief\n")
    proc = run(ws)
    assert proc.returncode == 1 and "brief-frontmatter" in codes(proc)


def test_brief_with_only_weighted_criteria_needs_no_exclusions_key(tmp_path):
    ws = workspace(tmp_path, brief_text(exclusion=()))
    votes = [default_vote(p, exclusion=()) for p in THREE]
    for v in votes:
        v["exclusions"] = {}
    cast(ws, votes)
    assert run(ws).returncode == 0


def test_brief_without_exclusions_rejects_exclusion_cells(tmp_path):
    ws = workspace(tmp_path, brief_text(exclusion=()))
    votes = [default_vote(p, exclusion=()) for p in THREE]
    votes[0]["exclusions"] = {"A": {"TC-05": "pass"}, "B": {}}
    cast(ws, votes)
    proc = run(ws)
    assert proc.returncode == 1 and "vote-exclusions-extra" in codes(proc)


# --- cli -------------------------------------------------------------------------------------------------------------------

def test_gate_filter_counts_only_that_gate(tmp_path):
    ws = workspace(tmp_path)
    put(ws / "decisions" / "D-002-stack" / "brief.md", brief_text(gate="G4").replace("D-001", "D-002"))
    cast(ws, unanimous())
    assert run(ws).returncode == 1  # D-002 has no votes yet
    proc = run(ws, "--gate", "G3")
    assert proc.returncode == 0 and "D-002" not in proc.stdout
    assert run(ws, "--gate", "G4").returncode == 1
    assert run(ws, "--gate", "G7").returncode == 0  # nothing at G7: clean


def test_one_decision_by_name(tmp_path):
    ws = workspace(tmp_path)
    put(ws / "decisions" / "D-002-stack" / "brief.md", brief_text(gate="G4").replace("D-001", "D-002"))
    cast(ws, unanimous())
    assert run(ws, "--decision", DEC).returncode == 0
    assert run(ws, "--decision", "D-009-none").returncode == 2


def test_no_decisions_is_clean(tmp_path):
    ws = tmp_path / ".agent-workspace"
    (ws / "checks").mkdir(parents=True)
    proc = run(ws)
    assert proc.returncode == 0
    assert "Không có quyết định" in read(ws / "checks" / f"tally-{TODAY}.md")


def test_bad_arguments_exit_two(tmp_path):
    ws = workspace(tmp_path)
    assert run(ws, "--gate", "banana").returncode == 2
    assert run(tmp_path / "missing").returncode == 2
    assert run(ws, "--config", str(tmp_path / "nope.yaml")).returncode == 2


def test_report_lists_the_errors(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    votes[0]["choice"] = "B"
    cast(ws, votes)
    run(ws)
    report = read(ws / "checks" / f"tally-{TODAY}.md")
    assert "LỖI" in report and "vote-choice-not-top" in report and "không đếm được" in report


def test_rerun_after_fixing_a_vote_writes_the_result(tmp_path):
    ws = workspace(tmp_path)
    votes = unanimous()
    votes[0]["choice"] = "B"
    cast(ws, votes)
    assert run(ws).returncode == 1
    votes[0]["choice"] = "A"
    cast(ws, votes)
    assert run(ws).returncode == 0
    assert "đề xuất phương án A" in read(decision_dir(ws) / "decision.md")


# --- repo consistency ------------------------------------------------------------------------------------------------------

def test_config_perspectives_are_the_council_agent_files():
    cfg, errors = tv.load_config(tv.DEFAULT_CONFIG)
    assert not errors
    assert sorted(cfg.perspectives) == sorted(p.stem for p in (CORE / "claude" / "agents" / "council").glob("*.md"))
    assert cfg.sizes[3] == cfg.sizes[5][:3]


def test_vote_keys_are_the_keys_of_the_vote_template():
    text = (CORE / "templates" / "workspace" / "vote.md").read_text(encoding="utf-8")
    front = text.split("---")[1]
    keys = tuple(re.findall(r"^([a-z_]+):", front, re.MULTILINE))
    assert keys == tv.VOTE_KEYS


def test_brief_keys_are_the_keys_of_the_brief_template():
    text = (CORE / "templates" / "workspace" / "brief.md").read_text(encoding="utf-8")
    front = text.split("---")[1]
    assert tuple(re.findall(r"^([a-z_]+):", front, re.MULTILINE)) == tv.BRIEF_KEYS


def test_docs_state_the_overreach_cap():
    cfg, _ = tv.load_config(tv.DEFAULT_CONFIG)
    cap = str(cfg.max_overreach)
    texts = [CORE.parent / "PLAN.md", CORE / "templates" / "workspace" / "vote.md", *(CORE / "claude" / "agents" / "council").glob("*.md")]
    for path in texts:
        text = path.read_text(encoding="utf-8")
        assert re.search(rf"(tối đa|không quá|giới hạn)[^.\n]{{0,40}}\b{cap}\b", text), path.name


def test_decision_template_has_the_council_markers():
    text = tv.DECISION_TEMPLATE.read_text(encoding="utf-8")
    assert len(tv.BEGIN_RE.findall(text)) == 1 and len(tv.END_RE.findall(text)) == 1
    assert tv.DEFAULT_BEGIN in text


# --- numbers in the reasons come from the brief ----------------------------------------------------------------------------

def reasoned(tmp_path, reasons, cites=("TC-01",), brief=None):
    ws = workspace(tmp_path, brief)
    votes = unanimous()
    for v in votes:
        v["cites"] = list(cites)
    cast(ws, votes, reasons=reasons)
    return ws, run(ws)


def test_a_number_that_is_not_in_the_brief_rejects_the_vote(tmp_path):
    _, proc = reasoned(tmp_path, "1. Chi phí 777 USD mỗi tháng — TC-01")
    assert proc.returncode == 1 and "vote-number-not-in-brief" in codes(proc) and "777" in proc.stdout


def test_a_number_that_is_in_the_brief_is_accepted(tmp_path):
    _, proc = reasoned(tmp_path, "1. Chi phí 120 USD mỗi tháng và độ trễ 99 ms — TC-01")
    assert proc.returncode == 0, proc.stdout


def test_each_reason_is_checked(tmp_path):
    _, proc = reasoned(tmp_path, "1. Chi phí 120 USD — TC-01\n2. Độ trễ 555 ms — TC-01")
    assert proc.returncode == 1 and "lý do 2" in proc.stdout and "lý do 1 " not in proc.stdout


def test_a_continuation_line_of_a_reason_is_checked_too(tmp_path):
    _, proc = reasoned(tmp_path, "1. Chi phí 120 USD — TC-01\n   và độ trễ 555 ms")
    assert proc.returncode == 1 and "vote-number-not-in-brief" in codes(proc)


def test_a_number_must_match_as_a_whole(tmp_path):
    # the brief has 120, 1.000 and 16.4.1, but not 20, 1.00, 16.4 or 000
    for reason in ("20 USD", "1.00 người dùng", "PostgreSQL 16.4", "000 người"):
        _, proc = reasoned(tmp_path, f"1. {reason} — TC-01")
        assert proc.returncode == 1 and "vote-number-not-in-brief" in codes(proc), reason
    for reason in ("1.000 người dùng", "PostgreSQL 16.4.1"):
        _, proc = reasoned(tmp_path, f"1. {reason} — TC-01")
        assert proc.returncode == 0, (reason, proc.stdout)


def test_digits_of_ids_and_of_the_list_marker_are_not_numbers(tmp_path):
    _, proc = reasoned(tmp_path, "7. Đáp ứng NFR-07, C-03, A-05 và R-02 — TC-01", cites=("NFR-07", "C-03", "A-05", "R-02", "TC-01"))
    assert proc.returncode == 0, proc.stdout


def test_digits_glued_to_letters_are_not_numbers(tmp_path):
    _, proc = reasoned(tmp_path, "1. Đạt p95 và dùng S3, Q5 theo TC-01")
    assert proc.returncode == 0, proc.stdout


def test_the_overreach_and_risk_sections_are_not_checked_for_numbers(tmp_path):
    ws = workspace(tmp_path)
    cast(ws, unanimous(), risks="khả năng 3, tác động 4, thiệt hại 987 USD", overreach_body="thêm 654 máy")
    assert run(ws).returncode == 0


def test_number_tokens():
    assert tv.number_tokens("120 USD, 99,5% và 1.000; 16.4.1. Hết 7.") == ["120", "99,5", "1.000", "16.4.1", "7"]
    assert tv.number_tokens("TC-01 NFR-07 A-03 p95 S3 Q5 v2") == []
    assert tv.number_tokens("a 5 b 5 c 6") == ["5", "6"]
    assert tv.number_tokens("2026-10-12") == ["2026", "10", "12"]


def test_an_assumption_can_be_cited(tmp_path):
    _, proc = reasoned(tmp_path, "1. Theo A-03 thì tải tăng — TC-01", cites=("A-03", "TC-01"))
    assert proc.returncode == 0, proc.stdout
    _, proc = reasoned(tmp_path, "1. Theo A-03 thì tải tăng — TC-01", cites=("TC-01",))
    assert proc.returncode == 1 and "vote-cites-incomplete" in codes(proc)


def test_cite_kinds_must_be_prefixes_of_the_shared_id_list(tmp_path):
    cfg_text = (tv.DEFAULT_CONFIG).read_text(encoding="utf-8").replace("cite_kinds: [TC, NFR, C, A, R]", "cite_kinds: [TC, XYZ]")
    path = tmp_path / "council.yaml"
    path.write_text(cfg_text, encoding="utf-8")
    cfg, errors = tv.load_config(path)
    assert cfg is None and any("XYZ" in e for e in errors)


def test_docs_state_the_number_rule():
    texts = [CORE / "templates" / "workspace" / "vote.md", CORE.parent / "PLAN.md", *(CORE / "claude" / "agents" / "council").glob("*.md")]
    for path in texts:
        text = path.read_text(encoding="utf-8")
        assert "nguyên văn trong" in text and "brief" in text, path.name
        assert re.search(r"nguyên văn trong\s+`?brief", text), path.name
