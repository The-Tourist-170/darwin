"""Tool RAG: index tool schemas in Qdrant and retrieve the most relevant per turn."""

import hashlib
import re

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from darwin.core.config import config

COLLECTION = "tools_registry"
EMBED_DIM = 384
MAX_LEXICAL_EXTRAS = 4
# Generic tool-name verbs: matching on these pulls in unrelated servers (every "list_*" tool).
GENERIC_WORDS = {
    "list", "read", "write", "create", "update", "delete", "find", "search",
    "fetch", "from", "with", "into", "this", "that", "what", "when", "which", "their", "some",
}
_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def _client() -> QdrantClient:
    client = QdrantClient(url=config.QDRANT_URL)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE)
        )
    return client


def _point_id(name: str) -> int:
    """Deterministic id: Python's hash() is salted per process and would duplicate points."""
    return int(hashlib.sha1(name.encode()).hexdigest()[:15], 16)


def index_tools(tools: list) -> None:
    """Rebuild the registry so it matches exactly the currently connected tools."""
    if not tools:
        return
    client = _client()
    client.delete_collection(COLLECTION)
    client.create_collection(COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE))
    texts = [f"{t.name}: {t.description}" for t in tools]
    vectors = _model.encode(texts)
    client.upsert(
        COLLECTION,
        [
            PointStruct(id=_point_id(t.name), vector=v.tolist(), payload={"name": t.name})
            for t, v in zip(tools, vectors)
        ],
    )


def select_tools(query: str, tools: list, k: int | None = None) -> list:
    """Return the most relevant tools: vector hits plus name-matching extras.

    Small embeddings miss phrasing like "repos from my profile" -> search_repositories,
    so tools whose name shares a query word are unioned in.
    """
    if not config.TOOL_RAG_ENABLED or not tools:
        return tools
    k = k or config.TOOL_RAG_TOP_K
    hits = _client().query_points(COLLECTION, query=_model.encode(query).tolist(), limit=k).points
    by_name = {t.name: t for t in tools}
    selected, seen = [], set()
    for hit in hits:
        name = hit.payload["name"]
        if name in by_name and name not in seen:
            seen.add(name)
            selected.append(by_name[name])

    words = {word for word in re.findall(r"[a-z]{4,}", query.lower())} - GENERIC_WORDS
    scored = sorted(
        ((sum(word in t.name.lower() for word in words), t) for t in tools if any(word in t.name.lower() for word in words)),
        key=lambda pair: -pair[0],
    )
    lexical = [t for _, t in scored if t.name not in seen]
    return selected + lexical[:MAX_LEXICAL_EXTRAS] or tools

