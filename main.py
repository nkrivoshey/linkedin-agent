import asyncio
import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from modules.generator import ContentGenerator
from modules.images import ImageFetcher
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


def build_pipeline(cfg, bot: PostApprovalBot):
    profile_text = PROFILE_PATH.read_text(encoding="utf-8")
    news = NewsCollector(newsapi_key=cfg.newsapi_key)
    generator = ContentGenerator(api_key=cfg.anthropic_api_key, profile_text=profile_text)
    images = ImageFetcher(unsplash_key=cfg.unsplash_access_key,
                          use_dalle=cfg.use_dalle, openai_key=cfg.openai_api_key)
    notion = NotionLogger(token=cfg.notion_token, database_id=cfg.notion_database_id)
    linkedin = LinkedInPublisher(access_token=cfg.linkedin_access_token,
                                 person_urn=cfg.linkedin_person_urn,
                                 token_issued_at=cfg.linkedin_token_issued_at)

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
            await bot.app.bot.send_message(chat_id=cfg.telegram_chat_id,
                                           text="ℹ️ No new articles found today.")
            return
        post_text = generator.generate(article)
        image_keywords = generator.suggest_image_keywords(article.title, post_text)
        candidates = images.fetch_candidates(keywords=image_keywords or article.keywords or [article.title.split()[0]])
        image_url = generator.pick_best_image(candidates, post_text)
        images.mark_used(image_url, candidates)
        topics = article.keywords[:5] if article.keywords else ["AI"]
        record = notion.create_draft(article, post_text, image_url, topics)
        notion.update_status(record.notion_page_id, "Pending")
        record.status = "Pending"
        await bot.send_preview(article, record)

    async def on_publish(record: PostRecord):
        url = linkedin.publish(text=record.post_text, image_url=record.image_url)
        notion.update_status(record.notion_page_id, "Published", linkedin_url=url)
        logger.info("Published: %s", url)

    async def on_skip(record: PostRecord):
        notion.update_status(record.notion_page_id, "Skipped")
        logger.info("Skipped: %s", record.notion_page_id)

    async def on_regenerate(article: Article, old_record: PostRecord, feedback: str) -> PostRecord:
        new_text = generator.regenerate(article, old_record.post_text, feedback)
        image_keywords = generator.suggest_image_keywords(article.title, new_text)
        candidates = images.fetch_candidates(keywords=image_keywords or article.keywords or [])
        new_image = generator.pick_best_image(candidates, new_text)
        images.mark_used(new_image, candidates)
        count = old_record.generation_count + 1
        notion.update_status(old_record.notion_page_id, "Pending",
                             post_text=new_text, feedback=feedback, generation_count=count)
        return PostRecord(
            notion_page_id=old_record.notion_page_id, title=old_record.title,
            status="Pending", source_url=old_record.source_url, post_text=new_text,
            image_url=new_image or old_record.image_url, topics=old_record.topics,
            feedback=feedback, generation_count=count,
        )

    async def on_custom_post(raw_text: str):
        post_text = generator.generate_from_custom(raw_text)
        image_keywords = generator.suggest_image_keywords("Custom Post", post_text)
        candidates = images.fetch_candidates(keywords=image_keywords or ["professional", "business"])
        image_url = generator.pick_best_image(candidates, post_text)
        images.mark_used(image_url, candidates)
        custom_article = Article(title="Custom Post", url="", summary=raw_text,
                                 source="Custom", published_at="", keywords=keywords)
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
    async def on_skip(r):
        await _refs["skip"](r)
        await _refs["pipeline"]()
    async def on_regen(a, r, f): return await _refs["regen"](a, r, f)
    async def manual_trigger(): await _refs["pipeline"]()
    async def on_custom(text): await _refs["custom"](text)

    bot = PostApprovalBot(
        token=cfg.telegram_bot_token, chat_id=cfg.telegram_chat_id,
        on_publish=on_publish, on_skip=on_skip, on_regenerate=on_regen,
        on_custom_post=on_custom, dry_run=cfg.dry_run, manual_trigger=manual_trigger,
    )

    run_pipeline, on_publish_real, on_skip_real, on_regen_real, on_custom_real = build_pipeline(cfg, bot)
    _refs.update({"pipeline": run_pipeline, "publish": on_publish_real,
                  "skip": on_skip_real, "regen": on_regen_real, "custom": on_custom_real})

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_pipeline, CronTrigger(day_of_week=days,
                                                hour=int(hour), minute=int(minute),
                                                jitter=7200))
    scheduler.add_job(bot.check_timeout, "interval", hours=1)
    scheduler.start()
    logger.info("Scheduler started: %s at %s UTC on days=%s", cfg.post_schedule,
                cfg.post_time_utc, days)

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
