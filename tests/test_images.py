from unittest.mock import patch, MagicMock
import pytest
from modules.images import ImageFetcher


@pytest.fixture
def fetcher():
    return ImageFetcher(unsplash_key="fake-unsplash", use_dalle=False, openai_key="")


def test_fetch_returns_url_on_success(fetcher):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"urls": {"regular": "https://images.unsplash.com/photo-123"}}]
    }
    with patch("modules.images.requests.get", return_value=mock_response):
        url = fetcher.fetch(keywords=["AI", "machine learning"])
    assert url == "https://images.unsplash.com/photo-123"


def test_fetch_returns_empty_string_on_failure(fetcher):
    mock_response = MagicMock()
    mock_response.status_code = 403
    with patch("modules.images.requests.get", return_value=mock_response):
        url = fetcher.fetch(keywords=["AI"])
    assert url == ""


def test_fetch_returns_empty_string_when_no_results(fetcher):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    with patch("modules.images.requests.get", return_value=mock_response):
        url = fetcher.fetch(keywords=["obscure topic"])
    assert url == ""
