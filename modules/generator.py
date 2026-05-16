import json
import logging
import random
import re
import time

import anthropic

from modules.models import Article, GeneratedPost

logger = logging.getLogger(__name__)

PERSONAL_CASES = [
    "At Metropolitan Premium Properties (Dubai's largest premium real estate brokerage), I built the full analytics stack from scratch — DWH architecture, CRM integration, Power BI dashboards — that drove a 10% revenue uplift.",
    "At Metropolitan Premium Properties, my analytics automation cut reporting turnaround 5× and boosted team productivity by 90%. The key was replacing manual Excel exports with a live CRM-connected pipeline.",
    "At Metropolitan, I own end-to-end data: from raw CRM events to executive dashboards C-suite actually uses for decisions. The hardest part wasn't the SQL — it was figuring out which metric actually drives broker performance.",
    "At Sberbank (70M+ customers, Russia's largest bank), I built NLP pipelines that detected 1.5M+ compliance violations across millions of documents — what used to take weeks, now runs overnight.",
    "At Sberbank, my ML model flagged 300K+ bankruptcy breaches in near-real-time. The lesson: a simple threshold model with good features beats a complex model with bad data every time.",
    "Working in Dubai real estate taught me that the right KPI framing matters more than the dashboard. Brokers need to see 'deals at risk' — not 'conversion rate'. Language shapes behavior.",
]

CONTENT_WEIGHTS: dict[str, int] = {
    "statistical_method": 35,
    "data_analytics_tip": 25,
    "case_study": 20,
    "ai_tools_for_analysts": 15,
    "industry_insight": 5,
}

_TYPE_INSTRUCTIONS: dict[str, str] = {
    "statistical_method": """Write about a SPECIFIC statistical method, formula, or analytical technique.

Required structure:
1. Hook: name the method + one surprising or counterintuitive fact (1-2 lines)
2. Plain-English definition: 1-2 sentences
3. When to use it: specific scenario with a concrete domain (e-commerce, SaaS, real estate, finance)
4. The formula or code: 1-8 lines of SQL or Python
5. The gotcha: one common mistake analysts make applying it
6. CTA: a question inviting practitioners to share experience

Good topics: Simpson's paradox, CUPED, cohort retention, Z-score normalization, Bayesian A/B testing, funnel decomposition, survival analysis, RFM segmentation, control charts, attribution modeling, Mann-Whitney U, log-normal revenue distributions.""",

    "data_analytics_tip": """Write about ONE practical, immediately actionable analytics tip.

Required structure:
1. Hook: the pain point or problem (1-2 relatable lines)
2. The tip: name the concrete technique, tool, or pattern explicitly
3. Implementation: show it — SQL snippet, DAX formula, Power BI pattern, or dbt code (3-12 lines)
4. Why it matters: business impact or time saved — quantify if possible
5. CTA: one question for the audience

Focus: SQL query patterns, DAX tricks, DWH design decisions, Power BI patterns, data modeling, dbt techniques, Python data manipulation.""",

    "case_study": """Write a real-world analytical case study. Anonymize company details if needed; keep numbers real.

Required structure:
1. Hook: the business problem or question (1-2 specific lines)
2. Context: industry, scale, constraints (2-3 sentences)
3. The analysis: what was measured and what method was used
4. The insight: what was found — include percentages or numbers
5. The outcome: business decision or result that followed
6. Lesson: the generalizable principle other analysts can apply
7. CTA: question for readers

Style: first-person, professional, humble but confident. Show the thinking process, not just the answer.""",

    "ai_tools_for_analysts": """Write about an AI tool or workflow SPECIFICALLY useful for data analysts — not generic AI hype.

Required structure:
1. Hook: the analyst workflow problem this tool solves (1-2 lines)
2. The tool: name it, what it does, why it matters for data work
3. Concrete use case: show it in action for a real DA task (SQL generation, data cleaning, report narration, anomaly detection, BI copilot)
4. Honest take: what it's good for vs. where it falls short
5. How to start: 1-2 sentence practical recommendation
6. CTA: question about whether readers use it

Focus: tools that augment DA work — SQL AI assistants, automated insights, AI for Power BI/Excel, dbt AI helpers. NOT generic ChatGPT tips or broad AI trend pieces.""",

    "industry_insight": """Write a specific, opinionated perspective on a data/analytics industry trend.

Required structure:
1. Hook: the trend or shift, stated boldly (1-2 lines)
2. Evidence: 2-3 concrete data points — tool releases, job posting shifts, company announcements
3. Impact on analysts: direct effect on the DA role or tech stack
4. Your take: a specific, opinionated view — avoid "it depends"
5. CTA: invite readers to share their perspective

Tone: thoughtful, specific, not hype. Skepticism is welcome if justified. No vague "AI is changing everything" statements.""",
}

