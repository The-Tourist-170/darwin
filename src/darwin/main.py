"""Darwin CLI: chat loop, MCP tools, memory and HITL approval (rich TUI)."""

import asyncio
import json

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from darwin import tui
from darwin.core.config import config
from darwin.core.llm import get_llm
from darwin.core.memory_client import get_memory_client
from darwin.core.orchestrator import build_graph
from darwin.mcp.adapters import to_langchain_tool
from darwin.mcp.client import MCPClient
from darwin.sessions import list_sessions, session_exists, new_session_id
from darwin.tools import ALL_TOOLS
from darwin.tools.registry import index_tools


def _trace(message) -> None:
    for call in getattr(message, "tool_calls", None) or []:
        tui.trace_call(call["name"], call["args"])
    if isinstance(message, ToolMessage):
        tui.trace_result(getattr(message, "name", "tool"), message.content)


async def _settle(graph, thread_config: dict) -> None:
    """Discard interrupts left pending by an earlier interrupted run."""
    while True:
        state = await graph.aget_state(thread_config)
        if not (state.tasks and state.tasks[0].interrupts):
            return
        payload = state.tasks[0].interrupts[0].value
        resume = {"approved": False} if isinstance(payload, dict) else False
        tui.notice("discarded a pending approval from an interrupted earlier turn")
        await graph.ainvoke(Command(resume=resume), thread_config)


async def _run(graph, payload: dict, thread_config: dict) -> dict:
    """Stream one turn: trace tools, prompt for approvals, handle escalations."""
    while True:
        interrupted = False
        async for chunk in graph.astream(payload, thread_config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupted = True
                    request = update[0].value
                    if isinstance(request, dict) and request.get("type") == "escalation":
                        payload = Command(resume=await tui.escalation_async(request))
                    else:
                        names = ", ".join(c["name"] for c in request)
                        payload = Command(resume=await tui.approval_async(names))
                    break
                for message in (update or {}).get("messages", []):
                    _trace(message)
        if not interrupted:
            break
    state = await graph.aget_state(thread_config)
    return {"messages": list(state.values["messages"])}


async def _chat(graph, memory, thread: dict) -> None:
    tui.notice("new session — it will be named from your first message (/sessions to switch)")
    while True:
        user_input = await tui.prompt_async()
        if user_input is None or user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            break
        if not user_input:
            continue
        if user_input == "/new":
            thread["id"] = None
            tui.notice("new session — it will be named from your first message")
            continue
        if user_input.startswith("/themes") or user_input.strip() == "/theme":
            chosen = await tui.pick_theme(tui.current_theme)
            if chosen:
                tui.notice(f"theme: {tui.set_theme(chosen)}")
            continue
        if user_input.startswith("/theme"):
            arg = user_input[len("/theme"):].strip()
            tui.notice(f"theme: {tui.set_theme(arg)}")
            continue
        if user_input.startswith("/sessions"):
            chosen = await tui.pick_session(list_sessions(), thread["id"] or "")
            if chosen:
                thread["id"] = chosen
                tui.notice(f"switched to session {chosen}")
            continue
        if user_input.startswith("/session"):
            arg = user_input[len("/session"):].strip()
            if not arg:
                tui.sessions_table(list_sessions())
            elif session_exists(arg):
                thread["id"] = arg
                tui.notice(f"switched to session {arg}")
            else:
                tui.notice(f"no such session: {arg}")
            continue

        if thread["id"] is None:
            thread["id"] = new_session_id(user_input)
            tui.notice(f"session: {thread['id']}")
        thread_config = {"configurable": {"thread_id": thread["id"]}}
        try:
            memories = [m["memory"] for m in memory.recall(user_input)] if memory else []
        except Exception:
            memories = []
        context = f"\n\nRelevant long-term memories:\n{json.dumps(memories)}" if memories else ""

        await _settle(graph, thread_config)
        result = await _run(
            graph,
            {"messages": [HumanMessage(content=user_input)], "context": context},
            thread_config,
        )
        reply = str(result["messages"][-1].content)
        tui.reply(reply)
        if not reply.strip():
            tui.notice("empty reply — the session history may be corrupt; use /new")
        try:
            if memory:
                memory.add(user_input, reply)
        except Exception:
            pass


async def main() -> None:
    mcp = MCPClient()
    status = tui.status("booting Darwin…")
    status.start()
    try:
        connected = await mcp.connect_all()
        mcp_tools = [to_langchain_tool(mcp, meta) for meta in mcp.tools()]
        # Tool RAG is a mitigation, not a dependency: a down Qdrant must not block boot.
        try:
            index_tools(mcp_tools)
        except Exception as exc:
            tui.notice(f"tool RAG unavailable ({type(exc).__name__}); binding tools by name only")
    finally:
        status.stop()

    memory = None
    try:
        memory = get_memory_client()
    except Exception as exc:
        tui.notice(f"long-term memory unavailable ({type(exc).__name__}); continuing without it")

    thread = {"id": None}
    try:
        tui.banner(connected, len(mcp_tools), len(ALL_TOOLS), thread["id"] or "(new)")
        async with AsyncPostgresSaver.from_conn_string(config.POSTGRES_URL) as saver:
            await saver.setup()
            graph = build_graph(get_llm(), saver, tools=ALL_TOOLS, mcp_tools=mcp_tools)
            await _chat(graph, memory, thread)
    finally:
        await mcp.cleanup()


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
