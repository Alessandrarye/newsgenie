from conftest import make_articles

from newsgenie.tools.reliability import filter_and_rank, headline_quality, reputation, score_articles


def test_reputation_tiers():
    assert reputation("https://www.reuters.com/x")[0] == 1.0
    assert reputation("https://news.bbc.co.uk/x")[0] == 1.0  # subdomain match
    assert reputation("https://theonion.com/x")[1] == ["satire site"]
    assert reputation("https://unknownsite.io/x")[0] == 0.5


def test_clickbait_flagged():
    score, flags = headline_quality("You WON'T BELIEVE what the Fed just did!!!")
    assert score < 0.5 and "clickbait headline" in flags


def test_corroboration_counts_other_outlets():
    scored = {a["source"]: a for a in score_articles(make_articles())}
    assert scored["Reuters"]["corroborated_by"] >= 1
    assert scored["Reuters"]["reliability_label"] == "High"


def test_filter_hides_satire_and_low_scores():
    kept, hidden = filter_and_rank(make_articles(), min_score=0.35, limit=10)
    kept_sources = [a["source"] for a in kept]
    assert "The Onion" not in kept_sources
    assert any(a["source"] == "The Onion" for a in hidden)
    assert kept[0]["reliability"] >= kept[-1]["reliability"]  # ranked


def test_near_duplicate_headlines_shown_once():
    arts = [
        {"title": "AI stocks just lost $5 trillion, but the stock market's sweetest stretch might be now",
         "url": "https://www.cnbc.com/x", "source": "CNBC"},
        {"title": "AI stocks just lost $5 trillion, but history says the stock market's sweetest stretch starts now",
         "url": "https://biztoc.com/y", "source": "Biztoc.com"},
        {"title": "Fed holds interest rates steady as inflation cools", "url": "https://www.reuters.com/z",
         "source": "Reuters"},
    ]
    kept, _ = filter_and_rank(arts, min_score=0.35, limit=10)
    titles = [a["title"] for a in kept]
    assert len(kept) == 2
    assert sum("5 trillion" in t for t in titles) == 1
    cnbc = next(a for a in kept if "5 trillion" in a["title"])
    assert cnbc["source"] == "CNBC" and cnbc["corroborated_by"] == 1  # higher-trust copy kept


def test_reworded_coverage_is_not_collapsed():
    kept, _ = filter_and_rank(make_articles(), min_score=0.35, limit=10)
    sources = {a["source"] for a in kept}
    assert {"Reuters", "AP"} <= sources  # same story, different wording: both kept
