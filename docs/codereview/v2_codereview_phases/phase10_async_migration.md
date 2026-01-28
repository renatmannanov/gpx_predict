# Phase 10: Async Migration

> **Сложность:** 🟡 Средняя
> **Строк:** ~600
> **Файлов:** 15
> **Зависимости:** Phase 9
> **Статус:** ✅ **ЗАВЕРШЕНО** (2026-01-28)

---

## Результат

Все API endpoints мигрированы на async:

| Файл | Session | Endpoints | Статус |
|------|---------|-----------|--------|
| **gpx.py** | ✅ async | 2 | Мигрирован, GPXRepository теперь async |
| **notifications.py** | ✅ async | 3 | Мигрирован, использует NotificationRepository |
| **users.py** | ✅ async | 4 | Мигрирован, использует UserRepository |
| **predict.py** | ✅ async | 4 | Мигрирован, использует async repositories для профилей |
| **profile.py** | 🗑️ удалён | - | Deprecated, удалён (вместо него profiles.py) |
| **profiles.py** | ✅ async | 5 | Не трогали (уже был async) |
| **strava.py** | ✅ async | 9 | Унифицирован на async |

**Итого:** 22 endpoints async (profile.py удалён)

---

## Что было сделано

1. **Удалён profile.py** — deprecated файл, bot использовал только profiles.py
2. **GPXRepository** — переведён на async (create, get_by_id)
3. **Все routes** — используют `get_async_db` и `AsyncSession`
4. **Repositories** — используются везде вместо прямых queries

---

## Актуальное состояние ДО миграции (для истории)

| Файл | Session | Endpoints | Функции | Сервисы |
|------|---------|-----------|---------|---------|
| **gpx.py** | sync (get_db) | 2 | async def | GPXParserService (sync), GPXRepository (sync) |
| **notifications.py** | sync (get_db) | 3 | async def | Прямые DB queries (sync) |
| **users.py** | sync (get_db) | 5 | async def | Прямые DB queries (sync) |
| **predict.py** | sync (get_db) | 4 | async def | PredictionService (sync static), ComparisonService (sync), TrailRunService (sync) |
| **profile.py** | **смешанный** | 5 | async def | UserProfileService (async), StravaSyncService (async) |
| **profiles.py** | ✅ async | 5 | async def | Repositories (async) - **НЕ ТРОГАЕМ** |
| **strava.py** | **смешанный** | 9 | async def | StravaClient (async), часть sync функций |

---

## ⚠️ Важно: Тестовое покрытие

**Критический момент:** В проекте НЕТ интеграционных тестов для API endpoints!

Все существующие тесты - unit-тесты бизнес-логики:
- ✅ Formulas (Tobler, Naismith)
- ✅ Geographic functions
- ✅ Calculators (GAP, fatigue, threshold)
- ❌ **Ни одного теста для endpoints**

**Рекомендация перед Phase 10:**
1. Создать базовые smoke-тесты для каждого endpoint
2. Или тестировать вручную после каждого файла

---

## Проблема

```python
# Текущий код (sync)
from app.db.session import get_db
db: Session = Depends(get_db)

# Правильный код (async)
from app.db.session import get_async_db
db: AsyncSession = Depends(get_async_db)
```

**Почему это плохо:**
- Смешение sync/async = технический долг
- Sync блокирует event loop
- Новый код (repositories) async, старый sync = несовместимость

---

## Scope

### Endpoints для миграции

| Файл | Endpoints | Текущее состояние | Действие |
|------|-----------|-------------------|----------|
| `gpx.py` | 2 | sync Session, async def | Полная миграция |
| `notifications.py` | 3 | sync Session, async def | Полная миграция |
| `users.py` | 5 | sync Session, async def | Полная миграция |
| `predict.py` | 4 | sync Session, async def | Полная миграция + проверить сервисы |
| `profile.py` | 5 | **смешанный** | Удалить (deprecated) или унифицировать |
| `strava.py` | 9 | **смешанный** (4 sync, 5 async) | Унифицировать на async |
| `profiles.py` | 5 | ✅ async | **НЕ ТРОГАЕМ** |

**Примечание:** profile.py deprecated в пользу profiles.py - рассмотреть удаление.

---

## Чеклист по файлам

### 1. strava.py (9 endpoints - смешанный)

**Текущее состояние:** 4 endpoint'а используют sync get_db, 5 используют async get_async_db

- [ ] Унифицировать все на `get_async_db`
- [ ] Проверить sync функции: `exchange_authorization_code`, `fetch_athlete_stats`, `revoke_access`
- [ ] Endpoints:
  - [ ] `GET /auth/strava` - инициировать OAuth
  - [ ] `GET /auth/strava/callback` - OAuth callback
  - [ ] `GET /strava/status/{telegram_id}`
  - [ ] `POST /strava/disconnect/{telegram_id}`
  - [ ] `GET /strava/stats/{telegram_id}`
  - [ ] `GET /strava/activities/{telegram_id}`
  - [ ] `GET /strava/sync-status/{telegram_id}`
  - [ ] `POST /strava/sync/{telegram_id}`
  - [ ] `GET /strava/admin/sync-stats`

### 2. users.py (5 endpoints)

- [ ] Заменить импорт: `get_db` → `get_async_db`
- [ ] Заменить тип: `Session` → `AsyncSession`
- [ ] Использовать `UserRepository` вместо прямых запросов
- [ ] Endpoints:
  - [ ] `GET /users/me`
  - [ ] `GET /users/{telegram_id}`
  - [ ] `POST /users`
  - [ ] `POST /users/{telegram_id}/onboarding`
  - [ ] `PUT /users/{telegram_id}/preferences`

