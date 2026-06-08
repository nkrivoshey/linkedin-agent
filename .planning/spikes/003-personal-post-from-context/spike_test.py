"""
Spike 003: Personal post generation from user context entries.
Validates: Claude generates Nikita-voice posts from raw context entries
(not generic LinkedIn fluff). Tests all 4 context categories.

Run: cd /Users/nikitakrivoshey/projects/linkedin-agent
     python .planning/spikes/003-personal-post-from-context/spike_test.py
"""
import os
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_env = dotenv_values(PROJECT_ROOT / ".env")

# dotenv_values reads raw — not affected by system env overrides in Claude Code
ANTHROPIC_API_KEY = _env.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set")
    sys.exit(1)

# Claude Code sets ANTHROPIC_AUTH_TOKEN='' in system env.
# SDK v0.96.0 reads it and creates "Authorization: Bearer " (empty) → h11 rejects.
# Fix: remove the empty token so SDK falls back to X-Api-Key header only.
if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(1)

PROFILE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "profile.md"
profile_text = PROFILE_PATH.read_text(encoding="utf-8")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Simulated context entries (as if user answered questionnaire) ──────────────

CONTEXT_ENTRIES = [
    {
        "category": "work",
        "text": "This week I finished building a deal termination analytics module for MPP. "
                "Found that 19% of 'empty' comment fields were actually whitespace-only strings — "
                "not NULL. Downstream GROUP BY was silently breaking. Fixed with NULLIF(btrim()). "
                "Also caught a timezone bug: Bitrix stores dates in UTC+4 but DWH syncs in UTC, "
                "creating fake 'future' dates. Classic ETL trap.",
    },
    {
        "category": "opinion",
        "text": "Most BI tools are absurdly overengineered. "
                "A well-structured SQL view with sensible naming beats a $50k Tableau license "
                "90% of the time. The real problem isn't the tool — it's that nobody agreed on "
                "what 'conversion rate' actually means before building the dashboard.",
    },
    {
        "category": "learning",
        "text": "Been going deep on Claude API — specifically prompt caching and the new "
                "tool use patterns. Realised that most people use LLMs like a search engine "
                "when they should be using them like a junior analyst: give context, ask for "
                "structured output, validate the result. Night and day difference in reliability.",
    },
    {
        "category": "life",
        "text": "Spent Saturday morning at a coffee shop in Downtown Dubai working on a side project. "
                "Noticed every table had someone with a laptop. Dubai has this weird energy — "
                "people hustle here on weekends like it's a normal Monday. "
                "Starting to understand why the city attracts ambitious people.",
    },
]

# ── Prompts to compare ─────────────────────────────────────────────────────────

PERSONAL_POST_PROMPT_V1 = """You are a LinkedIn ghostwriter for the following professional:

{profile}

---

The author shared this raw context from their life/work this week:

Category: {category}
Raw text: {raw_text}

Transform it into a polished LinkedIn post in English that:
- Keeps the author's authentic voice and the core message
- Has a strong hook (first 1-2 lines people see before "see more")
- Is structured: hook → story/insight → takeaway → CTA question
- Feels personal and genuine, not corporate
- Ends with 5-7 relevant hashtags on the last line

Write the post only — no meta-commentary. Hashtags are MANDATORY."""

PERSONAL_POST_PROMPT_V2 = """You are writing a LinkedIn post AS Nikita Krivoshei (first person).

{profile}

---

Raw context Nikita shared this week ({category}):
"{raw_text}"

LinkedIn post rules:
- Hook: 1-2 punchy lines that stop the scroll. NEVER start with "I". Use a bold claim, number, or question.
- Body: 3-4 short paragraphs. Stay close to the raw text — don't invent facts. Be specific.
- Voice: direct, slightly blunt, data-driven. Like a senior analyst who's seen things.
- CTA: end with ONE specific question or challenge. Not "What do you think?" — something shareable.
- Hashtags: 5-7 on last line. Mix specific + career visibility tags.

Category-specific tone:
- work → technical precision, real numbers, honest about the mess
- opinion → confident, willing to be wrong, invites pushback
- learning → curiosity + practical application, "here's what changed my approach"
- life → observational, connects personal to professional, not braggy

Write ONLY the post. No meta-commentary."""


def generate_post(prompt_template: str, entry: dict, label: str) -> str:
    prompt = prompt_template.format(
        profile=profile_text,
        category=entry["category"],
        raw_text=entry["text"],
    )
    start = time.time()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start
    result = msg.content[0].text
    print(f"  [{label}] {elapsed:.1f}s, {len(result)} chars")
    return result


def score_post(post: str, category: str) -> dict:
    """Heuristic scoring — checks for common LinkedIn quality signals."""
    lines = post.strip().split("\n")
    first_line = lines[0] if lines else ""

    scores = {
        "no_i_start": not first_line.strip().startswith("I "),
        "has_hook": len(first_line) > 20 and len(first_line) < 200,
        "has_hashtags": "#" in post,
        "has_numbers": any(c.isdigit() for c in post),
        "not_generic": not any(p in post.lower() for p in [
            "in today's fast-paced", "in the world of", "it's no secret",
            "as we navigate", "leveraging synergies",
        ]),
        "reasonable_length": 300 < len(post) < 1500,
        "has_question": "?" in post,
    }
    score = sum(scores.values())
    return {"total": score, "max": len(scores), "details": scores}


print("=" * 60)
print("SPIKE 003: Personal Post From Context — Prompt Comparison")
print("=" * 60)

results = []

for entry in CONTEXT_ENTRIES:
    print(f"\n{'─' * 60}")
    print(f"CATEGORY: {entry['category'].upper()}")
    print(f"RAW: {entry['text'][:80]}...")
    print()

    post_v1 = generate_post(PERSONAL_POST_PROMPT_V1, entry, "V1-ghostwriter")
    post_v2 = generate_post(PERSONAL_POST_PROMPT_V2, entry, "V2-as-nikita")

    score_v1 = score_post(post_v1, entry["category"])
    score_v2 = score_post(post_v2, entry["category"])

    print(f"\n  V1 score: {score_v1['total']}/{score_v1['max']} | V2 score: {score_v2['total']}/{score_v2['max']}")
    winner = "V2" if score_v2["total"] >= score_v1["total"] else "V1"
    print(f"  → Heuristic winner: {winner}")

    results.append({
        "category": entry["category"],
        "v1": post_v1, "v2": post_v2,
        "score_v1": score_v1, "score_v2": score_v2,
        "winner": winner,
    })

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
for r in results:
    print(f"\n[{r['category'].upper()}] V1={r['score_v1']['total']}/{r['score_v1']['max']} | V2={r['score_v2']['total']}/{r['score_v2']['max']} → {r['winner']}")

# Save full posts for review
OUTPUT = Path(__file__).parent / "generated_posts.md"
with open(OUTPUT, "w", encoding="utf-8") as f:
    for r in results:
        f.write(f"# {r['category'].upper()}\n\n")
        f.write(f"## V1 (ghostwriter prompt) — score {r['score_v1']['total']}/{r['score_v1']['max']}\n\n")
        f.write(r["v1"] + "\n\n")
        f.write(f"## V2 (as-Nikita prompt) — score {r['score_v2']['total']}/{r['score_v2']['max']}\n\n")
        f.write(r["v2"] + "\n\n")
        f.write("---\n\n")

print(f"\nFull posts saved to: {OUTPUT}")
print("→ Read generated_posts.md to compare quality side-by-side")
