# main.py
import asyncio
import logging
import re
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from modules.content_memory import ContentMemory
from modules.generator import ContentGenerator
from modules.images import ImageFetcher
from modules.interaction_agent import InteractionAgent
from modules.linkedin import LinkedInPublisher
from modules.models import Article, PostRecord
from modules.news import NewsCollector
from modules.notion import NotionLogger
from modules.telegram_bot import PostApprovalBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROFILE_PATH = Path(__file__).parent / "data" / "profile.md"

DOW_MAP = {"MON": "mon", "TUE": "tue", "WED": "wed", "THU": "thu",
           "FRI": "fri", "SAT": "sat", "SUN": "sun"}


def build_pipeline(cfg, bot: PostApprovalBot, scheduler: AsyncIOScheduler):
    profile_text = PROFILE_PATH.read_text(encoding="utf-8")
    news = NewsCollector(newsapi_key=cfg.newsapi_key)
    generator = ContentGenerator(api_key=cfg.anthropic_api_key, profile_text=profile_text)
    images = ImageFetcher(
        unsplash_key=cfg.unsplash_access_key,
        use_dalle=cfg.use_dalle,
        openai_key=cfg.openai_api_key,
        huggingface_key=cfg.huggingface_api_key,
    )
    notion = NotionLogger(token=cfg.notion_token, database_id=cfg.notion_database_id)
    linkedin = LinkedInPublisher(
        access_token=cfg.linkedin_access_token,
        person_urn=cfg.linkedin_person_urn,
        token_issued_at=cfg.linkedin_token_issued_at,
    )
    memory = ContentMemory(notion=notion)
    interaction = InteractionAgent(
        linkedin=linkedin,
        generator=generator,
        notion=notion,
        enabled=not cfg.dry_run,
    )

    async def run_pipeline():
        logger.info("Pipeline started")
        if linkedin.is_token_expiring_soon():
            await bot.app.bot.send_message(
                chat_id=cfg.telegram_chat_id,
                text="⚠️ LinkedIn token expires soon (≥55 days). Refresh at developers.linkedin.com.",
            )
        already_published = notion.get_published_urls()
        article = news.fetch(already_published_urls=already_published)
        if not article:
            logger.warning("No new articles — skipping this run")
            await bot.app.bot.send_message(
                chat_id=cfg.telegram_chat_id, text="ℹ️ No new articles found today."
            )
            return

        # Goal 3: query history before generation
        recent_posts = memory.get_recent_posts(cfg.content_memory_lookback)
        content_type = memory.pick_content_type(recent_posts)
        forbidden = memory.get_forbidden_topics(recent_posts)

        # Goal 1: structured generation with content type + forbidden topics
        generated = generator.generate(article, content_type=content_type, forbidden_topics=forbidden)

        # Goal 2: Pollinations first, Unsplash fallback
        image_url = images.get_image(generated.image_prompt, fallback_query=article.title)

        topics = article.keywords[:5] if article.keywords else ["Data Analytics"]
        record = notion.create_draft(
            article, generated.post_text, image_url, topics,
            content_type=generated.content_type,
            main_topic=generated.main_topic,
            resume_reference=generated.resume_reference,
            project_mentioned=generated.project_mentioned,
        )
        notion.update_status(record.notion_page_id, "Pending")
        record.status = "Pending"
        await bot.send_preview(article, record)

    async def on_publish(record: PostRecord):
        url = linkedin.publish(text=record.post_text, image_url=record.image_url)
        notion.update_status(record.notion_page_id, "Published", linkedin_url=url)
        logger.info("Published: %s", url)
        # Goal 4: schedule auto-comments after publish
        # Extract numeric post ID from URL (handles both urn:li:ugcPost and urn:li:activity)
        if url and not cfg.dry_run:
            m = re.search(r"(\d{10,})", url)
            post_id = m.group(1) if m else ""
            if post_id:
                await interaction.schedule_first_comment(
                    post_id, record.post_text, record.notion_page_id, scheduler
                )
                await interaction.schedule_boost_check(
                    post_id, record.post_text, cfg.engagement_threshold, scheduler
                )

    async def on_skip(record: PostRecord):
        notion.update_status(record.notion_page_id, "Skipped")
        logger.info("Skipped: %s", record.notion_page_id)

    async def on_regenerate(article: Article, old_record: PostRecord, feedback: str) -> PostRecord:
        generated = generator.regenerate(article, old_record.post_text, feedback)
        image_url = images.get_image(generated.image_prompt, fallback_query=article.title)
        count = old_record.generation_count + 1
        notion.update_status(
            old_record.notion_page_id, "Pending",
            post_text=generated.post_text, feedback=feedback, generation_count=count,
        )
        return PostRecord(
            notion_page_id=old_record.notion_page_id, title=old_record.title,
            status="Pending", source_url=old_record.source_url,
            post_text=generated.post_text,
            image_url=image_url or old_record.image_url,
            topics=old_record.topics, feedback=feedback, generation_count=count,
        )

    async def on_custom_post(raw_text: str):
        post_text = generator.generate_from_custom(raw_text)
        # Bug fix: was `keywords` (undefined) → corrected to `image_keywords`
        image_keywords = generator.suggest_image_keywords("Custom Post", post_text)
        image_url = images.get_image(
            "", fallback_query=image_keywords[0] if image_keywords else "data analytics"
        )
        custom_article = Article(
            title="Custom Post", url="", summary=raw_text,
            source="Custom", published_at="", keywords=image_keywords or [],
        )
        record = notion.create_draft(custom_article, post_text, image_url, ["Custom"])
        notion.update_status(record.notion_page_id, "Pending")
        record.status = "Pending"
        await bot.send_custom_preview(record)

    return run_pipeline, on_publish, on_skip, on_regenerate, on_custom_post


