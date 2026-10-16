"""Tool RAG: index tool schemas in Qdrant and retrieve the most relevant per turn."""

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from darwin.core.config import config

COLLECTION = "tools_registry"
EMBED_DIM = 384
_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def _client() -> QdrantClient:
    client = QdrantClient(url=config.QDRANT_URL)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE)
        )
    return client


def _point_id(name: str) -> int:
    return abs(hash(name)) % (10**15)


def index_tools(tools: list) -> None:
    """Upsert each tool's name + description into the tools_registry collection."""
    if not tools:
        return
    texts = [f"{t.name}: {t.description}" for t in tools]
    vectors = _model.encode(texts)
    _client().upsert(
        COLLECTION,
        [
            PointStruct(id=_point_id(t.name), vector=v.tolist(), payload={"name": t.name})
            for t, v in zip(tools, vectors)
        ],
    )


def select_tools(query: str, tools: list, k: int | None = None) -> list:
    """Return the k most relevant tools for a query (all tools if RAG is off or empty)."""
    if not config.TOOL_RAG_ENABLED or not tools:
        return tools
    k = k or config.TOOL_RAG_TOP_K
    hits = _client().query_points(COLLECTION, query=_model.encode(query).tolist(), limit=k).points
    by_name = {t.name: t for t in tools}
    selected = [by_name[hit.payload["name"]] for hit in hits if hit.payload["name"] in by_name]
    return selected or tools
