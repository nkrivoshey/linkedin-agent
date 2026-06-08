"""
modules/context_store.py

Notion CRUD for the personal context database (NOTION_CONTEXT_DB_ID).
Stores free-text context entries added by the user via the Telegram questionnaire.
Used by ContentGenerator to enrich personal posts.

Notion DB schema:
  Title    (title)       — first 100 chars of text
  Category (select)      — "work" | "life" | "learning" | "opinion"
  Text     (rich_text)   — full user response (truncated at 2000 chars)
  Created  (date)        — UTC date of creation
  Used     (checkbox)    — False on create, True after used in a post

Unsplash blacklist:
  Stored as a single special page with Title="__unsplash_blacklist__".
  The Text field holds comma-separated Unsplash image IDs.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from notion_client import Client as NotionClient
    _NOTION_AVAILABLE = True
except ImportError:
    _NOTION_AVAILABLE = False
    NotionClient = None  # type: ignore[assignment, misc]

_UNSPLASH_BLACKLIST_TITLE = "__unsplash_blacklist__"


class ContextStore:
    """Read/write personal context entries from/to a Notion database.

    Gracefully degrades when context_db_id is empty or notion_client is
    unavailable — all methods return neutral values (None / [] / set())
    without raising exceptions.
    """

    def __init__(self, token: str, context_db_id: str) -> None:
        self.context_db_id = context_db_id
        if context_db_id and _NOTION_AVAILABLE and token:
            try:
                self.client: NotionClient | None = NotionClient(auth=token)
            except Exception:
                logger.exception("ContextStore: failed to create Notion client")
                self.client = None
        else:
            self.client = None

    # ── Availability ──────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True iff context_db_id is set and Notion client is ready."""
        return bool(self.context_db_id and self.client)

    # ── Context entries ───────────────────────────────────────────────────────

    def add_entry(self, category: str, text: str) -> str | None:
        """Create a new context entry in Notion.

        Returns the Notion page_id on success, None on failure or unavailability.
        """
        if not self.is_available():
            return None
        try:
            page = self.client.pages.create(  # type: ignore[union-attr]
                parent={"database_id": self.context_db_id},
                properties={
                    "Title": {
                        "title": [{"text": {"content": text[:100]}}]
                    },
                    "Category": {
                        "select": {"name": category}
                    },
                    "Text": {
                        "rich_text": [{"text": {"content": text[:2000]}}]
                    },
                    "Created": {
                        "date": {"start": datetime.utcnow().date().isoformat()}
                    },
                    "Used": {
                        "checkbox": False
                    },
                },
            )
            return page["id"]
        except Exception:
            logger.exception("ContextStore.add_entry failed")
            return None

    def get_unused_entries(self, limit: int = 10) -> list[dict]:
        """Return up to *limit* entries where Used == False.

        Each dict has keys: "id", "category", "text".
        Returns [] on failure or unavailability.
        """
        if not self.is_available():
            return []
        try:
            response = self.client.databases.query(  # type: ignore[union-attr]
                database_id=self.context_db_id,
                filter={"property": "Used", "checkbox": {"equals": False}},
                page_size=limit,
            )
            entries: list[dict] = []
            for page in response.get("results", []):
                props = page.get("properties", {})
                category = (
                    (props.get("Category") or {})
                    .get("select") or {}
                ).get("name", "")
                rich_text_list = (props.get("Text") or {}).get("rich_text", [])
                text = rich_text_list[0]["text"]["content"] if rich_text_list else ""
                entries.append({"id": page["id"], "category": category, "text": text})
            return entries
        except Exception:
            logger.exception("ContextStore.get_unused_entries failed")
            return []

    def mark_entry_used(self, page_id: str) -> None:
        """Set Used = True on the given Notion page."""
        if not self.is_available():
            return
        try:
            self.client.pages.update(  # type: ignore[union-attr]
                page_id=page_id,
                properties={"Used": {"checkbox": True}},
            )
        except Exception:
            logger.exception("ContextStore.mark_entry_used failed")

    # ── Unsplash blacklist ────────────────────────────────────────────────────

    def get_used_unsplash_ids(self) -> set[str]:
        """Return the set of Unsplash image IDs that have already been used.

        The list is stored as a comma-separated string in the Text field of a
        special page titled "__unsplash_blacklist__".
        Returns set() on failure or unavailability.
        """
        if not self.is_available():
            return set()
        try:
            page = self._get_blacklist_page()
            if page is None:
                return set()
            raw = self._extract_text_from_page(page)
            if not raw:
                return set()
            return {id_.strip() for id_ in raw.split(",") if id_.strip()}
        except Exception:
            logger.exception("ContextStore.get_used_unsplash_ids failed")
            return set()

    def mark_unsplash_used(self, image_id: str) -> None:
        """Append *image_id* to the Unsplash blacklist page.

        Creates the page if it does not exist.
        Only logs on failure — never raises.
        """
        if not self.is_available():
            return
        try:
            existing_ids = self.get_used_unsplash_ids()
            existing_ids.add(image_id)
            new_text = ",".join(sorted(existing_ids))

            page = self._get_blacklist_page()
            if page is None:
                self.client.pages.create(  # type: ignore[union-attr]
                    parent={"database_id": self.context_db_id},
                    properties={
                        "Title": {
                            "title": [{"text": {"content": _UNSPLASH_BLACKLIST_TITLE}}]
                        },
                        "Category": {
                            "select": {"name": "work"}  # required select field
                        },
                        "Text": {
                            "rich_text": [{"text": {"content": new_text[:2000]}}]
                        },
                        "Created": {
                            "date": {"start": datetime.utcnow().date().isoformat()}
                        },
                        "Used": {"checkbox": False},
                    },
                )
            else:
                self.client.pages.update(  # type: ignore[union-attr]
                    page_id=page["id"],
                    properties={
                        "Text": {
                            "rich_text": [{"text": {"content": new_text[:2000]}}]
                        }
                    },
                )
        except Exception:
            logger.exception("ContextStore.mark_unsplash_used failed")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_blacklist_page(self) -> dict | None:
        """Find the __unsplash_blacklist__ page; return None if not found."""
        try:
            response = self.client.databases.query(  # type: ignore[union-attr]
                database_id=self.context_db_id,
                filter={
                    "property": "Title",
                    "title": {"contains": _UNSPLASH_BLACKLIST_TITLE},
                },
                page_size=1,
            )
            results = response.get("results", [])
            return results[0] if results else None
        except Exception:
            logger.exception("ContextStore._get_blacklist_page failed")
            return None

    @staticmethod
    def _extract_text_from_page(page: dict) -> str:
        """Extract Text rich_text content from a Notion page dict."""
        rich_text_list = (
            (page.get("properties") or {})
            .get("Text", {})
            .get("rich_text", [])
        )
        if not rich_text_list:
            return ""
        return rich_text_list[0].get("text", {}).get("content", "")
