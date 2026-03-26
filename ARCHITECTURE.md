# Архитектура GPX Predictor

**Последнее обновление:** 2026-02-13 (docs restructure + tools/calibration)

## Оглавление
1. [Обзор системы](#1-обзор-системы)
2. [Структура проекта](#2-структура-проекта)
3. [Слой данных (Models)](#3-слой-данных-models)
4. [Сервисный слой (Services)](#4-сервисный-слой-services)
5. [Калькуляторы времени](#5-калькуляторы-времени)
6. [Trail Running](#6-trail-running)
7. [API слой (Routes)](#7-api-слой-routes)
8. [Telegram Bot](#8-telegram-bot)
9. [Потоки данных](#9-потоки-данных)
10. [Внешние интеграции](#10-внешние-интеграции)

---

## 1. Обзор системы

GPX Predictor — система прогнозирования времени прохождения маршрутов с интеграцией Strava.

### Основные компоненты

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│   Backend API   │────▶│   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   Strava API    │
                        └─────────────────┘
```

### Технологический стек

| Компонент | Технология |
|-----------|------------|
| Backend | FastAPI + Python 3.11+ |
| Database | PostgreSQL / SQLite (dev) |
| ORM | SQLAlchemy 2.0 |
| Bot | aiogram 3.x |
| Async HTTP | httpx |

---

## 2. Структура проекта

> **После рефакторинга v2** проект использует feature-based структуру.

```
gpx-predictor/
├── backend/
│   └── app/
│       ├── api/v1/
│       │   ├── routes/
│       │   │   ├── predict.py      # Прогнозы (hiking + trail running)
│       │   │   ├── gpx.py          # Загрузка GPX
│       │   │   ├── races.py        # Гонки: каталог, результаты, прогнозы
│       │   │   ├── strava.py       # OAuth + активности
│       │   │   ├── profiles.py     # Профили (hiking + trail run)
│       │   │   └── users.py        # Пользователи
│       │   └── router.py           # Агрегация роутов
│       │
│       ├── features/               # Feature-based modules (NEW!)
│       │   ├── gpx/                # GPX parsing & storage
│       │   │   ├── __init__.py
│       │   │   ├── parser.py       # GPXParserService
│       │   │   ├── segmenter.py    # RouteSegmenter
│       │   │   ├── repository.py   # GPXRepository
│       │   │   └── models.py       # GPXFile model
│       │   │
│       │   ├── hiking/             # Hiking predictions
│       │   │   ├── __init__.py
│       │   │   ├── calculators/    # Tobler, Naismith
│       │   │   │   ├── tobler.py
│       │   │   │   ├── naismith.py
│       │   │   │   └── personalization.py
│       │   │   └── models.py       # UserPerformanceProfile
│       │   │
│       │   ├── trail_run/          # Trail running predictions
│       │   │   ├── __init__.py
│       │   │   ├── calculators/    # GAP, fatigue
│       │   │   │   ├── gap_calculator.py
│       │   │   │   ├── hike_run_threshold.py
│       │   │   │   └── runner_fatigue.py
│       │   │   ├── service.py      # TrailRunService
│       │   │   └── models.py       # UserRunProfile
│       │   │
│       │   ├── strava/             # Strava integration
│       │   │   ├── __init__.py
│       │   │   ├── client.py       # StravaClient
│       │   │   ├── sync/           # Background sync
│       │   │   │   ├── service.py  # StravaSyncService
│       │   │   │   └── runner.py   # BackgroundSyncRunner
│       │   │   └── models.py       # StravaToken, StravaActivity
│       │   │
│       │   ├── races/              # Race catalog, results & predictions
│       │   │   ├── __init__.py
│       │   │   ├── models.py       # RaceResult, RaceStats, RaceEditionData
│       │   │   ├── db_models.py    # SQLAlchemy: Race, RaceEdition, RaceDistance, RaceResultDB
│       │   │   ├── repository.py   # RaceRepository (DB reads: list, get, search, stats)
│       │   │   ├── catalog.py      # RaceCatalog (GPX file path lookup only)
│       │   │   ├── clax_parser.py  # CLAX XML parser (myrace.info)
│       │   │   ├── service.py      # RaceService (prediction + comparison from DB)
│       │   │   ├── stats.py        # Statistics calculations
│       │   │   ├── name_utils.py   # normalize_name() for participant matching
│       │   │   └── matching.py     # User matching across years
│       │   │
│       │   └── users/              # User management
│       │       ├── __init__.py
│       │       ├── models.py       # User, Notification
│       │       └── notification_service.py  # NotificationService
│       │
│       ├── shared/                 # Shared utilities (NEW!)
│       │   ├── __init__.py
│       │   ├── geo.py              # haversine(), calculate_total_distance()
│       │   ├── elevation.py        # smooth_elevations()
│       │   ├── calculator_types.py # MacroSegment, SegmentType, RouteComparison
│       │   ├── formulas.py         # tobler_hiking_speed(), etc.
│       │   ├── telegram.py         # TelegramNotifier (push notifications)
│       │   └── notification_formatter.py  # format_notification()
│       │
│       ├── services/               # Cross-feature services
│       │   ├── prediction.py       # Main prediction orchestrator
│       │   ├── naismith.py         # old_naismith (3rd method!)
│       │   ├── sun.py              # Sunrise/sunset
│       │   ├── user_profile.py     # Profile calculation
│       │   └── calculators/
│       │       ├── base.py         # Base calculator classes
│       │       └── comparison.py   # ComparisonService
│       │
│       ├── models/                 # Re-exports for backward compatibility
│       ├── schemas/                # Pydantic schemas
│       └── repositories/           # Re-exports for backward compatibility
│
│   └── tools/
│       └── calibration/            # Backtesting & calibration toolkit
│           ├── virtual_route.py    # VirtualRoute, VirtualSegment
│           ├── calculators.py      # CalculatorAdapter (Tobler/Naismith/GAP)
│           ├── metrics.py          # MetricsCalculator (MAE/MAPE/RMSE)
│           ├── service.py          # BacktestingService
│           ├── report.py           # ReportGenerator
│           └── cli.py              # CLI entry point
│
├── bot/
│   ├── handlers/
│   │   ├── prediction.py           # Хендлеры прогнозов (hiking)
│   │   ├── trail_run.py            # Хендлеры trail running
│   │   └── races.py               # Хендлеры гонок (/races)
│   ├── keyboards/
│   │   └── races.py               # Inline keyboards для гонок
│   ├── states/
│   │   └── races.py               # FSM states для гонок
│   └── services/
│       └── clients/                # API клиенты
│           ├── hiking.py
│           ├── trail_run.py
│           ├── strava.py
│           └── races.py            # API client для гонок
│
├── content/                        # Статический контент (не код)
│   └── races/
│       ├── catalog.yaml            # Мастер-каталог CLAX ссылок (ручной)
│       ├── races.yaml              # GPX file mapping для дистанций
│       └── gpx/                    # GPX файлы дистанций
│
└── docs/
    ├── ARCHITECTURE.md             # Этот файл
    ├── CALCULATIONS.md             # Детали расчётов
    ├── insights/                   # Справочные данные (результаты гонок, аналитика)
    ├── shareable/                  # Промпты/шаблоны для других проектов
    └── task_tracker/               # Планы и задачи
        ├── archieve/               # Неактуальное (не читать без запроса)
        ├── backlog/                # Отложенные задачи
        ├── done/                   # Выполненные задачи (не читать без запроса)
        └── todo/                   # Текущие задачи и планы
```

---

## 3. Слой данных (Models)

### 3.1 User

**Таблица:** `users`

```python
class User:
    id: UUID                    # PK
    telegram_id: str            # Уникальный Telegram ID
    email: Optional[str]
    name: Optional[str]
    strava_athlete_id: Optional[str]
    strava_connected: bool      # Флаг подключения Strava
    created_at: datetime
    updated_at: datetime
```

**Связи:**
- `performance_profile` → UserPerformanceProfile (1:1) — для hiking
- `run_profile` → UserRunProfile (1:1) — для trail running
- `strava_activities` → StravaActivity (1:N)
- `strava_tokens` → StravaToken (1:1)

---

### 3.2 UserPerformanceProfile

**Таблица:** `user_performance_profiles`

```python
class UserPerformanceProfile:
    id: int                     # PK
    user_id: UUID               # FK → users

    # Темпы по типам terrain (мин/км)
    avg_flat_pace_min_km: Optional[float]
    avg_uphill_pace_min_km: Optional[float]
    avg_downhill_pace_min_km: Optional[float]

    # Коэффициенты
    vertical_ability: float     # 1.0 = норма, >1 = медленнее в гору

    # Статистика
    total_activities_analyzed: int
    total_hike_activities: int
    total_distance_km: float
    total_elevation_m: float

    last_calculated_at: datetime
```

**Computed properties:**
- `has_split_data` — есть ли данные из splits
- `flat_speed_kmh` — скорость из темпа

---

### 3.3 GPXFile

**Таблица:** `gpx_files`

```python
class GPXFile:
    id: UUID                    # PK
    filename: str
    gpx_content: bytes          # LargeBinary
    name: Optional[str]
    description: Optional[str]
    user_id: Optional[UUID]     # FK → users

    # Метрики
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_elevation_m: float
    min_elevation_m: float

    # Координаты
    start_lat, start_lon: float
    end_lat, end_lon: float
```

---

### 3.4 StravaToken

**Таблица:** `strava_tokens`

```python
class StravaToken:
    id: int                     # PK
    user_id: UUID               # FK → users
    strava_athlete_id: str
    access_token: str
    refresh_token: str
    expires_at: int             # Unix timestamp
    scope: Optional[str]
```

---

### 3.5 StravaActivity

**Таблица:** `strava_activities`

```python
class StravaActivity:
    id: int                     # PK
    user_id: UUID               # FK → users
    strava_id: int              # Unique ID в Strava

    name: Optional[str]
    activity_type: str          # Run, Hike, Walk
    start_date: datetime

    # Метрики
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elevation_gain_m: float
    elevation_loss_m: float

    # Performance
    avg_speed_mps: float
    max_speed_mps: float
    avg_heartrate: Optional[float]
    max_heartrate: Optional[float]

    splits_synced: bool         # Синхронизированы ли splits
```

**Связи:**
- `splits` → StravaActivitySplit (1:N, cascade delete)

---

### 3.6 StravaActivitySplit

**Таблица:** `strava_activity_splits`

```python
class StravaActivitySplit:
    id: int                     # PK
    activity_id: int            # FK → strava_activities
    split_number: int           # Номер километра

    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elevation_diff_m: float     # Ключевое для terrain classification
    average_speed_mps: float
    average_heartrate: Optional[float]
    pace_zone: Optional[int]
```

**Computed properties:**
- `pace_min_km` — темп в мин/км
- `gradient_percent` — уклон в %

---

### 3.7 StravaSyncStatus

**Таблица:** `strava_sync_status`

```python
class StravaSyncStatus:
    id: int                     # PK
    user_id: UUID               # FK → users (unique)

    last_sync_at: Optional[datetime]
    oldest_synced_date: Optional[datetime]
    newest_synced_date: Optional[datetime]
    total_activities_synced: int

    sync_in_progress: bool
    last_error: Optional[str]
```

---

## 4. Сервисный слой (Services)

### 4.1 PredictionService

**Файл:** `services/prediction.py`

**Ответственность:** Основной сервис прогнозирования времени.

**Методы:**
| Метод | Описание |
|-------|----------|
| `predict_hike()` | Прогноз для одного человека |
| `predict_group()` | Прогноз для группы |
| `_calculate_personalized_time()` | Персонализированный расчёт (TODO: рефакторинг) |
| `_generate_warnings()` | Генерация предупреждений |
| `_calculate_segments()` | Расчёт по сегментам |

**Зависимости:**
```
PredictionService
├── GPXRepository
├── GPXParserService
├── naismith.py (naismith_with_descent, multipliers)
├── sun.py (get_sun_times)
└── UserPerformanceProfile (optional)
```

---

### 4.2 GPXParserService

**Файл:** `features/gpx/parser.py` (legacy: `services/gpx_parser.py` → re-export)

**Ответственность:** Парсинг GPX файлов.

**Методы:**
| Метод | Описание |
|-------|----------|
| `parse()` | Парсинг в GPXInfo |
| `extract_points()` | Извлечение координат |
| `segment_route()` | Сегментация маршрута |
| `_haversine()` | Расстояние между точками |
| `_calculate_elevation()` | Набор/сброс высоты |

---

### 4.3 StravaClient

**Файл:** `features/strava/client.py` (legacy: `services/strava.py` → re-export)

**Ответственность:** Взаимодействие с Strava API.

**Методы:**
| Метод | Описание |
|-------|----------|
| `get_authorization_url()` | URL для OAuth |
| `exchange_code()` | Обмен code на токены |
| `refresh_token()` | Обновление токена |
| `get_valid_token()` | Получение валидного токена |
| `get_athlete()` | Профиль атлета |
| `get_activities()` | Список активностей |
| `get_activity_with_splits()` | Активность с splits |

**Rate Limiting:**
- 200 запросов / 15 минут
- 2000 запросов / день

---

### 4.4 StravaSyncService

**Файл:** `features/strava/sync/service.py` (legacy: `services/strava_sync.py` → re-export)

**Ответственность:** Фоновая синхронизация активностей.

**Классы:**
- `SyncConfig` — конфигурация
- `SyncQueueManager` — очередь пользователей
- `StravaSyncService` — логика синхронизации
- `BackgroundSyncRunner` — фоновый процесс

**Методы:**
| Метод | Описание |
|-------|----------|
| `sync_user_activities()` | Синхронизация активностей |
| `sync_activity_splits()` | Синхронизация splits |
| `sync_splits_for_user()` | Batch sync splits |
| `run_priority_sync()` | Ускоренная синхронизация для новых пользователей |

**Логика синхронизации (после OAuth):**

```
Этап 1: Первый batch (сразу)
├── Загружаем 10 активностей
├── Считаем профиль
└── Уведомление по качеству:
    • 0 активностей → "Нет подходящих"
    • 1-4 активности → "Профиль приблизительный"
    • 5-10 активностей → "Профиль базовый"

Этап 2: Фоновая загрузка (по процентам)
├── При 30% → пересчёт + уведомление
├── При 60% → пересчёт + уведомление
└── При 100% → финальный пересчёт + "Профиль полный"

Итого: 4 уведомления за всю синхронизацию
```

**Конфигурация (config.py):**
| Параметр | Значение | Описание |
|----------|----------|----------|
| `FIRST_BATCH_QUALITY_THRESHOLD` | 5 | Граница между "приблизительный" и "базовый" |
| `SYNC_PROGRESS_CHECKPOINTS` | [30, 60, 100] | Checkpoints для уведомлений |
| `PRIORITY_SYNC_BATCH_DELAY_SECONDS` | 5 | Задержка между batches (dev) |
| `PRIORITY_SYNC_MAX_CONSECUTIVE_BATCHES` | 10 | Макс. batches для priority sync |

---

### 4.5 UserProfileService

**Файл:** `services/user_profile.py`

**Ответственность:** Расчёт профиля производительности.

**Методы:**
| Метод | Описание |
|-------|----------|
| `get_profile()` | Получение профиля |
| `calculate_profile()` | Базовый расчёт (из агрегатов) |
| `calculate_profile_with_splits()` | Детальный расчёт (из splits) |
| `_calculate_vertical_ability()` | Коэффициент вертикальной способности |

**Классификация terrain:**
- Flat: -3% to +3%
- Uphill: > +3%
- Downhill: < -3%

---

### 4.6 NotificationService

**Файл:** `features/users/notification_service.py`

**Ответственность:** Создание уведомлений в БД и отправка push в Telegram.

**Методы:**
| Метод | Описание |
|-------|----------|
| `create_and_send()` | Создать notification в БД и отправить push |
| `_send_push()` | Отправка в Telegram (внутренний) |

**Зависимости:**
```
NotificationService
├── TelegramNotifier (shared/telegram.py)
├── format_notification() (shared/notification_formatter.py)
└── User, Notification models
```

**Типы уведомлений:**
| Тип | Описание |
|-----|----------|
| `strava_connected` | Strava успешно подключён (перед sync) |
| `first_batch_complete` | После первого batch (0/1-4/5-10 активностей) |
| `sync_progress` | При 30%/60% синхронизации |
| `sync_complete` | При 100% (все активности загружены) |
| `profile_updated` | (Legacy) Профиль пересчитан |
| `profile_complete` | (Legacy) Все категории градиента заполнены |
| `profile_incomplete` | (Legacy) Не хватает данных для категорий |

**Использование:**
```python
notification_service = NotificationService(db)
await notification_service.create_and_send(
    user_id=user.id,
    notification_type="first_batch_complete",
    data={
        "quality": "basic",  # none/preliminary/basic
        "activities_with_splits": 7,
        "total_synced": 10
    }
)
```

---

## 5. Калькуляторы времени

### 5.1 Обзор методов

В системе 4 метода расчёта времени:

| Метод | Файл | Описание |
|-------|------|----------|
| `tobler` | `features/hiking/calculators/tobler.py` | Tobler's Hiking Function (1993) |
| `naismith` | `features/hiking/calculators/naismith.py` | Naismith + Langmuir corrections |
| `tobler_personalized` | `features/hiking/calculators/personalization.py` | Tobler + персональный темп из Strava |
| `naismith_personalized` | `features/hiking/calculators/personalization.py` | Naismith + персональный темп из Strava |

**Персонализированные методы** появляются только если у пользователя есть профиль с данными из Strava (≥1 hiking активность, ≥5 splits).

Пример для маршрута 24км, +1650м (Чёрный Камень):
```
naismith:             8ч 27мин
tobler:               7ч 32мин
tobler_personalized:  6ч 44мин  (🎯 ваш темп)
naismith_personalized: 6ч 44мин (🎯 ваш темп)
```

---

### 5.2 ToblerCalculator

**Файл:** `features/hiking/calculators/tobler.py`

**Формула:** `Speed = 6 * exp(-3.5 * |gradient + 0.05|)` км/ч

**Характеристики:**
- Максимум 6 км/ч при -5% уклоне (лёгкий спуск)
- 5 км/ч на ровной местности
- Основана на данных швейцарской армии (Imhof, 1950)

---

### 5.3 NaismithCalculator

**Файл:** `features/hiking/calculators/naismith.py`

**Формула:**
```
Базовое = distance / 5 км/ч + elevation_gain / 600 м/ч

Langmuir corrections для спуска:
- Пологий (5-12°): -10 мин на 300м (быстрее)
- Крутой (>12°): +10 мин на 300м (медленнее)
```

---

### 5.4 PersonalizationService

**Файл:** `features/hiking/calculators/personalization.py`

**Ответственность:** Расчёт времени на основе персональных данных из Strava.

**Логика:**
```python
def _get_pace_for_gradient(gradient_percent):
    if gradient > 3%:   return avg_uphill_pace_min_km
    elif gradient < -3%: return avg_downhill_pace_min_km
    else:               return avg_flat_pace_min_km
```

**Требования для профиля:**
- `MIN_ACTIVITIES_FOR_PROFILE = 1` (минимум 1 Hike/Walk активность)
- `MIN_SPLITS_FOR_DETAILED_PROFILE = 5` (минимум 5 сплитов)
- Типы активностей: `["Hike", "Walk"]` (Run исключён)

**Использование:**
```python
if PersonalizationService.is_profile_valid(user_profile):
    ps = PersonalizationService(user_profile)
    result = ps.calculate_segment(segment, base_method="tobler")
```

---

### 5.5 ComparisonService

**Файл:** `calculators/comparison.py`

**Ответственность:** Оркестрация всех калькуляторов для маршрута.

**Использование:**
```python
service = ComparisonService()
comparison = service.compare_route(
    points=[(lat, lon, ele), ...],
    profile_multiplier=1.0,
    user_profile=user_profile  # Optional
)

# Возвращает: RouteComparison с результатами:
# - totals: {"tobler": 7.5, "naismith": 8.4, "tobler_personalized": 6.7, ...}
# - segments: [SegmentComparison, ...]
# - personalized: True/False
# - activities_used: int
```

**Логика:**
1. Сегментирует маршрут через `RouteSegmenter`
2. Для каждого сегмента вызывает `ToblerCalculator` и `NaismithCalculator`
3. Если `user_profile` валиден, добавляет `PersonalizationService`
4. Суммирует время по методам

---

### 5.6 Сегментация маршрутов

В системе **два разных сегментера** для разных задач:

| Сегментер | Файл | Выход | Назначение |
|-----------|------|-------|------------|
| `GPXParserService.segment_route()` | `features/gpx/parser.py` | `List[GPXSegment]` | UI — равномерные сегменты |
| `RouteSegmenter.segment_route()` | `features/gpx/segmenter.py` | `List[MacroSegment]` | Калькуляторы — по направлению |

#### GPXParserService.segment_route() — для UI

Создаёт **сегменты примерно одинаковой длины** (~0.5-1.5 км) для отображения пользователю:
```
"0-1 км: 15 мин, уклон +5%"
"1-2 км: 20 мин, уклон +8%"
```

**Используется в:** `PredictionService._calculate_segments()` → API response `segments[]`

#### RouteSegmenter.segment_route() — для калькуляторов

Создаёт **сегменты по направлению движения** (подъём/спуск/flat):
```
Segment 1: ASCENT, 3.2 km, +450m
Segment 2: FLAT, 1.1 km, +20m
Segment 3: DESCENT, 2.8 km, -380m
```

**Используется в:** `ComparisonService.compare_route()` → Tobler/Naismith калькуляторы

**Параметры RouteSegmenter:**
- `MIN_SEGMENT_KM = 0.3`
- `FLAT_THRESHOLD_PERCENT = 3.0`

**Почему два сегментера:**
- UI-сегменты должны быть равномерными для понятного отображения
- Расчётные сегменты должны отражать реальную структуру маршрута (весь подъём как один сегмент)

---

## 6. Trail Running

### 6.1 Обзор

Trail Running — отдельная система расчётов для бега по пересечённой местности.

**Ключевые особенности (v3):**
- 3 базовых GAP метода считают **весь маршрут** как бег
- 6 комбинаций "Бег + Шаг" (3 GAP × 2 Hiking методов)
- Dual results: расчёт с Strava темпом + выбранный темп
- Переход на шаг при крутых подъёмах (порог **15%** по умолчанию)
- **Персонализированные методы** (Phase 3): `all_run_personalized`, `run_hike_personalized_*`
- Мета-информация о профиле в выводе (km, активности, сплиты, заполненность)

```
┌─────────────────────────────────────────────────────────────────┐
│                   TrailRunService                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  RouteSegmenter.segment_route()                                  │
│           │                                                      │
│           ▼                                                      │
│    List[MacroSegment]                                            │
│           │                                                      │
│           ├──► 3 GAP Calculators (STRAVA, MINETTI, STRAVA_MINETTI)
│           │           │                                          │
│           │           ▼                                          │
│           │    all_run_* totals (весь маршрут как бег)           │
│           │                                                      │
│           ├──► HikeRunThresholdService.decide()                  │
│           │           │                                          │
│           │    ┌──────┴──────┐                                   │
│           │    ▼             ▼                                   │
│           │  RUN           HIKE (>15% градиент по умолчанию)     │
│           │    │             │                                   │
│           │    ▼             ▼                                   │
│           │  GAP         Tobler/Naismith                         │
│           │           │                                          │
│           │           ▼                                          │
│           │    run_hike_* totals (6 комбинаций)                  │
│           │                                                      │
│           └──► RunnerFatigueService (optional)                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| `TrailRunService` | `features/trail_run/service.py` | Оркестратор всех компонентов |
| `GAPCalculator` | `features/trail_run/calculators/gap.py` | Grade Adjusted Pace (3 режима) |
| `HikeRunThresholdService` | `features/trail_run/calculators/threshold.py` | Определение run vs hike |
| `RunnerFatigueService` | `features/trail_run/calculators/fatigue.py` | Модель усталости бегуна |
| `RunPersonalizationService` | `features/trail_run/calculators/personalization.py` | Персонализация для бега |
| `ToblerCalculator` | `features/hiking/calculators/tobler.py` | Для hiking сегментов |
| `NaismithCalculator` | `features/hiking/calculators/naismith.py` | Для hiking сегментов |

### 6.3 GAPCalculator — 3 режима

**Grade Adjusted Pace** — корректирует темп с учётом уклона.

**Три режима (GAPMode enum):**

| Режим | Uphill | Downhill | Описание |
|-------|--------|----------|----------|
| `STRAVA` | Strava | Strava | Эмпирическая таблица (240k атлетов) |
| `MINETTI` | Minetti | Minetti | Чистая научная формула |
| `STRAVA_MINETTI` | Minetti | Strava | Гибрид: Minetti up + Strava down |

**Пример для 6:00/km flat pace:**

| Градиент | Strava GAP | Minetti GAP | Strava+Minetti |
|----------|------------|-------------|----------------|
| -15% | 5:24/km | ~5:06/km | 5:24/km |
| -9% | 5:17/km | ~5:00/km | 5:17/km |
| 0% | 6:00/km | 6:00/km | 6:00/km |
| +10% | 8:17/km | ~8:06/km | ~8:06/km |
| +20% | 12:54/km | ~11:30/km | ~11:30/km |
| +30% | 19:48/km | ~15:00/km | ~15:00/km |

**Minetti** даёт более оптимистичные результаты на подъёмах, **Strava** — более реалистичные на спусках.

### 6.4 Структура totals

TrailRunService возвращает богатую структуру totals:

```python
totals = {
    # Блок 1: Весь маршрут как бег (3 метода)
    "all_run_strava": 3.75,           # часы
    "all_run_minetti": 3.87,
    "all_run_strava_minetti": 3.80,

    # Блок 2: Бег + Шаг (6 комбинаций = 3 GAP × 2 Hiking)
    "run_hike_strava_tobler": 3.95,
    "run_hike_strava_naismith": 4.02,
    "run_hike_minetti_tobler": 4.05,
    "run_hike_minetti_naismith": 4.12,
    "run_hike_strava_minetti_tobler": 4.00,
    "run_hike_strava_minetti_naismith": 4.07,

    # Hiking времена (для всего маршрута)
    "tobler": 5.50,
    "naismith": 6.20,

    # Статистика разбивки Run/Hike
    "run_distance_km": 18.5,
    "hike_distance_km": 6.5,
    "run_percent": 74.0,
    "hike_percent": 26.0,
    "threshold_used": 15.0,  # DEFAULT_HIKE_THRESHOLD_PERCENT

    # Phase 3: Персонализированные методы (если есть run_profile)
    "all_run_personalized": 3.72,
    "run_hike_personalized_tobler": 3.92,
    "run_hike_personalized_naismith": 3.98,
    "run_profile": {
        "total_distance_km": 450,
        "total_activities": 32,
        "total_splits": 285,
        "categories_filled": 6,      # Только категории с ≥5 сэмплов
        "categories_total": 7,
        "min_samples_threshold": 5,
        "gradient_profile": [        # Детальная разбивка по градиентам
            {"category": "steep_uphill", "label": "steep_up (+15%↑)", "pace": None, "samples": 0, "is_personal": False},
            {"category": "moderate_uphill", "label": "moderate_up (+8-15%)", "pace": 10.36, "samples": 3, "is_personal": False},
            {"category": "gentle_uphill", "label": "gentle_up (+3-8%)", "pace": 8.50, "samples": 12, "is_personal": True},
            {"category": "flat", "label": "flat (-3 to +3%)", "pace": 6.00, "samples": 180, "is_personal": True},
            # ... и т.д.
        ]
    },

    # Legacy
    "combined": 4.10,  # primary time с fatigue
}
```

### 6.5 Dual Results (API)

API возвращает два набора totals если у пользователя есть Strava профиль:

```python
TrailRunCompareResponse:
    totals: Dict[str, float]              # = totals_manual (primary)
    totals_manual: Dict[str, float]       # Результаты с выбранным темпом
    totals_strava: Optional[Dict[str, float]]  # Результаты с Strava темпом
    manual_pace_used: float               # 6.0 (выбранный)
    strava_pace_used: Optional[float]     # 5.5 (из профиля)
```

**Логика dual calculation:**
1. Всегда считаем с `manual_pace` (выбранный/введённый пользователем)
2. Если есть Strava профиль и темп отличается — считаем ещё раз с `strava_pace`
3. Возвращаем оба набора для сравнения

### 6.6 HikeRunThresholdService

Определяет, когда бегун должен перейти на ходьбу.

**Параметры:**
- `uphill_threshold`: **15%** (по умолчанию, из `DEFAULT_HIKE_THRESHOLD_PERCENT`)
- `downhill_threshold`: -30% (технический спуск)
- `dynamic`: включить адаптацию к усталости

**Константа:** `shared/constants.py → DEFAULT_HIKE_THRESHOLD_PERCENT = 15.0`

**Логика хранения в БД:**
- Если threshold детектирован из Strava данных → хранится в профиле
- Если не детектирован (мало данных) → хранится `NULL`, используется константа
- При изменении константы все пользователи с `NULL` автоматически получают новое значение

**Пример для маршрута 20км с +2000м (порог 15%):**
- 14.8 км: RUN (74%)
- 5.2 км: HIKE (26%) — участки с градиентом >15%

### 6.7 UserRunProfile

**Таблица:** `user_run_profiles`

```python
class UserRunProfile:
    id: int                     # PK
    user_id: UUID               # FK → users

    # 7-category gradient paces (min/km)
    avg_flat_pace_min_km: Optional[float]
    avg_gentle_uphill_pace_min_km: Optional[float]
    avg_moderate_uphill_pace_min_km: Optional[float]
    avg_steep_uphill_pace_min_km: Optional[float]
    avg_gentle_downhill_pace_min_km: Optional[float]
    avg_moderate_downhill_pace_min_km: Optional[float]
    avg_steep_downhill_pace_min_km: Optional[float]

    # Sample counts per category (for confidence assessment)
    flat_sample_count: int
    gentle_uphill_sample_count: int
    moderate_uphill_sample_count: int
    steep_uphill_sample_count: int
    gentle_downhill_sample_count: int
    moderate_downhill_sample_count: int
    steep_downhill_sample_count: int

    # Walk threshold (NULL = use DEFAULT_HIKE_THRESHOLD_PERCENT)
    walk_threshold_percent: Optional[float]  # Default 15% (from constants)

    # Statistics
    total_activities: int
    total_distance_km: float
    total_elevation_m: float
```

**Sample counts и персонализация:**
- Минимум **5 сэмплов** на категорию для персонализации (`MIN_SAMPLES_FOR_CATEGORY = 5`)
- Если `sample_count < 5` → используется GAP fallback вместо персонального темпа
- `categories_filled` в API считает только категории с ≥5 сэмплов

**Отличия от UserHikingProfile:**
- Рассчитывается из Run/TrailRun активностей (не Hike/Walk)
- Включает walk_threshold_percent и sample_count поля
- Только 7-category система

### 6.8 RunnerFatigueService

Модель усталости для бегунов (отличается от hiking fatigue).

**Параметры:**
| Параметр | Значение | Описание |
|----------|----------|----------|
| Threshold | 2.0 часа | Когда начинается усталость |
| Linear rate | 5%/час | Линейная деградация |
| Quadratic rate | 0.8%/час² | Квадратичная деградация |
| Downhill multiplier | 1.5x | Дополнительная нагрузка на спусках |

**Пример multipliers:**
- 2h → 1.00 (без усталости)
- 4h → 1.13 (+13%)
- 6h → 1.33 (+33%)
- 6h downhill → 2.0 (+100%)

### 6.9 UX Flow в боте

При запросе trail run прогноза бот показывает разные сообщения в зависимости от Strava статуса:

| Сценарий | Сообщение | Клавиатура |
|----------|-----------|------------|
| Есть run profile | "👤 Твой темп: X:XX/км (N активностей)" | `[Strava X:XX] [5:30] [6:00] ...` |
| Strava подключена, нет run profile | "⚠️ Недостаточно беговых данных" | `[5:00] [5:30] [6:00] ...` |
| Strava не подключена | "⚠️ Strava не подключена" | `[5:00] [5:30] [6:00] ...` |

### 6.10 Пример вывода

```
🏃 Trail Run: Маршрут

📍 20.0 км | D+ 2000м | D- 2000м

━━━━━━━━━━━━━━━━━━━━━━━━

👤 НА ОСНОВЕ STRAVA (5:30/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP       3ч 38м
  Minetti GAP      3ч 44м
  Strava+Minetti   3ч 41м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 НА ОСНОВЕ ТВОЕГО ТЕМПА (6:00/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP       3ч 58м
  Minetti GAP      4ч 05м
  Strava+Minetti   4ч 01м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 БЕГ + ШАГ (порог 15%):
  🏃 14.8км (74%) | 🥾 5.2км (26%)

  Strava + Tobler    4ч 10м
  Strava + Naismith  4ч 15м
  Minetti + Tobler   4ч 18м
  Minetti + Naismith 4ч 22м
  S+M + Tobler       4ч 14м
  S+M + Naismith     4ч 18м
  🎯 Перс + Tobler   3ч 55м
  🎯 Перс + Naismith 3ч 58м

━━━━━━━━━━━━━━━━━━━━━━━━

📈 Персонализация: 450 км, 32 активностей, 285 сплитов, профиль 6 из 7

> 📊 Профиль по градиентам (✓ свой / GAP формула):
>
>   steep_up (+15%↑)       —   ( 0) GAP
>   moderate_up (+8-15%)  8.50 (12) ✓
>   gentle_up (+3-8%)     7.20 (45) ✓
>   flat (-3 to +3%)      5.50 (180) ✓
>   gentle_down (-3-8%)   5.00 (38) ✓
>   moderate_dn (-8-15%)  4.80 ( 8) ✓
>   steep_down (-15%↓)    5.20 ( 2) GAP
```

---

## 7. API слой (Routes)

### 7.1 Predict Routes

**Файл:** `routes/predict.py`

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/predict/hike` | POST | Индивидуальный прогноз (hiking) |
| `/predict/group` | POST | Групповой прогноз |
| `/predict/compare` | POST | Сравнение методов (hiking) |
| `/predict/trail-run/compare` | POST | Сравнение методов (trail running) |

---

### 7.2 GPX Routes

**Файл:** `routes/gpx.py`

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/gpx/upload` | POST | Загрузка GPX (max 20MB) |
| `/gpx/{gpx_id}` | GET | Получение метаданных |

---

### 7.3 Races Routes

**Файл:** `routes/races.py`

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/races` | GET | Каталог горных гонок |
| `/races/{race_id}` | GET | Карточка гонки |
| `/races/{race_id}/{year}/results` | GET | Результаты за год (все дистанции) |
| `/races/{race_id}/search?name=...` | GET | Поиск участника по всем годам |
| `/races/{race_id}/predict` | POST | Прогноз времени (trail_run или hiking) |

**Зависимости:**
```
races.py
├── RaceRepository (features/races/repository.py) — данные из PostgreSQL
├── RaceCatalog (features/races/catalog.py) — только GPX file lookup
├── RaceService (features/races/service.py) — прогнозы + comparison из БД
└── calculate_stats (features/races/stats.py) — статистика
```

**Данные:** PostgreSQL (16 рас, 47 editions, 203 дистанции, 27K результатов).
**GPX:** `content/races/gpx/` — треки дистанций, маппинг в `races.yaml`.
**Парсинг:** `scripts/batch_parse.py` — CLAX (myrace.info) → БД, ссылки в `catalog.yaml`.

---

### 7.5 Strava Routes

**Файл:** `routes/strava.py`

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/auth/strava` | GET | Начало OAuth |
| `/auth/strava/callback` | GET | OAuth callback |
| `/strava/status/{telegram_id}` | GET | Статус подключения |
| `/strava/disconnect/{telegram_id}` | POST | Отключение |
| `/strava/stats/{telegram_id}` | GET | Статистика атлета |
| `/strava/activities/{telegram_id}` | GET | Список активностей |
| `/strava/sync/{telegram_id}` | POST | Запуск синхронизации |

---

### 7.6 Profile Routes

**Файл:** `routes/profile.py`

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/profile/{telegram_id}` | GET | Получение профиля |
| `/profile/{telegram_id}/calculate` | POST | Пересчёт профиля |
| `/strava/sync-splits/{telegram_id}` | POST | Sync splits |

---

## 8. Telegram Bot

### 8.1 Handlers

| Handler | Файл | Команда/Flow |
|---------|------|-------------|
| prediction | `bot/handlers/prediction.py` | Загрузка GPX → прогноз (hiking) |
| trail_run | `bot/handlers/trail_run.py` | Trail running прогноз |
| races | `bot/handlers/races.py` | `/races` → каталог гонок, прогноз, поиск, статистика |

### 8.2 Races Flow

```
/races → Список горных гонок 2026
  → [Alpine Race — 1 мар]
    → Карточка: 4км ↑900м 🟠
    → [🔮 Мой прогноз]
       → [🏃 Бегом] / [🥾 Пешком]
       → Бегом: выбор темпа (Strava / ручной) → прогноз + перцентиль
       → Пешком: прогноз Tobler/Naismith + перцентиль
    → [🔍 Найти себя]
       → Ввод имени → результаты по всем годам
    → [📊 Статистика]
       → Финишёры, медиана, распределение
    → [📝 Регистрация]
       → Ссылка на athletex.kz
```

### 8.3 API Client

**Файл:** `bot/services/api_client.py`

HTTP клиент для взаимодействия с Backend API.

---

## 9. Потоки данных

### 9.1 Загрузка GPX

```
User → Telegram Bot → POST /gpx/upload → GPXParserService.parse()
                                        → GPXFile saved to DB
                                        → GPXInfo returned
```

### 9.2 Прогноз времени

```
User → POST /predict/hike (gpx_id, telegram_id, params)
       │
       ├─► Load GPXFile from DB
       ├─► Get sun times (sun.py)
       ├─► Load UserPerformanceProfile (optional)
       │
       ├─► IF personalized:
       │   └─► _calculate_personalized_time()
       ├─► ELSE:
       │   └─► naismith_with_descent()
       │
       ├─► Apply multipliers (experience, backpack, group, altitude)
       ├─► Add rest_time, lunch_time
       ├─► Generate warnings
       │
       └─► Return HikePrediction
```

### 9.3 Strava OAuth

```
User → GET /auth/strava?telegram_id=X
       │
       └─► Redirect to Strava OAuth
           │
           └─► User authorizes
               │
               └─► GET /auth/strava/callback?code=Y
                   │
                   ├─► Exchange code for tokens
                   ├─► Save StravaToken
                   ├─► Create/update User
                   ├─► Trigger background sync
                   │
                   └─► Return success page
```

### 9.4 Синхронизация Strava

```
Background Runner (every 5 min)
       │
       └─► For each user in queue:
           │
           ├─► Get valid token (refresh if needed)
           ├─► Fetch activities from Strava API
           ├─► Save to StravaActivity
           │
           └─► For activities needing splits:
               ├─► Fetch detailed activity
               └─► Save to StravaActivitySplit
```

### 9.5 Расчёт профиля

```
POST /profile/{telegram_id}/calculate
       │
       ├─► Load all StravaActivitySplit for user
       ├─► Classify by gradient (flat/uphill/downhill)
       ├─► Calculate average pace per terrain
       ├─► Calculate vertical_ability
       │
       └─► Save UserPerformanceProfile
```

---

## 10. Внешние интеграции

### 10.1 Strava API

**Документация:** https://developers.strava.com/docs/reference/

**Используемые endpoints:**
- `POST /oauth/token` — обмен/refresh токенов
- `GET /athlete` — профиль
- `GET /athletes/{id}/stats` — статистика
- `GET /athlete/activities` — список активностей
- `GET /activities/{id}` — детали активности

**Rate Limits:**
- 200 requests / 15 minutes
- 2,000 requests / day

**Data Policy:**
- Raw data: cache max 7 days
- Aggregated metrics: store indefinitely
- GPS coordinates: do NOT store

### 10.2 Telegram Bot API (Push Notifications)

**Файл:** `shared/telegram.py`

**Документация:** https://core.telegram.org/bots/api

**Используемые endpoints:**
- `POST /bot{token}/sendMessage` — отправка push-уведомлений

**Конфигурация:**
- `TELEGRAM_BOT_TOKEN` — токен бота (env variable)

**Особенности:**
- Fail-silent: ошибки логируются, но не прерывают основной flow
- Timeout: 10 секунд на запрос
- HTML parse mode для форматирования сообщений

**Когда отправляются push:**
- При подключении Strava (`strava_connected`)
- При завершении синхронизации (`sync_complete`)
- При обновлении профиля (`profile_updated`)
- При достижении прогресса синхронизации (`sync_progress`)

---

### 10.3 Astral (Sun times)

**Файл:** `services/sun.py`

Библиотека для расчёта восхода/заката по координатам.

---

## Appendix: Связи между компонентами

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Layer                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ predict  │ │   gpx    │ │  strava  │ │ profile  │ │  users   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
└───────┼────────────┼────────────┼────────────┼────────────┼────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Prediction  │ │  GPXParser  │ │   Strava    │ │ UserProfile │   │
│  │  Service    │ │   Service   │ │   Client    │ │  Service    │   │
│  └──────┬──────┘ └─────────────┘ └──────┬──────┘ └─────────────┘   │
│         │                               │                           │
│         ▼                               ▼                           │
│  ┌─────────────┐                 ┌─────────────┐                   │
│  │ Calculators │                 │ StravaSync  │                   │
│  │ tobler      │                 │  Service    │                   │
│  │ naismith    │                 └─────────────┘                   │
│  │ old_naismith│                                                   │
│  └─────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
        │                               │
        ▼                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                  │
│  ┌──────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │
│  │ User │ │ GPXFile     │ │ StravaToken  │ │ StravaActivity    │   │
│  └──────┘ └─────────────┘ └──────────────┘ │ StravaActivitySplit│  │
│     │                                       │ StravaSyncStatus   │  │
│     └─► UserPerformanceProfile              └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```
