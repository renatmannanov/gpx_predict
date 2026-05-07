# Phase 0e: Move and Split Strava Module

> **Статус:** Не начато
> **Оценка:** ~300 строк изменений
> **Зависимости:** Phase 0b
> **Ветка:** `refactor/phase-0e-strava`
> **Цель:** Разбить strava.py (716 строк) и strava_sync.py (1125 строк) на модули

---

## Проблема

Огромные файлы:
- `services/strava.py` — 716 строк (OAuth + API client смешаны)
- `services/strava_sync.py` — 1125 строк (слишком много ответственностей)

---

## Текущее расположение

```
backend/app/
├── models/
│   ├── strava_token.py          # StravaToken
│   └── strava_activity.py       # StravaActivity, Splits, SyncStatus
└── services/
    ├── strava.py                # OAuth + API client (716 строк!)
    └── strava_sync.py           # Sync service (1125 строк!)
```

---

## Целевая структура

```
backend/app/features/strava/
├── __init__.py
├── models.py                    # StravaToken, StravaActivity, Splits, SyncStatus
├── schemas.py                   # Pydantic schemas
├── oauth.py                     # OAuth flow only (~200 строк)
├── client.py                    # API client only (~300 строк)
├── sync/
│   ├── __init__.py
│   ├── service.py               # Orchestration (~250 строк)
│   ├── activities.py            # Activity sync (~200 строк)
│   └── splits.py                # Splits sync (~150 строк)
└── README.md
```

---

## Задачи

### 0e.1 Перенести модели
- [ ] Создать `features/strava/models.py`:
  ```python
  """
  Strava-related database models.
  """
  from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
  from sqlalchemy.orm import relationship
  from sqlalchemy.dialects.postgresql import UUID

  from app.models.base import Base


  class StravaToken(Base):
      """OAuth tokens for Strava API."""
      __tablename__ = "strava_tokens"
      # ... копировать из models/strava_token.py ...


  class StravaActivity(Base):
      """Synchronized Strava activity."""
      __tablename__ = "strava_activities"
      # ... копировать из models/strava_activity.py ...


  class StravaActivitySplit(Base):
      """Kilometer split data for activity."""
      __tablename__ = "strava_activity_splits"
      # ... копировать из models/strava_activity.py ...


  class StravaSyncStatus(Base):
      """Sync status per user."""
      __tablename__ = "strava_sync_status"
      # ... копировать из models/strava_activity.py ...
  ```

- [ ] Обновить старые файлы для re-export:
  ```python
  # models/strava_token.py
  """DEPRECATED: Use app.features.strava.models"""
  from app.features.strava.models import StravaToken
  __all__ = ["StravaToken"]

  # models/strava_activity.py
  """DEPRECATED: Use app.features.strava.models"""
  from app.features.strava.models import (
      StravaActivity,
      StravaActivitySplit,
      StravaSyncStatus,
  )
  __all__ = ["StravaActivity", "StravaActivitySplit", "StravaSyncStatus"]
  ```

### 0e.2 Создать oauth.py (выделить из strava.py)
- [ ] Создать `features/strava/oauth.py`:
  ```python
  """
  Strava OAuth flow.

  Handles:
  - Authorization URL generation
  - Code exchange for tokens
  - Token refresh
  """
  import httpx
  from typing import Optional
  from datetime import datetime

  from app.core.config import settings


  class StravaOAuth:
      """
      Strava OAuth handler.

      Usage:
          oauth = StravaOAuth()
          auth_url = oauth.get_authorization_url(state="telegram_123")
          tokens = await oauth.exchange_code(code)
          tokens = await oauth.refresh_token(refresh_token)
      """

      AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
      TOKEN_URL = "https://www.strava.com/oauth/token"

      def __init__(self):
          self.client_id = settings.STRAVA_CLIENT_ID
          self.client_secret = settings.STRAVA_CLIENT_SECRET

      def get_authorization_url(self, state: str) -> str:
          """Generate OAuth authorization URL."""
          # ... логика из strava.py ...

      async def exchange_code(self, code: str) -> dict:
          """Exchange authorization code for tokens."""
          # ... логика из strava.py ...

      async def refresh_token(self, refresh_token: str) -> dict:
          """Refresh access token."""
          # ... логика из strava.py ...
  ```

