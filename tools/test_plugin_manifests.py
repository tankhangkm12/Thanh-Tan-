"""The two manifests of each plugin agree, and the Antigravity one carries what the Antigravity marketplace lists.

Claude Code reads `.claude-plugin/plugin.json`; Antigravity reads `plugin.json` at the plugin root. The Antigravity
marketplace skips a plugin without a valid `version` and shows `displayName`, `author`, `license` and `keywords` on its
card, so those are required here; `version` must follow the Claude Code one, which `docs/release.md` bumps.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/tankhangkm12/Thanh-Tan-"
LICENSE = "MIT"
PLUGINS = sorted(path.parent.parent for path in REPO.glob("families/*/*/.claude-plugin/plugin.json"))
MARKETPLACE_FIELDS = {"$schema", "name", "displayName", "logo", "version", "description", "author", "license", "homepage", "repository", "keywords"}
# Claude Code's default file names; `agy plugin validate --strict` fails on them ("never loaded"), so Claude Code reads
# its hooks and MCP servers from claude/, named in `.claude-plugin/plugin.json`.
ANTIGRAVITY_WARNS_ON = (".mcp.json", "hooks/hooks.json")
CLAUDE_PATH_KEYS = ("hooks", "mcpServers", "icon")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def manifests(plugin: Path) -> tuple[dict, dict]:
    claude = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    antigravity = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    return claude, antigravity


def test_every_plugin_of_the_marketplace_is_covered():
    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    listed = {(REPO / entry["source"]).resolve() for entry in marketplace["plugins"]}
    assert listed == {plugin.resolve() for plugin in PLUGINS}


def test_the_repository_has_the_license_the_manifests_name():
    assert (REPO / "LICENSE").read_text(encoding="utf-8").startswith(f"{LICENSE} License")


@pytest.mark.parametrize("plugin", PLUGINS, ids=lambda p: p.name)
def test_both_manifests_agree(plugin):
    claude, antigravity = manifests(plugin)
    for key in ("name", "version", "description", "author", "license"):
        assert antigravity[key] == claude[key], key


@pytest.mark.parametrize("plugin", PLUGINS, ids=lambda p: p.name)
def test_the_antigravity_manifest_has_what_the_marketplace_lists(plugin):
    _, antigravity = manifests(plugin)
    assert MARKETPLACE_FIELDS <= set(antigravity)
    assert SEMVER.match(antigravity["version"])
    assert antigravity["license"] == LICENSE
    assert antigravity["repository"] == REPO_URL
    assert antigravity["homepage"] == f"{REPO_URL}/tree/develop/{plugin.relative_to(REPO).as_posix()}"
    assert antigravity["displayName"].strip() and antigravity["keywords"]
    assert all(isinstance(prompt, str) and prompt for prompt in antigravity.get("suggestedPrompts", []))


@pytest.mark.parametrize("plugin", PLUGINS, ids=lambda p: p.name)
def test_no_claude_code_file_makes_the_strict_antigravity_check_fail(plugin):
    for name in ANTIGRAVITY_WARNS_ON:
        assert not (plugin / name).exists(), name


@pytest.mark.parametrize("plugin", PLUGINS, ids=lambda p: p.name)
def test_the_files_the_manifests_name_exist(plugin):
    claude, antigravity = manifests(plugin)
    for key in CLAUDE_PATH_KEYS:
        if key in claude:
            assert (plugin / claude[key]).is_file(), key
    assert (plugin / antigravity["logo"]).is_file()
    assert antigravity["logo"].endswith((".png", ".svg", ".jpg", ".jpeg", ".webp"))
