# Trail Running Implementation - Part 2

**Фазы:** 2 (Hike/Run порог) + 3 (Run персонализация) + 4 (Усталость)
**Зависит от:** Part 1
**Статус:** Draft
**Дата:** 2026-01-23

---

## Содержание

1. [Обзор Part 2](#1-обзор-part-2)
2. [Фаза 2: Hike/Run порог](#2-фаза-2-hikerun-порог)
3. [Фаза 3: Run персонализация из Strava](#3-фаза-3-run-персонализация-из-strava)
4. [Фаза 4: Модель усталости для бегунов](#4-фаза-4-модель-усталости-для-бегунов)
5. [Чеклист Part 2](#5-чеклист-part-2)

---

## 1. Обзор Part 2

### Цели

1. Автоматическое определение участков бег/ходьба
2. Новая модель данных: раздельные таблицы `UserHikeProfile` и `UserRunProfile`
3. Персонализация для Run из Strava
4. Адаптированная модель усталости для бегунов

### Структура файлов после Part 2

```
backend/app/
├── models/
│   ├── user_profile.py          # РЕФАКТОРИНГ → user_hike_profile.py
│   ├── user_hike_profile.py     # НОВЫЙ (или переименованный)
│   └── user_run_profile.py      # НОВЫЙ
│
├── services/calculators/
│   ├── personalization_base.py  # Из Part 1
│   ├── personalization.py       # HikePersonalizationService
│   ├── personalization_run.py   # НОВЫЙ: RunPersonalizationService
│   │
│   └── trail_run/
│       ├── gap_calculator.py    # Из Part 1
│       ├── hike_run_threshold.py # НОВЫЙ
│       └── runner_fatigue.py    # НОВЫЙ
│
└── alembic/versions/
    ├── 007_split_user_profiles.py  # НОВЫЙ: разделение таблиц
    └── 008_add_run_profile_fields.py # НОВЫЙ: поля для run
```

---

## 2. Фаза 2: Hike/Run порог

### 2.1 Цель

Автоматически определять участки, где бегун переходит на ходьбу (power hiking).

### 2.2 Научная основа

| Источник | Порог |
|----------|-------|
| Colorado Boulder | 15.8° ≈ 28% |
| Runner's World | 15-25% — большинство переходит |
| Элитные атлеты | До 30% |

**Выбранный дефолт:** 25% (консервативный для большинства)

### 2.3 trail_run/hike_run_threshold.py

```python
"""
Hike/Run Threshold Service

Determines when a trail runner should walk vs run based on gradient.
Supports static and dynamic thresholds.

References:
- University of Colorado Boulder (walking efficiency study)
- Runner's World power hiking guide
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from app.services.calculators.base import MacroSegment


class MovementMode(Enum):
    """Movement mode for a segment."""
    RUN = "run"
    HIKE = "hike"


@dataclass
class HikeRunDecision:
    """Decision for a single segment."""
    segment: MacroSegment
    mode: MovementMode
    threshold_used: float       # Threshold that triggered the decision (%)
    reason: str
    confidence: float           # 0.0 - 1.0


class HikeRunThresholdService:
    """
    Service for determining run vs walk mode on trail segments.

    Supports:
    - Static threshold: fixed gradient cutoff
    - Dynamic threshold: adjusts based on fatigue/distance
    - Personalization: learn threshold from Strava data
    """

    # Default thresholds
    DEFAULT_UPHILL_THRESHOLD = 25.0      # % gradient
    DEFAULT_DOWNHILL_THRESHOLD = -30.0   # % gradient (very steep technical)

    # Bounds for threshold adjustment
    MIN_THRESHOLD = 15.0
    MAX_THRESHOLD = 35.0

    def __init__(
        self,
        uphill_threshold: float = DEFAULT_UPHILL_THRESHOLD,
        downhill_threshold: float = DEFAULT_DOWNHILL_THRESHOLD,
        dynamic: bool = False
    ):
        """
        Args:
            uphill_threshold: Gradient (%) above which to walk
            downhill_threshold: Gradient (%) below which to walk (steep descent)
            dynamic: If True, threshold decreases with fatigue
        """
        self.base_uphill_threshold = uphill_threshold
        self.downhill_threshold = downhill_threshold
        self.dynamic = dynamic

    @classmethod
    def from_user_preference(
        cls,
        uphill_threshold: Optional[float] = None,
        dynamic: bool = False
    ) -> "HikeRunThresholdService":
        """Create service from user's manual preference."""
        return cls(
            uphill_threshold=uphill_threshold or cls.DEFAULT_UPHILL_THRESHOLD,
            dynamic=dynamic
        )

    @classmethod
    def from_strava_profile(
        cls,
        run_splits: List[dict],
        dynamic: bool = False
    ) -> "HikeRunThresholdService":
        """
        Detect threshold from Strava Run activity splits.

        Looks for the gradient where pace suddenly jumps (indicating walk).

        Args:
            run_splits: List of dicts with gradient_percent and pace_min_km
            dynamic: Enable dynamic threshold
        """
        if not run_splits or len(run_splits) < 10:
            return cls(dynamic=dynamic)

        # Sort by gradient
        sorted_splits = sorted(run_splits, key=lambda x: x.get("gradient_percent", 0))
        uphill_splits = [s for s in sorted_splits if s.get("gradient_percent", 0) > 5]

        if len(uphill_splits) < 5:
            return cls(dynamic=dynamic)

        # Find steepest pace derivative (where pace jumps)
        max_derivative = 0
        threshold = cls.DEFAULT_UPHILL_THRESHOLD

        for i in range(1, len(uphill_splits)):
            prev = uphill_splits[i - 1]
            curr = uphill_splits[i]

            prev_pace = prev.get("pace_min_km", 0)
            curr_pace = curr.get("pace_min_km", 0)
            prev_grad = prev.get("gradient_percent", 0)
            curr_grad = curr.get("gradient_percent", 0)

            pace_change = curr_pace - prev_pace
            gradient_change = curr_grad - prev_grad

            if gradient_change > 0 and pace_change > 0:
                derivative = pace_change / gradient_change
                if derivative > max_derivative:
                    max_derivative = derivative
                    threshold = (prev_grad + curr_grad) / 2

        # Clamp to reasonable range
        threshold = max(cls.MIN_THRESHOLD, min(cls.MAX_THRESHOLD, threshold))
        return cls(uphill_threshold=threshold, dynamic=dynamic)

    def get_threshold(
        self,
        elapsed_hours: float = 0,
        total_distance_km: float = 0
    ) -> float:
        """
        Get current threshold, adjusted for fatigue if dynamic=True.

        Args:
            elapsed_hours: Time since start
            total_distance_km: Total route distance (for ultra adjustments)

        Returns:
            Current uphill threshold (%)
        """
        if not self.dynamic:
            return self.base_uphill_threshold

        threshold = self.base_uphill_threshold

        # Fatigue: lower threshold after 2 hours (walk earlier when tired)
        if elapsed_hours > 2:
            fatigue_reduction = min(5.0, (elapsed_hours - 2) * 1.5)
            threshold -= fatigue_reduction

        # Ultra distance: lower threshold for 50k+
        if total_distance_km > 50:
            distance_reduction = min(3.0, (total_distance_km - 50) / 25)
            threshold -= distance_reduction

        return max(self.MIN_THRESHOLD, threshold)

    def decide(
        self,
        segment: MacroSegment,
        elapsed_hours: float = 0,
        total_distance_km: float = 0
    ) -> HikeRunDecision:
        """
        Decide run vs walk for a single segment.

        Args:
            segment: MacroSegment to evaluate
            elapsed_hours: Elapsed time (for dynamic threshold)
            total_distance_km: Total route distance (for ultra adjustment)

        Returns:
            HikeRunDecision with mode and explanation
        """
        gradient = segment.gradient_percent
        threshold = self.get_threshold(elapsed_hours, total_distance_km)

        # Steep uphill → walk
        if gradient >= threshold:
            return HikeRunDecision(
                segment=segment,
                mode=MovementMode.HIKE,
                threshold_used=threshold,
                reason=f"Steep uphill ({gradient:.1f}% >= {threshold:.1f}%)",
                confidence=0.9 if gradient > threshold + 5 else 0.7
            )

        # Very steep downhill → walk (technical terrain)
        if gradient <= self.downhill_threshold:
            return HikeRunDecision(
                segment=segment,
                mode=MovementMode.HIKE,
                threshold_used=self.downhill_threshold,
                reason=f"Technical descent ({gradient:.1f}% <= {self.downhill_threshold}%)",
                confidence=0.8
            )

        # Otherwise → run
        return HikeRunDecision(
            segment=segment,
            mode=MovementMode.RUN,
            threshold_used=threshold,
            reason="Runnable gradient",
            confidence=0.9
        )

    def process_route(
        self,
        segments: List[MacroSegment],
        total_distance_km: float = 0
    ) -> List[HikeRunDecision]:
        """
        Process all segments and return decisions.

        Uses iterative time estimation for dynamic threshold.

        Args:
            segments: Route segments
            total_distance_km: Total route distance

        Returns:
            List of HikeRunDecision for each segment
        """
        decisions = []
        elapsed_hours = 0.0

        for segment in segments:
            decision = self.decide(segment, elapsed_hours, total_distance_km)
            decisions.append(decision)

            # Estimate time for next iteration (rough)
            avg_speed = 9.0 if decision.mode == MovementMode.RUN else 4.5
            elapsed_hours += segment.distance_km / avg_speed

        return decisions

    def get_info(self) -> dict:
        """Get service configuration for API response."""
        return {
            "uphill_threshold": self.base_uphill_threshold,
            "downhill_threshold": self.downhill_threshold,
            "dynamic": self.dynamic,
            "example_thresholds": {
                "start": self.get_threshold(0, 0),
                "after_2h": self.get_threshold(2.5, 20) if self.dynamic else self.base_uphill_threshold,
                "after_4h": self.get_threshold(4.0, 40) if self.dynamic else self.base_uphill_threshold,
                "ultra_6h": self.get_threshold(6.0, 60) if self.dynamic else self.base_uphill_threshold,
            }
        }
```

---

## 3. Фаза 3: Run персонализация из Strava

### 3.1 Новая модель данных

Разделяем `UserPerformanceProfile` на две таблицы:

```
users (1) ─────┬───── (0..1) user_hike_profiles
              └───── (0..1) user_run_profiles
```

### 3.2 Миграция 007: Разделение таблиц

```python
# backend/alembic/versions/007_split_user_profiles.py
"""
Split user_performance_profiles into user_hike_profiles and user_run_profiles.

Migration preserves existing hike data in new table.
"""

def upgrade():
    # 1. Rename existing table
    op.rename_table('user_performance_profiles', 'user_hike_profiles')

    # 2. Create new run profiles table
    op.create_table(
        'user_run_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True),

        # 7-category pace for running
        sa.Column('avg_flat_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_gentle_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_moderate_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_steep_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_gentle_downhill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_moderate_downhill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_steep_downhill_pace_min_km', sa.Float(), nullable=True),

        # Personal walk threshold (auto-detected or manual)
        sa.Column('walk_threshold_percent', sa.Float(), nullable=True, default=25.0),

        # Statistics
        sa.Column('total_activities', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Float(), default=0.0),
        sa.Column('total_elevation_m', sa.Float(), default=0.0),

        # Metadata
        sa.Column('last_calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
    )


def downgrade():
    op.drop_table('user_run_profiles')
    op.rename_table('user_hike_profiles', 'user_performance_profiles')
```

### 3.3 models/user_run_profile.py

```python
"""
User Run Performance Profile Model

Stores calculated performance metrics from Strava Run activities.
Used for personalizing trail running time predictions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserRunProfile(Base):
    """
    User's running performance profile from Strava Run/TrailRun activities.

    Similar to UserHikeProfile but:
    - Different activity types (Run, TrailRun, VirtualRun)
    - Includes walk threshold detection
    - Uses GAP-based fallbacks instead of Tobler
    """

    __tablename__ = "user_run_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # === Pace metrics (7-category system) ===
    avg_flat_pace_min_km = Column(Float, nullable=True)
    avg_gentle_uphill_pace_min_km = Column(Float, nullable=True)
    avg_moderate_uphill_pace_min_km = Column(Float, nullable=True)
    avg_steep_uphill_pace_min_km = Column(Float, nullable=True)
    avg_gentle_downhill_pace_min_km = Column(Float, nullable=True)
    avg_moderate_downhill_pace_min_km = Column(Float, nullable=True)
    avg_steep_downhill_pace_min_km = Column(Float, nullable=True)

    # === Walk threshold ===
    # Auto-detected from splits or set manually
    walk_threshold_percent = Column(Float, nullable=True, default=25.0)

    # === Statistics ===
    total_activities = Column(Integer, default=0)
    total_distance_km = Column(Float, default=0.0)
    total_elevation_m = Column(Float, default=0.0)

    # === Metadata ===
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="run_profile")

    def __repr__(self):
        return f"<UserRunProfile user={self.user_id} flat_pace={self.avg_flat_pace_min_km}>"

    @property
    def has_profile_data(self) -> bool:
        """Check if profile has any pace data."""
        return self.avg_flat_pace_min_km is not None

    @property
    def has_extended_gradient_data(self) -> bool:
        """Check if profile has 7-category gradient data."""
        has_uphill = (
            self.avg_gentle_uphill_pace_min_km is not None
            or self.avg_moderate_uphill_pace_min_km is not None
            or self.avg_steep_uphill_pace_min_km is not None
        )
        has_downhill = (
            self.avg_gentle_downhill_pace_min_km is not None
            or self.avg_moderate_downhill_pace_min_km is not None
            or self.avg_steep_downhill_pace_min_km is not None
        )
        return has_uphill and has_downhill

    @property
    def flat_speed_kmh(self) -> Optional[float]:
        """Convert flat pace to speed."""
        if self.avg_flat_pace_min_km and self.avg_flat_pace_min_km > 0:
            return round(60 / self.avg_flat_pace_min_km, 2)
        return None

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "avg_flat_pace_min_km": self.avg_flat_pace_min_km,
            "avg_gentle_uphill_pace_min_km": self.avg_gentle_uphill_pace_min_km,
            "avg_moderate_uphill_pace_min_km": self.avg_moderate_uphill_pace_min_km,
            "avg_steep_uphill_pace_min_km": self.avg_steep_uphill_pace_min_km,
            "avg_gentle_downhill_pace_min_km": self.avg_gentle_downhill_pace_min_km,
            "avg_moderate_downhill_pace_min_km": self.avg_moderate_downhill_pace_min_km,
            "avg_steep_downhill_pace_min_km": self.avg_steep_downhill_pace_min_km,
            "walk_threshold_percent": self.walk_threshold_percent,
            "flat_speed_kmh": self.flat_speed_kmh,
            "total_activities": self.total_activities,
            "total_distance_km": round(self.total_distance_km, 1),
            "total_elevation_m": round(self.total_elevation_m, 0),
            "has_profile_data": self.has_profile_data,
            "has_extended_gradient_data": self.has_extended_gradient_data,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
        }
```

### 3.4 personalization_run.py

```python
"""
Run Personalization Service

Applies user Run performance profile to trail running predictions.
Uses GAP calculator as fallback when profile data is missing.
"""

from typing import Optional

from app.models.user_run_profile import UserRunProfile
from app.services.calculators.personalization_base import (
    BasePersonalizationService,
    MIN_ACTIVITIES_FOR_PROFILE,
)
from app.services.calculators.trail_run.gap_calculator import GAPCalculator, GAPMode


# Default flat pace for runners (min/km)
DEFAULT_FLAT_PACE_MIN_KM = 6.0  # 10 km/h


class RunPersonalizationService(BasePersonalizationService):
    """
    Personalization service for Run/TrailRun activities.

    Uses GAP calculator (Strava mode) as fallback.
    Profile data from Strava Run/TrailRun activities.
    """

    def __init__(
        self,
        profile: UserRunProfile,
        use_extended_gradients: bool = True  # Default True for running
    ):
        super().__init__(use_extended_gradients)
        self.profile = profile

        # GAP calculator for fallback
        flat_pace = profile.avg_flat_pace_min_km or DEFAULT_FLAT_PACE_MIN_KM
        self._gap_calculator = GAPCalculator(flat_pace, GAPMode.STRAVA)

    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """
        Legacy mode not recommended for running.
        Falls back to extended mode.
        """
        return self._get_pace_extended(gradient_percent)

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
        """Default 10 km/h for runners."""
        return 60 / DEFAULT_FLAT_PACE_MIN_KM

    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """Use GAP calculator (Strava mode) for estimation."""
        result = self._gap_calculator.calculate(gradient_percent)
        return result.adjusted_pace_min_km

    @staticmethod
    def is_profile_valid(profile: Optional[UserRunProfile]) -> bool:
        """Check if run profile has enough data."""
        if not profile:
            return False
        if not profile.avg_flat_pace_min_km:
            return False
        if profile.total_activities < MIN_ACTIVITIES_FOR_PROFILE:
            return False
        return True

    @staticmethod
    def get_profile_summary(
        profile: Optional[UserRunProfile],
        include_extended: bool = True
    ) -> dict:
        """Get summary for API response."""
        if not profile:
            return {}

        summary = {
            "activities_analyzed": profile.total_activities,
            "flat_pace_min_km": profile.avg_flat_pace_min_km,
            "walk_threshold_percent": profile.walk_threshold_percent,
            "has_profile_data": profile.has_profile_data,
            "has_extended_gradient_data": profile.has_extended_gradient_data,
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
```

### 3.5 Обновление strava_sync.py

```python
# Добавить константу
ACTIVITY_TYPES_FOR_RUN_PROFILE = ["Run", "TrailRun", "VirtualRun"]

# Добавить метод
async def sync_run_activities(self, user_id: int) -> SyncResult:
    """Sync Run activities from Strava for run profile calculation."""
    # Аналогично sync_user_activities, но фильтр по RUN типам
    pass
```

### 3.6 Обновление user_profile.py (сервис)

```python
# Добавить метод
async def calculate_run_profile_with_splits(
    self,
    user_id: int
) -> UserRunProfile:
    """
    Calculate run profile from Run activity splits.

    Similar to calculate_profile_with_splits() but:
    - Uses Run/TrailRun/VirtualRun activities
    - Detects walk_threshold_percent automatically
    """
    pass
```

---

## 4. Фаза 4: Модель усталости для бегунов

### 4.1 Ключевые отличия от хайкинга

| Параметр | Hiking | Trail Running |
|----------|--------|---------------|
| Порог усталости | 3.0 часа | 2.0 часа |
| Linear rate | 0.03 (3%/час) | 0.05 (5%/час) |
| Quadratic rate | 0.005 | 0.008 |
| Спуски | Без изменений | x1.5 дополнительно |

### 4.2 trail_run/runner_fatigue.py

```python
"""
Runner Fatigue Service

Fatigue model adapted for trail runners.

Key differences from hiking:
1. Earlier threshold (2h vs 3h)
2. More aggressive degradation
3. Downhills degrade MORE than uphills late in race

References:
- UTMB Pacing Study (PMC7578994)
- Riegel's endurance formula
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# Runner fatigue constants
FATIGUE_THRESHOLD_HOURS = 2.0       # vs 3.0 for hiking
LINEAR_DEGRADATION = 0.05           # vs 0.03 for hiking
QUADRATIC_DEGRADATION = 0.008       # vs 0.005 for hiking
DOWNHILL_FATIGUE_MULTIPLIER = 1.5   # Downhills hurt more when tired

# Ultra adaptations
ULTRA_THRESHOLD_50K = 3.0   # Delayed fatigue for trained ultra runners
ULTRA_THRESHOLD_100K = 4.0


@dataclass
class RunnerFatigueConfig:
    """Configuration for runner fatigue model."""
    enabled: bool = False
    threshold_hours: float = FATIGUE_THRESHOLD_HOURS
    linear_rate: float = LINEAR_DEGRADATION
    quadratic_rate: float = QUADRATIC_DEGRADATION
    downhill_multiplier: float = DOWNHILL_FATIGUE_MULTIPLIER


class RunnerFatigueService:
    """
    Fatigue service for trail runners.

    Example multipliers (enabled, default config):
        2h  → 1.00
        3h  → 1.058 (+5.8%)
        4h  → 1.13 (+13%)
        5h  → 1.22 (+22%)
        6h  → 1.33 (+33%)
        8h  → 1.59 (+59%)
        10h → 1.92 (+92%)

    Downhill at 6h → 1.33 * 1.5 = 2.0 (+100%)
    """

    def __init__(self, config: RunnerFatigueConfig = None):
        self.config = config or RunnerFatigueConfig()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @classmethod
    def create_enabled(
        cls,
        distance_km: Optional[float] = None,
        threshold_hours: Optional[float] = None
    ) -> "RunnerFatigueService":
        """
        Factory for enabled service with auto-adapted threshold.

        Args:
            distance_km: Total route distance (for ultra adaptation)
            threshold_hours: Manual override for threshold
        """
        if threshold_hours is not None:
            threshold = threshold_hours
        elif distance_km and distance_km >= 100:
            threshold = ULTRA_THRESHOLD_100K
        elif distance_km and distance_km >= 50:
            threshold = ULTRA_THRESHOLD_50K
        else:
            threshold = FATIGUE_THRESHOLD_HOURS

        config = RunnerFatigueConfig(
            enabled=True,
            threshold_hours=threshold
        )
        return cls(config)

    @classmethod
    def create_disabled(cls) -> "RunnerFatigueService":
        """Factory for disabled service."""
        return cls(RunnerFatigueConfig(enabled=False))

    def calculate_multiplier(
        self,
        elapsed_hours: float,
        is_downhill: bool = False
    ) -> float:
        """
        Calculate fatigue multiplier.

        Args:
            elapsed_hours: Time since start
            is_downhill: If True, apply extra downhill penalty

        Returns:
            Multiplier (1.0 = no effect)
        """
        if not self.config.enabled:
            return 1.0

        if elapsed_hours <= self.config.threshold_hours:
            return 1.0

        extra = elapsed_hours - self.config.threshold_hours

        base_mult = (
            1.0
            + self.config.linear_rate * extra
            + self.config.quadratic_rate * extra ** 2
        )

        if is_downhill:
            # Downhills hurt more when tired (muscle damage, braking)
            return base_mult * self.config.downhill_multiplier

        return base_mult

    def apply_to_segment(
        self,
        base_time_hours: float,
        elapsed_hours: float,
        gradient_percent: float = 0
    ) -> Tuple[float, float]:
        """
        Apply fatigue to segment time.

        Args:
            base_time_hours: Time without fatigue
            elapsed_hours: Time before this segment
            gradient_percent: Segment gradient (for downhill detection)

        Returns:
            (adjusted_time, multiplier)
        """
        if not self.config.enabled:
            return base_time_hours, 1.0

        # Downhill defined as < -5%
        is_downhill = gradient_percent < -5.0

        # Use midpoint for more accurate fatigue
        midpoint = elapsed_hours + base_time_hours / 2
        multiplier = self.calculate_multiplier(midpoint, is_downhill)

        return base_time_hours * multiplier, multiplier

    def get_info(self) -> Dict:
        """Get model info for API response."""
        if not self.config.enabled:
            return {"enabled": False, "model": "runner"}

        examples = {}
        for hours in [2, 3, 4, 5, 6, 8, 10]:
            examples[f"{hours}h"] = round(self.calculate_multiplier(hours, False), 3)
            examples[f"{hours}h_downhill"] = round(self.calculate_multiplier(hours, True), 3)

        return {
            "enabled": True,
            "model": "runner",
            "threshold_hours": self.config.threshold_hours,
            "linear_rate": self.config.linear_rate,
            "quadratic_rate": self.config.quadratic_rate,
            "downhill_multiplier": self.config.downhill_multiplier,
            "example_multipliers": examples
        }
```

---

## 5. Чеклист Part 2

**Статус:** DONE
**Дата завершения:** 2026-01-23
**Тесты:** 129 passed (Part 1 + Part 2)

### Фаза 2: Hike/Run Threshold

- [x] Создать `trail_run/hike_run_threshold.py`
- [x] Реализовать `HikeRunThresholdService`
- [x] Добавить `from_strava_profile()` для автоопределения
- [x] Unit-тесты для статического и динамического режимов (21 tests)

### Фаза 3: Run Персонализация

- [x] Создать миграцию `007_add_user_run_profiles.py`
- [x] Создать модель `UserRunProfile`
- [x] Оставить `UserPerformanceProfile` для хайкинга (backward compatible)
- [x] Создать `personalization_run.py`
- [x] Расширить `strava_sync.py` для Run активностей
- [x] Добавить `calculate_run_profile_with_splits()` в UserProfileService
- [x] Unit-тесты (19 tests)

### Фаза 4: Runner Fatigue

- [x] Создать `trail_run/runner_fatigue.py`
- [x] Реализовать `RunnerFatigueService`
- [x] Добавить адаптацию для ultra-дистанций (50k, 100k thresholds)
- [x] Реализовать downhill multiplier (1.5x penalty)
- [x] Unit-тесты (24 tests)

### Обновление моделей

- [x] Обновить `User` модель — добавить `run_profile` relationship
- [x] Обновить импорты в существующем коде
- [x] Проверить обратную совместимость hiking функционала

---

## Переход к Part 3

Part 2 успешно завершён! Готовы компоненты:

1. ✅ **HikeRunThresholdService** — автоматическое определение бег/ходьба
2. ✅ **UserRunProfile** — отдельные профили для Run
3. ✅ **RunPersonalizationService** — персонализация для Run из Strava
4. ✅ **RunnerFatigueService** — модель усталости для бегунов

**Part 3 содержит:** API endpoint, TrailRunService оркестратор, интеграционные тесты
