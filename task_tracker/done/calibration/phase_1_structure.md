# Фаза 1: Структура и VirtualRouteBuilder

**Статус:** Готово к реализации
**Зависимости:** —
**Строк кода:** ~80

---

## Цель

1. Создать структуру директорий `backend/tools/calibration/`
2. Реализовать конвертацию Strava splits → виртуальный маршрут

---

## Что создаём

```
backend/
├── tools/
│   ├── __init__.py
│   └── calibration/
│       ├── __init__.py
│       └── virtual_route.py
```

---

## Код

### 1. `backend/tools/__init__.py`

```python
"""Development tools for GPX Predictor."""
```

### 2. `backend/tools/calibration/__init__.py`

```python
"""
Calibration tools for validating prediction accuracy.

Usage:
    python -m tools.calibration.cli backtest --user-id <user_id>
"""

from .virtual_route import VirtualRouteBuilder, VirtualRoute, VirtualSegment

__all__ = ["VirtualRouteBuilder", "VirtualRoute", "VirtualSegment"]
```

### 3. `backend/tools/calibration/virtual_route.py`

```python
"""
Virtual route builder for backtesting.

Converts Strava activity splits into a format suitable for
running through our calculators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.features.strava.models import StravaActivity, StravaActivitySplit


@dataclass
class VirtualSegment:
    """One segment of a virtual route (typically ~1km)."""

    distance_m: float
    gradient_percent: float
    elevation_diff_m: float
    actual_time_s: int  # Ground truth from Strava


@dataclass
class VirtualRoute:
    """Virtual route built from Strava splits."""

    # Activity info
    activity_id: int
    strava_id: int
    activity_name: str
    activity_type: str
    activity_date: datetime

    # Segments
    segments: List[VirtualSegment] = field(default_factory=list)

    # Totals (calculated)
    @property
    def total_distance_m(self) -> float:
        return sum(s.distance_m for s in self.segments)

    @property
    def total_distance_km(self) -> float:
        return self.total_distance_m / 1000

    @property
    def total_elevation_gain_m(self) -> float:
        return sum(s.elevation_diff_m for s in self.segments if s.elevation_diff_m > 0)

    @property
    def total_elevation_loss_m(self) -> float:
        return abs(sum(s.elevation_diff_m for s in self.segments if s.elevation_diff_m < 0))

    @property
    def actual_total_time_s(self) -> int:
        return sum(s.actual_time_s for s in self.segments)

    @property
    def actual_total_time_hours(self) -> float:
        return self.actual_total_time_s / 3600


class VirtualRouteBuilder:
    """
    Builds virtual routes from Strava activities.

    Converts splits (1km segments with elevation data) into
    a format our calculators can process.
    """

    def build_from_activity(
        self,
        activity: StravaActivity,
        splits: List[StravaActivitySplit]
    ) -> Optional[VirtualRoute]:
        """
        Build a virtual route from activity and its splits.

        Args:
            activity: Strava activity record
            splits: List of splits for this activity

        Returns:
            VirtualRoute or None if not enough data
        """
        if not splits:
            return None

        segments = []
        for split in splits:
            # Skip invalid splits
            if not split.distance_m or split.distance_m <= 0:
                continue
            if split.moving_time_s is None or split.moving_time_s <= 0:
                continue

            # Calculate gradient if not available
            gradient = split.gradient_percent
            if gradient is None and split.elevation_diff_m is not None:
                gradient = (split.elevation_diff_m / split.distance_m) * 100

            # Default to 0 if still None
            if gradient is None:
                gradient = 0.0

            segment = VirtualSegment(
                distance_m=split.distance_m,
                gradient_percent=round(gradient, 1),
                elevation_diff_m=split.elevation_diff_m or 0.0,
                actual_time_s=split.moving_time_s,
            )
            segments.append(segment)

        if not segments:
            return None

        return VirtualRoute(
            activity_id=activity.id,
            strava_id=activity.strava_id,
            activity_name=activity.name or "Unnamed",
            activity_type=activity.activity_type,
            activity_date=activity.start_date,
            segments=segments,
        )
```

---

## Проверка

После реализации — простой тест:

```python
# test_virtual_route.py (в консоли или как скрипт)

import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.features.strava.models import StravaActivity
from tools.calibration import VirtualRouteBuilder


async def test():
    async with async_session() as session:
        # Берём первую активность с splits
        result = await session.execute(
            select(StravaActivity)
            .options(selectinload(StravaActivity.splits))
            .where(StravaActivity.splits_synced == 1)
            .limit(1)
        )
        activity = result.scalar_one_or_none()

        if not activity:
            print("No activities with splits found")
            return

        builder = VirtualRouteBuilder()
        route = builder.build_from_activity(activity, activity.splits)

        if route:
            print(f"Activity: {route.activity_name}")
            print(f"Date: {route.activity_date}")
            print(f"Segments: {len(route.segments)}")
            print(f"Distance: {route.total_distance_km:.1f} km")
            print(f"D+: {route.total_elevation_gain_m:.0f} m")
            print(f"Actual time: {route.actual_total_time_s / 60:.0f} min")
            print()
            print("First 3 segments:")
            for i, seg in enumerate(route.segments[:3], 1):
                print(f"  {i}. {seg.distance_m:.0f}m, {seg.gradient_percent:+.1f}%, {seg.actual_time_s}s")
        else:
            print("Failed to build route")


if __name__ == "__main__":
    asyncio.run(test())
```

**Ожидаемый вывод:**

```
Activity: Morning Trail Run
Date: 2026-01-28 08:30:00
Segments: 12
Distance: 12.3 km
D+: 450 m
Actual time: 75 min

First 3 segments:
  1. 1000m, +2.3%, 312s
  2. 1000m, +5.1%, 345s
  3. 1000m, -1.2%, 285s
```

---

## Чеклист

- [ ] Создана директория `backend/tools/`
- [ ] Создана директория `backend/tools/calibration/`
- [ ] `__init__.py` файлы на месте
- [ ] `virtual_route.py` реализован
- [ ] Тест проходит — route строится из splits
