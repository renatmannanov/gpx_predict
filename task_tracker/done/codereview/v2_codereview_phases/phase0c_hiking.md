# Phase 0c: Move Hiking Module

> **Статус:** Не начато
> **Оценка:** ~200 строк изменений
> **Зависимости:** Phase 0b
> **Ветка:** `refactor/phase-0c-hiking`
> **Цель:** Перенести всё связанное с hiking в features/hiking/

---

## Текущее расположение

```
backend/app/
├── models/
│   └── user_profile.py          # UserPerformanceProfile (hiking)
├── services/
│   ├── prediction.py            # 532 строки, hiking логика
│   └── calculators/
│       ├── tobler.py            # ToblerCalculator
│       ├── naismith.py          # NaismithCalculator
│       ├── personalization.py   # HikePersonalizationService
│       ├── personalization_base.py
│       └── fatigue.py           # FatigueService
└── schemas/
    └── prediction.py            # HikePrediction и др.
```

---

## Целевая структура

```
backend/app/features/hiking/
├── __init__.py                  # Публичный API
├── models.py                    # UserHikingProfile
├── schemas.py                   # HikePrediction, HikeRequest
├── service.py                   # HikingPredictionService (~300 строк)
├── calculators/
│   ├── __init__.py
│   ├── tobler.py                # Без изменений
│   ├── naismith.py              # Без изменений
│   ├── personalization.py       # HikePersonalizationService
│   └── fatigue.py               # HikeFatigueService
└── README.md
```

---

## Задачи

### 0c.1 Перенести модель
- [ ] Создать `features/hiking/models.py`:
  ```python
  """
  Hiking profile models.

  Note: Table name remains 'user_performance_profiles' for now.
  Will be renamed to 'user_hiking_profiles' in Phase 2.
  """
  from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
  from sqlalchemy.orm import relationship
  from sqlalchemy.dialects.postgresql import UUID

  from app.models.base import Base


  class UserHikingProfile(Base):
      """
      User's hiking performance profile based on Strava data.

      Alias: UserPerformanceProfile (deprecated, use UserHikingProfile)
      """
      __tablename__ = "user_performance_profiles"  # Will rename in Phase 2

      # ... копировать содержимое из models/user_profile.py ...
  ```

- [ ] Добавить alias в старом месте для обратной совместимости:
  ```python
  # models/user_profile.py
  """DEPRECATED: Use app.features.hiking.models.UserHikingProfile"""
  from app.features.hiking.models import UserHikingProfile

  # Alias for backward compatibility
  UserPerformanceProfile = UserHikingProfile

  __all__ = ["UserPerformanceProfile", "UserHikingProfile"]
  ```

### 0c.2 Перенести калькуляторы
- [ ] Скопировать `services/calculators/tobler.py` → `features/hiking/calculators/tobler.py`
- [ ] Скопировать `services/calculators/naismith.py` → `features/hiking/calculators/naismith.py`
- [ ] Скопировать `services/calculators/personalization.py` → `features/hiking/calculators/personalization.py`
- [ ] Скопировать `services/calculators/personalization_base.py` → `features/hiking/calculators/personalization_base.py`
- [ ] Скопировать `services/calculators/fatigue.py` → `features/hiking/calculators/fatigue.py`
- [ ] Обновить импорты в скопированных файлах:
  ```python
  # Было
  from app.shared import haversine

  # Стало (если нужно)
  from app.shared import haversine
  ```

### 0c.3 Создать features/hiking/calculators/__init__.py
- [ ] Создать файл:
  ```python
  """
  Hiking time calculators.

  Available calculators:
  - ToblerCalculator: Tobler's Hiking Function (1993)
  - NaismithCalculator: Naismith's Rule + Langmuir corrections

  Personalization:
  - HikePersonalizationService: Adjusts times based on Strava profile
  - HikeFatigueService: Fatigue modeling for long routes
  """
  from .tobler import ToblerCalculator
  from .naismith import NaismithCalculator
  from .personalization import HikePersonalizationService
  from .fatigue import HikeFatigueService

  # Backward compatibility
  from .personalization import PersonalizationService

  __all__ = [
      "ToblerCalculator",
      "NaismithCalculator",
      "HikePersonalizationService",
      "HikeFatigueService",
      "PersonalizationService",  # deprecated alias
  ]
  ```

### 0c.4 Перенести схемы (частично)
- [ ] Создать `features/hiking/schemas.py`:
  ```python
  """
  Hiking prediction schemas.

  Pydantic models for API request/response.
  """
  from pydantic import BaseModel, Field
  from typing import Optional, List
  from datetime import datetime


  class HikePredictRequest(BaseModel):
      """Request for hiking prediction."""
      gpx_id: str
      telegram_id: str
      experience: str = "intermediate"
      backpack: str = "light"
      group_size: int = 1
      altitude_acclimatized: bool = False
      start_time: Optional[datetime] = None


  class HikeSegment(BaseModel):
      """Single segment of a hiking route."""
      start_km: float
      end_km: float
      distance_km: float
      elevation_gain_m: float
      elevation_loss_m: float
      gradient_percent: float
      time_hours: float


  class HikePrediction(BaseModel):
      """Hiking time prediction result."""
      estimated_time: float = Field(..., description="Time in hours")
      safe_time: float = Field(..., description="Time with safety margin")
      distance_km: float
      elevation_gain_m: float
      elevation_loss_m: float
      method: str = "tobler"
      personalized: bool = False
      segments: Optional[List[HikeSegment]] = None
      warnings: List[str] = []


  class MethodComparison(BaseModel):
      """Comparison of different calculation methods."""
      tobler: float
      naismith: float
      tobler_personalized: Optional[float] = None
      naismith_personalized: Optional[float] = None
      recommended: str
      personalized: bool = False
  ```

