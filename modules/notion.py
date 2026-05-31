from datetime import datetime
from notion_client import Client
from modules.models import Article, PostRecord


class NotionLogger:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    def create_draft(
        self, article: Article, post_text: str, image_url: str, topics: list[str]
    ) -> PostRecord:
        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Title": {"title": [{"text": {"content": article.title[:100]}}]},
                "Status": {"select": {"name": "Draft"}},
                "Source URL": {"url": article.url or None},
                "Topic": {"multi_select": [{"name": t} for t in topics]},
                "Post Text": {"rich_text": [{"text": {"content": post_text[:2000]}}]},
                "Image URL": {"url": image_url or None},
                "Publish Date": {"date": {"start": datetime.utcnow().date().isoformat()}},
                "Generation Count": {"number": 1},
            },
        )
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
