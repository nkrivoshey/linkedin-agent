---
phase: 01-linkedin-rebuild
plan: "09"
subsystem: orchestration
tags: [main, integration, content-router, context-store, questionnaire, scheduler]
dependency_graph:
  requires:
    - 01-01-config-models
    - 01-02-images
    - 01-03-linkedin
    - 01-05-content-router
    - 01-06-generator
    - 01-07-notion
    - 01-08-telegram-bot
  provides:
    - "build_pipeline() with ContentRouter + ContextStore + questionnaire job"
  affects:
    - "main.py (full rewrite of run_pipeline + build_pipeline)"
tech_stack:
  added: []
  patterns:
    - "Three-tier image selection per post_type (profile_photo > gpt-image-1 > Unsplash)"
    - "Indirection pattern via _refs dict for late binding of callbacks"
    - "Graceful degradation: no context entries -> falls back to news_insight"
key_files:
  created: []
  modified:
    - main.py
decisions:
  - "on_context_entry logs only category, not text (T-09-02 mitigation)"
  - "context_store.get_used_unsplash_ids wired as notion_blacklist_getter to avoid circular imports"
  - "on_new_image reconstructs PostRecord via explicit kwargs (PostRecord is a dataclass)"
  - "Questionnaire scheduler conditional on cfg.questionnaire_schedule being non-empty"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-09"
  tasks_completed: 1
  files_modified: 1
---

# Phase 01 Plan 09: main.py Final Integration Summary

Wire all Wave 1-2 modules (ContentRouter, ContextStore, ImageFetcher v2, questionnaire scheduler) into main.py — smart post-type rotation, personal post path, three-tier image selection, and context entry capture now live in production pipeline.

## What Was Built

### Task 1: Update build_pipeline() with ContentRouter, ContextStore, on_new_image

**New imports added:**
- `from modules.content_router import ContentRouter, needs_fresh_context`
- `from modules.context_store import ContextStore`
- `from modules.images import PERSONAL_POST_TYPES, GPT_IMAGE_TYPES`

**build_pipeline() changes:**
- `context_store = ContextStore(token=cfg.notion_token, context_db_id=cfg.notion_context_db_id)` — initialised before ImageFetcher
- `router = ContentRouter()` — stateless, created once per pipeline
- `ImageFetcher` now receives `notion_blacklist_getter`/`notion_blacklist_setter` from ContextStore (conditional on `context_store.is_available()`)

**run_pipeline() rewrite:**
1. `recent_types = notion.get_recent_post_types(n=30)` — feeds ContentRouter history
2. `entries = context_store.get_unused_entries(limit=10)` — checks personal context availability
3. `post_type = router.choose_post_type(recent_types, has_fresh_context=bool(entries))` — D-04 weighted rotation
4. Three branches:
   - `needs_fresh_context(post_type) and entries` → `generator.generate_personal()` + `mark_entry_used()`
   - `needs_fresh_context(post_type) and not entries` → degradation: post_type = "news_insight", news pipeline
   - default → news pipeline (news_insight)
5. Three-tier image selection per post_type:
   - `PERSONAL_POST_TYPES` → `fetch_profile_photo()` first, gpt-image-1 fallback
   - `GPT_IMAGE_TYPES` → `fetch_gpt_image()` first
   - No image yet → Unsplash candidates via `generator.suggest_image_keywords()`
6. `notion.create_draft(..., post_type=post_type)` — passes post_type for tracking

**New callbacks:**
- `on_new_image(record)` — regenerates image only, updates Notion via `update_status(image_url=...)`, re-sends preview via `bot.send_preview()`
- `on_context_entry(category, text)` — saves to ContextStore, logs only `category` (T-09-02)

**main() changes:**
- `on_new_image_func` and `on_context_entry_func` added as indirection wrappers in `_refs`
- `PostApprovalBot` constructor now receives `on_new_image=on_new_image_func, on_context_entry=on_context_entry_func`
- `build_pipeline()` now returns 7-tuple: `run_pipeline, on_publish, on_skip, on_regenerate, on_custom_post, on_new_image, on_context_entry`
- Questionnaire scheduler job added after post scheduler:
  ```python
  scheduler.add_job(bot.send_questionnaire, CronTrigger(day_of_week=q_days, hour=7, minute=0))
  ```

## Commits

| Hash | Description |
|------|-------------|
| 04d418f | feat(01-09): wire ContentRouter, ContextStore, questionnaire scheduler into main.py |

## Deviations from Plan

None — plan executed exactly as written.

All interfaces matched actual module exports:
- `ContentRouter.choose_post_type(recent_types, has_fresh_context)` — confirmed signature
- `ContextStore.__init__(token, context_db_id)` — confirmed
- `ImageFetcher.__init__(unsplash_key, openai_key, use_gpt_image, notion_blacklist_getter, notion_blacklist_setter)` — confirmed (uses `use_gpt_image`, not `use_dalle`)
- `NotionLogger.create_draft(..., post_type="")` — confirmed optional kwarg
- `PostApprovalBot.__init__(..., on_new_image=None, on_context_entry=None)` — confirmed optional params

## Threat Mitigations Applied

| Threat | Action |
|--------|--------|
| T-09-02: Information Disclosure — context entries in logs | `on_context_entry` logs only `category`, never `text` |
| T-09-03: Tampering — empty context_db_id | `context_store.is_available()` guard on all ContextStore calls |

## Known Stubs

None.

## Self-Check: PASSED

- `main.py` exists and passes `ast.parse()`
- All 9 verification checks from plan passed
- Commit `04d418f` exists in git log
- No unexpected file deletions
