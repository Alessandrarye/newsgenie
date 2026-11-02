"""Real-time news retrieval with a provider fallback chain.

Order of attempts for every request:
    1. fresh cache        (instant, no quota)
    2. NewsAPI            (primary, needs NEWSAPI_KEY)
    3. GNews              (backup, needs GNEWS_API_KEY)
    4. DuckDuckGo News    (no key needed)
    5. stale cache        (last good result, labeled as stale)
Each failure is recorded so the UI can show exactly what happened.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from newsgenie.config import Settings
from newsgenie.models import Article
from newsgenie.tools.cache import TTLCache
from newsgenie.tools.http import ProviderError, get_session

NEWSAPI_BASE = "https://newsapi.org/v2"
GNEWS_BASE = "https://gnews.io/api/v4"

# Search phrases used when a provider has no native category (DuckDuckGo)
CATEGORY_QUERIES = {
    "technology": "technology news",
    "business": "finance markets business news",
    "sports": "sports news",
    "science": "science news",
    "health": "health news",
    "entertainment": "entertainment news",
    "general": "top news today",
}

_cache: TTLCache | None = None


def get_cache(ttl: int) -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(ttl)
    return _cache


@dataclass
class NewsResult:
    articles: list[Article] = field(default_factory=list)
    provider: str = "none"
    errors: list[str] = field(default_factory=list)
    from_cache: bool = False
    stale: bool = False


# ---------------------------------------------------------------- providers

def _clean(articles: list[Article]) -> list[Article]:
    """Drop removed/empty items and exact duplicate URLs."""
    seen: set[str] = set()
    out: list[Article] = []
    for a in articles:
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title or not url or title == "[Removed]" or url in seen:
            continue
        seen.add(url)
        out.append(a)
    return out


def fetch_newsapi(settings: Settings, category: str | None, query: str | None, limit: int) -> list[Article]:
    if not settings.has_newsapi:
        raise ProviderError("NewsAPI skipped: NEWSAPI_KEY not set")
    if query:
        url = f"{NEWSAPI_BASE}/everything"
        params = {"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": min(limit * 2, 50)}
    else:
        url = f"{NEWSAPI_BASE}/top-headlines"
        params = {"country": "us", "category": category or "general", "pageSize": min(limit * 2, 50)}
    try:
        resp = get_session().get(url, params=params, headers={"X-Api-Key": settings.newsapi_key},
                                 timeout=settings.http_timeout)
        data = resp.json()
    except Exception as exc:  # network error, timeout, bad JSON
        raise ProviderError(f"NewsAPI request failed: {type(exc).__name__}") from exc
    if resp.status_code != 200 or data.get("status") != "ok":
        raise ProviderError(f"NewsAPI error {resp.status_code}: {data.get('code', '')} {data.get('message', '')}".strip())
    return [
        Article(
            title=a.get("title") or "",
            description=a.get("description") or "",
            url=a.get("url") or "",
            source=(a.get("source") or {}).get("name") or "",
            published_at=a.get("publishedAt") or "",
            provider="newsapi",
        )
        for a in data.get("articles", [])
    ]


def fetch_gnews(settings: Settings, category: str | None, query: str | None, limit: int) -> list[Article]:
    if not settings.has_gnews:
        raise ProviderError("GNews skipped: GNEWS_API_KEY not set")
    if query:
        url = f"{GNEWS_BASE}/search"
        params = {"q": query, "lang": "en", "max": min(limit, 10), "sortby": "publishedAt"}
    else:
        url = f"{GNEWS_BASE}/top-headlines"
        params = {"category": category or "general", "lang": "en", "country": "us", "max": min(limit, 10)}
    params["apikey"] = settings.gnews_api_key
    try:
        resp = get_session().get(url, params=params, timeout=settings.http_timeout)
        data = resp.json()
    except Exception as exc:
        raise ProviderError(f"GNews request failed: {type(exc).__name__}") from exc
    if resp.status_code != 200 or "articles" not in data:
        raise ProviderError(f"GNews error {resp.status_code}: {data.get('errors', '')}")
    return [
        Article(
            title=a.get("title") or "",
            description=a.get("description") or "",
            url=a.get("url") or "",
            source=(a.get("source") or {}).get("name") or "",
            published_at=a.get("publishedAt") or "",
            provider="gnews",
        )
        for a in data["articles"]
    ]


def fetch_ddg_news(settings: Settings, category: str | None, query: str | None, limit: int) -> list[Article]:
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise ProviderError("DuckDuckGo skipped: ddgs not installed") from exc
    q = query or CATEGORY_QUERIES.get(category or "general", "top news today")
    try:
        rows = DDGS(timeout=int(settings.http_timeout)).news(q, max_results=limit * 2, timelimit="d")
        if not rows:  # nothing in the last day, widen to a week
            rows = DDGS(timeout=int(settings.http_timeout)).news(q, max_results=limit * 2, timelimit="w")
    except Exception as exc:
        raise ProviderError(f"DuckDuckGo news failed: {type(exc).__name__}") from exc
    return [
        Article(
            title=r.get("title") or "",
            description=r.get("body") or "",
            url=r.get("url") or "",
            source=r.get("source") or "",
            published_at=r.get("date") or "",
            provider="duckduckgo",
        )
        for r in rows or []
    ]


PROVIDERS = [
    ("NewsAPI", fetch_newsapi),
    ("GNews", fetch_gnews),
    ("DuckDuckGo News", fetch_ddg_news),
]


# ---------------------------------------------------------------- public entry

def get_news(settings: Settings, category: str | None = None, query: str | None = None,
             limit: int = 6) -> NewsResult:
    """Fetch news for a category or a free-text topic, walking the fallback chain."""
    cache = get_cache(settings.cache_ttl)
    key = f"q:{query.lower().strip()}" if query else f"c:{category or 'general'}"
    result = NewsResult()

    cached = cache.get(key)
    if cached:
        result.articles, result.provider, result.from_cache = cached["articles"], cached["provider"], True
        return result

    for name, fn in PROVIDERS:
        try:
            articles = _clean(fn(settings, category, query, limit))
        except ProviderError as exc:
            result.errors.append(str(exc))
            continue
        if not articles:
            result.errors.append(f"{name} returned no articles")
            continue
        result.articles, result.provider = articles, name
        cache.set(key, {"articles": articles, "provider": name})
        return result

    stale = cache.get_stale(key)
    if stale:
        ts, payload = stale
        age_min = int((time.time() - ts) / 60)
        result.articles = [dict(a, provider="stale-cache") for a in payload["articles"]]
        result.provider = f"cached copy from {age_min} min ago"
        result.stale = True
        result.errors.append("All live providers failed; showing last good result")
    return result


def format_published(ts: str) -> str:
    """Turn provider timestamps into a short readable form. Unparseable values pass through."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%b %d, %I:%M %p")
    except ValueError:
        return ts
