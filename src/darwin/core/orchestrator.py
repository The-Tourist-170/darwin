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
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from darwin.core.config import config
from darwin.guardrails import sanitize_input, sanitize_output
from darwin.guardrails.permissions import decide, kind_of
from darwin.guardrails.scope import scope
from darwin.tools.registry import select_tools

MAX_BUFFER_MESSAGES = 50
NATIVE_MUTATING = {"write_file", "run_shell"}
SYSTEM_PROMPT = (
    "You are Darwin, an autonomous general-purpose agent. "
    "Always think through a plan before executing any work."
)


def is_mutating(name: str) -> bool:
    """Two-tier permissions: MCP tools are mutating unless allowlisted read-only."""
    if "__" in name:
        return name.split("__", 1)[1] not in config.READ_ONLY_MCP_TOOLS
    return name in NATIVE_MUTATING


class AgentState(TypedDict):
    """Short-term conversational buffer (message upsert reducer)."""

    messages: Annotated[list[BaseMessage], add_messages]
    approved: bool
    context: str
    session_allowed_paths: list[str]


def _trim_buffer(state: AgentState) -> AgentState:
    """Guard node: drop stored SystemMessages and keep the buffer under the limit."""
    messages = state["messages"]
    stale = [RemoveMessage(id=m.id) for m in messages if isinstance(m, SystemMessage)]
    over_limit = len(messages) - MAX_BUFFER_MESSAGES
    if over_limit > 0:
        stale += [RemoveMessage(id=m.id) for m in messages[:over_limit] if not isinstance(m, SystemMessage)]
    return {"messages": stale}


def _approve(state: AgentState) -> AgentState:
    """Human-in-the-loop gate: interrupt on mutating tool calls until approved."""
    calls = state["messages"][-1].tool_calls
    mutating = [c for c in calls if is_mutating(c["name"])]
    if not mutating:
        return {"approved": True}
    request = [{"name": c["name"], "args": c["args"]} for c in mutating]
    if interrupt(request) is True:
        return {"approved": True}
    return {
        "approved": False,
        "messages": [
            ToolMessage(content="Denied by user.", tool_call_id=c["id"], name=c["name"]) for c in calls
        ],
    }


def _intent(state: AgentState) -> str:
    """The assistant's own text for THIS turn (empty if it only emitted tool calls).

    Walking back past the user's message would surface stale text from earlier turns.
    """
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return ""
        if isinstance(message, AIMessage) and message.content.strip():
            return message.content
    return ""


def _permissions(state: AgentState) -> AgentState:
    """Scope gate: allow in-bounds calls, hard-deny policy violations, escalate the rest."""
    calls = state["messages"][-1].tool_calls
    session_paths = list(state.get("session_allowed_paths") or [])
    scope.clear_ephemeral()

    pending: list[str] = []
    pending_modes: list[str] = []
    for call in calls:
        decision, reason, call_targets = decide(call["name"], call["args"], session_paths)
        if decision == "deny":
            return {
                "approved": False,
                "messages": [
                    ToolMessage(
                        content=f"Error: {reason}. Use an in-workspace alternative or ask the user.",
                        tool_call_id=c["id"],
                        name=c["name"],
                    )
                    for c in calls
                ],
            }
        if decision == "ask":
            pending += call_targets
            pending_modes.append(kind_of(call["name"]))

    if not pending:
        return {"approved": True}

    intent = _intent(state)
    answer = interrupt(
        {
            "type": "escalation",
            "tool": calls[0]["name"],
            "targets": sorted(set(pending)),
            "mode": "read-only" if set(pending_modes) <= {"Read"} else "mutating",
            "intent": intent,
        }
    )
    if not answer or not answer.get("approved"):
        return {
            "approved": False,
            "messages": [
                ToolMessage(
                    content="Permission denied by user. Use an in-workspace alternative or ask the user.",
                    tool_call_id=c["id"],
                    name=c["name"],
                )
                for c in calls
            ],
        }

    granted = sorted(set(pending))
    persistent = answer.get("scope") == "session"
    for target in granted:
        scope.add(target, persistent=persistent)
    if persistent:
        return {"approved": True, "session_allowed_paths": session_paths + granted}
    return {"approved": True}


def _route_approval(state: AgentState) -> str:
    return "tools" if state.get("approved", True) else "agent"


def _route_scope(state: AgentState) -> str:
    return "approve" if state.get("approved", True) else "agent"


def _sanitize_history(state: AgentState) -> list[BaseMessage]:
    """Redact secrets everywhere and reject injection on the latest human input.

    Stored SystemMessages are dropped: the system prompt is rebuilt per turn from
    SYSTEM_PROMPT + state["context"], so it must never accumulate in history.
    """
    cleaned = []
    stored = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
    for i, msg in enumerate(stored):
        if isinstance(msg, HumanMessage):
            try:
                cleaned.append(HumanMessage(content=sanitize_input(msg.content), id=msg.id))
            except ValueError:
                if i == len(stored) - 1:
                    raise
                cleaned.append(msg)
        elif isinstance(msg, ToolMessage):
            content = sanitize_output(msg.content) or " "
            cleaned.append(ToolMessage(content=content, tool_call_id=msg.tool_call_id, id=msg.id))
        elif isinstance(msg, AIMessage):
            if not msg.content:
                # OpenAI-compatible proxies reject null content on tool-call turns,
                # and langchain-openai turns "" into None when tool calls are present.
                msg.content = " "
            cleaned.append(msg)
        else:
            cleaned.append(msg)
    return cleaned


def build_graph(
    llm: BaseChatModel,
    checkpointer,
    tools: list[BaseTool] | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> StateGraph:
    native = tools or []
    mcp = mcp_tools or []
    all_tools = native + mcp

    async def agent_node(state: AgentState) -> AgentState:
        try:
            messages = _sanitize_history(state)
        except ValueError:
            return {"messages": [AIMessage(content="Blocked by input guardrails.")]}

        bound = native
        if mcp:
            query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
            bound = native + select_tools(query, mcp)
        model = llm.bind_tools(bound) if bound else llm

        reply = await model.ainvoke([SystemMessage(content=SYSTEM_PROMPT + state.get("context", "")), *messages])
        reply.content = sanitize_output(reply.content)
        return {"messages": [reply]}

    graph = StateGraph(AgentState)
    graph.add_node("guard", _trim_buffer)
    graph.add_node("agent", agent_node)
    if all_tools:
        graph.add_node("permissions", _permissions)
        graph.add_node("approve", _approve)
        graph.add_node("tools", ToolNode(all_tools))
        graph.add_conditional_edges("agent", lambda s: "permissions" if s["messages"][-1].tool_calls else END)
        graph.add_conditional_edges("permissions", _route_scope, ["approve", "agent"])
        graph.add_conditional_edges("approve", _route_approval, ["tools", "agent"])
        graph.add_edge("tools", "agent")
    graph.add_edge(START, "guard")
    graph.add_edge("guard", "agent")

    return graph.compile(checkpointer=checkpointer)

