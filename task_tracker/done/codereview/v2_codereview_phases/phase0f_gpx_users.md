# Phase 0f: Move GPX and Users Modules

> **Статус:** Не начато
> **Оценка:** ~150 строк изменений
> **Зависимости:** Phase 0b
> **Ветка:** `refactor/phase-0f-gpx-users`
> **Цель:** Перенести GPX и Users модули в features/

---

## Текущее расположение

```
backend/app/
├── models/
│   ├── gpx.py                   # GPXFile
│   ├── user.py                  # User
│   └── notification.py          # Notification
├── services/
│   └── gpx_parser.py            # GPXParserService
├── repositories/
│   └── gpx.py                   # GPXRepository
└── api/v1/routes/
    ├── gpx.py
    └── users.py
```

---

## Целевая структура

```
backend/app/features/
├── gpx/
│   ├── __init__.py
│   ├── models.py                # GPXFile
│   ├── schemas.py               # GPXInfo, etc.
│   ├── parser.py                # GPXParserService
│   ├── segmenter.py             # RouteSegmenter (из calculators/)
│   ├── repository.py            # GPXRepository
│   └── README.md
│
└── users/
    ├── __init__.py
    ├── models.py                # User, Notification
    ├── schemas.py               # UserCreate, etc.
    ├── service.py               # UserService (stub)
    ├── repository.py            # UserRepository (stub)
    └── README.md
```

---

## Задачи

### 0f.1 Перенести GPX модуль

- [ ] Создать `features/gpx/models.py`:
  ```python
  """
  GPX file model.
  """
  from sqlalchemy import Column, String, Float, LargeBinary, DateTime
  from sqlalchemy.dialects.postgresql import UUID
  import uuid

  from app.models.base import Base


  class GPXFile(Base):
      """
      Stored GPX file with metadata.
      """
      __tablename__ = "gpx_files"

      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      filename = Column(String, nullable=False)
      gpx_content = Column(LargeBinary, nullable=False)
      # ... остальные поля из models/gpx.py ...
  ```

- [ ] Скопировать `services/gpx_parser.py` → `features/gpx/parser.py`
  - Обновить импорты на `from app.shared import haversine`

- [ ] Скопировать `services/calculators/segmenter.py` → `features/gpx/segmenter.py`
  - RouteSegmenter используется и для hiking, и для trail_run
  - Логично держать рядом с парсером GPX

- [ ] Скопировать `repositories/gpx.py` → `features/gpx/repository.py`

- [ ] Создать `features/gpx/schemas.py`:
  ```python
  """
  GPX-related schemas.
  """
  from pydantic import BaseModel
  from typing import List, Optional, Tuple


  class GPXPoint(BaseModel):
      """Single point in GPX."""
      lat: float
      lon: float
      elevation: float


  class GPXInfo(BaseModel):
      """Parsed GPX information."""
      name: Optional[str]
      distance_km: float
      elevation_gain_m: float
      elevation_loss_m: float
      max_elevation_m: float
      min_elevation_m: float
      points_count: int


  class GPXUploadResponse(BaseModel):
      """Response for GPX upload."""
      gpx_id: str
      filename: str
      info: GPXInfo
  ```

- [ ] Создать `features/gpx/__init__.py`:
  ```python
  """
  GPX file handling module.

  Usage:
      from app.features.gpx import GPXFile, GPXParserService, GPXRepository
  """
  from .models import GPXFile
  from .parser import GPXParserService
  from .segmenter import RouteSegmenter
  from .repository import GPXRepository
  from .schemas import GPXInfo, GPXPoint, GPXUploadResponse

  __all__ = [
      "GPXFile",
      "GPXParserService",
      "RouteSegmenter",
      "GPXRepository",
      "GPXInfo",
      "GPXPoint",
      "GPXUploadResponse",
  ]
  ```

- [ ] Создать `features/gpx/README.md`:
  ```markdown
  # GPX Module

  ## Purpose
  GPX file parsing, storage, and route segmentation.

  ## Public API
  ```python
  from app.features.gpx import (
      GPXFile,
      GPXParserService,
      RouteSegmenter,
      GPXRepository,
  )
  ```

  ## Components

  | Component | Description |
  |-----------|-------------|
  | GPXFile | SQLAlchemy model for stored GPX |
  | GPXParserService | Parse GPX files, extract points |
  | RouteSegmenter | Segment route by gradient direction |
  | GPXRepository | CRUD operations for GPX files |

  ## Files
  | File | Lines | Description |
  |------|-------|-------------|
  | models.py | ~50 | GPXFile model |
  | parser.py | ~200 | GPX parsing |
  | segmenter.py | ~150 | Route segmentation |
  | repository.py | ~100 | Data access |
  ```

### 0f.2 Перенести Users модуль

- [ ] Создать `features/users/models.py`:
  ```python
  """
  User-related models.
  """
  from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text
  from sqlalchemy.orm import relationship
  from sqlalchemy.dialects.postgresql import UUID
  import uuid

  from app.models.base import Base


  class User(Base):
      """Application user."""
      __tablename__ = "users"

      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      telegram_id = Column(String, unique=True, nullable=False, index=True)
      # ... остальные поля из models/user.py ...

      # Relationships
      hiking_profile = relationship("UserHikingProfile", back_populates="user", uselist=False)
      run_profile = relationship("UserRunProfile", back_populates="user", uselist=False)
      # ...


  class Notification(Base):
      """User notification."""
      __tablename__ = "notifications"

      id = Column(Integer, primary_key=True)
      user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
      # ... остальные поля из models/notification.py ...
  ```

