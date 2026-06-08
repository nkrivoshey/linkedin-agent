# Spike Manifest

## Idea

Rebuild LinkedIn agent from news-aggregator bot into a **living personal account** that posts as Nikita Krivoshei. The bot should feel like a real person: mix of news insights, personal thoughts, career reflections, and weekly wins. Key problems in current system: same images repeat on Railway restart (in-memory blacklist), DALL-E replaced by gpt-image-1 (not integrated), no personal context source, no content type rotation.

## Requirements

- Image strategy: HYBRID
  - personal_story / achievement / hot_take → real Nikita photos from data/profile_photos/ (rotated)
  - news_insight / learning → gpt-image-1 (no people — scenes, data viz, Dubai, abstract tech)
  - Unsplash fallback if gpt-image-1 fails, with Notion-persisted blacklist (not in-memory)
- gpt-image-1 params: quality="medium", size="1536x1024", output=b64_json
- LinkedIn publisher: add _upload_image_bytes(bytes) method (skip URL download step)
- Proactive Telegram questionnaire 2x/week (Tue + Fri): 4 categories — work/projects, life/Dubai, learning/books, opinions/hot-takes
- Context stored in dedicated Notion database, consumed by generator
- Smart content rotator: reads last 30 Notion posts by type, avoids clustering
- Post type tracked in Notion for every post
- Separate Notion DB: NOTION_CONTEXT_DB_ID for personal context entries
- data/profile_photos/ gitignored, min 2-3 photos required

## Content Types (rotator)

| Type | Weight | Source |
|------|--------|--------|
| `news_insight` | 35% | NewsAPI / RSS → Claude |
| `personal_story` | 25% | Notion context DB → Claude |
| `hot_take` | 20% | Notion context DB (opinion category) → Claude |
| `achievement` | 10% | Notion context DB (work category, wins) → Claude |
| `learning` | 10% | Notion context DB (learning category) → Claude |

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | gpt-image-1-api | standard | Given a post text+topic, when calling gpt-image-1 API, then produces LinkedIn-quality image as bytes, integratable with LinkedIn binary upload | VALIDATED ✓ | images, openai, linkedin |
| 002 | proactive-questionnaire | standard | Given APScheduler + Telegram bot, when bot sends categorized questions 2x/week and user responds, then context stored in Notion context DB | VALIDATED ✓ | telegram, notion, context |
| 003 | personal-post-from-context | standard | Given Notion context entries (raw user input), when Claude generates personal post, then output sounds like Nikita (not generic LinkedIn fluff) | VALIDATED ✓ | generation, prompts, voice |
| 004 | smart-content-rotator | standard | Given Notion post history with type field, when rotator analyses last 30 posts, then next type balances distribution without 2+ same types in a row | VALIDATED ✓ | rotator, notion, analytics |
