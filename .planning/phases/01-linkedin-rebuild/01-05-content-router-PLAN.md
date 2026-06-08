---
phase: 01-linkedin-rebuild
plan: 5
type: execute
wave: 2
depends_on:
  - 01-01-config-models
  - 01-04-context-store-questionnaire
files_modified:
  - modules/content_router.py
autonomous: true
requirements:
  - REQ-06

must_haves:
  truths:
    - "ContentRouter читает последние 30 постов из Notion и возвращает следующий post_type"
    - "Если 2 последних поста одного типа — этот тип исключается из выборки"
    - "Веса типов: news_insight=35%, personal_story=25%, hot_take=20%, achievement=10%, learning=10%"
    - "Если нет свежих context entries (Used=False) — вес news_insight увеличивается"
  artifacts:
    - path: "modules/content_router.py"
      provides: "ContentRouter.choose_post_type() → str"
      contains: "class ContentRouter"
  key_links:
    - from: "modules/notion.py"
      to: "modules/content_router.py"
      via: "get_recent_post_types(n=30) → list[str]"
      pattern: "get_recent_post_types"
    - from: "modules/content_router.py"
      to: "main.py run_pipeline()"
      via: "post_type = router.choose_post_type(has_fresh_context=...)"
      pattern: "choose_post_type"
---

<objective>
Создать модуль modules/content_router.py с умным ротатором типов контента.

Purpose: REQ-06 — ротатор читает историю из Notion и предотвращает 2+ постов одного типа подряд. Это новый файл без зависимости от modules/notion.py — принимает данные через параметры, не читает Notion сам.

Output: modules/content_router.py с ContentRouter.choose_post_type().
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
</context>

<interfaces>
<!-- Решение D-04 из CONTEXT.md -->
Types and weights:
  POST_TYPES = ["news_insight", "personal_story", "hot_take", "achievement", "learning"]
  BASE_WEIGHTS = {"news_insight": 35, "personal_story": 25, "hot_take": 20, "achievement": 10, "learning": 10}

Hard rule: если последние 2 поста = тот же тип → вес этого типа = 0 (forced rotation)
No-context fallback: если has_fresh_context=False → news_insight weight += 20 (итого 55)

Публичный интерфейс:
  class ContentRouter:
      def choose_post_type(
          self,
          recent_types: list[str],   # последние N типов постов из Notion (от новых к старым)
          has_fresh_context: bool = True
      ) -> str

Дополнительно:
  def needs_fresh_context(post_type: str) -> bool:
      # True для: personal_story, hot_take, achievement, learning
      # False для: news_insight

Этот модуль НЕ обращается к Notion напрямую.
Логика get_recent_post_types() добавляется в notion.py (план 7).
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Создать modules/content_router.py</name>
  <files>modules/content_router.py</files>
  <read_first>
    - .planning/phases/01-linkedin-rebuild/01-CONTEXT.md — секция D-04 (Content Type Rotator)
  </read_first>
  <action>
    Создать новый файл modules/content_router.py.

    Константы:
    - POST_TYPES: list[str] = ["news_insight", "personal_story", "hot_take", "achievement", "learning"]
    - BASE_WEIGHTS: dict[str, int] = {"news_insight": 35, "personal_story": 25, "hot_take": 20, "achievement": 10, "learning": 10}
    - CONTEXT_DEPENDENT_TYPES: frozenset = frozenset({"personal_story", "hot_take", "achievement", "learning"})

    Функция needs_fresh_context(post_type: str) -> bool:
    - вернуть post_type in CONTEXT_DEPENDENT_TYPES

    Класс ContentRouter:
    - __init__(self): без аргументов, только импорты

    Метод choose_post_type(self, recent_types: list[str], has_fresh_context: bool = True) -> str:
    - Скопировать weights = dict(BASE_WEIGHTS) (не мутировать константу)
    - Проверить forced rotation: если len(recent_types) >= 2 и recent_types[0] == recent_types[1]:
        weights[recent_types[0]] = 0
    - Если not has_fresh_context:
        weights["news_insight"] = weights.get("news_insight", 35) + 20
        для всех CONTEXT_DEPENDENT_TYPES обнулить веса: weights[t] = 0
    - Отфильтровать типы с весом > 0: eligible = [t for t in POST_TYPES if weights.get(t, 0) > 0]
    - Если eligible пустой (теоретически невозможно, но failsafe): вернуть "news_insight"
    - Вернуть random.choices(eligible, weights=[weights[t] for t in eligible], k=1)[0]

    Импорты: random, logging. logger = logging.getLogger(__name__).
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.content_router import ContentRouter, needs_fresh_context, POST_TYPES

router = ContentRouter()

# Forced rotation: если последние 2 = news_insight → не должен снова выбрать news_insight
results = set()
for _ in range(50):
    t = router.choose_post_type(['news_insight', 'news_insight'])
    results.add(t)
assert 'news_insight' not in results, 'Forced rotation failed'

# No-context: только news_insight
results2 = set()
for _ in range(30):
    t = router.choose_post_type([], has_fresh_context=False)
    results2.add(t)
assert results2 == {'news_insight'}, f'No-context should only pick news_insight, got {results2}'

# needs_fresh_context
assert needs_fresh_context('personal_story') == True
assert needs_fresh_context('news_insight') == False

print('ContentRouter OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - choose_post_type(['news_insight', 'news_insight']) никогда не возвращает 'news_insight' (проверить 50 раз)
    - choose_post_type([], has_fresh_context=False) всегда возвращает 'news_insight' (30 раз)
    - choose_post_type([]) возвращает один из POST_TYPES
    - needs_fresh_context('personal_story') == True
    - needs_fresh_context('news_insight') == False
    - Результат всегда один из POST_TYPES
  </acceptance_criteria>
  <done>modules/content_router.py создан; ContentRouter.choose_post_type() реализует D-04 логику ротации</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| recent_types list → weights | данные из Notion не исполняются, только сравниваются строки |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01 | Tampering | recent_types содержит невалидный тип | mitigate | weights.get(t, 0) — неизвестные типы получают вес 0 |
| T-05-SC | Tampering | pip installs | accept | план не устанавливает новых зависимостей |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.content_router import ContentRouter, needs_fresh_context, POST_TYPES, BASE_WEIGHTS

# Проверка весов
assert sum(BASE_WEIGHTS.values()) == 100
assert set(BASE_WEIGHTS.keys()) == set(POST_TYPES)

# Ротация при двух одинаковых
r = ContentRouter()
for _ in range(20):
    t = r.choose_post_type(['hot_take', 'hot_take'])
    assert t != 'hot_take', f'Should not pick hot_take after 2 in a row, got {t}'

# No context → только news_insight
for _ in range(20):
    t = r.choose_post_type([], has_fresh_context=False)
    assert t == 'news_insight'

print('PASS: content_router OK')
"
</verification>

<success_criteria>
- ContentRouter.choose_post_type() реализован с forced rotation и no-context fallback
- needs_fresh_context() корректно классифицирует типы
- 100% покрытие логики ротации через проверки выше
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-05-SUMMARY.md` when done
</output>
