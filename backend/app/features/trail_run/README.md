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
| models.py | ~130 | UserRunProfile |
| schemas.py | ~60 | Pydantic schemas |
| service.py | ~320 | TrailRunService |
| calculators/gap.py | ~400 | GAPCalculator |
| calculators/threshold.py | ~290 | HikeRunThresholdService |
| calculators/fatigue.py | ~180 | RunnerFatigueService |
| calculators/personalization.py | ~130 | RunPersonalizationService |