_JSON_SUFFIX = """

---

Return your response as valid JSON with exactly these fields:
{{
  "post_text": "...(the full LinkedIn post, hashtags included on the last line)...",
  "image_prompt": "...(a visual scene, 15-25 words, data visualization aesthetic, dark background)",
  "main_topic": "...(2-5 word label, e.g. 'CUPED A/B testing', 'DAX CALCULATE trick')",
  "resume_reference": false,
  "project_mentioned": null
}}

Set resume_reference=true and project_mentioned="<project name>" if the post_text directly references Nikita's real work at MPP, Sberbank, LinkedIn Agent, or Dubai RE Bot.
Output ONLY valid JSON — no markdown fences, no surrounding commentary."""

_BASE_TEMPLATE = """You are writing a LinkedIn post for:

{profile}

---

Content type: {content_type_label}

{type_instructions}

---

Source material (use as topic seed — you may write a standalone educational post if the content type calls for it):
Title: {title}
Source: {source}
Summary: {summary}
URL: {url}

Post style: {post_style}

Format requirements:
- Hook: 1-2 punchy opening lines (surprising fact, bold claim, or question)
- Body: 3-4 short paragraphs, 150-200 words total. Be specific — use numbers, formulas, code.
- Source link: include {url} naturally only if the article is directly referenced; otherwise omit.
- CTA: one closing question to engage the audience
- End with a blank line then 5-7 hashtags (MANDATORY — never omit)

Tone: professional but conversational, data-driven, opinionated, no buzzwords.
{forbidden_block}""" + _JSON_SUFFIX

_CUSTOM_TEMPLATE = """You are a LinkedIn ghostwriter for:

{profile}

---

The author wrote this raw text:

{raw_text}

Transform it into a polished LinkedIn post in English:
- Keeps the author's authentic voice and core message
- Strong hook (first 1-2 lines before "see more")
- Structured: hook → insight → takeaway → CTA question
- Ends with 5-7 relevant hashtags (MANDATORY)

Write the post only — no meta-commentary."""

_REGEN_TEMPLATE = _BASE_TEMPLATE.replace(_JSON_SUFFIX, "") + """

---

PREVIOUS DRAFT (improve it, don't repeat):
{previous_draft}

USER FEEDBACK (apply this):
{feedback}""" + _JSON_SUFFIX


