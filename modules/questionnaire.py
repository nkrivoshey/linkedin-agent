"""
modules/questionnaire.py

State machine and constants for the proactive Telegram questionnaire.
Ported from .planning/spikes/002-proactive-questionnaire/questionnaire_spike.py (lines 29-85).

This module is intentionally free of Telegram bot handlers — it contains only:
  - CATEGORIES dict (4 categories with label / question / callback)
  - CALLBACK_TO_CATEGORY, CALLBACK_DONE, CALLBACK_ADD_MORE constants
  - QuestionnaireState dataclass (state machine)
  - category_keyboard() helper that builds the InlineKeyboardMarkup

No imports from telegram_bot.py — QuestionnaireState is independent of BotState.
The QuestionnaireState instance is created inside PostApprovalBot (plan 8).
"""

from dataclasses import dataclass, field
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ── Category definitions ───────────────────────────────────────────────────────

CATEGORIES: dict[str, dict] = {
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

CALLBACK_TO_CATEGORY: dict[str, str] = {v["callback"]: k for k, v in CATEGORIES.items()}
CALLBACK_DONE: str = "ctx_done"
CALLBACK_ADD_MORE: str = "ctx_more"


# ── State machine ──────────────────────────────────────────────────────────────

@dataclass
class QuestionnaireState:
    """State machine for a single questionnaire session.

    Lifecycle:
      (inactive) --start()--> active, waiting for category selection
                --category_selected(cat)--> waiting_for_response=True
                --response_received(text)--> entry dict returned, back to category selection
                --finish()--> inactive

    Independent of BotState — no shared fields, no imports from telegram_bot.py.
    """

    active: bool = False
    waiting_for_response: bool = False
    current_category: str | None = None
    entries_this_session: list[dict] = field(default_factory=list)

    def start(self) -> None:
        """Begin a new questionnaire session."""
        self.active = True
        self.waiting_for_response = False
        self.current_category = None
        self.entries_this_session = []

    def category_selected(self, category: str) -> None:
        """Record the chosen category and signal that we expect a text response."""
        self.current_category = category
        self.waiting_for_response = True

    def response_received(self, text: str) -> dict:
        """Record the user's response and return the entry dict.

        Resets waiting_for_response so the user can pick another category.
        Returned dict keys: "category", "text", "created_at" (UTC ISO-8601).
        """
        entry = {
            "category": self.current_category,
            "text": text,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.entries_this_session.append(entry)
        self.waiting_for_response = False
        self.current_category = None
        return entry

    def finish(self) -> None:
        """End the questionnaire session."""
        self.active = False
        self.waiting_for_response = False
        self.current_category = None


# ── Keyboard helper ────────────────────────────────────────────────────────────

def category_keyboard() -> InlineKeyboardMarkup:
    """Build the InlineKeyboardMarkup for category selection.

    One button per category (vertical layout) plus a "Done" button at the bottom.
    """
    buttons = [
        [InlineKeyboardButton(CATEGORIES[cat]["label"], callback_data=CATEGORIES[cat]["callback"])]
        for cat in CATEGORIES
    ]
    buttons.append([InlineKeyboardButton("Done", callback_data=CALLBACK_DONE)])
    return InlineKeyboardMarkup(buttons)
