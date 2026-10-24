"""The hooks dev-core declares must call `agentflow hook` with arguments the CLI accepts."""

import json
import shlex
from pathlib import Path

import pytest

from agentflow.cli import build_parser
from agentflow.constants import MCP_SERVER_NAME, PACKAGE_NAME, CliKind, Command, HookEvent, ToolName

CORE = Path(__file__).resolve().parents[2] / "families" / "software-dev" / "core"
CLAUDE_HOOKS = CORE / "hooks" / "hooks.json"
ANTIGRAVITY_HOOKS = CORE / "hooks.json"

pytestmark = pytest.mark.skipif(not CORE.is_dir(), reason="plugin sources are not next to foundation/")


def claude_argvs() -> list[list[str]]:
    data = json.loads(CLAUDE_HOOKS.read_text(encoding="utf-8"))
    return [
        [hook["command"], *hook["args"]]
        for groups in data["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]


def antigravity_argvs() -> list[list[str]]:
    data = json.loads(ANTIGRAVITY_HOOKS.read_text(encoding="utf-8"))
    argvs = []
    for events in data.values():
        for handlers in events.values():
            for handler in handlers:
                nested = handler.get("hooks", [handler])
                argvs += [shlex.split(item["command"]) for item in nested]
    return argvs


@pytest.mark.parametrize(("argvs", "cli"), [(claude_argvs, CliKind.CLAUDE), (antigravity_argvs, CliKind.ANTIGRAVITY)])
def test_every_declared_hook_is_a_valid_agentflow_call(argvs, cli):
    calls = argvs()
    parser = build_parser()
    seen = set()
    for argv in calls:
        assert argv[0] == PACKAGE_NAME
        args = parser.parse_args(argv[1:])
        assert args.command == Command.HOOK and args.cli is cli
        seen.add(args.event)
    assert seen == set(HookEvent)


def test_claude_pre_tool_matcher_covers_the_shell_and_file_tools():
    data = json.loads(CLAUDE_HOOKS.read_text(encoding="utf-8"))
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit"


def test_antigravity_pre_tool_matcher_covers_the_shell_and_file_tools():
    data = json.loads(ANTIGRAVITY_HOOKS.read_text(encoding="utf-8"))
    assert data["agentflow"]["PreToolUse"][0]["matcher"] == "run_command|write_to_file|replace_file_content|multi_replace_file_content"


# ---------------------------------------------------------------- MCP server


def test_both_clis_start_the_same_agentflow_mcp_server():
    for name in (".mcp.json", "mcp_config.json"):
        data = json.loads((CORE / name).read_text(encoding="utf-8"))
        assert data == {"mcpServers": {MCP_SERVER_NAME: {"command": "agentflow", "args": ["mcp", "serve"]}}}, name


def test_the_agent_builder_names_exactly_the_tools_the_server_offers():
    import importlib.util

    spec = importlib.util.spec_from_file_location("plugin_build", CORE.parents[2] / "tools" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {name for name in module.WORKSPACE_TOOL_NAMES + module.PROJECT_TOOL_NAMES + module.DIAGNOSE_TOOL_NAMES} == {str(name) for name in ToolName}
    assert module.MCP_SERVER_PREFIX == f"mcp__plugin_dev-core_{MCP_SERVER_NAME}__"
