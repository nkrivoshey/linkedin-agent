---
phase: 01-linkedin-rebuild
plan: 4
type: execute
wave: 2
depends_on:
  - plan-1
files_modified:
  - modules/context_store.py
  - modules/questionnaire.py
autonomous: true
requirements:
  - REQ-04
  - REQ-05

must_haves:
  truths:
    - "ContextStore читает/пишет записи в Notion NOTION_CONTEXT_DB_ID"
    - "Если NOTION_CONTEXT_DB_ID не задан — ContextStore gracefully пропускает все операции"
    - "QuestionnaireState машина состояний работает без конфликтов с BotState"
    - "CATEGORIES содержит 4 категории: work, life, learning, opinion"
  artifacts:
    - path: "modules/context_store.py"
      provides: "ContextStore — read/write/mark_used для Notion context DB"
      contains: "class ContextStore"
    - path: "modules/questionnaire.py"
      provides: "QuestionnaireState + CATEGORIES + callback constants"
      contains: "class QuestionnaireState"
  key_links:
    - from: "modules/questionnaire.py QuestionnaireState"
      to: "modules/telegram_bot.py PostApprovalBot"
      via: "QuestionnaireState экземпляр создаётся внутри PostApprovalBot (план 8)"
      pattern: "QuestionnaireState|CATEGORIES"
    - from: "modules/context_store.py ContextStore"
      to: "modules/generator.py ContentGenerator.generate_personal()"
      via: "get_unused_entries() → generator"
      pattern: "get_unused_entries|mark_used"
---

<objective>
Создать два новых модуля:
1. modules/context_store.py — Notion CRUD для базы данных личного контекста
2. modules/questionnaire.py — стейт-машина квестионнера (перенос из spike 002)

Purpose: Эти модули — строительные блоки Wave 2. ContextStore нужен generator.py (генерация персональных постов) и telegram_bot.py (запись ответов квестионнера). Questionnaire — для telegram_bot.py.

Output: Два новых файла, готовых к подключению в Wave 3.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/spikes/002-proactive-questionnaire/questionnaire_spike.py
</context>

<interfaces>
<!-- Схема Notion Context DB (из CONTEXT.md specifics) -->
Notion DB properties:
  Title (title)          — первые 100 символов текста
  Category (select)      — "work" | "life" | "learning" | "opinion"
  Text (rich_text)       — полный текст ответа пользователя
  Created (date)         — дата создания (YYYY-MM-DD)
  Used (checkbox)        — False при создании, True после использования в посте

<!-- ContextStore публичный интерфейс -->
class ContextStore:
    def __init__(self, token: str, context_db_id: str): ...
    def is_available(self) -> bool:                                         # context_db_id != ""
    def add_entry(self, category: str, text: str) -> str | None:           # → page_id или None
    def get_unused_entries(self, limit: int = 10) -> list[dict]:            # [{"id", "category", "text"}]
    def mark_entry_used(self, page_id: str) -> None:
    def get_used_unsplash_ids(self) -> set[str]:                            # для ImageFetcher blacklist
    def mark_unsplash_used(self, image_id: str) -> None:
    # Unsplash blacklist хранить в отдельном посте-странице в том же context_db_id
    # или в отдельном поле — на усмотрение исполнителя (Claude's Discretion в CONTEXT.md)

<!-- QuestionnaireState (из spike 002, перенести точно) -->
CATEGORIES dict и QuestionnaireState dataclass — скопировать из questionnaire_spike.py строки 29-85
CALLBACK_TO_CATEGORY, CALLBACK_DONE, CALLBACK_ADD_MORE — тоже перенести

