import pytest
from modules.telegram_bot import BotState
from modules.models import Article, PostRecord


def make_record(notion_id="page-1"):
    return PostRecord(
        notion_page_id=notion_id, title="Test Post", status="Pending",
        source_url="https://example.com", post_text="This is a test LinkedIn post. #AI",
        image_url="https://img.example.com/photo.jpg", topics=["AI"],
    )


def test_bot_state_initial_is_idle():
    state = BotState()
    assert state.is_idle()


def test_bot_state_transitions_to_pending():
    state = BotState()
    article = Article("title", "url", "summary", "source", "date")
    record = make_record()
    state.set_pending(article, record)
    assert not state.is_idle()
    assert state.current_record == record


def test_bot_state_clears_on_reset():
    state = BotState()
    article = Article("title", "url", "summary", "source", "date")
    state.set_pending(article, make_record())
    state.reset()
    assert state.is_idle()
    assert state.current_record is None


def test_bot_state_tracks_regenerate_mode():
    state = BotState()
    article = Article("title", "url", "summary", "source", "date")
    state.set_pending(article, make_record())
    assert not state.waiting_for_feedback
    state.waiting_for_feedback = True
    assert state.waiting_for_feedback
