"""LangGraph workflow for NewsGenie.

    START
      │
   classify ──greeting──────────────────────────────► greet ──► END
      │
      ├─news_category / news_topic─► fetch_news ─► filter_news ─┐
      │                                                         │ no articles, or topic
      │                                                         ▼ (needs related reading)
      ├─general / follow_up──────────────────────────────► web_search
      │                                                         │
      │                                  articles found ────────┤
      ▼                                                         ▼
                                                             respond ──► END

Conversation memory: an InMemorySaver checkpointer keyed by thread_id keeps
`messages` (chat history) and `last_articles` (for "tell me more about #2")
across turns. Per-turn fields are reset in `classify`.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from newsgenie import responder
from newsgenie.classifier import classify as classify_query
from newsgenie.config import Settings, load_settings
from newsgenie.llm import get_llm
from newsgenie.models import Article, SearchResult
from newsgenie.tools.http import ProviderError
from newsgenie.tools.news_api import get_news
from newsgenie.tools.reliability import filter_and_rank
from newsgenie.tools.web_search import web_search


class NewsGenieState(TypedDict, total=False):
    # inputs (set by the UI each turn)
    user_input: str
    selected_category: str | None   # set when the user clicks a sidebar category
    max_articles: int
    show_reliability: bool
    # persisted across turns by the checkpointer
    messages: Annotated[list[BaseMessage], add_messages]
    last_articles: list[Article]
    # per-turn working state
    intent: str
    category: str | None
    topic: str | None
    search_query: str | None
    article_index: int | None
    articles: list[Article]
    hidden_articles: list[Article]
    news_provider: str
    news_stale: bool
    web_results: list[SearchResult]
    errors: list[str]
    trace: list[str]
    response: str


PER_TURN_RESET: dict[str, Any] = {
    "intent": "", "category": None, "topic": None, "search_query": None, "article_index": None,
    "articles": [], "hidden_articles": [], "news_provider": "", "news_stale": False,
    "web_results": [], "errors": [], "trace": [], "response": "",
}


def build_graph(settings: Settings | None = None, checkpointer=None):
    settings = settings or load_settings()
    llm = get_llm(settings)

    # ------------------------------------------------------------- nodes

    def classify(state: NewsGenieState) -> dict:
        text = state.get("user_input", "").strip()
        history = state.get("messages", [])
        has_prev = bool(state.get("last_articles"))
        update = dict(PER_TURN_RESET)
        update["messages"] = [HumanMessage(text)]

        if state.get("selected_category"):  # sidebar button: no classification needed
            update.update(intent="news_category", category=state["selected_category"],
                          trace=[f"classify: sidebar selection -> news_category ({state['selected_category']})"])
            return update

        result, method = classify_query(text, history, has_prev, llm)
        update.update(
            intent=result.intent,
            category=result.category,
            topic=result.topic,
            search_query=result.search_query or result.topic or text,
            article_index=result.article_index,
            trace=[f"classify ({method}): intent={result.intent}"
                   + (f", category={result.category}" if result.category else "")
                   + (f", topic='{result.topic}'" if result.topic else "")],
        )
        return update

    def greet(state: NewsGenieState) -> dict:
        text = responder.GREETING_TEXT
        return {"response": text, "messages": [AIMessage(text)], "trace": state["trace"] + ["greet: canned reply"]}

    def fetch_news(state: NewsGenieState) -> dict:
        limit = state.get("max_articles", 6)
        query = state.get("topic") if state["intent"] == "news_topic" else None
        res = get_news(settings, category=state.get("category"), query=query, limit=limit * 2)
        where = "cache" if res.from_cache else res.provider
        step = f"fetch_news: {len(res.articles)} articles from {where}"
        if res.errors:
            step += f" (after {len(res.errors)} fallback event(s))"
        return {
            "articles": res.articles, "news_provider": res.provider, "news_stale": res.stale,
            "errors": state["errors"] + res.errors, "trace": state["trace"] + [step],
        }

    def filter_news(state: NewsGenieState) -> dict:
        kept, hidden = filter_and_rank(state["articles"], settings.min_reliability, state.get("max_articles", 6))
        return {
            "articles": kept, "hidden_articles": hidden,
            "trace": state["trace"] + [f"filter_news: kept {len(kept)}, hid {len(hidden)} below "
                                       f"{settings.min_reliability} reliability"],
        }

    def search_web(state: NewsGenieState) -> dict:
        intent = state["intent"]
        if intent == "follow_up":
            idx = state.get("article_index") or 1
            prev = state.get("last_articles", [])
            article = prev[idx - 1] if 0 < idx <= len(prev) else (prev[-1] if idx == -1 and prev else None)
            query = article["title"] if article else state["user_input"]
        elif intent in {"news_category", "news_topic"}:
            base = state.get("topic") or responder.CATEGORY_LABELS.get(state.get("category") or "", state.get("category") or "")
            query = f"{base} news" if not state["articles"] else f"{base} explained background"
        else:
            query = state.get("search_query") or state["user_input"]
        try:
            results = web_search(settings, query, limit=5 if intent == "general" else 3)
            step = f"web_search: {len(results)} results for '{query}'"
            errors = state["errors"]
        except ProviderError as exc:
            results, step, errors = [], f"web_search: failed ({exc})", state["errors"] + [str(exc)]
        return {"web_results": results, "errors": errors, "trace": state["trace"] + [step]}

    def respond(state: NewsGenieState) -> dict:
        intent = state["intent"]
        show_rel = state.get("show_reliability", True)
        update: dict = {}

        if intent in {"news_category", "news_topic"}:
            label = state.get("topic") or responder.CATEGORY_LABELS.get(state.get("category") or "general",
                                                                         state.get("category") or "top")
            if state["articles"]:
                text, used = responder.news_reply(llm, state["articles"], label, state["news_provider"],
                                                  state.get("news_stale", False), state.get("web_results", []), show_rel)
                update["last_articles"] = state["articles"]  # remember for follow-ups
            else:
                text, used = responder.no_news_reply(label, state["errors"], state.get("web_results", [])), False

        elif intent == "follow_up":
            idx = state.get("article_index") or 1
            prev = state.get("last_articles", [])
            article = prev[idx - 1] if 0 < idx <= len(prev) else (prev[-1] if idx == -1 and prev else None)
            if article is None:
                text, used = (f"I only have {len(prev)} article(s) from the last list, so I can't find #{idx}. "
                              "Try a number from the list above."), False
            else:
                text, used = responder.follow_up_reply(llm, article, state.get("web_results", []))

        else:  # general
            history = state.get("messages", [])[:-1]  # exclude the message we just added
            text, used = responder.general_reply(llm, state["user_input"], history, state.get("web_results", []))

        mode = "LLM" if used else ("template (no LLM key)" if llm is None else "template (LLM failed)")
        update.update(response=text, messages=[AIMessage(text)], trace=state["trace"] + [f"respond: {mode}"])
        return update

    # ------------------------------------------------------------- routing

    def route_after_classify(state: NewsGenieState) -> str:
        return {"greeting": "greet", "news_category": "fetch_news", "news_topic": "fetch_news"}.get(
            state["intent"], "search_web")

    def route_after_filter(state: NewsGenieState) -> str:
        # Fallback: nothing usable from news APIs -> try the web.
        # Topic requests also get a few background links ("additional external resources").
        if not state["articles"] or state["intent"] == "news_topic":
            return "search_web"
        return "respond"

    g = StateGraph(NewsGenieState)
    g.add_node("classify", classify)
    g.add_node("greet", greet)
    g.add_node("fetch_news", fetch_news)
    g.add_node("filter_news", filter_news)
    g.add_node("search_web", search_web)
    g.add_node("respond", respond)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route_after_classify, ["greet", "fetch_news", "search_web"])
    g.add_edge("fetch_news", "filter_news")
    g.add_conditional_edges("filter_news", route_after_filter, ["search_web", "respond"])
    g.add_edge("search_web", "respond")
    g.add_edge("greet", END)
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer if checkpointer is not None else InMemorySaver())


def ask(graph, text: str, thread_id: str, selected_category: str | None = None,
        max_articles: int = 6, show_reliability: bool = True) -> NewsGenieState:
    """Convenience wrapper used by the UI, CLI, and tests."""
    return graph.invoke(
        {"user_input": text, "selected_category": selected_category,
         "max_articles": max_articles, "show_reliability": show_reliability},
        config={"configurable": {"thread_id": thread_id}},
    )
