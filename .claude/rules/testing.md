# Testing Rules

- pytest + pytest-asyncio для async
- Тесты в tests/ с mirror структурой src/
- Unit тесты: mock внешние API (не вызывать реально)
- Integration тесты: маркер `@pytest.mark.real_api`
- Перед деплоем: pytest без real_api маркера
