"""Orchestrator: a custom LangGraph StateGraph tool-calling reasoning loop.

- State is an explicit TypedDict with a message reducer (upsert semantics:
  trimmed IDs are replaced, not duplicated — also required by ToolNode).
- PostgresSaver checkpoints state so sessions survive process restarts.
- Tools are injected at graph build time (populated in later phases).
"""

from typing import Annotated, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
import psycopg

from darwin.core.config import config
from darwin.guardrails import sanitize_input, sanitize_output

MAX_BUFFER_MESSAGES = 50
MUTATING_TOOLS = {"write_file", "run_shell"}
SYSTEM_PROMPT = (
    "You are Darwin, an autonomous general-purpose agent. "
    "Always think through a plan before executing any work."
)


class AgentState(TypedDict):
    """Short-term conversational buffer (message upsert reducer)."""

    messages: Annotated[list[BaseMessage], add_messages]
    approved: bool


def _trim_buffer(state: AgentState) -> AgentState:
    """Guard node: keeps the buffer under MAX_BUFFER_MESSAGES by removing older messages."""
    messages = state["messages"]
    over_limit = len(messages) - MAX_BUFFER_MESSAGES
    if over_limit > 0:
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:over_limit]]}
    return state


def _approve(state: AgentState) -> AgentState:
    """Human-in-the-loop gate: interrupt on mutating tool calls until approved."""
    calls = state["messages"][-1].tool_calls
    mutating = [c for c in calls if c["name"] in MUTATING_TOOLS]
    if not mutating:
        return {"approved": True}
    request = [{"name": c["name"], "args": c["args"]} for c in mutating]
    if interrupt(request) is True:
        return {"approved": True}
    return {
        "approved": False,
        "messages": [ToolMessage(content="Denied by user.", tool_call_id=c["id"]) for c in calls],
    }


def _route_approval(state: AgentState) -> str:
    return "tools" if state.get("approved", True) else "agent"


def _sanitize_history(state: AgentState) -> list[BaseMessage]:
    """Redact secrets everywhere and reject injection on the latest human input."""
    cleaned = []
    for i, msg in enumerate(state["messages"]):
        if isinstance(msg, HumanMessage):
            try:
                cleaned.append(HumanMessage(content=sanitize_input(msg.content), id=msg.id))
            except ValueError:
                if i == len(state["messages"]) - 1:
                    raise
                cleaned.append(msg)
        elif isinstance(msg, ToolMessage):
            cleaned.append(ToolMessage(content=sanitize_output(msg.content), tool_call_id=msg.tool_call_id, id=msg.id))
        else:
            cleaned.append(msg)
    return cleaned


def build_graph(llm: BaseChatModel, tools: list[BaseTool] | None = None) -> StateGraph:
    tools = tools or []
    model = llm.bind_tools(tools) if tools else llm

    def agent_node(state: AgentState) -> AgentState:
        try:
            messages = _sanitize_history(state)
        except ValueError:
            return {"messages": [AIMessage(content="Blocked by input guardrails.")]}
        reply = model.invoke([SystemMessage(content=SYSTEM_PROMPT), *messages])
        reply.content = sanitize_output(reply.content)
        return {"messages": [reply]}

    graph = StateGraph(AgentState)
    graph.add_node("guard", _trim_buffer)
    graph.add_node("agent", agent_node)
    if tools:
        graph.add_node("approve", _approve)
        graph.add_node("tools", ToolNode(tools))
        graph.add_conditional_edges("agent", lambda s: "approve" if s["messages"][-1].tool_calls else END)
        graph.add_conditional_edges("approve", _route_approval, ["tools", "agent"])
        graph.add_edge("tools", "agent")
    graph.add_edge(START, "guard")
    graph.add_edge("guard", "agent")

    conn = psycopg.connect(config.POSTGRES_URL, autocommit=True)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return graph.compile(checkpointer=checkpointer)

