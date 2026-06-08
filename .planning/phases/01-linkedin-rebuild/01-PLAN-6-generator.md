---
phase: 01-linkedin-rebuild
plan: 6
type: execute
wave: 2
depends_on:
  - plan-1
  - plan-4
files_modified:
  - modules/generator.py
autonomous: true
requirements:
  - REQ-08
  - REQ-09
  - REQ-10

must_haves:
  truths:
    - "ANTHROPIC_AUTH_TOKEN fix применён в ContentGenerator.__init__()"
    - "PERSONAL_CASES константа удалена"
    - "generate_personal() принимает context entries из Notion и генерирует пост голосом Никиты"
    - "V3 prompts не используют em-dash, 'Here's what I learned:', bullet-lists of lessons"
    - "Регенерация работает для обоих типов постов: news + personal"
  artifacts:
    - path: "modules/generator.py"
      provides: "ContentGenerator с generate_personal(), V3 prompts, ANTHROPIC_AUTH_TOKEN fix"
      contains: "generate_personal"
  key_links:
    - from: "modules/generator.py ContentGenerator.__init__()"
      to: "anthropic.Anthropic()"
      via: "pop ANTHROPIC_AUTH_TOKEN перед init"
      pattern: "ANTHROPIC_AUTH_TOKEN"
    - from: "modules/context_store.py get_unused_entries()"
      to: "modules/generator.py generate_personal()"
      via: "entries: list[dict] с category, text"
      pattern: "generate_personal"
---

<objective>
Обновить modules/generator.py: добавить ANTHROPIC_AUTH_TOKEN fix, V3 prompt, generate_personal(), удалить PERSONAL_CASES.

Purpose: REQ-08 (V3 prompt), REQ-09 (генерация из Notion контекста), REQ-10 (ANTHROPIC_AUTH_TOKEN fix). Без этих изменений пайплайн будет производить generic LinkedIn fluff вместо постов голосом Никиты, и падать в Claude Code environment.

Output: Обновлённый modules/generator.py с тремя ключевыми изменениями.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/spikes/003-personal-post-from-context/spike_test.py
</context>

<interfaces>
<!-- Существующий интерфейс из modules/generator.py -->
class ContentGenerator:
    def __init__(self, api_key: str, profile_text: str, max_retries: int = 3)
    def generate(self, article: Article) -> str
    def regenerate(self, article: Article, previous_draft: str, feedback: str) -> str
    def generate_from_custom(self, raw_text: str) -> str
    def pick_best_image(self, candidates: list[dict], post_text: str) -> str
    def suggest_image_keywords(self, title: str, post_text: str) -> list[str]

<!-- Новые методы и изменения -->
Новый метод generate_personal(entries: list[dict], post_type: str) -> str:
  entries = [{"category": str, "text": str}, ...]  из ContextStore.get_unused_entries()
  post_type = "personal_story" | "hot_take" | "achievement" | "learning"

ANTHROPIC_AUTH_TOKEN fix (из spike 003, строки 27-29):
  В __init__() ПЕРЕД anthropic.Anthropic(api_key=api_key):
    import os
    if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

V3 PERSONAL_POST_PROMPT (из решения D-05 в CONTEXT.md):
  - Пишет от первого лица как Никита (не ghostwriter)
  - Нет em-dash (—), нет "Here's what I learned:", нет bullet-list of lessons
  - Естественная смесь длин предложений
  - Category-specific tone:
    work → technical precision, real numbers
    opinion → confident, invites pushback
    learning → curiosity + practical application
    life → observational, connects personal to professional
  - Никогда не использует #OpenToWork
  - 5-7 хэштегов на последней строке

