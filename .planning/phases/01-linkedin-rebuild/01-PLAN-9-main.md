---
phase: 01-linkedin-rebuild
plan: 9
type: execute
wave: 3
depends_on:
  - plan-1
  - plan-2
  - plan-3
  - plan-5
  - plan-6
  - plan-7
  - plan-8
files_modified:
  - main.py
autonomous: true
requirements:
  - REQ-03
  - REQ-04
  - REQ-06
  - REQ-09

must_haves:
  truths:
    - "Квестионнер запускается 2x/week по расписанию QUESTIONNAIRE_SCHEDULE"
    - "run_pipeline() использует ContentRouter для выбора post_type"
    - "Для personal post_types вызывается generator.generate_personal(entries)"
    - "on_new_image callback регенерирует только изображение, обновляет PostRecord.image_url в Notion"
    - "ImageFetcher инициализируется с notion_blacklist_getter/setter из ContextStore"
    - "Все существующие on_publish, on_skip, on_regenerate работают без изменений"
  artifacts:
    - path: "main.py"
      provides: "build_pipeline() с ContentRouter + questionnaire scheduler job"
      contains: "questionnaire"
  key_links:
    - from: "APScheduler"
      to: "bot.send_questionnaire()"
      via: "CronTrigger на TUE,FRI"
      pattern: "questionnaire_schedule|send_questionnaire"
    - from: "content_router.choose_post_type()"
      to: "generator.generate_personal() или generator.generate()"
      via: "post_type in CONTEXT_DEPENDENT_TYPES"
      pattern: "choose_post_type|generate_personal"
    - from: "ImageFetcher"
      to: "context_store.get_used_unsplash_ids"
      via: "notion_blacklist_getter callback"
      pattern: "notion_blacklist_getter|get_used_unsplash_ids"
---

<objective>
Обновить main.py: подключить все новые модули в build_pipeline() и добавить квестионнер как scheduled job.

Purpose: Финальная интеграция — все компоненты Wave 1-2 подключаются в main.py. Это самый чувствительный план: любая ошибка здесь сломает production deploy на Railway.

Output: Обновлённый main.py с полным пайплайном и квестионнером.
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
<!-- Существующий код main.py (ключевые части) -->
Существующие импорты в main.py:
from modules.generator import ContentGenerator
from modules.images import ImageFetcher
from modules.linkedin import LinkedInPublisher
from modules.models import Article, PostRecord
from modules.news import NewsCollector
from modules.notion import NotionLogger
from modules.telegram_bot import PostApprovalBot

Существующий build_pipeline() создаёт:
  news = NewsCollector(...)
  generator = ContentGenerator(api_key=..., profile_text=...)
  images = ImageFetcher(unsplash_key=..., use_dalle=..., openai_key=...)
  notion = NotionLogger(...)
  linkedin = LinkedInPublisher(...)

Существующие on_publish, on_skip, on_regenerate — НЕ менять логику, только добавить post_type.

Новые импорты добавить:
from modules.context_store import ContextStore
from modules.content_router import ContentRouter, needs_fresh_context
from modules.questionnaire import QuestionnaireState  (не нужен здесь, в боте уже)

Новая инициализация в build_pipeline():
  context_store = ContextStore(token=cfg.notion_token, context_db_id=cfg.notion_context_db_id)
  router = ContentRouter()
  images = ImageFetcher(
      unsplash_key=cfg.unsplash_access_key,
      openai_key=cfg.openai_api_key,
      use_gpt_image=cfg.use_gpt_image,
      notion_blacklist_getter=context_store.get_used_unsplash_ids if context_store.is_available() else None,
      notion_blacklist_setter=context_store.mark_unsplash_used if context_store.is_available() else None,
  )

Обновлённый run_pipeline():
  1. recent_types = notion.get_recent_post_types(n=30)
  2. entries = context_store.get_unused_entries(limit=10) if context_store.is_available() else []
  3. has_fresh = bool(entries)
  4. post_type = router.choose_post_type(recent_types, has_fresh_context=has_fresh)
  5. if needs_fresh_context(post_type) and entries:
       post_text = generator.generate_personal(entries, post_type)
       context_store.mark_entry_used(entries[0]["id"]) if context_store.is_available() else None
       article = Article(title="Personal Post", url="", summary=entries[0]["text"],
                         source="Context", published_at="", keywords=[])
     elif needs_fresh_context(post_type) and not entries:
       # деградация: нет контекста → переключиться на news
       post_type = "news_insight"
       → продолжить как news pipeline (fetch article, generate(article))
     else:  # news_insight
       article = news.fetch(already_published_urls=notion.get_published_urls())
       if not article: [существующий no-article path]
       post_text = generator.generate(article)
  6. Получить image: если post_type in PERSONAL_POST_TYPES → image_bytes = images.fetch_gpt_image(post_type, post_text)
                                                                           photo_path = images.fetch_profile_photo(post_type)
                    если post_type in GPT_IMAGE_TYPES → image_bytes = images.fetch_gpt_image(post_type, post_text)
     Fallback: если image_bytes/photo_path — None → Unsplash candidates
  7. Создать record с post_type: record = notion.create_draft(article, post_text, image_url, topics, post_type=post_type)
  8. Передать в bot.send_preview()

