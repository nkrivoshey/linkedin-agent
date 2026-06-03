# HANDOFF — LinkedIn Agent

> Лог передачи между Claude Code и Gemini CLI.
> Последние 5 записей. Старше → архивировать в `.claude/plans/archive/`.

---

### Claude Code 2026-06-03 — эталонная документация
**Что сделано:** Создана полная документация проекта. Обновлён CLAUDE.md (цель, контекст, метрики, стек с точными версиями, архитектура с data flow, правила, команды, таблица env vars). Созданы README.md (публичный), AGENTS.md, GEMINI.md, HANDOFF.md. Восстановлены `.claude/agents/` (11 агентов из шаблона) и `.claude/rules/` (coding.md, git.md, testing.md).

**Ключевые решения:**
- CLAUDE.md содержит полный data flow (APScheduler → NewsCollector → ContentGenerator → ImageFetcher → NotionLogger → TelegramBot → LinkedInPublisher)
- Явно зафиксировано правило: NO Selenium, только LinkedIn API v2
- Все 20 env vars задокументированы с типами и дефолтами

**Следующий шаг:** Активировать Railway деплой когда оплачен сервер. Перед деплоем — `pytest tests/ -v -m "not real_api"` и проверить актуальность LinkedIn access token.

**Изменённые файлы:**
- `CLAUDE.md` (обновлён)
- `README.md` (создан)
- `AGENTS.md` (создан)
- `GEMINI.md` (создан)
- `HANDOFF.md` (создан)
- `.claude/agents/*.md` (11 файлов восстановлены из шаблона)
- `.claude/rules/coding.md` (создан)
- `.claude/rules/git.md` (создан)
- `.claude/rules/testing.md` (создан)

---

<!-- Формат новой записи:
### [Claude Code | Gemini] YYYY-MM-DD — тема
**Что сделано:** ...
**Ключевые решения:** ...
**Следующий шаг:** ...
**Изменённые файлы:** ...
-->
