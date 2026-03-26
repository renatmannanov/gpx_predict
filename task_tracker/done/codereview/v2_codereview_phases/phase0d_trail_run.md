# Phase 0d: Move Trail Run Module

> **Статус:** Не начато
> **Оценка:** ~150 строк изменений
> **Зависимости:** Phase 0b
> **Ветка:** `refactor/phase-0d-trail-run`
> **Цель:** Перенести всё связанное с trail running в features/trail_run/

---

## Текущее расположение

```
backend/app/
├── models/
│   └── user_run_profile.py          # UserRunProfile
└── services/calculators/trail_run/
    ├── __init__.py
    ├── gap_calculator.py            # GAPCalculator
    ├── hike_run_threshold.py        # HikeRunThresholdService
    ├── runner_fatigue.py            # RunnerFatigueService
    └── trail_run_service.py         # TrailRunService
```

---

## Целевая структура

```
backend/app/features/trail_run/
├── __init__.py
├── models.py                        # UserRunProfile
├── schemas.py                       # TrailRunPrediction, etc.
├── service.py                       # TrailRunService (rename)
├── calculators/
│   ├── __init__.py
│   ├── gap.py                       # GAPCalculator
│   ├── threshold.py                 # HikeRunThresholdService
│   ├── personalization.py           # RunPersonalizationService
│   └── fatigue.py                   # RunnerFatigueService
└── README.md
```

---

## Задачи

### 0d.1 Перенести модель
- [ ] Создать `features/trail_run/models.py`:
  ```python
  """
  Trail run profile models.
  """
  from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean
  from sqlalchemy.orm import relationship
  from sqlalchemy.dialects.postgresql import UUID

  from app.models.base import Base


  class UserRunProfile(Base):
      """
      User's trail running profile based on Strava data.

      Uses 7-category gradient system for more accurate pace predictions.
      """
      __tablename__ = "user_run_profiles"

      # ... копировать содержимое из models/user_run_profile.py ...
  ```

- [ ] Добавить re-export в старом месте:
  ```python
  # models/user_run_profile.py
  """DEPRECATED: Use app.features.trail_run.models.UserRunProfile"""
  from app.features.trail_run.models import UserRunProfile

  __all__ = ["UserRunProfile"]
  ```

### 0d.2 Перенести калькуляторы
- [ ] Скопировать `services/calculators/trail_run/gap_calculator.py` → `features/trail_run/calculators/gap.py`
- [ ] Скопировать `services/calculators/trail_run/hike_run_threshold.py` → `features/trail_run/calculators/threshold.py`
- [ ] Скопировать `services/calculators/trail_run/runner_fatigue.py` → `features/trail_run/calculators/fatigue.py`
- [ ] Скопировать `services/calculators/personalization_run.py` → `features/trail_run/calculators/personalization.py`

### 0d.3 Перенести сервис
- [ ] Скопировать `services/calculators/trail_run/trail_run_service.py` → `features/trail_run/service.py`
- [ ] Обновить импорты внутри файла:
  ```python
  # Было
  from .gap_calculator import GAPCalculator
  from .hike_run_threshold import HikeRunThresholdService

  # Стало
  from .calculators.gap import GAPCalculator
  from .calculators.threshold import HikeRunThresholdService
  ```

### 0d.4 Создать features/trail_run/calculators/__init__.py
- [ ] Создать файл:
  ```python
  """
  Trail running calculators.

  Components:
  - GAPCalculator: Grade Adjusted Pace (Strava/Minetti)
  - HikeRunThresholdService: Detect when to hike vs run
  - RunPersonalizationService: User-specific adjustments
  - RunnerFatigueService: Fatigue modeling for runners
  """
  from .gap import GAPCalculator, GAPMethod
  from .threshold import HikeRunThresholdService
  from .personalization import RunPersonalizationService
  from .fatigue import RunnerFatigueService

  __all__ = [
      "GAPCalculator",
      "GAPMethod",
      "HikeRunThresholdService",
      "RunPersonalizationService",
      "RunnerFatigueService",
  ]
  ```

### 0d.5 Создать features/trail_run/schemas.py
- [ ] Создать файл:
  ```python
  """
  Trail run prediction schemas.
  """
  from pydantic import BaseModel, Field
  from typing import Optional, List
  from datetime import datetime
  from enum import Enum


  class GAPMethod(str, Enum):
      """GAP calculation method."""
      STRAVA = "strava"
      MINETTI = "minetti"


  class TrailRunRequest(BaseModel):
      """Request for trail run prediction."""
      gpx_id: str
      telegram_id: str
      flat_pace_min_km: float = 6.0
      gap_method: GAPMethod = GAPMethod.STRAVA
      enable_fatigue: bool = True
      uphill_threshold_percent: float = 25.0


  class TrailRunSegment(BaseModel):
      """Single segment result."""
      start_km: float
      end_km: float
      distance_km: float
      elevation_diff_m: float
      gradient_percent: float
      mode: str  # "run" or "hike"
      time_hours: float
      pace_min_km: float


  class TrailRunPrediction(BaseModel):
      """Trail run prediction result."""
      estimated_time: float = Field(..., description="Time in hours")
      distance_km: float
      elevation_gain_m: float
      elevation_loss_m: float
      run_distance_km: float
      hike_distance_km: float
      run_time_hours: float
      hike_time_hours: float
      gap_method: GAPMethod
      fatigue_applied: bool
      segments: Optional[List[TrailRunSegment]] = None
  ```

