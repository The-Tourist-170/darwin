"""Darwin CLI: interactive chat loop for the Phase 1 reasoning engine."""

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command

from darwin.core.llm import get_llm
from darwin.core.memory_client import MemoryClient
from darwin.core.orchestrator import build_graph, SYSTEM_PROMPT
from darwin.tools import ALL_TOOLS


def _run(graph, payload: dict, config: dict) -> dict:
    result = graph.invoke(payload, config)
    while True:
        state = graph.get_state(config)
        if state.tasks and state.tasks[0].interrupts:
            request = state.tasks[0].interrupts[0].value
            print("\n[approval required]")
            print(json.dumps(request, indent=2))
            approved = input("approve? (y/n): ").strip().lower() == "y"
            result = graph.invoke(Command(resume=approved), config)
        else:
            return result


def main() -> None:
    graph = build_graph(get_llm(), tools=ALL_TOOLS)
    memory = MemoryClient()
    thread_id = "default"
    config = {"configurable": {"thread_id": thread_id}}

    print("Darwin — type 'exit' to quit.")
    while True:
        user_input = input("\nyou > ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        try:
            memories = [m["memory"] for m in memory.recall(user_input)]
        except Exception:
            memories = []
        context = f"\n\nRelevant long-term memories:\n{json.dumps(memories)}" if memories else ""
        result = _run(
            graph,
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT + context),
                    HumanMessage(content=user_input),
                ]
            },
            config,
        )
        reply = result["messages"][-1].content
        print(f"\ndarwin > {reply}")
        try:
            memory.add(user_input, reply)
        except Exception:
            pass


if __name__ == "__main__":
    main()