- [ ] Создать `features/users/schemas.py`:
  ```python
  """
  User schemas.
  """
  from pydantic import BaseModel
  from typing import Optional
  from datetime import datetime


  class UserCreate(BaseModel):
      """Create user request."""
      telegram_id: str
      name: Optional[str] = None


  class UserResponse(BaseModel):
      """User response."""
      id: str
      telegram_id: str
      name: Optional[str]
      strava_connected: bool
      created_at: datetime

      class Config:
          from_attributes = True


  class NotificationCreate(BaseModel):
      """Create notification."""
      user_id: str
      type: str
      message: str


  class NotificationResponse(BaseModel):
      """Notification response."""
      id: int
      type: str
      message: str
      read: bool
      created_at: datetime

      class Config:
          from_attributes = True
  ```

- [ ] Создать `features/users/service.py` (stub):
  ```python
  """
  User service.

  TODO: Extract user-related logic from routes.
  """
  from sqlalchemy.ext.asyncio import AsyncSession


  class UserService:
      """User management service."""

      def __init__(self, db: AsyncSession):
          self.db = db

      async def get_or_create(self, telegram_id: str) -> tuple:
          """Get existing user or create new."""
          # TODO: Implement in Phase 5
          raise NotImplementedError()
  ```

- [ ] Создать `features/users/repository.py` (stub):
  ```python
  """
  User repository.

  Will be implemented in Phase 5.
  """
  pass
  ```

- [ ] Создать `features/users/__init__.py`:
  ```python
  """
  User management module.

  Usage:
      from app.features.users import User, Notification
  """
  from .models import User, Notification
  from .schemas import UserCreate, UserResponse, NotificationCreate, NotificationResponse

  __all__ = [
      "User",
      "Notification",
      "UserCreate",
      "UserResponse",
      "NotificationCreate",
      "NotificationResponse",
  ]
  ```

- [ ] Создать `features/users/README.md`:
  ```markdown
  # Users Module

  ## Purpose
  User and notification management.

  ## Public API
  ```python
  from app.features.users import User, Notification
  ```

  ## Models

  | Model | Description |
  |-------|-------------|
  | User | Application user with Telegram ID |
  | Notification | User notifications |

  ## Relationships
  - User → UserHikingProfile (1:1)
  - User → UserRunProfile (1:1)
  - User → StravaToken (1:1)
  - User → StravaActivity (1:N)
  - User → Notification (1:N)
  ```

### 0f.3 Обновить старые файлы для обратной совместимости

- [ ] `models/gpx.py`:
  ```python
  """DEPRECATED: Use app.features.gpx.models"""
  from app.features.gpx.models import GPXFile
  __all__ = ["GPXFile"]
  ```

- [ ] `models/user.py`:
  ```python
  """DEPRECATED: Use app.features.users.models"""
  from app.features.users.models import User
  __all__ = ["User"]
  ```

- [ ] `models/notification.py`:
  ```python
  """DEPRECATED: Use app.features.users.models"""
  from app.features.users.models import Notification
  __all__ = ["Notification"]
  ```

- [ ] `services/gpx_parser.py`:
  ```python
  """DEPRECATED: Use app.features.gpx.parser"""
  from app.features.gpx.parser import GPXParserService
  __all__ = ["GPXParserService"]
  ```

- [ ] `repositories/gpx.py`:
  ```python
  """DEPRECATED: Use app.features.gpx.repository"""
  from app.features.gpx.repository import GPXRepository
  __all__ = ["GPXRepository"]
  ```

---

## Файлы для создания/изменения

```
NEW:
backend/app/features/gpx/models.py
backend/app/features/gpx/schemas.py
backend/app/features/gpx/parser.py
backend/app/features/gpx/segmenter.py
backend/app/features/gpx/repository.py
backend/app/features/gpx/README.md
backend/app/features/users/models.py
backend/app/features/users/schemas.py
backend/app/features/users/service.py
backend/app/features/users/repository.py
backend/app/features/users/README.md

UPDATE:
backend/app/features/gpx/__init__.py
backend/app/features/users/__init__.py
backend/app/models/gpx.py (re-export)
backend/app/models/user.py (re-export)
backend/app/models/notification.py (re-export)
backend/app/services/gpx_parser.py (re-export)
backend/app/repositories/gpx.py (re-export)
```

---

## Критерии завершения

- [ ] `features/gpx/` содержит все GPX-related файлы
- [ ] `features/users/` содержит User и Notification
- [ ] RouteSegmenter перенесён в gpx/
- [ ] Старые импорты работают
- [ ] README.md созданы
- [ ] Приложение запускается

---

## Проверка

```bash
cd backend

# Новые импорты
python -c "from app.features.gpx import GPXFile, GPXParserService; print('OK')"
python -c "from app.features.users import User, Notification; print('OK')"

# Старые импорты
python -c "from app.models.gpx import GPXFile; print('OK')"
python -c "from app.models.user import User; print('OK')"

# Приложение
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0f - move gpx and users modules

- Move GPXFile, GPXParserService, GPXRepository to features/gpx/
- Move RouteSegmenter to features/gpx/segmenter.py
- Move User, Notification to features/users/
- Add backward compatibility re-exports
- Add README.md for both modules

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0f-gpx-users
```

---

*Phase 0f — Move GPX and Users Modules*
