"""Central configuration for Darwin. All values come from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Model provider (any OpenAI-compatible endpoint: OpenAI, DeepSeek, vLLM, Ollama)
    LLM_BASE_URL: str = os.getenv("DARWIN_LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("DARWIN_LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("DARWIN_LLM_MODEL", "gpt-4o-mini")

    # Persistence & memory
    # Credentials default to the docker-compose services — zero config needed.
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://darwin:darwin@localhost:5432/darwin")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "darwin123")

    # Background queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


config = Config()