on_new_image callback (новый):
  async def on_new_image(record: PostRecord):
      image_bytes = images.fetch_gpt_image(record.post_type or "news_insight", record.post_text)
      photo_path = images.fetch_profile_photo(record.post_type or "")
      new_image_url = ""
      if image_bytes:
          new_image_url = "[gpt-image-1]"  # bytes переданы через bot, не URL
      elif photo_path:
          new_image_url = photo_path
      else:
          candidates = images.fetch_candidates(keywords=[record.title.split()[0]])
          new_image_url = generator.pick_best_image(candidates, record.post_text)
          images.mark_used(new_image_url, candidates)
      notion.update_status(record.notion_page_id, record.status, image_url=new_image_url)
      # Отправить обновлённое превью с новым изображением
      updated_record = PostRecord(**{**record.__dict__, "image_url": new_image_url})
      await bot.send_preview(
          Article(title=record.title, url=record.source_url, summary="", source="", published_at=""),
          updated_record
      )

Квестионнер в main():
  DOW_MAP используется для questionnaire_schedule так же как для post_schedule
  q_days = ",".join(DOW_MAP[d] for d in cfg.questionnaire_schedule.split(",") if d.strip() in DOW_MAP)
  if q_days:
      scheduler.add_job(bot.send_questionnaire, CronTrigger(day_of_week=q_days, hour=7, minute=0))

Bot инициализация в main() добавить параметры:
  on_new_image=on_new_image_func,
  on_context_entry=on_context_entry_func

on_context_entry:
  async def on_context_entry(category: str, text: str):
      context_store.add_entry(category=category, text=text)
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Обновить build_pipeline() с ContentRouter, ContextStore, on_new_image</name>
  <files>main.py</files>
  <read_first>
    - main.py — прочитать полностью перед изменением
    - modules/content_router.py — убедиться что ContentRouter, needs_fresh_context, CONTEXT_DEPENDENT_TYPES, GPT_IMAGE_TYPES, PERSONAL_POST_TYPES экспортируются
    - modules/context_store.py — проверить сигнатуру ContextStore.__init__()
    - modules/images.py — проверить сигнатуру нового ImageFetcher.__init__()
    - modules/notion.py — проверить что create_draft() принимает post_type
  </read_first>
  <action>
    Прочитать main.py полностью.

    Шаг 1 — Обновить импорты:
    Удалить: (нет удаляемых импортов)
    Добавить в блок импортов:
    from modules.context_store import ContextStore
    from modules.content_router import ContentRouter, needs_fresh_context
    from modules.images import PERSONAL_POST_TYPES, GPT_IMAGE_TYPES

    Шаг 2 — Обновить build_pipeline():
    Изменить инициализацию images:
    - Удалить: ImageFetcher(unsplash_key=..., use_dalle=cfg.use_dalle, openai_key=...)
    - Добавить: context_store = ContextStore(token=cfg.notion_token, context_db_id=cfg.notion_context_db_id) ПЕРЕД images
    - Добавить: router = ContentRouter()
    - Новый: images = ImageFetcher(
          unsplash_key=cfg.unsplash_access_key,
          openai_key=cfg.openai_api_key,
          use_gpt_image=cfg.use_gpt_image,
          notion_blacklist_getter=context_store.get_used_unsplash_ids if context_store.is_available() else None,
          notion_blacklist_setter=context_store.mark_unsplash_used if context_store.is_available() else None,
      )

    Шаг 3 — Переписать run_pipeline():
    Сохранить: LinkedIn token expiry warning. Добавить логику ContentRouter как описано в interfaces.
    Ключевые точки:
    - recent_types = notion.get_recent_post_types(30)
    - entries = context_store.get_unused_entries(10) if context_store.is_available() else []
    - post_type = router.choose_post_type(recent_types, has_fresh_context=bool(entries))
    - Ветки if/elif/else для personal vs news
    - Image selection: gpt-image-1 bytes для impersonal, profile_photo ИЛИ gpt-image-1 для personal; Unsplash как fallback
    - record = notion.create_draft(..., post_type=post_type)

    Шаг 4 — Добавить on_new_image async функцию в build_pipeline() (рядом с on_publish, on_skip):
    async def on_new_image(record: PostRecord):
        [логика из interfaces выше]
        [Обновить Notion через notion.update_status с image_url]
        [send_preview с обновлённым record]

    Шаг 5 — Добавить on_context_entry:
    async def on_context_entry(category: str, text: str):
        context_store.add_entry(category=category, text=text)
        logger.info("Context entry saved: category=%s", category)

    Шаг 6 — Добавить on_new_image и on_context_entry в return из build_pipeline() и в _refs dict.

    Шаг 7 — Обновить PostApprovalBot инициализацию в main():
    Добавить параметры: on_new_image=on_new_image_func, on_context_entry=on_context_entry_func

    Шаг 8 — Добавить questionnaire scheduler job в main() ПОСЛЕ post scheduler:
    if cfg.questionnaire_schedule:
        raw_q_days = [d.strip() for d in cfg.questionnaire_schedule.split(",") if d.strip()]
        q_days = ",".join(DOW_MAP[d] for d in raw_q_days if d in DOW_MAP)
        if q_days:
            scheduler.add_job(bot.send_questionnaire, CronTrigger(day_of_week=q_days, hour=7, minute=0))
            logger.info("Questionnaire scheduled: %s at 07:00 UTC", cfg.questionnaire_schedule)
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import ast, sys
with open('main.py') as f:
    src = f.read()
