import random
import time
import anthropic
from modules.models import Article

# Real cases from Nikita's experience — rotated across posts
PERSONAL_CASES = [
    "At Metropolitan Premium Properties (Dubai's largest premium real estate brokerage), I built the full analytics stack from scratch — DWH architecture, CRM integration, Power BI dashboards — that drove a 10% revenue uplift.",
    "At Metropolitan Premium Properties, my analytics automation cut reporting turnaround 5× and boosted team productivity by 90%. The key was replacing manual Excel exports with a live CRM-connected pipeline.",
    "At Metropolitan, I own end-to-end data: from raw CRM events to executive dashboards C-suite actually uses for decisions. The hardest part wasn't the SQL — it was figuring out which metric actually drives broker performance.",
    "At Sberbank (70M+ customers, Russia's largest bank), I built NLP pipelines that detected 1.5M+ compliance violations across millions of documents — what used to take weeks, now runs overnight.",
    "At Sberbank, my ML model flagged 300K+ bankruptcy breaches in near-real-time. The lesson: a simple threshold model with good features beats a complex model with bad data every time.",
    "Working in Dubai real estate taught me that the right KPI framing matters more than the dashboard. Brokers need to see 'deals at risk' — not 'conversion rate'. Language shapes behavior.",
]

BASE_PROMPT = """You are writing a LinkedIn post for the following professional:

{profile}

---

Write a LinkedIn post in English based on this news article or topic:

Title: {title}
Source: {source}
Summary: {summary}
URL: {url}

Post style: {post_style}

Format requirements:
- Hook: 1-2 lines that STOP the scroll — use a counterintuitive stat, bold claim, or "hot take". Never start with "I" or generic opener.
- Body: 3-4 short paragraphs, 150-200 words total. Be specific — use numbers, examples, frameworks.
- Links: include the source URL ({url}) naturally in the text.
- CTA (MANDATORY engagement trigger): end the body with ONE of these — a specific debate question ("Agree or disagree: [bold statement]?"), a poll ("A or B: which matters more?"), or a personal challenge ("Has your team made this mistake? Drop a 🔥 if yes"). Never use generic "What do you think?"
- ALWAYS end the post with a blank line followed by 6-9 hashtags on the last line

Hashtag rules (MANDATORY):
- 2-3 topic-specific tags matching the article
- 3-4 career visibility tags from: #DataAnalyst #Analytics #SQL #Python #PowerBI #BusinessIntelligence #DataScience #DataEngineering #AnalyticsEngineering
- 1-2 broad reach tags: #DataDriven #AI #TechLeadership
- NEVER use #OpenToWork or #HiringNow

Tone: professional but direct, opinionated, data-driven. One strong opinion per post. No buzzwords, no fluff.
Write the post only — no meta-commentary, no "Here is your post:".
Hashtags are MANDATORY — never omit them."""

CUSTOM_PROMPT = """You are a LinkedIn ghostwriter for the following professional:

{profile}

---

The author wrote this raw text about something they want to share:

{raw_text}

Transform it into a polished LinkedIn post in English that:
- Keeps the author's authentic voice and the core message
- Has a strong hook (first 1-2 lines people see before "see more")
- Is structured: hook → story/insight → takeaway → CTA question
- Feels personal and genuine, not corporate
- Ends with 5-7 relevant hashtags on the last line

Write the post only — no meta-commentary. Hashtags are MANDATORY."""

REGEN_PROMPT = BASE_PROMPT + """

---

PREVIOUS DRAFT (improve it, don't repeat):
{previous_draft}

USER FEEDBACK (apply this):
{feedback}"""


