import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    anthropic_api_key: str
    newsapi_key: str
    unsplash_access_key: str
    use_dalle: bool
    openai_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    linkedin_access_token: str
    linkedin_person_urn: str
    linkedin_token_issued_at: str
    notion_token: str
    notion_database_id: str
    post_schedule: str
    post_time_utc: str
    timezone: str
    dry_run: bool


def load_config() -> Config:
    return Config(
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        newsapi_key=_require("NEWSAPI_KEY"),
        unsplash_access_key=_require("UNSPLASH_ACCESS_KEY"),
        use_dalle=os.getenv("USE_DALLE", "false").lower() == "true",
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
        linkedin_access_token=_require("LINKEDIN_ACCESS_TOKEN"),
        linkedin_person_urn=_require("LINKEDIN_PERSON_URN"),
        linkedin_token_issued_at=os.getenv("LINKEDIN_TOKEN_ISSUED_AT", ""),
        notion_token=_require("NOTION_TOKEN"),
        notion_database_id=_require("NOTION_DATABASE_ID"),
        post_schedule=os.getenv("POST_SCHEDULE", "MON,WED,FRI"),
        post_time_utc=os.getenv("POST_TIME_UTC", "05:00"),
        timezone=os.getenv("TIMEZONE", "Asia/Dubai"),
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
    )


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Required env var {key} is not set")
    return val
