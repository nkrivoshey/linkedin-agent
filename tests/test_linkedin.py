from unittest.mock import patch, MagicMock
from datetime import date
import pytest
from modules.linkedin import LinkedInPublisher


@pytest.fixture
def publisher():
    return LinkedInPublisher(
        access_token="fake-token",
        person_urn="urn:li:person:abc123",
        token_issued_at="2026-02-21",  # 60 days before 2026-04-22
    )


def test_publish_calls_ugc_posts_endpoint(publisher):
    with patch("modules.linkedin.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=201, headers={"X-RestLi-Id": "urn:li:ugcPost:999"},
        )
        url = publisher.publish(text="My LinkedIn post #AI", image_url="")
    assert "999" in url
    assert mock_post.called


def test_is_token_expiring_soon_true_when_60_days(publisher):
    assert publisher.is_token_expiring_soon() is True


def test_is_token_expiring_soon_false_when_fresh():
    fresh = LinkedInPublisher(access_token="t", person_urn="urn:li:person:x",
                              token_issued_at=date.today().isoformat())
    assert fresh.is_token_expiring_soon() is False


def test_publish_raises_on_non_201(publisher):
    with patch("modules.linkedin.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        with pytest.raises(RuntimeError, match="LinkedIn API error"):
            publisher.publish(text="post", image_url="")
