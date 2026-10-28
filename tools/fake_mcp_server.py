# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""A tiny MCP server with one tool that reads and one that writes, for trying `agentflow role grant`.

    uv run tools/fake_mcp_server.py                        # speaks MCP on stdio
    uv run tools/fake_mcp_server.py --notes-file notes.txt # also appends every written note to that file

The notes stay in memory unless a file is given. The smoke test lists the tools over MCP and grants roles tools by their
real names; the real-session trial reads the file to see that an agent really called the tool.
"""

import argparse
from pathlib import Path

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

SERVER_NAME = "fakesrv"
READ_TOOL = "get_note"
WRITE_TOOL = "write_note"
TOOL_NAMES = (READ_TOOL, WRITE_TOOL)
NOTES: dict[str, str] = {}
NEWLINE = "\n"


def build_server(notes_file: Path | None = None) -> MCPServer:
    server = MCPServer(SERVER_NAME, instructions="Notes kept in memory, for trying agentflow role grant.")

    def get_note(name: str) -> str:
        return NOTES.get(name, "")

    def write_note(name: str, text: str) -> str:
        NOTES[name] = text
        if notes_file is not None:
            with notes_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{name}: {text}{NEWLINE}")
        return "saved"

    server.tool(name=READ_TOOL, description="Read a note.", annotations=ToolAnnotations(readOnlyHint=True))(get_note)
    server.tool(name=WRITE_TOOL, description="Write a note.", annotations=ToolAnnotations(readOnlyHint=False))(write_note)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes-file", type=Path, default=None)
    build_server(parser.parse_args().notes_file).run("stdio")
