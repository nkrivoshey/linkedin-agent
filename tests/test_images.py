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
        "results": [{"id": "photo-123", "urls": {"regular": "https://images.unsplash.com/photo-123"}}]
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


def test_get_image_uses_pollinations_first():
    from unittest.mock import MagicMock, patch
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_get.return_value = mock_resp

        from modules.images import ImageFetcher
        fetcher = ImageFetcher(unsplash_key="test")
        url = fetcher.get_image("dark data visualization chart", fallback_query="analytics")
        assert "pollinations.ai" in url


def test_get_image_falls_back_to_unsplash_when_pollinations_fails():
    from unittest.mock import MagicMock, patch
    import requests as req_lib
    with patch("requests.get") as mock_get:
        def side_effect(url, **kwargs):
            if "pollinations" in url:
                raise req_lib.exceptions.Timeout()
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"results": [{
                "id": "abc123",
                "urls": {"regular": "https://images.unsplash.com/photo-abc"},
                "description": "data analytics",
                "alt_description": "chart",
                "tags": [],
            }]}
            return resp
        mock_get.side_effect = side_effect

        from modules.images import ImageFetcher
        fetcher = ImageFetcher(unsplash_key="test")
        url = fetcher.get_image("prompt", fallback_query="analytics dashboard")
        assert "unsplash" in url


def test_get_image_returns_empty_string_on_total_failure():
    from unittest.mock import patch
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("network down")

        from modules.images import ImageFetcher
        fetcher = ImageFetcher(unsplash_key="test")
        url = fetcher.get_image("prompt", fallback_query="analytics")
        assert url == ""


def test_get_image_skips_pollinations_when_prompt_empty():
    from unittest.mock import MagicMock, patch
    with patch("requests.get") as mock_get:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"results": [{
            "id": "xyz",
            "urls": {"regular": "https://images.unsplash.com/photo-xyz"},
            "description": "data",
            "alt_description": "",
            "tags": [],
        }]}
        mock_get.return_value = resp

        from modules.images import ImageFetcher
        fetcher = ImageFetcher(unsplash_key="test")
        url = fetcher.get_image("", fallback_query="data science")
        # With empty prompt, Pollinations should not be called
        calls = [str(c) for c in mock_get.call_args_list]
        assert not any("pollinations" in c for c in calls)
        assert "unsplash" in url
