# modules/notion.py
import logging
from datetime import datetime

from notion_client import Client

from modules.models import Article, PostRecord

logger = logging.getLogger(__name__)


class NotionLogger:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    def create_draft(
        self,
        article: Article,
        post_text: str,
        image_url: str,
        topics: list[str],
        content_type: str = "",
        main_topic: str = "",
        resume_reference: bool = False,
        project_mentioned: str | None = None,
    ) -> PostRecord:
        properties: dict = {
            "Title": {"title": [{"text": {"content": article.title[:100]}}]},
            "Status": {"select": {"name": "Draft"}},
            "Source URL": {"url": article.url or None},
            "Topic": {"multi_select": [{"name": t} for t in topics]},
            "Post Text": {"rich_text": [{"text": {"content": post_text[:2000]}}]},
            "Image URL": {"url": image_url or None},
            "Publish Date": {"date": {"start": datetime.utcnow().date().isoformat()}},
            "Generation Count": {"number": 1},
            "Resume Reference": {"checkbox": resume_reference},
        }
        if content_type:
            properties["Content Type"] = {"select": {"name": content_type}}
        if main_topic:
            properties["Main Topic"] = {"rich_text": [{"text": {"content": main_topic[:200]}}]}
        if project_mentioned:
            properties["Project Mentioned"] = {
                "rich_text": [{"text": {"content": project_mentioned[:200]}}]
            }
        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )
        logger.info("Draft created: page_id=%s content_type=%s", page["id"], content_type)
        return PostRecord(
            notion_page_id=page["id"],
            title=article.title,
            status="Draft",
            source_url=article.url,
            post_text=post_text,
            image_url=image_url,
            topics=topics,
        )

    def update_status(self, page_id: str, status: str, **kwargs) -> None:
        properties: dict = {"Status": {"select": {"name": status}}}
        if "linkedin_url" in kwargs:
            properties["LinkedIn URL"] = {"url": kwargs["linkedin_url"]}
        if "feedback" in kwargs:
            properties["Feedback"] = {
                "rich_text": [{"text": {"content": kwargs["feedback"][:2000]}}]
            }
        if "generation_count" in kwargs:
            properties["Generation Count"] = {"number": kwargs["generation_count"]}
        if "post_text" in kwargs:
            properties["Post Text"] = {
                "rich_text": [{"text": {"content": kwargs["post_text"][:2000]}}]
            }
        self.client.pages.update(page_id=page_id, properties=properties)

    def get_published_urls(self) -> set[str]:
        try:
            results = self.client.databases.query(database_id=self.database_id)
        except Exception:
            return set()
        urls = set()
        for page in results.get("results", []):
            url = page["properties"].get("Source URL", {}).get("url")
            if url:
                urls.add(url)
        return urls

    def get_recent_posts(self, n: int = 20) -> list[dict]:
        """Return last n posts with memory fields for dedup logic."""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                sorts=[{"property": "Publish Date", "direction": "descending"}],
                page_size=n,
            )
        except Exception as e:
            logger.warning("get_recent_posts failed: %s", e)
            return []
        results = []
        for page in response.get("results", []):
            props = page["properties"]
            results.append({
                "page_id": page["id"],
                "content_type": self._get_select(props, "Content Type"),
                "main_topic": self._get_rich_text(props, "Main Topic"),
                "resume_reference": self._get_checkbox(props, "Resume Reference"),
                "project_mentioned": self._get_rich_text(props, "Project Mentioned") or None,
                "publish_date": self._get_date(props, "Publish Date"),
                "status": self._get_select(props, "Status"),
            })
        return results

    def _get_select(self, props: dict, key: str) -> str:
        sel = props.get(key, {}).get("select")
        return sel["name"] if sel else ""

    def _get_rich_text(self, props: dict, key: str) -> str:
        rt = props.get(key, {}).get("rich_text", [])
        return rt[0]["plain_text"] if rt else ""

    def _get_checkbox(self, props: dict, key: str) -> bool:
        return bool(props.get(key, {}).get("checkbox", False))

    def _get_date(self, props: dict, key: str) -> str:
        d = props.get(key, {}).get("date")
        return d["start"] if d else ""
