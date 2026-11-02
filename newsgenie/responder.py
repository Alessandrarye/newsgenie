"""Turns retrieved articles and search results into the assistant's reply.

Every function has an LLM path and a template path. The template path runs when
no key is configured or the LLM call fails, so the user always gets an answer.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from newsgenie.models import Article, SearchResult
from newsgenie.tools.news_api import format_published

CATEGORY_LABELS = {"business": "finance", "general": "top"}

GREETING_TEXT = (
    "Hi, I'm **NewsGenie**. I can do two things:\n\n"
    "1. **Curated news.** Pick a category in the sidebar or ask things like "
    "*\"latest tech news\"* or *\"any news on the Fed rate decision?\"*. "
    "I rank stories by source reliability and hide low-credibility ones.\n"
    "2. **General questions.** Ask me anything, and I'll answer with web sources where I can.\n\n"
    "After I list headlines, you can say *\"tell me more about #2\"*."
)

BADGE = {"High": "🟢", "Medium": "🟡", "Low": "🔴", "Unknown": "⚪"}


def article_list_md(articles: list[Article], show_reliability: bool = True) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        meta = [a.get("source") or "unknown source"]
        when = format_published(a.get("published_at", ""))
        if when:
            meta.append(when)
        if show_reliability and "reliability" in a:
            meta.append(f"{BADGE.get(a.get('reliability_label', 'Unknown'))} {a['reliability_label']} reliability")
            if a.get("corroborated_by"):
                meta.append(f"also reported by {a['corroborated_by']} other outlet(s)")
        lines.append(f"{i}. **[{a['title']}]({a['url']})**  \n   _{' · '.join(meta)}_")
    return "\n".join(lines)


def _clip(title: str, n: int = 110) -> str:
    """Some search results come back with very long or run-together titles."""
    title = " ".join((title or "").split()).replace("[", "(").replace("]", ")")
    return title if len(title) <= n else title[: n - 3].rstrip() + "..."


def search_list_md(results: list[SearchResult]) -> str:
    return "\n".join(f"- [{_clip(r['title'])}]({r['url']})" for r in results)


def numbered_sources_md(results: list[SearchResult]) -> str:
    """Numbered list so the [n] citations in the answer line up with the links."""
    return "\n".join(f"{i}. [{_clip(r['title'])}]({r['url']})" for i, r in enumerate(results, 1))


def _context_block(articles: list[Article]) -> str:
    return "\n".join(
        f"[{i}] {a['title']} ({a.get('source', '')}): {a.get('description', '')[:300]}"
        for i, a in enumerate(articles, 1)
    )


def _web_block(results: list[SearchResult]) -> str:
    return "\n".join(f"[{i}] {r['title']}: {r.get('snippet', '')[:300]} ({r['url']})" for i, r in enumerate(results, 1))


# ------------------------------------------------------------------ news

def news_reply(llm, articles: list[Article], label: str, provider: str, stale: bool,
               web_results: list[SearchResult], show_reliability: bool) -> tuple[str, bool]:
    """Return (markdown, used_llm)."""
    header = f"### {label.title()} headlines"
    note = f"_Source: {provider}._"
    if stale:
        note = f"⚠️ _Live news sources are unavailable, so this is a {provider}._"
    body = article_list_md(articles, show_reliability)

    briefing, used = "", False
    if llm is not None:
        try:
            msg = llm.invoke([
                SystemMessage("You are NewsGenie. Write a 2-3 sentence neutral briefing of these headlines. "
                              "Reference stories by their [number]. Do not add facts that are not in the text."),
                HumanMessage(_context_block(articles)),
            ])
            briefing, used = msg.content.strip(), True
        except Exception:
            briefing = ""
    parts = [header]
    if briefing:
        parts.append(briefing)
    parts += [body, note]
    if web_results:
        parts.append("**Related reading**\n\n" + search_list_md(web_results[:3]))
    return "\n\n".join(parts), used


def no_news_reply(label: str, errors: list[str], web_results: list[SearchResult]) -> str:
    text = (f"I couldn't find reliable {label} news right now. "
            "The news services either failed or returned nothing that passed the reliability filter.")
    if web_results:
        text += "\n\nHere are some web results that may help instead:\n\n" + search_list_md(web_results)
    else:
        text += " Please try again in a minute, or pick a different category."
    return text


# ------------------------------------------------------------------ general

def general_reply(llm, question: str, history: list[BaseMessage], web_results: list[SearchResult]) -> tuple[str, bool]:
    if llm is not None:
        try:
            system = ("You are NewsGenie, a concise, accurate assistant. Answer the user's question. "
                      "If web results are provided, ground your answer in them and cite as [n]. "
                      "If they are missing or irrelevant, answer from general knowledge and say so briefly. "
                      "Keep answers under 200 words unless asked for more.")
            ctx = f"Web results:\n{_web_block(web_results)}" if web_results else "Web results: none available."
            msgs = [SystemMessage(system)] + history[-8:] + [HumanMessage(f"{question}\n\n{ctx}")]
            answer = llm.invoke(msgs).content.strip()
            if web_results:
                answer += "\n\n**Sources**\n\n" + numbered_sources_md(web_results)
            return answer, True
        except Exception:
            pass
    if web_results:
        top = web_results[0]
        text = (f"Here's what I found on the web for **{question}**:\n\n"
                f"> {top.get('snippet', '')}\n\nSource: [{_clip(top['title'])}]({top['url']})")
        if len(web_results) > 1:
            text += "\n\n**More results**\n\n" + search_list_md(web_results[1:])
        return text, False
    return ("I couldn't reach my answer engine or web search just now, so I can't answer that reliably. "
            "Check the service status in the sidebar and try again."), False


# ------------------------------------------------------------------ follow-up

def follow_up_reply(llm, article: Article, web_results: list[SearchResult]) -> tuple[str, bool]:
    head = f"### {article['title']}\n_{article.get('source', '')}_ · [Read the original]({article['url']})"
    if llm is not None:
        try:
            msg = llm.invoke([
                SystemMessage("Explain this news story in 4-6 sentences for a general reader: what happened, "
                              "why it matters, and what to watch next. Use only the provided text; cite web "
                              "results as [n]. Say if details are unconfirmed."),
                HumanMessage(f"Article: {article['title']}\n{article.get('description', '')}\n\n"
                             f"Related web results:\n{_web_block(web_results)}"),
            ])
            text = f"{head}\n\n{msg.content.strip()}"
            if web_results:
                text += "\n\n**Related coverage**\n\n" + numbered_sources_md(web_results)
            return text, True
        except Exception:
            pass
    text = f"{head}\n\n{article.get('description') or 'No summary was provided by the source.'}"
    if web_results:
        text += "\n\n**Related coverage**\n\n" + search_list_md(web_results)
    return text, False
