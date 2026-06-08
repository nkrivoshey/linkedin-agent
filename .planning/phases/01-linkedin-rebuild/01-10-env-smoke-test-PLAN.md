---
phase: 01-linkedin-rebuild
plan: 10
type: execute
wave: 4
depends_on:
  - 01-09-main
files_modified:
  - .env.example
autonomous: false
requirements:
  - REQ-01
  - REQ-02
  - REQ-03
  - REQ-04
  - REQ-05
  - REQ-06
  - REQ-07
  - REQ-08
  - REQ-09
  - REQ-10
  - REQ-11
  - REQ-12

must_haves:
  truths:
    - ".env.example содержит все новые переменные с комментариями"
    - "python main.py импортируется без ошибок с минимальным .env"
    - "ContentRouter правильно выбирает тип при тестовом запуске"
    - "QuestionnaireState машина проходит все переходы без ошибок"
  artifacts:
    - path: ".env.example"
      provides: "Документация всех env переменных включая новые"
      contains: "USE_GPT_IMAGE"
  key_links:
    - from: ".env.example"
      to: "config.py load_config()"
      via: "env vars"
      pattern: "USE_GPT_IMAGE|NOTION_CONTEXT_DB_ID|QUESTIONNAIRE_SCHEDULE"
---

<objective>
Обновить .env.example и провести финальную smoke-проверку всей системы.

Purpose: REQ-01 через REQ-12 — финальная верификация. Убедиться что все переменные документированы, импорты работают, ключевые модули инициализируются корректно.

Output: Обновлённый .env.example + checkpoint-верификация у пользователя.
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
  <name>Task 1: Обновить .env.example</name>
  <files>.env.example</files>
  <read_first>
    - .env.example — прочитать текущее содержимое если файл существует
    - config.py — получить полный список переменных из load_config()
  </read_first>
  <action>
    Прочитать .env.example (если существует). Прочитать config.py.

    Создать или перезаписать .env.example со всеми переменными из load_config().
    Удалить устаревшие переменные: USE_DALLE, HUGGINGFACE_API_KEY, OBSIDIAN_VAULT_PATH.

    Структура .env.example (каждая переменная с комментарием):

    # === Required ===
    ANTHROPIC_API_KEY=                    # Claude API key
    NEWSAPI_KEY=                          # NewsAPI.org key
    UNSPLASH_ACCESS_KEY=                  # Unsplash API key
    TELEGRAM_BOT_TOKEN=                   # Telegram bot token from BotFather
    TELEGRAM_CHAT_ID=                     # Your personal Telegram chat ID
    LINKEDIN_ACCESS_TOKEN=                # LinkedIn OAuth 2.0 access token
    LINKEDIN_PERSON_URN=                  # urn:li:person:XXXX
    NOTION_TOKEN=                         # Notion integration token
    NOTION_DATABASE_ID=                   # Notion posts database ID

    # === Images ===
    OPENAI_API_KEY=                       # Required for gpt-image-1
    USE_GPT_IMAGE=true                    # true=gpt-image-1 primary; false=Unsplash only

    # === Personal Context ===
    NOTION_CONTEXT_DB_ID=                 # Notion context DB ID (for questionnaire storage)
                                          # Schema: Title(title), Category(select), Text(rich_text), Created(date), Used(checkbox)

    # === Scheduling ===
    POST_SCHEDULE=MON,WED,FRI            # Days to post (MON,TUE,WED,THU,FRI,SAT,SUN)
    POST_TIME_UTC=05:00                  # Posting time in UTC (HH:MM)
    QUESTIONNAIRE_SCHEDULE=TUE,FRI       # Days to send questionnaire (leave empty to disable)

    # === Optional ===
    LINKEDIN_TOKEN_ISSUED_AT=            # YYYY-MM-DD, for token expiry warning
    TIMEZONE=Asia/Dubai                  # Local timezone (informational only)
    DRY_RUN=false                        # true=simulate without publishing
    CONTENT_MEMORY_LOOKBACK=30           # N past posts checked for dedup
    ENGAGEMENT_THRESHOLD=0.05            # (unused in v2)
    ENABLE_NETWORK_AGENT=false           # (unused in v2)
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && grep -c "USE_GPT_IMAGE" .env.example && grep -c "NOTION_CONTEXT_DB_ID" .env.example && grep -c "QUESTIONNAIRE_SCHEDULE" .env.example && echo ".env.example OK"</automated>
  </verify>
  <acceptance_criteria>
    - .env.example содержит USE_GPT_IMAGE
    - .env.example содержит NOTION_CONTEXT_DB_ID с комментарием о схеме Notion DB
    - .env.example содержит QUESTIONNAIRE_SCHEDULE
    - USE_DALLE, HUGGINGFACE_API_KEY, OBSIDIAN_VAULT_PATH отсутствуют
    - Все ключи из Config dataclass присутствуют в .env.example
  </acceptance_criteria>
  <done>.env.example обновлён: все новые переменные добавлены с комментариями, устаревшие удалены</done>
