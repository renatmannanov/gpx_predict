# Code Review Plan - GPX Predictor

> **Дата создания:** 2026-01-24
> **Цель:** Привести кодовую базу в адекватное, понятное и простое для работы AI-агентов состояние
> **Условия:** Можем полностью пересоздать БД (миграция на PostgreSQL), можем ломать API

---

## Принятые решения (2026-01-24)

| Решение | Выбор |
|---------|-------|
| Имя профиля для hiking | `UserHikingProfile` (было `UserPerformanceProfile`) |
| Имя типа активности для бега | `trail_run` везде (унифицировать) |
| Добавление road_run | Не сейчас, добавим когда понадобится |
| Naismith 2 версии | **ОСТАВИТЬ** — нужны оба для 3 вариантов расчёта в HikePrediction |
| Лимиты размера файлов | Сервисы 500, Routes/Handlers 400, Models 300, Utils 200 |

---

## Обзор найденных проблем

### Критические проблемы (блокеры)

| # | Проблема | Влияние | Приоритет |
|---|----------|---------|-----------|
| 1 | **Смешение sync/async в StravaSyncService** | Блокировка event loop, undefined behavior | 🔴 P0 |
| 2 | ~~Дублирование Naismith (2 версии)~~ | **ОТЛОЖЕНО** — нужны оба для 3 вариантов расчёта | ⚪ Backlog |
| 3 | **Несогласованный Activity Type naming** | 3+ варианта: hiking/running/trail_run/hike/run | 🔴 P0 |
| 4 | **Миграция зависит от auto-generated ID** | Сломается при чистом PostgreSQL | 🔴 P0 |
| 5 | **Файлы-гиганты (1000+ строк)** | Агент тратит много контекста | 🔴 P0 |

### Высокий приоритет

| # | Проблема | Влияние | Приоритет |
|---|----------|---------|-----------|
| 6 | **UserPerformanceProfile vs UserRunProfile naming** | "Performance" = hiking, но название generic | 🟠 P1 |
| 7 | **Дублирование tobler_speed()** | Две идентичные реализации | 🟠 P1 |
| 8 | **Дублирование format_time/format_pace в боте** | 4 копии одних функций | 🟠 P1 |
| 9 | **Keyboards в handlers/strava.py** | Архитектурное нарушение | 🟠 P1 |
| 10 | **N+1 queries потенциально** | Проблемы производительности | 🟠 P1 |
| 11 | **Отсутствие Repository pattern** | Только GPXRepository, остальное в routes | 🟠 P1 |

### Средний приоритет

| # | Проблема | Влияние | Приоритет |
|---|----------|---------|-----------|
| 12 | **Token refresh дублирование** | 3 места с token management | 🟡 P2 |
| 13 | **Нет единого ActivityType enum** | Строки везде | 🟡 P2 |
| 14 | **Inconsistent profile endpoints** | `/profile/{id}` vs `/profile/{id}/run` | 🟡 P2 |
| 15 | **Gradient classification несогласованность** | enum vs strings | 🟡 P2 |

---

## Текущие размеры файлов (проблема)

```
1125 строк  backend/app/services/strava_sync.py      ← КРИТИЧНО, разбить
 907 строк  bot/services/api_client.py               ← КРИТИЧНО, разбить
 716 строк  backend/app/services/strava.py           ← Превышает лимит
 692 строк  backend/app/services/user_profile.py     ← Превышает лимит
 628 строк  backend/app/api/v1/routes/strava.py      ← Превышает лимит
 583 строк  bot/handlers/prediction.py               ← Превышает лимит
 532 строк  backend/app/services/prediction.py       ← Превышает лимит
```

**Лимиты (новые правила):**
| Тип файла | Лимит | Причина |
|-----------|-------|---------|
| Сервисы | 500 строк | Один responsibility |
| Routes/Handlers | 400 строк | Должны быть тонкими |
| Models/Schemas | 300 строк | Простые структуры |
| Утилиты | 200 строк | Маленькие функции |

---

## План рефакторинга

### PHASE 0: Architecture for AI (НОВАЯ)
**Оценка:** ~400-500 строк изменений
**Зависимости:** Нет (делается первой)
**Цель:** Структурировать код так, чтобы агент мог работать с одним модулем, не читая весь проект

#### 0.1 Feature-based модульная структура

