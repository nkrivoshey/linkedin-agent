# Phase 1: LinkedIn Bot "Living Account" Rebuild — Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Source:** Spike sessions 001–004 + user decisions

<domain>
## Phase Boundary

Rebuild existing LinkedIn agent (Railway production) from news-aggregator into living personal account. All changes are in-place — same repo, same Railway deploy. No new infrastructure. No breaking changes to existing Telegram approval flow.

Existing working components to KEEP intact:
- Telegram approval bot flow (send_preview, on_publish, on_skip, on_regenerate)
- LinkedIn UGC publishing API integration
- Notion post database (add fields, don't replace)
- APScheduler with cron trigger
- NewsCollector (NewsAPI + RSS fallback)

</domain>

<decisions>
## Implementation Decisions

### D-01: Image Strategy
- **LOCKED**: gpt-image-1 as primary image source for ALL post types
- Prompt style: person from behind / silhouette / hands only — NO visible faces
- No real photos from data/profile_photos/ in posts (privacy decision)
- Unsplash as fallback when gpt-image-1 fails (API error or key missing)
- Unsplash blacklist: persist used image IDs in Notion (not in-memory set — crashes lose state)
- gpt-image-1 params: `quality="medium"`, `size="1536x1024"`, output=b64_json

### D-02: Image Regeneration UX
- **LOCKED**: Add "🖼️ New Image" button to Telegram approval keyboard
- Button regenerates ONLY the image — post text unchanged
- New image sent as updated photo in existing Telegram preview message
- Does NOT create new Notion draft — updates image_url on existing record

### D-03: Personal Context Source
- **LOCKED**: Hybrid — proactive Telegram questionnaire + AI theme generation
- Bot asks Nikita 2x/week (TUE + FRI morning) via Telegram
- 4 categories per session: work/projects, life/Dubai, learning/books, opinions/hot-takes
- UX: category buttons (InlineKeyboard) → free text response → save → "Another?" loop
- All entries stored in dedicated Notion DB: NOTION_CONTEXT_DB_ID
- Entry schema: Title, Category (select), Text (rich_text), Created (date), Used (checkbox)
- QuestionnaireState is separate from BotState — no conflicts

### D-04: Content Type Rotator
- **LOCKED**: Smart rotator reads last 30 Notion posts, weighted selection
- Types: news_insight (35%), personal_story (25%), hot_take (20%), achievement (10%), learning (10%)
- Hard rule: if last 2 posts are same type → that type weight = 0 (forced rotation)
- If no fresh context entries (Used=False) → lean toward news_insight
- post_type field added to Notion posts DB (select field)

### D-05: Post Generation Tone
- **LOCKED**: V3 "relaxed professional" prompt
- No em-dash overload, no "Here's what I learned:" headers, no bullet lists of lessons
- Mix sentence lengths naturally, writes like smart colleague texting, not LinkedIn influencer
- Category-specific tone: work=technical precision, opinion=confident+invites pushback, learning=curiosity+practical, life=observational+connects to professional
- NEVER use #OpenToWork hashtag (explicit rule in prompt)
- 5-7 hashtags on last line, mix specific + career visibility

### D-06: Personal Post Generation
- **LOCKED**: Generator reads Notion context entries (not hardcoded PERSONAL_CASES)
- Marks entries as Used=True after generating a post from them
- Fallback: if no unused context → AI generates theme from extended profile
- PERSONAL_CASES constant removed from generator.py

### D-07: ANTHROPIC_AUTH_TOKEN Fix
- **LOCKED**: Must pop empty ANTHROPIC_AUTH_TOKEN before Anthropic client init
- Claude Code sets ANTHROPIC_AUTH_TOKEN='' in system env → SDK v0.96.0 creates Bearer header with empty value → h11 rejects
- Fix: `if not os.environ.get("ANTHROPIC_AUTH_TOKEN"): os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)`
- Apply to ContentGenerator.__init__()

### D-08: LinkedIn Binary Upload
- **LOCKED**: Add `_upload_image_bytes(image_bytes: bytes)` method to LinkedInPublisher
- Current: `_upload_image(image_url)` downloads bytes from URL then uploads
- New: accepts bytes directly (for gpt-image-1 base64 output)
- publish() signature: add `image_bytes: bytes | None = None` param
- If image_bytes provided → use `_upload_image_bytes()`; if image_url provided → existing path

### D-09: New Config Variables
- USE_GPT_IMAGE (bool, default "true") — enables gpt-image-1 generation
- NOTION_CONTEXT_DB_ID (str, required when questionnaire is active) — context entries DB
- QUESTIONNAIRE_SCHEDULE (str, default "TUE,FRI") — days for weekly questionnaire

### Claude's Discretion
- Exact Unsplash blacklist key format in Notion (can use rich_text or page property)
- Questionnaire trigger time (use same POST_TIME_UTC offset or hardcode morning local)
- Image scene prompt templates (exact wording for each post type)
- How to handle Notion NOTION_CONTEXT_DB_ID when not set (skip questionnaire gracefully)

</decisions>

<canonical_refs>
## Canonical References

### Spike Findings
- `.planning/spikes/001-gpt-image-1-api/README.md` — gpt-image-1 API params, face edit findings, hybrid strategy decision
- `.planning/spikes/002-proactive-questionnaire/questionnaire_spike.py` — QuestionnaireState, CATEGORIES dict, Telegram flow
- `.planning/spikes/003-personal-post-from-context/spike_test.py` — V3 prompt, ANTHROPIC_AUTH_TOKEN fix
- `.planning/spikes/MANIFEST.md` — All requirements locked

### Existing Production Code (READ before modifying)
- `modules/telegram_bot.py` — BotState, existing callbacks, handler registration
- `modules/images.py` — current ImageFetcher (Unsplash), mark_used(), fetch_candidates()
- `modules/generator.py` — ContentGenerator, existing prompts, PERSONAL_CASES
- `modules/notion.py` — NotionLogger, create_draft(), update_status(), get_published_urls()
- `modules/linkedin.py` — LinkedInPublisher, _upload_image(), publish()
- `modules/models.py` — Article, PostRecord datamodels
- `config.py` — Config dataclass, load_config()
- `main.py` — build_pipeline(), scheduler setup, bot callbacks

</canonical_refs>

<specifics>
## Specific Implementation Notes

### gpt-image-1 No-Face Scene Prompts (by post type)
- news_insight: "data analyst workspace from above, dual monitors showing dashboards and charts, coffee cup, notebook, Dubai skyline through window at dusk, photorealistic"
- personal_story: "person from behind sitting at desk in modern office, contemplative posture, window with city view, soft lighting"
- hot_take: "person's hands typing rapidly on laptop keyboard, dark room with single monitor glow, data visualizations visible on screen"
- achievement: "silhouette of person standing at floor-to-ceiling window overlooking Dubai skyline at night, triumphant stance"
- learning: "open technical book with laptop beside it, handwritten notes visible, coffee cup, clean minimal desk"

### Notion Context DB Schema
Required properties (create manually before deploy):
- Title (title) — first 100 chars of text
- Category (select) — options: work, life, learning, opinion
- Text (rich_text) — full user response
- Created (date)
- Used (checkbox, default false)

### Telegram Questionnaire Questions
- work: "What happened at work this week? New insight, win, or interesting problem you solved?"
- life: "Anything interesting from life or Dubai recently? Observation, experience, thought?"
- learning: "What are you learning or reading right now? Any insight worth sharing?"
- opinion: "Any strong opinion or contrarian view on something in data/tech/real estate?"

</specifics>

<deferred>
## Deferred Ideas

- LinkedIn engagement analytics (likes/comments tracking) — needs separate LinkedIn API polling job
- Multi-language posts (Russian + English) — post-MVP
- Automatic LinkedIn token refresh — post-MVP
- HuggingFace models for local image generation — post-MVP
- Obsidian vault integration — not needed, Telegram questionnaire covers this
- Image style fine-tuning per brand colors — post-MVP

</deferred>

---
*Phase: 01-linkedin-rebuild*
*Context gathered: 2026-06-08 via spike sessions*
