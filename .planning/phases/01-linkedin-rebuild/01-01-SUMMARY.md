---
phase: 01-linkedin-rebuild
plan: 1
subsystem: config-models
tags: [config, models, dataclass, foundation]
dependency_graph:
  requires: []
  provides: [Config.use_gpt_image, Config.notion_context_db_id, Config.questionnaire_schedule, PostRecord.post_type]
  affects: [main.py, modules/notion.py, modules/image_fetcher.py, modules/content_router.py]
tech_stack:
  added: []
  patterns: [dataclass, os.getenv with defaults]
key_files:
  created: []
  modified:
    - config.py
    - modules/models.py
decisions:
  - "use_gpt_image default=true: gpt-image-1 is the primary image source in new architecture"
  - "notion_context_db_id via os.getenv (not _require): field is optional, questionnaire can be disabled"
  - "questionnaire_schedule default=TUE,FRI: twice-weekly collection cadence"
  - "post_type default='': empty string ensures backward compat with existing PostRecord constructors"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 01 Plan 01: Config + Models Foundation Summary

Config dataclass updated with 3 new fields (use_gpt_image, notion_context_db_id, questionnaire_schedule), 3 deferred fields removed, and PostRecord extended with post_type for tracking post categories in Notion.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add new fields to Config dataclass | 438af7c | config.py |
| 2 | Add post_type to PostRecord | b7c386e | modules/models.py |

## What Was Built

### config.py
- Added `use_gpt_image: bool` — enables gpt-image-1 as primary image source; loaded from `USE_GPT_IMAGE` env var, default `"true"`
- Added `notion_context_db_id: str` — Notion DB ID for questionnaire context storage; loaded from `NOTION_CONTEXT_DB_ID`, optional (default `""`)
- Added `questionnaire_schedule: str` — weekdays for questionnaire collection; loaded from `QUESTIONNAIRE_SCHEDULE`, default `"TUE,FRI"`
- Removed `use_dalle: bool` — superseded by use_gpt_image (deferred)
- Removed `huggingface_api_key: str` — not used in new architecture (deferred)
- Removed `obsidian_vault_path: str` — not used in new architecture (deferred)
- Kept `openai_api_key: str` — required for gpt-image-1 API calls

### modules/models.py
- Added `post_type: str = ""` to PostRecord after publish_date field
- Supported values: `news_insight`, `personal_story`, `hot_take`, `achievement`, `learning`
- Default `""` ensures full backward compatibility

## Verification

```
PASS: config + models foundation OK
```

All acceptance criteria met:
- Config contains use_gpt_image, notion_context_db_id, questionnaire_schedule
- Config does not contain use_dalle, huggingface_api_key, obsidian_vault_path
- PostRecord.post_type defaults to ""
- All imports work without errors

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. Both new Config fields (notion_context_db_id) are read from env vars as strings per the existing pattern, consistent with T-01-01 in plan's threat model (accept disposition).

## Self-Check: PASSED

- config.py modified: FOUND
- modules/models.py modified: FOUND
- Commit 438af7c: FOUND (feat(01-01): add use_gpt_image...)
- Commit b7c386e: FOUND (feat(01-01): add post_type...)
