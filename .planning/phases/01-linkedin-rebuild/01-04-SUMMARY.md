---
phase: 01-linkedin-rebuild
plan: 4
subsystem: context-store-questionnaire
tags: [notion, context-store, questionnaire, state-machine, telegram]
dependency_graph:
  requires: [01-01-config-models]
  provides: [modules/context_store.py, modules/questionnaire.py]
  affects: [modules/generator.py, modules/telegram_bot.py]
tech_stack:
  added: [notion_client, python-telegram-bot InlineKeyboardMarkup]
  patterns: [graceful-degradation, dataclass-state-machine, try-except-all-external-calls]
key_files:
  created:
    - modules/context_store.py
    - modules/questionnaire.py
  modified: []
decisions:
  - "Unsplash blacklist хранится как специальная страница __unsplash_blacklist__ в том же context_db_id (Category=work как required select)"
  - "category_keyboard() импортирует InlineKeyboardMarkup из telegram напрямую — без прокидывания через bot"
  - "NotionClient создаётся в __init__ только если context_db_id непустой — иначе self.client = None"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-06-08"
  tasks_completed: 2
  files_created: 2
---

# Phase 1 Plan 4: Context Store + Questionnaire State Summary

**One-liner:** ContextStore (Notion CRUD с graceful degradation) и QuestionnaireState (dataclass стейт-машина, перенос из spike 002) готовы для подключения в Wave 3.

## Tasks Completed

| Task | Name | Files | Status |
|------|------|-------|--------|
| 1 | Создать modules/context_store.py | modules/context_store.py | Done |
| 2 | Создать modules/questionnaire.py | modules/questionnaire.py | Done |

## Implementation Details

### Task 1: ContextStore

Файл: `modules/context_store.py`

Публичный интерфейс:
- `__init__(token, context_db_id)` — создаёт Notion client только если context_db_id непустой
- `is_available() -> bool` — возвращает True только если context_db_id и client заданы
- `add_entry(category, text) -> str | None` — создаёт страницу в Notion; text[:2000], title=text[:100]
- `get_unused_entries(limit=10) -> list[dict]` — фильтр Used==False, возвращает [{"id","category","text"}]
- `mark_entry_used(page_id)` — устанавливает Used=True
- `get_used_unsplash_ids() -> set[str]` — читает comma-separated IDs из страницы __unsplash_blacklist__
- `mark_unsplash_used(image_id)` — добавляет ID в blacklist (создаёт страницу если нет)

Все Notion-вызовы в try/except с logger.exception(). При context_db_id=="" все методы возвращают None/[]/set().

### Task 2: QuestionnaireState

Файл: `modules/questionnaire.py`

Перенос из spike 002 (строки 29-85):
- `CATEGORIES` — 4 ключа: work, life, learning, opinion с label/question/callback
- `CALLBACK_TO_CATEGORY` — обратный маппинг callback → ключ категории
- `CALLBACK_DONE = "ctx_done"`, `CALLBACK_ADD_MORE = "ctx_more"`
- `QuestionnaireState` — dataclass, методы: start(), category_selected(), response_received(), finish()

Дополнительно:
- `category_keyboard() -> InlineKeyboardMarkup` — keyboard с кнопками категорий + Done

Нет импортов из telegram_bot.py — независим от BotState.

## Deviations from Plan

None — план выполнен точно.

### Notes on Commits

Bash-инструмент был недоступен в процессе выполнения. Файлы созданы в worktree корректно.
Коммиты `feat(01-04): create ContextStore` и `feat(01-04): create QuestionnaireState` должны быть выполнены вручную или через оркестратор.

Ожидаемые команды коммитов:
```
git add modules/context_store.py
git commit -m "feat(01-04): create ContextStore — Notion CRUD for personal context DB"

git add modules/questionnaire.py
git commit -m "feat(01-04): create QuestionnaireState — port from spike + category_keyboard()"
```

## Threat Model Compliance

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-04-01 | text[:2000] в add_entry() | Implemented |
| T-04-03 | try/except на всех Notion вызовах + graceful degradation | Implemented |

## Known Stubs

None — все методы полностью реализованы.

## Self-Check

- [x] modules/context_store.py создан
- [x] modules/questionnaire.py создан
- [x] ContextStore graceful при context_db_id=""
- [x] QuestionnaireState: start→category_selected→response_received→finish
- [x] Нет импортов из telegram_bot.py
- [ ] Коммиты — Bash недоступен, выполнить вручную

## Self-Check: PARTIAL

Файлы созданы. Git-коммиты заблокированы отсутствием Bash-доступа — требуется ручное выполнение.