class ContentGenerator:
    def __init__(self, api_key: str, profile_text: str, max_retries: int = 3):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.profile_text = profile_text
        self.max_retries = max_retries
        self._last_case_idx: int = -1

    def _pick_case(self) -> str:
        available = [i for i in range(len(PERSONAL_CASES)) if i != self._last_case_idx]
        idx = random.choice(available)
        self._last_case_idx = idx
        return PERSONAL_CASES[idx]

    def _pick_post_style(self) -> str:
        styles = [
            ("pure_insight", 30),
            ("with_case", 30),
            ("personal_story", 15),
            ("personal_project", 15),
            ("health_productivity", 10),
        ]
        names, weights = zip(*styles)
        chosen = random.choices(names, weights=weights, k=1)[0]

        if chosen == "pure_insight":
            return (
                "Pure insight post — share the key takeaway from the article. "
                "Focus on what this means for data professionals. Include a bold opinion or contrarian take."
            )
        elif chosen == "with_case":
            case = self._pick_case()
            return (
                f"Insight post with a personal reference. Naturally weave in this real experience "
                f"(1-2 sentences max): '{case}'. Then expand on the broader lesson from the article."
            )
        elif chosen == "personal_story":
            case = self._pick_case()
            return (
                f"Personal story post — open with this real experience: '{case}'. "
                f"Connect it to the article topic. Make it feel like a lesson learned, not a brag."
            )
        elif chosen == "personal_project":
            case = self._pick_case()
            return (
                f"Portfolio showcase post — use the article as a springboard to deep-dive on this "
                f"real project: '{case}'. Go specific: what was the technical challenge, what decision "
                f"was made, what was the measured outcome. This is a self-presentation post — make it "
                f"compelling for a hiring manager or potential collaborator reading it."
            )
        else:  # health_productivity
            return (
                "Health & productivity insight post — connect the article topic to focus, deep work, "
                "cognitive performance, or team wellbeing. Share a practical take: what data professionals "
                "can do to stay sharp and productive. Personal angle welcome but not required. "
                "Tone: grounded and practical, not motivational fluff."
            )

    def generate(self, article: Article) -> str:
        post_style = self._pick_post_style()
        prompt = BASE_PROMPT.format(
            profile=self.profile_text,
            title=article.title, source=article.source,
            summary=article.summary, url=article.url,
            post_style=post_style,
        )
        return self._call_with_retry(prompt)

    def regenerate(self, article: Article, previous_draft: str, feedback: str) -> str:
        post_style = self._pick_post_style()
        prompt = REGEN_PROMPT.format(
            profile=self.profile_text,
            title=article.title, source=article.source,
            summary=article.summary, url=article.url,
            post_style=post_style,
            previous_draft=previous_draft, feedback=feedback,
        )
        return self._call_with_retry(prompt)

    def generate_from_custom(self, raw_text: str) -> str:
        prompt = CUSTOM_PROMPT.format(
            profile=self.profile_text,
            raw_text=raw_text,
        )
        return self._call_with_retry(prompt)

    def pick_best_image(self, candidates: list[dict], post_text: str) -> str:
        """
        Given Unsplash candidates with metadata, ask Claude to pick the one
        that best matches the post content. Returns the URL of the best match.
        Falls back to first candidate on any error.
        """
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]["url"]

        lines = []
        for i, c in enumerate(candidates, 1):
            tags = ", ".join(c["tags"][:8]) if c["tags"] else "—"
            desc = c["description"] or c["alt_description"] or "no description"
            lines.append(f"{i}. Description: \"{desc[:120]}\" | Tags: {tags}")

        prompt = (
            f"You are selecting the most relevant Unsplash photo for a LinkedIn post.\n\n"
            f"Post excerpt (first 400 chars):\n{post_text[:400]}\n\n"
            f"Candidate photos:\n" + "\n".join(lines) + "\n\n"
            f"Which photo number best visually represents the post topic? "
            f"Consider: does the description/tags match the post theme? "
            f"Prefer concrete, professional imagery over generic abstracts.\n"
            f"Reply with ONLY the number (1–{len(candidates)})."
        )
        try:
            raw = self._call_with_retry(prompt).strip()
            # extract first integer from response
            import re
            match = re.search(r"\d+", raw)
            if match:
                idx = int(match.group()) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]["url"]
        except Exception:
            pass
        return candidates[0]["url"]

    def suggest_image_keywords(self, title: str, post_text: str) -> list[str]:
        prompt = (
            f"You need to find a photo on Unsplash that visually matches this LinkedIn post.\n\n"
            f"Article title: {title}\n"
            f"Post excerpt: {post_text[:200]}\n\n"
            f"Generate 3 Unsplash search queries, from most specific to most general:\n"
            f"1. A very specific visual scene or object directly related to the article title\n"
            f"2. A professional setting that fits the topic\n"
            f"3. A broader but still relevant fallback\n\n"
            f"Rules:\n"
            f"- Think like a photo editor: what IMAGE would run alongside this story in a magazine?\n"
            f"- Avoid abstract concepts — search for things that photograph well\n"
            f"- Good: 'analyst working laptop night office', 'neural network chip closeup', 'team meeting whiteboard data'\n"
            f"- Bad: 'technology', 'innovation', 'business'\n\n"
            f"Return ONLY 3 comma-separated search queries, nothing else."
        )
        try:
            result = self._call_with_retry(prompt)
            terms = [t.strip() for t in result.split(",") if t.strip()]
            return terms[:3] if terms else []
        except Exception:
            return []

    def _call_with_retry(self, prompt: str) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                return message.content[0].text
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Claude API failed after {self.max_retries} retries: {last_error}")
