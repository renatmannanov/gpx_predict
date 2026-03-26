# Phase 12d: Complete Import Migration

> **Сложность:** 🟢 Низкая
> **Строк:** ~50
> **Файлов:** 18
> **Зависимости:** Phase 9-11 выполнены
> **Статус:** ✅ Выполнено (2026-01-28)

---

## Контекст

Phase 9 планировала обновить импорты в routes/ вместе с Phase 10, но это **не было сделано**.
В результате ~33 импорта всё ещё используют старые пути через re-export файлы.

---

## Проблема

```python
# Текущее состояние (через re-export)
from app.services.gpx_parser import GPXParserService
from app.repositories.gpx import GPXRepository
from app.models.user import User

# Правильное состояние (напрямую из features/)
from app.features.gpx import GPXParserService, GPXRepository
from app.features.users import User
```

---

## Замены по файлам

### 1. app/api/v1/routes/gpx.py (2 замены)

```python
# Было:
from app.services.gpx_parser import GPXParserService
from app.repositories.gpx import GPXRepository

# Станет:
from app.features.gpx import GPXParserService, GPXRepository
```

### 2. app/api/v1/routes/predict.py (2 замены)

```python
# Было:
from app.repositories.gpx import GPXRepository
from app.services.gpx_parser import GPXParserService

# Станет:
from app.features.gpx import GPXParserService, GPXRepository
```

### 3. app/api/v1/routes/strava.py (4 замены)

```python
# Было:
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity, StravaSyncStatus
from app.services.strava_sync import trigger_user_sync, get_sync_stats, StravaSyncService
from app.services.strava import (...)

# Станет:
from app.features.strava import StravaToken, StravaActivity, StravaSyncStatus, StravaClient
from app.features.strava.sync import trigger_user_sync, get_sync_stats, StravaSyncService
```

### 4. app/api/v1/routes/profiles.py (1 замена)

```python
# Было:
from app.services.strava_sync import StravaSyncService

# Станет:
from app.features.strava.sync import StravaSyncService
```

### 5. app/main.py (1 замена)

```python
# Было:
from app.services.strava_sync import background_sync

# Станет:
from app.features.strava.sync import background_sync
```

### 6. app/services/prediction.py (2 замены)

```python
# Было:
from app.repositories.gpx import GPXRepository
from app.services.gpx_parser import GPXParserService, GPXSegment

# Станет:
from app.features.gpx import GPXRepository, GPXParserService, GPXSegment
```

### 7. app/services/user_profile.py (2 замены)

```python
# Было:
from app.models.strava_activity import StravaActivity
from app.models.strava_activity import StravaActivitySplit  # внутри функций

# Станет:
from app.features.strava import StravaActivity, StravaActivitySplit
```

### 8. app/features/strava/client.py (2 замены)

```python
# Было:
from app.models.user import User  # внутри функций

# Станет:
from app.features.users import User
```

### 9. app/features/strava/sync/background.py (1 замена)

```python
# Было:
from app.models.user import User

# Станет:
from app.features.users import User
```

---

## Замены в scripts/ (опционально)

Скрипты не критичны, но для консистентности:

| Файл | Замены |
|------|--------|
| `test_trail_run_service.py` | `app.models.gpx` → `app.features.gpx` |
| `test_talgar_trail.py` | `app.models.gpx` → `app.features.gpx` |
| `test_talgar_trail_part2.py` | `app.models.gpx` → `app.features.gpx` |
| `recalculate_run_profile_smart.py` | `app.models.user`, `app.models.strava_activity` → `app.features.*` |
| `calculate_run_profile.py` | `app.models.user`, `app.models.strava_activity`, `app.models.gpx` → `app.features.*` |
| `analyze_segments.py` | `app.models.gpx` → `app.features.gpx` |
| `analyze_threshold_comparison.py` | `app.models.gpx` → `app.features.gpx` |
| `analyze_run_profile.py` | `app.models.user`, `app.models.strava_activity`, `app.models.gpx` → `app.features.*` |
| `analyze_specific_activities.py` | `app.models.user`, `app.models.strava_activity` → `app.features.*` |

---

## После обновления импортов

### Удалить re-export файлы (9 файлов):

```bash
rm backend/app/services/gpx_parser.py
rm backend/app/services/strava.py
rm backend/app/services/strava_sync.py
rm backend/app/repositories/gpx.py
rm backend/app/models/gpx.py
rm backend/app/models/notification.py
rm backend/app/models/strava_token.py
rm backend/app/models/user.py
rm backend/app/models/strava_activity.py
```

### Обновить __init__.py файлы (убрать re-exports):

- `app/services/__init__.py` — убрать re-exports для gpx_parser, strava, strava_sync
- `app/models/__init__.py` — убрать re-exports для gpx, notification, strava_*, user
- `app/repositories/__init__.py` — убрать re-export для gpx

---

## Проверка

```bash
# 1. Тесты
cd backend && python -m pytest tests/ -v

# 2. Импорт main
python -c "from app.main import app; print('OK')"

# 3. Проверить что старые пути НЕ работают
python -c "from app.services.gpx_parser import GPXParserService"
# Должна быть ошибка ImportError
```

---

## Порядок выполнения

```
1. Обновить импорты в app/ (16 замен)
   ↓
2. Запустить тесты
   ↓
3. Удалить re-export файлы
   ↓
4. Обновить __init__.py
   ↓
5. Запустить тесты снова
   ↓
6. (Опционально) Обновить импорты в scripts/
   ↓
7. Создать коммит
```

---

## Git commit

```bash
git add -A
git commit -m "refactor: phase 12d - complete import migration to features/

- Update all imports in routes/ to use features/ paths directly
- Update imports in services/prediction.py and services/user_profile.py
- Update imports in features/strava/client.py and sync/background.py
- Remove 9 re-export files (no longer needed)
- Update __init__.py files

All code now imports directly from features/, no more re-exports.
Tests: 208 passed.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

*Phase 12d of v2.2 post-refactor cleanup*
*Created: 2026-01-28*