Текущая структура (плохо для агента):
```
backend/app/services/
├── calculators/         # 15+ файлов
├── strava.py           # OAuth + client смешаны
├── strava_sync.py      # 1125 строк!
├── user_profile.py     # hiking + running смешаны
└── prediction.py       # Всё в одном
```

Целевая структура (хорошо для агента):
```
backend/app/
├── features/
│   ├── hiking/                    # ВСЁ про hiking в одном месте
│   │   ├── __init__.py           # Публичный API модуля
│   │   ├── models.py             # UserHikingProfile
│   │   ├── schemas.py            # HikePrediction, request/response
│   │   ├── service.py            # HikingPredictionService
│   │   ├── calculators/
│   │   │   ├── tobler.py
│   │   │   ├── naismith.py
│   │   │   └── personalization.py
│   │   └── README.md             # Описание для агента
│   │
│   ├── trail_run/                 # ВСЁ про trail running
│   │   ├── __init__.py
│   │   ├── models.py             # UserRunProfile
│   │   ├── schemas.py
│   │   ├── service.py            # TrailRunService
│   │   ├── calculators/
│   │   │   ├── gap.py
│   │   │   ├── threshold.py
│   │   │   └── personalization.py
│   │   └── README.md
│   │
│   ├── strava/                    # ВСЁ про Strava интеграцию
│   │   ├── __init__.py
│   │   ├── models.py             # StravaToken, StravaActivity, SyncStatus
│   │   ├── oauth.py              # OAuth flow (из strava.py)
│   │   ├── client.py             # API client (из strava.py)
│   │   ├── sync/
│   │   │   ├── service.py        # Sync service (разбить strava_sync.py)
│   │   │   ├── activities.py     # Activity sync
│   │   │   └── splits.py         # Splits sync
│   │   └── README.md
│   │
│   ├── gpx/                       # GPX parsing
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   ├── segmenter.py
│   │   └── repository.py
│   │
│   └── users/                     # User management
│       ├── __init__.py
│       ├── models.py             # User, notifications
│       ├── service.py
│       └── repository.py
│
├── shared/                        # Общие утилиты (НЕ бизнес-логика)
│   ├── geo.py                    # haversine
│   ├── elevation.py              # smoothing
│   ├── formatters.py             # format_time, format_pace
│   └── constants.py              # ActivityType enum, etc
│
└── api/                           # ТОЛЬКО роутинг, минимум логики
    └── v1/routes/
        ├── hiking.py             # Вызывает features/hiking
        ├── trail_run.py          # Вызывает features/trail_run
        ├── strava.py             # Вызывает features/strava
        └── users.py              # Вызывает features/users
```

#### 0.2 README.md в каждом feature модуле

Пример `features/hiking/README.md`:
```markdown
# Hiking Prediction Module

## Назначение
Расчёт времени прохождения пешего маршрута.

## Публичный API
```python
from app.features.hiking import HikingPredictionService, UserHikingProfile

service = HikingPredictionService(db)
result = await service.predict(gpx_info, user_id, params)
```

## Зависимости
- `shared.geo` — расчёт расстояний
- `shared.elevation` — сглаживание высот
- `features.gpx` — парсинг GPX файлов

## Калькуляторы
| Метод | Когда использовать |
|-------|-------------------|
| Tobler | По умолчанию, горные маршруты |
| Naismith | Альтернатива, плоские маршруты |
| Personalized | Если есть профиль из Strava |

## Файлы и их размеры
- `service.py` — 250 строк (orchestration)
- `calculators/tobler.py` — 150 строк
- `calculators/naismith.py` — 200 строк
```

#### 0.3 Явные контракты в `__init__.py`

```python
# features/hiking/__init__.py
"""
Hiking prediction module.

Public API:
- HikingPredictionService — main service
- UserHikingProfile — user profile model
- HikePrediction — prediction result schema

Usage:
    from app.features.hiking import HikingPredictionService

    async with get_db() as db:
        service = HikingPredictionService(db)
        result = await service.predict(gpx_info, telegram_id)
"""

from .service import HikingPredictionService
from .models import UserHikingProfile
from .schemas import HikePrediction, HikePredictRequest

__all__ = [
    "HikingPredictionService",
    "UserHikingProfile",
    "HikePrediction",
    "HikePredictRequest",
]
```

