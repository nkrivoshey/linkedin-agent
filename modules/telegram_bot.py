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
from modules.questionnaire import (
    QuestionnaireState, CATEGORIES, CALLBACK_TO_CATEGORY,
    CALLBACK_DONE, category_keyboard,
)

logger = logging.getLogger(__name__)

CALLBACK_PUBLISH = "publish"
CALLBACK_REGENERATE = "regenerate"
CALLBACK_SKIP = "skip"
CALLBACK_NEW_IMAGE = "new_image"

APPROVAL_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Publish Now", callback_data=CALLBACK_PUBLISH),
        InlineKeyboardButton("✏️ Regenerate", callback_data=CALLBACK_REGENERATE),
        InlineKeyboardButton("❌ Skip", callback_data=CALLBACK_SKIP),
    ],
    [
        InlineKeyboardButton("🖼️ New Image", callback_data=CALLBACK_NEW_IMAGE),
    ],
])


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
        on_new_image: Callable[[PostRecord], Coroutine] | None = None,
        on_context_entry: Callable[[str, str], Coroutine] | None = None,
    ):
        self.chat_id = chat_id
        self.on_publish = on_publish
        self.on_skip = on_skip
        self.on_regenerate = on_regenerate
        self.on_custom_post = on_custom_post
        self.dry_run = dry_run
        self.manual_trigger = manual_trigger
        self.on_new_image = on_new_image
        self.on_context_entry = on_context_entry
        self._state = BotState()
        self._q_state = QuestionnaireState()
        self.context_store = None
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

    async def send_questionnaire(self) -> None:
        """Start the weekly context questionnaire session."""
        self._q_state.start()
        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text="🧠 <b>Weekly Context Update</b>\n\nWhat do you want to share this week?\nPick a category:",
            parse_mode="HTML",
            reply_markup=category_keyboard(),
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data

        # Questionnaire callbacks handled first — whitelist check (T-08-02, D-03)
        if data in CALLBACK_TO_CATEGORY and self._q_state.active:
            await query.answer()
            category = CALLBACK_TO_CATEGORY[data]
            self._q_state.category_selected(category)
            question = CATEGORIES[category]["question"]
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=self.chat_id,
                text=f"<b>{CATEGORIES[category]['label']}</b>\n\n{question}",
                parse_mode="HTML",
            )
            return

        if data == CALLBACK_DONE and self._q_state.active:
            await query.answer()
            n = len(self._q_state.entries_this_session)
            self._q_state.finish()
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=self.chat_id,
                text=f"✅ Got {n} update{'s' if n != 1 else ''}! Next posts will feel alive 🔥",
            )
            return

        # Standard approval flow
        # For CALLBACK_NEW_IMAGE answer() is called with a status text further below (T-08-03)
        if data != CALLBACK_NEW_IMAGE:
            await query.answer()
        if self._state.current_record is None:
            await query.edit_message_reply_markup(reply_markup=None)
            return
        action = data
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
        elif action == CALLBACK_NEW_IMAGE:
            if self._state.current_record is None:
                return
            # answer() called immediately to clear Telegram pending state (T-08-03)
            await query.answer("🔄 Generating new image...")
            if self.on_new_image:
                await self.on_new_image(self._state.current_record)

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Questionnaire text handling — must come BEFORE BotState handlers (D-03)
        if self._q_state.active and self._q_state.waiting_for_response:
            entry = self._q_state.response_received(update.message.text)
            if self.on_context_entry:
                await self.on_context_entry(entry["category"], entry["text"])
            await update.message.reply_text(
                f"📝 Saved! (<i>{entry['category']}</i>)\n\nAdd another topic or tap Done:",
                parse_mode="HTML",
                reply_markup=category_keyboard(),
            )
            return

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