class ContentGenerator:
    def __init__(self, api_key: str, profile_text: str, max_retries: int = 3):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.profile_text = profile_text
        self.max_retries = max_retries
        self._last_case_idx: int = -1

    def _pick_case(self) -> str:
        available = [i for i in range(len(PERSONAL_CASES)) if i != self._last_case_idx]
        if not available:
            available = list(range(len(PERSONAL_CASES)))
        idx = random.choice(available)
        self._last_case_idx = idx
        return PERSONAL_CASES[idx]

    def _pick_post_style(self) -> str:
        styles = [("pure_insight", 40), ("with_case", 40), ("personal_story", 20)]
        names, weights = zip(*styles)
        chosen = random.choices(names, weights=weights, k=1)[0]
        if chosen == "pure_insight":
            return "Pure insight — focus on the key educational takeaway for data professionals."
        case = self._pick_case()
        if chosen == "with_case":
            return f"Weave in this real experience naturally (1-2 sentences max): '{case}'"
        return f"Open with this real experience: '{case}'. Then connect to the broader lesson."

    def _pick_content_type(self) -> str:
        names = list(CONTENT_WEIGHTS.keys())
        weights = list(CONTENT_WEIGHTS.values())
        return random.choices(names, weights=weights, k=1)[0]

    def generate(
        self,
        article: Article,
        content_type: str | None = None,
        forbidden_topics: list[str] | None = None,
    ) -> GeneratedPost:
        """Generate a LinkedIn post. Returns GeneratedPost with text, image prompt, and metadata."""
        chosen_type = content_type or self._pick_content_type()
        type_label = chosen_type.replace("_", " ").title()
        forbidden_block = ""
        if forbidden_topics:
            forbidden_block = f"\nFORBIDDEN topics (do not reference these projects or cases): {', '.join(forbidden_topics)}\n"
        prompt = _BASE_TEMPLATE.format(
            profile=self.profile_text,
            content_type_label=type_label,
            type_instructions=_TYPE_INSTRUCTIONS[chosen_type],
            title=article.title, source=article.source,
            summary=article.summary, url=article.url,
            post_style=self._pick_post_style(),
            forbidden_block=forbidden_block,
        )
        raw = self._call_with_retry(prompt)
        result = self._parse_generated(raw)
        result.content_type = chosen_type
        logger.info(
            "Generated post: type=%s topic=%s resume_ref=%s",
            chosen_type, result.main_topic, result.resume_reference,
        )
        return result

    def regenerate(
        self,
        article: Article,
        previous_draft: str,
        feedback: str,
        content_type: str | None = None,
    ) -> GeneratedPost:
        """Regenerate post incorporating user feedback."""
        chosen_type = content_type or self._pick_content_type()
        prompt = _REGEN_TEMPLATE.format(
            profile=self.profile_text,
            content_type_label=chosen_type.replace("_", " ").title(),
            type_instructions=_TYPE_INSTRUCTIONS[chosen_type],
            title=article.title, source=article.source,
            summary=article.summary, url=article.url,
            post_style=self._pick_post_style(),
            forbidden_block="",
            previous_draft=previous_draft,
            feedback=feedback,
        )
        raw = self._call_with_retry(prompt)
        result = self._parse_generated(raw)
        result.content_type = chosen_type
        return result

    def generate_from_custom(self, raw_text: str) -> str:
        """Generate post from user's raw text. Returns plain string (no JSON)."""
        prompt = _CUSTOM_TEMPLATE.format(profile=self.profile_text, raw_text=raw_text)
        return self._call_with_retry(prompt)

    def pick_best_image(self, candidates: list[dict], post_text: str) -> str:
        """Ask Claude to pick the most relevant Unsplash photo for the post."""
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
            f"Select the most relevant Unsplash photo for a LinkedIn post.\n\n"
            f"Post excerpt:\n{post_text[:400]}\n\n"
            f"Candidates:\n" + "\n".join(lines) + "\n\n"
            f"Reply with ONLY the number (1–{len(candidates)})."
        )
        try:
            raw = self._call_with_retry(prompt).strip()
            match = re.search(r"\d+", raw)
            if match:
                idx = int(match.group()) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]["url"]
        except Exception as e:
            logger.warning("pick_best_image failed, using first candidate: %s", e)
        return candidates[0]["url"]

    def suggest_image_keywords(self, title: str, post_text: str) -> list[str]:
        """Suggest Unsplash search terms for the post."""
        prompt = (
            f"Suggest 2-3 specific Unsplash search terms for this LinkedIn post.\n\n"
            f"Title: {title}\nPost (first 300 chars): {post_text[:300]}\n\n"
            f"Return ONLY a comma-separated list. Example: data center, server rack, cloud infrastructure"
        )
        try:
            result = self._call_with_retry(prompt)
            return [t.strip() for t in result.split(",") if t.strip()][:3]
        except Exception:
            return []

    def _parse_generated(self, raw: str) -> GeneratedPost:
        """Parse JSON response from Claude. Falls back to raw text as post_text on error."""
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return GeneratedPost(
                    post_text=data.get("post_text", raw),
                    image_prompt=data.get("image_prompt", ""),
                    content_type=data.get("content_type", ""),
                    main_topic=data.get("main_topic", ""),
                    resume_reference=bool(data.get("resume_reference", False)),
                    project_mentioned=data.get("project_mentioned") or None,
                )
            except json.JSONDecodeError:
                logger.warning("Claude returned invalid JSON — using full response as post_text")
        return GeneratedPost(post_text=raw, image_prompt="", content_type="", main_topic="")

    def _call_with_retry(self, prompt: str) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                if not message.content:
                    raise ValueError("Empty content in Claude response")
                return message.content[0].text
            except Exception as e:
                last_error = e
                logger.warning(
                    "Claude API attempt %d/%d failed: %s", attempt + 1, self.max_retries, e
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Claude API failed after {self.max_retries} retries: {last_error}")
