"""Long-term memory via mem0: Qdrant vector store + Neo4j graph store, one client."""

import logging
from pathlib import Path

from mem0 import Memory
from qdrant_client import QdrantClient

from darwin.core.config import config

# mem0 raises these loggers back to WARNING at import; set them quiet here, after that.
for _name in ("huggingface_hub", "transformers", "sentence_transformers", "urllib3"):
    logging.getLogger(_name).setLevel(logging.ERROR)
logging.getLogger("posthog").disabled = True
# Memory writes are best-effort; mem0 logs loud tracebacks when the provider returns non-JSON.
logging.getLogger("mem0").setLevel(logging.CRITICAL)


def _build_config() -> dict:
    embedder = {
        "provider": "huggingface",
        "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
    }
    # If the model is already cached, never contact the Hub (no prompt/download noise).
    cached = Path.home() / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2"
    if cached.exists():
        embedder["config"]["model_kwargs"] = {"local_files_only": True}
    return {
        "version": "v1.1",
        "embedder": embedder,
        "llm": {
            "provider": "openai",
            "config": {
                "model": config.LLM_MODEL,
                "openai_base_url": config.LLM_BASE_URL,
                "api_key": config.LLM_API_KEY,
            },
        },
        "graph_store": {
            "provider": "neo4j",
            "config": {
                "username": config.NEO4J_USER,
                "password": config.NEO4J_PASSWORD,
                "url": config.NEO4J_URI,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "client": QdrantClient(url=config.QDRANT_URL, check_compatibility=False),
                "collection_name": "memories",
                "embedding_model_dims": 384,
            },
        },
    }


_shared: "MemoryClient | None" = None


def get_memory_client() -> "MemoryClient":
    """One process-wide client, so expensive embedder models load once."""
    global _shared
    if _shared is None:
        _shared = MemoryClient()
    return _shared


class MemoryClient:
    def __init__(self, user_id: str = "default") -> None:
        self.client = Memory.from_config(_build_config())
        self.user_id = user_id

    def recall(self, query: str) -> list[dict]:
        return self.client.search(query, user_id=self.user_id).get("results", [])

    def add(self, user_message: str, assistant_message: str) -> dict:
        return self.client.add(
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ],
            user_id=self.user_id,
        )