### 0d.6 Обновить features/trail_run/__init__.py
- [ ] Обновить файл:
  ```python
  """
  Trail running prediction module.

  Usage:
      from app.features.trail_run import TrailRunService, UserRunProfile
      from app.features.trail_run.calculators import GAPCalculator

  Components:
  - TrailRunService: Main prediction service
  - GAPCalculator: Grade Adjusted Pace
  - HikeRunThresholdService: Run vs walk detection
  - RunnerFatigueService: Fatigue modeling
  """
  from .models import UserRunProfile
  from .schemas import TrailRunRequest, TrailRunPrediction, GAPMethod
  from .service import TrailRunService

  __all__ = [
      "UserRunProfile",
      "TrailRunRequest",
      "TrailRunPrediction",
      "GAPMethod",
      "TrailRunService",
  ]
  ```

### 0d.7 Создать README.md
- [ ] Создать `features/trail_run/README.md`:
  ```markdown
  # Trail Run Module

  ## Purpose
  Time prediction for trail running routes.

  ## Public API
  ```python
  from app.features.trail_run import (
      TrailRunService,
      UserRunProfile,
      TrailRunPrediction,
  )
  from app.features.trail_run.calculators import (
      GAPCalculator,
      HikeRunThresholdService,
  )
  ```

  ## How it works

  1. Route is segmented by gradient direction
  2. For each segment, determine: RUN or HIKE
     - RUN if gradient < uphill_threshold (default 25%)
     - HIKE otherwise
  3. Apply GAP (Grade Adjusted Pace) for running segments
  4. Apply Tobler's function for hiking segments
  5. Add fatigue penalty for long routes (optional)

  ## GAP Methods

  | Method | Description |
  |--------|-------------|
  | STRAVA | Empirical table from 240k athletes |
  | MINETTI | Scientific formula (Minetti et al., 2002) |

  ## Files

  | File | Lines | Description |
  |------|-------|-------------|
  | models.py | ~80 | UserRunProfile |
  | schemas.py | ~60 | Pydantic schemas |
  | service.py | ~200 | TrailRunService |
  | calculators/gap.py | ~150 | GAPCalculator |
  | calculators/threshold.py | ~100 | HikeRunThresholdService |
  ```

### 0d.8 Обновить старые импорты
- [ ] `services/calculators/trail_run/__init__.py`:
  ```python
  """
  DEPRECATED: Use app.features.trail_run

  Re-exports for backward compatibility.
  """
  from app.features.trail_run import TrailRunService
  from app.features.trail_run.calculators import (
      GAPCalculator,
      HikeRunThresholdService,
      RunnerFatigueService,
  )

  __all__ = [
      "TrailRunService",
      "GAPCalculator",
      "HikeRunThresholdService",
      "RunnerFatigueService",
  ]
  ```

---

## Файлы для создания/изменения

```
NEW:
backend/app/features/trail_run/models.py
backend/app/features/trail_run/schemas.py
backend/app/features/trail_run/service.py
backend/app/features/trail_run/calculators/gap.py
backend/app/features/trail_run/calculators/threshold.py
backend/app/features/trail_run/calculators/personalization.py
backend/app/features/trail_run/calculators/fatigue.py
backend/app/features/trail_run/README.md

UPDATE:
backend/app/features/trail_run/__init__.py
backend/app/features/trail_run/calculators/__init__.py
backend/app/models/user_run_profile.py (re-export)
backend/app/services/calculators/trail_run/__init__.py (re-export)
```

---

## Критерии завершения

- [ ] `features/trail_run/` содержит все trail_run-related файлы
- [ ] Все калькуляторы перенесены
- [ ] Старые импорты работают
- [ ] Новые импорты работают
- [ ] README.md создан
- [ ] Приложение запускается

---

## Проверка

```bash
cd backend

# Новые импорты
python -c "from app.features.trail_run import TrailRunService; print('OK')"
python -c "from app.features.trail_run.calculators import GAPCalculator; print('OK')"

# Старые импорты
python -c "from app.services.calculators.trail_run import TrailRunService; print('OK')"

# Приложение
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0d - move trail_run module to features/

- Move UserRunProfile to features/trail_run/models.py
- Move calculators (gap, threshold, fatigue, personalization)
- Move TrailRunService
- Add backward compatibility re-exports
- Add features/trail_run/README.md

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0d-trail-run
```

---

*Phase 0d — Move Trail Run Module*
