import random
from datetime import datetime, timedelta, timezone
import feedparser
from newsapi import NewsApiClient
from modules.models import Article

KEYWORD_CATEGORIES = {
    "ai_models": [
        "new AI model", "LLM release", "model comparison", "open source AI",
        "AI benchmark", "generative AI", "large language model",
    ],
    "data_analytics": [
        "data analytics", "analytics engineering", "dbt", "data pipeline",
        "data warehouse", "business intelligence", "SQL analytics",
    ],
    "product_metrics": [
        "product analytics", "product metrics", "A/B testing",
        "funnel analysis", "cohort analysis", "growth metrics", "retention analysis",
    ],
    "data_science": [
        "machine learning", "data science", "Python machine learning",
        "deep learning", "MLOps", "feature engineering",
    ],
    "business_tech": [
        "business intelligence", "KPI dashboard", "revenue analytics",
        "data-driven business", "startup metrics", "SaaS analytics",
    ],
}

DEFAULT_KEYWORDS = [kw for kws in KEYWORD_CATEGORIES.values() for kw in kws]

DEFAULT_RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://feeds.feedburner.com/towards-data-science",
    "https://www.technologyreview.com/feed/",
    "https://thesequence.substack.com/feed",
    "https://benn.substack.com/feed",
    "https://roundup.getdbt.com/feed",
    "https://www.deeplearning.ai/the-batch/feed/",
]


class NewsCollector:
    def __init__(
        self,
        newsapi_key: str,
        rss_feeds: list[str] | None = None,
        keywords: list[str] | None = None,
    ):
        self.api = NewsApiClient(api_key=newsapi_key)
        self.rss_feeds = rss_feeds or DEFAULT_RSS_FEEDS
        self.keywords = keywords or DEFAULT_KEYWORDS

    def fetch(self, already_published_urls: set[str]) -> Article | None:
        articles = self._fetch_from_newsapi(already_published_urls)
        if not articles:
            articles = self._fetch_from_rss(already_published_urls)
        return articles[0] if articles else None

    def _fetch_from_newsapi(self, skip_urls: set[str]) -> list[Article]:
        # AI + analytics get 65% of the weight
        categories = list(KEYWORD_CATEGORIES.keys())
        weights = {"ai_models": 30, "data_analytics": 35, "product_metrics": 10,
                   "data_science": 15, "business_tech": 10}
        chosen = random.choices(categories, weights=[weights[c] for c in categories], k=1)[0]
        category_kws = KEYWORD_CATEGORIES[chosen]
        query = " OR ".join(f'"{kw}"' for kw in random.sample(category_kws, min(4, len(category_kws))))
        from_date = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S")
        try:
            response = self.api.get_everything(
                q=query, from_param=from_date, language="en",
                sort_by="relevancy", page_size=10,
            )
        except Exception:
            return []
        results = []
        for item in response.get("articles", []):
            url = item.get("url", "")
            if url in skip_urls:
                continue
            desc = (item.get("description") or "").lower()
            keywords = [kw for kw in self.keywords if kw.lower() in desc]
            results.append(Article(
                title=item.get("title", ""),
                url=url,
                summary=item.get("description") or "",
                source=item.get("source", {}).get("name", ""),
                published_at=item.get("publishedAt", ""),
                keywords=keywords or self.keywords[:3],
            ))
        return results

    def _fetch_from_rss(self, skip_urls: set[str]) -> list[Article]:
        results = []
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
            except Exception:
                continue
            for entry in feed.entries[:5]:
                url = getattr(entry, "link", "")
                if url in skip_urls:
                    continue
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                text = (title + " " + summary).lower()
                if not any(kw.lower() in text for kw in self.keywords):
                    continue
                results.append(Article(
                    title=title, url=url, summary=summary,
                    source=feed.feed.get("title", "RSS") if hasattr(feed, "feed") else "RSS",
                    published_at=getattr(entry, "published", ""),
                    keywords=[kw for kw in self.keywords if kw.lower() in text],
                ))
        return results
