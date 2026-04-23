from unittest.mock import MagicMock, patch
import pytest
from modules.news import NewsCollector
from modules.models import Article

KEYWORDS = ["AI", "LLM", "machine learning", "data science", "data analytics"]
RSS_FEEDS = ["https://techcrunch.com/category/artificial-intelligence/feed/"]


@pytest.fixture
def collector():
    return NewsCollector(newsapi_key="fake-key", rss_feeds=RSS_FEEDS, keywords=KEYWORDS)


def test_fetch_returns_none_when_no_news(collector):
    with patch("modules.news.NewsApiClient") as MockAPI:
        MockAPI.return_value.get_everything.return_value = {"articles": []}
        with patch("modules.news.feedparser.parse") as mock_rss:
            mock_rss.return_value = MagicMock(entries=[])
            result = collector.fetch(already_published_urls=set())
    assert result is None


def test_fetch_returns_best_article():
    fake_articles = [{
        "title": "New LLM beats GPT-4", "url": "https://example.com/llm",
        "description": "A new LLM model beats GPT-4 on benchmarks",
        "source": {"name": "TechCrunch"}, "publishedAt": "2026-04-22T08:00:00Z",
    }]
    with patch("modules.news.NewsApiClient") as MockAPI:
        MockAPI.return_value.get_everything.return_value = {"articles": fake_articles}
        c = NewsCollector(newsapi_key="fake-key", rss_feeds=RSS_FEEDS, keywords=KEYWORDS)
        result = c.fetch(already_published_urls=set())
    assert result is not None
    assert isinstance(result, Article)
    assert result.url == "https://example.com/llm"


def test_fetch_skips_already_published(collector):
    fake_articles = [{
        "title": "New LLM beats GPT-4", "url": "https://example.com/llm",
        "description": "Summary", "source": {"name": "TC"}, "publishedAt": "2026-04-22T08:00:00Z",
    }]
    with patch("modules.news.NewsApiClient") as MockAPI:
        MockAPI.return_value.get_everything.return_value = {"articles": fake_articles}
        with patch("modules.news.feedparser.parse") as mock_rss:
            mock_rss.return_value = MagicMock(entries=[])
            result = collector.fetch(already_published_urls={"https://example.com/llm"})
    assert result is None


def test_fetch_falls_back_to_rss_when_newsapi_empty(collector):
    rss_entry = MagicMock()
    rss_entry.title = "AI data analytics revolution"
    rss_entry.link = "https://rss.example.com/article1"
    rss_entry.summary = "AI is transforming data analytics"
    rss_entry.published = "Mon, 22 Apr 2026 08:00:00 +0000"
    with patch("modules.news.NewsApiClient") as MockAPI:
        MockAPI.return_value.get_everything.return_value = {"articles": []}
        with patch("modules.news.feedparser.parse") as mock_rss:
            mock_rss.return_value = MagicMock(entries=[rss_entry])
            result = collector.fetch(already_published_urls=set())
    assert result is not None
    assert result.url == "https://rss.example.com/article1"
