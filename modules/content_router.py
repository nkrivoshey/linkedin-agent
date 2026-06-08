"""
modules/content_router.py

Content type rotator for LinkedIn posts.
Implements D-04 from CONTEXT.md: weighted random selection with forced rotation
when the last 2 posts are the same type, and no-context fallback to news_insight.

This module does NOT access Notion directly.
recent_types list is passed in by the caller (e.g. from notion.get_recent_post_types()).
"""

import logging
import random

logger = logging.getLogger(__name__)

# All valid post types in priority order (highest weight first)
POST_TYPES: list[str] = [
    "news_insight",
    "personal_story",
    "hot_take",
    "achievement",
    "learning",
]

# Base weights must sum to 100 (D-04: news_insight 35%, personal_story 25%,
# hot_take 20%, achievement 10%, learning 10%)
BASE_WEIGHTS: dict[str, int] = {
    "news_insight": 35,
    "personal_story": 25,
    "hot_take": 20,
    "achievement": 10,
    "learning": 10,
}

# Types that require fresh personal context entries (Used=False in Notion context DB).
# news_insight does NOT require personal context — it is driven by news articles.
CONTEXT_DEPENDENT_TYPES: frozenset[str] = frozenset(
    {"personal_story", "hot_take", "achievement", "learning"}
)


def needs_fresh_context(post_type: str) -> bool:
    """Return True if post_type requires unused personal context entries.

    Context-dependent types: personal_story, hot_take, achievement, learning.
    news_insight does not require personal context.

    Args:
        post_type: one of POST_TYPES

    Returns:
        True  — caller must check context store before generating this post type
        False — type can be generated without personal context (news_insight)
    """
    return post_type in CONTEXT_DEPENDENT_TYPES


class ContentRouter:
    """Weighted random selector for LinkedIn post types.

    Implements the D-04 rotator logic:
    1. Base weights: news_insight=35, personal_story=25, hot_take=20,
       achievement=10, learning=10
    2. Forced rotation: if recent_types[0] == recent_types[1] (last 2 identical),
       that type's weight is set to 0
    3. No-context fallback: if has_fresh_context=False, news_insight weight += 20
       and all CONTEXT_DEPENDENT_TYPES are set to 0

    Does not hold state between calls — all logic based on passed-in recent_types.
    """

    def choose_post_type(
        self,
        recent_types: list[str],
        has_fresh_context: bool = True,
    ) -> str:
        """Select the next post type using weighted random with forced rotation.

        Args:
            recent_types: ordered list of recent post types, newest first
                          (e.g. from notion.get_recent_post_types(n=30)).
                          May be empty if no posts exist yet.
            has_fresh_context: True if there are unused context entries (Used=False)
                               in the Notion context DB. Defaults to True.

        Returns:
            A string from POST_TYPES representing the chosen post type.
        """
        # Work on a copy — never mutate the module-level constant
        weights: dict[str, int] = dict(BASE_WEIGHTS)

        # --- Rule 1: Forced rotation -------------------------------------------
        # If the last 2 posts are the same type, ban that type from this selection.
        if len(recent_types) >= 2 and recent_types[0] == recent_types[1]:
            repeated_type = recent_types[0]
            if repeated_type in weights:
                weights[repeated_type] = 0
                logger.debug(
                    "ContentRouter: forced rotation — '%s' appeared twice in a row, weight set to 0",
                    repeated_type,
                )

        # --- Rule 2: No-context fallback ----------------------------------------
        # If there are no fresh personal context entries, boost news_insight and
        # disable all context-dependent types so the generator won't be starved.
        if not has_fresh_context:
            weights["news_insight"] = weights.get("news_insight", 35) + 20
            for t in CONTEXT_DEPENDENT_TYPES:
                weights[t] = 0
            logger.debug(
                "ContentRouter: no fresh context — news_insight boosted to %d, "
                "context-dependent types disabled",
                weights["news_insight"],
            )

        # --- Build eligible pool ------------------------------------------------
        # Preserve POST_TYPES order for deterministic test behaviour
        eligible = [t for t in POST_TYPES if weights.get(t, 0) > 0]

        if not eligible:
            # Theoretical failsafe: cannot happen with current rules because
            # news_insight is only banned by forced rotation AND its weight is
            # always increased (not zeroed) by no-context path.  But be safe.
            logger.warning(
                "ContentRouter: eligible pool is empty — falling back to news_insight"
            )
            return "news_insight"

        selected = random.choices(eligible, weights=[weights[t] for t in eligible], k=1)[0]
        logger.debug("ContentRouter: selected post type '%s'", selected)
        return selected
