---
phase: 01-linkedin-rebuild
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - config.py
  - modules/models.py
autonomous: true
requirements:
  - REQ-07
  - REQ-09
  - REQ-10

must_haves:
  truths:
    - "Config содержит USE_GPT_IMAGE, NOTION_CONTEXT_DB_ID, QUESTIONNAIRE_SCHEDULE"
    - "PostRecord содержит поле post_type"
    - "ANTHROPIC_AUTH_TOKEN фикс применён в ContentGenerator.__init__()"
  artifacts:
    - path: "config.py"
      provides: "Config dataclass + load_config() с тремя новыми полями"
      contains: "use_gpt_image"
    - path: "modules/models.py"
      provides: "PostRecord с полем post_type"
      contains: "post_type"
  key_links:
    - from: "config.py"
      to: "main.py"
      via: "load_config()"
      pattern: "use_gpt_image|notion_context_db_id|questionnaire_schedule"
    - from: "modules/models.py"
      to: "modules/notion.py"
      via: "PostRecord.post_type"
      pattern: "post_type"
---

<objective>
Добавить три новых конфигурационных переменных в Config dataclass и поле post_type в PostRecord. Это фундаментальные изменения, от которых зависят все остальные планы фазы.

Purpose: Без новых полей Config невозможно инициализировать ImageFetcher (gpt-image-1), ContextStore (Notion context DB) и ContentRouter. Без post_type в PostRecord невозможно отслеживать тип поста в Notion.

Output: Обновлённые config.py и modules/models.py.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Добавить новые поля в Config dataclass</name>
  <files>config.py</files>
  <read_first>
    - config.py — прочитать полностью перед изменением
  </read_first>
  <action>
    Прочитать config.py. В dataclass Config добавить три новых поля ПОСЛЕ существующих полей:
    - use_gpt_image: bool — включает gpt-image-1 как основной источник изображений
    - notion_context_db_id: str — ID Notion DB для хранения контекстных записей квестionnaire
    - questionnaire_schedule: str — дни недели для квестионнера (например "TUE,FRI")

    В функции load_config() добавить соответствующие строки:
    - use_gpt_image читать из env USE_GPT_IMAGE, default "true", преобразовать .lower() == "true"
    - notion_context_db_id читать из env NOTION_CONTEXT_DB_ID через os.getenv(key, ""), НЕ через _require (поле опциональное)
    - questionnaire_schedule читать из env QUESTIONNAIRE_SCHEDULE, default "TUE,FRI"

    Удалить поля use_dalle, huggingface_api_key, obsidian_vault_path из dataclass и из load_config() — они помечены как deferred в CONTEXT.md и не используются в новой архитектуре. openai_api_key ОСТАВИТЬ — используется для gpt-image-1.

    Не менять порядок существующих полей; не трогать _require().
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "from config import load_config; print('Config OK')"</automated>
  </verify>
  <acceptance_criteria>
    - python -c "from config import Config; c = Config.__dataclass_fields__; assert 'use_gpt_image' in c and 'notion_context_db_id' in c and 'questionnaire_schedule' in c"
    - Поля use_dalle, huggingface_api_key, obsidian_vault_path отсутствуют в Config
    - load_config() импортируется без ошибок
  </acceptance_criteria>
  <done>Config dataclass содержит use_gpt_image (bool), notion_context_db_id (str), questionnaire_schedule (str); устаревшие поля удалены</done>
</task>

<task type="auto">
  <name>Task 2: Добавить post_type в PostRecord</name>
  <files>modules/models.py</files>
  <read_first>
    - modules/models.py — прочитать полностью перед изменением
  </read_first>
  <action>
    Прочитать modules/models.py. В dataclass PostRecord добавить одно новое поле ПОСЛЕ поля publish_date:
    - post_type: str = "" — тип поста: "news_insight", "personal_story", "hot_take", "achievement", "learning"

    Значение по умолчанию "" (пустая строка) обеспечивает обратную совместимость — существующий код, не передающий post_type, продолжит работать.

    Не трогать Article dataclass. Не менять существующие поля PostRecord.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "from modules.models import PostRecord; r = PostRecord(notion_page_id='x', title='t', status='Draft', source_url='', post_text='', image_url='', topics=[]); assert r.post_type == ''; print('PostRecord OK')"</automated>
  </verify>
  <acceptance_criteria>
    - PostRecord(notion_page_id='x', title='t', status='Draft', source_url='', post_text='', image_url='', topics=[]).post_type == ""
    - PostRecord с явным post_type="news_insight" создаётся без ошибок
    - Существующий код в main.py, создающий PostRecord без post_type, продолжает работать
  </acceptance_criteria>
  <done>modules/models.py содержит PostRecord.post_type: str = ""; существующий код не сломан</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| env → Config | Все переменные окружения читаются через os.getenv; пользовательский ввод не попадает напрямую |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | notion_context_db_id в env | accept | секрет уровня Railway env vars, не попадает в логи |
| T-01-SC | Tampering | npm/pip installs | accept | план не устанавливает новых зависимостей |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from config import Config, load_config
from modules.models import PostRecord, Article
fields = Config.__dataclass_fields__
assert 'use_gpt_image' in fields, 'use_gpt_image missing'
assert 'notion_context_db_id' in fields, 'notion_context_db_id missing'
assert 'questionnaire_schedule' in fields, 'questionnaire_schedule missing'
assert 'use_dalle' not in fields, 'use_dalle still present'
r = PostRecord(notion_page_id='x', title='t', status='Draft', source_url='', post_text='', image_url='', topics=[])
assert hasattr(r, 'post_type'), 'post_type missing from PostRecord'
print('PASS: config + models foundation OK')
"
</verification>

<success_criteria>
- Config содержит use_gpt_image, notion_context_db_id, questionnaire_schedule
- PostRecord содержит post_type: str = ""
- Все существующие тесты и импорты проходят
- python -c "from config import load_config; from modules.models import PostRecord" выполняется без ошибок
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-01-SUMMARY.md` when done
</output>
