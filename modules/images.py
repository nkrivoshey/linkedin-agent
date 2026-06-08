"""
ImageFetcher — three-tier image strategy for LinkedIn posts.

Tier 1a: gpt-image-1 (for news_insight / learning — impersonal scenes, returns bytes)
Tier 1b: real profile photo rotation (for personal_story / achievement / hot_take, returns path)
Tier 2:  Unsplash API with Notion-persisted blacklist (returns URL string)
Tier 3:  hardcoded fallback URL (returns URL string)
"""
from __future__ import annotations

import base64
import logging
import random
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FALLBACK_QUERIES = [
    "data analytics dashboard",
    "artificial intelligence technology",
    "business intelligence",
    "machine learning abstract",
    "data science visualization",
    "technology innovation",
]

# gpt-image-1 scene prompts by post type — NO visible human faces per D-01 (CONTEXT.md)
SCENE_PROMPTS: dict[str, str] = {
    "news_insight": (
        "data analyst workspace from above, dual monitors showing dashboards and charts, "
        "coffee cup, notebook, Dubai skyline through window at dusk, photorealistic"
    ),
    "personal_story": (
        "person from behind sitting at desk in modern office, contemplative posture, "
        "window with city view, soft lighting"
    ),
    "hot_take": (
        "person's hands typing rapidly on laptop keyboard, dark room with single monitor glow, "
        "data visualizations visible on screen"
    ),
    "achievement": (
        "silhouette of person standing at floor-to-ceiling window overlooking Dubai skyline at night, "
        "triumphant stance"
    ),
    "learning": (
        "open technical book with laptop beside it, handwritten notes visible, "
        "coffee cup, clean minimal desk"
    ),
}

# Post types that use real profile photos (privacy decision in D-01 — no AI-generated faces)
PERSONAL_POST_TYPES: frozenset[str] = frozenset({"personal_story", "achievement", "hot_take"})

# Post types that use gpt-image-1 AI scenes
GPT_IMAGE_TYPES: frozenset[str] = frozenset({"news_insight", "learning"})

# Path to real profile photos directory (gitignored, populated by user)
PROFILE_PHOTOS_DIR: Path = Path(__file__).parent.parent / "data" / "profile_photos"

# Hardcoded fallback image URL — professional LinkedIn-suitable scene (data dashboard)
FALLBACK_IMAGE_URL: str = (
    "https://images.unsplash.com/photo-1551288049-bebda4e38f71"
    "?w=1200&q=80&fit=crop&auto=format"
)

_CANDIDATES_PER_QUERY = 6
_MAX_CANDIDATES = 15


# ---------------------------------------------------------------------------
# ImageFetcher
# ---------------------------------------------------------------------------


