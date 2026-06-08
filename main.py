import asyncio
import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from modules.content_router import ContentRouter, needs_fresh_context
from modules.context_store import ContextStore
from modules.generator import ContentGenerator
from modules.images import ImageFetcher, PERSONAL_POST_TYPES, GPT_IMAGE_TYPES
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
    notion = NotionLogger(token=cfg.notion_token, database_id=cfg.notion_database_id)
    linkedin = LinkedInPublisher(access_token=cfg.linkedin_access_token,
                                 person_urn=cfg.linkedin_person_urn,
                                 token_issued_at=cfg.linkedin_token_issued_at)

    context_store = ContextStore(token=cfg.notion_token, context_db_id=cfg.notion_context_db_id)
    router = ContentRouter()

    images = ImageFetcher(
        unsplash_key=cfg.unsplash_access_key,
        openai_key=cfg.openai_api_key,
        use_gpt_image=cfg.use_gpt_image,
        notion_blacklist_getter=context_store.get_used_unsplash_ids if context_store.is_available() else None,
        notion_blacklist_setter=context_store.mark_unsplash_used if context_store.is_available() else None,
    )

    async def run_pipeline():
        logger.info("Pipeline started")
        if linkedin.is_token_expiring_soon():
            await bot.app.bot.send_message(
                chat_id=cfg.telegram_chat_id,
                text="⚠️ LinkedIn token expires soon (≥55 days). Refresh at developers.linkedin.com.",
            )

        # --- Content type routing (D-04) ---
        recent_types = notion.get_recent_post_types(n=30)
        entries = context_store.get_unused_entries(limit=10) if context_store.is_available() else []
        has_fresh = bool(entries)
        post_type = router.choose_post_type(recent_types, has_fresh_context=has_fresh)
        logger.info("ContentRouter selected post_type=%r (has_fresh_context=%s)", post_type, has_fresh)

        # --- Content generation ---
        if needs_fresh_context(post_type) and entries:
            # Personal post path: use context entry
            post_text = generator.generate_personal(entries, post_type)
            if context_store.is_available():
                context_store.mark_entry_used(entries[0]["id"])
            article = Article(
                title="Personal Post",
                url="",
                summary=entries[0]["text"],
                source="Context",
                published_at="",
                keywords=[],
            )
            logger.info("Generated personal post: post_type=%r, category=%r",
                        post_type, entries[0].get("category", ""))
        elif needs_fresh_context(post_type) and not entries:
            # Degradation: no context available → fall back to news_insight
            logger.warning(
                "No context entries available for post_type=%r — degrading to news_insight",
                post_type,
            )
            post_type = "news_insight"
            article = news.fetch(already_published_urls=notion.get_published_urls())
            if not article:
                logger.warning("No new articles — skipping this run")
                await bot.app.bot.send_message(chat_id=cfg.telegram_chat_id,
                                               text="ℹ️ No new articles found today.")
                return
            post_text = generator.generate(article)
        else:
            # News pipeline path (news_insight)
            article = news.fetch(already_published_urls=notion.get_published_urls())
            if not article:
                logger.warning("No new articles — skipping this run")
                await bot.app.bot.send_message(chat_id=cfg.telegram_chat_id,
                                               text="ℹ️ No new articles found today.")
                return
            post_text = generator.generate(article)

        # --- Image selection (three-tier strategy) ---
        image_url = ""
        image_bytes: bytes | None = None
        photo_path: str | None = None

        if post_type in PERSONAL_POST_TYPES:
            # Tier 1b: real profile photo for personal types
            photo_path = images.fetch_profile_photo(post_type)
            if photo_path:
                image_url = photo_path
                logger.info("Using profile photo for post_type=%r: %s", post_type, photo_path)
            else:
                # Fallback to gpt-image-1 if no profile photo available
                image_bytes = images.fetch_gpt_image(post_type, post_text)
                if image_bytes:
                    image_url = "[gpt-image-1]"
                    logger.info("Profile photo not found — using gpt-image-1 for post_type=%r", post_type)
        elif post_type in GPT_IMAGE_TYPES:
            # Tier 1a: gpt-image-1 AI scene for impersonal types
            image_bytes = images.fetch_gpt_image(post_type, post_text)
            if image_bytes:
                image_url = "[gpt-image-1]"
                logger.info("Using gpt-image-1 for post_type=%r", post_type)

        if not image_url:
            # Tier 2: Unsplash fallback
            image_keywords = generator.suggest_image_keywords(article.title, post_text)
            candidates = images.fetch_candidates(
                keywords=image_keywords or getattr(article, "keywords", None) or [article.title.split()[0]]
            )
            image_url = generator.pick_best_image(candidates, post_text)
            images.mark_used(image_url, candidates)

        topics = article.keywords[:5] if article.keywords else ["AI"]
        record = notion.create_draft(article, post_text, image_url, topics, post_type=post_type)
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
                                 source="Custom", published_at="", keywords=image_keywords or ["Custom"])
        record = notion.create_draft(custom_article, post_text, image_url, ["Custom"])
        notion.update_status(record.notion_page_id, "Pending")
        record.status = "Pending"
        await bot.send_custom_preview(record)

    async def on_new_image(record: PostRecord):
        """Regenerate only the image for an existing post and update Notion + send preview."""
        pt = record.post_type or "news_insight"
        image_bytes: bytes | None = None
        photo_path: str | None = None
        new_image_url = ""

        if pt in PERSONAL_POST_TYPES:
            photo_path = images.fetch_profile_photo(pt)
            if photo_path:
                new_image_url = photo_path
            else:
                image_bytes = images.fetch_gpt_image(pt, record.post_text)
                if image_bytes:
                    new_image_url = "[gpt-image-1]"
        elif pt in GPT_IMAGE_TYPES:
            image_bytes = images.fetch_gpt_image(pt, record.post_text)
            if image_bytes:
                new_image_url = "[gpt-image-1]"

        if not new_image_url:
            # Fallback to Unsplash
            candidates = images.fetch_candidates(keywords=[record.title.split()[0]] if record.title else ["professional"])
            new_image_url = generator.pick_best_image(candidates, record.post_text)
            images.mark_used(new_image_url, candidates)

        notion.update_status(record.notion_page_id, record.status, image_url=new_image_url)
        updated_record = PostRecord(
            notion_page_id=record.notion_page_id,
            title=record.title,
            status=record.status,
            source_url=record.source_url,
            post_text=record.post_text,
            image_url=new_image_url,
            topics=record.topics,
            feedback=record.feedback,
            generation_count=record.generation_count,
            post_type=record.post_type,
        )
        await bot.send_preview(
            Article(title=record.title, url=record.source_url or "",
                    summary="", source="", published_at="", keywords=[]),
            updated_record,
        )
        logger.info("on_new_image: updated image for page_id=%s", record.notion_page_id)

    async def on_context_entry(category: str, text: str):
        """Save a new personal context entry from the Telegram questionnaire."""
        # T-09-02: log only category, not text content
        context_store.add_entry(category=category, text=text)
        logger.info("Context entry saved: category=%s", category)

    return run_pipeline, on_publish, on_skip, on_regenerate, on_custom_post, on_new_image, on_context_entry


