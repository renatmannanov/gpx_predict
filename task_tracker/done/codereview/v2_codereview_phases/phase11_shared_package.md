# Phase 11: Shared Package (Опционально)

> **Сложность:** 🟡 Средняя
> **Время:** 1-2 часа
> **Строк:** ~150
> **Файлов:** 20
> **Зависимости:** Phase 10
> **Статус:** ✅ **ЗАВЕРШЕНО** (2026-01-28) - Вариант A

---

## Проблема

Дублирование кода между backend и bot:

```
backend/app/shared/formatters.py  → format_time_hours(), format_pace()
bot/utils/formatters.py           → format_time(), format_pace() (почти копия)
```

**Небольшие отличия:**
- Backend: `f"{m}мин"`
- Bot: `f"{m:02d}мин"` (с leading zero)

---

## Почему опционально?

1. **Дублирование некритично** - ~80 строк, функции простые
2. **Разный деплой** - если bot и backend деплоятся отдельно, shared усложняет
3. **Разные требования** - bot может хотеть немного другой формат

---

## Варианты решения

### Вариант A: Bot импортирует из backend

**Плюсы:** Минимум изменений
**Минусы:** Нужен PYTHONPATH, coupling между компонентами

```python
# bot/utils/formatters.py
from app.shared.formatters import format_time_hours as format_time
```

### Вариант B: Отдельный shared package

**Плюсы:** Чистая архитектура
**Минусы:** Больше работы, отдельный package

```
packages/
  shared/
    __init__.py
    formatters.py

# pyproject.toml или setup.py для shared package
```

### Вариант C: Оставить как есть

**Плюсы:** Нет работы, независимость компонентов
**Минусы:** Дублирование кода

---

## Если выбрали Вариант A

### Чеклист

1. [ ] Убедиться что backend в PYTHONPATH бота
2. [ ] Обновить `bot/utils/formatters.py`:

```python
"""
Bot formatters - re-export from shared with bot-specific adjustments.
"""
from app.shared.formatters import (
    format_time_hours,
    format_pace as _format_pace,
    format_distance_km as format_distance,
    format_elevation,
)

# Re-export with bot naming
format_time = format_time_hours

# Override if bot needs different format
def format_pace(pace_min_km: float | None) -> str:
    """Format pace without 'мин/км' suffix for compact display."""
    if pace_min_km is None:
        return "—"
    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

__all__ = ["format_time", "format_pace", "format_distance", "format_elevation"]
```

3. [ ] Проверить все handlers что используют formatters
4. [ ] Тесты бота

---

## Если выбрали Вариант B

### Структура

```
gpx-predictor/
├── packages/
│   └── gpx_shared/
│       ├── __init__.py
│       ├── formatters.py
│       └── constants.py
├── backend/
│   └── ...
├── bot/
│   └── ...
└── pyproject.toml  # или setup.py
```

### Чеклист

1. [ ] Создать `packages/gpx_shared/`
2. [ ] Перенести общий код:
   - [ ] `formatters.py`
   - [ ] Возможно `constants.py` (ActivityType и т.д.)
3. [ ] Настроить package:

```toml
# pyproject.toml
[tool.poetry]
packages = [
    { include = "gpx_shared", from = "packages" }
]
```

4. [ ] Обновить импорты в backend:
```python
from gpx_shared.formatters import format_time_hours
```

5. [ ] Обновить импорты в bot:
```python
from gpx_shared.formatters import format_time_hours as format_time
```

6. [ ] Удалить дубликаты:
   - [ ] `backend/app/shared/formatters.py` → делегирует к gpx_shared
   - [ ] `bot/utils/formatters.py` → делегирует к gpx_shared

7. [ ] Тесты

---

## Что можно вынести в shared

| Файл | Что | Приоритет |
|------|-----|-----------|
| `formatters.py` | format_time, format_pace, format_distance | Средний |
| `constants.py` | ActivityType enum | Низкий (уже в backend) |

---

## Рекомендация

**Для этого проекта рекомендую Вариант C (оставить как есть):**

1. Дублирование минимальное (~80 строк)
2. Функции простые и стабильные
3. Bot и backend могут деплоиться независимо
4. Не стоит усложнять ради 80 строк

**Когда стоит делать shared package:**
- Дублирование > 500 строк
- Сложная логика которая часто меняется
- Нужна синхронизация между компонентами

---

## Результат (если сделать)

- ✅ Один источник правды для форматтеров
- ✅ Изменения в одном месте
- ⚠️ Coupling между компонентами
- ⚠️ Сложнее деплой

---

## Что было сделано (Вариант A)

**Выбран Вариант A** — Bot импортирует из backend.

### Изменения:

1. **backend/app/shared/formatters.py** — добавлен комментарий "SINGLE SOURCE OF TRUTH"
2. **bot/utils/formatters.py** — переписан:
   - Импортирует `format_time_hours`, `format_distance_km`, `format_elevation` из backend
   - Re-export с bot naming: `format_time = format_time_hours`
   - Override `format_pace()` — без суффикса "мин/км" для компактности

### Архитектура:

```
backend/app/shared/formatters.py  ← SINGLE SOURCE OF TRUTH
    ↓
bot/utils/formatters.py           ← imports + overrides
    ↓
bot/handlers/*.py                 ← uses bot formatters
```

### Что унифицировано:
- `format_time` — из backend
- `format_distance` — из backend
- `format_elevation` — из backend

### Что переопределено в bot:
- `format_pace` — без суффикса "мин/км" для компактности в Telegram

---

*Phase 11 of v2.1 cleanup - COMPLETED*
