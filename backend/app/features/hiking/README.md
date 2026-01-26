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

| File | Description |
|------|-------------|
| models.py | UserHikingProfile (re-export from app.models) |
| schemas.py | Pydantic schemas |
| service.py | Main service (stub) |
| calculators/tobler.py | Tobler calculator |
| calculators/naismith.py | Naismith calculator |
| calculators/personalization.py | Personalization service |
| calculators/fatigue.py | Fatigue modeling |

## Backward Compatibility

Old imports still work:
```python
from app.models.user_profile import UserPerformanceProfile  # OK
from app.services.calculators import ToblerCalculator  # OK
```
