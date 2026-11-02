"""Central configuration. Reads .env once and reports which services are usable."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str = "") -> str:
    """Read an env var and treat blank or placeholder values as missing."""
    value = os.getenv(name, default).strip()
    if value.lower() in {"", "your_key_here", "changeme", "none"}:
        return default
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    newsapi_key: str
    gnews_api_key: str
    cache_ttl: int
    http_timeout: float
    min_reliability: float

    @property
    def has_llm(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_newsapi(self) -> bool:
        return bool(self.newsapi_key)

    @property
    def has_gnews(self) -> bool:
        return bool(self.gnews_api_key)

    def status(self) -> dict[str, bool]:
        """Used by the UI sidebar to show what is configured."""
        return {
            "OpenAI (LLM)": self.has_llm,
            "NewsAPI": self.has_newsapi,
            "GNews (backup)": self.has_gnews,
            "DuckDuckGo search (no key)": True,
        }


def load_settings() -> Settings:
    return Settings(
        openai_api_key=_get("OPENAI_API_KEY"),
        openai_model=_get("OPENAI_MODEL", "gpt-4.1-mini"),
        newsapi_key=_get("NEWSAPI_KEY"),
        gnews_api_key=_get("GNEWS_API_KEY"),
        cache_ttl=int(_get("NEWS_CACHE_TTL_SECONDS", "600")),
        http_timeout=float(_get("HTTP_TIMEOUT_SECONDS", "8")),
        min_reliability=float(_get("MIN_RELIABILITY_SCORE", "0.35")),
    )


# UI label -> provider category. "Finance" maps to "business" on both APIs.
CATEGORIES: dict[str, str] = {
    "Technology": "technology",
    "Finance": "business",
    "Sports": "sports",
    "Science": "science",
    "Health": "health",
    "Entertainment": "entertainment",
    "General": "general",
}
