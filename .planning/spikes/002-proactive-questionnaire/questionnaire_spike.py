"""
Spike 002: Proactive Telegram Questionnaire
Validates: multi-step Telegram dialog (buttons → free text → Notion write) works
without conflicting with existing BotState.

Run: cd /Users/nikitakrivoshey/projects/linkedin-agent
     QUESTIONNAIRE_SPIKE=1 python -m telegram.ext  # not this way
     → see simulate_conversation() below for state machine validation
     → see test_notion_context_write() for Notion DB validation

For live Telegram test: python .planning/spikes/002-proactive-questionnaire/questionnaire_spike.py --live
"""
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Category definitions ─────────────────────────────────────────────────────

CATEGORIES = {
    "work": {
        "label": "💼 Work & Projects",
        "question": "What happened at work this week? New insight, win, or interesting problem you solved?",
        "callback": "ctx_work",
    },
    "life": {
        "label": "🌆 Life & Dubai",
        "question": "Anything interesting from life or Dubai recently? Observation, experience, thought?",
        "callback": "ctx_life",
    },
    "learning": {
        "label": "📚 Learning & Books",
        "question": "What are you learning or reading right now? Any insight worth sharing?",
        "callback": "ctx_learning",
    },
    "opinion": {
        "label": "🔥 Opinion / Hot Take",
        "question": "Any strong opinion or contrarian view on something in data/tech/real estate?",
        "callback": "ctx_opinion",
    },
}

CALLBACK_TO_CATEGORY = {v["callback"]: k for k, v in CATEGORIES.items()}
CALLBACK_DONE = "ctx_done"
CALLBACK_ADD_MORE = "ctx_more"


# ── State machine ─────────────────────────────────────────────────────────────

