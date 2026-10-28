import pytest

from agentflow.constants import ConventionPrefix, PlanRuleKind
from agentflow.convention_sources import load_decision_conventions
from agentflow.conventions import parse_conventions, render_conventions, validate_conventions
from agentflow.interfaces import PlanWideRule
from agentflow.plan import check_plan, parse_plan
from agentflow.plan_rules import LayerOrderRule

LAYERS = ("interface", "api", "infra", "service", "domain")


class Roles:
    def roles(self):
        return {"implementer"}


def item(code, layer, files="src/x.py"):
    layer_line = f"- layer: {layer}\n" if layer else ""
    return f"### {code} - {code} title\n- role: implementer\n{layer_line}- files: {files}\n- done-when: ok\n- docs: không có — internal\n\n"


def problems(text, rule=None):
    rule = rule or LayerOrderRule("PC-04", LAYERS)
    return [str(p) for p in check_plan(parse_plan(text), Roles(), wide_rules=[rule])]


def test_the_rule_implements_the_protocol():
    assert isinstance(LayerOrderRule("PC-04", LAYERS), PlanWideRule)


def test_layers_in_order_pass_even_when_each_layer_has_its_own_folder():
    text = item("C1", "interface", "src/interface/a.py") + item("C2", "api", "src/api/a.py") + item("C3", "domain", "src/domain/a.py")
    assert problems(text) == []


def test_a_later_layer_before_an_earlier_one_is_refused_across_the_whole_plan():
    text = item("C1", "domain", "src/domain/a.py") + item("C2", "interface", "src/interface/a.py")
    found = problems(text)
    assert len(found) == 1 and "C2" in found[0] and "C1" in found[0] and "PC-04" in found[0]


def test_the_same_layer_may_repeat_and_skipping_a_layer_is_fine():
    assert problems(item("C1", "api") + item("C2", "api") + item("C3", "domain")) == []


def test_every_item_needs_a_known_layer():
    found = problems(item("C1", None) + item("C2", "banana"))
    assert any("C1" in p and "missing 'layer'" in p for p in found)
    assert any("C2" in p and "banana" in p for p in found)


def test_without_a_scope_items_need_no_files():
    text = "### C1 - x\n- role: implementer\n- layer: api\n- done-when: ok\n- docs: không có — internal\n"
    assert problems(text) == []


def test_a_scope_limits_the_rule_to_items_inside_it():
    rule = LayerOrderRule("PC-04", LAYERS, ["src/**"])
    outside = item("C1", "domain", "docs/a.md") + item("C2", "interface", "docs/b.md")
    assert problems(outside, rule) == []
    inside = item("C1", "domain", "src/d.py") + item("C2", "interface", "src/i.py") + item("C3", None, "docs/c.md")
    found = problems(inside, rule)
    assert len(found) == 1 and "C2" in found[0]


def test_a_scoped_rule_needs_the_files_of_every_item():
    rule = LayerOrderRule("PC-04", LAYERS, ["src/**"])
    text = "### C1 - x\n- role: implementer\n- layer: api\n- done-when: ok\n- docs: không có — internal\n"
    assert any("C1" in p and "files" in p for p in problems(text, rule))


CONVENTION = """### PC-04 - Layers
- check: plan
- rule: layer-order
- layers: Interface, api , infra, service, domain
- scope: src/**, lib/**
- status: unconfirmed
- source: docs/arch.md:3
- description: Build layers in order.
"""


def test_a_convention_reads_and_writes_its_layers_and_scope():
    doc = parse_conventions(CONVENTION)
    assert validate_conventions(doc) == []
    convention = doc.conventions[0]
    assert convention.layer_names == LAYERS and convention.scope_globs == ("src/**", "lib/**")
    again = parse_conventions(render_conventions(doc))
    assert again.conventions[0].layer_names == LAYERS and again.conventions[0].scope_globs == ("src/**", "lib/**")


@pytest.mark.parametrize(
    "edit, message",
    [
        ("- layers: interface, api, infra, service, domain\n- layers: x\n", None),
        ("- layers: api\n", "at least two layers"),
        ("- layers: api, api\n", "twice"),
        ("", "at least two layers"),
        ("- layers: api, domain\n- scope:\n", None),
    ],
)
def test_layers_are_validated(edit, message):
    text = "### PC-04 - Layers\n- check: plan\n- rule: layer-order\n" + edit + "- source: s\n- description: d\n"
    found = validate_conventions(parse_conventions(text))
    if message is None:
        assert not any("at least two" in p or "twice" in p for p in found)
    else:
        assert any(message in p for p in found)


def test_layers_belong_to_the_layer_order_rule_only():
    text = "### PC-05 - Order\n- check: plan\n- rule: item-order\n- layers: a, b\n- source: s\n- description: d\n"
    assert any("layer-order" in p for p in validate_conventions(parse_conventions(text)))


def test_layer_order_is_a_known_plan_rule():
    assert PlanRuleKind.LAYER_ORDER == "layer-order"


def test_a_decision_answer_carries_layers_and_scope(tmp_path):
    from agentflow.convention_sources import write_answer
    from agentflow.constants import CheckKind

    (tmp_path / "decisions").mkdir()
    write_answer(tmp_path, "T-001", "Q1", "DC-01", "Layers in order", CheckKind.PLAN, "layer-order", None, "2026-01-01T00:00:00Z", "api, domain", "src/**")
    (convention,) = load_decision_conventions(tmp_path)
    assert convention.code.startswith(ConventionPrefix.DECISION) and convention.layer_names == ("api", "domain")
    assert convention.scope_globs == ("src/**",)
