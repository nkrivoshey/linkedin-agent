# tests/test_content_memory.py
from datetime import date, timedelta
from unittest.mock import MagicMock


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def test_get_forbidden_topics_blocks_project_within_14_days():
    from modules.content_memory import ContentMemory
    memory = ContentMemory(notion=MagicMock())
    recent = [
        {"content_type": "case_study", "main_topic": "MPP DWH", "resume_reference": True,
         "project_mentioned": "MPP DWH", "publish_date": _days_ago(5), "status": "Published"},
    ]
    assert "MPP DWH" in memory.get_forbidden_topics(recent)


def test_get_forbidden_topics_allows_project_after_14_days():
    from modules.content_memory import ContentMemory
    memory = ContentMemory(notion=MagicMock())
    recent = [
        {"content_type": "case_study", "main_topic": "MPP DWH", "resume_reference": True,
         "project_mentioned": "MPP DWH", "publish_date": _days_ago(15), "status": "Published"},
    ]
    assert "MPP DWH" not in memory.get_forbidden_topics(recent)


def test_get_forbidden_topics_deduplicates():
    from modules.content_memory import ContentMemory
    memory = ContentMemory(notion=MagicMock())
    recent = [
        {"project_mentioned": "MPP DWH", "publish_date": _days_ago(1), "resume_reference": True,
         "content_type": "case_study", "main_topic": "", "status": "Published"},
        {"project_mentioned": "MPP DWH", "publish_date": _days_ago(2), "resume_reference": True,
         "content_type": "case_study", "main_topic": "", "status": "Published"},
    ]
    forbidden = memory.get_forbidden_topics(recent)
    assert forbidden.count("MPP DWH") == 1


def test_pick_content_type_downweights_case_study_if_recent():
    from modules.content_memory import ContentMemory
    memory = ContentMemory(notion=MagicMock())
    recent = [
        {"content_type": "case_study", "main_topic": "x", "resume_reference": True,
         "project_mentioned": None, "publish_date": _days_ago(3), "status": "Published"},
    ]
    counts: dict[str, int] = {}
    for _ in range(500):
        ct = memory.pick_content_type(recent)
        counts[ct] = counts.get(ct, 0) + 1
    # case_study weight drops from 20 to 2 (20-18), should be very rare
    assert counts.get("case_study", 0) < 20


def test_pick_content_type_normal_distribution_without_constraints():
    from modules.content_memory import ContentMemory
    memory = ContentMemory(notion=MagicMock())
    counts: dict[str, int] = {}
    for _ in range(1000):
        ct = memory.pick_content_type([])
        counts[ct] = counts.get(ct, 0) + 1
    assert counts.get("statistical_method", 0) > 150
    assert counts.get("industry_insight", 0) > 0
    assert all(ct in counts for ct in [
        "statistical_method", "data_analytics_tip", "case_study",
        "ai_tools_for_analysts", "industry_insight"
    ])


def test_get_recent_posts_delegates_to_notion():
    from modules.content_memory import ContentMemory
    notion = MagicMock()
    notion.get_recent_posts.return_value = [{"content_type": "data_analytics_tip"}]
    memory = ContentMemory(notion=notion)
    posts = memory.get_recent_posts(n=10)
    notion.get_recent_posts.assert_called_once_with(10)
    assert posts[0]["content_type"] == "data_analytics_tip"
