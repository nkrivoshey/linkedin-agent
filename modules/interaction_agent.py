# modules/interaction_agent.py
import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_FIRST_COMMENT_DELAY_SECONDS = 3600   # 1 hour after publish
_BOOST_CHECK_DELAY_SECONDS = 86400    # 24 hours after publish

_COMMENT_PROMPT = """You are writing a follow-up comment on a LinkedIn post by a Senior Data Analyst.

The post was just published. Write a SHORT first comment (2-4 sentences) that:
- Adds one new data point, example, or angle NOT already in the post
- OR asks a specific practitioner question to invite responses
- Reads like a genuine follow-up thought, not self-promotion
- No hashtags, no "Great post!" opener

Post text:
{post_text}

Write ONLY the comment text, nothing else."""

_BOOST_PROMPT = """You are writing a boost comment on a LinkedIn post by a Senior Data Analyst.

The post has low engagement after 24 hours. Write a SHORT comment (2-4 sentences) that:
- Takes a different angle — a contrarian view, edge case, or related concept
- Invites specific practitioners to weigh in ("What's your experience with X?")
- Feels like a genuine continuation of thought, not an engagement bait
- No hashtags

Post text:
{post_text}

Write ONLY the comment text, nothing else."""


class InteractionAgent:
    """Phase A: auto-comment own posts and boost on low engagement."""

    def __init__(self, linkedin, generator, notion, enabled: bool = True):
        self._linkedin = linkedin
        self._generator = generator
        self._notion = notion
        self._enabled = enabled

    def _generate_first_comment(self, post_text: str) -> str:
        prompt = _COMMENT_PROMPT.format(post_text=post_text[:1500])
        return self._generator._call_with_retry(prompt)

    def _generate_boost_comment(self, post_text: str) -> str:
        prompt = _BOOST_PROMPT.format(post_text=post_text[:1500])
        return self._generator._call_with_retry(prompt)

    async def schedule_first_comment(
        self, post_id: str, post_text: str, notion_page_id: str, scheduler
    ) -> None:
        """Generate first comment and schedule it for 1 hour after publish."""
        if not self._enabled:
            logger.info("InteractionAgent disabled — skipping comment for post %s", post_id)
            return
        try:
            comment_text = self._generate_first_comment(post_text)
            run_date = datetime.now(timezone.utc) + timedelta(seconds=_FIRST_COMMENT_DELAY_SECONDS)
            scheduler.add_job(
                self._post_comment,
                "date",
                run_date=run_date,
                args=[post_id, comment_text],
                misfire_grace_time=600,
                id=f"first_comment_{post_id}",
                replace_existing=True,
            )
            logger.info(
                "Comment scheduled for post %s at %s UTC",
                post_id, run_date.strftime("%H:%M"),
            )
        except Exception as e:
            logger.error("Failed to schedule comment for %s: %s", post_id, e)

    async def schedule_boost_check(
        self, post_id: str, post_text: str, threshold: int, scheduler
    ) -> None:
        """Schedule engagement check 24h after publish. Low reactions → boost comment."""
        if not self._enabled:
            return
        try:
            run_date = datetime.now(timezone.utc) + timedelta(seconds=_BOOST_CHECK_DELAY_SECONDS)
            scheduler.add_job(
                self._run_boost_check,
                "date",
                run_date=run_date,
                args=[post_id, post_text, threshold],
                misfire_grace_time=3600,
                id=f"boost_check_{post_id}",
                replace_existing=True,
            )
            logger.info("Boost check scheduled for post %s at %s UTC", post_id, run_date.strftime("%H:%M"))
        except Exception as e:
            logger.error("Failed to schedule boost check for %s: %s", post_id, e)

    def _run_boost_check(self, post_id: str, post_text: str, threshold: int) -> None:
        try:
            stats = self._get_post_stats(post_id)
            reactions = stats.get("numLikes", 0) + stats.get("numComments", 0)
            logger.info("Post %s: %d reactions (threshold=%d)", post_id, reactions, threshold)
            if reactions < threshold:
                boost_text = self._generate_boost_comment(post_text)
                self._post_comment(post_id, boost_text)
                logger.info("Boost comment posted for %s", post_id)
        except Exception as e:
            logger.error("Boost check failed for %s: %s", post_id, e)

    def _post_comment(self, post_id: str, comment_text: str) -> None:
        """Post comment via LinkedIn socialActions API."""
        activity_urn = f"urn:li:activity:{post_id}"
        try:
            resp = requests.post(
                f"{self._linkedin.BASE_URL}/socialActions/{activity_urn}/comments",
                headers={"Authorization": f"Bearer {self._linkedin.access_token}"},
                json={
                    "actor": self._linkedin.person_urn,
                    "message": {"text": comment_text},
                },
                timeout=15,
            )
            logger.info("Comment posted for %s: HTTP %d", post_id, resp.status_code)
        except Exception as e:
            logger.error("Failed to post comment for %s: %s", post_id, e)

    def _get_post_stats(self, post_id: str) -> dict:
        """Get engagement stats via LinkedIn socialActions API."""
        activity_urn = f"urn:li:activity:{post_id}"
        try:
            resp = requests.get(
                f"{self._linkedin.BASE_URL}/socialActions/{activity_urn}",
                headers={"Authorization": f"Bearer {self._linkedin.access_token}"},
                timeout=15,
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.warning("Failed to get stats for %s: %s", post_id, e)
            return {}


class NetworkGrowthAgent:
    """Phase B scaffold — all methods raise NotImplementedError until explicitly activated."""

    def search_target_profiles(self, keywords: list[str], location: str) -> list[dict]:
        # TODO: Phase B — find relevant profiles to connect with
        raise NotImplementedError("NetworkGrowthAgent Phase B not yet activated")

    def send_connection_request(self, profile_id: str, personalized_note: str) -> bool:
        # TODO: Phase B — send connection request with personalized note
        raise NotImplementedError("NetworkGrowthAgent Phase B not yet activated")

    def like_and_comment_on_feed(self, n: int = 5) -> None:
        # TODO: Phase B — like and comment on n posts in feed
        raise NotImplementedError("NetworkGrowthAgent Phase B not yet activated")

    def reply_to_comments_on_own_posts(self) -> None:
        # TODO: Phase B — auto-reply to comments on own posts
        raise NotImplementedError("NetworkGrowthAgent Phase B not yet activated")
