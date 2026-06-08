import logging
import os
import time
import anthropic
from modules.models import Article

logger = logging.getLogger(__name__)

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

PERSONAL_POST_PROMPT_V3 = """You are writing a LinkedIn post AS Nikita Krivoshei (first person).

{profile}

---

Raw context Nikita shared ({category} category):
"{context_text}"

Write rules:
- Hook: 1-2 punchy lines. NEVER start with 'I'. Bold claim, number, or question.
- Body: 3-4 short paragraphs. Stay close to raw context. Be specific.
- Voice: direct, slightly blunt, data-driven. Like a senior analyst texting a colleague -- not a LinkedIn influencer.
- No em-dashes (--). No 'Here's what I learned:' headers. No bullet lists of lessons.
- Mix sentence lengths naturally.
- CTA: ONE specific question or challenge. Not 'What do you think?' -- something concrete.
- Hashtags: 5-7 on last line. Mix specific + career visibility. NEVER #OpenToWork.

Category tone:
- work -> technical precision, real numbers, honest about the mess
- opinion -> confident, willing to be wrong, invites pushback
- learning -> curiosity + practical application, 'here's what changed my approach'
- life -> observational, connects personal to professional, not braggy

Write ONLY the post. No meta-commentary.
Hashtags are MANDATORY."""


class ContentGenerator:
    def __init__(self, api_key: str, profile_text: str, max_retries: int = 3):
        # Claude Code sets ANTHROPIC_AUTH_TOKEN='' in system env.
        # SDK v0.96.0 reads it and creates "Authorization: Bearer " (empty) -> h11 rejects.
        # Fix: remove the empty token so SDK falls back to X-Api-Key header only.
        if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.profile_text = profile_text
        self.max_retries = max_retries

    def generate(self, article: Article) -> str:
        post_style = (
            "Pure insight post -- share the key takeaway. "
            "Focus on data professionals. Bold opinion or contrarian take."
        )
        prompt = BASE_PROMPT.format(
            profile=self.profile_text,
            title=article.title, source=article.source,
            summary=article.summary, url=article.url,
            post_style=post_style,
        )
        return self._call_with_retry(prompt)

    def regenerate(self, article: Article, previous_draft: str, feedback: str) -> str:
        post_style = (
            "Pure insight post -- share the key takeaway. "
            "Focus on data professionals. Bold opinion or contrarian take."
        )
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

    def generate_personal(self, entries: list[dict], post_type: str) -> str:
        """Generate a personal LinkedIn post from context entries.

        Args:
            entries: list of dicts with 'category' and 'text' keys,
                     as returned by ContextStore.get_unused_entries().
                     If empty, AI generates a fallback theme from profile_text.
            post_type: one of 'personal_story' | 'hot_take' | 'achievement' | 'learning'

        Returns:
            Generated post text.
        """
        if not entries:
            context_text = self._generate_fallback_theme(post_type)
            category = "work"
        else:
            entry = entries[0]
            category = entry.get("category", "work")
            context_text = entry.get("text", "")

        prompt = PERSONAL_POST_PROMPT_V3.format(
            profile=self.profile_text,
            category=category,
            context_text=context_text,
        )
        return self._call_with_retry(prompt)

    def _generate_fallback_theme(self, post_type: str) -> str:
        """Ask AI to generate a specific work insight for the given post type."""
        type_descriptions = {
            "personal_story": "tells a personal professional story about a challenge or win",
            "hot_take": "presents a bold contrarian opinion on data/analytics/tech",
            "achievement": "highlights a concrete professional achievement with metrics",
            "learning": "shares a practical learning or insight that changed your approach",
        }
        description = type_descriptions.get(
            post_type,
            "shares a relevant professional insight or observation"
        )
        fallback_prompt = (
            f"Generate a specific work insight or observation that {description} "
            f"for Nikita Krivoshei's LinkedIn post, based on this profile:\n\n"
            f"{self.profile_text}\n\n"
            f"Return ONLY the context text (2-3 sentences). "
            f"Be specific -- include real numbers or situations."
        )
        return self._call_with_retry(fallback_prompt)

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
            tags = ", ".join(c["tags"][:8]) if c["tags"] else "--"
            desc = c["description"] or c["alt_description"] or "no description"
            lines.append(f"{i}. Description: \"{desc[:120]}\" | Tags: {tags}")

        prompt = (
            f"You are selecting the most relevant Unsplash photo for a LinkedIn post.\n\n"
            f"Post excerpt (first 400 chars):\n{post_text[:400]}\n\n"
            f"Candidate photos:\n" + "\n".join(lines) + "\n\n"
            f"Which photo number best visually represents the post topic? "
            f"Consider: does the description/tags match the post theme? "
            f"Prefer concrete, professional imagery over generic abstracts.\n"
            f"Reply with ONLY the number (1-{len(candidates)})."
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
            logger.exception("Image selection by Claude failed, using first candidate")
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
            f"- Avoid abstract concepts -- search for things that photograph well\n"
            f"- Good: 'analyst working laptop night office', 'neural network chip closeup', 'team meeting whiteboard data'\n"
            f"- Bad: 'technology', 'innovation', 'business'\n\n"
            f"Return ONLY 3 comma-separated search queries, nothing else."
        )
        try:
            result = self._call_with_retry(prompt)
            terms = [t.strip() for t in result.split(",") if t.strip()]
            return terms[:3] if terms else []
        except Exception:
            logger.exception("Image keyword suggestion failed")
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