### 3. predict.py (4 endpoints)

- [ ] Заменить импорт: `get_db` → `get_async_db`
- [ ] Заменить тип: `Session` → `AsyncSession`
- [ ] Endpoints:
  - [ ] `POST /predict/hiking`
  - [ ] `POST /predict/trail-run`
  - [ ] `POST /predict/compare`
  - [ ] `POST /predict/from-gpx`

### 4. notifications.py (3 endpoints)

- [ ] Заменить импорт: `get_db` → `get_async_db`
- [ ] Заменить тип: `Session` → `AsyncSession`
- [ ] Использовать `NotificationRepository`
- [ ] Endpoints:
  - [ ] `GET /notifications/{telegram_id}`
  - [ ] `POST /notifications/{telegram_id}/read`
  - [ ] `POST /notifications/{telegram_id}/read-all`

### 5. gpx.py (2 endpoints)

- [ ] Заменить импорт: `get_db` → `get_async_db`
- [ ] Заменить тип: `Session` → `AsyncSession`
- [ ] Endpoints:
  - [ ] `POST /gpx/upload`
  - [ ] `POST /gpx/analyze`

### 6. profile.py (5 endpoints) - УДАЛИТЬ

**Текущее состояние:** Смешанный (get_db + get_async_db в одном файле!)

**Проверено 2026-01-28:** Bot НЕ использует старые endpoints. Все вызовы идут через `/api/v1/profiles/...`

**Действие:** Удалить файл полностью

- [ ] Удалить `backend/app/api/v1/routes/profile.py`
- [ ] Убрать из `backend/app/api/v1/router.py`:
  ```python
  # Удалить эти строки:
  from app.api.v1.routes import ... profile ...
  api_router.include_router(profile.router, tags=["Profile (deprecated)"])
  ```

Mapping (для справки, если кто-то использовал старые endpoints напрямую):
- `GET /profile/{telegram_id}` → `GET /profiles/{telegram_id}/hiking`
- `GET /profile/{telegram_id}/run` → `GET /profiles/{telegram_id}/trail-run`
- `POST /profile/{telegram_id}/calculate` → `POST /profiles/{telegram_id}/hiking/calculate`
- `POST /profile/{telegram_id}/run/calculate` → `POST /profiles/{telegram_id}/trail-run/calculate`
- `POST /strava/sync-splits/{telegram_id}` → `POST /profiles/{telegram_id}/sync-splits`

---

## Паттерн миграции

### Шаг 1: Импорты

**До:**
```python
from sqlalchemy.orm import Session
from app.db.session import get_db
```

**После:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_db
```

### Шаг 2: Dependency

**До:**
```python
def get_user(telegram_id: str, db: Session = Depends(get_db)):
```

**После:**
```python
async def get_user(telegram_id: str, db: AsyncSession = Depends(get_async_db)):
```

### Шаг 3: DB операции

**До:**
```python
user = db.query(User).filter(User.telegram_id == telegram_id).first()
```

**После (вариант A - через repository):**
```python
repo = UserRepository(db)
user = await repo.get_by_telegram_id(telegram_id)
```

**После (вариант B - напрямую):**
```python
result = await db.execute(
    select(User).where(User.telegram_id == telegram_id)
)
user = result.scalar_one_or_none()
```

### Шаг 4: Commit/Flush

**До:**
```python
db.add(user)
db.commit()
db.refresh(user)
```

**После:**
```python
db.add(user)
await db.commit()
await db.refresh(user)
```

---

## Сервисы для обновления

Некоторые сервисы тоже нужно сделать async:

- [ ] `services/prediction.py` - если используется sync Session
- [ ] `services/strava_sync.py` - частично async
- [ ] `services/user_profile.py` - проверить

---

## Проверка после каждого файла

```bash
# 1. Тесты
python -m pytest tests/ -v

# 2. Запустить backend
uvicorn app.main:app --reload

# 3. Проверить endpoint
curl http://localhost:8000/api/v1/users/test123
```

---

## Порядок миграции

Рекомендуемый порядок (от простого к сложному):

1. `gpx.py` - простой, мало зависимостей
2. `notifications.py` - уже есть NotificationRepository
3. `users.py` - есть UserRepository
4. `predict.py` - может потребовать изменений в services
5. `strava.py` - самый сложный, много логики
6. `profile.py` - deprecated, можно в конце или удалить

---

## Результат

- ✅ Все endpoints async
- ✅ Единый подход к DB операциям
- ✅ Repositories используются везде
- ✅ Нет блокировки event loop

---

## ⚠️ Риски и mitigation

### Риск 1: Нет тестов для endpoints

**Mitigation:**
- Ручное тестирование каждого endpoint после миграции
- Или создать минимальные smoke-тесты перед началом

```bash
# Минимальная проверка после каждого файла
curl -X GET http://localhost:8000/api/v1/health
curl -X GET http://localhost:8000/api/v1/users/test123
# ... и т.д.
```

### Риск 2: Sync сервисы

Некоторые сервисы sync (PredictionService, ComparisonService). Они вызываются из async endpoints.

**Это ОК если:**
- Сервисы не делают I/O (только CPU-bound расчёты)
- Нет обращений к БД внутри сервиса

**Нужен рефакторинг если:**
- Сервис делает DB queries внутри

### Риск 3: profile.py смешивает sync/async

Файл уже частично async, но с багами:
- Часть endpoints используют get_db
- Часть используют get_async_db
- Это legacy код

**Решение:** Удалить profile.py, использовать только profiles.py

---

*Phase 10 of v2.1 cleanup*
