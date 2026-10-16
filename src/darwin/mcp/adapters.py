"""Bridge MCP tools into LangChain tools (replaces an adapter library)."""

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

from darwin.mcp.client import MCPClient

JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _json_type(spec: dict) -> type:
    kind = spec.get("type")
    if isinstance(kind, list):  # e.g. ["string", "null"]
        kind = next((k for k in kind if k != "null"), "string")
    return JSON_TYPES.get(kind, str)


def _args_model(tool_name: str, schema: dict):
    """Build a Pydantic args model from an MCP JSON schema."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {
        key: (_json_type(spec), ... if key in required else None)
        for key, spec in properties.items()
    }
    return create_model(f"{tool_name}_args", **fields)


def to_langchain_tool(client: MCPClient, meta: dict) -> StructuredTool:
    """Wrap one MCP tool as a LangChain tool named {server}__{tool}."""
    server, tool = meta["server"], meta["name"]

    async def _call(**kwargs):
        return await client.call_tool(server, tool, kwargs)

    return StructuredTool.from_function(
        coroutine=_call,
        name=f"{server}__{tool}",
        description=meta["description"] or f"{tool} (MCP server: {server})",
        args_schema=_args_model(tool, meta["input_schema"]),
    )
