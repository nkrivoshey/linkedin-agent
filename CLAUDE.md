# LinkedIn Agent

## Цель
Автоматический постинг на LinkedIn по двум направлениям:
1. **Личный бренд Data Analyst** — демонстрация экспертизы (Python, SQL, DWH, Power BI) для получения job offers из EU / UAE / USA
2. **Продвижение Telegram AI Office** — привлечение технических партнёров и клиентов к SaaS-продукту с AI-ботами

## Контекст
- **Автор**: Никита Кривошей, Data Analyst @ Metropolitan Premium Properties, Dubai UAE
- **Аудитория #1**: Hiring Managers и рекрутеры из EU/UAE/USA в сфере Data & Analytics
- **Аудитория #2**: Технические основатели и product people — потенциальные партнёры Telegram AI Office
- **Апрув-флоу**: Агент генерирует пост → отправляет превью в Telegram → кнопки Approve / Edit / Reject → только после Approve публикует в LinkedIn
- **Статус**: Railway не оплачен — работает локально; готов к деплою

## Метрики успеха
- Engagement rate > 5% на каждый пост (лайки + комментарии / показы)
- Рост connections от target-компаний: +10 в месяц из EU/UAE/USA
- 0 фактических ошибок в тексте постов (галлюцинации LLM)
- 0 дублей — система проверяет уже опубликованные URL через Notion
- LinkedIn token не протухает (предупреждение за 5 дней до истечения)

## Стек
```
Python 3.11
anthropic>=0.96.0          — генерация контента (claude-sonnet-4-6)
python-telegram-bot==21.6  — апрув-бот
APScheduler==3.10.4        — расписание постов
newsapi-python==0.2.7      — поиск новостей
feedparser==6.0.11         — RSS fallback
notion-client==2.2.1       — логирование постов
requests==2.31.0           — LinkedIn API, Unsplash
python-dotenv==1.0.1       — переменные окружения
openai>=1.12.0             — опциональная генерация изображений (DALL-E)
pytz==2024.1               — работа с таймзонами
```

## Архитектура

### Структура файлов
```
linkedin-agent/
├── main.py                    — точка входа, APScheduler, сборка pipeline
├── config.py                  — конфигурация через dataclass + os.getenv
├── Procfile                   — Railway: worker: python main.py
├── railway.toml               — Railway конфиг
├── runtime.txt                — python-3.11.x
├── requirements.txt
├── data/
│   └── profile.md             — профиль Никиты для LLM промптов
├── modules/
│   ├── generator.py           — ContentGenerator (Anthropic claude-sonnet-4-6)
│   ├── news.py                — NewsCollector (NewsAPI + RSS)
│   ├── images.py              — ImageFetcher (Unsplash + опц. DALL-E)
│   ├── linkedin.py            — LinkedInPublisher (LinkedIn API v2)
│   ├── notion.py              — NotionLogger (база данных постов)
│   ├── telegram_bot.py        — PostApprovalBot (апрув-флоу)
│   └── models.py              — Pydantic-модели: Article, PostRecord
└── tests/
    ├── test_generator.py
    ├── test_images.py
    ├── test_linkedin.py
    ├── test_news.py
    ├── test_notion.py
    └── test_telegram_bot.py
```

### Data Flow
```
APScheduler (cron)
    │
    ▼
NewsCollector.fetch()
    │  NewsAPI → RSS fallback
    │  фильтр по уже опубликованным URL (Notion)
    ▼
ContentGenerator.generate()
    │  claude-sonnet-4-6 + profile.md + тема статьи
    ▼
ImageFetcher.fetch_candidates()
    │  Unsplash по ключевым словам
    │  → ContentGenerator.pick_best_image() (LLM выбирает)
    ▼
NotionLogger.create_draft()     ← статус "Pending"
    │
    ▼
PostApprovalBot.send_preview()
    │  Telegram: текст + изображение + кнопки
    │
    ├─ Approve → LinkedInPublisher.publish()
    │              → NotionLogger.update_status("Published")
    │
    ├─ Edit   → пользователь редактирует → повторный апрув
    │
    └─ Reject → NotionLogger.update_status("Rejected")
```

