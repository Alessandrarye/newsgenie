from conftest import make_articles

from newsgenie.tools import news_api
from newsgenie.tools.http import ProviderError


def _fail(name):
    def fn(*_a, **_k):
        raise ProviderError(f"{name} down")
    return fn


def _ok(name):
    def fn(*_a, **_k):
        return [dict(a, provider=name) for a in make_articles()]
    return fn


def test_falls_through_to_next_provider(monkeypatch, no_key_settings):
    monkeypatch.setattr(news_api, "PROVIDERS", [("NewsAPI", _fail("NewsAPI")), ("GNews", _fail("GNews")),
                                                ("DuckDuckGo News", _ok("duckduckgo"))])
    res = news_api.get_news(no_key_settings, category="business")
    assert res.provider == "DuckDuckGo News"
    assert len(res.errors) == 2 and res.articles


def test_second_call_is_served_from_cache(monkeypatch, no_key_settings):
    calls = {"n": 0}

    def counting(*_a, **_k):
        calls["n"] += 1
        return make_articles()

    monkeypatch.setattr(news_api, "PROVIDERS", [("NewsAPI", counting)])
    news_api.get_news(no_key_settings, category="technology")
    res = news_api.get_news(no_key_settings, category="technology")
    assert res.from_cache and calls["n"] == 1


def test_stale_cache_when_everything_fails(monkeypatch, no_key_settings):
    monkeypatch.setattr(news_api, "PROVIDERS", [("NewsAPI", _ok("newsapi"))])
    news_api.get_news(no_key_settings, category="sports")
    news_api.get_cache(600)._data.clear()  # simulate TTL expiry
    monkeypatch.setattr(news_api, "PROVIDERS", [("NewsAPI", _fail("NewsAPI"))])
    res = news_api.get_news(no_key_settings, category="sports")
    assert res.stale and res.articles and res.articles[0]["provider"] == "stale-cache"


def test_total_failure_returns_empty_with_errors(monkeypatch, no_key_settings):
    monkeypatch.setattr(news_api, "PROVIDERS", [("NewsAPI", _fail("NewsAPI")), ("GNews", _fail("GNews"))])
    res = news_api.get_news(no_key_settings, category="health")
    assert res.articles == [] and len(res.errors) == 2


def test_missing_keys_are_reported_not_crashed(no_key_settings):
    for fn in (news_api.fetch_newsapi, news_api.fetch_gnews):
        try:
            fn(no_key_settings, "technology", None, 5)
        except ProviderError as exc:
            assert "not set" in str(exc)
        else:
            raise AssertionError("expected ProviderError")