async def main():
    cfg = load_config()
    try:
        hour, minute = cfg.post_time_utc.split(":")
        int(hour)
        int(minute)
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid POST_TIME_UTC={cfg.post_time_utc!r}: expected HH:MM format"
        ) from e

    try:
        raw_days = [d.strip() for d in cfg.post_schedule.split(",") if d.strip()]
        unknown = [d for d in raw_days if d not in DOW_MAP]
        if unknown:
            logger.warning("Unknown day(s) in POST_SCHEDULE, ignoring: %s", unknown)
        days = ",".join(DOW_MAP[d] for d in raw_days if d in DOW_MAP)
        if not days:
            raise ValueError(f"POST_SCHEDULE={cfg.post_schedule!r} contains no valid days")
    except (AttributeError, TypeError) as e:
        raise ValueError(
            f"Invalid POST_SCHEDULE={cfg.post_schedule!r}: expected comma-separated day abbreviations"
        ) from e

    _refs: dict = {}

    async def on_publish(r): await _refs["publish"](r)
    async def on_skip(r):
        await _refs["skip"](r)
        await _refs["pipeline"]()
    async def on_regen(a, r, f): return await _refs["regen"](a, r, f)
    async def manual_trigger(): await _refs["pipeline"]()
    async def on_custom(text): await _refs["custom"](text)
    async def on_new_image_func(r): await _refs["new_image"](r)
    async def on_context_entry_func(category, text): await _refs["context_entry"](category, text)

    bot = PostApprovalBot(
        token=cfg.telegram_bot_token, chat_id=cfg.telegram_chat_id,
        on_publish=on_publish, on_skip=on_skip, on_regenerate=on_regen,
        on_custom_post=on_custom, dry_run=cfg.dry_run, manual_trigger=manual_trigger,
        on_new_image=on_new_image_func,
        on_context_entry=on_context_entry_func,
    )

    (run_pipeline, on_publish_real, on_skip_real, on_regen_real,
     on_custom_real, on_new_image_real, on_context_entry_real) = build_pipeline(cfg, bot)
    _refs.update({
        "pipeline": run_pipeline,
        "publish": on_publish_real,
        "skip": on_skip_real,
        "regen": on_regen_real,
        "custom": on_custom_real,
        "new_image": on_new_image_real,
        "context_entry": on_context_entry_real,
    })

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_pipeline, CronTrigger(day_of_week=days,
                                                hour=int(hour), minute=int(minute),
                                                jitter=7200))
    scheduler.add_job(bot.check_timeout, "interval", hours=1)

    # Questionnaire scheduler (D-04: TUE,FRI by default via QUESTIONNAIRE_SCHEDULE)
    if cfg.questionnaire_schedule:
        raw_q_days = [d.strip() for d in cfg.questionnaire_schedule.split(",") if d.strip()]
        q_days = ",".join(DOW_MAP[d] for d in raw_q_days if d in DOW_MAP)
        if q_days:
            scheduler.add_job(bot.send_questionnaire, CronTrigger(day_of_week=q_days, hour=7, minute=0))
            logger.info("Questionnaire scheduled: %s at 07:00 UTC", cfg.questionnaire_schedule)
        else:
            logger.warning("QUESTIONNAIRE_SCHEDULE=%r contains no valid days — questionnaire disabled",
                           cfg.questionnaire_schedule)

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
