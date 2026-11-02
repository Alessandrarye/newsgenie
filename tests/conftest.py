import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from newsgenie.config import Settings  # noqa: E402
from newsgenie.tools import news_api  # noqa: E402


@pytest.fixture
def no_key_settings():
    return Settings(openai_api_key="", openai_model="test", newsapi_key="", gnews_api_key="",
                    cache_ttl=600, http_timeout=2, min_reliability=0.35)


@pytest.fixture(autouse=True)
def fresh_news_cache():
    news_api._cache = None
    yield
    news_api._cache = None


def make_articles():
    return [
        {"title": "Fed holds interest rates steady as inflation cools", "url": "https://www.reuters.com/a",
         "source": "Reuters", "description": "The Federal Reserve kept rates unchanged.", "published_at": "2026-10-28T14:00:00Z"},
        {"title": "Federal Reserve holds rates steady, signals patience", "url": "https://apnews.com/b",
         "source": "AP", "description": "Policymakers held rates.", "published_at": "2026-10-28T13:00:00Z"},
        {"title": "You WON'T BELIEVE what the Fed just did!!!", "url": "https://randomblog.xyz/c",
         "source": "Random Blog", "description": "Clickbait.", "published_at": "2026-10-28T12:00:00Z"},
        {"title": "Area man declares himself chairman of the Federal Reserve", "url": "https://theonion.com/d",
         "source": "The Onion", "description": "Satire.", "published_at": "2026-10-28T11:00:00Z"},
        {"title": "Nasdaq rises as tech earnings beat estimates", "url": "https://www.cnbc.com/e",
         "source": "CNBC", "description": "Stocks climbed.", "published_at": "2026-10-28T10:00:00Z"},
    ]
