---
spike: 001
name: gpt-image-1-api
type: standard
validates: "Given a post text+topic, when calling gpt-image-1 API, then produces LinkedIn-quality image as bytes, integratable with LinkedIn binary upload"
verdict: VALIDATED
related: []
tags: [images, openai, linkedin]
---

# Spike 001: gpt-image-1-api

## What This Validates
Given a LinkedIn post text and topic, when calling OpenAI gpt-image-1 API, then produces a professional image as PNG bytes, directly uploadable to LinkedIn binary upload endpoint.

## Research

### API Differences vs DALL-E 3

| Parameter | DALL-E 3 | gpt-image-1 |
|-----------|----------|-------------|
| quality   | standard, hd | low, medium, high, auto |
| output    | URL (expires) | base64 (b64_json) |
| size landscape | 1792x1024 | 1536x1024 |
| edit API  | masks required | maskless edit supported |
| face consistency | poor | poor (not face-swap model) |

### Chosen approach: Hybrid image strategy

**Problem discovered:** `images.edit` does NOT reliably preserve facial identity. Clothing/style may match, but the face is noticeably different from reference photo. This is a fundamental limitation of diffusion-based edit models — they are not face-swap/face-embedding models.

**Solution (validated by spike):**
- **Personal posts** (personal_story, achievement, hot_take) → rotate real photos from `data/profile_photos/`. Real photos outperform AI-generated faces on LinkedIn engagement.
- **Impersonal posts** (news_insight, learning) → gpt-image-1 scene WITHOUT people (data visualizations, Dubai skyline, abstract tech, office environments).

## How to Run
```bash
cd /Users/nikitakrivoshey/projects/linkedin-agent
python .planning/spikes/001-gpt-image-1-api/spike_test.py          # basic generation
python .planning/spikes/001-gpt-image-1-api/spike_001b_face_edit.py  # face edit (inconclusive)
```

## Investigation Trail

1. **First run:** `quality="standard"` → 400 error. Fixed to `quality="medium"`.
2. **Basic generation:** 3/3 prompts passed. PNG format, ~2MB, ~25s generation time, binary-upload-ready.
3. **Face edit (001b):** `images.edit` with 3 reference photos — API succeeds, but face not recognizable as reference person. Clothing/accessories may match but face identity is lost.
4. **Decision:** Pivot to hybrid strategy — real photos for personal posts, AI scenes for news posts.

## Results

**Verdict: VALIDATED ✓**

### Technical findings:
- `quality` param: `low | medium | high | auto` (not `standard`)
- Output: `b64_json` (base64 PNG, ~2MB), NOT a URL
- Generation time: 20–41 seconds per image
- LinkedIn upload: bytes are drop-in compatible with existing `_upload_image` method (just skip the `requests.get` step)
- `images.edit` works but does NOT preserve facial identity

### Architecture requirements locked:
- `USE_GPT_IMAGE=true` → use gpt-image-1 for impersonal post types
- `USE_GPT_IMAGE=false` → fallback to Unsplash with Notion-persisted blacklist
- Real photos stored in `data/profile_photos/` (gitignored), rotated for personal post types
- LinkedIn `_upload_image` → add `_upload_image_bytes(bytes)` method to skip URL download
