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


def test_create_draft_stores_content_type_and_memory_fields():
    from unittest.mock import MagicMock, patch
    with patch("modules.notion.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        from modules.notion import NotionLogger
        from modules.models import Article
        notion = NotionLogger(token="test", database_id="db-123")
        article = Article(
            title="Test", url="http://x.com", summary="s",
            source="src", published_at="2026-05-16",
        )
        notion.create_draft(
            article, "post text", "http://img.com", ["Data"],
            content_type="statistical_method",
            main_topic="CUPED",
            resume_reference=True,
            project_mentioned="MPP DWH",
        )
        props = mock_client.pages.create.call_args[1]["properties"]
        assert props["Content Type"]["select"]["name"] == "statistical_method"
        assert props["Main Topic"]["rich_text"][0]["text"]["content"] == "CUPED"
        assert props["Resume Reference"]["checkbox"] is True
        assert props["Project Mentioned"]["rich_text"][0]["text"]["content"] == "MPP DWH"


def test_create_draft_omits_content_type_when_empty():
    from unittest.mock import MagicMock, patch
    with patch("modules.notion.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-456"}

        from modules.notion import NotionLogger
        from modules.models import Article
        notion = NotionLogger(token="test", database_id="db-123")
        article = Article(title="T", url="", summary="s", source="src", published_at="")
        notion.create_draft(article, "text", "", [])
        props = mock_client.pages.create.call_args[1]["properties"]
        assert "Content Type" not in props


def test_get_recent_posts_returns_structured_list():
    from unittest.mock import MagicMock, patch
    with patch("modules.notion.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [{
                "id": "p1",
                "properties": {
                    "Content Type": {"select": {"name": "case_study"}},
                    "Main Topic": {"rich_text": [{"plain_text": "MPP DWH Project"}]},
                    "Resume Reference": {"checkbox": True},
                    "Project Mentioned": {"rich_text": [{"plain_text": "MPP DWH"}]},
                    "Publish Date": {"date": {"start": "2026-05-15"}},
                    "Status": {"select": {"name": "Published"}},
                },
            }]
        }
        from modules.notion import NotionLogger
        notion = NotionLogger(token="test", database_id="db-123")
        posts = notion.get_recent_posts(n=10)
        assert len(posts) == 1
        assert posts[0]["content_type"] == "case_study"
        assert posts[0]["resume_reference"] is True
        assert posts[0]["project_mentioned"] == "MPP DWH"
        assert posts[0]["publish_date"] == "2026-05-15"
