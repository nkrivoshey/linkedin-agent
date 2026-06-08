---
phase: 01-linkedin-rebuild
plan: 2
subsystem: images
tags: [images, gpt-image-1, unsplash, profile-photos, fallback]
dependency_graph:
  requires: []
  provides: [ImageFetcher, SCENE_PROMPTS, PERSONAL_POST_TYPES, GPT_IMAGE_TYPES]
  affects: [main.py, modules/linkedin.py]
tech_stack:
  added: []
  patterns: [three-tier-fallback, dependency-injection-callbacks, lazy-import]
key_files:
  created: []
  modified:
    - modules/images.py
decisions:
  - "gpt-image-1 используется только для news_insight и learning (impersonal scenes)"
  - "Notion blacklist инжектируется через callbacks — no circular import"
  - "profile photos для personal_story/achievement/hot_take — реальные фото из data/profile_photos/"
  - "FALLBACK_IMAGE_URL как Tier 3 — hardcoded Unsplash URL для data dashboard сцены"
  - "openai импортируется lazy (внутри метода) — не ломает тесты без openai установленного"
metrics:
  duration: "~15min"
  completed: "2026-06-08"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 1 Plan 2: ImageFetcher 3-tier Strategy Summary

**One-liner:** Rewrote ImageFetcher with gpt-image-1 scene generation (bytes), real photo rotation, Unsplash+Notion-callback blacklist, and hardcoded fallback URL.

## What Was Built

Complete rewrite of `modules/images.py` implementing a three-tier image strategy:

**Tier 1a — gpt-image-1 (`fetch_gpt_image`):**
- Calls `openai.OpenAI.images.generate(model="gpt-image-1", quality="medium", size="1536x1024", response_format="b64_json")`
- Returns PNG bytes via `base64.b64decode(response.data[0].b64_json)`
- Per-type scene prompts in `SCENE_PROMPTS` dict — all enforce no visible faces (D-01)
- Graceful degradation: any exception → `logger.exception` + return `None`

**Tier 1b — Real photo rotation (`fetch_profile_photo`):**
- Rotates files from `data/profile_photos/` for `PERSONAL_POST_TYPES`
- Path traversal mitigated via `Path.glob` with fixed extension list (T-02-03)
- Returns `None` safely if directory missing or empty

**Tier 2 — Unsplash with Notion-persisted blacklist (`fetch_candidates`):**
- Notion integration injected via `notion_blacklist_getter` / `notion_blacklist_setter` callbacks
- In-memory `_used_ids` set as fallback when callbacks not wired
- Preserves full backward-compatible `fetch()` and `mark_used()` interface

**Tier 3 — Hardcoded fallback URL (`FALLBACK_IMAGE_URL`):**
- Professional data-dashboard Unsplash image
- Used when Unsplash API unavailable

## New Public Interface

```python
SCENE_PROMPTS: dict[str, str]          # 5 post types, no-face prompts
PERSONAL_POST_TYPES: frozenset[str]    # personal_story, achievement, hot_take
GPT_IMAGE_TYPES: frozenset[str]        # news_insight, learning
FALLBACK_IMAGE_URL: str                # Tier-3 fallback

class ImageFetcher:
    def __init__(self, unsplash_key, openai_key="", use_gpt_image=True,
                 notion_blacklist_getter=None, notion_blacklist_setter=None)
    def fetch_gpt_image(post_type, post_text) -> bytes | None
    def fetch_profile_photo(post_type) -> str | None
    def fetch_candidates(keywords) -> list[dict]
    def mark_used(image_url, candidates) -> None
    def get_unsplash_blacklist() -> set[str]
    def mark_unsplash_used_notion(image_id) -> None
    def fetch(keywords) -> str          # backward compat
```

## Deviations from Plan

None — plan executed exactly as written.

The task_summary in the prompt described a simplified interface (different from the PLAN.md spec). Implemented the full PLAN.md spec which includes profile photo rotation (Tier 1b) per locked decision D-01 in CONTEXT.md.

## Threat Surface Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-02-02: gpt-image-1 timeout (20-41s) | try/except returns None, pipeline degrades to Unsplash |
| T-02-03: profile_photos path traversal | Path.glob("*.jpg") etc. — only files from fixed PROFILE_PHOTOS_DIR |

No new threat surface introduced beyond the plan's threat model.

## Self-Check

- [x] `modules/images.py` written with all required classes and constants
- [x] No `use_dalle` or `_fetch_dalle` references in new code
- [x] `SCENE_PROMPTS` contains all 5 post types
- [x] `PERSONAL_POST_TYPES` = frozenset({"personal_story", "achievement", "hot_take"})
- [x] `GPT_IMAGE_TYPES` = frozenset({"news_insight", "learning"})
- [x] `fetch_gpt_image("news_insight", "")` returns None when openai_key="" (early return on line 129)
- [x] `fetch_profile_photo("news_insight")` returns None (not in PERSONAL_POST_TYPES, line 165)
- [x] `fetch_candidates([])` safe — returns [] if Unsplash unavailable
- [x] `mark_used(url, [])` safe — empty loop, no exception
