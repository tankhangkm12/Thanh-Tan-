"""Call the tools of an thanhtan MCP server from a test (the same helper test_mcp_server.py uses, shared)."""

import asyncio

from mcp import Client


def call(server, name, **arguments):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def tool_list(server):
    async def run():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())
