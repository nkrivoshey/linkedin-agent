# LinkedIn Agent — Living Account Rebuild

## Project Goal

Transform the LinkedIn automation bot from a news-aggregator into a **living personal account** that posts as Nikita Krivoshei — a real data analyst in Dubai. Posts should feel authentic: mix of news insights, personal thoughts, career wins, hot takes.

## Phase 1: LinkedIn Bot "Living Account" Rebuild

**Goal:** Rebuild the bot with personal context engine, smart content rotation, unique images, and proactive Telegram questionnaire.

**Status:** Pending

**Plans:** 10 plans

Plans:
- [ ] 01-PLAN-1-config-models.md — Config new vars + PostRecord.post_type field
- [ ] 01-PLAN-2-images.md — ImageFetcher rewrite: gpt-image-1, profile photos, Unsplash+Notion blacklist
- [ ] 01-PLAN-3-linkedin.md — _upload_image_bytes() + publish() signature update
- [ ] 01-PLAN-4-context-store-questionnaire.md — NEW: ContextStore + QuestionnaireState modules
- [ ] 01-PLAN-5-content-router.md — NEW: ContentRouter with weighted rotation logic
- [ ] 01-PLAN-6-generator.md — V3 prompt, generate_personal(), ANTHROPIC_AUTH_TOKEN fix
- [ ] 01-PLAN-7-notion.md — post_type tracking + get_recent_post_types() + image_url update
- [ ] 01-PLAN-8-telegram-bot.md — New Image button + QuestionnaireState integration
- [ ] 01-PLAN-9-main.md — Full pipeline integration with ContentRouter + questionnaire scheduler
- [ ] 01-PLAN-10-env-smoke-test.md — .env.example update + smoke test + human checkpoint

**Delivers:**
- `modules/images.py` — gpt-image-1 (no-face scenes), Unsplash fallback with Notion-persisted blacklist
- `modules/questionnaire.py` — Proactive Telegram 2x/week context collector (4 categories)
- `modules/context_store.py` — Notion context DB read/write
- `modules/content_router.py` — Smart post type rotator based on Notion history
- `modules/generator.py` — Relaxed professional V3 prompt, generate_personal(), ANTHROPIC_AUTH_TOKEN fix
- `modules/notion.py` — Post type tracking, used_image_ids persistence
- `modules/linkedin.py` — `_upload_image_bytes()` for gpt-image-1 base64 output
- `modules/telegram_bot.py` — "🖼️ New Image" callback button, QuestionnaireState integration
- `config.py` — USE_GPT_IMAGE, NOTION_CONTEXT_DB_ID, QUESTIONNAIRE_SCHEDULE new vars
- `main.py` — Questionnaire scheduled job, pipeline updated with content router
- `.env.example` — Updated with new vars

**Requirements:**
- REQ-01: Images never repeat (persistent blacklist in Notion, not in-memory)
- REQ-02: gpt-image-1 generates no-face scenes (person from behind/silhouette) for all post types
- REQ-03: "🖼️ New Image" Telegram button regenerates only image without touching post text
- REQ-04: Proactive questionnaire 2x/week (TUE+FRI) with 4 categories: work, life, learning, opinion
- REQ-05: Context entries stored in dedicated Notion DB (NOTION_CONTEXT_DB_ID)
- REQ-06: Smart rotator reads last 30 Notion posts, prevents 2+ same types in a row
- REQ-07: post_type field tracked in Notion for every post
- REQ-08: V3 "relaxed professional" prompt replaces V1/V2 ghostwriter prompts
- REQ-09: Personal posts generated from Notion context entries (not hardcoded PERSONAL_CASES)
- REQ-10: ANTHROPIC_AUTH_TOKEN workaround applied (pop empty token before client init)
- REQ-11: LinkedIn publisher handles image bytes directly (no URL download for gpt-image-1)
- REQ-12: Unsplash fallback with Notion-persisted image ID blacklist (not in-memory set)