## Правила
- **NO Selenium** — только LinkedIn API v2 (REST). Selenium не упоминать, не предлагать
- **Апрув обязателен** — публикация без Telegram-апрува запрещена (исключение: DRY_RUN=true)
- **LLM**: только `claude-sonnet-4-6` для генерации контента. Смена модели — через config
- **Расписание**: APScheduler CronTrigger, дни в `POST_SCHEDULE`, время в `POST_TIME_UTC`
- **Дубли**: перед генерацией получать список опубликованных URL из Notion
- **Токен LinkedIn**: проверять срок истечения при каждом запуске pipeline, предупреждать в Telegram
- **DRY_RUN=true**: генерирует и логирует, но не публикует и не отправляет в Telegram

## Команды

```bash
# Установка
pip install -r requirements.txt

# Тесты (без реальных API-вызовов)
pytest tests/ -v -m "not real_api"

# Тесты с реальными API (требуют .env)
pytest tests/ -v -m real_api

# Запуск локально
python main.py

# Деплой на Railway
git push origin main  # Railway автоматически деплоит из main

# Проверка деплоя
railway logs --tail
```

## Переменные окружения

| Переменная | Обязательная | Default | Описание |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | да | — | Ключ Anthropic API для генерации контента (claude-sonnet-4-6) |
| `NEWSAPI_KEY` | да | — | Ключ NewsAPI для поиска свежих новостей |
| `UNSPLASH_ACCESS_KEY` | да | — | Ключ Unsplash для подбора изображений |
| `TELEGRAM_BOT_TOKEN` | да | — | Токен Telegram-бота для апрув-флоу |
| `TELEGRAM_CHAT_ID` | да | — | ID чата/пользователя куда слать апрув |
| `LINKEDIN_ACCESS_TOKEN` | да | — | OAuth2 access token LinkedIn API |
| `LINKEDIN_PERSON_URN` | да | — | URN профиля (`urn:li:person:XXXX`) |
| `NOTION_TOKEN` | да | — | Integration token Notion для логирования |
| `NOTION_DATABASE_ID` | да | — | ID базы данных Notion с логом постов |
| `OPENAI_API_KEY` | нет | `""` | Ключ OpenAI (только если USE_DALLE=true) |
| `HUGGINGFACE_API_KEY` | нет | `""` | Ключ HuggingFace (резервная генерация) |
| `USE_DALLE` | нет | `false` | Использовать DALL-E для генерации изображений |
| `POST_SCHEDULE` | нет | `MON,WED,FRI` | Дни публикации через запятую |
| `POST_TIME_UTC` | нет | `05:00` | Время публикации в UTC (HH:MM) |
| `TIMEZONE` | нет | `Asia/Dubai` | Таймзона для логов (UTC+4) |
| `DRY_RUN` | нет | `false` | Тестовый режим: без публикации и Telegram |
| `CONTENT_MEMORY_LOOKBACK` | нет | `30` | Дней назад для проверки дублей |
| `ENGAGEMENT_THRESHOLD` | нет | `0.05` | Минимальный engagement rate (5%) |
| `ENABLE_NETWORK_AGENT` | нет | `false` | Агент для расширения сети контактов |
| `LINKEDIN_TOKEN_ISSUED_AT` | нет | `""` | Дата выдачи токена (ISO format) для трекинга срока |
| `OBSIDIAN_VAULT_PATH` | нет | `""` | Путь к Obsidian vault (локальное логирование) |

## API / Интеграции
- **LinkedIn API v2** — публикация постов (`/ugcPosts`), проверка токена
- **Anthropic API** — генерация текста поста (claude-sonnet-4-6), выбор изображения
- **NewsAPI** — поиск актуальных новостей по темам (Data, AI, Analytics)
- **RSS feeds** — fallback если NewsAPI не даёт результатов
- **Unsplash API** — поиск и выбор изображений по ключевым словам
- **OpenAI API** — опциональная генерация изображений через DALL-E 3
- **Notion API** — база данных постов: черновики, статусы, ссылки на опубликованное
- **Telegram Bot API** — апрув-флоу: превью + inline-кнопки Approve/Edit/Reject
