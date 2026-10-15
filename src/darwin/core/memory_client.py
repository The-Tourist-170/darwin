"""Long-term memory via mem0: Qdrant vector store + Neo4j graph store, one client."""

from mem0 import Memory

from darwin.core.config import config


def _build_config() -> dict:
    return {
        "version": "v1.1",
        "embedder": {
            "provider": "huggingface",
            "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
        },
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
                "host": "localhost",
                "port": 6333,
                "collection_name": "memories",
                "embedding_model_dims": 384,
            },
        },
    }


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
