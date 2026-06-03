# Gemini Context — LinkedIn Agent

## Роль Gemini в этом проекте
Research, code review, анализ внешних API. НЕ пишет production код.

## Проект
Автоматический постинг на LinkedIn: генерация контента через claude-sonnet-4-6, апрув через Telegram-бот, публикация через LinkedIn API v2. Два направления: личный бренд Data Analyst и продвижение Telegram AI Office.

## Стек
Python 3.11 · Anthropic SDK (>=0.96.0) · python-telegram-bot 21.6 · APScheduler 3.10.4 · LinkedIn API v2 · Notion API · Unsplash API · NewsAPI

## Приоритетные темы для research

### LinkedIn API
- Актуальные лимиты на частоту публикаций (posts per day/week)
- Изменения в `/ugcPosts` endpoint (v2 → v202x)
- OAuth2 token refresh flow — как продлить без re-auth
- Поддержка изображений в постах: форматы, размеры, API для загрузки (`/assets`)
- Статус устаревания endpoints (deprecation notices)

### Engagement best practices (2024-2025)
- Оптимальное время публикации для аудитории EU/UAE/USA
- Форматы контента с наибольшим охватом (текст vs изображение vs карусель)
- Длина поста: оптимальный диапазон символов
- Хэштеги: количество, стратегия выбора
- Hook-формулы для Data Analyst / AI аудитории

### Anthropic SDK
- Prompt caching: применимость для повторяющихся системных промптов (profile.md)
- claude-sonnet-4-6 vs более новые модели: разница в качестве контента
- Structured outputs / tool use для извлечения ключевых слов из статей
- Rate limits и retry best practices

### APScheduler
- AsyncIOScheduler vs BackgroundScheduler в контексте Railway worker
- Graceful shutdown при SIGTERM (Railway рестарт)
- Персистентность джобов (jobstore) — нужна ли для этого проекта

## Code review фокус
При review Python-кода обращать внимание на:

1. **Retry логика** — есть ли экспоненциальный backoff при ошибках LinkedIn/Notion API?
2. **Async корректность** — нет ли blocking calls в async функциях?
3. **APScheduler конфиг** — правильный ли тип scheduler для Railway worker?
4. **Token expiry** — корректно ли вычисляется срок LinkedIn token?
5. **Error handling** — обрабатываются ли HTTP 429 (rate limit) от LinkedIn?
6. **Anthropic SDK** — используется ли prompt caching для системного промпта?
7. **Telegram bot** — корректен ли апрув-флоу при concurrent requests?

## Когда вызывать Gemini

- Перед изменением стратегии постинга (частота, формат, время)
- При обновлении LinkedIn API (новые endpoints, устаревшие методы)
- После выхода нового клиента Anthropic SDK (breaking changes)
- При падении engagement ниже 5% — анализ причин и рекомендации
- При подготовке к Railway деплою — проверка конфига и инфра-рисков
- Second opinion по архитектурным решениям (sync vs async, scheduler choice)

## Формат ответа Gemini
1. **Findings** — конкретные факты с источниками (не "возможно, стоит...")
2. **Рекомендации** — 2-3 actionable пункта для Claude Code
3. **Риски** — что может сломаться при изменении
4. Записать результаты в HANDOFF.md или `.claude/plans/`
