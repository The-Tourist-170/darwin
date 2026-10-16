"""MCP client: connects Darwin to external MCP servers over stdio.

Modelled on the learning client in ~/Dev/Python/14_MCP_Client:
StdioServerParameters + stdio_client + ClientSession, managed by an AsyncExitStack.
"""

import json
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from darwin.core.config import config


ENV_REF = re.compile(r"\$\{(\w+)\}")


def _expand_env(env: dict) -> dict:
    """Substitute ${VAR} references from the environment and keep PATH etc. intact."""
    resolved = {key: ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), str(value)) for key, value in env.items()}
    return {**os.environ, **resolved}


def _resolve_server_command(server_script_path: str) -> str:
    """Pick the interpreter for a .py server script (their original logic).

    Precedence: MCP_SERVER_COMMAND env var -> the server project's own
    .venv interpreter -> the current interpreter.
    """
    env_command = os.getenv("MCP_SERVER_COMMAND")
    if env_command:
        return env_command

    venv_python = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    script_path = Path(server_script_path).resolve()
    for parent in script_path.parents:
        candidate = parent / ".venv" / venv_python
        if candidate.exists():
            return str(candidate)

    return sys.executable


class MCPClient:
    def __init__(self) -> None:
        self.exit_stack = AsyncExitStack()
        self.sessions: dict[str, ClientSession] = {}
        self.raw_tools: dict[str, list] = {}
        log_path = Path.home() / ".darwin" / "mcp.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.errlog = open(log_path, "a")

    async def connect(self, name: str, server: dict) -> None:
        """Connect to one server and cache its tool list."""
        command = config.MCP_SERVER_COMMAND or server["command"]
        args = list(server.get("args", []))
        if command.endswith(".py"):
            args = [command, *args]
            command = _resolve_server_command(command)

        env = _expand_env(server["env"]) if server.get("env") else None
        params = StdioServerParameters(command=command, args=args, env=env)
        # Server stderr goes to ~/.darwin/mcp.log so it never clutters the chat.
        read, write = await self.exit_stack.enter_async_context(stdio_client(params, errlog=self.errlog))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self.sessions[name] = session
        self.raw_tools[name] = (await session.list_tools()).tools

    async def connect_all(self) -> list[str]:
        """Connect every enabled server; a failing server is skipped, not fatal."""
        servers = json.loads(Path(config.MCP_CONFIG_PATH).read_text())["mcpServers"]
        connected, disabled = [], []
        for name, server in servers.items():
            if server.get("disabled"):
                disabled.append(name)
                continue
            try:
                await self.connect(name, server)
                connected.append(name)
            except Exception as exc:
                print(f"[mcp] {name} failed to start: {exc}")
        if disabled:
            print(f"[mcp] disabled (no credentials yet): {disabled}")
        return connected

    def tools(self) -> list[dict]:
        """Flat view of every MCP tool: server, name, description, input_schema."""
        return [
            {
                "server": server,
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": getattr(tool, "input_schema", None) or {},
            }
            for server, tools in self.raw_tools.items()
            for tool in tools
        ]

    async def call_tool(self, server: str, tool: str, args: dict) -> str:
        """Call a tool and return its text content."""
        result = await self.sessions[server].call_tool(tool, args)
        return "\n".join(
            block.text for block in result.content if getattr(block, "type", None) == "text"
        )

    async def cleanup(self) -> None:
        await self.exit_stack.aclose()
        self.errlog.close()
