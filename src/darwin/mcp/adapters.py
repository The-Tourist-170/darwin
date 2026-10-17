"""Bridge MCP tools into LangChain tools (replaces an adapter library)."""

from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, create_model

from darwin.mcp.client import MCPClient

JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
# Names that clash with BaseModel attributes raise a pydantic warning; expose them by alias.
RESERVED_NAMES = {"schema", "copy", "dict", "json", "construct", "validate", "fields", "model_config"}


def _json_type(spec: dict) -> Any:
    if "const" in spec:
        return Literal[tuple([spec["const"]])]
    if spec.get("enum"):
        return Literal[tuple(spec["enum"])]
    kind = spec.get("type")
    if isinstance(kind, list):  # e.g. ["string", "null"]
        kind = next((k for k in kind if k != "null"), "string")
    return JSON_TYPES.get(kind, str)


def _args_model(tool_name: str, schema: dict) -> tuple[type[BaseModel], dict[str, str]]:
    """Build a Pydantic args model from an MCP JSON schema (enums and defaults preserved).

    Returns the model plus a {field_name: upstream_name} map for fields renamed to dodge
    BaseModel attribute clashes (e.g. Firecrawl's "schema").
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    aliases: dict[str, str] = {}
    for key, spec in properties.items():
        default = ... if key in required else spec.get("default")
        description = spec.get("description", "")
        if key in RESERVED_NAMES:
            field_name = f"{key}_"
            aliases[field_name] = key
            fields[field_name] = (_json_type(spec), Field(default, alias=key, description=description))
        else:
            fields[key] = (_json_type(spec), Field(default, description=description))
    model = create_model(f"{tool_name}_args", __config__=ConfigDict(populate_by_name=True), **fields)
    return model, aliases


def to_langchain_tool(client: MCPClient, meta: dict) -> StructuredTool:
    """Wrap one MCP tool as a LangChain tool named {server}__{tool}."""
    server, tool = meta["server"], meta["name"]
    args_model, aliases = _args_model(tool, meta["input_schema"])

    async def _call(**kwargs):
        # Omit unset optional args: MCP servers distinguish "absent" from null,
        # and our generated model gives every optional field a None default.
        args = {
            aliases.get(key, key): value for key, value in kwargs.items() if value is not None
        }
        return await client.call_tool(server, tool, args)

    return StructuredTool.from_function(
        coroutine=_call,
        name=f"{server}__{tool}",
        description=meta["description"] or f"{tool} (MCP server: {server})",
        args_schema=args_model,
    )