### 0e.3 Создать client.py (выделить из strava.py)
- [ ] Создать `features/strava/client.py`:
  ```python
  """
  Strava API client.

  Provides methods for interacting with Strava API.
  Handles rate limiting and token management.
  """
  import httpx
  from typing import Optional, List
  from datetime import datetime

  from .oauth import StravaOAuth


  class StravaClient:
      """
      Strava API client.

      Usage:
          client = StravaClient(access_token)
          athlete = await client.get_athlete()
          activities = await client.get_activities(per_page=30)
      """

      API_BASE = "https://www.strava.com/api/v3"

      def __init__(self, access_token: str):
          self.access_token = access_token
          self._client: Optional[httpx.AsyncClient] = None

      async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
          """Make authenticated API request."""
          # ... логика из strava.py ...

      async def get_athlete(self) -> dict:
          """Get authenticated athlete profile."""
          return await self._request("GET", "/athlete")

      async def get_athlete_stats(self, athlete_id: int) -> dict:
          """Get athlete statistics."""
          return await self._request("GET", f"/athletes/{athlete_id}/stats")

      async def get_activities(
          self,
          after: Optional[datetime] = None,
          before: Optional[datetime] = None,
          per_page: int = 30,
          page: int = 1,
      ) -> List[dict]:
          """Get list of activities."""
          # ... логика из strava.py ...

      async def get_activity(self, activity_id: int) -> dict:
          """Get detailed activity with splits."""
          return await self._request("GET", f"/activities/{activity_id}")

      async def close(self):
          """Close HTTP client."""
          if self._client:
              await self._client.aclose()
  ```

### 0e.4 Разбить strava_sync.py на модули

- [ ] Создать `features/strava/sync/service.py` (~250 строк):
  ```python
  """
  Strava sync orchestration.

  Coordinates activity and splits synchronization.
  """
  from sqlalchemy.ext.asyncio import AsyncSession
  from typing import Optional

  from ..client import StravaClient
  from ..models import StravaToken, StravaSyncStatus
  from .activities import ActivitySyncService
  from .splits import SplitsSyncService


  class StravaSyncService:
      """
      Main sync orchestrator.

      Usage:
          service = StravaSyncService(db)
          await service.sync_user(telegram_id)
      """

      def __init__(self, db: AsyncSession):
          self.db = db
          self.activity_sync = ActivitySyncService(db)
          self.splits_sync = SplitsSyncService(db)

      async def sync_user(self, telegram_id: str) -> dict:
          """Full sync for user."""
          # ... orchestration logic ...

      async def get_sync_status(self, telegram_id: str) -> StravaSyncStatus:
          """Get current sync status."""
          # ...
  ```

- [ ] Создать `features/strava/sync/activities.py` (~200 строк):
  ```python
  """
  Activity synchronization.
  """
  from sqlalchemy.ext.asyncio import AsyncSession
  from typing import List

  from ..client import StravaClient
  from ..models import StravaActivity


  class ActivitySyncService:
      """Sync activities from Strava."""

      def __init__(self, db: AsyncSession):
          self.db = db

      async def sync_activities(
          self,
          client: StravaClient,
          user_id: str,
          full_sync: bool = False
      ) -> List[StravaActivity]:
          """Sync user's activities."""
          # ... логика из strava_sync.py ...

      async def _save_activity(self, activity_data: dict, user_id: str) -> StravaActivity:
          """Save single activity to DB."""
          # ...
  ```

- [ ] Создать `features/strava/sync/splits.py` (~150 строк):
  ```python
  """
  Splits synchronization.
  """
  from sqlalchemy.ext.asyncio import AsyncSession
  from typing import List

  from ..client import StravaClient
  from ..models import StravaActivity, StravaActivitySplit


  class SplitsSyncService:
      """Sync activity splits from Strava."""

      def __init__(self, db: AsyncSession):
          self.db = db

      async def sync_splits(
          self,
          client: StravaClient,
          activity: StravaActivity
      ) -> List[StravaActivitySplit]:
          """Sync splits for single activity."""
          # ... логика из strava_sync.py ...

      async def sync_all_pending(
          self,
          client: StravaClient,
          user_id: str
      ) -> int:
          """Sync splits for all activities missing them."""
          # ...
  ```

- [ ] Создать `features/strava/sync/__init__.py`:
  ```python
  """
  Strava sync services.
  """
  from .service import StravaSyncService
  from .activities import ActivitySyncService
  from .splits import SplitsSyncService

  __all__ = [
      "StravaSyncService",
      "ActivitySyncService",
      "SplitsSyncService",
  ]
  ```

