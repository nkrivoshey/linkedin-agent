import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Coroutine

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)
from modules.models import Article, PostRecord

logger = logging.getLogger(__name__)

CALLBACK_PUBLISH = "publish"
CALLBACK_REGENERATE = "regenerate"
CALLBACK_SKIP = "skip"

APPROVAL_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Publish Now", callback_data=CALLBACK_PUBLISH),
    InlineKeyboardButton("✏️ Regenerate", callback_data=CALLBACK_REGENERATE),
    InlineKeyboardButton("❌ Skip", callback_data=CALLBACK_SKIP),
]])


@dataclass
class BotState:
    current_article: Article | None = None
    current_record: PostRecord | None = None
    waiting_for_feedback: bool = False
    waiting_for_custom_text: bool = False
    sent_at: datetime | None = None

    def is_idle(self) -> bool:
        return self.current_record is None and not self.waiting_for_custom_text

    def set_pending(self, article: Article, record: PostRecord) -> None:
        self.current_article = article
        self.current_record = record
        self.waiting_for_feedback = False
        self.waiting_for_custom_text = False
        self.sent_at = datetime.utcnow()

    def reset(self) -> None:
        self.current_article = None
        self.current_record = None
        self.waiting_for_feedback = False
        self.waiting_for_custom_text = False
        self.sent_at = None


class PostApprovalBot:
    def __init__(
        self,
        token: str,
        chat_id: str,
        on_publish: Callable[[PostRecord], Coroutine],
        on_skip: Callable[[PostRecord], Coroutine],
        on_regenerate: Callable[[Article, PostRecord, str], Coroutine],
        on_custom_post: Callable[[str], Coroutine] | None = None,
        dry_run: bool = False,
        manual_trigger: Callable[[], Coroutine] | None = None,
    ):
        self.chat_id = chat_id
        self.on_publish = on_publish
        self.on_skip = on_skip
        self.on_regenerate = on_regenerate
        self.on_custom_post = on_custom_post
        self.dry_run = dry_run
        self.manual_trigger = manual_trigger
        self._state = BotState()
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(CommandHandler("generate", self._handle_generate_command))
        self.app.add_handler(CommandHandler("dryrun", self._handle_dryrun_command))
        self.app.add_handler(CommandHandler("mypost", self._handle_mypost_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

    async def send_preview(self, article: Article, record: PostRecord) -> None:
        self._state.set_pending(article, record)
        dry_prefix = "<b>[DRY RUN]</b>\n" if self.dry_run else ""
        header = f"📰 <b>{html.escape(article.title)}</b>\n🔗 {html.escape(article.url)}"
        body = f"{dry_prefix}{html.escape(record.post_text)}"
        if record.image_url:
            await self.app.bot.send_photo(
                chat_id=self.chat_id, photo=record.image_url,
                caption=header, parse_mode="HTML",
            )
        await self.app.bot.send_message(
            chat_id=self.chat_id, text=body[:4096],
            parse_mode="HTML", reply_markup=APPROVAL_KEYBOARD,
        )

    async def send_custom_preview(self, record: PostRecord) -> None:
        self._state.set_pending(
            Article(title="Custom Post", url="", summary="", source="", published_at="", keywords=[]),
            record,
        )
        dry_prefix = "<b>[DRY RUN]</b>\n" if self.dry_run else ""
        body = f"✍️ <b>Your Post</b>\n\n{dry_prefix}{html.escape(record.post_text)}"
        if record.image_url:
            await self.app.bot.send_photo(
                chat_id=self.chat_id, photo=record.image_url,
                caption="✍️ <b>Your Post</b>", parse_mode="HTML",
            )
        await self.app.bot.send_message(
            chat_id=self.chat_id, text=body[:4096],
            parse_mode="HTML", reply_markup=APPROVAL_KEYBOARD,
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if self._state.current_record is None:
            await query.edit_message_reply_markup(reply_markup=None)
            return
        action = query.data
        if action == CALLBACK_PUBLISH:
            record = self._state.current_record
            self._state.reset()
            await query.edit_message_reply_markup(reply_markup=None)
            if not self.dry_run:
                await self.on_publish(record)
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text="✅ Published!" if not self.dry_run else "✅ [DRY RUN] Would publish.",
            )
        elif action == CALLBACK_SKIP:
            record = self._state.current_record
            self._state.reset()
            await query.edit_message_reply_markup(reply_markup=None)
            await self.on_skip(record)
            await self.app.bot.send_message(chat_id=self.chat_id, text="❌ Skipped.")
        elif action == CALLBACK_REGENERATE:
            self._state.waiting_for_feedback = True
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text="✏️ What should be changed? Write your comment:",
            )

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self._state.waiting_for_custom_text:
            raw_text = update.message.text
            self._state.waiting_for_custom_text = False
            await update.message.reply_text("✍️ Generating your post...")
            if self.on_custom_post:
                await self.on_custom_post(raw_text)
            return

        if not self._state.waiting_for_feedback or self._state.current_record is None:
            return
        feedback = update.message.text
        self._state.waiting_for_feedback = False
        article = self._state.current_article
        old_record = self._state.current_record
        await update.message.reply_text("🔄 Regenerating...")
        new_record = await self.on_regenerate(article, old_record, feedback)
        await self.send_preview(article, new_record)

    async def _handle_generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.manual_trigger:
            await update.message.reply_text("⚡ Generating new post...")
            await self.manual_trigger()
        else:
            await update.message.reply_text("Manual trigger not configured.")

    async def _handle_dryrun_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        original = self.dry_run
        self.dry_run = True
        await update.message.reply_text("🧪 Dry run mode ON. Generating...")
        if self.manual_trigger:
            await self.manual_trigger()
        self.dry_run = original

    async def _handle_mypost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._state.reset()
        self._state.waiting_for_custom_text = True
        await update.message.reply_text(
            "✍️ Write your raw text — an event, idea, case, or anything you want to share.\n"
            "I'll turn it into a polished LinkedIn post with an image."
        )

    async def check_timeout(self, timeout_hours: int = 24) -> None:
        if self._state.current_record is None or self._state.sent_at is None:
            return
        if datetime.utcnow() - self._state.sent_at > timedelta(hours=timeout_hours):
            record = self._state.current_record
            self._state.reset()
            await self.on_skip(record)
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=f"⏰ Post timed out after {timeout_hours}h — marked as Skipped.",
            )
