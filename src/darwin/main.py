"""Darwin CLI: async chat loop with MCP tools, memory and HITL approval."""

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from darwin.core.config import config
from darwin.core.llm import get_llm
from darwin.core.memory_client import MemoryClient
from darwin.core.orchestrator import build_graph
from darwin.mcp.adapters import to_langchain_tool
from darwin.mcp.client import MCPClient
from darwin.tools import ALL_TOOLS
from darwin.tools.registry import index_tools


async def _ask(prompt: str) -> str | None:
    """Read a line from stdin; None on EOF (e.g. piped input ran out)."""
    try:
        return (await asyncio.to_thread(input, prompt)).strip()
    except EOFError:
        return None


def _clip(text: str, limit: int = 240) -> str:
    flat = " ".join(str(text).split())
    return flat[:limit] + ("…" if len(flat) > limit else "")


def _trace(message) -> None:
    """Print tool activity as concise one-liners."""
    for call in getattr(message, "tool_calls", None) or []:
        print(f"  -> {call['name']} {_clip(json.dumps(call['args'], ensure_ascii=False))}")
    if isinstance(message, ToolMessage):
        print(f"  <- {getattr(message, 'name', 'tool')}: {_clip(message.content)}")


async def _ask_escalation(payload: dict) -> dict:
    """Render the JIT authorization prompt and return the resume payload."""
    targets = payload.get("targets") or []
    mode = payload.get("mode", "read-only")
    print(f"\n  !! out-of-workspace access: {payload.get('tool')}")
    for target in targets:
        print(f"     target : {target}  ({mode})")
    if payload.get("intent"):
        print(f"     intent : {_clip(payload['intent'], 160)}")
    print("     [1] allow once   [2] allow for session   [3] deny")
    choice = await _ask("     choice: ")
    if choice == "1":
        return {"approved": True, "scope": "once"}
    if choice == "2":
        return {"approved": True, "scope": "session"}
    print("     denied")
    return {"approved": False}


async def _settle(graph, thread_config: dict) -> None:
    """Discard interrupts left pending by an earlier interrupted run.

    Without this, a thread paused at an unanswered approval hijacks the next turn:
    the graph resumes the stale task and the new user message is never processed.
    """
    while True:
        state = await graph.aget_state(thread_config)
        if not (state.tasks and state.tasks[0].interrupts):
            return
        payload = state.tasks[0].interrupts[0].value
        resume = {"approved": False} if isinstance(payload, dict) else False
        print("  [discarded a pending approval from an interrupted earlier turn]")
        await graph.ainvoke(Command(resume=resume), thread_config)


async def _run(graph, payload: dict, thread_config: dict) -> dict:
    """Stream one turn: trace tool activity, gate scope and mutations on approval."""
    while True:
        interrupted = False
        async for chunk in graph.astream(payload, thread_config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupted = True
                    request = update[0].value
                    if isinstance(request, dict) and request.get("type") == "escalation":
                        payload = Command(resume=await _ask_escalation(request))
                    else:
                        calls = ", ".join(c["name"] for c in request)
                        print(f"  !! approval required: {calls}")
                        answer = await _ask("     approve? (y/n): ")
                        payload = Command(resume=(answer or "n").lower() == "y")
                    break
                for message in (update or {}).get("messages", []):
                    _trace(message)
        if not interrupted:
            break
    state = await graph.aget_state(thread_config)
    return {"messages": list(state.values["messages"])}


async def _chat(graph, memory: MemoryClient) -> None:
    thread = {"id": "default"}
    print("Darwin — type 'exit' to quit ('/new' starts a fresh session).")
    while True:
        user_input = await _ask("\nyou > ")
        if user_input is None or user_input.lower() in {"exit", "quit"}:
            break
        if user_input.lower() == "/new":
            thread["id"] = f"session-{int(asyncio.get_event_loop().time())}"
            print(f"  [new session: {thread['id']}]")
            continue

        try:
            memories = [m["memory"] for m in memory.recall(user_input)]
        except Exception:
            memories = []
        context = f"\n\nRelevant long-term memories:\n{json.dumps(memories)}" if memories else ""
        thread_config = {"configurable": {"thread_id": thread["id"]}}
        await _settle(graph, thread_config)

        result = await _run(
            graph,
            {"messages": [HumanMessage(content=user_input)], "context": context},
            thread_config,
        )
        reply = result["messages"][-1].content
        print(f"\ndarwin > {reply}")
        if not reply.strip():
            print(
                "  [empty reply — this session's history may be corrupt. "
                "Type /new to start a fresh session.]"
            )

        try:
            memory.add(user_input, reply)
        except Exception:
            pass


async def main() -> None:
    mcp = MCPClient()
    try:
        connected = await mcp.connect_all()
        mcp_tools = [to_langchain_tool(mcp, meta) for meta in mcp.tools()]
        index_tools(mcp_tools)
        print(f"[mcp] servers: {connected or 'none'}")
        print(f"[mcp] tools: {[t.name for t in mcp_tools]}")

        async with AsyncPostgresSaver.from_conn_string(config.POSTGRES_URL) as saver:
            await saver.setup()
            graph = build_graph(get_llm(), saver, tools=ALL_TOOLS, mcp_tools=mcp_tools)
            await _chat(graph, MemoryClient())
    finally:
        await mcp.cleanup()


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