class ImageFetcher:
    """
    Three-tier image strategy:
      Tier 1a — gpt-image-1 for GPT_IMAGE_TYPES (returns bytes via fetch_gpt_image)
      Tier 1b — real photo rotation for PERSONAL_POST_TYPES (returns file path via fetch_profile_photo)
      Tier 2  — Unsplash with Notion-persisted blacklist (returns URL via fetch_candidates)
      Tier 3  — FALLBACK_IMAGE_URL constant (hardcoded safe fallback)

    Notion integration is injected via callbacks so this module has no hard
    dependency on modules/notion.py — avoids circular imports and keeps the
    module independently testable.
    """

    def __init__(
        self,
        unsplash_key: str,
        openai_key: str = "",
        use_gpt_image: bool = True,
        notion_blacklist_getter: Optional[Callable[[], set[str]]] = None,
        notion_blacklist_setter: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.unsplash_key = unsplash_key
        self.openai_key = openai_key
        self.use_gpt_image = use_gpt_image
        self._notion_getter = notion_blacklist_getter
        self._notion_setter = notion_blacklist_setter
        # In-memory fallback used when Notion callbacks are not wired up.
        # NOTE: loses state on restart — acceptable per arch decision D-01.
        self._used_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public API — Tier 1a
    # ------------------------------------------------------------------

    def fetch_gpt_image(self, post_type: str, post_text: str) -> bytes | None:
        """
        Generate a scene image via gpt-image-1.

        Returns PNG bytes on success, None if:
          - openai_key is empty
          - use_gpt_image is False
          - API call fails for any reason (network, quota, timeout ~20-41s per spike)

        On failure the caller should fall through to Unsplash / fallback.
        T-02-02 mitigation: try/except returns None, pipeline degrades gracefully.
        """
        if not self.use_gpt_image or not self.openai_key:
            return None

        prompt = SCENE_PROMPTS.get(post_type, SCENE_PROMPTS["news_insight"])
        try:
            from openai import OpenAI  # lazy import — not always installed in tests

            client = OpenAI(api_key=self.openai_key)
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                quality="medium",
                size="1536x1024",
                response_format="b64_json",
            )
            raw_b64 = response.data[0].b64_json
            return base64.b64decode(raw_b64)
        except Exception:
            logger.exception("gpt-image-1 failed for post_type=%r", post_type)
            return None

    # ------------------------------------------------------------------
    # Public API — Tier 1b
    # ------------------------------------------------------------------

    def fetch_profile_photo(self, post_type: str) -> str | None:
        """
        Return a random real profile photo path for personal post types.

        Returns None if:
          - post_type not in PERSONAL_POST_TYPES
          - PROFILE_PHOTOS_DIR does not exist or contains no supported images

        T-02-03 mitigation: path traversal prevented by Path.glob with fixed
        extensions anchored to the PROFILE_PHOTOS_DIR constant.
        """
        if post_type not in PERSONAL_POST_TYPES:
            return None

        if not PROFILE_PHOTOS_DIR.exists():
            logger.warning(
                "Profile photos directory does not exist: %s. "
                "Create data/profile_photos/ and add real photos.",
                PROFILE_PHOTOS_DIR,
            )
            return None

        photos: list[Path] = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            photos.extend(PROFILE_PHOTOS_DIR.glob(ext))

        if not photos:
            logger.warning(
                "No profile photos found in data/profile_photos/ "
                "(expected .jpg / .jpeg / .png / .webp files)"
            )
            return None

        return str(random.choice(photos))

    # ------------------------------------------------------------------
    # Public API — Tier 2 (Unsplash)
    # ------------------------------------------------------------------

    def fetch_candidates(self, keywords: list[str]) -> list[dict]:
        """
        Fetch up to _MAX_CANDIDATES Unsplash photos, excluding blacklisted IDs.

        Returns list of dicts: {id, url, description, alt_description, tags}.
        Returns [] if Unsplash API is unavailable — caller should use fallback.
        """
        blacklist = self._get_blacklist()
        queries = keywords[:3] if keywords else [random.choice(FALLBACK_QUERIES)]
        seen_ids: set[str] = set()
        candidates: list[dict] = []

        for query in queries:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            page = random.randint(1, 4)
            results = self._search_raw(query, page=page, per_page=_CANDIDATES_PER_QUERY)
            if not results and page > 1:
                results = self._search_raw(query, page=1, per_page=_CANDIDATES_PER_QUERY)

            for r in results:
                if r["id"] in seen_ids or r["id"] in blacklist:
                    continue
                seen_ids.add(r["id"])
                tags = [t["title"] for t in r.get("tags", []) if isinstance(t, dict)]
                candidates.append(
                    {
                        "id": r["id"],
                        "url": r["urls"]["regular"],
                        "description": r.get("description") or "",
                        "alt_description": r.get("alt_description") or "",
                        "tags": tags,
                    }
                )

            if len(candidates) < _CANDIDATES_PER_QUERY:
                # Current query gave few results — also try a random fallback query
                fb = random.choice(FALLBACK_QUERIES)
                for r in self._search_raw(fb, page=1, per_page=_CANDIDATES_PER_QUERY):
                    if r["id"] in seen_ids or r["id"] in blacklist:
                        continue
                    seen_ids.add(r["id"])
                    tags = [t["title"] for t in r.get("tags", []) if isinstance(t, dict)]
                    candidates.append(
                        {
                            "id": r["id"],
                            "url": r["urls"]["regular"],
                            "description": r.get("description") or "",
                            "alt_description": r.get("alt_description") or "",
                            "tags": tags,
                        }
                    )

        return candidates[:_MAX_CANDIDATES]

    def mark_used(self, image_url: str, candidates: list[dict]) -> None:
        """
        Mark an Unsplash image as used so it is excluded from future candidates.

        Delegates to Notion if notion_blacklist_setter is wired; otherwise stores
        in the in-memory _used_ids set (state lost on restart — acceptable per D-01).
        """
        for c in candidates:
            if c["url"] == image_url:
                image_id = c["id"]
                if self._notion_setter is not None:
                    try:
                        self._notion_setter(image_id)
                    except Exception:
                        logger.exception(
                            "Failed to persist used Unsplash ID to Notion; "
                            "falling back to in-memory set"
                        )
                        self._used_ids.add(image_id)
                else:
                    self._used_ids.add(image_id)
                    # Prevent unbounded growth of in-memory set
                    if len(self._used_ids) > 100:
                        self._used_ids.clear()
                return

    def get_unsplash_blacklist(self) -> set[str]:
        """Return the full set of used Unsplash image IDs. Delegates to Notion if wired."""
        return self._get_blacklist()

    def mark_unsplash_used_notion(self, image_id: str) -> None:
        """Persist a single Unsplash image ID via the Notion callback (or in-memory fallback)."""
        if self._notion_setter is not None:
            try:
                self._notion_setter(image_id)
            except Exception:
                logger.exception("Failed to persist Unsplash ID to Notion; using in-memory")
                self._used_ids.add(image_id)
        else:
            self._used_ids.add(image_id)

    # ------------------------------------------------------------------
    # Backward-compatible fetch() — used by existing callers
    # ------------------------------------------------------------------

    def fetch(self, keywords: list[str]) -> str:
        """
        Simple single-result fetch returning a URL string.
        Kept for backward compatibility with existing callers in main.py.
        Does NOT use gpt-image-1 (returns URL, not bytes).
        Falls back to FALLBACK_IMAGE_URL if Unsplash is unavailable.
        """
        candidates = self.fetch_candidates(keywords)
        if not candidates:
            logger.warning("No Unsplash candidates found; using hardcoded fallback URL")
            return FALLBACK_IMAGE_URL
        blacklist = self._get_blacklist()
        fresh = [c for c in candidates if c["id"] not in blacklist]
        pick = random.choice(fresh) if fresh else random.choice(candidates)
        self.mark_used(pick["url"], candidates)
        return pick["url"]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_blacklist(self) -> set[str]:
        """
        Return the current blacklist.
        Tries Notion getter first; falls back to in-memory set on any error.
        """
        if self._notion_getter is not None:
            try:
                return self._notion_getter()
            except Exception:
                logger.exception(
                    "Failed to load Unsplash blacklist from Notion; using in-memory fallback"
                )
        return self._used_ids

    def _search_raw(self, query: str, page: int = 1, per_page: int = 10) -> list[dict]:
        """Call Unsplash search API and return raw result list. Returns [] on any error."""
        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": per_page,
                    "page": page,
                    "orientation": "landscape",
                },
                headers={"Authorization": f"Client-ID {self.unsplash_key}"},
                timeout=10,
            )
        except Exception:
            logger.exception("Unsplash API request failed for query=%r", query)
            return []

        if resp.status_code != 200:
            logger.error(
                "Unsplash API returned non-200 status: %s for query=%r",
                resp.status_code,
                query,
            )
            return []

        try:
            return resp.json().get("results", [])
        except Exception:
            logger.exception("Failed to parse Unsplash JSON response for query=%r", query)
            return []
