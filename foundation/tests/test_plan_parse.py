from thanhtan.plan import PlanItem, check_plan, docs_problem, parse_plan

PLAN = """# Plan

### C1 — Add greeting
- role: implementer
- files: src/greet.py, tests/test_greet.py
- done-when: `uv run pytest tests/test_greet.py`
- docs: https://docs.python.org/3/

### C2 - Tidy
- role: tester
- files: không có
- done-when: lint passes
- docs: không có — nothing to read for a rename
"""


class Roles:
    def __init__(self, *names):
        self.names = set(names)

    def roles(self):
        return self.names


def test_parse_items():
    plan = parse_plan(PLAN)
    assert [item.code for item in plan.items] == ["C1", "C2"]
    first, second = plan.items
    assert first == PlanItem(
        "C1", "Add greeting", "implementer", ("src/greet.py", "tests/test_greet.py"),
        "`uv run pytest tests/test_greet.py`", "https://docs.python.org/3/",
    )
    assert first.docs_links == ("https://docs.python.org/3/",)
    assert second.files == () and second.docs_links == ()


def test_parse_ignores_fenced_blocks_and_flags_bad_headings():
    plan = parse_plan("```\n### C9 - inside\n```\n### Notes\n### C1 - a\n- role: x\n")
    assert [item.code for item in plan.items] == ["C1"]
    assert plan.bad_headings == ("Notes",)


def test_valid_plan_has_no_problems():
    assert check_plan(parse_plan(PLAN), Roles("implementer", "tester")) == []


def test_every_problem_is_reported_with_its_code():
    text = "### C1 - a\n- role: wizard\n- docs: see the wiki\n### C1 - b\n- role: tester\n- done-when: x\n- docs: không có\n"
    problems = [str(p) for p in check_plan(parse_plan(text), Roles("tester"))]
    assert any("C1: unknown role 'wizard'" in p for p in problems)
    assert any("C1: missing 'done-when'" in p for p in problems)
    assert any("duplicate item code" in p for p in problems)
    assert any("must be a link" in p for p in problems)
    assert any("needs a reason" in p for p in problems)


def test_empty_plan_and_bad_heading_are_problems():
    assert check_plan(parse_plan("nothing here"), Roles("a"))
    assert check_plan(parse_plan("### Foo\n"), Roles("a"))


def test_files_required_when_asked():
    plan = parse_plan("### C1 - a\n- role: tester\n- done-when: x\n- docs: https://e.example/\n")
    assert check_plan(plan, Roles("tester")) == []
    assert any("files" in str(p) for p in check_plan(plan, Roles("tester"), require_files=True))


def test_rules_add_problems():
    class Never:
        def problems(self, item):
            return [f"rule hit on {item.code}"]

    plan = parse_plan(PLAN)
    problems = check_plan(plan, Roles("implementer", "tester"), rules=[Never()])
    assert [str(p) for p in problems] == ["C1: rule hit on C1", "C2: rule hit on C2"]


def test_docs_problem_variants():
    assert docs_problem("không có - lý do") is None
    assert docs_problem("") is not None
    assert docs_problem(None) is not None


# ------------------------------------------------------------------ tier and layer


def _tiered(tier_line, layer_line=""):
    return f"### C1 - x\n- role: implementer\n{tier_line}{layer_line}- done-when: ok\n- docs: không có — internal\n"


def test_an_item_carries_its_tier_and_layer():
    from thanhtan.plan import parse_plan

    item = parse_plan(_tiered("- tier: FAST\n", "- layer: `Domain`\n")).items[0]
    assert (item.tier, item.layer) == ("fast", "domain")


def test_a_missing_tier_counts_as_deep():
    from thanhtan.constants import PlanTier
    from thanhtan.plan import parse_plan

    item = parse_plan(_tiered("")).items[0]
    assert item.tier is None and item.effective_tier == PlanTier.DEEP


def test_plan_check_refuses_an_unknown_tier_and_accepts_the_known_ones():
    from thanhtan.plan import check_plan, parse_plan

    class Roles:
        def roles(self):
            return {"implementer"}

    def found(text):
        return [str(p) for p in check_plan(parse_plan(text), Roles())]

    assert found(_tiered("- tier: fast\n")) == [] and found(_tiered("- tier: deep\n")) == [] and found(_tiered("")) == []
    assert any("C1" in p and "tier 'turbo'" in p for p in found(_tiered("- tier: turbo\n")))


def _plan_with_files(files):
    return parse_plan(f"### C1 - Big\n- role: implementer\n- files: {files}\n- done-when: `uv run pytest`\n- docs: không có — none\n")


def test_an_item_with_too_many_files_has_to_be_split():
    many = ", ".join(f"src/f{n}.py" for n in range(11))
    problems = check_plan(_plan_with_files(many), Roles("implementer"))
    assert [p.code for p in problems] == ["C1"] and "split" in problems[0].message


def test_an_item_at_the_limit_is_fine_and_a_folder_counts_once():
    ten = ", ".join(f"src/f{n}.py" for n in range(10))
    assert check_plan(_plan_with_files(ten), Roles("implementer")) == []
    assert check_plan(_plan_with_files("src/, tests/, docs/"), Roles("implementer")) == []


# ------------------------------------------------------------------ requirements of the confirm step covered by the plan


def _covering(*covers):
    items = "".join(
        f"### C{n} - Do {n}\n- role: implementer\n- files: f{n}.py\n- covers: {cover}\n- done-when: `uv run pytest`\n- docs: không có — none\n\n"
        for n, cover in enumerate(covers, 1)
    )
    return parse_plan(items)


def test_requirements_are_read_from_the_confirm_report():
    from thanhtan.plan import parse_requirements

    text = "# Confirmed\n\n## Yêu cầu\n- Y1: users can log in\n- Y2 - and log out\n* Y10: a long one\nY3 is mentioned in prose\n"
    assert parse_requirements(text) == ("Y1", "Y2", "Y10")


def test_an_item_carries_the_requirements_it_covers():
    plan = _covering("Y1, y2")
    assert plan.items[0].covers == ("Y1", "Y2")


def test_every_requirement_has_to_be_covered_and_every_cover_has_to_exist():
    problems = check_plan(_covering("Y1"), Roles("implementer"), requirements=("Y1", "Y2"))
    assert [str(p) for p in problems] == ["requirement Y2 is not covered by any plan item (add `covers: Y2` to the item that does it)"]
    problems = check_plan(_covering("Y1, Y9"), Roles("implementer"), requirements=("Y1",))
    assert [(p.code, "Y9" in p.message) for p in problems] == [("C1", True)]


def test_without_requirements_nothing_is_checked():
    assert check_plan(_covering("Y1"), Roles("implementer"), requirements=None) == []
    assert check_plan(_covering("Y1"), Roles("implementer"), requirements=()) == []
