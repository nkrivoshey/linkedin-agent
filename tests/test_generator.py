from unittest.mock import MagicMock, patch
import pytest
from modules.generator import ContentGenerator
from modules.models import Article

PROFILE = "I'm a Data Analyst with 4+ years of experience at Metropolitan Premium Properties in Dubai."


@pytest.fixture
def generator():
    with patch("modules.generator.anthropic.Anthropic"):
        return ContentGenerator(api_key="fake-key", profile_text=PROFILE)


def test_generate_returns_non_empty_string(generator):
    article = Article("GPT-5 Released", "https://example.com", "OpenAI's latest model",
                      "TechCrunch", "2026-04-22", keywords=["AI", "LLM"])
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Hook line.\n\nBody text.\n\n#AI")]
    with patch.object(generator.client.messages, "create", return_value=mock_message):
        result = generator.generate(article)
    assert len(result) > 10
    assert isinstance(result, str)


def test_regenerate_includes_feedback_in_prompt(generator):
    article = Article("GPT-5 Released", "https://example.com", "OpenAI's latest model",
                      "TechCrunch", "2026-04-22", keywords=["AI"])
    previous_draft = "First version of the post."
    feedback = "Make it shorter and add a specific metric."
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Improved version.")]
    with patch.object(generator.client.messages, "create", return_value=mock_message) as mock_create:
        result = generator.regenerate(article, previous_draft, feedback)
    prompt_used = mock_create.call_args[1]["messages"][0]["content"]
    assert "Make it shorter and add a specific metric." in prompt_used
    assert "First version of the post." in prompt_used
    assert result == "Improved version."


def test_generate_retries_on_failure(generator):
    article = Article("title", "url", "summary", "source", "date")
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Success on third try.")]
    with patch.object(generator.client.messages, "create",
                      side_effect=[
                          Exception("API error"), Exception("API error"),
                          mock_message,
                      ]) as mock_create:
        result = generator.generate(article)
    assert result == "Success on third try."
    assert mock_create.call_count == 3
