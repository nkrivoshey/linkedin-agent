---
phase: 01-linkedin-rebuild
plan: 3
subsystem: linkedin
tags: [linkedin, image-upload, binary, gpt-image-1, backwards-compatible]
dependency_graph:
  requires: []
  provides:
    - LinkedInPublisher._upload_image_bytes(bytes) -> str | None
    - LinkedInPublisher.publish(image_bytes=bytes) path
  affects:
    - modules/linkedin.py
tech_stack:
  added: []
  patterns:
    - Direct binary PUT upload to LinkedIn media API (skip URL download)
    - Dual-path image upload with priority ordering (bytes > url > none)
key_files:
  created: []
  modified:
    - modules/linkedin.py
decisions:
  - publish() image routing: bytes priority over url (if image_bytes is not None -> _upload_image_bytes; elif image_url -> _upload_image; else None)
  - _upload_image_bytes() wrapped in try/except to return None on any failure (matches threat T-03-02)
  - logging.getLogger(__name__) added for structured error reporting
metrics:
  duration: "~5m"
  completed: "2026-06-08T21:35:23Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 01 Plan 03: LinkedIn Binary Image Upload Summary

## One-liner

Added `_upload_image_bytes(bytes)` to LinkedInPublisher and updated `publish()` with dual-path image routing — bytes priority for gpt-image-1 output, URL fallback for legacy callers.

## What Was Built

- **`_upload_image_bytes(self, image_bytes: bytes) -> str | None`** — new method that registers an upload slot with LinkedIn `/assets?action=registerUpload` (same payload as `_upload_image`) and then PUTs the raw bytes directly, bypassing the `requests.get(url)` download step. Wrapped in `try/except Exception` with `logger.exception` to return `None` on any failure.

- **Updated `publish()` signature** — `publish(self, text: str, image_url: str = "", image_bytes: bytes | None = None) -> str` — priority routing: `image_bytes` -> `_upload_image_bytes`; `image_url` -> `_upload_image` (unchanged); neither -> `image_urn = None`.

- **`logging` import and `logger = logging.getLogger(__name__)`** added at module level.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _upload_image_bytes() and update publish() | 5aee8f9 | modules/linkedin.py |

## Deviations from Plan

None — plan executed exactly as written.

## Verification

All assertions from plan verification script passed:
- `image_bytes` param present with `default=None`
- `image_url` param present with `default=""`
- `_upload_image_bytes` attribute exists on class
- `registerUpload` and `image_bytes` present in method source

## Known Stubs

None.

## Threat Flags

None — no new network endpoints or trust boundaries introduced beyond those in plan threat model.

## Self-Check

- [x] modules/linkedin.py modified with all required changes
- [x] Commit 5aee8f9 exists
- [x] Backwards compatible: `publish(text="t", image_url="http://...")` still works
- [x] No file deletions in commit

## Self-Check: PASSED