#### 0.4 Разбиение файлов-гигантов

| Файл | Строк | Как разбить |
|------|-------|-------------|
| `strava_sync.py` (1125) | → 3 файла | `sync/service.py`, `sync/activities.py`, `sync/splits.py` |
| `api_client.py` (907) | → 4 файла | По features: `hiking.py`, `trail_run.py`, `strava.py`, `users.py` |
| `strava.py` (716) | → 2 файла | `oauth.py`, `client.py` |
| `user_profile.py` (692) | → 2 файла | В `hiking/profile_calc.py`, `trail_run/profile_calc.py` |
| `routes/strava.py` (628) | → тоньше | Логика в `features/strava/`, route только вызывает |

#### 0.5 Обновление CLAUDE.md с картой

- [ ] Добавить карту модулей
- [ ] Добавить "типичные задачи" с указанием файлов
- [ ] Добавить лимиты размеров файлов

**Файлы Phase 0:**
```
NEW: backend/app/features/hiking/
NEW: backend/app/features/trail_run/
NEW: backend/app/features/strava/
NEW: backend/app/features/gpx/
NEW: backend/app/features/users/
NEW: backend/app/shared/
MOVE: много файлов из services/ в features/
UPDATE: CLAUDE.md
```

---

### PHASE 1: Database & Infrastructure (P0)
**Оценка:** ~250-300 строк изменений
**Зависимости:** Phase 0 (частично, можно параллельно)

#### 1.1 Docker для PostgreSQL
- [ ] Создать `docker-compose.yml`:
  ```yaml
  services:
    postgres:
      image: postgres:16
      environment:
        POSTGRES_DB: gpx_predictor
        POSTGRES_USER: gpx
        POSTGRES_PASSWORD: secret
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data

  volumes:
    postgres_data:
  ```
- [ ] Обновить `.env.example` с DATABASE_URL для PostgreSQL
- [ ] Добавить `asyncpg` и `psycopg2-binary` в requirements

#### 1.2 Исправление миграций
- [ ] Переименовать `537cb9c6ae39_add_sample_count_columns...` → `007a_add_sample_count_columns`
- [ ] Обновить `down_revision` в `008_add_onboarding_and_notifications.py`
- [ ] Создать единую initial миграцию для PostgreSQL (опционально)

#### 1.3 Полный async переход
- [ ] `StravaSyncService` — заменить все `db.query()` на `await db.execute(select())`
- [ ] Убрать `Union[Session, AsyncSession]` — только AsyncSession
- [ ] Обновить все routes использовать `get_async_db`

#### 1.4 Eager loading
- [ ] Добавить `lazy="selectin"` для `StravaActivity.splits`
- [ ] Добавить `lazy="selectin"` для `User.notifications`
- [ ] Использовать `joinedload()` в критичных queries

#### 1.5 Connection pool для PostgreSQL
- [ ] Настроить pool_size, max_overflow в session.py

**Файлы Phase 1:**
```
NEW: docker-compose.yml
UPDATE: .env.example
UPDATE: requirements.txt
RENAME: backend/alembic/versions/537cb9c6ae39_*.py
UPDATE: backend/alembic/versions/008_*.py
UPDATE: backend/app/db/session.py
UPDATE: backend/app/features/strava/sync/*.py (после Phase 0)
```

---

### PHASE 2: Naming & Types Unification (P0-P1)
**Оценка:** ~300-350 строк изменений
**Зависимости:** Phase 0

#### 2.1 Создание единого ActivityType
- [ ] Создать `backend/app/shared/constants.py`:
  ```python
  from enum import Enum

  class ActivityType(str, Enum):
      """Наши типы активностей"""
      HIKING = "hiking"
      TRAIL_RUN = "trail_run"

  class StravaActivityType(str, Enum):
      """Типы из Strava API"""
      RUN = "Run"
      TRAIL_RUN = "TrailRun"
      HIKE = "Hike"
      WALK = "Walk"
      VIRTUAL_RUN = "VirtualRun"

  STRAVA_TO_ACTIVITY_TYPE = {
      StravaActivityType.HIKE: ActivityType.HIKING,
      StravaActivityType.WALK: ActivityType.HIKING,
      StravaActivityType.RUN: ActivityType.TRAIL_RUN,
      StravaActivityType.TRAIL_RUN: ActivityType.TRAIL_RUN,
  }
  ```

