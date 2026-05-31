# LinkedIn Agent

## Цель
Автоматический постинг на LinkedIn: генерация контента через Gemini/Claude,
поиск новостей, публикация через Selenium. Railway deployment.

## Стек
Python 3.11 · Anthropic API · Selenium · Railway · pytest

## Архитектура
```
main.py (entrypoint, APScheduler)
  → modules/generator.py   (контент через LLM)
  → modules/news.py        (поиск новостей)
  → modules/linkedin.py    (публикация через Selenium)
  → modules/images.py      (генерация изображений)
  → modules/notion.py      (логирование в Notion)
config.py                  (Pydantic Settings)
```

## Команды
- Установка: `pip install -r requirements.txt`
- Тесты: `pytest tests/ -v`
- Запуск локально: `python main.py`
- Деплой: push в main → Railway автоматически

## Переменные окружения
Смотри `.env.example`. Обязательные: ANTHROPIC_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD.

## Правила
- Production бот, работает 24/7 на Railway
- Не менять schedule логику без тестирования
- LLM: использовать claude-sonnet-4-6 или gemini-flash
