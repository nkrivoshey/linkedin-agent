---
phase: 01-linkedin-rebuild
plan: 6
subsystem: generator
tags: [generator, anthropic, v3-prompt, personal-post, auth-fix]
dependency_graph:
  requires:
    - 01-01-config-models
    - 01-04-context-store-questionnaire
  provides:
    - ContentGenerator.generate_personal(entries, post_type)
    - PERSONAL_POST_PROMPT_V3
    - ANTHROPIC_AUTH_TOKEN fix
  affects:
    - modules/generator.py
tech_stack:
  added: []
  patterns:
    - ANTHROPIC_AUTH_TOKEN env cleanup before SDK init
    - AI fallback theme generation when context entries empty
key_files:
  modified:
    - modules/generator.py
decisions:
  - "Fixed post_style in generate()/regenerate() replaces weighted random PERSONAL_CASES rotation (D-06)"
  - "PERSONAL_POST_PROMPT_V3 uses category-specific tone rules per D-05"
  - "_generate_fallback_theme() uses separate _call_with_retry() call to avoid embedding profile twice"
metrics:
  duration: "5 min"
  completed: "2026-06-08"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 1 Plan 6: Generator V3 Summary

ContentGenerator updated with ANTHROPIC_AUTH_TOKEN fix, V3 personal post prompt with category-specific tone rules, and generate_personal() method that reads Notion context entries.

## What Was Done

### Task 1: ANTHROPIC_AUTH_TOKEN fix + V3 prompt + generate_personal()

**Files modified:** `modules/generator.py`
**Commit:** f60c1d0

Five changes applied in one pass:

1. **ANTHROPIC_AUTH_TOKEN fix (REQ-10):** Added before `anthropic.Anthropic()` init in `__init__()`. Claude Code sets `ANTHROPIC_AUTH_TOKEN=''` in system env; SDK v0.96.0 reads it and creates `Authorization: Bearer ` (empty), which h11 rejects. Fix pops the empty token so SDK falls back to `X-Api-Key` header only.

2. **PERSONAL_CASES removed (REQ-09, D-06):** Deleted constant (6 hardcoded strings) plus `_pick_case()` and `_pick_post_style()` methods. `generate()` and `regenerate()` now use a fixed post_style string. Content type rotation is now ContentRouter's responsibility (01-05).

3. **PERSONAL_POST_PROMPT_V3 added (REQ-08, D-05):** Constant writing AS Nikita (first person). Rules: no em-dashes, no `Here's what I learned:` headers, no bullet lists of lessons, natural sentence length mix, category-specific tone (`work` = technical precision, `opinion` = confident+invites pushback, `learning` = curiosity+practical, `life` = observational), NEVER `#OpenToWork`, 5-7 hashtags mandatory.

4. **generate_personal(entries, post_type) added (REQ-09):** Accepts entries from `ContextStore.get_unused_entries()`. If entries empty, calls `_generate_fallback_theme(post_type)` which asks AI to generate 2-3 sentences of context from profile. Otherwise uses `entries[0]` (category + text). Formats `PERSONAL_POST_PROMPT_V3` and calls `_call_with_retry()`.

5. **Backward compatibility preserved:** `generate(article)`, `regenerate()`, `generate_from_custom()`, `pick_best_image()`, `suggest_image_keywords()` all work unchanged.

## Verification

```
PASS: generator V3 OK
```

All assertions passed:
- `PERSONAL_CASES` not in module
- `PERSONAL_POST_PROMPT_V3` exists, contains `OpenToWork` rule and em-dash rule
- `__init__()` source contains `ANTHROPIC_AUTH_TOKEN`
- `generate_personal` method exists on ContentGenerator
- `_pick_case` and `_pick_post_style` deleted

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. `generate_personal()` is fully wired: real entries path uses entry data, fallback path generates via AI from profile.

## Self-Check: PASSED

- `modules/generator.py` exists and passes import check
- Commit f60c1d0 exists in git log
- SUMMARY.md created at correct path
