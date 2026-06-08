---
plan: 01-04-context-store-questionnaire
status: complete
phase: 01-linkedin-rebuild
---

## Summary

Созданы два новых модуля: `modules/context_store.py` и `modules/questionnaire.py`.

## What Was Built

**ContextStore** (`modules/context_store.py`):
- Notion CRUD для базы личного контекста (NOTION_CONTEXT_DB_ID)
- `is_available()` → False при пустом context_db_id (graceful no-op)
- `add_entry(category, text)` → page_id | None (text ≤2000, title ≤100 символов)
- `get_unused_entries(limit=10)` → [{"id","category","text"}] фильтр Used==False
- `mark_entry_used(page_id)` → Used=True
- `get_used_unsplash_ids()` / `mark_unsplash_used(image_id)` → Notion-persisted blacklist через страницу `__unsplash_blacklist__`
- Все вызовы Notion в try/except

**QuestionnaireState** (`modules/questionnaire.py`):
- Точный перенос из spike 002 (строки 29-85)
- `CATEGORIES`: 4 ключа — work, life, learning, opinion (каждый: label, question, callback)
- `CALLBACK_TO_CATEGORY`, `CALLBACK_DONE="ctx_done"`, `CALLBACK_ADD_MORE="ctx_more"`
- State machine: `start()` → `category_selected(cat)` → `response_received(text)` → `finish()`
- `category_keyboard()` → InlineKeyboardMarkup с кнопками категорий + ✅ Done
- Независим от BotState (нет импортов из telegram_bot)

## Key Files

- `modules/context_store.py` — новый файл (233 строки)
- `modules/questionnaire.py` — новый файл (119 строк)

## Self-Check: PASSED