### 0c.5 Создать features/hiking/service.py (упрощённый)
- [ ] Создать файл с основной логикой:
  ```python
  """
  Hiking prediction service.

  Main entry point for hiking time predictions.
  """
  from typing import Optional
  from sqlalchemy.ext.asyncio import AsyncSession

  from .schemas import HikePredictRequest, HikePrediction
  from .calculators import ToblerCalculator, HikePersonalizationService


  class HikingPredictionService:
      """
      Service for hiking time predictions.

      Usage:
          service = HikingPredictionService(db)
          prediction = await service.predict(request)
      """

      def __init__(self, db: AsyncSession):
          self.db = db

      async def predict(self, request: HikePredictRequest) -> HikePrediction:
          """
          Make hiking time prediction.

          TODO: Extract logic from services/prediction.py
          """
          # Placeholder - will be implemented by extracting from prediction.py
          raise NotImplementedError("Will be implemented in Phase 6")
  ```

### 0c.6 Создать features/hiking/__init__.py
- [ ] Обновить файл:
  ```python
  """
  Hiking prediction module.

  Usage:
      from app.features.hiking import UserHikingProfile, HikingPredictionService
      from app.features.hiking.calculators import ToblerCalculator

  Available components:
  - UserHikingProfile: SQLAlchemy model for user's hiking profile
  - HikingPredictionService: Main prediction service
  - ToblerCalculator, NaismithCalculator: Time calculators
  - HikePersonalizationService: Personalization based on Strava
  """
  from .models import UserHikingProfile
  from .schemas import HikePredictRequest, HikePrediction, MethodComparison
  from .service import HikingPredictionService

  # Backward compatibility
  UserPerformanceProfile = UserHikingProfile

  __all__ = [
      "UserHikingProfile",
      "UserPerformanceProfile",  # deprecated
      "HikePredictRequest",
      "HikePrediction",
      "MethodComparison",
      "HikingPredictionService",
  ]
  ```

### 0c.7 Создать README.md
- [ ] Создать `features/hiking/README.md`:
  ```markdown
  # Hiking Module

  ## Purpose
  Time prediction for hiking routes.

  ## Public API
  ```python
  from app.features.hiking import (
      UserHikingProfile,
      HikingPredictionService,
      HikePrediction,
  )
  from app.features.hiking.calculators import (
      ToblerCalculator,
      NaismithCalculator,
  )
  ```

  ## Calculators

  | Calculator | Description | Use when |
  |------------|-------------|----------|
  | ToblerCalculator | Tobler's Hiking Function | Mountain routes (default) |
  | NaismithCalculator | Naismith + Langmuir | Flat/gentle routes |
  | HikePersonalizationService | User-specific | Has Strava profile |

  ## Files

  | File | Lines | Description |
  |------|-------|-------------|
  | models.py | ~100 | UserHikingProfile |
  | schemas.py | ~80 | Pydantic schemas |
  | service.py | ~300 | Main service |
  | calculators/tobler.py | ~150 | Tobler calculator |
  | calculators/naismith.py | ~150 | Naismith calculator |
  ```

### 0c.8 Обновить импорты в старых файлах
- [ ] `services/calculators/__init__.py`:
  ```python
  """
  DEPRECATED: Use app.features.hiking.calculators or app.features.trail_run.calculators

  This module re-exports for backward compatibility.
  """
  # Re-export from new locations
  from app.features.hiking.calculators import (
      ToblerCalculator,
      NaismithCalculator,
      HikePersonalizationService,
      PersonalizationService,
  )

  # Keep base classes here for now
  from .base import MacroSegment, SegmentType, PaceCalculator
  from .segmenter import RouteSegmenter
  from .comparison import ComparisonService
  ```

---

## Файлы для создания/изменения

```
NEW:
backend/app/features/hiking/models.py
backend/app/features/hiking/schemas.py
backend/app/features/hiking/service.py
backend/app/features/hiking/calculators/tobler.py
backend/app/features/hiking/calculators/naismith.py
backend/app/features/hiking/calculators/personalization.py
backend/app/features/hiking/calculators/personalization_base.py
backend/app/features/hiking/calculators/fatigue.py
backend/app/features/hiking/README.md

UPDATE:
backend/app/features/hiking/__init__.py
backend/app/features/hiking/calculators/__init__.py
backend/app/models/user_profile.py (re-export)
backend/app/services/calculators/__init__.py (re-export)
```

---

## Критерии завершения

- [ ] `features/hiking/` содержит все hiking-related файлы
- [ ] Все калькуляторы скопированы
- [ ] Старые импорты работают (backward compatibility)
- [ ] Новые импорты работают
- [ ] README.md создан
- [ ] Приложение запускается

---

## Проверка

```bash
cd backend

# Новые импорты
python -c "from app.features.hiking import UserHikingProfile; print('OK')"
python -c "from app.features.hiking.calculators import ToblerCalculator; print('OK')"

# Старые импорты (backward compatibility)
python -c "from app.models.user_profile import UserPerformanceProfile; print('OK')"
python -c "from app.services.calculators import ToblerCalculator; print('OK')"

# Приложение
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0c - move hiking module to features/

- Move UserPerformanceProfile to features/hiking/models.py
- Move calculators (tobler, naismith, personalization, fatigue)
- Create hiking schemas and service stub
- Add backward compatibility re-exports
- Add features/hiking/README.md

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0c-hiking
```

Перейти к Phase 0d или Phase 2.

---

*Phase 0c — Move Hiking Module*
