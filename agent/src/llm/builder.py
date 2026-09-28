from openai import OpenAI

from agent.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_LOCAL_MODE,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_USE_JSON_SCHEMA,
)
from agent.src.llm.client import LLMClient


def build_llm_client() -> LLMClient:
    raw_client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        timeout=LLM_TIMEOUT,
        max_retries=1,
    )
    return LLMClient(
        client=raw_client,
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        local_mode=LLM_LOCAL_MODE,
        use_json_schema=LLM_USE_JSON_SCHEMA,
    )