Публичный интерфейс questionnaire.py:
  CATEGORIES: dict[str, dict]   # label, question, callback
  CALLBACK_TO_CATEGORY: dict[str, str]
  CALLBACK_DONE: str = "ctx_done"
  CALLBACK_ADD_MORE: str = "ctx_more"
  class QuestionnaireState: start(), category_selected(cat), response_received(text) → dict, finish()
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Создать modules/context_store.py</name>
  <files>modules/context_store.py</files>
  <read_first>
    - modules/notion.py — посмотреть паттерн работы с Notion client
    - .planning/phases/01-linkedin-rebuild/01-CONTEXT.md — секция "Notion Context DB Schema"
    - .planning/spikes/002-proactive-questionnaire/questionnaire_spike.py — test_notion_context_write() строки 172-214
  </read_first>
  <action>
    Создать новый файл modules/context_store.py.

    Импорты: logging, datetime, notion_client.Client (опциональный импорт с try/except).

    Класс ContextStore:
    - __init__(self, token: str, context_db_id: str): сохранить поля, создать self.client = Client(auth=token) если context_db_id непустой иначе self.client = None
    - is_available(self) -> bool: вернуть bool(self.context_db_id и self.client)

    Метод add_entry(category: str, text: str) -> str | None:
    - Если not is_available(): вернуть None
    - client.pages.create с parent={"database_id": self.context_db_id}, properties:
      Title: title с text[:100]
      Category: select name=category
      Text: rich_text с полным text (обрезать до 2000 символов)
      Created: date с datetime.utcnow().date().isoformat()
      Used: checkbox False
    - Вернуть page["id"]
    - При Exception: logger.exception("ContextStore.add_entry failed"), вернуть None

    Метод get_unused_entries(limit: int = 10) -> list[dict]:
    - Если not is_available(): вернуть []
    - client.databases.query с filter={"property": "Used", "checkbox": {"equals": False}}, page_size=limit
    - Для каждой страницы извлечь id, Category.select.name, Text.rich_text[0].text.content
    - Вернуть list[{"id": ..., "category": ..., "text": ...}]
    - При Exception: logger.exception, вернуть []

    Метод mark_entry_used(page_id: str) -> None:
    - Если not is_available(): return
    - client.pages.update(page_id=page_id, properties={"Used": {"checkbox": True}})
    - При Exception: logger.exception("ContextStore.mark_entry_used failed")

    Методы get_used_unsplash_ids() и mark_unsplash_used() для Notion-persisted Unsplash blacklist:
    - Хранить blacklist как единственную страницу в context_db_id с Title="__unsplash_blacklist__"
    - get_used_unsplash_ids(): найти страницу по Title через databases.query с filter Title contains "__unsplash_blacklist__"; вернуть set из comma-separated IDs из поля Text; при ошибке или отсутствии страницы вернуть set()
    - mark_unsplash_used(image_id): найти или создать страницу __unsplash_blacklist__; добавить image_id к существующим; обновить Text поле; при ошибке только логировать

    Все внешние вызовы Notion обернуть в try/except.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.context_store import ContextStore
