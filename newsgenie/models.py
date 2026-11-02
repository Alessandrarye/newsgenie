"""Shared data shapes."""

from __future__ import annotations

from typing import TypedDict


class Article(TypedDict, total=False):
    title: str
    description: str
    url: str
    source: str
    published_at: str
    provider: str          # newsapi | gnews | duckduckgo | stale-cache
    reliability: float     # 0..1, set by reliability.score_articles
    reliability_label: str # High | Medium | Low | Unknown
    flags: list[str]       # e.g. ["clickbait headline", "satire site"]
    corroborated_by: int   # other outlets carrying a similar story


class SearchResult(TypedDict, total=False):
    title: str
    url: str
    snippet: str
