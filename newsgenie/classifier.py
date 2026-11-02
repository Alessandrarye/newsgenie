"""Query differentiation: decide whether a message is a news request or a general query.

Two layers:
  * Rules (always available, instant). Handles greetings, follow-ups about listed
    articles, and obvious category requests without spending an LLM call.
  * LLM structured output (when OPENAI_API_KEY is set). Handles ambiguous phrasing
    and rewrites follow-ups into standalone search queries using chat history.
If the LLM call fails for any reason, the rule result is used.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

Intent = Literal["greeting", "news_category", "news_topic", "follow_up", "general"]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "technology": ["tech", "technology", "ai", "artificial intelligence", "software", "apple", "google",
                   "microsoft", "nvidia", "openai", "chip", "semiconductor", "startup", "cyber", "gadget"],
    "business": ["finance", "financial", "business", "market", "markets", "stock", "stocks", "economy",
                 "economic", "fed", "federal reserve", "inflation", "earnings", "crypto", "bitcoin",
                 "wall street", "dow", "nasdaq", "s&p", "interest rate", "money"],
    "sports": ["sport", "sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball",
               "baseball", "hockey", "tennis", "golf", "olympics", "world series", "playoff", "score"],
    "science": ["science", "space", "nasa", "climate", "physics", "research"],
    "health": ["health", "medical", "medicine", "vaccine", "disease", "fda"],
    "entertainment": ["entertainment", "movie", "movies", "film", "music", "celebrity", "tv show", "streaming"],
}

NEWS_CUES = re.compile(
    r"\b(news|headlines?|latest|breaking|today'?s|this week|happening|update|updates|recent|"
    r"going on|current events|what'?s new|top stories)\b",
    re.IGNORECASE,
)
GREETING = re.compile(r"^\s*(hi|hello|hey|yo|good (morning|afternoon|evening)|thanks?( you)?|thank you|"
                      r"help|what can you do)\b[\s!.?]*$", re.IGNORECASE)
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "last": -1}
FOLLOW_UP = re.compile(
    r"\b(?:more (?:about|on)|expand on|explain|summari[sz]e|details? (?:on|about)|tell me about)\b.*?"
    r"(?:#\s*(\d+)|\b(?:article|story|headline|one|number|item)\s*(\d+)\b|\b("
    + "|".join(ORDINALS) + r")\b)",
    re.IGNORECASE,
)
FILLER = re.compile(
    r"\b(what'?s|what is|whats|the|latest|news|headlines?|on|about|regarding|for|any|recent|"
    r"breaking|give me|show me|tell me|get me|today'?s?|this week|updates?|happening|going on|"
    r"in|with|me|please|top|stories|story|current|events|new|are|there|anything)\b",
    re.IGNORECASE,
)


class Classification(BaseModel):
    intent: Intent = Field(description="greeting | news_category | news_topic | follow_up | general")
    category: str | None = Field(default=None, description="technology, business, sports, science, health, entertainment, or general")
    topic: str | None = Field(default=None, description="Specific news topic, e.g. 'Nvidia earnings'")
    article_index: int | None = Field(default=None, description="1-based index for follow_up, -1 for last")
    search_query: str | None = Field(default=None, description="Standalone web search query resolved from chat history")


def detect_category(text: str) -> str | None:
    t = f" {text.lower()} "
    best, hits = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        n = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", t))
        if n > hits:
            best, hits = cat, n
    return best


GENERIC_CATEGORY_WORDS = {"tech", "technology", "finance", "financial", "business", "market", "markets",
                          "economy", "sport", "sports", "science", "health", "entertainment", "general",
                          "world", "us", "u.s.", "national", "money", "stock", "stocks", "wall street"}


def _topic_remainder(text: str) -> str:
    """Strip filler words. Whatever is left is the subject the user asked about."""
    rest = FILLER.sub(" ", text)
    rest = re.sub(r"[^\w\s&.-]", " ", rest)
    words = [w for w in rest.split() if w.lower() not in GENERIC_CATEGORY_WORDS]
    return " ".join(words).strip(" .-")


def rule_classify(text: str, has_previous_articles: bool = False) -> Classification:
    text = text.strip()
    if GREETING.match(text):
        return Classification(intent="greeting")

    m = FOLLOW_UP.search(text)
    if m and has_previous_articles:
        num = m.group(1) or m.group(2)
        idx = int(num) if num else ORDINALS[m.group(3).lower()]
        return Classification(intent="follow_up", article_index=idx)

    category = detect_category(text)
    if NEWS_CUES.search(text):
        topic = _topic_remainder(text)
        # "latest tech news" -> category; "latest news on the Fed rate cut" -> topic
        if topic:
            return Classification(intent="news_topic", category=category, topic=topic, search_query=topic)
        return Classification(intent="news_category", category=category or "general")

    return Classification(intent="general", search_query=text)


SYSTEM = """You route messages for NewsGenie, a news and information assistant.
Classify the user's LATEST message using the chat history for context.

intent:
- greeting: hello, thanks, "what can you do"
- news_category: wants current headlines for a broad category (tech, finance/business, sports, science, health, entertainment, general)
- news_topic: wants recent news/developments about a specific subject, company, person, or event
- follow_up: asks for more about an article NewsGenie listed earlier (by number or position). Set article_index (1-based, -1 = last)
- general: anything else (facts, explanations, how-to, opinions about timeless topics)

Map finance, markets, economy to category "business".
For news_topic and general, write search_query as a standalone web query that resolves pronouns from history.
Previously listed articles available: {has_articles}"""


def llm_classify(llm, text: str, history: list[BaseMessage], has_previous_articles: bool) -> Classification:
    from langchain_core.messages import HumanMessage, SystemMessage
    structured = llm.with_structured_output(Classification)
    msgs = [SystemMessage(SYSTEM.format(has_articles=has_previous_articles))]
    msgs += history[-6:]  # recent context only; keeps latency and cost down
    msgs.append(HumanMessage(text))
    return structured.invoke(msgs)


def classify(text: str, history: list[BaseMessage], has_previous_articles: bool, llm=None) -> tuple[Classification, str]:
    """Return (classification, method) where method is 'rules' or 'llm'."""
    rules = rule_classify(text, has_previous_articles)
    # Cheap paths that rules handle reliably
    if rules.intent in {"greeting", "follow_up"} or llm is None:
        return rules, "rules"
    try:
        result = llm_classify(llm, text, history, has_previous_articles)
        if result.intent == "follow_up" and not has_previous_articles:
            result.intent = "general"
        if result.intent == "news_category" and not result.category:
            result.category = rules.category or "general"
        return result, "llm"
    except Exception:
        return rules, "rules (llm failed)"
