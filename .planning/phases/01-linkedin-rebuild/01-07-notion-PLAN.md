---
phase: 01-linkedin-rebuild
plan: 7
type: execute
wave: 3
depends_on:
  - 01-01-config-models
  - 01-04-context-store-questionnaire
  - 01-05-content-router
files_modified:
  - modules/notion.py
autonomous: true
requirements:
  - REQ-07
  - REQ-12

must_haves:
  truths:
    - "create_draft() сохраняет post_type в Notion"
    - "get_recent_post_types(n=30) возвращает список типов постов из истории"
    - "update_status() поддерживает параметр image_url для обновления image при regenerate"
  artifacts:
    - path: "modules/notion.py"
      provides: "NotionLogger с post_type tracking и get_recent_post_types()"
      contains: "get_recent_post_types"
  key_links:
    - from: "modules/notion.py create_draft()"
      to: "Notion posts DB"
      via: "Post Type select property"
      pattern: "Post Type|post_type"
    - from: "modules/notion.py get_recent_post_types()"
      to: "modules/content_router.py choose_post_type()"
      via: "list[str] recent_types"
      pattern: "get_recent_post_types"
---

<objective>
Обновить modules/notion.py: добавить post_type tracking в create_draft() и метод get_recent_post_types() для ContentRouter.

Purpose: REQ-07 (tracking post_type в каждом посте), REQ-12 (get_recent_post_types нужен ContentRouter для избегания повторений). Также update_status() нужно поддерживать обновление image_url для "🖼️ New Image" функции из плана 8.

Output: Обновлённый modules/notion.py с тремя добавлениями, без ломания существующего API.
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
<!-- Текущий интерфейс из modules/notion.py -->
class NotionLogger:
    def create_draft(self, article: Article, post_text: str, image_url: str, topics: list[str]) -> PostRecord
    def update_status(self, page_id: str, status: str, **kwargs) -> None
        kwargs supported: linkedin_url, feedback, generation_count, post_text
    def get_published_urls(self) -> set[str]

<!-- Необходимые изменения -->

create_draft() — добавить параметр post_type: str = "":
    В properties добавить:
    "Post Type": {"select": {"name": post_type}} if post_type else ничего не добавлять
    В возвращаемый PostRecord добавить: post_type=post_type

update_status() — добавить поддержку image_url в kwargs:
    if "image_url" in kwargs and kwargs["image_url"]:
        properties["Image URL"] = {"url": kwargs["image_url"]}

Новый метод get_recent_post_types(self, n: int = 30) -> list[str]:
    Запросить последние n постов из posts DB, отсортированных по Publish Date DESC
    Вернуть list[str] с значениями Post Type select (пропустить записи без Post Type)
    Вернуть [] при исключении

ВАЖНО: Поле "Post Type" должно быть select в Notion DB — создать вручную перед деплоем.
Если select значение отсутствует на странице → пропустить эту запись (не падать).
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Добавить post_type в create_draft() и get_recent_post_types()</name>
  <files>modules/notion.py</files>
  <read_first>
    - modules/notion.py — прочитать полностью перед изменением
    - modules/models.py — проверить что PostRecord.post_type существует (план 1)
  </read_first>
  <action>
    Прочитать modules/notion.py полностью.

    Изменение 1 — create_draft():
    - Изменить сигнатуру: добавить post_type: str = "" как последний позиционный параметр
    - В properties dict добавить ПЕРЕД закрывающей скобкой:
      если post_type непустой: добавить "Post Type": {"select": {"name": post_type}}
      если post_type пустой: не добавлять ключ "Post Type" (Notion примет без него)
    - В возвращаемом PostRecord добавить: post_type=post_type

    Изменение 2 — update_status():
    - В блоке обработки kwargs добавить:
      if "image_url" in kwargs and kwargs["image_url"]:
          properties["Image URL"] = {"url": kwargs["image_url"]}

    Изменение 3 — Добавить новый метод get_recent_post_types(self, n: int = 30) -> list[str]:
    - Запросить self.client.databases.query(
          database_id=self.database_id,
          sorts=[{"property": "Publish Date", "direction": "descending"}],
          page_size=n
      )
    - Для каждой страницы попытаться извлечь page["properties"]["Post Type"]["select"]["name"]
    - Использовать .get() цепочку чтобы не падать если поле отсутствует
    - Собрать непустые значения в список и вернуть
    - Обернуть в try/except: при исключении logger.exception("get_recent_post_types failed"), return []

    Существующий метод get_published_urls() не трогать.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import inspect
from modules.notion import NotionLogger
sig = inspect.signature(NotionLogger.create_draft)
params = sig.parameters
assert 'post_type' in params, 'post_type missing from create_draft'
assert hasattr(NotionLogger, 'get_recent_post_types'), 'get_recent_post_types missing'
src_update = inspect.getsource(NotionLogger.update_status)
assert 'image_url' in src_update, 'image_url not handled in update_status'
print('NotionLogger interface OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - create_draft(article, post_text, image_url, topics) работает без ошибок (обратная совместимость: post_type="" по умолчанию)
    - create_draft(article, post_text, image_url, topics, post_type="news_insight") включает Post Type в properties
    - update_status(page_id, "Pending", image_url="http://new-image.jpg") обновляет Image URL
    - get_recent_post_types() существует и возвращает list (даже пустой) без исключений
    - python -c "from modules.notion import NotionLogger" без ошибок
  </acceptance_criteria>
  <done>modules/notion.py обновлён: create_draft() принимает post_type, update_status() поддерживает image_url, get_recent_post_types() добавлен</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| post_type string → Notion select | строка из ContentRouter, только известные значения |
| image_url kwargs → Notion URL field | URL от ImageFetcher или OpenAI |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-01 | Tampering | post_type значение не из POST_TYPES | accept | Notion select создаст новый вариант если значение неизвестно; ContentRouter гарантирует валидные значения |
| T-07-02 | Denial of Service | Notion API unavailable | mitigate | get_recent_post_types() возвращает [] при ошибке; ContentRouter работает с пустым списком |
| T-07-SC | Tampering | pip installs | accept | notion_client уже в requirements.txt |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
import inspect
from modules.notion import NotionLogger

# create_draft имеет post_type
sig = inspect.signature(NotionLogger.create_draft)
assert 'post_type' in sig.parameters
assert sig.parameters['post_type'].default == ''

# get_recent_post_types существует
assert hasattr(NotionLogger, 'get_recent_post_types')
src = inspect.getsource(NotionLogger.get_recent_post_types)
assert 'Post Type' in src

# update_status поддерживает image_url
src_update = inspect.getsource(NotionLogger.update_status)
assert 'image_url' in src_update

print('PASS: notion module OK')
"
</verification>

<success_criteria>
- create_draft() сохраняет Post Type (select) в Notion для каждого поста
- get_recent_post_types() возвращает list[str] типов постов от новых к старым
- update_status() может обновить image_url (для "🖼️ New Image" кнопки)
- Обратная совместимость: существующие вызовы без post_type продолжают работать
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-07-SUMMARY.md` when done
</output>