</task>

<task type="auto">
  <name>Task 2: Автоматическая smoke-проверка всех модулей</name>
  <files></files>
  <read_first>
    (нет файлов — только запуск проверок)
  </read_first>
  <action>
    Запустить серию проверок которые не требуют реальных API ключей.

    Проверка 1 — все модули импортируются:
    python -c "from modules.images import ImageFetcher, SCENE_PROMPTS, PERSONAL_POST_TYPES, GPT_IMAGE_TYPES; from modules.linkedin import LinkedInPublisher; from modules.context_store import ContextStore; from modules.questionnaire import QuestionnaireState, CATEGORIES, category_keyboard; from modules.content_router import ContentRouter, needs_fresh_context; from modules.generator import ContentGenerator, PERSONAL_POST_PROMPT_V3; from modules.notion import NotionLogger; from modules.telegram_bot import PostApprovalBot, CALLBACK_NEW_IMAGE; from config import Config; print('ALL IMPORTS OK')"

    Проверка 2 — Config содержит новые поля:
    python -c "from config import Config; f = Config.__dataclass_fields__; assert all(k in f for k in ['use_gpt_image','notion_context_db_id','questionnaire_schedule']); print('Config fields OK')"

    Проверка 3 — ContentRouter forced rotation:
    python -c "from modules.content_router import ContentRouter; r = ContentRouter(); results = set(r.choose_post_type(['news_insight','news_insight']) for _ in range(30)); assert 'news_insight' not in results; print('Rotation OK')"

    Проверка 4 — QuestionnaireState:
    python -c "from modules.questionnaire import QuestionnaireState; s = QuestionnaireState(); s.start(); s.category_selected('work'); e = s.response_received('test'); s.finish(); assert e['category']=='work' and not s.active; print('QState OK')"

    Проверка 5 — ContextStore graceful no-op:
    python -c "from modules.context_store import ContextStore; cs = ContextStore('t',''); assert not cs.is_available(); assert cs.get_unused_entries()==[]; print('ContextStore graceful OK')"

    Проверка 6 — ANTHROPIC_AUTH_TOKEN fix:
    python -c "import os; os.environ['ANTHROPIC_AUTH_TOKEN']=''; from modules.generator import ContentGenerator; print('AUTH_TOKEN fix OK')"

    Если любая проверка упала — исправить соответствующий модуль перед переходом к checkpoint.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.images import ImageFetcher, SCENE_PROMPTS, PERSONAL_POST_TYPES, GPT_IMAGE_TYPES
