from unittest.mock import MagicMock, patch
import pytest
from modules.generator import ContentGenerator
from modules.models import Article

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
