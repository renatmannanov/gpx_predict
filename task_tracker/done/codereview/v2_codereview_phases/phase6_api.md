# Phase 6: API Cleanup

> **Статус:** Не начато
> **Оценка:** ~200 строк изменений
> **Зависимости:** Phase 2, Phase 5
> **Ветка:** `refactor/phase-6-api`
> **Цель:** Унифицировать API endpoints, сделать routes тонкими

---

## Проблемы

1. **Inconsistent profile endpoints:**
   - `GET /profile/{id}` — hiking
   - `GET /profile/{id}/run` — trail run
   - Не интуитивно

2. **Бизнес-логика в routes** вместо services

3. **Token management дублирование** в routes/strava.py

---

## Задачи

### 6.1 Унифицировать profile endpoints

**Было:**
```
GET  /profile/{telegram_id}              → hiking profile
GET  /profile/{telegram_id}/run          → run profile
POST /profile/{telegram_id}/calculate    → calc hiking
POST /profile/{telegram_id}/run/calculate → calc run
```

**Стало:**
```
GET  /api/v1/profiles/{telegram_id}/hiking      → hiking profile
GET  /api/v1/profiles/{telegram_id}/trail-run   → trail run profile
POST /api/v1/profiles/{telegram_id}/hiking/calculate
POST /api/v1/profiles/{telegram_id}/trail-run/calculate
```

### 6.2 Реорганизовать routes

**`backend/app/api/v1/routes/profiles.py`** (новый файл):

```python
"""Profile management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.features.hiking import HikingProfileRepository, HikingProfileService
from app.features.trail_run import TrailRunProfileRepository, TrailRunProfileService
from app.features.users import UserRepository

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/{telegram_id}/hiking")
async def get_hiking_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's hiking profile."""
    user_repo = UserRepository(db)
    profile_repo = HikingProfileRepository(db)

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return {"has_profile": False}

    return {
        "has_profile": True,
        "profile": profile.to_dict()
    }


@router.get("/{telegram_id}/trail-run")
async def get_trail_run_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's trail run profile."""
    user_repo = UserRepository(db)
    profile_repo = TrailRunProfileRepository(db)

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return {"has_profile": False}

    return {
        "has_profile": True,
        "profile": profile.to_dict()
    }


@router.post("/{telegram_id}/hiking/calculate")
async def calculate_hiking_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Recalculate hiking profile from Strava data."""
    service = HikingProfileService(db)
    result = await service.calculate_profile(telegram_id)
    return result


@router.post("/{telegram_id}/trail-run/calculate")
async def calculate_trail_run_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Recalculate trail run profile from Strava data."""
    service = TrailRunProfileService(db)
    result = await service.calculate_profile(telegram_id)
    return result
```

### 6.3 Удалить token management из routes

**Было в `routes/strava.py`:**
```python
def _get_valid_token_sync(db: Session, user_id: str) -> StravaToken | None:
    """Get valid token, refreshing if needed."""
    token = db.query(StravaToken).filter(...).first()
    if token and token.is_expired():
        # refresh logic...
    return token
```

**Стало — использовать StravaClient:**
```python
from app.features.strava import StravaClient

@router.get("/strava/stats/{telegram_id}")
async def get_strava_stats(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    client = StravaClient(db)
    stats = await client.get_athlete_stats(telegram_id)
    return stats
```

### 6.4 Сделать routes тонкими

Правило: Route только:
1. Валидирует input (Pydantic делает автоматически)
2. Вызывает service
3. Возвращает response

**Пример тонкого route:**
```python
@router.post("/predict/hike")
async def predict_hike(
    request: HikePredictRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Make hiking time prediction."""
    service = HikingPredictionService(db)
    return await service.predict(request)
```

**НЕ делать так:**
```python
@router.post("/predict/hike")
async def predict_hike(request: HikePredictRequest, db: AsyncSession = ...):
    # ❌ Бизнес-логика в route
    gpx = await db.execute(select(GPXFile).where(...))
    user = await db.execute(select(User).where(...))
    profile = await db.execute(select(UserHikingProfile).where(...))

    calculator = ToblerCalculator()
    segments = calculator.calculate(gpx.points)

    if profile:
        personalization = PersonalizationService(profile)
        segments = personalization.adjust(segments)

    # ... 50 строк логики
    return result
```

### 6.5 Обновить router.py

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from .routes import gpx, predict, strava, profiles, users, notifications

api_router = APIRouter()

api_router.include_router(gpx.router)
api_router.include_router(predict.router)
api_router.include_router(strava.router)
api_router.include_router(profiles.router)  # Новый
api_router.include_router(users.router)
api_router.include_router(notifications.router)
```

### 6.6 Обновить bot api_client

После изменения endpoints нужно обновить bot:

```python
# bot/services/clients/hiking.py

async def get_profile(self, telegram_id: str) -> dict:
    """Get hiking profile."""
    # Было: /api/v1/profile/{telegram_id}
    # Стало:
    return await self._get(f"/api/v1/profiles/{telegram_id}/hiking")

async def calculate_profile(self, telegram_id: str) -> dict:
    """Recalculate hiking profile."""
    # Было: /api/v1/profile/{telegram_id}/calculate
    # Стало:
    return await self._post(f"/api/v1/profiles/{telegram_id}/hiking/calculate")
```

---

## Файлы для изменения

```
NEW:
backend/app/api/v1/routes/profiles.py

DELETE (или сильно упростить):
backend/app/api/v1/routes/profile.py

UPDATE:
backend/app/api/v1/router.py
backend/app/api/v1/routes/strava.py (remove token management)
backend/app/api/v1/routes/predict.py (thin routes)
bot/services/clients/hiking.py (new endpoints)
bot/services/clients/trail_run.py (new endpoints)
```

---

## Критерии завершения

- [ ] Profile endpoints унифицированы
- [ ] Нет бизнес-логики в routes (только service calls)
- [ ] Нет `_get_valid_token_sync` в routes
- [ ] Bot обновлён на новые endpoints
- [ ] Приложение работает
- [ ] Бот работает

---

*Phase 6 — API Cleanup*
