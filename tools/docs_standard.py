"""Check the plugin documentation standard (docs/architecture.md, "Chuẩn tài liệu của plugin").

Every family that has a core needs one USAGE.md, either `families/<family>/USAGE.md` or `families/<family>/core/USAGE.md`
(not both), with a `## Khuôn yêu cầu task` section holding a code
block, a `## Dùng cùng <core>` section in the README of each child plugin, and a link to its USAGE.md in the root
README. Relative links in the files of the standard must point at something that exists.

    uv run tools/docs_standard.py [--repo PATH]
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

FAMILIES_DIR = "families"
CORE_DIR = "core"
WORKFLOW_FILE = "workflow.yaml"
ROOT_README = "README.md"
README_FILE = "README.md"
USAGE_FILE = "USAGE.md"
CLAUDE_MANIFEST = ".claude-plugin/plugin.json"
ANTIGRAVITY_MANIFEST = "plugin.json"
TEMPLATE_HEADING = "## Khuôn yêu cầu task"
CHILD_HEADING_PREFIX = "## Dùng cùng "
SECTION_PREFIX = "## "
FENCE = "```"
FAMILY_LINK = "{families}/{family}/{usage}"
ENCODING = "utf-8"

FENCED_BLOCK = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class Rule(Enum):
    MISSING_USAGE = "missing-usage"
    MISSING_TEMPLATE = "missing-template"
    MISSING_CHILD_SECTION = "missing-child-section"
    MISSING_ROOT_LINK = "missing-root-link"
    BROKEN_LINK = "broken-link"
    DUPLICATE_USAGE = "duplicate-usage"


@dataclass(frozen=True)
class Finding:
    rule: Rule
    file: str  # path from the repository root, with forward slashes
    message: str

    def __str__(self) -> str:
        return f"{self.file}: [{self.rule.value}] {self.message}"


def relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def is_plugin(directory: Path) -> bool:
    return (directory / CLAUDE_MANIFEST).is_file() or (directory / ANTIGRAVITY_MANIFEST).is_file()


def core_name(core: Path) -> str:
    manifest = core / CLAUDE_MANIFEST
    if manifest.is_file():
        name = json.loads(manifest.read_text(encoding=ENCODING)).get("name")
        if name:
            return str(name)
    return core.parent.name + "-" + CORE_DIR


def family_dirs(repo: Path) -> list[Path]:
    root = repo / FAMILIES_DIR
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []


def usage_files(family: Path) -> list[Path]:
    """The USAGE.md files of a family: in its core and/or at the family level."""
    return [path for path in (family / USAGE_FILE, family / CORE_DIR / USAGE_FILE) if path.is_file()]


def usage_target(family: Path) -> str:
    """Path of the family's USAGE.md from the family folder (the core's one when the family has none yet)."""
    found = usage_files(family)
    return found[0].relative_to(family).as_posix() if found else USAGE_FILE


def has_core(family: Path) -> bool:
    """A family is checked when it has a USAGE.md; a core with a workflow.yaml must have one too."""
    return bool(usage_files(family)) or (family / CORE_DIR / WORKFLOW_FILE).is_file()


def core_families(repo: Path) -> dict[str, str]:
    """Family name -> name of its core plugin, for the families that have a core (the ones the standard applies to)."""
    return {family.name: core_name(family / CORE_DIR) for family in family_dirs(repo) if has_core(family)}


def children(family: Path) -> list[Path]:
    return sorted(path for path in family.iterdir() if path.is_dir() and path.name != CORE_DIR and is_plugin(path))


def read(path: Path) -> str:
    return path.read_text(encoding=ENCODING)


def has_heading(text: str, heading: str) -> bool:
    return any(line.strip() == heading for line in text.splitlines())


def section_has_code_block(text: str, heading: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        for following in lines[index + 1 :]:
            if following.startswith(SECTION_PREFIX):
                break
            if following.lstrip().startswith(FENCE):
                return True
    return False


def check_usage(repo: Path, family: Path) -> list[Finding]:
    found = usage_files(family)
    if len(found) > 1:
        names = " and ".join(relative(repo, path) for path in found)
        return [Finding(Rule.DUPLICATE_USAGE, relative(repo, found[0]), f"the family has two {USAGE_FILE} files: {names}")]
    usage = found[0] if found else family / USAGE_FILE
    name = relative(repo, usage)
    if not found:
        return [Finding(Rule.MISSING_USAGE, name, f"the family has a core but no {USAGE_FILE}")]
    text = read(usage)
    if not has_heading(text, TEMPLATE_HEADING):
        return [Finding(Rule.MISSING_TEMPLATE, name, f'no "{TEMPLATE_HEADING}" section')]
    if not section_has_code_block(text, TEMPLATE_HEADING):
        return [Finding(Rule.MISSING_TEMPLATE, name, f'the "{TEMPLATE_HEADING}" section has no code block')]
    return []


def check_children(repo: Path, family: Path, core: str) -> list[Finding]:
    heading = CHILD_HEADING_PREFIX + core
    findings = []
    for child in children(family):
        readme = child / README_FILE
        name = relative(repo, readme)
        if not readme.is_file():
            findings.append(Finding(Rule.MISSING_CHILD_SECTION, name, f'no {README_FILE}, so no "{heading}" section'))
        elif not has_heading(read(readme), heading):
            findings.append(Finding(Rule.MISSING_CHILD_SECTION, name, f'no "{heading}" section'))
    return findings


def check_root_links(repo: Path, families: dict[str, str]) -> list[Finding]:
    readme = repo / ROOT_README
    name = relative(repo, readme)
    text = read(readme) if readme.is_file() else ""
    targets = {link_path(target) for target in LINK.findall(text)}
    findings = []
    for family in families:
        wanted = FAMILY_LINK.format(families=FAMILIES_DIR, family=family, usage=usage_target(repo / FAMILIES_DIR / family))
        if wanted not in targets:
            findings.append(Finding(Rule.MISSING_ROOT_LINK, name, f"no link to {wanted}"))
    return findings


def link_path(target: str) -> str:
    return target.split("#", 1)[0].split("?", 1)[0]


def files_with_links(repo: Path) -> list[Path]:
    files = [repo / ROOT_README]
    for family in family_dirs(repo):
        files += [family / README_FILE, *usage_files(family)]
        files += [path / README_FILE for path in sorted(family.iterdir()) if path.is_dir() and is_plugin(path)]
    return [path for path in files if path.is_file()]


def check_links(repo: Path) -> list[Finding]:
    findings = []
    for path in files_with_links(repo):
        text = INLINE_CODE.sub("", FENCED_BLOCK.sub("", read(path)))
        for target in LINK.findall(text):
            if SCHEME.match(target) or target.startswith(("#", "/")):
                continue
            file_part = link_path(target)
            if file_part and not (path.parent / file_part).exists():
                findings.append(Finding(Rule.BROKEN_LINK, relative(repo, path), f"link target not found: {target}"))
    return findings


def check(repo: Path) -> list[Finding]:
    families = core_families(repo)
    findings: list[Finding] = []
    for family in family_dirs(repo):
        if family.name in families:
            findings += check_usage(repo, family)
            findings += check_children(repo, family, families[family.name])
    findings += check_root_links(repo, families)
    findings += check_links(repo)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the plugin documentation standard.")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    findings = check(args.repo)
    for finding in findings:
        print(finding)
    if findings:
        print(f"{len(findings)} problem(s) against the documentation standard")
        return 1
    print("documentation standard ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
