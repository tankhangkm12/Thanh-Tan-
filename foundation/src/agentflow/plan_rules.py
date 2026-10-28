"""Plan rules that conventions switch on (``check: plan``)."""

from collections.abc import Sequence
from typing import Any

from agentflow.constants import PlanItemKind
from agentflow.globs import select_files


class ItemOrderRule:
    """Interfaces before implementations: an ``implement`` item may not come before an ``interface`` item of the same file.

    While the rule is on, every item says what it is (``kind:``), and interface and implement items list their files.
    """

    def __init__(self, convention_code: str) -> None:
        self.code = convention_code

    def problems(self, items: Sequence[Any]) -> list[tuple[str | None, str]]:
        found: list[tuple[str | None, str]] = []
        for item in items:
            if item.kind is None:
                found.append((item.code, f"missing 'kind' ({', '.join(PlanItemKind)}), which {self.code} needs"))
            elif item.kind in {PlanItemKind.INTERFACE, PlanItemKind.IMPLEMENT} and item.files is None:
                found.append((item.code, f"missing 'files': {self.code} orders {item.kind} items by the files they touch"))
        for index, item in enumerate(items):
            if item.kind != PlanItemKind.IMPLEMENT:
                continue
            for later in items[index + 1 :]:
                shared = sorted(set(item.files or ()) & set(later.files or ()))
                if later.kind == PlanItemKind.INTERFACE and shared:
                    found.append(
                        (item.code, f"implements {', '.join(shared)} before its interface item {later.code} ({self.code}): put {later.code} first")
                    )
        return found


class MaxPlanItemsRule:
    """A small task keeps its plan small: at most ``limit`` items."""

    def __init__(self, limit: int, size: str) -> None:
        self.limit = limit
        self.size = size

    def problems(self, items: Sequence[Any]) -> list[tuple[str | None, str]]:
        if len(items) <= self.limit:
            return []
        return [(None, f"the plan has {len(items)} items; a {self.size} task allows at most {self.limit}: split the work into another task, or start this one as a larger size")]


class LayerOrderRule:
    """Layers in order: an item of a later layer may not stand before an item of an earlier layer.

    The layers come from the convention (``layers: interface, api, infra, service, domain``). By default the rule covers
    the whole plan; with ``scope`` globs it covers the items whose files match one of them. Items in the rule's reach
    say which layer they belong to (``layer:``).
    """

    def __init__(self, convention_code: str, layers: Sequence[str], scope: Sequence[str] = ()) -> None:
        self.code = convention_code
        self.layers = tuple(layers)
        self.scope = tuple(scope)

    def problems(self, items: Sequence[Any]) -> list[tuple[str | None, str]]:
        found: list[tuple[str | None, str]] = []
        covered = []
        for item in items:
            if self.scope and item.files is None:
                found.append((item.code, f"missing 'files': {self.code} is limited to {', '.join(self.scope)}, so it needs the files an item changes"))
            elif not self.scope or select_files(item.files or (), self.scope):
                covered.append(item)
        latest: Any = None
        for item in covered:
            if item.layer is None:
                found.append((item.code, f"missing 'layer' ({', '.join(self.layers)}), which {self.code} needs"))
            elif item.layer not in self.layers:
                found.append((item.code, f"unknown layer '{item.layer}' ({self.code} has: {', '.join(self.layers)})"))
            else:
                if latest is not None and self.layers.index(item.layer) < self.layers.index(latest.layer):
                    found.append(
                        (item.code, f"layer '{item.layer}' comes after {latest.code} of layer '{latest.layer}' ({self.code}): put {item.code} first")
                    )
                if latest is None or self.layers.index(item.layer) > self.layers.index(latest.layer):
                    latest = item
        return found