Fallback в generate_personal(): если entries пустой → вызвать AI для генерации темы из profile_text
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: ANTHROPIC_AUTH_TOKEN fix + V3 prompt + generate_personal()</name>
  <files>modules/generator.py</files>
  <read_first>
    - modules/generator.py — прочитать полностью перед изменением
    - .planning/spikes/003-personal-post-from-context/spike_test.py — строки 26-29 (AUTH_TOKEN fix) и строки 99-120 (PERSONAL_POST_PROMPT_V2 как основа для V3)
    - .planning/phases/01-linkedin-rebuild/01-CONTEXT.md — секция D-05 (V3 tone rules)
  </read_first>
  <action>
    Прочитать modules/generator.py полностью.

    Изменение 1 — ANTHROPIC_AUTH_TOKEN fix (REQ-10):
    В __init__() добавить ПЕРЕД self.client = anthropic.Anthropic(api_key=api_key):
      import os
      if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
          os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    (os уже импортирован в Python, добавить import os в начало файла если отсутствует)

    Изменение 2 — Удалить PERSONAL_CASES (REQ-09):
    - Удалить константу PERSONAL_CASES (строки 10-17)
    - Удалить методы _pick_case() и _pick_post_style() — они использовали PERSONAL_CASES
    - В методе generate() заменить: вместо post_style = self._pick_post_style() использовать фиксированный тип "pure_insight" (новые типы определяются ContentRouter снаружи)
    - Упростить generate() до: prompt = BASE_PROMPT.format(profile=..., title=..., ..., post_style="Pure insight post — share the key takeaway. Focus on data professionals. Bold opinion or contrarian take.")

    Изменение 3 — Добавить PERSONAL_POST_PROMPT_V3 константу (REQ-08):
    Новая константа PERSONAL_POST_PROMPT_V3 после BASE_PROMPT:

    Шаблон промпта (пишется AS Nikita Krivoshei, first person):
    - Открывать: "You are writing a LinkedIn post AS Nikita Krivoshei (first person).\n\n{profile}\n\n---\n\n"
    - Контекст: "Raw context Nikita shared ({category} category):\n\"{context_text}\"\n\n"
    - Правила поста:
      "Write rules:\n"
      "- Hook: 1-2 punchy lines. NEVER start with 'I'. Bold claim, number, or question.\n"
      "- Body: 3-4 short paragraphs. Stay close to raw context. Be specific.\n"
      "- Voice: direct, slightly blunt, data-driven. Like a senior analyst texting a colleague — not a LinkedIn influencer.\n"
      "- No em-dashes (—). No 'Here's what I learned:' headers. No bullet lists of lessons.\n"
      "- Mix sentence lengths naturally.\n"
      "- CTA: ONE specific question or challenge. Not 'What do you think?' — something concrete.\n"
      "- Hashtags: 5-7 on last line. Mix specific + career visibility. NEVER #OpenToWork.\n\n"
      "Category tone:\n"
      "- work → technical precision, real numbers, honest about the mess\n"
      "- opinion → confident, willing to be wrong, invites pushback\n"
      "- learning → curiosity + practical application, 'here's what changed my approach'\n"
      "- life → observational, connects personal to professional, not braggy\n\n"
      "Write ONLY the post. No meta-commentary.\n"
      "Hashtags are MANDATORY."

    Изменение 4 — Добавить метод generate_personal() (REQ-09):
    def generate_personal(self, entries: list[dict], post_type: str) -> str:
    - Если entries пустой: сгенерировать тему из profile_text через _generate_fallback_theme(post_type) → вызвать _call_with_retry с запросом "Generate a specific work insight or observation that {post_type_description} for Nikita Krivoshei's LinkedIn post. Return ONLY the context text (2-3 sentences)."
    - Иначе: выбрать entry = entries[0] (первый неиспользованный)
    - Составить prompt = PERSONAL_POST_PROMPT_V3.format(profile=self.profile_text, category=entry["category"], context_text=entry["text"])
    - Вернуть self._call_with_retry(prompt)

    Изменение 5 — suggest_image_keywords() и pick_best_image() оставить без изменений.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import os
os.environ['ANTHROPIC_AUTH_TOKEN'] = ''
from modules.generator import ContentGenerator, PERSONAL_POST_PROMPT_V3
assert 'PERSONAL_CASES' not in dir(__import__('modules.generator', fromlist=['generator']))
assert 'PERSONAL_POST_PROMPT_V3' in dir(__import__('modules.generator', fromlist=['generator']))
import inspect
src = inspect.getsource(ContentGenerator.__init__)
assert 'ANTHROPIC_AUTH_TOKEN' in src
assert 'generate_personal' in [m for m in dir(ContentGenerator) if not m.startswith('__')]
print('ContentGenerator V3 OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - PERSONAL_CASES не определён в modules/generator.py
    - PERSONAL_POST_PROMPT_V3 константа существует
    - ContentGenerator.__init__() содержит ANTHROPIC_AUTH_TOKEN fix
    - ContentGenerator.generate_personal(entries, post_type) существует
    - В PERSONAL_POST_PROMPT_V3 нет em-dash в инструкциях (явно запрещены)
    - В PERSONAL_POST_PROMPT_V3 есть правило "NEVER #OpenToWork"
    - python -c "from modules.generator import ContentGenerator" без ошибок
    - Старый метод generate(article) продолжает работать (обратная совместимость)
  </acceptance_criteria>
  <done>modules/generator.py обновлён: ANTHROPIC_AUTH_TOKEN fix, PERSONAL_CASES удалён, V3 prompt добавлен, generate_personal() реализован</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| context entries → Claude prompt | текст из Notion вставляется в промпт как контент, не как инструкции |
| ANTHROPIC_AUTH_TOKEN env → SDK | пустой токен удаляется из env перед инициализацией |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-01 | Tampering | context_text in prompt injection | accept | текст вставляется в user content, не в system prompt; Claude не будет исполнять инструкции из контента пользователя без явного указания |
| T-06-02 | Denial of Service | Claude API retry loop | mitigate | _call_with_retry с max_retries=3, exponential backoff; после 3 попыток raising RuntimeError |
| T-06-SC | Tampering | pip installs | accept | anthropic уже в requirements.txt |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import modules.generator as g
import inspect

# PERSONAL_CASES удалён
assert not hasattr(g, 'PERSONAL_CASES'), 'PERSONAL_CASES should be deleted'

# V3 prompt существует
assert hasattr(g, 'PERSONAL_POST_PROMPT_V3')
v3 = g.PERSONAL_POST_PROMPT_V3
assert '—' not in v3 or 'em-dash' in v3.lower(), 'V3 should forbid em-dashes'
assert 'OpenToWork' in v3

# AUTH_TOKEN fix в __init__
src = inspect.getsource(g.ContentGenerator.__init__)
assert 'ANTHROPIC_AUTH_TOKEN' in src

# generate_personal существует
assert hasattr(g.ContentGenerator, 'generate_personal')

print('PASS: generator V3 OK')
"
</verification>

<success_criteria>
- PERSONAL_CASES удалён из кода
- V3 prompt содержит правила: no em-dash, no 'Here's what I learned', category-specific tone
- ANTHROPIC_AUTH_TOKEN fix применён до Anthropic client init
- generate_personal([], "personal_story") работает без исключений (fallback path)
- generate(article) продолжает работать (регрессия отсутствует)
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-06-SUMMARY.md` when done
</output>
