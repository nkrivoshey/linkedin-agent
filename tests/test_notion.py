from unittest.mock import MagicMock, patch
import pytest
from modules.models import Article, PostRecord
from modules.notion import NotionLogger


@pytest.fixture
def mock_notion_client():
    with patch("modules.notion.Client") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


@pytest.fixture
def logger(mock_notion_client):
    return NotionLogger(token="fake-token", database_id="fake-db-id")


def test_create_draft_returns_post_record(logger, mock_notion_client):
    mock_notion_client.pages.create.return_value = {"id": "page-123", "properties": {}}
    article = Article(
        title="GPT-5 Released", url="https://example.com/gpt5",
        summary="OpenAI releases GPT-5", source="TechCrunch",
        published_at="2026-04-22", keywords=["AI", "LLM"],
    )
    record = logger.create_draft(article, "Post text here", "https://img.url", ["AI", "LLM"])
    assert record.notion_page_id == "page-123"
    assert record.status == "Draft"
    assert record.source_url == "https://example.com/gpt5"
    assert record.post_text == "Post text here"


def test_update_status_calls_pages_update(logger, mock_notion_client):
    logger.update_status("page-123", "Published", linkedin_url="https://linkedin.com/post/1")
    mock_notion_client.pages.update.assert_called_once()
    call_kwargs = mock_notion_client.pages.update.call_args[1]
    assert call_kwargs["page_id"] == "page-123"
    assert call_kwargs["properties"]["Status"]["select"]["name"] == "Published"


def test_get_published_urls_returns_set(logger, mock_notion_client):
    mock_notion_client.databases.query.return_value = {
        "results": [
            {"properties": {"Source URL": {"url": "https://example.com/a1"}}},
            {"properties": {"Source URL": {"url": "https://example.com/a2"}}},
        ]
    }
    urls = logger.get_published_urls()
    assert urls == {"https://example.com/a1", "https://example.com/a2"}
