"""LLM access. Returns None when no key is configured so callers can fall back."""

from __future__ import annotations

from functools import lru_cache

from newsgenie.config import Settings


@lru_cache(maxsize=4)
def _build(api_key: str, model: str, temperature: float):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(api_key=api_key, model=model, temperature=temperature, timeout=30, max_retries=1)


def get_llm(settings: Settings, temperature: float = 0.2):
    if not settings.has_llm:
        return None
    try:
        return _build(settings.openai_api_key, settings.openai_model, temperature)
    except Exception:
        return None
