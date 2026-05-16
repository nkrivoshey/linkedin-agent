from dataclasses import dataclass, field
from typing import Literal

ContentType = Literal[
    "statistical_method",
    "data_analytics_tip",
    "case_study",
    "ai_tools_for_analysts",
    "industry_insight",
]


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


@dataclass
class GeneratedPost:
    post_text: str        # Full LinkedIn post text
    image_prompt: str     # Prompt for image generation
    content_type: str     # statistical_method | data_analytics_tip | case_study | ...
    main_topic: str       # 2-5 word topic label
    resume_reference: bool = False        # True if post references Nikita's real experience
    project_mentioned: str | None = None  # Project name if referenced
