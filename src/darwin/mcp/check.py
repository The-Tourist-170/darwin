"""Debug CLI: test MCP servers independently of the agent.

    python -m darwin.mcp.check                     # list servers and their tools
    python -m darwin.mcp.check time                # list tools of one server
    python -m darwin.mcp.check time get_current_time '{"timezone": "Asia/Kolkata"}'
"""

import argparse
import asyncio
import json

from darwin.mcp.adapters import to_langchain_tool
from darwin.mcp.client import MCPClient


async def run(server: str | None, tool: str | None, args: dict) -> None:
    client = MCPClient()
    try:
        connected = await client.connect_all()
        if not connected:
            print("no MCP servers connected")
            return

        if server and tool:
            print(await client.call_tool(server, tool, args))
            return

        for meta in client.tools():
            if server and meta["server"] != server:
                continue
            lc_tool = to_langchain_tool(client, meta)
            print(f"{lc_tool.name}: {lc_tool.description}")
    finally:
        await client.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(prog="darwin.mcp.check", description="Test an MCP server")
    parser.add_argument("server", nargs="?", help="Server name from mcp.json")
    parser.add_argument("tool", nargs="?", help="Tool name to call")
    parser.add_argument("args", nargs="?", default="{}", help="JSON args for the tool call")
    parsed = parser.parse_args()

    asyncio.run(run(parsed.server, parsed.tool, json.loads(parsed.args)))


if __name__ == "__main__":
    main()
