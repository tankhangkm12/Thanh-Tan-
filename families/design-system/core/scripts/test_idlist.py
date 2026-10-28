"""The ID prefixes live in core/data/ids.yaml; no script repeats the list, every script that needs it uses idlist.py,
and the docs name the same prefixes.

Run with: uv run --with pytest --with pyyaml pytest families/design-system/core/scripts
"""

import ast
import re
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import calc_capacity  # noqa: E402
import check_links  # noqa: E402
import check_numbers  # noqa: E402
import idlist  # noqa: E402
import tally_votes  # noqa: E402

CORE = HERE.parent
IDS = idlist.load()
DATA = yaml.safe_load((CORE / "data" / "ids.yaml").read_text(encoding="utf-8"))
SCRIPTS = sorted(p for p in HERE.glob("*.py") if not p.name.startswith("test_") and p.name != "idlist.py")
USERS = ["check_links.py", "check_numbers.py", "tally_votes.py", "check_trace.py"]  # the scripts the shared list is for


def write(tmp_path: Path, **overrides) -> Path:
    data = {**DATA, **overrides}
    path = tmp_path / "ids.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# --- the list --------------------------------------------------------------------------------------------------------------

def test_the_list_has_the_agreed_prefixes():
    assert set(IDS.kinds) == {"FR", "NFR", "C", "A", "TC", "FL", "SCR", "SVC", "API", "EVT", "TBL", "BKT", "R", "D", "CH"}
    assert set(IDS.backlink_kinds) == {"SVC", "TBL", "BKT", "EVT", "API"}
    assert IDS.homes == {"C": "00-context/constraints.md", "A": "00-context/assumptions.md"}


@pytest.mark.parametrize("text, found", [
    ("Xem C-01 và A-03.", ["C-01", "A-03"]),
    ("TC-01 NFR-02 FR-02", ["TC-01", "NFR-02", "FR-02"]),  # no C-01, R-02 read out of the middle of them
    ("SVC-order, TBL-orders, API-create-order", ["SVC-order", "TBL-orders", "API-create-order"]),
    ("A-B và C-level không có số", ["A-B", "C-level"]),   # a prefix plus a name is an ID: the cost of short prefixes
    ("xA-01 hay -A-01 hay _A-01", []),
    ("(C-01), [A-02]; FL-001.", ["C-01", "A-02", "FL-001"]),
])
def test_id_re(text, found):
    assert IDS.id_re().findall(text) == found


def test_id_re_can_be_limited_to_some_kinds():
    assert IDS.id_re(["A"]).findall("A-1 C-2 TC-3 A-4") == ["A-1", "A-4"]


def test_kind_of():
    assert IDS.kind_of("NFR-p95") == "NFR" and IDS.kind_of("C-01") == "C"


@pytest.mark.parametrize("overrides, message", [
    ({"kinds": []}, "kinds"),
    ({"kinds": ["FR", "FR"]}, "trùng"),
    ({"kinds": ["fr"]}, "kinds"),
    ({"backlink_kinds": ["ZZZ"]}, "backlink_kinds"),
    ({"homes": {"ZZ": "a.md"}}, "homes"),
    ({"homes": {"C": "/abs/constraints.md"}}, "homes"),
    ({"homes": {"C": "constraints.txt"}}, "homes"),
    ({"homes": ["C"]}, "homes"),
    ({"placeholder_name": "["}, "placeholder_name"),
])
def test_a_bad_list_is_refused(tmp_path, overrides, message):
    with pytest.raises(ValueError, match=message):
        idlist.load(write(tmp_path, **overrides))


def test_missing_or_broken_file_is_refused(tmp_path):
    with pytest.raises(ValueError):
        idlist.load(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("kinds: [", encoding="utf-8")
    with pytest.raises(ValueError):
        idlist.load(bad)
    bad.write_text("- a\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        idlist.load(bad)


# --- the scripts use it ----------------------------------------------------------------------------------------------------

def test_check_links_uses_the_shared_list():
    assert check_links.ID_KINDS == IDS.kinds and check_links.BACKLINK_KINDS == IDS.backlink_kinds
    assert check_links.ID_RE.pattern == IDS.id_re().pattern
    assert check_links.IDS.homes == IDS.homes


def test_check_numbers_masks_every_id_and_reads_a_ids_from_the_list():
    assert check_numbers.ASSUMPTION_REF.pattern == IDS.id_re(["A"]).pattern
    for kind in IDS.kinds:
        masked = check_numbers.mask(f"dùng {kind}-ab2 và {kind}-v3 ở đây")
        assert not re.search(r"\d", masked), kind


def test_tally_votes_cites_only_kinds_of_the_list():
    cfg, errors = tally_votes.load_config(tally_votes.DEFAULT_CONFIG)
    assert not errors and set(cfg.cite_kinds) <= set(IDS.kinds)
    assert {"C", "A"} <= set(cfg.cite_kinds)
    assert cfg.cite_re().pattern == IDS.id_re(cfg.cite_kinds).pattern
    assert tally_votes.IDS.kinds == IDS.kinds


def test_calc_capacity_assumption_ids_are_ids_of_the_list():
    for ident in ("A-dau", "A-peak-factor", "A-1"):
        assert calc_capacity.ASSUMPTION_ID.fullmatch(ident)
        assert IDS.id_re(["A"]).findall(ident) == [ident]


@pytest.mark.parametrize("script", USERS)
def test_every_script_that_needs_the_list_imports_idlist(script):
    path = HERE / script
    if not path.exists():
        pytest.skip(f"{script} is not written yet")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert "idlist" in imported, f"{script} must read the ID prefixes through idlist.py"


def string_constants(node):
    return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_no_script_repeats_the_list(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    kinds = set(IDS.kinds)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            hits = [s for s in string_constants(node) if s in kinds]
            assert len(hits) < 4, f"{path.name}:{node.lineno} lists ID prefixes {hits}: read them from data/ids.yaml"
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "\n" not in node.value:
            assert not re.search(r"\b(?:NFR\|FR|FR\|NFR|TBL\|BKT|SVC\|API|EVT\|TBL)\b", node.value), f"{path.name}:{node.lineno} spells out an ID prefix alternation"


# --- the docs --------------------------------------------------------------------------------------------------------------

def test_plan_names_every_prefix_and_both_home_files():
    plan = (CORE.parent / "PLAN.md").read_text(encoding="utf-8")
    paragraph = next(p for p in plan.split("\n\n") if p.startswith("**Danh sách tiền tố ID dùng chung"))
    for kind in IDS.kinds:
        assert f"`{kind}`" in paragraph, kind
    for home in IDS.homes.values():
        assert home in plan, home
    assert "core/data/ids.yaml" in paragraph


def test_stages_names_the_home_files_of_c_and_a():
    stages = (CORE / "workflow" / "stages.md").read_text(encoding="utf-8")
    for home in IDS.homes.values():
        assert home in stages, home