cs = ContextStore(token='fake', context_db_id='')
assert not cs.is_available()
assert cs.get_unused_entries() == []
assert cs.add_entry('work', 'test') is None
assert cs.get_used_unsplash_ids() == set()
print('ContextStore graceful degradation OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - ContextStore(token="x", context_db_id="") → is_available() == False
    - При is_available()==False все методы возвращают None/[]/set() без исключений
    - add_entry() создаёт страницу в Notion с правильной схемой (проверить логикой кода)
    - get_unused_entries() фильтрует по Used==False
    - mark_entry_used() устанавливает Used=True
    - Unsplash blacklist читается/пишется через страницу с Title="__unsplash_blacklist__"
  </acceptance_criteria>
  <done>modules/context_store.py создан; ContextStore реализован; graceful degradation при отсутствии NOTION_CONTEXT_DB_ID</done>
</task>

<task type="auto">
  <name>Task 2: Создать modules/questionnaire.py</name>
  <files>modules/questionnaire.py</files>
  <read_first>
    - .planning/spikes/002-proactive-questionnaire/questionnaire_spike.py — строки 29-85 (CATEGORIES, QuestionnaireState)
  </read_first>
  <action>
    Создать новый файл modules/questionnaire.py.

    Перенести из questionnaire_spike.py строки 29-85 точно:
    - Импорты: dataclasses (dataclass, field), datetime
    - CATEGORIES dict (4 ключа: work, life, learning, opinion) с label, question, callback
    - CALLBACK_TO_CATEGORY = {v["callback"]: k for k, v in CATEGORIES.items()}
    - CALLBACK_DONE = "ctx_done"
    - CALLBACK_ADD_MORE = "ctx_more"
    - Класс QuestionnaireState (dataclass) с методами start(), category_selected(), response_received(), finish()

    Дополнительно добавить вспомогательную функцию category_keyboard() -> InlineKeyboardMarkup:
    - Создаёт keyboard с кнопками для каждой категории плюс кнопку "✅ Done" с callback_data=CALLBACK_DONE
    - Импортирует InlineKeyboardButton, InlineKeyboardMarkup из telegram

    Не включать логику Telegram bot (handlers, Application) — только стейт и константы.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.questionnaire import QuestionnaireState, CATEGORIES, CALLBACK_TO_CATEGORY, CALLBACK_DONE
assert len(CATEGORIES) == 4
assert set(CATEGORIES.keys()) == {'work', 'life', 'learning', 'opinion'}
s = QuestionnaireState()
assert not s.active
s.start()
assert s.active
s.category_selected('work')
assert s.waiting_for_response
entry = s.response_received('test text')
assert entry['category'] == 'work'
assert entry['text'] == 'test text'
s.finish()
assert not s.active
print('QuestionnaireState OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - CATEGORIES содержит ключи "work", "life", "learning", "opinion"
    - Каждая категория имеет поля label, question, callback
    - QuestionnaireState: start() → active=True; category_selected("work") → waiting_for_response=True; response_received("text") → возвращает dict с category и text; finish() → active=False
    - QuestionnaireState и BotState независимы (никаких импортов из telegram_bot)
    - python -c "from modules.questionnaire import QuestionnaireState, CATEGORIES, category_keyboard" без ошибок
  </acceptance_criteria>
  <done>modules/questionnaire.py создан; QuestionnaireState и CATEGORIES перенесены из spike; category_keyboard() добавлена</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Telegram text → ContextStore | Свободный ввод пользователя записывается в Notion |
| ContextStore → Notion API | Все данные обрезаются до лимитов Notion (title:100, text:2000) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01 | Tampering | Telegram free text → Notion | mitigate | text обрезается до 2000 символов перед записью |
| T-04-02 | Information Disclosure | NOTION_CONTEXT_DB_ID в Config | accept | в Railway env, не логируется |
| T-04-03 | Denial of Service | Notion API unavailable | mitigate | все методы ContextStore обёрнуты в try/except; graceful degradation |
| T-04-SC | Tampering | pip installs | accept | notion_client уже в requirements.txt |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.context_store import ContextStore
from modules.questionnaire import QuestionnaireState, CATEGORIES, CALLBACK_DONE

# ContextStore graceful
cs = ContextStore(token='t', context_db_id='')
assert not cs.is_available()
assert cs.get_unused_entries() == []
assert cs.get_used_unsplash_ids() == set()

# QuestionnaireState machine
s = QuestionnaireState()
s.start()
s.category_selected('opinion')
e = s.response_received('BI tools are overrated')
assert e['category'] == 'opinion'
s.finish()
assert not s.active

print('PASS: context_store + questionnaire OK')
"
</verification>

<success_criteria>
- modules/context_store.py и modules/questionnaire.py созданы
- ContextStore работает без NOTION_CONTEXT_DB_ID (graceful no-op)
- QuestionnaireState прошла все state transitions без ошибок
- Нет конфликтов с BotState из telegram_bot.py
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-04-SUMMARY.md` when done
</output>
