"""Darwin CLI: interactive chat loop for the Phase 1 reasoning engine."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from darwin.core.llm import get_llm
from darwin.core.memory_client import MemoryClient
from darwin.core.orchestrator import build_graph, SYSTEM_PROMPT


def main() -> None:
    graph = build_graph(get_llm())
    memory = MemoryClient()
    thread_id = "default"

    print("Darwin (Phase 1) — type 'exit' to quit.")
    while True:
        user_input = input("\nyou > ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        memories = [m["memory"] for m in memory.recall(user_input)]
        context = f"\n\nRelevant long-term memories:\n{json.dumps(memories)}" if memories else ""
        result = graph.invoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT + context),
                    HumanMessage(content=user_input),
                ]
            },
            {"configurable": {"thread_id": thread_id}},
        )
        reply = result["messages"][-1].content
        print(f"\ndarwin > {reply}")
        memory.add(user_input, reply)


if __name__ == "__main__":
    main()
