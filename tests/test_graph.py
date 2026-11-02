"""End-to-end workflow tests with all network calls replaced by fakes."""

import uuid

import pytest
from conftest import make_articles

from newsgenie import graph as graph_mod
from newsgenie.classifier import Classification
from newsgenie.tools.http import ProviderError
from newsgenie.tools.news_api import NewsResult


@pytest.fixture
def fake_net(monkeypatch):
    calls = {"news": [], "web": []}

    def fake_news(settings, category=None, query=None, limit=6):
        calls["news"].append((category, query))
        return NewsResult(articles=make_articles(), provider="NewsAPI")

    def fake_web(settings, query, limit=5):
        calls["web"].append(query)
        return [{"title": f"Result for {query}", "url": "https://example.org/r", "snippet": "A useful snippet."}]

    monkeypatch.setattr(graph_mod, "get_news", fake_news)
    monkeypatch.setattr(graph_mod, "web_search", fake_web)
    return calls


def tid():
    return str(uuid.uuid4())


def test_greeting_skips_all_tools(fake_net, no_key_settings):
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "hello", tid())
    assert "NewsGenie" in out["response"]
    assert fake_net["news"] == [] and fake_net["web"] == []


def test_sidebar_category_goes_straight_to_news(fake_net, no_key_settings):
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "Show me finance headlines", tid(), selected_category="business")
    assert out["intent"] == "news_category"
    assert fake_net["news"] == [("business", None)]
    assert "Reuters" in out["response"] and "The Onion" not in out["response"]
    assert any(a["source"] == "The Onion" for a in out["hidden_articles"])


def test_follow_up_uses_remembered_articles(fake_net, no_key_settings):
    g = graph_mod.build_graph(no_key_settings)
    t = tid()
    first = graph_mod.ask(g, "latest finance news", t)
    second_title = first["last_articles"][1]["title"]
    out = graph_mod.ask(g, "tell me more about #2", t)
    assert out["intent"] == "follow_up"
    assert second_title in out["response"]
    assert len(out["messages"]) == 4  # 2 user + 2 assistant, memory persisted


def test_threads_are_isolated(fake_net, no_key_settings):
    g = graph_mod.build_graph(no_key_settings)
    graph_mod.ask(g, "latest finance news", tid())
    out = graph_mod.ask(g, "tell me more about #2", tid())  # new thread, nothing remembered
    assert out["intent"] != "follow_up"


def test_general_question_uses_web_search(fake_net, no_key_settings):
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "what is a black hole", tid())
    assert out["intent"] == "general"
    assert fake_net["web"] == ["what is a black hole"]
    assert "example.org" in out["response"]


def test_news_falls_back_to_web_when_no_articles(monkeypatch, no_key_settings):
    monkeypatch.setattr(graph_mod, "get_news",
                        lambda *a, **k: NewsResult(errors=["NewsAPI down", "GNews down", "DuckDuckGo down"]))
    monkeypatch.setattr(graph_mod, "web_search",
                        lambda s, q, limit=5: [{"title": "Backup", "url": "https://example.org/b", "snippet": "x"}])
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "latest sports news", tid())
    assert "couldn't find reliable" in out["response"]
    assert "example.org/b" in out["response"]
    assert len(out["errors"]) == 3


def test_everything_down_still_answers(monkeypatch, no_key_settings):
    monkeypatch.setattr(graph_mod, "get_news", lambda *a, **k: NewsResult(errors=["all down"]))

    def broken(*a, **k):
        raise ProviderError("Web search failed: ConnectError")

    monkeypatch.setattr(graph_mod, "web_search", broken)
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "latest tech news", tid())
    assert out["response"]  # user still gets a clear message
    assert any("Web search failed" in e for e in out["errors"])


class StubLLM:
    """Mimics the two ChatOpenAI methods the app uses."""

    class _Msg:
        def __init__(self, content):
            self.content = content

    def __init__(self, classification):
        self.classification = classification

    def with_structured_output(self, _schema):
        outer = self

        class _S:
            def invoke(self, _msgs):
                return outer.classification
        return _S()

    def invoke(self, _msgs):
        return self._Msg("Stub briefing citing [1].")


def test_llm_path(monkeypatch, fake_net, no_key_settings):
    stub = StubLLM(Classification(intent="news_topic", category="business", topic="Fed rates",
                                  search_query="Fed rates"))
    monkeypatch.setattr(graph_mod, "get_llm", lambda s: stub)
    g = graph_mod.build_graph(no_key_settings)
    out = graph_mod.ask(g, "what did the central bank do?", tid())
    assert out["intent"] == "news_topic"
    assert "Stub briefing" in out["response"]
    assert "Related reading" in out["response"]  # topic requests add web context
    assert any("classify (llm)" in t for t in out["trace"])
