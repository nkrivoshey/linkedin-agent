from dataclasses import dataclass, field


@dataclass
class Article:
    title: str
    url: str
    summary: str
    source: str
    published_at: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class PostRecord:
    notion_page_id: str
    title: str
    status: str          # Draft | Pending | Approved | Published | Skipped
    source_url: str
    post_text: str
    image_url: str
    topics: list[str]
    feedback: str = ""
    generation_count: int = 1
    linkedin_url: str = ""
    publish_date: str = ""