from modules.linkedin import LinkedInPublisher
from modules.context_store import ContextStore
from modules.questionnaire import QuestionnaireState, CATEGORIES, category_keyboard
from modules.content_router import ContentRouter, needs_fresh_context
from modules.generator import ContentGenerator, PERSONAL_POST_PROMPT_V3
from modules.notion import NotionLogger
from modules.telegram_bot import PostApprovalBot, CALLBACK_NEW_IMAGE
from config import Config
print('ALL IMPORTS OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - Все 8 импортов выше проходят без ошибок
    - ContentRouter forced rotation работает
    - QuestionnaireState state machine работает
    - ContextStore возвращает пустые значения без NOTION_CONTEXT_DB_ID
    - ANTHROPIC_AUTH_TOKEN fix не вызывает исключений
  </acceptance_criteria>
  <done>Все модули импортируются; ключевые поведения верифицированы без API вызовов</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Полный rebuild LinkedIn агента в living account. Все 10 планов выполнены:
    - Plan 1: Config + PostRecord (use_gpt_image, notion_context_db_id, post_type)
    - Plan 2: ImageFetcher (gpt-image-1, profile photos, Unsplash+Notion blacklist)
    - Plan 3: LinkedInPublisher._upload_image_bytes()
    - Plan 4: ContextStore + QuestionnaireState
    - Plan 5: ContentRouter с weighted rotation
    - Plan 6: ContentGenerator V3 + generate_personal() + AUTH_TOKEN fix
    - Plan 7: NotionLogger + post_type tracking + get_recent_post_types()
    - Plan 8: telegram_bot + 🖼️ New Image кнопка + questionnaire integration
    - Plan 9: main.py — финальная интеграция всех модулей
    - Plan 10: .env.example обновлён
  </what-built>
  <how-to-verify>
    1. Убедиться что Notion Context DB создана с правильной схемой:
       Title (title), Category (select: work/life/learning/opinion), Text (rich_text), Created (date), Used (checkbox)
       Скопировать ID базы в NOTION_CONTEXT_DB_ID в .env

    2. Убедиться что Post Type (select) поле добавлено в Notion Posts DB

    3. Положить 2-3 фото в data/profile_photos/ (jpg/png)

    4. Запустить dry run:
       DRY_RUN=true python main.py
       Ожидаемое: бот стартует, scheduler показывает два job в логах

    5. В Telegram: отправить /generate
       Ожидаемое: preview с 4 кнопками (Publish, Regenerate, Skip, 🖼️ New Image)

    6. Нажать 🖼️ New Image
       Ожидаемое: "🔄 Generating new image..." → новое фото в превью (без смены текста)

    7. Отправить /generate снова, нажать Publish
       Ожидаемое: пост опубликован, в Notion появилось поле Post Type

    8. Для теста квестионнера:
       QUESTIONNAIRE_SCHEDULE=MON (текущий день) и POST_TIME_UTC на ближайшие 2 минуты → перезапустить
       Ожидаемое: бот присылает "🧠 Weekly Context Update" с кнопками категорий
  </how-to-verify>
  <resume-signal>Type "approved" если всё работает, или опишите проблему для диагностики</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .env.example → репозиторий | только шаблон без реальных значений |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-10-01 | Information Disclosure | .env.example с примерами | accept | только шаблон; реальные значения в .env (gitignored) |
| T-10-SC | Tampering | pip installs | accept | план не устанавливает новых зависимостей |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
# Финальная комплексная проверка
from modules.images import ImageFetcher, SCENE_PROMPTS
from modules.linkedin import LinkedInPublisher
from modules.context_store import ContextStore
from modules.questionnaire import QuestionnaireState, CATEGORIES
from modules.content_router import ContentRouter, needs_fresh_context
from modules.generator import ContentGenerator, PERSONAL_POST_PROMPT_V3
from modules.notion import NotionLogger
from modules.telegram_bot import PostApprovalBot, CALLBACK_NEW_IMAGE, APPROVAL_KEYBOARD
from config import Config
import inspect

# Config fields
f = Config.__dataclass_fields__
assert 'use_gpt_image' in f and 'notion_context_db_id' in f and 'questionnaire_schedule' in f
assert 'use_dalle' not in f

# Keyboard
kb = APPROVAL_KEYBOARD.inline_keyboard
assert len(kb) == 2 and kb[1][0].callback_data == 'new_image'

# V3 prompt
assert 'OpenToWork' in PERSONAL_POST_PROMPT_V3

# Router
r = ContentRouter()
for _ in range(20):
    t = r.choose_post_type(['news_insight', 'news_insight'])
    assert t != 'news_insight'

print('PASS: All phase 01 checks passed')
"
</verification>

<success_criteria>
- Все автоматические проверки пройдены
- .env.example документирует все 3 новые переменные
- DRY_RUN=true python main.py запускается без ошибок
- Пользователь подтверждает корректную работу approval flow с 4 кнопками
- Пользователь подтверждает что 🖼️ New Image меняет только изображение
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-10-SUMMARY.md` when done
</output>