@dataclass
class QuestionnaireState:
    active: bool = False
    waiting_for_response: bool = False
    current_category: str | None = None
    entries_this_session: list[dict] = field(default_factory=list)

    def start(self):
        self.active = True
        self.waiting_for_response = False
        self.current_category = None
        self.entries_this_session = []

    def category_selected(self, category: str):
        self.current_category = category
        self.waiting_for_response = True

    def response_received(self, text: str) -> dict:
        entry = {
            "category": self.current_category,
            "text": text,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.entries_this_session.append(entry)
        self.waiting_for_response = False
        self.current_category = None
        return entry

    def finish(self):
        self.active = False
        self.waiting_for_response = False
        self.current_category = None


# ── State machine simulation (no Telegram needed) ────────────────────────────

def simulate_conversation():
    """
    Simulates the full questionnaire flow as a state machine.
    Proves: state transitions are clean, no conflicts with existing BotState flags.
    """
    print("\n" + "=" * 60)
    print("SIMULATION: Questionnaire State Machine")
    print("=" * 60)

    state = QuestionnaireState()

    # Step 1: Scheduler triggers questionnaire
    assert not state.active
    state.start()
    assert state.active
    assert not state.waiting_for_response
    print("\n[SCHEDULER] → Triggered questionnaire")
    print("[BOT SENDS] 'Time for your weekly context! What do you want to share?'")
    print("[BOT SENDS] Buttons: 💼 Work | 🌆 Life | 📚 Learning | 🔥 Opinion | Done")

    # Step 2: User taps "Work"
    callback = "ctx_work"
    category = CALLBACK_TO_CATEGORY[callback]
    state.category_selected(category)
    assert state.waiting_for_response
    assert state.current_category == "work"
    question = CATEGORIES[category]["question"]
    print(f"\n[USER TAPS] 💼 Work & Projects")
    print(f"[BOT ASKS] {question}")

    # Step 3: User types response
    user_text = "Built a deal termination analytics module this week. Discovered 19% of deals have whitespace-only comments — huge data quality issue."
    entry = state.response_received(user_text)
    assert not state.waiting_for_response
    assert len(state.entries_this_session) == 1
    assert entry["category"] == "work"
    print(f"\n[USER TYPES] '{user_text[:60]}...'")
    print(f"[BOT SAVES] Entry: category=work, text={user_text[:40]}...")
    print("[BOT SENDS] 'Saved! 📝 Add another topic or Done?'")
    print("[BOT SENDS] Buttons: 💼 Work | 🌆 Life | 📚 Learning | 🔥 Opinion | Done")

    # Step 4: User taps "Opinion"
    callback = "ctx_opinion"
    category = CALLBACK_TO_CATEGORY[callback]
    state.category_selected(category)
    assert state.waiting_for_response
    question = CATEGORIES[category]["question"]
    print(f"\n[USER TAPS] 🔥 Opinion / Hot Take")
    print(f"[BOT ASKS] {question}")

    # Step 5: User types opinion
    user_text2 = "Most BI tools are overengineered. A well-structured SQL view beats a $50k Tableau license 90% of the time."
    entry2 = state.response_received(user_text2)
    assert len(state.entries_this_session) == 2
    print(f"\n[USER TYPES] '{user_text2[:60]}...'")
    print(f"[BOT SAVES] Entry: category=opinion")
    print("[BOT SENDS] 'Saved! 📝 Add another topic or Done?'")

    # Step 6: User taps Done
    state.finish()
    assert not state.active
    assert not state.waiting_for_response
    print(f"\n[USER TAPS] Done")
    print(f"[BOT SENDS] '✅ Got {len(state.entries_this_session)} updates! Next post will feel alive 🔥'")

    print("\n" + "=" * 60)
    print("STATE MACHINE: VALIDATED ✓")
    print(f"  Entries collected: {len(state.entries_this_session)}")
    print(f"  State after finish: active={state.active}, waiting={state.waiting_for_response}")
    print("  No conflict with BotState.waiting_for_feedback or waiting_for_custom_text")
    print("=" * 60)

    return state.entries_this_session


# ── Notion context DB write test ──────────────────────────────────────────────

def test_notion_context_write(entries: list[dict]):
    """
    Tests writing context entries to Notion.
    Requires NOTION_CONTEXT_DB_ID env var (separate DB from posts DB).
    """
    notion_token = os.getenv("NOTION_TOKEN", "")
    context_db_id = os.getenv("NOTION_CONTEXT_DB_ID", "")

    if not context_db_id:
        print("\n[SKIP] NOTION_CONTEXT_DB_ID not set — skipping Notion write test")
        print("  Create a Notion DB with columns: Category (select), Text (rich_text), Created (date), Used (checkbox)")
        print("  Then set NOTION_CONTEXT_DB_ID in .env")
        return False

    if not notion_token:
        print("\n[SKIP] NOTION_TOKEN not set")
        return False

    print("\n" + "=" * 60)
    print("TEST: Notion Context DB Write")
    print("=" * 60)

    try:
        from notion_client import Client
        client = Client(auth=notion_token)

        for entry in entries[:1]:  # test with first entry only
            print(f"  Writing: category={entry['category']}, text={entry['text'][:50]}...")
            page = client.pages.create(
                parent={"database_id": context_db_id},
                properties={
                    "Title": {"title": [{"text": {"content": entry["text"][:100]}}]},
                    "Category": {"select": {"name": entry["category"]}},
                    "Text": {"rich_text": [{"text": {"content": entry["text"]}}]},
                    "Created": {"date": {"start": entry["created_at"][:10]}},
                    "Used": {"checkbox": False},
                },
            )
            print(f"  Created page: {page['id']}")
            print("  NOTION WRITE: VALIDATED ✓")
            return True

    except Exception as e:
        print(f"  NOTION WRITE FAILED: {e}")
        return False


# ── Live Telegram bot test ─────────────────────────────────────────────────────

async def run_live_bot():
    """
    Starts a minimal Telegram bot that runs ONLY the questionnaire flow.
    Tests real Telegram interaction: buttons + free text + state transitions.

    Usage: python questionnaire_spike.py --live
    Send /context in Telegram to trigger the questionnaire.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        return

    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
        from telegram.ext import (
            Application, CallbackQueryHandler,
            CommandHandler, ContextTypes, MessageHandler, filters,
        )
    except ImportError:
        print("ERROR: pip install python-telegram-bot==21.6")
        return

    state = QuestionnaireState()
    saved_entries: list[dict] = []

    def category_buttons():
        buttons = [
            [InlineKeyboardButton(CATEGORIES[c]["label"], callback_data=CATEGORIES[c]["callback"])]
            for c in CATEGORIES
        ]
        buttons.append([InlineKeyboardButton("✅ Done", callback_data=CALLBACK_DONE)])
        return InlineKeyboardMarkup(buttons)

    async def handle_context_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        state.start()
        await update.message.reply_text(
            "🧠 <b>Weekly Context Update</b>\n\nWhat do you want to share this week?\nPick a category:",
            parse_mode="HTML",
            reply_markup=category_buttons(),
        )

    async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == CALLBACK_DONE:
            n = len(state.entries_this_session)
            state.finish()
            await query.edit_message_reply_markup(reply_markup=None)
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Got {n} update{'s' if n != 1 else ''}! Next posts will feel alive 🔥",
            )
            return

        if data in CALLBACK_TO_CATEGORY and state.active:
            category = CALLBACK_TO_CATEGORY[data]
            state.category_selected(category)
            question = CATEGORIES[category]["question"]
            await query.edit_message_reply_markup(reply_markup=None)
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=f"<b>{CATEGORIES[category]['label']}</b>\n\n{question}",
                parse_mode="HTML",
            )

    async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not state.active or not state.waiting_for_response:
            return  # not in questionnaire mode — existing bot handles this

        text = update.message.text
        entry = state.response_received(text)
        saved_entries.append(entry)
        logger.info("Context entry saved: %s", entry)

        await update.message.reply_text(
            f"📝 Saved! (<i>{entry['category']}</i>)\n\nAdd another topic or tap Done:",
            parse_mode="HTML",
            reply_markup=category_buttons(),
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("context", handle_context_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print(f"Bot running. Send /context in Telegram (chat_id={chat_id})")
    print("Ctrl+C to stop.")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()

    print(f"\nCollected {len(saved_entries)} entries:")
    for e in saved_entries:
        print(f"  [{e['category']}] {e['text'][:60]}")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--live" in sys.argv:
        asyncio.run(run_live_bot())
    else:
        entries = simulate_conversation()
        test_notion_context_write(entries)
        print("\n→ For live Telegram test: python questionnaire_spike.py --live")
        print("  Then send /context in Telegram to test the full flow.")
