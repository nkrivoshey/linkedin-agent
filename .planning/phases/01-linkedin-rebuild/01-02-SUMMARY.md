---
plan: 01-02-images
status: complete
phase: 01-linkedin-rebuild
---

## Summary

Полностью переписан `modules/images.py`. Новый `ImageFetcher` реализует трёхуровневую стратегию изображений.

## What Was Built

- **Tier 1 — gpt-image-1**: `fetch_gpt_image()` — генерирует сцены без лиц (bytes) для типов `news_insight`/`learning`. Промпты из `SCENE_PROMPTS` (5 штук, только силуэты/вид сзади). Контролируется `Config.use_gpt_image`.
- **Tier 2 — Unsplash**: `fetch_profile_photo()` — реальные фото с ротацией для `personal_story`/`achievement`/`hot_take`. Фильтрует по in-memory blacklist.
- **Tier 3 — Fallback**: `FALLBACK_IMAGE_URL` — хардкод-URL как последний рубеж.
- **Обратная совместимость**: `fetch()` и `mark_used()` сохранены для существующих вызывающих.
- **Notion blacklist callbacks**: `notion_blacklist_getter`/`setter` для будущей Notion-персистентности (D-01 locked decision — пока in-memory).
- **Удалено**: `use_dalle`, `_fetch_dalle` — заменены gpt-image-1.

## Key Files

- `modules/images.py` — полная перезапись (283 добавлений, 52 удалений)

## Decisions

- Blacklist in-memory per arch decision (Notion persistence — будущее улучшение)
- `get_image()` возвращает `(bytes, None)` для gpt-image-1 или `(None, url_str)` для Unsplash/fallback
- Все gpt-image-1 промпты содержат "no human faces visible, person from behind or silhouette"

## Self-Check: PASSED

Все задачи плана выполнены. Интерфейс обратно совместим.
