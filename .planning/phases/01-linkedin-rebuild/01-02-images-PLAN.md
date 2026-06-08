---
phase: 01-linkedin-rebuild
plan: 2
type: execute
wave: 1
depends_on: []
files_modified:
  - modules/images.py
autonomous: true
requirements:
  - REQ-01
  - REQ-02
  - REQ-12

must_haves:
  truths:
    - "gpt-image-1 генерирует изображение без лиц и возвращает bytes"
    - "Unsplash fallback работает когда gpt-image-1 недоступен"
    - "Использованные Unsplash ID хранятся в Notion, не в памяти"
    - "Реальные фото из data/profile_photos/ ротируются для personal/achievement/hot_take"
  artifacts:
    - path: "modules/images.py"
      provides: "ImageFetcher с gpt-image-1, photo rotation, Unsplash fallback"
      contains: "fetch_gpt_image"
    - path: "modules/images.py"
      provides: "Notion-persisted blacklist для Unsplash"
      contains: "used_unsplash_ids"
  key_links:
    - from: "modules/images.py ImageFetcher.fetch()"
      to: "modules/linkedin.py _upload_image_bytes()"
      via: "возвращает bytes для post_type in ['news_insight','learning']"
      pattern: "fetch_gpt_image|fetch_profile_photo"
    - from: "modules/images.py"
      to: "modules/notion.py"
      via: "get_used_unsplash_ids() / mark_unsplash_used()"
      pattern: "used_unsplash_ids|notion_blacklist"
---

<objective>
Полностью переписать modules/images.py. Новый ImageFetcher реализует трёхуровневую стратегию изображений:
1. Для news_insight/learning — gpt-image-1 (сцены без лиц, возвращает bytes)
2. Для personal_story/achievement/hot_take — реальные фото из data/profile_photos/ (ротация)
3. Unsplash fallback для любого типа при сбое, с Notion-persisted blacklist

Purpose: Это ядро REQ-01 (изображения не повторяются), REQ-02 (gpt-image-1 без лиц), REQ-12 (Unsplash blacklist в Notion). Модуль независим от Wave 2 — работает без context_store.

Output: Переписанный modules/images.py с обратно-совместимым интерфейсом.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/ROADMAP.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-CONTEXT.md
@/Users/nikitakrivoshey/projects/linkedin-agent/.planning/spikes/001-gpt-image-1-api/README.md
</context>

<interfaces>
<!-- Текущий интерфейс ImageFetcher (из modules/images.py) -->
<!-- Новый ImageFetcher должен сохранить совместимость по вызовам из main.py -->

Текущие вызовы из main.py (сохранить совместимость):
  images.fetch_candidates(keywords=[...])  → list[dict]  (для Unsplash пути)
  images.mark_used(image_url, candidates)  → None

Новые вызовы (добавить):
  images.fetch_gpt_image(post_type: str, post_text: str) → bytes | None
  images.fetch_profile_photo(post_type: str) → str | None   # путь к файлу
  images.get_unsplash_blacklist() → set[str]                 # делегирует в notion
  images.mark_unsplash_used_notion(image_id: str) → None     # делегирует в notion

gpt-image-1 параметры (из spike 001):
  client.images.generate(model="gpt-image-1", prompt=..., quality="medium", size="1536x1024", response_format="b64_json")
  Результат: base64.b64decode(response.data[0].b64_json) → bytes (PNG ~2MB)

Промпты по типу поста (из 01-CONTEXT.md specifics):
  news_insight: "data analyst workspace from above, dual monitors showing dashboards and charts, coffee cup, notebook, Dubai skyline through window at dusk, photorealistic"
  personal_story: "person from behind sitting at desk in modern office, contemplative posture, window with city view, soft lighting"
  hot_take: "person's hands typing rapidly on laptop keyboard, dark room with single monitor glow, data visualizations visible on screen"
  achievement: "silhouette of person standing at floor-to-ceiling window overlooking Dubai skyline at night, triumphant stance"
  learning: "open technical book with laptop beside it, handwritten notes visible, coffee cup, clean minimal desk"

