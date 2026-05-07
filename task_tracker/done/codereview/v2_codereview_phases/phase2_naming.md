# Phase 2: Naming & Types Unification

> **Статус:** Не начато
> **Оценка:** ~200 строк изменений
> **Зависимости:** Phase 0c, 0d
> **Ветка:** `refactor/phase-2-naming`
> **Цель:** Унифицировать naming, создать единый ActivityType enum

---

## Проблемы

1. **Activity Type хаос:**
   - `hiking` / `running` (user preference)
   - `hike` / `run` (PredictionType)
   - `HIKE` / `TRAIL_RUN` (ActivityType enum — несовпадение!)
   - `Run` / `Hike` / `Walk` (Strava API)

2. **Profile naming:**
   - `UserPerformanceProfile` — generic название для hiking
   - `UserRunProfile` — явное название для running

3. **PredictionType.RUN** не соответствует `ActivityType.TRAIL_RUN`

---

## Задачи

### 2.1 Создать единый ActivityType

Создать `backend/app/shared/constants.py`:

```python
from enum import Enum

class ActivityType(str, Enum):
    """Наши типы активностей для predictions"""
    HIKING = "hiking"
    TRAIL_RUN = "trail_run"
    # В будущем: ROAD_RUN = "road_run"


class StravaActivityType(str, Enum):
    """Типы активностей из Strava API (их naming)"""
    RUN = "Run"
    TRAIL_RUN = "TrailRun"
    VIRTUAL_RUN = "VirtualRun"
    HIKE = "Hike"
    WALK = "Walk"


# Маппинг Strava → наш тип
STRAVA_TO_ACTIVITY_TYPE: dict[StravaActivityType, ActivityType] = {
    StravaActivityType.HIKE: ActivityType.HIKING,
    StravaActivityType.WALK: ActivityType.HIKING,
    StravaActivityType.RUN: ActivityType.TRAIL_RUN,
    StravaActivityType.TRAIL_RUN: ActivityType.TRAIL_RUN,
    StravaActivityType.VIRTUAL_RUN: ActivityType.TRAIL_RUN,
}


# Strava типы для каждого профиля
STRAVA_TYPES_FOR_HIKING = [StravaActivityType.HIKE, StravaActivityType.WALK]
STRAVA_TYPES_FOR_TRAIL_RUN = [
    StravaActivityType.RUN,
    StravaActivityType.TRAIL_RUN,
    StravaActivityType.VIRTUAL_RUN,
]


class PredictionType(str, Enum):
    """Тип prediction (соответствует ActivityType)"""
    HIKING = "hiking"
    TRAIL_RUN = "trail_run"
```

### 2.2 Переименовать UserPerformanceProfile

- [ ] Переименовать класс:
  ```python
  # Было
  class UserPerformanceProfile(Base):
      __tablename__ = "user_performance_profiles"

  # Стало
  class UserHikingProfile(Base):
      __tablename__ = "user_hiking_profiles"
  ```

- [ ] Создать миграцию:
  ```python
  # backend/alembic/versions/010_rename_performance_to_hiking.py
  def upgrade():
      op.rename_table('user_performance_profiles', 'user_hiking_profiles')

  def downgrade():
      op.rename_table('user_hiking_profiles', 'user_performance_profiles')
  ```

### 2.3 Обновить все импорты и использования

Заменить везде:
```python
# Было
from app.models import UserPerformanceProfile
user.performance_profile

# Стало
from app.features.hiking import UserHikingProfile
user.hiking_profile
```

### 2.4 Унифицировать PredictionType

В `schemas/prediction.py` (или `features/hiking/schemas.py`):
```python
# Было
class PredictionType(str, Enum):
    HIKE = "hike"
    RUN = "run"

# Стало (импортировать из shared/constants.py)
from app.shared.constants import PredictionType
# PredictionType.HIKING, PredictionType.TRAIL_RUN
```

### 2.5 Обновить User model

```python
# Было
preferred_activity_type = Column(String, default="hiking")

# Стало
from app.shared.constants import ActivityType

preferred_activity_type = Column(
    Enum(ActivityType),
    default=ActivityType.HIKING
)
```

### 2.6 Обновить bot

В боте заменить строки на enum:
```python
# Было
if activity_type == "hiking":
    ...
elif activity_type == "trail_run":
    ...

# Стало
from app.shared.constants import ActivityType

if activity_type == ActivityType.HIKING:
    ...
elif activity_type == ActivityType.TRAIL_RUN:
    ...
```

---

## Файлы для изменения

```
NEW:
backend/app/shared/constants.py
backend/alembic/versions/010_rename_performance_to_hiking.py

UPDATE:
backend/app/features/hiking/models.py (rename class)
backend/app/features/users/models.py (User.preferred_activity_type)
backend/app/features/hiking/schemas.py (PredictionType)
backend/app/features/trail_run/schemas.py
backend/app/features/strava/sync/*.py (use constants)
backend/app/api/v1/routes/*.py (use constants)

bot/handlers/prediction.py
bot/handlers/trail_run.py
bot/handlers/onboarding.py
bot/handlers/profile.py
bot/services/api_client.py (or clients/*.py after Phase 4)
```

---

## Критерии завершения

- [ ] `shared/constants.py` создан с ActivityType, StravaActivityType, PredictionType
- [ ] `UserPerformanceProfile` → `UserHikingProfile`
- [ ] Таблица переименована через миграцию
- [ ] Нигде нет строк `"hiking"`, `"trail_run"` — только enum
- [ ] Приложение работает
- [ ] Бот работает

---

## Проверка

```bash
cd backend

# Проверить константы
python -c "from app.shared.constants import ActivityType, PredictionType; print('OK')"

# Миграция
alembic upgrade head

# Приложение
uvicorn app.main:app --reload

# Бот (в другом терминале)
cd ../bot && python main.py
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 2 - unify naming and types

- Create shared/constants.py with ActivityType, StravaActivityType, PredictionType
- Rename UserPerformanceProfile -> UserHikingProfile
- Add migration for table rename
- Replace string literals with enums

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-2-naming
```

Перейти к Phase 3.

---

*Phase 2 — Naming & Types Unification*
