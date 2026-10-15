# NOTES — Implementation Log

## Phase 1: Core Design & Reasoning Engine

### What was built
- `src/darwin/core/config.py` — single `Config` class; every value read from `DARWIN_*` env vars via `.env`.
- `src/darwin/core/llm.py` — model-agnostic client wrapping `ChatOpenAI` for any OpenAI-compatible endpoint.
- `src/darwin/core/orchestrator.py` — custom StateGraph tool-calling loop:
  - `guard` node: deterministic short-term buffer trim (last 50 messages).
  - `agent` node: LLM invocation with system prompt injected (not persisted into history).
  - Tools node + conditional routing (auto-attached in Phase 2).
  - `PostgresSaver` checkpointer wired to every compiled graph (survives restarts).
- `src/darwin/core/memory.py` — `VectorMemory` (Qdrant, `memories` collection, fastembed local embeddings).
- `src/darwin/core/graph_memory.py` — `GraphMemory` (Neo4j entity-relation store: `remember_fact` / `recall_facts`).
- `src/darwin/core/queue.py` — `TaskQueue` (Redis/Valkey + RQ `darwin` queue).
- `src/darwin/main.py` — CLI chat loop with thread persistence.

### Decisions
- Unified memory on **mem0** (0.1.116): one `Memory.from_config` client manages Qdrant vector store (`memories` collection) + Neo4j graph store — replaced the earlier hand-rolled `VectorMemory`/`GraphMemory` modules. Note: mem0 2.x dropped graph stores, hence the `<1` pin.
- mem0's internal extraction LLM is configured with the same Darwin provider settings (base URL, key, model) — no separate credentials.
- Embeddings via local `sentence-transformers/all-MiniLM-L6-v2` (384 dims), no extra API key.
- Chat loop: recall memories per turn (injected into the system prompt) and sync both sides of the turn into mem0 after the reply (`main.py`).
- State is an explicit `TypedDict` (`Annotated[list[BaseMessage], add_messages]`) — full control, fewer prebuilt shims. Chose `add_messages` over `operator.add` because it upserts by message ID (trim actually removes old entries instead of appending duplicates) and `ToolNode` depends on that semantic. Buffer trim uses `RemoveMessage` in the guard node (keeps last 50).
- Zero-config: `docker-compose.yml` ships Postgres/Qdrant/Neo4j/Valkey with credentials baked in and mirrored as defaults in `config.py`. Only `.env` vars a user must set: API key, model, base url, (optional) neo4j password.
- Neo4j runs a JVM (~1.5–2 GB RAM) — the heaviest local service. To save resources users can run a free **Neo4j Aura** instance instead and point `DARWIN_NEO4J_URI` / `DARWIN_NEO4J_USER` / `DARWIN_NEO4J_PASSWORD` at it (see `.env.example`); otherwise the local docker defaults are used.

### Breaking changes
- `src/darwin/core/__init__.py` old experiment (in-memory graph with `add` demo tool) replaced with clean re-exports.

### Test results
- All modules import OK after `uv sync` (with `psycopg[binary]` added).
- **Phase 1 verified live (2026-10-15)** against the local docker stack:
  - mem0: add → facts extracted in Qdrant (`memories`) + relations in Neo4j graph (e.g. `testuser favorite_programming_language python`); recall returns scored results.
  - Orchestrator: full LLM turn with tool-calling graph via local proxy (`deepseek/deepseek-v4-flash`); checkpoint verified in Postgres (state reloads with 2 messages).
- `PostgresSaver` in current versions needs a live `psycopg.Connection` — `from_conn_string` returns a context manager. Fixed: `psycopg.connect(url, autocommit=True)` → `PostgresSaver(conn)`.
- Old leftover compose stack (`bridge/infra`, random creds) removed; root `docker-compose.yml` is now the single source of truth.

### How to test yourself
1. `docker-compose up -d` (from repo root)
2. Fill `.env` from `.env.example` (API key, base URL, model)
3. `uv run darwin` — chat; memory recall/ sync happens automatically per turn
4. Programmatic memory test: `python -c "from darwin.core.memory_client import MemoryClient; m=MemoryClient(); print(m.recall('favorite language'))"`