async def main():
    cfg = load_config()
    hour, minute = cfg.post_time_utc.split(":")
    days = ",".join(DOW_MAP[d.strip()] for d in cfg.post_schedule.split(",")
                    if d.strip() in DOW_MAP)

    _refs: dict = {}

    async def on_publish(r): await _refs["publish"](r)
    async def on_skip(r): await _refs["skip"](r)
    async def on_regen(a, r, f): return await _refs["regen"](a, r, f)
    async def manual_trigger(): await _refs["pipeline"]()
    async def on_custom(text): await _refs["custom"](text)

    bot = PostApprovalBot(
        token=cfg.telegram_bot_token, chat_id=cfg.telegram_chat_id,
        on_publish=on_publish, on_skip=on_skip, on_regenerate=on_regen,
        on_custom_post=on_custom, dry_run=cfg.dry_run, manual_trigger=manual_trigger,
    )

    scheduler = AsyncIOScheduler(timezone="UTC")

    run_pipeline, on_publish_real, on_skip_real, on_regen_real, on_custom_real = build_pipeline(
        cfg, bot, scheduler
    )
    _refs.update({
        "pipeline": run_pipeline, "publish": on_publish_real,
        "skip": on_skip_real, "regen": on_regen_real, "custom": on_custom_real,
    })

    scheduler.add_job(
        run_pipeline,
        CronTrigger(day_of_week=days, hour=int(hour), minute=int(minute), jitter=7200),
    )
    scheduler.add_job(bot.check_timeout, "interval", hours=1)
    scheduler.start()
    logger.info("Scheduler started: %s at %s UTC on days=%s", cfg.post_schedule, cfg.post_time_utc, days)

    await bot.app.initialize()
    await bot.app.start()
    await bot.app.updater.start_polling()
    logger.info("Bot polling started")

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await bot.app.updater.stop()
        await bot.app.stop()


if __name__ == "__main__":
    asyncio.run(main())
