# Trail Running Implementation - Part 1

**Фазы:** 0 (Рефакторинг) + 1 (GAP Calculator)
**Статус:** Draft
**Дата:** 2026-01-23

---

## Содержание

1. [Обзор Part 1](#1-обзор-part-1)
2. [Фаза 0: Рефакторинг PersonalizationService](#2-фаза-0-рефакторинг-personalizationservice)
3. [Фаза 1: GAP Calculator](#3-фаза-1-gap-calculator)
4. [Чеклист Part 1](#4-чеклист-part-1)

---

## 1. Обзор Part 1

### Цели

1. Подготовить инфраструктуру для Run-персонализации
2. Создать GAP калькулятор с двумя режимами (Strava / Minetti+Strava)
3. Не ломать существующий hiking функционал

### Структура файлов после Part 1

```
backend/app/services/calculators/
├── base.py                      # Без изменений
├── segmenter.py                 # Без изменений
├── tobler.py                    # Без изменений
├── naismith.py                  # Без изменений
├── fatigue.py                   # Без изменений
├── comparison.py                # Минимальные изменения (импорты)
│
├── personalization_base.py      # НОВЫЙ: BasePersonalizationService
├── personalization.py           # РЕФАКТОРИНГ → HikePersonalizationService
├── personalization_run.py       # НОВЫЙ: RunPersonalizationService
│
├── trail_run/
│   ├── __init__.py              # НОВЫЙ
│   └── gap_calculator.py        # НОВЫЙ: GAPCalculator
│
└── __init__.py                  # Обновить экспорты
```

---

## 2. Фаза 0: Рефакторинг PersonalizationService

### 2.1 Цель

Выделить общую логику в базовый класс, чтобы:
- `HikePersonalizationService` — для Hike/Walk (текущий код)
- `RunPersonalizationService` — для Run/TrailRun (новый)

### 2.2 personalization_base.py

```python
"""
Base Personalization Service

Abstract base class for terrain-based pace personalization.
Shared logic for Hike and Run personalization services.
"""

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from app.services.calculators.base import MacroSegment, MethodResult


# Gradient thresholds for terrain classification (7 categories)
GRADIENT_THRESHOLDS = {
    'steep_downhill': (-100.0, -15.0),
    'moderate_downhill': (-15.0, -8.0),
    'gentle_downhill': (-8.0, -3.0),
    'flat': (-3.0, 3.0),
    'gentle_uphill': (3.0, 8.0),
    'moderate_uphill': (8.0, 15.0),
    'steep_uphill': (15.0, 100.0),
}

# Legacy thresholds (3 categories)
FLAT_GRADIENT_MIN = -3.0
FLAT_GRADIENT_MAX = 3.0

# Minimum activities required
MIN_ACTIVITIES_FOR_PROFILE = 1


class BasePersonalizationService(ABC):
    """
    Abstract base class for personalization services.

    Provides common logic:
    - 7-category gradient classification
    - Segment time calculation
    - Fallback to base calculator
    - Profile validation pattern
    """

    def __init__(self, use_extended_gradients: bool = False):
        """
        Args:
            use_extended_gradients: If True, use 7-category system.
                                   If False, use legacy 3-category.
        """
        self.use_extended_gradients = use_extended_gradients

    def calculate_segment(
        self,
        segment: MacroSegment,
        base_method: str = "personalized"
    ) -> MethodResult:
        """
        Calculate personalized time for a single segment.

        Args:
            segment: MacroSegment with distance and gradient
            base_method: Base method name (e.g., "tobler" → "tobler_personalized")

        Returns:
            MethodResult with personalized speed and time
        """
        pace_min_km = self._get_pace_for_gradient(segment.gradient_percent)
        speed_kmh = 60 / pace_min_km if pace_min_km > 0 else self._get_default_speed()
        time_hours = segment.distance_km / speed_kmh if speed_kmh > 0 else 0.0

        terrain_type = self._classify_terrain(segment.gradient_percent)
        formula = self._build_formula(segment, pace_min_km, speed_kmh, time_hours, terrain_type)

        method_name = f"{base_method}_personalized" if base_method != "personalized" else "personalized"

        return MethodResult(
            method_name=method_name,
            speed_kmh=round(speed_kmh, 2),
            time_hours=round(time_hours, 4),
            formula_used=formula
        )

    def calculate_route(
        self,
        segments: List[MacroSegment],
        base_method: str = "personalized"
    ) -> tuple[float, List[MethodResult]]:
        """Calculate total personalized time for a route."""
        results = []
        total_hours = 0.0

        for segment in segments:
            result = self.calculate_segment(segment, base_method)
            results.append(result)
            total_hours += result.time_hours

        return total_hours, results

    def _get_pace_for_gradient(self, gradient_percent: float) -> float:
        """Get pace for gradient using extended or legacy system."""
        if self.use_extended_gradients:
            return self._get_pace_extended(gradient_percent)
        else:
            return self._get_pace_legacy(gradient_percent)

    def _get_pace_extended(self, gradient_percent: float) -> float:
        """Get pace using 7-category system with fallback."""
        category = self._classify_gradient_extended(gradient_percent)
        pace = self._get_pace_for_category(category)

        if pace is not None:
            return pace

        # Fallback to base calculator estimation
        return self._estimate_pace_for_gradient(gradient_percent)

    def _classify_gradient_extended(self, gradient_percent: float) -> str:
        """Classify gradient into one of 7 categories."""
        for category, (min_grad, max_grad) in GRADIENT_THRESHOLDS.items():
            if min_grad <= gradient_percent < max_grad:
                return category

        if gradient_percent >= 15.0:
            return 'steep_uphill'
        if gradient_percent <= -15.0:
            return 'steep_downhill'
        return 'flat'

    def _classify_terrain(self, gradient_percent: float) -> str:
        """Classify terrain for display."""
        if self.use_extended_gradients:
            return self._classify_gradient_extended(gradient_percent)
        else:
            if gradient_percent > FLAT_GRADIENT_MAX:
                return "uphill"
            elif gradient_percent < FLAT_GRADIENT_MIN:
                return "downhill"
            return "flat"

    def _build_formula(
        self,
        segment: MacroSegment,
        pace: float,
        speed: float,
        time: float,
        terrain: str
    ) -> str:
        """Build formula string for result."""
        return (
            f"Personal {terrain} pace: {pace:.1f} min/km = {speed:.1f} km/h, "
            f"{segment.distance_km:.2f}km / {speed:.1f}km/h = {time:.3f}h"
        )

    # === ABSTRACT METHODS (implement in subclasses) ===

    @abstractmethod
    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """Get pace using legacy 3-category system."""
        pass

    @abstractmethod
    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """Get pace from profile for extended category."""
        pass

    @abstractmethod
    def _get_default_speed(self) -> float:
        """Default speed when no data (km/h)."""
        pass

    @abstractmethod
    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """Estimate pace using base calculator (Tobler for hike, GAP for run)."""
        pass

    @staticmethod
    @abstractmethod
    def is_profile_valid(profile) -> bool:
        """Check if profile has enough data for personalization."""
        pass
```

### 2.3 personalization.py (рефакторинг)

```python
"""
Hike Personalization Service

Applies user Hike/Walk performance profile to route segments.
Inherits from BasePersonalizationService.
"""

import math
from typing import Optional

from app.models.user_profile import UserPerformanceProfile
from app.services.calculators.personalization_base import (
    BasePersonalizationService,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)


# Fallback speeds for hiking (km/h)
DEFAULT_FLAT_SPEED_KMH = 5.0
DEFAULT_UPHILL_SPEED_KMH = 3.3
DEFAULT_DOWNHILL_SPEED_KMH = 6.0


class HikePersonalizationService(BasePersonalizationService):
    """
    Personalization service for Hike/Walk activities.

    Uses Tobler's hiking function as fallback calculator.
    Profile data from Strava Hike/Walk activities.
    """

    def __init__(
        self,
        profile: UserPerformanceProfile,
        use_extended_gradients: bool = False
    ):
        super().__init__(use_extended_gradients)
        self.profile = profile

    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """Legacy 3-category: flat, uphill, downhill."""
        if gradient_percent > FLAT_GRADIENT_MAX:
            return self.profile.avg_uphill_pace_min_km or self._estimate_uphill_pace()
        elif gradient_percent < FLAT_GRADIENT_MIN:
            return self.profile.avg_downhill_pace_min_km or self._estimate_downhill_pace()
        else:
            return self.profile.avg_flat_pace_min_km or (60 / DEFAULT_FLAT_SPEED_KMH)

    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """Map 7-category to profile fields."""
        mapping = {
            'steep_downhill': self.profile.avg_steep_downhill_pace_min_km,
            'moderate_downhill': self.profile.avg_moderate_downhill_pace_min_km,
            'gentle_downhill': self.profile.avg_gentle_downhill_pace_min_km,
            'flat': self.profile.avg_flat_pace_min_km,
            'gentle_uphill': self.profile.avg_gentle_uphill_pace_min_km,
            'moderate_uphill': self.profile.avg_moderate_uphill_pace_min_km,
            'steep_uphill': self.profile.avg_steep_uphill_pace_min_km,
        }
        return mapping.get(category)

    def _get_default_speed(self) -> float:
        return DEFAULT_FLAT_SPEED_KMH

    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """Use Tobler's function scaled by user's flat pace."""
        flat_pace = self.profile.avg_flat_pace_min_km
        if flat_pace:
            flat_speed = 60 / flat_pace
        else:
            flat_speed = DEFAULT_FLAT_SPEED_KMH

        tobler_speed = self._tobler_speed(gradient_percent / 100)
        scale_factor = flat_speed / 5.0
        estimated_speed = tobler_speed * scale_factor

        return 60 / estimated_speed if estimated_speed > 0 else 60 / DEFAULT_FLAT_SPEED_KMH

    def _tobler_speed(self, gradient_decimal: float) -> float:
        """Tobler's hiking function: v = 6 * exp(-3.5 * |s + 0.05|)"""
        exponent = -3.5 * abs(gradient_decimal + 0.05)
        return 6.0 * math.exp(exponent)

    def _estimate_uphill_pace(self) -> float:
        """~50% slower on uphills."""
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 1.5
        return 60 / DEFAULT_UPHILL_SPEED_KMH

    def _estimate_downhill_pace(self) -> float:
        """~20% faster on descents."""
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 0.83
        return 60 / DEFAULT_DOWNHILL_SPEED_KMH

    @staticmethod
    def is_profile_valid(profile: Optional[UserPerformanceProfile]) -> bool:
        """Check if hike profile has enough data."""
        if not profile:
            return False
        if not profile.avg_flat_pace_min_km:
            return False
        if profile.total_activities_analyzed < MIN_ACTIVITIES_FOR_PROFILE:
            return False
        return True

    @staticmethod
    def get_profile_summary(
        profile: Optional[UserPerformanceProfile],
        include_extended: bool = False
    ) -> dict:
        """Get summary for API response."""
        if not profile:
            return {}

        summary = {
            "activities_analyzed": profile.total_activities_analyzed,
            "flat_pace_min_km": profile.avg_flat_pace_min_km,
            "uphill_pace_min_km": profile.avg_uphill_pace_min_km,
            "downhill_pace_min_km": profile.avg_downhill_pace_min_km,
            "has_split_data": getattr(profile, 'has_split_data', False),
            "has_extended_gradient_data": getattr(profile, 'has_extended_gradient_data', False),
        }

        if include_extended:
            summary["extended_gradients"] = {
                "steep_downhill_pace": profile.avg_steep_downhill_pace_min_km,
                "moderate_downhill_pace": profile.avg_moderate_downhill_pace_min_km,
                "gentle_downhill_pace": profile.avg_gentle_downhill_pace_min_km,
                "gentle_uphill_pace": profile.avg_gentle_uphill_pace_min_km,
                "moderate_uphill_pace": profile.avg_moderate_uphill_pace_min_km,
                "steep_uphill_pace": profile.avg_steep_uphill_pace_min_km,
            }

        return summary


# Backward compatibility alias
PersonalizationService = HikePersonalizationService
```

### 2.4 Обратная совместимость

В `comparison.py` и других файлах менять импорты НЕ нужно:
```python
# Это продолжит работать
from app.services.calculators.personalization import PersonalizationService
```

---

## 3. Фаза 1: GAP Calculator

### 3.1 Цель

Создать калькулятор для трейлраннинга с двумя режимами:
1. **strava_gap** — чистая модель Strava (lookup table)
2. **minetti_gap** — гибрид Minetti (подъёмы) + Strava (спуски)

### 3.2 trail_run/gap_calculator.py

```python
"""
Grade Adjusted Pace (GAP) Calculator for Trail Running.

Two calculation modes:
1. strava_gap - Pure Strava model (empirical, 240k athletes)
2. minetti_gap - Minetti uphill + Strava downhill (hybrid)

References:
- Minetti et al. (2002) - Energy cost of walking/running at extreme slopes
- Strava Engineering (2017) - Improved GAP model
"""

from dataclasses import dataclass
from enum import Enum
from math import exp
from typing import Optional

from app.services.calculators.base import MacroSegment, MethodResult


class GAPMode(Enum):
    """GAP calculation mode."""
    STRAVA = "strava_gap"      # Pure Strava model
    MINETTI = "minetti_gap"    # Minetti + Strava hybrid


@dataclass
class GAPResult:
    """Result of GAP calculation for a single gradient."""
    gradient_percent: float
    pace_adjustment: float      # 1.0 = flat, 1.5 = +50% slower
    adjusted_pace_min_km: float
    energy_cost_ratio: float    # Relative to flat (Minetti only)
    mode: str                   # Which model was used


# Strava GAP lookup table (based on 2017 model)
# Key: gradient percent, Value: pace adjustment factor
STRAVA_GAP_TABLE = {
    -30: 1.15,   # Very steep descent: braking required
    -25: 1.05,
    -20: 0.95,
    -15: 0.90,
    -10: 0.88,   # Near optimal descent
    -9:  0.88,   # Optimal descent (Strava)
    -5:  0.92,
    -3:  0.96,
    0:   1.00,   # Flat
    3:   1.08,
    5:   1.15,
    8:   1.28,
    10:  1.38,
    12:  1.50,
    15:  1.70,
    18:  1.95,
    20:  2.15,
    25:  2.70,
    30:  3.30,
    35:  4.00,
    40:  4.80,
    45:  5.70,
}


class GAPCalculator:
    """
    Grade Adjusted Pace calculator for trail running.

    Usage:
        # Strava mode (recommended for most users)
        calc = GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.STRAVA)

        # Minetti mode (more scientific, aggressive on steep uphills)
        calc = GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.MINETTI)
    """

    # Minetti constants
    FLAT_ENERGY_COST = 3.6      # J/kg/m on flat

    # Strava constants
    STRAVA_OPTIMAL_DESCENT = -9.0  # Optimal descent gradient (%)
    STRAVA_MAX_DESCENT_BENEFIT = 0.88  # Max speedup on descent (12% faster)

    def __init__(
        self,
        base_flat_pace_min_km: float = 6.0,
        mode: GAPMode = GAPMode.STRAVA
    ):
        """
        Args:
            base_flat_pace_min_km: User's flat pace (min/km).
                                  Should be "conversational" Z2 pace for long efforts.
            mode: Calculation mode (STRAVA or MINETTI)
        """
        self.base_flat_pace = base_flat_pace_min_km
        self.mode = mode

    def calculate(self, gradient_percent: float) -> GAPResult:
        """
        Calculate adjusted pace for given gradient.

        Args:
            gradient_percent: Gradient as percentage (10 = 10% uphill)

        Returns:
            GAPResult with adjusted pace and metadata
        """
        if self.mode == GAPMode.STRAVA:
            return self._calculate_strava(gradient_percent)
        else:
            return self._calculate_minetti(gradient_percent)

    def calculate_segment(self, segment: MacroSegment) -> MethodResult:
        """
        Calculate time for a MacroSegment.

        Compatible with ToblerCalculator/NaismithCalculator interface.
        """
        result = self.calculate(segment.gradient_percent)
        speed_kmh = 60 / result.adjusted_pace_min_km
        time_hours = segment.distance_km / speed_kmh

        return MethodResult(
            method_name=self.mode.value,
            speed_kmh=round(speed_kmh, 2),
            time_hours=round(time_hours, 4),
            formula_used=(
                f"GAP ({self.mode.value}): {result.adjusted_pace_min_km:.2f} min/km "
                f"(adj: x{result.pace_adjustment:.2f})"
            )
        )

    # === STRAVA MODEL ===

    def _calculate_strava(self, gradient_percent: float) -> GAPResult:
        """Pure Strava GAP model using lookup table with interpolation."""
        pace_adj = self._interpolate_strava(gradient_percent)
        adjusted_pace = self.base_flat_pace * pace_adj

        return GAPResult(
            gradient_percent=gradient_percent,
            pace_adjustment=round(pace_adj, 3),
            adjusted_pace_min_km=round(adjusted_pace, 2),
            energy_cost_ratio=pace_adj,  # Approximation for Strava
            mode=GAPMode.STRAVA.value
        )

    def _interpolate_strava(self, gradient: float) -> float:
        """Interpolate between Strava lookup table values."""
        # Get sorted gradients
        gradients = sorted(STRAVA_GAP_TABLE.keys())

        # Clamp to table range
        if gradient <= gradients[0]:
            return STRAVA_GAP_TABLE[gradients[0]]
        if gradient >= gradients[-1]:
            return STRAVA_GAP_TABLE[gradients[-1]]

        # Find surrounding points
        for i in range(len(gradients) - 1):
            g1, g2 = gradients[i], gradients[i + 1]
            if g1 <= gradient <= g2:
                # Linear interpolation
                v1, v2 = STRAVA_GAP_TABLE[g1], STRAVA_GAP_TABLE[g2]
                t = (gradient - g1) / (g2 - g1)
                return v1 + t * (v2 - v1)

        return 1.0  # Fallback

    # === MINETTI MODEL ===

    def _calculate_minetti(self, gradient_percent: float) -> GAPResult:
        """
        Hybrid model: Minetti for uphills, Strava for downhills.

        Minetti is more aggressive on steep uphills (scientific basis),
        but unrealistic on downhills (predicts too much speedup).
        """
        gradient_decimal = gradient_percent / 100

        if gradient_decimal >= 0:
            # Uphill: use Minetti
            energy_ratio = self._minetti_energy_cost(gradient_decimal)
            # Convert energy to pace (power law relationship)
            pace_adj = energy_ratio ** 0.75
        else:
            # Downhill: use Strava (more realistic)
            pace_adj = self._interpolate_strava(gradient_percent)
            energy_ratio = pace_adj  # Approximation

        adjusted_pace = self.base_flat_pace * pace_adj

        return GAPResult(
            gradient_percent=gradient_percent,
            pace_adjustment=round(pace_adj, 3),
            adjusted_pace_min_km=round(adjusted_pace, 2),
            energy_cost_ratio=round(energy_ratio, 3),
            mode=GAPMode.MINETTI.value
        )

    def _minetti_energy_cost(self, gradient_decimal: float) -> float:
        """
        Minetti's polynomial for energy cost (J/kg/m).

        Formula: 155.4i^5 - 30.4i^4 - 43.3i^3 + 46.3i^2 + 19.5i + 3.6

        Returns ratio relative to flat.
        """
        i = gradient_decimal
        cost = (
            155.4 * i**5
            - 30.4 * i**4
            - 43.3 * i**3
            + 46.3 * i**2
            + 19.5 * i
            + self.FLAT_ENERGY_COST
        )
        return cost / self.FLAT_ENERGY_COST

    # === UTILITY ===

    def get_info(self) -> dict:
        """Get calculator info for API response."""
        return {
            "mode": self.mode.value,
            "base_flat_pace_min_km": self.base_flat_pace,
            "base_flat_speed_kmh": round(60 / self.base_flat_pace, 1),
            "example_adjustments": {
                "-15%": round(self.calculate(-15).pace_adjustment, 2),
                "-9%": round(self.calculate(-9).pace_adjustment, 2),
                "0%": round(self.calculate(0).pace_adjustment, 2),
                "+10%": round(self.calculate(10).pace_adjustment, 2),
                "+20%": round(self.calculate(20).pace_adjustment, 2),
                "+30%": round(self.calculate(30).pace_adjustment, 2),
            }
        }


def compare_gap_modes(
    base_pace: float = 6.0,
    gradients: list = None
) -> dict:
    """
    Compare Strava vs Minetti modes for debugging/testing.

    Args:
        base_pace: Flat pace in min/km
        gradients: List of gradients to compare (default: common values)

    Returns:
        Dict with comparison data
    """
    if gradients is None:
        gradients = [-20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30]

    strava = GAPCalculator(base_pace, GAPMode.STRAVA)
    minetti = GAPCalculator(base_pace, GAPMode.MINETTI)

    comparison = {}
    for g in gradients:
        s = strava.calculate(g)
        m = minetti.calculate(g)
        comparison[f"{g}%"] = {
            "strava_adj": s.pace_adjustment,
            "minetti_adj": m.pace_adjustment,
            "difference": round(m.pace_adjustment - s.pace_adjustment, 3),
            "strava_pace": s.adjusted_pace_min_km,
            "minetti_pace": m.adjusted_pace_min_km,
        }

    return comparison
```

### 3.3 trail_run/__init__.py

```python
"""
Trail Running calculators package.

Contains:
- GAPCalculator: Grade Adjusted Pace for trail running
- (Future) HikeRunThresholdService
- (Future) RunnerFatigueService
- (Future) TrailRunService
"""

from .gap_calculator import (
    GAPCalculator,
    GAPMode,
    GAPResult,
    STRAVA_GAP_TABLE,
    compare_gap_modes,
)

__all__ = [
    'GAPCalculator',
    'GAPMode',
    'GAPResult',
    'STRAVA_GAP_TABLE',
    'compare_gap_modes',
]
```

---

## 4. Чеклист Part 1

### Фаза 0: Рефакторинг

- [x] Создать `personalization_base.py` с `BasePersonalizationService`
- [x] Рефакторинг `personalization.py` → `HikePersonalizationService`
- [x] Проверить обратную совместимость (alias `PersonalizationService`)
- [x] Убедиться, что существующие тесты проходят

### Фаза 1: GAP Calculator

- [x] Создать директорию `trail_run/`
- [x] Реализовать `GAPCalculator` с двумя режимами
- [x] Добавить `STRAVA_GAP_TABLE` lookup table
- [x] Добавить `compare_gap_modes()` для тестирования

### Тестирование Part 1

- [x] Unit-тесты для `BasePersonalizationService` (27 тестов в test_personalization.py)
- [x] Unit-тесты для `HikePersonalizationService`
- [x] Unit-тесты для `GAPCalculator` (Strava mode) (38 тестов в test_gap_calculator.py)
- [x] Unit-тесты для `GAPCalculator` (Minetti mode)
- [x] Сравнительный тест Strava vs Minetti

### Документация

- [x] Обновить `ARCHITECTURE_CALCULATIONS.md` — добавить GAP формулы
- [ ] Обновить `ARCHITECTURE.md` — добавить новые файлы

---

## Статус Part 1: ✅ ЗАВЕРШЕНО

**Дата завершения:** 2026-01-23

**Результаты:**
- 65 тестов passed (27 personalization + 38 GAP)
- Обратная совместимость подтверждена
- ComparisonService работает без изменений

---

## Переход к Part 2

После успешного завершения Part 1:
1. ✅ GAP калькулятор работает в обоих режимах
2. ✅ Hiking персонализация не сломана
3. ✅ Базовый класс готов для `RunPersonalizationService`

**Part 2 содержит:** Hike/Run порог, Run персонализация, модель усталости для бегунов
