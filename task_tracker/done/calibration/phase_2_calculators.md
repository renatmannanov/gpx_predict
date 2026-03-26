# Фаза 2: Адаптеры калькуляторов

**Статус:** Ожидает Фазу 1
**Зависимости:** Фаза 1 ✓
**Строк кода:** ~100

---

## Цель

Создать адаптеры для прогона VirtualRoute через наши калькуляторы GAP и Hiking.

---

## Что создаём

```
backend/tools/calibration/
├── __init__.py          # обновить
├── virtual_route.py     # из Фазы 1
└── calculators.py       # NEW
```

---

## Код

### `backend/tools/calibration/calculators.py`

```python
"""
Calculator adapters for backtesting.

Runs virtual routes through our prediction calculators
and collects predicted times.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List

from app.features.trail_run.calculators.gap_calculator import GAPCalculator
from app.features.hiking.calculators.tobler import ToblerCalculator
from app.features.hiking.calculators.naismith import NaismithCalculator
from app.features.trail_run.calculators.personalization import RunPersonalizationService
from app.models.user_run_profile import UserRunProfile
from app.shared.constants import DEFAULT_FLAT_PACE_MIN_KM

from .virtual_route import VirtualRoute, VirtualSegment


@dataclass
class SegmentPredictions:
    """Predicted times for one segment by all methods."""

    segment_index: int
    distance_m: float
    gradient_percent: float
    actual_time_s: int

    # Predictions (seconds)
    strava_gap: float
    minetti_gap: float
    strava_minetti_gap: float
    personalized: Optional[float]  # None if no profile
    tobler: float
    naismith: float


@dataclass
class RoutePredictions:
    """Predicted times for entire route by all methods."""

    activity_id: int
    activity_name: str

    # Actual
    actual_time_s: int

    # Totals by method (seconds)
    strava_gap: float
    minetti_gap: float
    strava_minetti_gap: float
    personalized: Optional[float]
    tobler: float
    naismith: float

    # Per-segment (for detailed analysis)
    segments: List[SegmentPredictions]

    def get_predictions_dict(self) -> Dict[str, float]:
        """Get all predictions as dict."""
        result = {
            "strava_gap": self.strava_gap,
            "minetti_gap": self.minetti_gap,
            "strava_minetti_gap": self.strava_minetti_gap,
            "tobler": self.tobler,
            "naismith": self.naismith,
        }
        if self.personalized is not None:
            result["personalized"] = self.personalized
        return result


class CalculatorAdapter:
    """
    Adapter to run virtual routes through calculators.

    Initializes all calculators and provides a unified interface
    for getting predictions.
    """

    def __init__(
        self,
        run_profile: Optional[UserRunProfile] = None,
        flat_pace_min_km: float = DEFAULT_FLAT_PACE_MIN_KM,
    ):
        """
        Initialize adapter with optional user profile.

        Args:
            run_profile: User's run profile for personalization
            flat_pace_min_km: Base flat pace for GAP calculations
        """
        self._flat_pace = flat_pace_min_km

        # GAP calculator
        self._gap = GAPCalculator(flat_pace_min_km=flat_pace_min_km)

        # Hiking calculators
        self._tobler = ToblerCalculator()
        self._naismith = NaismithCalculator()

        # Personalization (if profile available)
        self._personalization = None
        if run_profile and run_profile.has_profile_data:
            self._personalization = RunPersonalizationService(run_profile)

    def calculate_route(self, route: VirtualRoute) -> RoutePredictions:
        """
        Calculate predictions for entire route.

        Args:
            route: Virtual route to analyze

        Returns:
            RoutePredictions with all method results
        """
        segment_predictions = []

        # Accumulators for totals
        total_strava = 0.0
        total_minetti = 0.0
        total_strava_minetti = 0.0
        total_personalized = 0.0 if self._personalization else None
        total_tobler = 0.0
        total_naismith = 0.0

        for i, segment in enumerate(route.segments):
            seg_pred = self._calculate_segment(i, segment)
            segment_predictions.append(seg_pred)

            # Accumulate totals
            total_strava += seg_pred.strava_gap
            total_minetti += seg_pred.minetti_gap
            total_strava_minetti += seg_pred.strava_minetti_gap
            total_tobler += seg_pred.tobler
            total_naismith += seg_pred.naismith

            if seg_pred.personalized is not None:
                total_personalized += seg_pred.personalized

        return RoutePredictions(
            activity_id=route.activity_id,
            activity_name=route.activity_name,
            actual_time_s=route.actual_total_time_s,
            strava_gap=total_strava,
            minetti_gap=total_minetti,
            strava_minetti_gap=total_strava_minetti,
            personalized=total_personalized,
            tobler=total_tobler,
            naismith=total_naismith,
            segments=segment_predictions,
        )

    def _calculate_segment(
        self,
        index: int,
        segment: VirtualSegment
    ) -> SegmentPredictions:
        """Calculate predictions for single segment."""

        distance_km = segment.distance_m / 1000
        gradient = segment.gradient_percent

        # GAP methods (returns hours, convert to seconds)
        strava_time = self._gap.calculate_strava_gap(
            distance_km, gradient
        ) * 3600

        minetti_time = self._gap.calculate_minetti_gap(
            distance_km, gradient
        ) * 3600

        strava_minetti_time = self._gap.calculate_strava_minetti_gap(
            distance_km, gradient
        ) * 3600

        # Hiking methods
        tobler_time = self._tobler.calculate_segment_time(
            distance_km, gradient
        ) * 3600

        naismith_time = self._naismith.calculate_segment_time(
            distance_km, gradient
        ) * 3600

        # Personalized (if available)
        personalized_time = None
        if self._personalization:
            pers_result = self._personalization.calculate_segment_time(
                distance_km, gradient
            )
            personalized_time = pers_result * 3600

        return SegmentPredictions(
            segment_index=index,
            distance_m=segment.distance_m,
            gradient_percent=gradient,
            actual_time_s=segment.actual_time_s,
            strava_gap=strava_time,
            minetti_gap=minetti_time,
            strava_minetti_gap=strava_minetti_time,
            personalized=personalized_time,
            tobler=tobler_time,
            naismith=naismith_time,
        )
```

