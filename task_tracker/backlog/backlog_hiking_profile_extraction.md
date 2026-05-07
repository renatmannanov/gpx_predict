# Backlog: Выделить UserHikingProfile в отдельный файл

**Дата:** 2026-02-14
**Приоритет:** Низкий (тех. долг)

## Контекст

`UserHikingProfile` живёт в общем файле `backend/app/models/user_profile.py`,
тогда как `UserRunProfile` уже выделен в `backend/app/models/user_run_profile.py`.

После добавления JSON полей, sample counts и хелпер-методов (hiking effort levels)
модель стала достаточно большой, чтобы заслуживать отдельного файла.

## Задачи

1. Создать `backend/app/models/user_hiking_profile.py`
2. Перенести `UserHikingProfile` из `user_profile.py`
3. Обновить re-export в `backend/app/models/__init__.py`
4. Обновить все импорты (grep по `UserHikingProfile`)
5. Проверить, что тесты проходят

## Зависимости

- Выполнять после завершения `hiking_effort_levels` (все 4 фазы)
