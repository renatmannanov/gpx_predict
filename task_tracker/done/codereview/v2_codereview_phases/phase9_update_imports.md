# Phase 9: Update Imports (Remove Re-exports)

> **Сложность:** 🟢 Низкая
> **Строк:** ~60
> **Файлов:** 27
> **Зависимости:** Phase 8

---

## Оптимизация

**Рекомендация:** Для файлов в `api/v1/routes/` обновлять импорты вместе с Phase 10 (async migration), чтобы не редактировать одни и те же файлы дважды.

Файлы routes для объединённого обновления:
- `predict.py` - импорты + async
- `gpx.py` - импорты + async
- `profile.py` - импорты + async (или удалить - deprecated)
- `strava.py` - импорты + async
- `profiles.py` - только импорты (уже async)

---

## Проблема

После рефакторинга v2 код использует re-exports для backward compatibility:

```python
# Старый путь (через re-export)
from app.services.calculators import ToblerCalculator

# Новый путь (правильный)
from app.features.hiking.calculators import ToblerCalculator
```

**Почему это плохо:**
- Два пути к одному классу = путаница
- IDE показывает неправильные пути
- Stack trace запутанный
- Сложнее понять архитектуру

---

## Решение

Обновить все импорты на новые пути, затем добавить deprecation warnings в re-exports.

---

## Чеклист

### 1. Обновить импорты в app/

- [ ] `app/services/prediction.py` (3 импорта)
- [ ] `app/services/calculators/comparison.py` (1 импорт)
- [ ] `app/api/v1/routes/predict.py` (5 импортов)
- [ ] `app/api/v1/routes/gpx.py` (1 импорт)
- [ ] `app/api/v1/routes/profile.py` (2 импорта)
- [ ] `app/api/v1/routes/strava.py` (2 импорта)
- [ ] `app/api/v1/routes/profiles.py` (2 импорта)
- [ ] `app/features/trail_run/service.py` (2 импорта)
- [ ] `app/features/trail_run/calculators/gap.py` (1 импорт)
- [ ] `app/features/trail_run/calculators/threshold.py` (1 импорт)
- [ ] `app/features/hiking/calculators/tobler.py` (1 импорт)
- [ ] `app/features/hiking/calculators/naismith.py` (1 импорт)
- [ ] `app/features/hiking/calculators/personalization_base.py` (1 импорт)
- [ ] `app/features/strava/sync/service.py` (1 импорт)
- [ ] `app/main.py` (1 импорт)

### 2. Обновить импорты в tests/

- [ ] `tests/features/trail_run/test_gap_calculator.py` (1 импорт)
- [ ] `tests/features/trail_run/test_hike_run_threshold.py` (1 импорт)
- [ ] `tests/features/trail_run/test_personalization.py` (1 импорт)
- [ ] `tests/features/hiking/test_personalization.py` (1 импорт)

### 3. Обновить импорты в scripts/

- [ ] `scripts/test_trail_run_service.py` (1 импорт)
- [ ] `scripts/analyze_segments.py` (2 импорта)
- [ ] `scripts/calculate_run_profile.py` (2 импорта)
- [ ] `scripts/analyze_run_profile.py` (2 импорта)
- [ ] `scripts/analyze_threshold_comparison.py` (3 импорта)
- [ ] `scripts/test_talgar_trail.py` (4 импорта)
- [ ] `scripts/test_talgar_trail_part2.py` (4 импорта)

### 4. Добавить deprecation warnings

- [ ] В `app/services/calculators/__init__.py` добавить warnings

```python
"""
DEPRECATED: Use app.features.hiking.calculators or app.features.trail_run.calculators

This module re-exports for backward compatibility.
These will be removed in a future version.
"""
import warnings

def __getattr__(name):
    warnings.warn(
        f"Importing {name} from app.services.calculators is deprecated. "
        f"Use app.features.hiking.calculators or app.features.trail_run.calculators instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... return the actual import
```

### 5. Проверка

- [ ] `python -m pytest tests/ -v` - все тесты проходят
- [ ] `python -c "from app.services.calculators import ToblerCalculator"` - показывает warning

---

## Mapping старых → новых путей

| Старый путь | Новый путь |
|-------------|------------|
| `app.services.calculators.ToblerCalculator` | `app.features.hiking.calculators.ToblerCalculator` |
| `app.services.calculators.NaismithCalculator` | `app.features.hiking.calculators.NaismithCalculator` |
| `app.services.calculators.GAPCalculator` | `app.features.trail_run.calculators.GAPCalculator` |
| `app.services.calculators.RouteSegmenter` | `app.features.gpx.segmenter.RouteSegmenter` |
| `app.services.calculators.MacroSegment` | `app.shared.calculator_types.MacroSegment` |
| `app.services.calculators.SegmentType` | `app.shared.calculator_types.SegmentType` |
| `app.services.calculators.PersonalizationService` | `app.features.hiking.calculators.HikePersonalizationService` |
| `app.services.calculators.FatigueService` | `app.features.hiking.calculators.HikeFatigueService` |
| `app.services.calculators.HikeRunThresholdService` | `app.features.trail_run.calculators.HikeRunThresholdService` |
| `app.services.calculators.RunPersonalizationService` | `app.features.trail_run.calculators.RunPersonalizationService` |
| `app.services.calculators.RunnerFatigueService` | `app.features.trail_run.calculators.RunnerFatigueService` |

---

## Пример изменения

**До:**
```python
from app.services.calculators import (
    ToblerCalculator,
    NaismithCalculator,
    MacroSegment,
)
```

**После:**
```python
from app.features.hiking.calculators import ToblerCalculator, NaismithCalculator
from app.shared.calculator_types import MacroSegment
```

---

## Результат

- ✅ Единый путь к каждому классу
- ✅ IDE показывает правильные пути
- ✅ Deprecation warnings предупреждают о старых импортах
- ✅ Архитектура понятнее

---

*Phase 9 of v2.1 cleanup*
