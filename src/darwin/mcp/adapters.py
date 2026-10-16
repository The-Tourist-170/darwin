"""Bridge MCP tools into LangChain tools (replaces an adapter library)."""

from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from darwin.mcp.client import MCPClient

JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _json_type(spec: dict) -> Any:
    if "const" in spec:
        return Literal[tuple([spec["const"]])]
    if spec.get("enum"):
        return Literal[tuple(spec["enum"])]
    kind = spec.get("type")
    if isinstance(kind, list):  # e.g. ["string", "null"]
        kind = next((k for k in kind if k != "null"), "string")
    return JSON_TYPES.get(kind, str)


def _args_model(tool_name: str, schema: dict):
    """Build a Pydantic args model from an MCP JSON schema (enums and defaults preserved)."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {
        key: (
            _json_type(spec),
            Field(... if key in required else spec.get("default"), description=spec.get("description", "")),
        )
        for key, spec in properties.items()
    }
    return create_model(f"{tool_name}_args", **fields)


def to_langchain_tool(client: MCPClient, meta: dict) -> StructuredTool:
    """Wrap one MCP tool as a LangChain tool named {server}__{tool}."""
    server, tool = meta["server"], meta["name"]

    async def _call(**kwargs):
        # Omit unset optional args: MCP servers distinguish "absent" from null,
        # and our generated model gives every optional field a None default.
        args = {key: value for key, value in kwargs.items() if value is not None}
        return await client.call_tool(server, tool, args)

    return StructuredTool.from_function(
        coroutine=_call,
        name=f"{server}__{tool}",
        description=meta["description"] or f"{tool} (MCP server: {server})",
        args_schema=_args_model(tool, meta["input_schema"]),
    )
