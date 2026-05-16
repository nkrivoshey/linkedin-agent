# modules/content_memory.py
import logging
import random
from datetime import date, timedelta

from modules.generator import CONTENT_WEIGHTS
from modules.notion import NotionLogger

logger = logging.getLogger(__name__)

_CASE_STUDY_COOLDOWN_DAYS = 7   # case_study not published more than once per 7 days
_PROJECT_COOLDOWN_DAYS = 14     # project not mentioned more than once per 14 days


class ContentMemory:
    """Queries Notion post history to control topic dedup and content type selection."""

    def __init__(self, notion: NotionLogger):
        self._notion = notion

    def get_recent_posts(self, n: int = 20) -> list[dict]:
        return self._notion.get_recent_posts(n)

    def get_forbidden_topics(self, recent_posts: list[dict]) -> list[str]:
        """Projects mentioned in last 14 days are forbidden for reuse."""
        cutoff = date.today() - timedelta(days=_PROJECT_COOLDOWN_DAYS)
        forbidden: set[str] = set()
        for post in recent_posts:
            pub_str = post.get("publish_date", "")
            if not pub_str or not post.get("project_mentioned"):
                continue
            try:
                pub_date = date.fromisoformat(pub_str[:10])
            except ValueError:
                continue
            if pub_date >= cutoff:
                forbidden.add(post["project_mentioned"])
        if forbidden:
            logger.info("Forbidden projects (last %d days): %s", _PROJECT_COOLDOWN_DAYS, list(forbidden))
        return list(forbidden)

    def pick_content_type(self, recent_posts: list[dict]) -> str:
        """Weighted content type selection, downweighting case_study if published recently."""
        weights = dict(CONTENT_WEIGHTS)
        cutoff = date.today() - timedelta(days=_CASE_STUDY_COOLDOWN_DAYS)
        for post in recent_posts:
            pub_str = post.get("publish_date", "")
            if not pub_str or post.get("content_type") != "case_study":
                continue
            try:
                pub_date = date.fromisoformat(pub_str[:10])
            except ValueError:
                continue
            if pub_date >= cutoff:
                days_since = (date.today() - pub_date).days
                weights["case_study"] = max(0, weights["case_study"] - 18)
                logger.info("case_study downweighted: last was %d days ago", days_since)
                break
        names = list(weights.keys())
        w = list(weights.values())
        return random.choices(names, weights=w, k=1)[0]
