# LinkedIn AI Agent

> Production AI pipeline that auto-generates and publishes LinkedIn posts: collects latest AI/analytics news → generates post via Claude Sonnet → sends Telegram preview for approval → publishes to LinkedIn. Deployed on Railway.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/Claude_Sonnet_4.6-orange?style=flat)
![Railway](https://img.shields.io/badge/Railway-deployed-blueviolet?style=flat&logo=railway)
![Telegram](https://img.shields.io/badge/Telegram_Bot-2CA5E0?style=flat&logo=telegram)

---

## How It Works

```
Scheduler (APScheduler · 3–4x/week · 09:00–11:00 Dubai)
    │
    ▼
NewsCollector
(NewsAPI + RSS fallback · AI/analytics/data science topics)
    │
    ▼
ContentGenerator (Claude Sonnet 4.6)
─ Generates post with hook + body + CTA + hashtags
─ Picks best Unsplash image via metadata matching
    │
    ▼
NotionLogger → status: Draft
    │
    ▼
Telegram Bot → preview sent to owner
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      ✅ Publish   ✏️ Regen    ❌ Skip
                  (with         │
                 feedback)      └→ auto-fetch
                                   next article
          │
          ▼
    LinkedInPublisher (OAuth 2.0 · UGC API)
    NotionLogger → status: Published + URL
```

---

## Features

- **Semi-automated** — every post gets human review via Telegram before publishing
- **Engagement-optimized prompts** — hook, specific CTA (debate/poll/challenge), 6-9 hashtags with career-visibility tags
- **Smart image selection** — fetches 15 Unsplash candidates, Claude picks best match based on photo metadata vs. post content
- **Regeneration loop** — press Regenerate, type feedback, get improved draft instantly
- **Skip → auto-next** — skip a post and the bot immediately fetches a fresh article
- **Schedule + manual** — `/generate` command triggers pipeline outside schedule
- **Notion log** — every post tracked with status, text, image URL, LinkedIn URL, feedback history
- **Token expiry alert** — Telegram warning 5 days before LinkedIn OAuth token expires

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Content generation | Claude Sonnet 4.6 (Anthropic API) |
| News collection | NewsAPI + RSS (feedparser) |
| Image selection | Unsplash API + Claude scoring |
| Scheduling | APScheduler (CronTrigger + 2h jitter) |
| Telegram bot | python-telegram-bot 21.6 (async) |
| LinkedIn posting | OAuth 2.0 · `/v2/ugcPosts` · image upload |
| Content log | Notion API (notion-client) |
| Deployment | Railway (worker process, auto-redeploy) |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/nkrivoshey/linkedin-agent.git
cd linkedin-agent
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all keys (see .env.example for required variables)
```

Required environment variables:
```env
ANTHROPIC_API_KEY=...         # Claude API key
NEWSAPI_KEY=...               # newsapi.org free tier
UNSPLASH_ACCESS_KEY=...       # unsplash.com API
TELEGRAM_BOT_TOKEN=...        # @BotFather
TELEGRAM_CHAT_ID=...          # your chat ID
LINKEDIN_ACCESS_TOKEN=...     # OAuth 2.0 token (60-day expiry)
LINKEDIN_PERSON_URN=...       # urn:li:person:XXXXX
LINKEDIN_TOKEN_ISSUED_AT=...  # YYYY-MM-DD
NOTION_TOKEN=...              # Notion integration token
NOTION_DATABASE_ID=...        # Notion DB UUID
POST_SCHEDULE=MON,WED,FRI     # posting days
POST_TIME_UTC=05:00           # 09:00 Dubai = 05:00 UTC
DRY_RUN=false
```

### 3. Add your profile

Edit `data/profile.md` with your LinkedIn profile summary — used in all generation prompts.

### 4. Run locally

```bash
python main.py
# Use /generate in Telegram to trigger manually
# Use /dryrun to test without publishing
```

---

## Deploy to Railway

1. Push to GitHub
2. Create Railway project → connect repo
3. Set all env vars in Railway Variables
4. Deploy as **worker** (not web service)

---

## Project Structure

```
linkedin-agent/
├── main.py                   # entry point, APScheduler setup, pipeline wiring
├── config.py                 # env var loading + validation
├── modules/
│   ├── news.py               # NewsAPI + RSS news collector
│   ├── generator.py          # Claude content generation + image scoring
│   ├── images.py             # Unsplash candidate fetching
│   ├── telegram_bot.py       # approval bot + regenerate loop
│   ├── linkedin.py           # OAuth 2.0 + UGC post publisher
│   ├── notion.py             # Notion content log
│   └── models.py             # Article, PostRecord dataclasses
├── data/
│   └── profile.md            # your LinkedIn profile for prompts
├── requirements.txt
├── railway.toml
└── .env.example
```

---

*Built by [Nikita Krivoshei](https://www.linkedin.com/in/nikita-krivoshei/) · Data Analyst & Analytics Engineer*