# Проверить ключевые импорты
assert 'from modules.context_store import ContextStore' in src
assert 'from modules.content_router import ContentRouter' in src
# Проверить что ContentRouter используется
assert 'router = ContentRouter()' in src
# Проверить questionnaire scheduler
assert 'send_questionnaire' in src
assert 'questionnaire_schedule' in src
# Синтаксическая проверка
try:
    ast.parse(src)
    print('main.py syntax OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    sys.exit(1)
print('main.py structure checks OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - main.py парсится без SyntaxError (ast.parse)
    - ContentRouter и ContextStore импортированы и используются в build_pipeline()
    - run_pipeline() содержит вызов router.choose_post_type()
    - run_pipeline() содержит ветку для needs_fresh_context (generate_personal path)
    - on_new_image функция определена и подключена в _refs
    - scheduler содержит job для send_questionnaire
    - PostApprovalBot получает on_new_image и on_context_entry
    - Существующий on_publish/on_skip код не изменён (только добавлено post_type)
  </acceptance_criteria>
  <done>main.py обновлён: ContentRouter, ContextStore, ImageFetcher с Notion blacklist подключены; run_pipeline() использует smart rotation; questionnaire scheduler добавлен; on_new_image реализован</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Scheduler → bot.send_questionnaire() | внутренний вызов, нет внешнего триггера |
| on_context_entry text → ContextStore | текст из Telegram, обрезается до 2000 символов в ContextStore |
| image_bytes → LinkedIn | bytes от OpenAI, не исполняются |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-09-01 | Denial of Service | gpt-image-1 в run_pipeline ~25s | accept | pipeline не блокирует бота; Telegram approval уже async |
| T-09-02 | Information Disclosure | context entries в логах | mitigate | логировать только category, не text |
| T-09-03 | Tampering | context_db_id пустой → ContextStore no-op | accept | graceful degradation документирована |
| T-09-SC | Tampering | pip installs | accept | план не устанавливает новых зависимостей |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import ast
with open('/Users/nikitakrivoshey/projects/linkedin-agent/main.py') as f:
    src = f.read()

# Синтаксис
ast.parse(src)

# Ключевые компоненты
checks = [
    ('ContextStore import', 'from modules.context_store import ContextStore'),
    ('ContentRouter import', 'from modules.content_router import ContentRouter'),
    ('router usage', 'router = ContentRouter()'),
    ('choose_post_type', 'router.choose_post_type'),
    ('generate_personal', 'generate_personal'),
    ('send_questionnaire', 'send_questionnaire'),
    ('questionnaire_schedule', 'questionnaire_schedule'),
    ('on_new_image', 'on_new_image'),
    ('notion blacklist', 'notion_blacklist_getter'),
]
for name, pattern in checks:
    assert pattern in src, f'Missing: {name} ({pattern!r})'
    print(f'  OK: {name}')

print('PASS: main.py integration complete')
"
</verification>

<success_criteria>
- python -c "import main" выполняется без ImportError (при наличии .env с переменными)
- Scheduler содержит два job: run_pipeline (post schedule) + send_questionnaire (questionnaire schedule)
- build_pipeline() возвращает all callbacks включая on_new_image и on_context_entry
- Весь существующий approval flow (publish/skip/regenerate) работает
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-09-SUMMARY.md` when done
</output>
