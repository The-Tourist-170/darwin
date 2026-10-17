"""Session naming and listing, backed by the Postgres checkpointer tables."""

import re

import psycopg

from darwin.core.config import config

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "my", "me",
    "is", "are", "was", "can", "could", "would", "should", "please", "you", "your", "this", "that",
    "what", "whats", "how", "why", "do", "does", "use", "using", "show", "give", "tell", "list",
    "about", "into", "from", "over", "some", "any", "will", "just", "now", "also", "there", "here",
    "it", "its", "be", "been", "i", "we", "he", "she", "they", "s", "t",
}


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(config.POSTGRES_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def list_sessions(limit: int = 20) -> list[tuple[str, str, int]]:
    return _query(
        "SELECT thread_id, max(checkpoint_id), count(*) FROM checkpoints "
        "GROUP BY thread_id ORDER BY max(checkpoint_id) DESC LIMIT %s",
        (limit,),
    )


def session_exists(thread_id: str) -> bool:
    return bool(_query("SELECT 1 FROM checkpoints WHERE thread_id = %s LIMIT 1", (thread_id,)))


def slugify(text: str, words: int = 4) -> str:
    """Context title from the first message: 'git-status-this-repo'."""
    tokens = [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]
    picked = [token for token in tokens if token not in STOPWORDS][:words] or tokens[:words]
    return "-".join(picked)[:40] or "session"


def new_session_id(first_message: str) -> str:
    """Unique, human-readable session id derived from the first message."""
    base = slugify(first_message)
    candidate, counter = base, 2
    while session_exists(candidate):
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
