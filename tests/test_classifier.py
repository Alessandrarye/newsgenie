import pytest

from newsgenie.classifier import classify, rule_classify


@pytest.mark.parametrize("text,intent,category", [
    ("hi", "greeting", None),
    ("thanks!", "greeting", None),
    ("latest tech news", "news_category", "technology"),
    ("give me finance headlines", "news_category", "business"),
    ("what's happening in sports", "news_category", "sports"),
    ("top stories", "news_category", "general"),
    ("what is a black hole", "general", None),
    ("how do I convert Celsius to Fahrenheit", "general", None),
])
def test_rule_intents(text, intent, category):
    r = rule_classify(text)
    assert r.intent == intent
    if category:
        assert r.category == category


def test_topic_extraction_keeps_entities():
    r = rule_classify("any news about Nvidia earnings")
    assert r.intent == "news_topic"
    assert r.topic == "Nvidia earnings"


def test_follow_up_requires_previous_articles():
    assert rule_classify("tell me more about #2", has_previous_articles=True).article_index == 2
    assert rule_classify("explain the second article", has_previous_articles=True).article_index == 2
    assert rule_classify("tell me more about #2", has_previous_articles=False).intent != "follow_up"


def test_llm_failure_falls_back_to_rules():
    class BrokenLLM:
        def with_structured_output(self, _):
            raise RuntimeError("API down")

    result, method = classify("what is a black hole", [], False, llm=BrokenLLM())
    assert result.intent == "general"
    assert method == "rules (llm failed)"