#### 2.2 Переименование моделей
- [ ] `UserPerformanceProfile` → `UserHikingProfile`
- [ ] Миграция для rename таблицы
- [ ] Обновить все импорты

#### 2.3 Унификация PredictionType
- [ ] `PredictionType.RUN` → `PredictionType.TRAIL_RUN`

**Файлы Phase 2:**
```
NEW: backend/app/shared/constants.py
UPDATE: backend/app/features/hiking/models.py
UPDATE: backend/app/features/trail_run/models.py
NEW: backend/alembic/versions/010_rename_performance_to_hiking.py
```

---

### PHASE 3: Calculator Cleanup (P1)
**Оценка:** ~200 строк изменений
**Зависимости:** Phase 0, Phase 2

#### 3.1 Устранение дублирования tobler_speed
- [ ] Вынести `tobler_speed()` в `shared/formulas.py`
- [ ] Использовать из обоих мест

#### 3.2 Документирование калькуляторов
- [ ] Добавить docstrings
- [ ] README в каждом calculator модуле

**Файлы Phase 3:**
```
NEW: backend/app/shared/formulas.py
UPDATE: backend/app/features/hiking/calculators/tobler.py
UPDATE: backend/app/features/hiking/calculators/personalization.py
```

---

### PHASE 4: Bot Cleanup (P1)
**Оценка:** ~250-300 строк изменений
**Зависимости:** Phase 2

#### 4.1 Создание utils
- [ ] `bot/utils/formatters.py` — format_time, format_pace, etc
- [ ] `bot/utils/callbacks.py` — CallbackPrefix enum

#### 4.2 Разбиение api_client.py (907 строк!)
- [ ] `bot/services/clients/hiking.py`
- [ ] `bot/services/clients/trail_run.py`
- [ ] `bot/services/clients/strava.py`
- [ ] `bot/services/clients/users.py`
- [ ] `bot/services/clients/base.py` — общий HTTP клиент

#### 4.3 Перемещение Strava keyboards
- [ ] Создать `bot/keyboards/strava.py`
- [ ] Убрать keyboards из handlers

**Файлы Phase 4:**
```
NEW: bot/utils/formatters.py
NEW: bot/utils/callbacks.py
NEW: bot/services/clients/
NEW: bot/keyboards/strava.py
UPDATE: bot/handlers/*.py
```

---

### PHASE 5: Repository Pattern (P1-P2)
**Оценка:** ~300-350 строк изменений
**Зависимости:** Phase 0, Phase 1

#### 5.1 Base repository
- [ ] `backend/app/shared/repository.py`

#### 5.2 Feature repositories
- [ ] Каждый feature модуль имеет свой `repository.py`
- [ ] Вынести queries из routes

**Файлы Phase 5:**
```
NEW: backend/app/shared/repository.py
UPDATE: backend/app/features/*/repository.py
UPDATE: backend/app/api/v1/routes/*.py
```

---

### PHASE 6: API Cleanup (P2)
**Оценка:** ~150-200 строк изменений
**Зависимости:** Phase 2, Phase 5

#### 6.1 Унификация endpoints
```
GET  /api/v1/profiles/{telegram_id}/hiking
GET  /api/v1/profiles/{telegram_id}/trail-run
POST /api/v1/profiles/{telegram_id}/hiking/calculate
POST /api/v1/profiles/{telegram_id}/trail-run/calculate
```

#### 6.2 Тонкие routes
- [ ] Routes только валидируют и вызывают services
- [ ] Никакой бизнес-логики в routes

---

## Правила для CLAUDE.md (добавить после рефакторинга)

