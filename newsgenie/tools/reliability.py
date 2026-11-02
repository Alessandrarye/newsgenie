"""Source reliability and misinformation filtering.

This is a transparent, rule-based scorer, not a fact checker. It combines three
signals that are easy to explain in a report and easy to audit:

    1. Source reputation  - curated allow/deny lists by domain
    2. Headline signals   - clickbait and sensationalism patterns
    3. Corroboration      - how many *other* outlets carry a similar headline

Score = 0.55 * reputation + 0.25 * headline + 0.20 * corroboration, clipped to 0..1.
Articles under MIN_RELIABILITY_SCORE are hidden (the UI can show them on request).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from newsgenie.models import Article

# Wire services, papers of record, and established beat outlets
HIGH_TRUST = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org", "pbs.org",
    "nytimes.com", "washingtonpost.com", "wsj.com", "bloomberg.com", "ft.com",
    "economist.com", "theguardian.com", "axios.com", "cnbc.com", "marketwatch.com",
    "barrons.com", "forbes.com", "fortune.com", "businessinsider.com", "politico.com",
    "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com", "engadget.com",
    "zdnet.com", "cnet.com", "technologyreview.com", "ieee.org", "nature.com",
    "science.org", "scientificamerican.com", "statnews.com", "espn.com", "theathletic.com",
    "cbssports.com", "nbcsports.com", "si.com", "cbsnews.com", "nbcnews.com", "abcnews.go.com",
    "cnn.com", "foxnews.com", "foxbusiness.com", "usatoday.com", "latimes.com", "yahoo.com",
}

# Known satire (not misinformation, but should never be presented as news)
SATIRE = {"theonion.com", "babylonbee.com", "clickhole.com", "thebeaverton.com"}

# Sites repeatedly rated as low-credibility by independent media-rating orgs.
# Keep this short and defensible; extend it with a source you can cite.
LOW_TRUST = {
    "infowars.com", "naturalnews.com", "beforeitsnews.com", "worldtruth.tv",
    "yournewswire.com", "newspunch.com", "thegatewaypundit.com",
}

CLICKBAIT_PATTERNS = [
    r"you won'?t believe", r"what happens next", r"shocking", r"\bmind[- ]?blowing\b",
    r"doctors hate", r"this one trick", r"goes viral", r"\bslams\b", r"\bdestroys\b",
    r"miracle cure", r"they don'?t want you to know", r"!!+",
]
_clickbait_re = re.compile("|".join(CLICKBAIT_PATTERNS), re.IGNORECASE)
_word_re = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "at", "with", "as", "by", "after", "from"}


def domain_of(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _matches(domain: str, group: set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in group)


def reputation(url: str) -> tuple[float, list[str]]:
    d = domain_of(url)
    if not d:
        return 0.4, ["unknown source"]
    if _matches(d, SATIRE):
        return 0.0, ["satire site"]
    if _matches(d, LOW_TRUST):
        return 0.05, ["low-credibility source"]
    if _matches(d, HIGH_TRUST):
        return 1.0, []
    return 0.5, []  # unknown is neutral, not penalized hard


def headline_quality(title: str) -> tuple[float, list[str]]:
    flags: list[str] = []
    score = 1.0
    if _clickbait_re.search(title or ""):
        score -= 0.6
        flags.append("clickbait headline")
    letters = [c for c in title if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6 and len(letters) > 12:
        score -= 0.4
        flags.append("all-caps headline")
    return max(score, 0.0), flags


def _tokens(text: str) -> set[str]:
    return {w for w in _word_re.findall((text or "").lower()) if w not in _STOP and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similar(a: set[str], b: set[str]) -> bool:
    """Same story, possibly worded differently (used for corroboration)."""
    return _jaccard(a, b) >= 0.25


def _duplicate(a: set[str], b: set[str]) -> bool:
    """Nearly the same headline (syndicated or reworded copy). Shown once."""
    return _jaccard(a, b) >= 0.5


def score_articles(articles: list[Article]) -> list[Article]:
    """Annotate every article with reliability, label, flags, and corroboration count."""
    toks = [_tokens(a.get("title", "")) for a in articles]
    doms = [domain_of(a.get("url", "")) or a.get("source", "") for a in articles]
    scored: list[Article] = []
    for i, a in enumerate(articles):
        rep, f1 = reputation(a.get("url", ""))
        head, f2 = headline_quality(a.get("title", ""))
        others = {doms[j] for j in range(len(articles)) if j != i and doms[j] != doms[i] and _similar(toks[i], toks[j])}
        corr = min(len(others) / 2, 1.0)  # 2+ independent outlets = full credit
        score = round(min(max(0.55 * rep + 0.25 * head + 0.20 * corr, 0.0), 1.0), 2)
        label = "High" if score >= 0.7 else "Medium" if score >= 0.45 else "Low"
        scored.append(dict(a, reliability=score, reliability_label=label, flags=f1 + f2, corroborated_by=len(others)))
    return scored


def filter_and_rank(articles: list[Article], min_score: float, limit: int) -> tuple[list[Article], list[Article]]:
    """Return (kept, hidden). Kept is sorted by reliability, then recency."""
    scored = score_articles(articles)
    kept = [a for a in scored if a["reliability"] >= min_score and "satire site" not in a["flags"]]
    hidden = [a for a in scored if a not in kept]
    kept.sort(key=lambda a: (a["reliability"], a.get("published_at", "")), reverse=True)

    # Collapse duplicates: keep the highest-ranked copy of each story. The
    # dropped copies are already reflected in its "also reported by" count.
    unique: list[Article] = []
    seen: list[set[str]] = []
    for a in kept:
        t = _tokens(a.get("title", ""))
        if any(_duplicate(t, s) for s in seen):
            continue
        seen.append(t)
        unique.append(a)
    return unique[:limit], hidden
