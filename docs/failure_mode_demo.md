# NewsGenie failure-mode demo (all external services unreachable)

Generated October 28, 2026 at 08:32 PM. Configured services: OpenAI (LLM) off, NewsAPI off, GNews (backup) off, DuckDuckGo search (no key) on.


---

## Technology headlines (sidebar button)

**User:** Show me the latest technology headlines

**Workflow trace:** classify: sidebar selection -> news_category (technology) → fetch_news: 0 articles from none (after 3 fallback event(s)) → filter_news: kept 0, hid 0 below 0.35 reliability → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (1.3s)

**Fallback events:** NewsAPI skipped: NEWSAPI_KEY not set; GNews skipped: GNEWS_API_KEY not set; DuckDuckGo news failed: DDGSException; Web search failed: DDGSException


**NewsGenie:**

I couldn't find reliable technology news right now. The news services either failed or returned nothing that passed the reliability filter. Please try again in a minute, or pick a different category.


---

## Finance headlines (sidebar button)

**User:** Show me the latest finance headlines

**Workflow trace:** classify: sidebar selection -> news_category (business) → fetch_news: 0 articles from none (after 3 fallback event(s)) → filter_news: kept 0, hid 0 below 0.35 reliability → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (1.7s)

**Fallback events:** NewsAPI skipped: NEWSAPI_KEY not set; GNews skipped: GNEWS_API_KEY not set; DuckDuckGo news failed: DDGSException; Web search failed: DDGSException


**NewsGenie:**

I couldn't find reliable finance news right now. The news services either failed or returned nothing that passed the reliability filter. Please try again in a minute, or pick a different category.


---

## Sports headlines (sidebar button)

**User:** Show me the latest sports headlines

**Workflow trace:** classify: sidebar selection -> news_category (sports) → fetch_news: 0 articles from none (after 3 fallback event(s)) → filter_news: kept 0, hid 0 below 0.35 reliability → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (1.3s)

**Fallback events:** NewsAPI skipped: NEWSAPI_KEY not set; GNews skipped: GNEWS_API_KEY not set; DuckDuckGo news failed: DDGSException; Web search failed: DDGSException


**NewsGenie:**

I couldn't find reliable sports news right now. The news services either failed or returned nothing that passed the reliability filter. Please try again in a minute, or pick a different category.


---

## Follow-up on a listed article

**User:** tell me more about #1

**Workflow trace:** classify (rules): intent=general → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (0.8s)

**Fallback events:** Web search failed: DDGSException


**NewsGenie:**

I couldn't reach my answer engine or web search just now, so I can't answer that reliably. Check the service status in the sidebar and try again.


---

## Topic news typed in chat

**User:** any news about Nvidia?

**Workflow trace:** classify (rules): intent=news_topic, category=technology, topic='Nvidia' → fetch_news: 0 articles from none (after 3 fallback event(s)) → filter_news: kept 0, hid 0 below 0.35 reliability → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (1.2s)

**Fallback events:** NewsAPI skipped: NEWSAPI_KEY not set; GNews skipped: GNEWS_API_KEY not set; DuckDuckGo news failed: DDGSException; Web search failed: DDGSException


**NewsGenie:**

I couldn't find reliable Nvidia news right now. The news services either failed or returned nothing that passed the reliability filter. Please try again in a minute, or pick a different category.


---

## General question

**User:** What is the difference between a stock and a bond?

**Workflow trace:** classify (rules): intent=general → web_search: failed (Web search failed: DDGSException) → respond: template (no LLM key) (0.8s)

**Fallback events:** Web search failed: DDGSException


**NewsGenie:**

I couldn't reach my answer engine or web search just now, so I can't answer that reliably. Check the service status in the sidebar and try again.