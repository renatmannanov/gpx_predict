# Trail Running Implementation - Part 3

**Фазы:** API + Тестирование + Документация
**Зависит от:** Part 1, Part 2
**Статус:** Draft
**Дата:** 2026-01-23

---

## Содержание

1. [Обзор Part 3](#1-обзор-part-3)
2. [API: Расширение /predict/compare](#2-api-расширение-predictcompare)
3. [TrailRunService: Оркестратор](#3-trailrunservice-оркестратор)
4. [Тестирование](#4-тестирование)
5. [Документация](#5-документация)
6. [Чеклист Part 3](#6-чеклист-part-3)

---

## 1. Обзор Part 3

### Цели

1. Расширить существующий `/predict/compare` для trail running
2. Создать `TrailRunService` — оркестратор всех компонентов
3. Полное тестирование на реальных данных
4. Обновить документацию

### Итоговая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     POST /predict/compare                        │
│                   { activity_type: "trail_run" }                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   TrailRunService                           ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │  RouteSegmenter.segment_route()  ◄── переиспользуем         ││
│  │           │                                                  ││
│  │           ▼                                                  ││
│  │    List[MacroSegment]                                        ││
│  │           │                                                  ││
│  │           ├──► HikeRunThresholdService.decide()             ││
│  │           │           │                                      ││
│  │           │    ┌──────┴──────┐                               ││
│  │           │    ▼             ▼                               ││
│  │           │  RUN           HIKE                              ││
│  │           │    │             │                               ││
│  │           │  ┌─┴─┐         ┌─┴─┐                             ││
│  │           │  ▼   ▼         ▼   ▼                             ││
│  │           │ Run  GAP     Hike  Tobler                        ││
│  │           │ Pers Calc    Pers  Calc                          ││
│  │           │                                                  ││
│  │           └──► RunnerFatigueService (опционально)           ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. API: Расширение /predict/compare

### 2.1 Обновлённые схемы

```python
# backend/app/schemas/prediction.py

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel


class ActivityType(str, Enum):
    """Type of activity for prediction."""
    HIKE = "hike"
    TRAIL_RUN = "trail_run"


class GAPModeEnum(str, Enum):
    """GAP calculation mode for trail running."""
    STRAVA = "strava_gap"
    MINETTI = "minetti_gap"


class CompareRequest(BaseModel):
    """Extended compare request supporting both hike and trail_run."""
    gpx_id: str
    telegram_id: Optional[str] = None

    # Activity type (NEW)
    activity_type: ActivityType = ActivityType.HIKE

    # Common options
    experience: str = "intermediate"
    backpack: str = "light"
    group_size: int = 1
    altitude_threshold: int = 2500
    use_extended_gradients: bool = False
    apply_fatigue: bool = False

    # Trail Run specific options (ignored for hike)
    gap_mode: GAPModeEnum = GAPModeEnum.STRAVA
    flat_pace_min_km: Optional[float] = None  # Manual input if no Strava
    apply_dynamic_threshold: bool = True
    walk_threshold_override: Optional[float] = None  # Manual override


class SegmentMovementInfo(BaseModel):
    """Movement info for a segment (trail run only)."""
    mode: str              # "run" | "hike"
    reason: str
    threshold_used: float
    confidence: float


class TrailRunSegmentPrediction(BaseModel):
    """Extended segment prediction for trail running."""
    start_km: float
    end_km: float
    distance_km: float
    elevation_change_m: float
    gradient_percent: float

    # Movement mode (trail run only)
    movement: Optional[SegmentMovementInfo] = None

    # Time predictions by method
    times: Dict[str, float]  # method_name → time_hours

    # Fatigue info
    fatigue_multiplier: Optional[float] = None


class TrailRunSummary(BaseModel):
    """Summary statistics for trail run prediction."""
    total_distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float

    # Time breakdown
    running_time_hours: float
    hiking_time_hours: float
    running_distance_km: float
    hiking_distance_km: float

    # Flat equivalent
    flat_equivalent_hours: float
    elevation_impact_percent: float


class CompareResponse(BaseModel):
    """Extended compare response."""
    # Existing fields
    totals: Dict[str, float]
    segments: List[TrailRunSegmentPrediction]
    personalized: bool
    activities_used: int

    # Activity type
    activity_type: str

    # Trail Run specific (None for hike)
    trail_run_summary: Optional[TrailRunSummary] = None
    hike_activities_used: Optional[int] = None  # For hike segments
    run_activities_used: Optional[int] = None   # For run segments
    walk_threshold_used: Optional[float] = None
    dynamic_threshold_applied: Optional[bool] = None
    gap_mode: Optional[str] = None

    # Fatigue (both hike and trail_run)
    fatigue_applied: bool = False
    fatigue_info: Optional[Dict] = None
```

### 2.2 Обновлённый endpoint

```python
# backend/app/api/v1/routes/predict.py

@router.post("/compare", response_model=CompareResponse)
async def compare_methods(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db)
) -> CompareResponse:
    """
    Compare prediction methods for a route.

    Supports two activity types:
    - hike: Uses Tobler, Naismith, and personalized hiking methods
    - trail_run: Uses GAP calculator with hike/run threshold detection

    For trail_run:
    - Segments are classified as RUN or HIKE
    - RUN segments use GAP calculator or Run personalization
    - HIKE segments use Tobler or Hike personalization
    - Fatigue model is runner-specific (earlier threshold, downhill penalty)
    """
    # Load GPX
    gpx_file = await gpx_repo.get_by_id(request.gpx_id)
    if not gpx_file:
        raise HTTPException(404, "GPX file not found")

    # Parse points
    parser = GPXParserService()
    gpx_info = parser.parse(gpx_file.gpx_content)
    points = gpx_info.points

    if request.activity_type == ActivityType.HIKE:
        # Existing hiking logic
        return await _compare_hiking(request, points, db)
    else:
        # New trail running logic
        return await _compare_trail_run(request, points, db)


async def _compare_trail_run(
    request: CompareRequest,
    points: List[tuple],
    db: AsyncSession
) -> CompareResponse:
    """Trail running comparison logic."""
    from app.services.calculators.trail_run.trail_run_service import TrailRunService

    # Load profiles if telegram_id provided
    hike_profile = None
    run_profile = None

    if request.telegram_id:
        hike_profile = await user_profile_service.get_hike_profile(
            db, request.telegram_id
        )
        run_profile = await user_profile_service.get_run_profile(
            db, request.telegram_id
        )

    # Determine flat pace
    if run_profile and run_profile.avg_flat_pace_min_km:
        flat_pace = run_profile.avg_flat_pace_min_km
    elif request.flat_pace_min_km:
        flat_pace = request.flat_pace_min_km
    else:
        flat_pace = 6.0  # Default 10 km/h

    # Create service
    service = TrailRunService(
        gap_mode=GAPMode(request.gap_mode),
        flat_pace_min_km=flat_pace,
        hike_profile=hike_profile,
        run_profile=run_profile,
        apply_fatigue=request.apply_fatigue,
        apply_dynamic_threshold=request.apply_dynamic_threshold,
        walk_threshold_override=request.walk_threshold_override,
        use_extended_gradients=request.use_extended_gradients,
    )

    # Calculate
    result = service.calculate_route(points)

    return CompareResponse(
        totals=result.totals,
        segments=result.segments,
        personalized=result.personalized,
        activities_used=result.total_activities_used,
        activity_type="trail_run",
        trail_run_summary=result.summary,
        hike_activities_used=result.hike_activities_used,
        run_activities_used=result.run_activities_used,
        walk_threshold_used=result.walk_threshold_used,
        dynamic_threshold_applied=request.apply_dynamic_threshold,
        gap_mode=request.gap_mode,
        fatigue_applied=request.apply_fatigue,
        fatigue_info=result.fatigue_info,
    )
```

---

## 3. TrailRunService: Оркестратор

### 3.1 trail_run/trail_run_service.py

```python
"""
Trail Run Service

Orchestrates all trail running components:
- Route segmentation
- Hike/Run threshold detection
- GAP calculation for running segments
- Tobler/personalization for hiking segments
- Runner fatigue model

This is the main entry point for trail running predictions.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.services.calculators.base import MacroSegment
from app.services.calculators.segmenter import RouteSegmenter
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.personalization import HikePersonalizationService
from app.services.calculators.personalization_run import RunPersonalizationService
from app.services.calculators.trail_run.gap_calculator import GAPCalculator, GAPMode
from app.services.calculators.trail_run.hike_run_threshold import (
    HikeRunThresholdService,
    MovementMode,
    HikeRunDecision,
)
from app.services.calculators.trail_run.runner_fatigue import RunnerFatigueService

from app.models.user_hike_profile import UserHikeProfile
from app.models.user_run_profile import UserRunProfile


@dataclass
class SegmentResult:
    """Result for a single segment."""
    segment: MacroSegment
    movement: HikeRunDecision
    times: Dict[str, float]      # method → hours
    fatigue_multiplier: float = 1.0


@dataclass
class TrailRunResult:
    """Complete result of trail run prediction."""
    segments: List[SegmentResult]
    totals: Dict[str, float]
    summary: Dict[str, Any]
    personalized: bool
    total_activities_used: int
    hike_activities_used: int
    run_activities_used: int
    walk_threshold_used: float
    fatigue_info: Optional[Dict] = None


class TrailRunService:
    """
    Main service for trail running time predictions.

    Combines:
    - GAPCalculator for running segments
    - ToblerCalculator for hiking segments
    - HikeRunThresholdService for mode detection
    - RunnerFatigueService for fatigue modeling
    - Personalization for both run and hike segments
    """

    def __init__(
        self,
        gap_mode: GAPMode = GAPMode.STRAVA,
        flat_pace_min_km: float = 6.0,
        hike_profile: Optional[UserHikeProfile] = None,
        run_profile: Optional[UserRunProfile] = None,
        apply_fatigue: bool = False,
        apply_dynamic_threshold: bool = True,
        walk_threshold_override: Optional[float] = None,
        use_extended_gradients: bool = True,
        total_distance_km: Optional[float] = None,
    ):
        """
        Initialize trail run service.

        Args:
            gap_mode: GAP calculation mode (STRAVA or MINETTI)
            flat_pace_min_km: Base flat pace for GAP (if no run profile)
            hike_profile: UserHikeProfile for hiking segments
            run_profile: UserRunProfile for running segments
            apply_fatigue: Enable runner fatigue model
            apply_dynamic_threshold: Enable dynamic hike/run threshold
            walk_threshold_override: Manual override for walk threshold
            use_extended_gradients: Use 7-category gradient system
            total_distance_km: Total route distance (for ultra adaptation)
        """
        self.gap_mode = gap_mode
        self.use_extended_gradients = use_extended_gradients

        # Determine flat pace from profile or manual input
        if run_profile and run_profile.avg_flat_pace_min_km:
            self.flat_pace = run_profile.avg_flat_pace_min_km
        else:
            self.flat_pace = flat_pace_min_km

        # Profiles
        self.hike_profile = hike_profile
        self.run_profile = run_profile

        # Calculators
        self._gap_calc = GAPCalculator(self.flat_pace, gap_mode)
        self._tobler_calc = ToblerCalculator()

        # Personalization services (if profiles valid)
        self._run_pers = None
        self._hike_pers = None

        if RunPersonalizationService.is_profile_valid(run_profile):
            self._run_pers = RunPersonalizationService(run_profile, use_extended_gradients)

        if HikePersonalizationService.is_profile_valid(hike_profile):
            self._hike_pers = HikePersonalizationService(hike_profile, use_extended_gradients)

        # Threshold service
        threshold = walk_threshold_override
        if threshold is None and run_profile and run_profile.walk_threshold_percent:
            threshold = run_profile.walk_threshold_percent

        self._threshold_service = HikeRunThresholdService(
            uphill_threshold=threshold or 25.0,
            dynamic=apply_dynamic_threshold
        )

        # Fatigue service
        if apply_fatigue:
            self._fatigue_service = RunnerFatigueService.create_enabled(
                distance_km=total_distance_km
            )
        else:
            self._fatigue_service = RunnerFatigueService.create_disabled()

    def calculate_route(
        self,
        points: List[tuple]
    ) -> TrailRunResult:
        """
        Calculate trail run prediction for a route.

        Args:
            points: List of (lat, lon, elevation) tuples

        Returns:
            TrailRunResult with all predictions
        """
        # Segment route
        segmenter = RouteSegmenter()
        segments = segmenter.segment_route(points)

        total_distance = sum(s.distance_km for s in segments)

        # Get hike/run decisions
        decisions = self._threshold_service.process_route(segments, total_distance)

        # Calculate each segment
        results = []
        cumulative_time = 0.0

        totals = {
            "strava_gap": 0.0,
            "minetti_gap": 0.0,
            "tobler": 0.0,
        }

        if self._run_pers:
            totals["run_personalized"] = 0.0
        if self._hike_pers:
            totals["hike_personalized"] = 0.0

        running_time = 0.0
        hiking_time = 0.0
        running_distance = 0.0
        hiking_distance = 0.0

        for segment, decision in zip(segments, decisions):
            times = {}

            if decision.mode == MovementMode.RUN:
                # Running segment
                running_distance += segment.distance_km

                # GAP methods
                gap_result = self._gap_calc.calculate_segment(segment)
                times["strava_gap"] = gap_result.time_hours

                # Also calculate with other mode for comparison
                other_mode = GAPMode.MINETTI if self.gap_mode == GAPMode.STRAVA else GAPMode.STRAVA
                other_calc = GAPCalculator(self.flat_pace, other_mode)
                other_result = other_calc.calculate_segment(segment)
                times["minetti_gap"] = other_result.time_hours

                # Run personalization
                if self._run_pers:
                    pers_result = self._run_pers.calculate_segment(segment, "run")
                    times["run_personalized"] = pers_result.time_hours

                # Primary time for this segment
                if self._run_pers:
                    primary_time = times["run_personalized"]
                else:
                    primary_time = times["strava_gap"] if self.gap_mode == GAPMode.STRAVA else times["minetti_gap"]

            else:
                # Hiking segment
                hiking_distance += segment.distance_km

                # Tobler
                tobler_result = self._tobler_calc.calculate_segment(segment)
                times["tobler"] = tobler_result.time_hours

                # Hike personalization
                if self._hike_pers:
                    pers_result = self._hike_pers.calculate_segment(segment, "hike")
                    times["hike_personalized"] = pers_result.time_hours

                # Primary time
                if self._hike_pers:
                    primary_time = times["hike_personalized"]
                else:
                    primary_time = times["tobler"]

            # Apply fatigue
            adjusted_time, multiplier = self._fatigue_service.apply_to_segment(
                primary_time,
                cumulative_time,
                segment.gradient_percent
            )

            # Track cumulative time with fatigue
            cumulative_time += adjusted_time

            # Track running/hiking time
            if decision.mode == MovementMode.RUN:
                running_time += adjusted_time
            else:
                hiking_time += adjusted_time

            # Accumulate totals
            for method, time in times.items():
                if method in totals:
                    # Apply fatigue to all methods consistently
                    fatigue_adj, _ = self._fatigue_service.apply_to_segment(
                        time, cumulative_time - adjusted_time, segment.gradient_percent
                    )
                    totals[method] += fatigue_adj

            results.append(SegmentResult(
                segment=segment,
                movement=decision,
                times=times,
                fatigue_multiplier=multiplier
            ))

        # Build summary
        total_elevation_gain = sum(
            max(0, s.elevation_change_m) for s in segments
        )
        total_elevation_loss = sum(
            abs(min(0, s.elevation_change_m)) for s in segments
        )

        # Calculate flat equivalent
        flat_time = total_distance / (60 / self.flat_pace)
        primary_total = totals.get("run_personalized") or totals.get("strava_gap", flat_time)
        elevation_impact = ((primary_total / flat_time) - 1) * 100 if flat_time > 0 else 0

        summary = {
            "total_distance_km": round(total_distance, 2),
            "total_elevation_gain_m": round(total_elevation_gain, 0),
            "total_elevation_loss_m": round(total_elevation_loss, 0),
            "running_time_hours": round(running_time, 3),
            "hiking_time_hours": round(hiking_time, 3),
            "running_distance_km": round(running_distance, 2),
            "hiking_distance_km": round(hiking_distance, 2),
            "flat_equivalent_hours": round(flat_time, 3),
            "elevation_impact_percent": round(elevation_impact, 1),
        }

        # Activity counts
        hike_activities = self.hike_profile.total_activities_analyzed if self.hike_profile else 0
        run_activities = self.run_profile.total_activities if self.run_profile else 0

        return TrailRunResult(
            segments=results,
            totals={k: round(v, 4) for k, v in totals.items()},
            summary=summary,
            personalized=self._run_pers is not None or self._hike_pers is not None,
            total_activities_used=hike_activities + run_activities,
            hike_activities_used=hike_activities,
            run_activities_used=run_activities,
            walk_threshold_used=self._threshold_service.base_uphill_threshold,
            fatigue_info=self._fatigue_service.get_info() if self._fatigue_service.enabled else None,
        )
```

---

## 4. Тестирование

### 4.1 Unit-тесты

```
backend/tests/calculators/
├── personalization/
│   ├── test_base.py
│   ├── test_hike.py
│   └── test_run.py
│
├── trail_run/
│   ├── test_gap_calculator.py
│   ├── test_hike_run_threshold.py
│   ├── test_runner_fatigue.py
│   └── test_trail_run_service.py
```

### 4.2 Интеграционные тесты

```python
# backend/tests/integration/test_trail_run_prediction.py

@pytest.mark.asyncio
async def test_trail_run_basic():
    """Test basic trail run prediction without profiles."""
    pass


@pytest.mark.asyncio
async def test_trail_run_with_run_profile():
    """Test trail run with Strava Run profile."""
    pass


@pytest.mark.asyncio
async def test_trail_run_mixed_profiles():
    """Test trail run with both Hike and Run profiles."""
    pass


@pytest.mark.asyncio
async def test_trail_run_fatigue():
    """Test runner fatigue model on long route."""
    pass
```

### 4.3 Валидация на реальных данных

| Трасса | Дистанция | D+ | Ожидаемое | Strava GAP | Minetti GAP | Персонализ. |
|--------|-----------|-----|-----------|------------|-------------|-------------|
| Medeu Trail 21K | 21 км | 1100м | ~2.5ч | ? | ? | ? |
| Shymbulak 50K | 50 км | 2800м | ~6-7ч | ? | ? | ? |
| UTMB 171K | 171 км | 10000м | ~24-30ч | ? | ? | ? |

**Критерий успеха:** Ошибка <15% для коротких трейлов, <20% для ультра.

---

## 5. Документация

### 5.1 Обновить ARCHITECTURE.md

- [ ] Добавить `TrailRunService` в секцию Services
- [ ] Добавить `GAPCalculator`, `HikeRunThresholdService`, `RunnerFatigueService`
- [ ] Обновить диаграмму компонентов
- [ ] Добавить новые таблицы `user_hike_profiles`, `user_run_profiles`
- [ ] Документировать расширенный `/predict/compare` endpoint

### 5.2 Обновить ARCHITECTURE_CALCULATIONS.md

- [ ] Добавить секцию "Trail Running Calculations"
- [ ] Описать GAP формулы (Strava и Minetti)
- [ ] Описать логику Hike/Run threshold
- [ ] Описать модель Runner Fatigue
- [ ] Добавить таблицу сравнения Hike vs Trail Run

### 5.3 Обновить CODE_REVIEW.md

- [ ] Обновить статус рефакторинга PersonalizationService
- [ ] Добавить раздел о новых trail run компонентах

### 5.4 Обновить CLAUDE.md (если нужно)

- [ ] Добавить правила для `trail_run/` директории
- [ ] Обновить список калькуляторов

---

## 6. Чеклист Part 3

### API

- [ ] Обновить `schemas/prediction.py` — добавить trail run схемы
- [ ] Расширить `POST /predict/compare` для `activity_type`
- [ ] Добавить helper функцию `_compare_trail_run()`
- [ ] Интеграционные тесты для API

### TrailRunService

- [ ] Создать `trail_run/trail_run_service.py`
- [ ] Интегрировать все компоненты (GAP, threshold, fatigue, personalization)
- [ ] Unit-тесты для оркестратора

### Тестирование

- [ ] Unit-тесты для всех новых компонентов
- [ ] Интеграционные тесты
- [ ] Валидация на реальных GPX файлах
- [ ] Сравнение с известными результатами (Strava/COROS)

### Документация

- [ ] `ARCHITECTURE.md` — новые сервисы и модели
- [ ] `ARCHITECTURE_CALCULATIONS.md` — GAP формулы и логика
- [ ] `CODE_REVIEW.md` — статус рефакторинга
- [ ] OpenAPI документация endpoint'ов

### Интеграция с ботом

- [ ] Обновить `api_client.py` — поддержка `activity_type`
- [ ] Обновить хендлеры — выбор hike/trail_run
- [ ] Форматирование вывода для trail run

---

## Итоговая структура файлов

```
backend/app/
├── api/v1/routes/
│   └── predict.py                 # Расширен для trail_run
│
├── models/
│   ├── user_hike_profile.py       # Переименованный user_profile.py
│   └── user_run_profile.py        # Новый
│
├── schemas/
│   └── prediction.py              # Расширен для trail_run
│
├── services/
│   ├── calculators/
│   │   ├── base.py
│   │   ├── segmenter.py
│   │   ├── tobler.py
│   │   ├── naismith.py
│   │   ├── fatigue.py
│   │   ├── comparison.py
│   │   ├── personalization_base.py    # Новый
│   │   ├── personalization.py         # HikePersonalizationService
│   │   ├── personalization_run.py     # Новый
│   │   │
│   │   └── trail_run/
│   │       ├── __init__.py
│   │       ├── gap_calculator.py      # Новый
│   │       ├── hike_run_threshold.py  # Новый
│   │       ├── runner_fatigue.py      # Новый
│   │       └── trail_run_service.py   # Новый
│   │
│   ├── user_profile.py                # Расширен для run
│   └── strava_sync.py                 # Расширен для run
│
└── alembic/versions/
    ├── 007_split_user_profiles.py     # Новый
    └── ...
```

---

## Завершение проекта

После Part 3:
1. ✅ Trail running полностью функционален
2. ✅ API поддерживает hike и trail_run
3. ✅ Персонализация для обоих типов активностей
4. ✅ Модели усталости для hike и trail_run
5. ✅ Документация актуальна
6. ✅ Тесты покрывают новый функционал

**Следующие шаги (будущее):**
- Terrain crowdsourcing
- HR-based pace normalization
- Weather impact factor
