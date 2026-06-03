# LinkedIn Agent

Автоматический постинг на LinkedIn с апрувом через Telegram.

Генерирует контент на основе свежих новостей, отправляет превью в Telegram для ручного апрува, публикует только после подтверждения. Работает по расписанию (APScheduler), логирует всё в Notion.

## Направления контента

- **Личный бренд Data Analyst** — посты о Python, SQL, DWH, Power BI, карьере в данных. Аудитория: hiring managers из EU / UAE / USA
- **Telegram AI Office** — продвижение SaaS-продукта с AI-ботами. Аудитория: технические основатели, потенциальные партнёры

## Быстрый старт

### 1. Установка

```bash
git clone https://github.com/nkrivoshey/linkedin-agent
cd linkedin-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Заполни обязательные переменные (см. секцию Env Vars ниже)
```

### 3. Запуск

```bash
# Тестовый режим — без публикации, без Telegram
DRY_RUN=true python main.py

# Боевой режим
python main.py
```

## Апрув-флоу

```
APScheduler запускает pipeline
    ↓
Агент ищет свежие новости (NewsAPI + RSS)
    ↓
Claude генерирует текст поста (claude-sonnet-4-6)
    ↓
Unsplash подбирает изображение
    ↓
Telegram-бот отправляет превью
    ↓
[Approve] → публикация в LinkedIn + Notion лог
[Edit]    → пользователь правит текст → повторный апрув
[Reject]  → пост отклонён, статус "Rejected" в Notion
```

Публикация без апрува невозможна.

## Архитектура

```
main.py                 — точка входа, APScheduler
config.py               — конфигурация из env
data/profile.md         — профиль автора для LLM промптов
modules/
  generator.py          — генерация контента (Anthropic API)
  news.py               — сбор новостей (NewsAPI + RSS)
  images.py             — подбор изображений (Unsplash / DALL-E)
  linkedin.py           — публикация (LinkedIn API v2)
  notion.py             — логирование (Notion Database)
  telegram_bot.py       — апрув-бот (python-telegram-bot)
  models.py             — модели данных (Article, PostRecord)
tests/                  — pytest тесты с mock внешних API
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `ANTHROPIC_API_KEY` | да | Anthropic API — генерация постов |
| `NEWSAPI_KEY` | да | NewsAPI — поиск новостей |
| `UNSPLASH_ACCESS_KEY` | да | Unsplash — изображения |
| `TELEGRAM_BOT_TOKEN` | да | Telegram-бот для апрува |
| `TELEGRAM_CHAT_ID` | да | ID чата с апрувами |
| `LINKEDIN_ACCESS_TOKEN` | да | OAuth2 токен LinkedIn API |
| `LINKEDIN_PERSON_URN` | да | URN профиля LinkedIn |
| `NOTION_TOKEN` | да | Notion integration token |
| `NOTION_DATABASE_ID` | да | ID базы данных с постами |
| `POST_SCHEDULE` | нет | Дни публикации (default: `MON,WED,FRI`) |
| `POST_TIME_UTC` | нет | Время публикации UTC (default: `05:00`) |
| `DRY_RUN` | нет | `true` — без реальной публикации |
| `USE_DALLE` | нет | `true` — DALL-E вместо Unsplash |
| `OPENAI_API_KEY` | нет | Нужен если `USE_DALLE=true` |

Полная таблица — в [CLAUDE.md](./CLAUDE.md).

## Тесты

```bash
# Без реальных API (для CI)
pytest tests/ -v -m "not real_api"

# С реальными API (требует .env)
pytest tests/ -v -m real_api
```

## Деплой на Railway

### Требования
- Аккаунт Railway с оплаченным планом
- Все переменные окружения в Railway Variables Panel

### Шаги

```bash
# 1. Установить Railway CLI
npm install -g @railway/cli

# 2. Авторизация
railway login

# 3. Привязать проект
railway link

# 4. Задать переменные окружения
railway variables set ANTHROPIC_API_KEY=sk-ant-...
# (задать все обязательные переменные)

# 5. Деплой
git push origin main
# Railway автоматически деплоит из main через nixpacks
```

### Procfile
```
worker: python main.py
```

Сервис запускается как worker (без HTTP-сервера) — APScheduler работает в фоне.

### Проверка деплоя
```bash
railway logs --tail
```

Успешный запуск: `Pipeline scheduled: MON,WED,FRI at 05:00 UTC`

## LinkedIn Token

LinkedIn OAuth2 токен действует 60 дней. Агент отслеживает срок и предупреждает в Telegram за 5 дней до истечения. Обновить: [developers.linkedin.com](https://developers.linkedin.com).

## Стек

Python 3.11 · Anthropic API (claude-sonnet-4-6) · python-telegram-bot · APScheduler · NewsAPI · feedparser · Unsplash · Notion · LinkedIn API v2 · Railway
