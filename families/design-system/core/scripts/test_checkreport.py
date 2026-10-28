"""Tests for checkreport.py: the hash block of the reports, and what promote_drafts.py asks of the reports of a gate.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import hashlib
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import checkreport as cr  # noqa: E402

CORE = Path(__file__).resolve().parent.parent
CONFIG, CONFIG_ERRORS = cr.load_config()


def put(path: Path, text: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def write_report(ws: Path, prefix: str, day: str, script: str, ok=True, files=None, gate=None, mode=None) -> Path:
    return put(ws / "checks" / f"{prefix}-{day}.md", "# báo cáo\n" + cr.render(script, ok, files or {}, gate, mode))


# --- hashing ---------------------------------------------------------------------------------------------------------------

def test_the_hash_is_sha256_of_the_content_and_ignores_line_endings(tmp_path):
    lf = put(tmp_path / "a.md", "một\nhai\n")
    crlf = put(tmp_path / "b.md", "một\r\nhai\r\n")
    assert cr.sha256_file(lf) == cr.sha256_file(crlf) == hashlib.sha256("một\nhai\n".encode()).hexdigest()
    assert cr.sha256_file(put(tmp_path / "c.md", "một\nhai")) != cr.sha256_file(lf)       # content still counts


def test_a_lone_carriage_return_is_content_not_a_line_ending(tmp_path):
    assert cr.sha256_file(put(tmp_path / "a", b"x\ry")) != cr.sha256_file(put(tmp_path / "b", b"x\ny"))


def test_paths_are_relative_to_the_workspace_and_absolute_outside_it(tmp_path):
    ws = tmp_path / "ws"
    inside = put(ws / "drafts" / "a.md", "x")
    outside = put(tmp_path / "other" / "b.md", "y")
    assert cr.rel_path(ws, inside) == "drafts/a.md"
    assert cr.rel_path(ws, outside) == outside.resolve().as_posix()
    assert set(cr.hash_files(ws, [inside, outside])) == {"drafts/a.md", outside.resolve().as_posix()}


def test_hash_files_skips_what_is_not_a_file_and_is_sorted(tmp_path):
    ws = tmp_path
    put(ws / "b.md", "b")
    put(ws / "a.md", "a")
    (ws / "dir").mkdir()
    assert list(cr.hash_files(ws, [ws / "b.md", ws / "dir", ws / "missing.md", ws / "a.md"])) == ["a.md", "b.md"]


def test_expand_matches_globs_to_files_only(tmp_path):
    put(tmp_path / "drafts" / "x" / "a.md", "1")
    put(tmp_path / "drafts" / "b.md", "2")
    put(tmp_path / "drafts" / "c.txt", "3")
    (tmp_path / "drafts" / "empty.md").mkdir()
    assert [p.name for p in cr.expand(tmp_path, ["drafts/**/*.md"])] == ["b.md", "a.md"]       # sorted by path: drafts/b.md before drafts/x/a.md
    assert cr.expand(tmp_path, ["nothing/**/*"]) == []


# --- the block -------------------------------------------------------------------------------------------------------------

def test_a_block_round_trips():
    files = {"drafts/a.md": "a" * 64, "state.md": "b" * 64}
    block = cr.parse("# r\n\ntext\n" + cr.render("check_links.py", True, files, "G3", "check"))
    assert block == cr.Block("check_links.py", True, "G3", "check", files)


def test_a_dirty_report_without_gate_or_mode_round_trips():
    block = cr.parse(cr.render("check_links.py", False, {}))
    assert block == cr.Block("check_links.py", False, None, None, {})


def test_awkward_file_names_cannot_break_the_table(tmp_path):
    names = ["drafts/a|b.md", "drafts/with `tick`.md", "drafts/100%.md", "drafts/a%7Cb.md","drafts/new\nline.md", "drafts/ünï cødé.md"]
    files = {n: "c" * 64 for n in names}
    block = cr.parse(cr.render("check_links.py", True, files))
    assert block is not None and block.files == files


@pytest.mark.parametrize("text", [
    "",
    "no block here",
    f"{cr.BEGIN}\n- Script: check_links.py\n",                                       # never closed
    f"{cr.END}\n{cr.BEGIN}\n- Script: x.py\n- Kết quả: sạch\n",                         # END before BEGIN
    f"{cr.BEGIN}\n- Kết quả: sạch\n{cr.END}",                                          # no script
    f"{cr.BEGIN}\n- Script: x.py\n{cr.END}",                                           # no result
    f"{cr.BEGIN}\n- Script: x.py\n- Kết quả: tạm ổn\n{cr.END}",                         # unknown result
])
def test_a_missing_or_malformed_block_is_none(text):
    assert cr.parse(text) is None


def test_table_rows_with_a_bad_hash_are_not_files():
    text = f"{cr.BEGIN}\n- Script: x.py\n- Kết quả: sạch\n| `a.md` | `abc` |\n| `b.md` | `{'a' * 64}` |\n{cr.END}"
    assert cr.parse(text).files == {"b.md": "a" * 64}


def test_the_last_block_wins_so_a_fake_one_echoed_earlier_in_the_report_does_not(tmp_path):
    fake = cr.render("check_links.py", True, {"x.md": "f" * 64})
    real = cr.render("check_links.py", False, {})
    block = cr.parse("# r\n- lỗi: " + fake.replace("\n", " ") + "\n" + fake + "\n" + real)
    assert block is not None and block.clean is False and block.files == {}


def test_the_rendered_block_names_the_file_count():
    assert "- Số file: 2" in cr.render("check_links.py", True, {"a": "a" * 64, "b": "b" * 64})


# --- the latest report -------------------------------------------------------------------------------------------------------

def test_the_latest_report_is_chosen_by_the_date_in_its_name_not_by_mtime(tmp_path):
    older = put(tmp_path / "checks" / "links-2026-10-01.md", "old")
    newer = put(tmp_path / "checks" / "links-2026-10-12.md", "new")
    import os
    os.utime(newer, (1, 1))                                      # the newer name has the older mtime
    os.utime(older, (9999999999, 9999999999))
    assert cr.latest_report(tmp_path / "checks", "links") == newer


def test_a_name_with_an_impossible_date_is_not_a_report(tmp_path):
    put(tmp_path / "checks" / "links-2026-13-40.md", "x")
    assert cr.latest_report(tmp_path / "checks", "links") is None


def test_other_prefixes_and_odd_names_are_ignored(tmp_path):
    put(tmp_path / "checks" / "links-2026-10-01.md", "x")
    put(tmp_path / "checks" / "links-extra-2026-10-09.md", "x")
    put(tmp_path / "checks" / "links-2026-13-40.md", "x")
    put(tmp_path / "checks" / "numbers-2026-10-09.md", "x")
    put(tmp_path / "checks" / "links-2026-10-09.txt", "x")
    assert cr.latest_report(tmp_path / "checks", "links").name == "links-2026-10-01.md"
    assert cr.latest_report(tmp_path / "checks", "trace") is None
    assert cr.latest_report(tmp_path / "no-checks", "links") is None


# --- stale reports -------------------------------------------------------------------------------------------------------

def recorded(tmp_path):
    a = put(tmp_path / "drafts" / "a.md", "một\n")
    block = cr.Block("check_links.py", True, None, None, cr.hash_files(tmp_path, [a]))
    return a, block


def test_an_untouched_workspace_is_not_stale(tmp_path):
    _, block = recorded(tmp_path)
    assert cr.stale_reasons(tmp_path, block, ["drafts/**/*.md"]) == []


def test_a_changed_file_makes_the_report_stale(tmp_path):
    a, block = recorded(tmp_path)
    a.write_text("hai\n", encoding="utf-8")
    assert cr.stale_reasons(tmp_path, block, []) == ["đã đổi sau khi kiểm: drafts/a.md"]


def test_a_deleted_file_makes_the_report_stale(tmp_path):
    a, block = recorded(tmp_path)
    a.unlink()
    assert cr.stale_reasons(tmp_path, block, []) == ["đã xóa sau khi kiểm: drafts/a.md"]


def test_a_new_file_in_scope_makes_the_report_stale_but_one_outside_does_not(tmp_path):
    _, block = recorded(tmp_path)
    put(tmp_path / "drafts" / "new.md", "x")
    put(tmp_path / "elsewhere" / "z.md", "x")
    assert cr.stale_reasons(tmp_path, block, ["drafts/**/*.md"]) == ["mới thêm sau khi kiểm (báo cáo không có): drafts/new.md"]
    assert cr.stale_reasons(tmp_path, block, []) == []                      # an empty scope compares only the listed files


def test_line_ending_changes_alone_do_not_make_a_report_stale(tmp_path):
    a, block = recorded(tmp_path)
    a.write_bytes("một\r\n".encode())
    assert cr.stale_reasons(tmp_path, block, []) == []


# --- data/gates.yaml -------------------------------------------------------------------------------------------------------

def test_the_shipped_config_loads():
    assert CONFIG is not None, CONFIG_ERRORS
    assert sorted(CONFIG.gates) == list(range(11))
    assert CONFIG.reports["calc_capacity"].modes_for(1) == ("assumptions-only", "write", "check")
    assert CONFIG.reports["calc_capacity"].modes_for(5) == ("write", "check")
    assert CONFIG.reports["check_links"].modes_for(5) is None
    assert CONFIG.reports["check_profile"].gated and not CONFIG.reports["check_links"].gated


def edited(tmp_path, change) -> tuple:
    data = yaml.safe_load(cr.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "gates.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return cr.load_config(path)


@pytest.mark.parametrize("change", [
    lambda d: d.update(version=2),
    lambda d: d["gates"].pop("G7"),
    lambda d: d["gates"].update(G11=["check_links"]),
    lambda d: d["gates"].update(G3=["no_such_script"]),
    lambda d: d["reports"]["check_links"].pop("prefix"),
    lambda d: d["reports"]["check_numbers"].update(prefix="links"),
    lambda d: d["reports"]["check_links"].update(scope="drafts/**/*.md"),
    lambda d: d["reports"]["calc_capacity"].update(modes={"G1": ["check"]}),
    lambda d: d.update(non_report_scripts=["check_links"]),
    lambda d: d.pop("non_report_scripts"),
])
def test_a_bad_config_is_refused_with_a_reason(tmp_path, change):
    config, errors = edited(tmp_path, change)
    assert config is None and errors


def test_a_missing_or_broken_config_is_refused(tmp_path):
    assert cr.load_config(tmp_path / "nope.yaml")[0] is None
    (tmp_path / "bad.yaml").write_text("a: [", encoding="utf-8")
    assert cr.load_config(tmp_path / "bad.yaml")[0] is None


# --- gate_problems ---------------------------------------------------------------------------------------------------------

class Gate:
    """A workspace where every script G0 asks for has a clean report; tests spoil one thing at a time."""

    def __init__(self, tmp_path, gate=0):
        self.ws = tmp_path
        self.gate = gate
        put(self.ws / "state.md", "x")
        for script in CONFIG.gates[gate]:
            self.write(script)

    def write(self, script, day="2026-10-12", ok=True, files=None, gate="default", mode="default"):
        spec = CONFIG.reports[script]
        gate = (f"G{self.gate}" if spec.gated else None) if gate == "default" else gate
        modes = spec.modes_for(self.gate)
        mode = (modes[0] if modes else None) if mode == "default" else mode
        if files is None:
            files = cr.hash_files(self.ws, cr.expand(self.ws, spec.scope))
        return write_report(self.ws, spec.prefix, day, script + ".py", ok, files, gate, mode)

    def problems(self):
        return cr.gate_problems(self.ws, self.gate, CONFIG)


def test_every_script_with_a_clean_fresh_report_is_accepted(tmp_path):
    problems, accepted = Gate(tmp_path, 3).problems()
    assert problems == [] and len(accepted) == len(CONFIG.gates[3])


def test_a_missing_report_names_the_script_and_the_gate_to_run_it_for(tmp_path):
    gate = Gate(tmp_path, 3)
    (tmp_path / "checks" / "profile-2026-10-12.md").unlink()
    problems, _ = gate.problems()
    assert len(problems) == 1 and "check_profile.py" in problems[0] and "--gate G3" in problems[0]


def test_every_gate_needs_exactly_the_scripts_of_gates_yaml(tmp_path):
    for number in range(11):
        gate = Gate(tmp_path / f"g{number}", number)
        problems, accepted = gate.problems()
        assert problems == [] and len(accepted) == len(CONFIG.gates[number])


def test_a_report_with_errors_is_refused(tmp_path):
    gate = Gate(tmp_path, 3)
    gate.write("check_links", ok=False)
    problems, _ = gate.problems()
    assert len(problems) == 1 and "có lỗi" in problems[0] and "check_links" in problems[0]


def test_only_the_latest_report_counts_a_later_dirty_one_beats_an_earlier_clean_one(tmp_path):
    gate = Gate(tmp_path, 3)
    gate.write("check_links", day="2026-10-13", ok=False)
    assert "có lỗi" in gate.problems()[0][0]
    gate.write("check_links", day="2026-10-14", ok=True)
    assert gate.problems()[0] == []


def test_an_older_clean_report_does_not_save_a_newer_dirty_one_even_with_a_newer_mtime(tmp_path):
    gate = Gate(tmp_path, 3)
    clean = gate.write("check_links", day="2026-10-13", ok=True)
    gate.write("check_links", day="2026-10-14", ok=False)
    import os
    os.utime(clean, (9999999999, 9999999999))
    assert len(gate.problems()[0]) == 1


def test_a_report_without_the_block_or_from_another_script_is_refused(tmp_path):
    gate = Gate(tmp_path, 3)
    put(tmp_path / "checks" / "links-2026-10-12.md", "# check_links\n\nkhông có lỗi\n")
    put(tmp_path / "checks" / "numbers-2026-10-12.md", "# r\n" + cr.render("check_links.py", True, {}))
    problems, _ = gate.problems()
    assert len(problems) == 2 and all("khối" in p for p in problems)


def test_a_gated_report_must_be_for_the_gate_but_a_run_over_everything_counts(tmp_path):
    gate = Gate(tmp_path, 3)
    gate.write("check_profile", gate="G5")
    problems, _ = gate.problems()
    assert len(problems) == 1 and "G5" in problems[0] and "cần G3" in problems[0]
    gate.write("check_profile", gate=None)
    assert "không ghi" in gate.problems()[0][0]
    gate.write("tally_votes", gate="tất cả")
    gate.write("check_profile", gate="G3")
    assert gate.problems()[0] == []


def test_the_capacity_mode_must_be_allowed_for_the_gate(tmp_path):
    g1, g5 = Gate(tmp_path / "a", 1), Gate(tmp_path / "b", 5)
    g1.write("calc_capacity", mode="assumptions-only")
    assert g1.problems()[0] == []
    g5.write("calc_capacity", mode="assumptions-only")
    problems, _ = g5.problems()
    assert len(problems) == 1 and "assumptions-only" in problems[0] and "write, check" in problems[0]
    g5.write("calc_capacity", mode=None)
    assert len(g5.problems()[0]) == 1
    g5.write("calc_capacity", mode="check")
    assert g5.problems()[0] == []


def test_a_changed_file_makes_a_report_stale_and_the_message_names_it(tmp_path):
    gate = Gate(tmp_path, 1)
    put(tmp_path / "drafts" / "a.md", "một")
    for script in ("check_links", "check_numbers", "check_profile"):
        gate.write(script)
    assert gate.problems()[0] == []
    put(tmp_path / "drafts" / "a.md", "hai")
    problems, _ = gate.problems()
    assert len(problems) == 3 and all("drafts/a.md" in p and "đã cũ" in p for p in problems)


def test_a_file_added_after_the_check_makes_scoped_reports_stale(tmp_path):
    gate = Gate(tmp_path, 3)
    put(tmp_path / "drafts" / "new.md", "x")
    problems, _ = gate.problems()
    assert {p.split(":")[0] for p in problems} == {"check_links.py", "check_numbers.py", "check_profile.py"}


def test_a_state_file_change_makes_the_workspace_report_stale(tmp_path):
    gate = Gate(tmp_path, 3)
    put(tmp_path / "state.md", "đổi")
    problems, _ = gate.problems()
    assert [p.split(":")[0] for p in problems] == ["check_workspace.py"]


def test_long_stale_lists_are_shortened(tmp_path):
    gate = Gate(tmp_path, 1)
    for i in range(6):
        put(tmp_path / "drafts" / f"f{i}.md", str(i))
    gate.write("check_links")
    for i in range(6):
        put(tmp_path / "drafts" / f"f{i}.md", "đổi")
    problem = [p for p in gate.problems()[0] if p.startswith("check_links")][0]
    assert "và 3 file nữa" in problem


def test_a_report_made_with_a_root_outside_the_workspace_does_not_cover_the_drafts(tmp_path):
    ws, other = tmp_path / "ws", tmp_path / "other.md"
    put(other, "một")
    gate = Gate(ws, 3)
    put(ws / "drafts" / "a.md", "x")
    gate.write("check_links", files=cr.hash_files(ws, [other]))
    problems, _ = gate.problems()
    assert any(p.startswith("check_links") and "drafts/a.md" in p for p in problems)


# --- data/gates.yaml and the rest of the family ---------------------------------------------------------------------------------

STAGES = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")


def stage_script_names() -> dict[int, set[str]]:
    gate, found = None, {}
    for line in STAGES.splitlines():
        heading = re.match(r"## G(\d+)\.", line)
        if heading:
            gate = int(heading.group(1))
        if line.startswith("- **Script:**"):
            found[gate] = set(re.findall(r"`([a-z_]+)\.py", line))
    return found


def test_gates_yaml_lists_the_report_scripts_of_each_gate_of_stages_md():
    named = stage_script_names()
    assert sorted(named) == list(range(11))
    for gate, names in named.items():
        assert set(CONFIG.gates[gate]) == names - set(CONFIG.non_report), f"G{gate}: gates.yaml and stages.md disagree"


def test_every_script_is_either_a_report_script_a_non_report_one_or_the_hook():
    import test_workflow_scripts as tws
    scripts = {p.stem for p in Path(__file__).parent.glob("*.py") if not p.name.startswith("test_") and p.name not in tws.MODULES}
    listed = set(CONFIG.reports) | set(CONFIG.non_report)
    assert scripts - listed == {"guard_write"}, "a script is in neither reports nor non_report_scripts of gates.yaml"
    assert listed - scripts == {n.removesuffix(".py") for n in tws.PENDING}, "gates.yaml names a script that does not exist (and is not pending)"


def test_the_scripts_that_judge_a_gate_are_gated_when_they_take_a_gate():
    for script in ("check_profile", "check_trace", "check_workspace", "tally_votes"):
        assert CONFIG.reports[script].gated
    for script in ("check_links", "check_numbers", "check_versions", "calc_capacity"):
        assert not CONFIG.reports[script].gated


def test_trace_scope_covers_every_source_file_check_trace_reads():
    import check_trace as ct
    trace, _ = ct.load_config(ct.DEFAULT_CONFIG)
    scope = CONFIG.reports["check_trace"].scope
    for rel, _ in trace.sources:
        assert any(g == rel or g.startswith(rel + "/") for g in scope), f"{rel} is read by check_trace but not in its scope"


def test_the_mode_names_of_gates_yaml_are_the_ones_the_scripts_write():
    source = (Path(__file__).parent / "calc_capacity.py").read_text(encoding="utf-8")
    for mode in {m for modes in CONFIG.reports["calc_capacity"].modes.values() for m in modes}:
        assert f'"{mode}"' in source
    assert '"templates"' in (Path(__file__).parent / "check_profile.py").read_text(encoding="utf-8")


# --- dated reports and the promoted block ------------------------------------------------------------------------------------

def test_dated_reports_come_latest_date_first_and_skip_odd_names(tmp_path):
    for name in ("promote-2026-10-01.md", "promote-2026-12-01.md", "promote-2026-11-05.md", "promote-2026-13-40.md", "promote-x-2026-12-09.md", "promote-2026-12-09.txt"):
        put(tmp_path / "checks" / name, "x")
    assert [p.name for p in cr.dated_reports(tmp_path / "checks", "promote")] == ["promote-2026-12-01.md", "promote-2026-11-05.md", "promote-2026-10-01.md"]
    assert cr.dated_reports(tmp_path / "none", "promote") == []


def test_a_promoted_block_round_trips_with_awkward_paths():
    files = {"README.md": "a" * 64, "01-system/sub dir/a `b`.md": "b" * 64, "x%41.md": "c" * 64}
    parsed = cr.parse_promoted("# r\n\n## G10: đã chép\n" + cr.render_promoted(10, files))
    assert len(parsed) == 1 and parsed[0].gate == "G10" and parsed[0].files == files


def test_every_block_of_a_report_is_parsed_in_order_and_bad_ones_are_dropped():
    one = cr.render_promoted(3, {"a.md": "a" * 64})
    two = cr.render_promoted(10, {"b.md": "b" * 64})
    empty = cr.render_promoted(5, {})
    nogate = two.replace("- Gate: G10", "- Gate: X")
    badhash = two.replace("b" * 64, "b" * 63)
    parsed = cr.parse_promoted("\n".join([one, empty, nogate, badhash, two]))
    assert [(b.gate, sorted(b.files)) for b in parsed] == [("G3", ["a.md"]), ("G10", ["b.md"])]
    assert cr.parse_promoted("no block here") == [] and cr.parse_promoted(cr.PROMOTED_BEGIN + " unterminated") == []


def test_a_promoted_block_is_not_mistaken_for_the_checked_block():
    text = cr.render_promoted(10, {"a.md": "a" * 64})
    assert cr.parse(text) is None
    assert cr.parse_promoted(cr.render("check_links.py", True, {"a.md": "a" * 64}, "G3")) == []
