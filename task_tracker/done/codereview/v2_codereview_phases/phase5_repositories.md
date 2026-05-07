# Phase 5: Repository Pattern

> **Статус:** Не начато
> **Оценка:** ~300 строк изменений
> **Зависимости:** Phase 0f, Phase 1
> **Ветка:** `refactor/phase-5-repositories`
> **Цель:** Вынести queries из routes в repositories

---

## Проблема

Сейчас только `GPXRepository` существует. Все остальные queries прямо в routes:

```python
# routes/strava.py — прямые queries
user = db.query(User).filter(User.telegram_id == telegram_id).first()
token = db.query(StravaToken).filter(StravaToken.user_id == user.id).first()
activities = db.query(StravaActivity).filter(...).all()
```

---

## Задачи

### 5.1 Создать BaseRepository

**`backend/app/shared/repository.py`:**

```python
"""Base repository with common CRUD operations."""
from typing import TypeVar, Generic, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository for database operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: AsyncSession):
                super().__init__(db, User)

            async def get_by_telegram_id(self, telegram_id: str) -> User | None:
                return await self.get_by(telegram_id=telegram_id)
    """

    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    async def get_by_id(self, id: str) -> T | None:
        """Get entity by ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by(self, **kwargs) -> T | None:
        """Get entity by arbitrary fields."""
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, **kwargs) -> list[T]:
        """Get all entities matching criteria."""
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        """Create new entity."""
        entity = self.model(**kwargs)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: T, **kwargs) -> T:
        """Update entity fields."""
        for key, value in kwargs.items():
            setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """Delete entity."""
        await self.db.delete(entity)
        await self.db.flush()
```

### 5.2 Создать feature repositories

**`backend/app/features/users/repository.py`:**

```python
"""User repository."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.repository import BaseRepository
from .models import User, Notification


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_telegram_id(self, telegram_id: str) -> User | None:
        """Get user by Telegram ID."""
        return await self.get_by(telegram_id=telegram_id)

    async def get_with_profiles(self, telegram_id: str) -> User | None:
        """Get user with hiking and run profiles loaded."""
        result = await self.db.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(
                selectinload(User.hiking_profile),
                selectinload(User.run_profile)
            )
        )
        return result.scalar_one_or_none()

    async def create_or_get(self, telegram_id: str, **kwargs) -> tuple[User, bool]:
        """Get existing user or create new one."""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = await self.create(telegram_id=telegram_id, **kwargs)
        return user, True


class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Notification)

    async def get_unread(self, user_id: str) -> list[Notification]:
        """Get unread notifications for user."""
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.read == False)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_as_read(self, notification_ids: list[int]) -> None:
        """Mark notifications as read."""
        for nid in notification_ids:
            notif = await self.get_by_id(nid)
            if notif:
                await self.update(notif, read=True)
```

**`backend/app/features/strava/repository.py`:**

```python
"""Strava repositories."""
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.repository import BaseRepository
from .models import StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus


class StravaTokenRepository(BaseRepository[StravaToken]):
    """Repository for Strava tokens."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaToken)

    async def get_by_user_id(self, user_id: str) -> StravaToken | None:
        """Get token for user."""
        return await self.get_by(user_id=user_id)

    async def get_by_athlete_id(self, athlete_id: int) -> StravaToken | None:
        """Get token by Strava athlete ID."""
        return await self.get_by(strava_athlete_id=athlete_id)


class StravaActivityRepository(BaseRepository[StravaActivity]):
    """Repository for Strava activities."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaActivity)

    async def get_by_strava_id(self, strava_id: int) -> StravaActivity | None:
        """Get activity by Strava ID."""
        return await self.get_by(strava_id=strava_id)

    async def get_user_activities(
        self,
        user_id: str,
        activity_type: str | None = None,
        limit: int = 10,
        offset: int = 0
    ) -> list[StravaActivity]:
        """Get user activities with pagination."""
        query = (
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .order_by(desc(StravaActivity.start_date))
            .offset(offset)
            .limit(limit)
        )
        if activity_type:
            query = query.where(StravaActivity.activity_type == activity_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_with_splits(self, activity_id: int) -> StravaActivity | None:
        """Get activity with splits loaded."""
        result = await self.db.execute(
            select(StravaActivity)
            .where(StravaActivity.id == activity_id)
            .options(selectinload(StravaActivity.splits))
        )
        return result.scalar_one_or_none()


class SyncStatusRepository(BaseRepository[StravaSyncStatus]):
    """Repository for sync status."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaSyncStatus)

    async def get_by_user_id(self, user_id: str) -> StravaSyncStatus | None:
        """Get sync status for user."""
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> StravaSyncStatus:
        """Get existing or create new sync status."""
        status = await self.get_by_user_id(user_id)
        if not status:
            status = await self.create(user_id=user_id)
        return status
```

**`backend/app/features/hiking/repository.py`:**

```python
"""Hiking profile repository."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.repository import BaseRepository
from .models import UserHikingProfile


class HikingProfileRepository(BaseRepository[UserHikingProfile]):
    """Repository for hiking profiles."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserHikingProfile)

    async def get_by_user_id(self, user_id: str) -> UserHikingProfile | None:
        """Get hiking profile for user."""
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> UserHikingProfile:
        """Get existing or create empty profile."""
        profile = await self.get_by_user_id(user_id)
        if not profile:
            profile = await self.create(user_id=user_id)
        return profile
```

### 5.3 Обновить routes

**Пример — `routes/strava.py`:**

```python
# Было
@router.get("/strava/status/{telegram_id}")
async def get_strava_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    token = db.query(StravaToken).filter(StravaToken.user_id == user.id).first()
    ...

# Стало
@router.get("/strava/status/{telegram_id}")
async def get_strava_status(telegram_id: str, db: AsyncSession = Depends(get_async_db)):
    user_repo = UserRepository(db)
    token_repo = StravaTokenRepository(db)

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    token = await token_repo.get_by_user_id(user.id)
    ...
```

### 5.4 Dependency Injection для repositories (опционально)

```python
# Можно создать dependency
def get_user_repo(db: AsyncSession = Depends(get_async_db)) -> UserRepository:
    return UserRepository(db)

# Использование в route
@router.get("/users/{telegram_id}")
async def get_user(
    telegram_id: str,
    user_repo: UserRepository = Depends(get_user_repo)
):
    return await user_repo.get_by_telegram_id(telegram_id)
```

---

## Файлы для изменения

```
NEW:
backend/app/shared/repository.py
backend/app/features/users/repository.py
backend/app/features/strava/repository.py
backend/app/features/hiking/repository.py
backend/app/features/trail_run/repository.py

UPDATE:
backend/app/shared/__init__.py (export BaseRepository)
backend/app/features/*/\ __init__.py (export repositories)
backend/app/api/v1/routes/strava.py (use repositories)
backend/app/api/v1/routes/profile.py (use repositories)
backend/app/api/v1/routes/users.py (use repositories)
backend/app/api/v1/routes/notifications.py (use repositories)
```

---

## Критерии завершения

- [ ] `BaseRepository` создан в `shared/`
- [ ] Каждый feature имеет `repository.py`
- [ ] Routes используют repositories вместо прямых queries
- [ ] Нет `db.query()` в routes
- [ ] Приложение работает

---

*Phase 5 — Repository Pattern*
