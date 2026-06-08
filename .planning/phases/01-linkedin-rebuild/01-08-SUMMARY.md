---
phase: 01-linkedin-rebuild
plan: 8
subsystem: telegram-bot
tags: [telegram, ui, questionnaire, callback, state-machine]
dependency_graph:
  requires:
    - 01-04-context-store-questionnaire  # QuestionnaireState, category_keyboard
  provides:
    - CALLBACK_NEW_IMAGE handler
    - QuestionnaireState integration in PostApprovalBot
    - send_questionnaire() method
  affects:
    - modules/telegram_bot.py
tech_stack:
  added: []
  patterns:
    - Dual state machine (BotState + QuestionnaireState, separated per D-03)
    - Immediate query.answer() for long-running callbacks (T-08-03 mitigation)
    - Whitelist callback_data validation via CALLBACK_TO_CATEGORY dict
key_files:
  modified:
    - modules/telegram_bot.py
decisions:
  - "BotState and QuestionnaireState remain fully separate per D-03 LOCKED decision"
  - "query.answer() called conditionally — with status text for CALLBACK_NEW_IMAGE to show progress indicator, silent for other callbacks"
  - "Questionnaire callbacks checked before approval flow in _handle_callback to prevent ctx_* data from triggering approval guards"
metrics:
  duration: "~15 min"
  completed: "2026-06-08"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 01 Plan 08: Telegram Bot — New Image Button + QuestionnaireState Summary

**One-liner:** APPROVAL_KEYBOARD extended with 2-row layout (New Image button) and QuestionnaireState integrated as separate state machine in PostApprovalBot with category/text/done callback handlers.

## What Was Built

### Task 1: Add CALLBACK_NEW_IMAGE and QuestionnaireState to telegram_bot.py

Updated `modules/telegram_bot.py` with two independent changes:

**Change 1 — New Image button (REQ-03):**
- `CALLBACK_NEW_IMAGE = "new_image"` constant added
- `APPROVAL_KEYBOARD` restructured into 2 rows: row 1 keeps existing [Publish, Regenerate, Skip], row 2 adds [🖼️ New Image]
- `_handle_callback` handles `CALLBACK_NEW_IMAGE`: calls `query.answer("🔄 Generating new image...")` immediately (T-08-03 DoS mitigation), then calls `self.on_new_image(record)` if wired

**Change 2 — QuestionnaireState integration (REQ-04):**
- Import: `QuestionnaireState, CATEGORIES, CALLBACK_TO_CATEGORY, CALLBACK_DONE, category_keyboard` from `modules.questionnaire`
- `self._q_state = QuestionnaireState()` added to `__init__`
- `self.context_store = None` placeholder added (to be wired in plan-09)
- `on_new_image` and `on_context_entry` parameters added to `__init__` (both `None` default — backward compatible)
- `_handle_callback`: questionnaire callbacks (`ctx_work`, `ctx_life`, `ctx_learning`, `ctx_opinion`, `ctx_done`) handled FIRST, before approval flow — whitelist check via `CALLBACK_TO_CATEGORY` dict
- `_handle_text`: `_q_state.active and _q_state.waiting_for_response` check placed BEFORE `waiting_for_custom_text` check per D-03 requirement
- `send_questionnaire()` method: starts `_q_state`, sends category keyboard to chat

## Commits

| Hash | Message |
|------|---------|
| 350bad9 | feat(01-08): add New Image button and QuestionnaireState integration to telegram bot |

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed double query.answer() for CALLBACK_NEW_IMAGE**
- **Found during:** Task 1 code review
- **Issue:** Standard approval flow called `await query.answer()` unconditionally, then `CALLBACK_NEW_IMAGE` branch called `await query.answer("🔄 Generating...")` again — double-answer causes Telegram API error
- **Fix:** Added `if data != CALLBACK_NEW_IMAGE:` guard before the standard `query.answer()` call so the status-text answer in the NEW_IMAGE branch is the only one called
- **Files modified:** modules/telegram_bot.py
- **Commit:** 350bad9 (included in same task commit)

## Threat Surface Scan

No new network endpoints or auth paths introduced. Changes are internal callback handlers within the existing Telegram bot. T-08-02 (callback_data whitelist) properly implemented via `if data in CALLBACK_TO_CATEGORY` check.

## Known Stubs

- `self.context_store = None` — placeholder for ContextStore wiring. Plan-09 (main.py) will set `bot.context_store = context_store_instance`. The `on_context_entry` callback is the primary path for context saving; `context_store` field is reserved for direct access if needed.

## Self-Check: PASSED

- [x] modules/telegram_bot.py exists and modified
- [x] Commit 350bad9 exists: `git log --oneline | grep 350bad9`
- [x] APPROVAL_KEYBOARD has 2 rows verified by automated test
- [x] on_new_image, on_context_entry params with None default verified
- [x] send_questionnaire method exists verified
- [x] _q_state checked before waiting_for_custom_text verified
