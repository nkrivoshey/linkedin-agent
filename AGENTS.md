# Agents — LinkedIn Agent

> Этот файл описывает проект для всех AI-инструментов: Claude Code, Gemini CLI, и других.
> Читать при старте новой сессии.

## Проект
- **Название**: LinkedIn Agent
- **Цель**: Автоматический постинг на LinkedIn (личный бренд DA + продвижение Telegram AI Office) с апрувом через Telegram
- **Статус**: Railway не оплачен — локальная разработка. Готов к деплою.
- **Автор**: Никита Кривошей, Data Analyst, Dubai UAE

## Стек
Python 3.11 · Anthropic API (claude-sonnet-4-6) · python-telegram-bot · APScheduler · NewsAPI · RSS · Unsplash · LinkedIn API v2 · Notion · Railway

## Ключевые правила (обязательно соблюдать)
- Публикация только после Telegram-апрува — никогда в обход
- LinkedIn API v2 (REST), NO Selenium
- LLM: `claude-sonnet-4-6` — не менять без явного запроса
- Расписание: APScheduler, не cron системы
- Конфиг: `config.py` с `load_config()`, не `os.getenv()` напрямую в модулях

## Claude Code (главный строитель)
- Пишет производственный Python-код: модули, тесты, конфиги
- Следует стандартам из `.claude/rules/coding.md`
- Создаёт планы в `.claude/plans/` на русском языке
- Читает `CLAUDE.md` при старте каждой сессии
- Не трогает расписание APScheduler без тестирования
- Перед деплоем — `pytest tests/ -v -m "not real_api"`

## Gemini CLI (research + review)
- Исследует актуальные изменения LinkedIn API, лимиты постинга
- Делает code review Python-кода: APScheduler конфиги, retry логика, async паттерны
- Проверяет Anthropic SDK usage на соответствие последним best practices
- Анализирует engagement тактики для LinkedIn: форматы постов, хэштеги, время публикации
- Результаты research пишет в `.claude/plans/` или HANDOFF.md
- НЕ пишет production код

## Взаимодействие агентов

```
Claude Code → реализация фичи
    → пишет в HANDOFF.md: что сделано, что нужно проверить
Gemini CLI → review реализации
    → пишет в HANDOFF.md: findings, рекомендации
Claude Code → применяет рекомендации
```

## HANDOFF протокол
При передаче между агентами — обновить HANDOFF.md:

```
### [Claude Code | Gemini] YYYY-MM-DD — краткая тема
**Что сделано:** ...
**Ключевые решения:** ...
**Следующий шаг:** ...
**Изменённые файлы:** ...
```

## Файлы для чтения при старте
1. `CLAUDE.md` — цель, архитектура, правила, команды
2. `HANDOFF.md` — последние 5 записей лога
3. `config.py` — все параметры конфигурации
4. `data/profile.md` — профиль автора (нужен для понимания контента)
