---
phase: 01-linkedin-rebuild
plan: 5
subsystem: content-router
tags: [content-routing, weighted-random, post-types, rotation]
dependency_graph:
  requires:
    - 01-01-config-models
    - 01-04-context-store-questionnaire
  provides:
    - ContentRouter.choose_post_type(recent_types, has_fresh_context) → str
    - needs_fresh_context(post_type) → bool
  affects:
    - main.py (run_pipeline will call router.choose_post_type)
    - modules/notion.py (plan 7 adds get_recent_post_types())
tech_stack:
  added: []
  patterns:
    - weighted random selection via random.choices()
    - forced rotation via weight zeroing
    - no-context fallback via weight boosting
key_files:
  created:
    - modules/content_router.py
  modified: []
decisions:
  - D-04 (Content Type Rotator): locked weights news_insight=35, personal_story=25, hot_take=20, achievement=10, learning=10
  - Forced rotation: last 2 posts same type → weight zeroed, not merely reduced
  - No-context fallback: news_insight += 20 AND all CONTEXT_DEPENDENT_TYPES zeroed (not just boosted)
  - Module is pure logic — no Notion access, caller provides recent_types list
metrics:
  completed_date: "2026-06-08T21:56:44Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 1 Plan 5: Content Router Summary

**One-liner:** Weighted random post type selector with forced rotation (D-04) — news_insight=35%, personal_story=25%, hot_take=20%, achievement+learning=10% each, zeroes repeated types and boosts news when context is empty.

## What Was Built

`modules/content_router.py` — pure logic module, no external I/O.

### Public interface

```python
POST_TYPES: list[str]       # 5 valid types, priority order
BASE_WEIGHTS: dict[str,int] # sums to 100
CONTEXT_DEPENDENT_TYPES: frozenset[str]  # types requiring personal context

def needs_fresh_context(post_type: str) -> bool: ...

class ContentRouter:
    def choose_post_type(
        self,
        recent_types: list[str],   # newest first, from notion.get_recent_post_types()
        has_fresh_context: bool = True,
    ) -> str: ...
```

### Rotation logic

| Rule | Trigger | Effect |
|------|---------|--------|
| Forced rotation | `recent_types[0] == recent_types[1]` | `weights[repeated_type] = 0` |
| No-context fallback | `has_fresh_context=False` | `news_insight += 20`, all CONTEXT_DEPENDENT_TYPES zeroed |
| Failsafe | eligible pool empty | returns `"news_insight"` unconditionally |

## Verification Results

All checks passed:
- `choose_post_type(['news_insight','news_insight'])` never returns `news_insight` (50 runs)
- `choose_post_type([], has_fresh_context=False)` always returns `news_insight` (30 runs)
- `choose_post_type(['hot_take','hot_take'])` never returns `hot_take` (20 runs)
- `needs_fresh_context('personal_story') == True`
- `needs_fresh_context('news_insight') == False`
- `sum(BASE_WEIGHTS.values()) == 100`
- All returned values are members of `POST_TYPES`

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: Create content_router.py | bbf21a2 | feat(01-05): create ContentRouter with weighted post type rotation |

## Deviations from Plan

None — plan executed exactly as written.

The task summary in the prompt referenced `get_recent_post_types()` inside `ContentRouter`, but the PLAN.md itself clarifies this was moved to `notion.py` (plan 7). The module was correctly built as pure logic without Notion access, matching the locked interface in the plan.

## Known Stubs

None.

## Threat Flags

None. The module only compares strings from `recent_types` against known constants — no untrusted data is executed or interpolated. Invalid/unknown types in `recent_types` receive weight 0 via `weights.get(t, 0)` (T-05-01 mitigated as planned).

## Self-Check: PASSED

- `modules/content_router.py` — FOUND
- Commit `bbf21a2` — verified via git log
