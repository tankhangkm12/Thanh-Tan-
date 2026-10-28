"""The plan and commit checks an extension's path rules and plan rules turn into."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from agentflow.extension import Extension, PathRule, PlanRuleDecl
from agentflow.globs import glob_regex
from agentflow.placeholders import expand_text
from agentflow.plan import PlanItem

Lookup = Callable[[str], Any]
CURRENT_DIR_PREFIX = "./"
BACKSLASH = "\\"
SLASH = "/"
ANY_BELOW = "/**"


def normalize(path: str) -> str:
    path = path.strip().replace(BACKSLASH, SLASH)
    while path.startswith(CURRENT_DIR_PREFIX):
        path = path[len(CURRENT_DIR_PREFIX) :]
    return path


@dataclass(frozen=True)
class PathPattern:
    regex: re.Pattern[str]
    # The literal folder the pattern starts with (``db/secure`` for ``db/secure/**``).
    base: str

    def match(self, path: str) -> bool:
        return bool(self.regex.match(path))


def pattern_for(template: str, lookup: Lookup) -> PathPattern:
    text = normalize(expand_text(template, lookup))
    literal = re.split(r"[*?]", text, maxsplit=1)[0].rstrip(SLASH)
    return PathPattern(glob_regex(text), literal)


def entry_touches(entry: str, pattern: PathPattern) -> bool:
    """Whether a plan ``files`` entry (a file, a folder or a glob) can fall under ``pattern``."""
    entry = normalize(entry)
    folder = entry.rstrip(SLASH)
    if pattern.match(entry) or pattern.match(folder + SLASH + "x") or pattern.match(folder + ANY_BELOW):
        return True
    # A broader folder than the guarded one (``db/`` when ``db/secure/**`` is guarded) can reach into it.
    return bool(pattern.base) and (pattern.base == folder or pattern.base.startswith(folder + SLASH))


def file_listed(path: str, entries: Sequence[str]) -> bool:
    """Whether a staged ``path`` is covered by an item's ``files`` entries."""
    path = normalize(path)
    for entry in entries:
        entry = normalize(entry)
        if glob_regex(entry).match(path) or path.startswith(entry.rstrip(SLASH) + SLASH):
            return True
    return False


class ExtensionRules:
    """Plan rules (``PlanRule``) and commit rules from the registered extensions."""

    def __init__(self, extensions: Sequence[Extension], lookup: Lookup) -> None:
        self.path_rules: list[PathRule] = [r for e in extensions for r in e.path_rules]
        self.plan_rules: list[PlanRuleDecl] = [r for e in extensions for r in e.plan_rules]
        self.lookup = lookup

    @property
    def requires_files(self) -> bool:
        """Path-based rules only work if every item says which paths it changes."""
        return bool(self.path_rules or self.plan_rules)

    # -- plan items

    def problems(self, item: PlanItem) -> list[str]:
        found: list[str] = []
        files = item.files or ()
        for rule in self.path_rules:
            patterns = [pattern_for(p, self.lookup) for p in rule.paths]
            touched = [f for f in files if any(entry_touches(f, p) for p in patterns)]
            if touched and item.role not in rule.roles:
                found.append(
                    f"role '{item.role}' may not change {', '.join(touched)}: only {', '.join(rule.roles)} may ({rule.id})"
                )
        for rule in self.plan_rules:
            patterns = [pattern_for(p, self.lookup) for p in rule.when_paths]
            if not any(entry_touches(f, p) for f in files for p in patterns):
                continue
            done_when = item.done_when or ""
            for needed in rule.done_when_contains:
                expected = expand_text(needed, self.lookup)
                if expected not in done_when:
                    found.append(f"done-when must contain `{expected}` ({rule.id})")
        return found

    # -- commits

    def commit_problems(self, item: PlanItem | None, staged: Sequence[str]) -> list[str]:
        found: list[str] = []
        for rule in self.path_rules:
            patterns = [pattern_for(p, self.lookup) for p in rule.paths]
            guarded = [path for path in staged if any(p.match(normalize(path)) for p in patterns)]
            if guarded and item is None:
                found.append(f"{', '.join(guarded)} may only be committed for a plan item of {'/'.join(rule.roles)} (use --item) ({rule.id})")
            elif guarded and item is not None and item.role not in rule.roles:
                found.append(
                    f"item {item.code} has role '{item.role}', which may not commit {', '.join(guarded)}: only {', '.join(rule.roles)} may ({rule.id})"
                )
        if item is not None and self.requires_files:
            entries = item.files or ()
            found += [f"{path} is not in the files of item {item.code}" for path in staged if not file_listed(path, entries)]
        return found
