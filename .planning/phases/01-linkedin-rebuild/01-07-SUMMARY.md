---
phase: 01-linkedin-rebuild
plan: 7
subsystem: notion
tags: [notion, post_type, tracking, content_router]
dependency_graph:
  requires:
    - 01-01-config-models   # PostRecord.post_type field
    - 01-04-context-store-questionnaire
    - 01-05-content-router
  provides:
    - NotionLogger.get_recent_post_types()
    - post_type tracking in create_draft()
    - image_url update in update_status()
  affects:
    - modules/notion.py
tech_stack:
  added: []
  patterns:
    - Notion select property write (conditional on non-empty value)
    - Safe chained .get() for reading optional Notion properties
key_files:
  modified:
    - modules/notion.py
decisions:
  - "Post Type conditional write: пустой post_type не добавляется в properties (Notion не создаёт пустой select)"
  - "get_recent_post_types использует page_size=n без pagination (достаточно для 30 записей)"
  - "image_url в update_status обновляется только если значение непустое (нельзя обнулить URL через None)"
metrics:
  duration: "5m"
  completed_date: "2026-06-09"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 01 Plan 07: Notion post_type tracking and get_recent_post_types() Summary

Post Type select tracking in NotionLogger.create_draft() and get_recent_post_types() query for ContentRouter deduplication.

## What Was Built

`modules/notion.py` получил три изменения без ломания существующего API:

1. **create_draft() — параметр post_type: str = ""**
   - Сигнатура расширена: `create_draft(article, post_text, image_url, topics, post_type="")`
   - Properties dict собирается динамически; `"Post Type": {"select": {"name": post_type}}` добавляется только если `post_type` непустой
   - Возвращаемый `PostRecord` включает `post_type=post_type`

2. **update_status() — kwargs image_url**
   - Добавлена обработка: `if "image_url" in kwargs and kwargs["image_url"]: properties["Image URL"] = {"url": kwargs["image_url"]}`
   - Поддерживает сценарий "New Image" из плана 08 (Telegram-кнопка regenerate image)

3. **get_recent_post_types(n: int = 30) -> list[str]**
   - Запрос к posts DB: `sorts=[{"property": "Publish Date", "direction": "descending"}], page_size=n`
   - Безопасное извлечение: `page.get("properties", {}).get("Post Type", {}).get("select") or {}).get("name")`
   - Пропускает записи без Post Type (select = None)
   - При любом исключении логирует и возвращает `[]` — ContentRouter продолжает работу без истории

## Deviations from Plan

None - план выполнен точно как написан.

## Verification

```
PASS: notion module OK
```

Верификация из плана прошла:
- `create_draft` имеет параметр `post_type` с default `""`
- `get_recent_post_types` существует, содержит `"Post Type"`
- `update_status` содержит `image_url`

## Known Stubs

None.

## Threat Flags

None. Изменения затрагивают только запись/чтение Notion properties — новых сетевых endpoints или auth paths нет.

## Self-Check: PASSED

- modules/notion.py: файл существует и изменён
- Коммит 583e027: feat(01-07): add post_type tracking and get_recent_post_types() to NotionClient
