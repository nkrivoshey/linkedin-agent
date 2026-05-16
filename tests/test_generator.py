from unittest.mock import MagicMock, patch
import pytest
from modules.generator import ContentGenerator
from modules.models import Article


def test_generated_post_dataclass():
    from modules.models import GeneratedPost
    gp = GeneratedPost(
        post_text="Hook\n\nBody",
        image_prompt="dark background data visualization",
        content_type="data_analytics_tip",
        main_topic="SQL Window Functions",
    )
    assert gp.post_text == "Hook\n\nBody"
    assert gp.resume_reference is False
    assert gp.project_mentioned is None

PROFILE = "I'm a Data Analyst with 4+ years of experience at Metropolitan Premium Properties in Dubai."


@pytest.fixture
def generator():
    with patch("modules.generator.genai"):
        return ContentGenerator(api_key="fake-key", profile_text=PROFILE)


def test_generate_returns_non_empty_string(generator):
    article = Article("GPT-5 Released", "https://example.com", "OpenAI's latest model",
                      "TechCrunch", "2026-04-22", keywords=["AI", "LLM"])
    with patch.object(generator, "model") as mock_model:
        mock_model.generate_content.return_value = MagicMock(text="Hook line.\n\nBody text.\n\n#AI")
        result = generator.generate(article)
    assert len(result) > 10
    assert isinstance(result, str)


def test_regenerate_includes_feedback_in_prompt(generator):
    article = Article("GPT-5 Released", "https://example.com", "OpenAI's latest model",
                      "TechCrunch", "2026-04-22", keywords=["AI"])
    previous_draft = "First version of the post."
    feedback = "Make it shorter and add a specific metric."
    with patch.object(generator, "model") as mock_model:
        mock_model.generate_content.return_value = MagicMock(text="Improved version.")
        result = generator.regenerate(article, previous_draft, feedback)
    prompt_used = mock_model.generate_content.call_args[0][0]
    assert "Make it shorter and add a specific metric." in prompt_used
    assert "First version of the post." in prompt_used
    assert result == "Improved version."


def test_generate_retries_on_failure(generator):
    article = Article("title", "url", "summary", "source", "date")
    with patch.object(generator, "model") as mock_model:
        mock_model.generate_content.side_effect = [
            Exception("API error"), Exception("API error"),
            MagicMock(text="Success on third try."),
        ]
        result = generator.generate(article)
    assert result == "Success on third try."
    assert mock_model.generate_content.call_count == 3


def test_config_has_new_fields():
    import os
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["NEWSAPI_KEY"] = "test"
    os.environ["UNSPLASH_ACCESS_KEY"] = "test"
    os.environ["TELEGRAM_BOT_TOKEN"] = "test"
    os.environ["TELEGRAM_CHAT_ID"] = "test"
    os.environ["LINKEDIN_ACCESS_TOKEN"] = "test"
    os.environ["LINKEDIN_PERSON_URN"] = "test"
    os.environ["NOTION_TOKEN"] = "test"
    os.environ["NOTION_DATABASE_ID"] = "test"
    from config import load_config
    cfg = load_config()
    assert hasattr(cfg, "huggingface_api_key")
    assert hasattr(cfg, "engagement_threshold")
    assert hasattr(cfg, "enable_network_agent")
    assert hasattr(cfg, "content_memory_lookback")
    assert cfg.engagement_threshold == 10
    assert cfg.enable_network_agent is False
    assert cfg.content_memory_lookback == 20


# ---------------------------------------------------------------------------
# New tests for Task 3: ContentGenerator returns GeneratedPost
# ---------------------------------------------------------------------------

from modules.models import Article, GeneratedPost  # noqa: E402


def _make_article():
    return Article(
        title="Test Article", url="https://example.com",
        summary="A summary about data analytics",
        source="Test Source", published_at="2026-05-16",
        keywords=["data", "analytics"],
    )


def test_generate_returns_generated_post():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(
            text='{"post_text": "Hook\\n\\nBody #data", "image_prompt": "dark data viz", '
                 '"main_topic": "SQL Tips", "resume_reference": false, "project_mentioned": null}'
        )])
        from modules.generator import ContentGenerator
        gen = ContentGenerator(api_key="test", profile_text="profile")
        result = gen.generate(_make_article())
        assert isinstance(result, GeneratedPost)
        assert result.post_text == "Hook\n\nBody #data"
        assert result.image_prompt == "dark data viz"
        assert result.main_topic == "SQL Tips"
        assert result.resume_reference is False


def test_generate_falls_back_on_invalid_json():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Plain text post without JSON")]
        )
        from modules.generator import ContentGenerator
        gen = ContentGenerator(api_key="test", profile_text="profile")
        result = gen.generate(_make_article())
        assert isinstance(result, GeneratedPost)
        assert result.post_text == "Plain text post without JSON"
        assert result.image_prompt == ""


def test_pick_content_type_respects_weights():
    with patch("anthropic.Anthropic"):
        from modules.generator import ContentGenerator, CONTENT_WEIGHTS
        gen = ContentGenerator(api_key="test", profile_text="profile")
        counts: dict[str, int] = {}
        for _ in range(1000):
            ct = gen._pick_content_type()
            counts[ct] = counts.get(ct, 0) + 1
        assert 200 < counts.get("statistical_method", 0) < 500
        assert counts.get("industry_insight", 0) < 150
        assert all(ct in counts for ct in CONTENT_WEIGHTS)


def test_generate_accepts_explicit_content_type():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(
            text='{"post_text": "Stats post", "image_prompt": "chart", '
                 '"main_topic": "CUPED", "resume_reference": false, "project_mentioned": null}'
        )])
        from modules.generator import ContentGenerator
        gen = ContentGenerator(api_key="test", profile_text="profile")
        result = gen.generate(_make_article(), content_type="statistical_method")
        assert result.content_type == "statistical_method"


def test_generate_passes_forbidden_topics_in_prompt():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(
            text='{"post_text": "post", "image_prompt": "", "main_topic": "x", '
                 '"resume_reference": false, "project_mentioned": null}'
        )])
        from modules.generator import ContentGenerator
        gen = ContentGenerator(api_key="test", profile_text="profile")
        gen.generate(_make_article(), forbidden_topics=["MPP DWH", "Sberbank NLP"])
        call_args = mock_client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "MPP DWH" in prompt_text
        assert "FORBIDDEN" in prompt_text
