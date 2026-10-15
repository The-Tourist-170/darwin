"""Model-agnostic LLM client. Uses ChatOpenAI against any OpenAI-compatible base URL."""

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from darwin.core.config import config


def get_llm() -> BaseChatModel:
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0.2,
    )