PROFILE_PHOTOS_DIR = Path(__file__).parent.parent / "data" / "profile_photos"
Поддерживаемые типы для фото: ["personal_story", "achievement", "hot_take"]
Поддерживаемые типы для gpt-image-1: ["news_insight", "learning"]
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Переписать ImageFetcher с тремя стратегиями</name>
  <files>modules/images.py</files>
  <read_first>
    - modules/images.py — прочитать полностью перед заменой
    - .planning/spikes/001-gpt-image-1-api/README.md — технические параметры API
    - .planning/phases/01-linkedin-rebuild/01-CONTEXT.md — секция "gpt-image-1 No-Face Scene Prompts"
  </read_first>
  <action>
    Переписать modules/images.py полностью. Новый класс ImageFetcher принимает:
    - unsplash_key: str
    - openai_key: str = ""
    - use_gpt_image: bool = True
    - notion_blacklist_getter: Callable[[], set[str]] | None = None  — callback для получения blacklist из Notion
    - notion_blacklist_setter: Callable[[str], None] | None = None   — callback для записи ID в Notion

    Константы:
    - SCENE_PROMPTS: dict[str, str] с пятью ключами по типу поста (из specifics в CONTEXT.md)
    - PERSONAL_POST_TYPES = frozenset({"personal_story", "achievement", "hot_take"})
    - GPT_IMAGE_TYPES = frozenset({"news_insight", "learning"})
    - PROFILE_PHOTOS_DIR = Path(__file__).parent.parent / "data" / "profile_photos"
    - FALLBACK_QUERIES остаётся для Unsplash

    Метод fetch_gpt_image(post_type: str, post_text: str) -> bytes | None:
    - Если not use_gpt_image или not openai_key: вернуть None
    - prompt = SCENE_PROMPTS.get(post_type, SCENE_PROMPTS["news_insight"])
    - Вызвать openai.OpenAI(api_key=openai_key).images.generate(model="gpt-image-1", prompt=prompt, quality="medium", size="1536x1024", response_format="b64_json")
    - Вернуть base64.b64decode(response.data[0].b64_json)
    - При любом исключении: logger.exception("gpt-image-1 failed"), вернуть None

    Метод fetch_profile_photo(post_type: str) -> str | None:
    - Если post_type not in PERSONAL_POST_TYPES: вернуть None
    - Если PROFILE_PHOTOS_DIR не существует: logger.warning, вернуть None
    - Собрать список файлов с расширениями .jpg, .jpeg, .png, .webp
    - Если пусто: logger.warning("No profile photos in data/profile_photos/"), вернуть None
    - Вернуть str(random.choice(photos))

    Метод fetch_candidates(keywords: list[str]) -> list[dict]:
    - Получить blacklist: _get_blacklist() → вызов notion_blacklist_getter() если задан, иначе self._used_ids (in-memory fallback для backward compat)
    - Логика из текущего _search_raw + цикл по queries — оставить как есть
    - Фильтровать кандидатов: исключать id из blacklist
    - Вернуть list[dict] с полями id, url, description, alt_description, tags

    Метод mark_used(image_url: str, candidates: list[dict]) -> None:
    - Найти id по url в candidates
    - Если notion_blacklist_setter задан: вызвать notion_blacklist_setter(id)
    - Иначе: self._used_ids.add(id) (in-memory fallback)

    Приватный метод _search_raw(query, page, per_page) — перенести без изменений из текущего кода.

    Удалить: _fetch_dalle, use_dalle из конструктора.
    Оставить: _used_ids: set[str] как fallback когда Notion недоступен.
  </action>
  <verify>
    <automated>cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.images import ImageFetcher
f = ImageFetcher(unsplash_key='test', openai_key='', use_gpt_image=False)
assert hasattr(f, 'fetch_gpt_image')
assert hasattr(f, 'fetch_profile_photo')
assert hasattr(f, 'fetch_candidates')
assert hasattr(f, 'mark_used')
print('ImageFetcher interface OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - ImageFetcher(unsplash_key="x", openai_key="", use_gpt_image=False) создаётся без ошибок
    - fetch_gpt_image("news_insight", "") возвращает None когда openai_key="" (нет API вызова)
    - fetch_profile_photo("personal_story") возвращает None если PROFILE_PHOTOS_DIR не существует
    - fetch_candidates([]) не вызывает исключений (возвращает [] если Unsplash недоступен)
    - mark_used(url, []) не вызывает исключений
    - Нет упоминаний use_dalle и _fetch_dalle в новом коде
    - Код импортируется: python -c "from modules.images import ImageFetcher"
  </acceptance_criteria>
  <done>modules/images.py переписан; gpt-image-1 (bytes output), profile photo rotation, Unsplash fallback с Notion-callback интерфейсом — всё реализовано</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| OpenAI API → bytes | base64 декодируется из ответа OpenAI; контент не исполняется |
| Unsplash API → URL | внешний URL записывается в Notion; не исполняется |
| data/profile_photos/ → LinkedIn | локальные файлы читаются и отправляются напрямую |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | openai_api_key в памяти | accept | ключ живёт в Railway env, не логируется |
| T-02-02 | Denial of Service | gpt-image-1 timeout 20-41s | mitigate | try/except возвращает None, pipeline деградирует до Unsplash |
| T-02-03 | Tampering | profile_photos path traversal | mitigate | использовать Path.glob("*.jpg") — только файлы из фиксированной директории |
| T-02-SC | Tampering | pip installs | accept | план не устанавливает новых зависимостей (openai уже в requirements.txt) |
</threat_model>

<verification>
cd /Users/nikitakrivoshey/projects/linkedin-agent && python -c "
from modules.images import ImageFetcher, SCENE_PROMPTS, PERSONAL_POST_TYPES, GPT_IMAGE_TYPES
assert 'news_insight' in SCENE_PROMPTS
assert 'learning' in SCENE_PROMPTS
assert 'personal_story' in PERSONAL_POST_TYPES
assert 'news_insight' in GPT_IMAGE_TYPES
f = ImageFetcher(unsplash_key='test', openai_key='', use_gpt_image=False)
result = f.fetch_gpt_image('news_insight', 'test post')
assert result is None, 'Should return None without openai_key'
photo = f.fetch_profile_photo('news_insight')
assert photo is None, 'news_insight is not a personal post type'
print('PASS: images module OK')
"
</verification>

<success_criteria>
- gpt-image-1 вызывается для news_insight и learning с правильными параметрами (quality=medium, size=1536x1024)
- Реальные фото ротируются для personal_story/achievement/hot_take
- Unsplash blacklist делегируется через callback в Notion (fallback: in-memory)
- Нет краша при отсутствии profile_photos директории
- Все методы импортируются без ошибок
</success_criteria>

<output>
Create `/Users/nikitakrivoshey/projects/linkedin-agent/.planning/phases/01-linkedin-rebuild/01-02-SUMMARY.md` when done
</output>