```markdown
## Архитектура проекта

### Feature-based модули
Каждая бизнес-область в своём модуле:
- `features/hiking/` — всё про hiking
- `features/trail_run/` — всё про trail running
- `features/strava/` — интеграция со Strava
- `features/gpx/` — работа с GPX файлами
- `features/users/` — управление пользователями

### Где искать код
| Задача | Где искать |
|--------|-----------|
| Добавить калькулятор hiking | `features/hiking/calculators/` |
| Изменить sync Strava | `features/strava/sync/` |
| Добавить API endpoint | `api/v1/routes/` + вызов feature service |
| Добавить bot handler | `bot/handlers/` + вызов api_client |

### Shared код
`shared/` содержит ТОЛЬКО:
- Утилиты без бизнес-логики (geo, elevation)
- Константы и enums
- Base классы (BaseRepository)

НЕ добавлять в shared бизнес-логику!

## Лимиты размера файлов

| Тип | Лимит | Действие при превышении |
|-----|-------|------------------------|
| Сервисы | 500 строк | Разбить по responsibility |
| Routes/Handlers | 400 строк | Вынести логику в service |
| Models/Schemas | 300 строк | Разбить по entities |
| Утилиты | 200 строк | Разбить по функциям |

**Правило:** Если файл превышает лимит — это сигнал к рефакторингу.

## Правила нейминга

### Activity Types
- Использовать `ActivityType` enum из `shared/constants.py`
- НИКОГДА строки напрямую: ❌ `"hiking"` → ✅ `ActivityType.HIKING`

### Profile Models
- `UserHikingProfile` — для hiking
- `UserRunProfile` — для trail running
- ❌ НЕ использовать "performance" — слишком общее

### Method Names в калькуляторах
Допустимые: `naismith`, `tobler`, `hiking_personalized`, `trail_run_personalized`

## Правила работы с БД

### Async-only
```python
# ✅ Правильно
result = await db.execute(select(User).where(User.id == id))
user = result.scalar_one_or_none()

# ❌ Неправильно
user = db.query(User).filter(User.id == id).first()
```

### Repositories
- Все queries через repository, НЕ в routes
- Каждый feature имеет свой `repository.py`

### Relationships
- ВСЕГДА указывать `lazy` параметр
- Для частых join: `lazy="selectin"` или `lazy="joined"`

## Правила для бота

### Форматтеры
Все в `bot/utils/formatters.py`. НЕ дублировать!

### Keyboards
Все в `bot/keyboards/`. НЕ в handlers!

### API Client
Разбит по features:
- `bot/services/clients/hiking.py`
- `bot/services/clients/strava.py`
- etc.

## README в каждом модуле

Каждый feature модуль ДОЛЖЕН иметь README.md с:
1. Назначение модуля
2. Публичный API (что экспортирует __init__.py)
3. Зависимости
4. Список файлов с размерами
```

---

## Порядок выполнения

```
Phase 0 (Architecture) ──► Phase 1 (Database) ──► Phase 5 (Repositories)
         │                        │
         └──► Phase 2 (Naming) ───┼──► Phase 3 (Calculators)
                                  │
                                  └──► Phase 4 (Bot) ──► Phase 6 (API)
```

**Рекомендуемый порядок для AI-агентов:**

| Сессия | Фаза | Описание | Строк |
|--------|------|----------|-------|
| 1 | Phase 0 | Architecture restructure | ~500 |
| 2 | Phase 1 | Database + Docker + async | ~300 |
| 3 | Phase 2 | Naming + constants | ~350 |
| 4 | Phase 3 | Calculator cleanup | ~200 |
| 5 | Phase 4 | Bot cleanup | ~300 |
| 6 | Phase 5 | Repositories | ~350 |
| 7 | Phase 6 | API cleanup | ~200 |

---

## Чеклист перед каждой сессией

- [ ] Прочитать эту секцию плана
- [ ] Прочитать CLAUDE.md
- [ ] `git status` — чистый?
- [ ] Тесты проходят? (если есть)

## Чеклист после каждой сессии

- [ ] Все изменения закоммичены
- [ ] CLAUDE.md обновлён (если нужно)
- [ ] Отмечены ✅ выполненные пункты
- [ ] README.md созданы для новых модулей

---

## Metrics (до/после)

| Метрика | До | После | Цель |
|---------|-----|-------|------|
| Файлов >500 строк | 7 | ? | 0 |
| Файлов >1000 строк | 2 | ? | 0 |
| Sync/async смешение | 3 файла | ? | 0 |
| Activity type variants | 5+ | ? | 2 (enum) |
| Feature modules | 0 | ? | 5 |
| README в модулях | 0 | ? | 5+ |
| Дублирование форматтеров | 4 | ? | 1 |

---

*Создано: Claude Code Review Session, 2026-01-24*
*Обновлено: добавлена Phase 0 (Architecture for AI)*