### 0e.5 Создать features/strava/__init__.py
- [ ] Обновить файл:
  ```python
  """
  Strava integration module.

  Usage:
      from app.features.strava import StravaOAuth, StravaClient
      from app.features.strava.sync import StravaSyncService

  Components:
  - StravaOAuth: OAuth flow (auth URL, token exchange, refresh)
  - StravaClient: API client (get athlete, activities, splits)
  - StravaSyncService: Background synchronization
  """
  from .models import StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus
  from .oauth import StravaOAuth
  from .client import StravaClient

  __all__ = [
      "StravaToken",
      "StravaActivity",
      "StravaActivitySplit",
      "StravaSyncStatus",
      "StravaOAuth",
      "StravaClient",
  ]
  ```

### 0e.6 Создать README.md
- [ ] Создать `features/strava/README.md`:
  ```markdown
  # Strava Module

  ## Purpose
  Integration with Strava API for activity synchronization.

  ## Public API
  ```python
  from app.features.strava import StravaOAuth, StravaClient
  from app.features.strava.sync import StravaSyncService
  ```

  ## OAuth Flow
  1. Generate auth URL: `StravaOAuth().get_authorization_url(state)`
  2. User authorizes on Strava
  3. Exchange code: `await oauth.exchange_code(code)`
  4. Refresh when expired: `await oauth.refresh_token(token)`

  ## Sync Flow
  1. Get valid token
  2. Fetch activities: `ActivitySyncService`
  3. Fetch splits: `SplitsSyncService`
  4. Update profiles (in hiking/trail_run modules)

  ## Rate Limits
  - 200 requests / 15 minutes
  - 2000 requests / day

  ## Files
  | File | Lines | Description |
  |------|-------|-------------|
  | models.py | ~150 | All Strava models |
  | oauth.py | ~150 | OAuth flow |
  | client.py | ~200 | API client |
  | sync/service.py | ~200 | Sync orchestration |
  | sync/activities.py | ~150 | Activity sync |
  | sync/splits.py | ~100 | Splits sync |
  ```

### 0e.7 Обновить старые файлы для обратной совместимости
- [ ] `services/strava.py`:
  ```python
  """
  DEPRECATED: Use app.features.strava

  Re-exports for backward compatibility.
  """
  from app.features.strava import StravaOAuth, StravaClient
  from app.features.strava.models import StravaToken

  # Legacy class name
  StravaService = StravaClient

  __all__ = ["StravaOAuth", "StravaClient", "StravaService", "StravaToken"]
  ```

- [ ] `services/strava_sync.py`:
  ```python
  """
  DEPRECATED: Use app.features.strava.sync

  Re-exports for backward compatibility.
  """
  from app.features.strava.sync import StravaSyncService

  __all__ = ["StravaSyncService"]
  ```

---

## Файлы для создания/изменения

```
NEW:
backend/app/features/strava/models.py
backend/app/features/strava/oauth.py
backend/app/features/strava/client.py
backend/app/features/strava/sync/service.py
backend/app/features/strava/sync/activities.py
backend/app/features/strava/sync/splits.py
backend/app/features/strava/README.md

UPDATE:
backend/app/features/strava/__init__.py
backend/app/features/strava/sync/__init__.py
backend/app/models/strava_token.py (re-export)
backend/app/models/strava_activity.py (re-export)
backend/app/services/strava.py (re-export)
backend/app/services/strava_sync.py (re-export)
```

---

## Критерии завершения

- [ ] strava.py разбит на oauth.py + client.py
- [ ] strava_sync.py разбит на sync/service.py + activities.py + splits.py
- [ ] Все файлы < 300 строк
- [ ] Старые импорты работают
- [ ] Приложение запускается

---

## Проверка

```bash
cd backend

# Новые импорты
python -c "from app.features.strava import StravaOAuth, StravaClient; print('OK')"
python -c "from app.features.strava.sync import StravaSyncService; print('OK')"

# Старые импорты
python -c "from app.services.strava import StravaService; print('OK')"
python -c "from app.services.strava_sync import StravaSyncService; print('OK')"

# Приложение
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0e - split and move strava module

- Split strava.py (716 lines) into oauth.py + client.py
- Split strava_sync.py (1125 lines) into sync/service.py, activities.py, splits.py
- Move all Strava models to features/strava/models.py
- Add backward compatibility re-exports
- All files now < 300 lines

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0e-strava
```

---

*Phase 0e — Move and Split Strava Module*
