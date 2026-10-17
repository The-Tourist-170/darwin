"""Agent-facing episodic memory: recall relevant context, store explicit facts."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from darwin.core.memory_client import get_memory_client

def _memory():
    return get_memory_client()


class RecallArgs(BaseModel):
    query: str = Field(min_length=1)


@tool(args_schema=RecallArgs)
def memory_recall(query: str) -> str:
    """Search long-term episodic memory for context relevant to the query."""
    results = _memory().recall(query)
    memories = [m.get("memory") for m in results if m.get("memory")]
    if not memories:
        return "no relevant memories yet"
    return "\n".join("- " + m for m in memories)


class SaveArgs(BaseModel):
    content: str = Field(min_length=1, description="Fact to remember verbatim")


@tool(args_schema=SaveArgs)
def memory_save(content: str) -> str:
    """Store an explicit fact in long-term memory so later sessions can recall it."""
    if not _memory().add(content, content).get("results", []):
        return "saved nothing (mem0 extracted no facts); rephrase and retry"
    return f"saved: {content[:80]}"