---

## Обновить `__init__.py`

```python
"""Calibration tools for validating prediction accuracy."""

from .virtual_route import VirtualRouteBuilder, VirtualRoute, VirtualSegment
from .calculators import CalculatorAdapter, RoutePredictions, SegmentPredictions

__all__ = [
    "VirtualRouteBuilder",
    "VirtualRoute",
    "VirtualSegment",
    "CalculatorAdapter",
    "RoutePredictions",
    "SegmentPredictions",
]
```

---

## Проверка

```python
# test_calculators.py

import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.features.strava.models import StravaActivity
from app.models.user_run_profile import UserRunProfile
from tools.calibration import VirtualRouteBuilder, CalculatorAdapter


async def test():
    async with async_session() as session:
        # Get activity with splits
        result = await session.execute(
            select(StravaActivity)
            .options(selectinload(StravaActivity.splits))
            .where(StravaActivity.splits_synced == 1)
            .limit(1)
        )
        activity = result.scalar_one_or_none()

        if not activity:
            print("No activities found")
            return

        # Get user profile
        profile_result = await session.execute(
            select(UserRunProfile)
            .where(UserRunProfile.user_id == activity.user_id)
        )
        profile = profile_result.scalar_one_or_none()

        # Build route
        builder = VirtualRouteBuilder()
        route = builder.build_from_activity(activity, activity.splits)

        if not route:
            print("Failed to build route")
            return

        # Calculate predictions
        adapter = CalculatorAdapter(run_profile=profile)
        predictions = adapter.calculate_route(route)

        # Print results
        print(f"Activity: {predictions.activity_name}")
        print(f"Actual time: {predictions.actual_time_s / 60:.0f} min")
        print()
        print("Predictions:")
        print(f"  Strava GAP:       {predictions.strava_gap / 60:.0f} min")
        print(f"  Minetti GAP:      {predictions.minetti_gap / 60:.0f} min")
        print(f"  Strava+Minetti:   {predictions.strava_minetti_gap / 60:.0f} min")
        if predictions.personalized:
            print(f"  Personalized:     {predictions.personalized / 60:.0f} min")
        print(f"  Tobler (hiking):  {predictions.tobler / 60:.0f} min")
        print(f"  Naismith (hiking):{predictions.naismith / 60:.0f} min")


if __name__ == "__main__":
    asyncio.run(test())
```

**Ожидаемый вывод:**

```
Activity: Morning Trail Run
Actual time: 75 min

Predictions:
  Strava GAP:       71 min
  Minetti GAP:      68 min
  Strava+Minetti:   70 min
  Personalized:     74 min
  Tobler (hiking):  92 min
  Naismith (hiking):108 min
```

---

## Примечания

**Возможные проблемы:**
1. Интерфейс калькуляторов может отличаться — нужно будет адаптировать
2. Некоторые калькуляторы могут требовать дополнительные параметры

**При реализации:**
- Сначала проверить реальные сигнатуры методов калькуляторов
- Адаптировать код под фактический API

---

## Чеклист

- [ ] `calculators.py` создан
- [ ] `__init__.py` обновлён
- [ ] Интерфейсы калькуляторов проверены
- [ ] Тест проходит — predictions генерируются
- [ ] Все методы возвращают разумные значения
