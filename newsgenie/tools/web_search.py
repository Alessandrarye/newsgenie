"""General web search (DuckDuckGo, no API key) used to ground general answers
and to add background context to news topics."""

from __future__ import annotations

from newsgenie.config import Settings
from newsgenie.models import SearchResult
from newsgenie.tools.cache import TTLCache
from newsgenie.tools.http import ProviderError

_cache = TTLCache(ttl_seconds=900)


def web_search(settings: Settings, query: str, limit: int = 5) -> list[SearchResult]:
    key = f"web:{query.lower().strip()}:{limit}"
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        from ddgs import DDGS
        rows = DDGS(timeout=int(settings.http_timeout)).text(query, max_results=limit)
    except Exception as exc:
        raise ProviderError(f"Web search failed: {type(exc).__name__}") from exc
    results = [
        SearchResult(title=r.get("title") or "", url=r.get("href") or "", snippet=r.get("body") or "")
        for r in rows or []
        if r.get("href")
    ]
    if results:
        _cache.set(key, results)
    return results
