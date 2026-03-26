# Фаза 3: Расчёт метрик

**Статус:** Ожидает Фазу 2
**Зависимости:** Фаза 2 ✓
**Строк кода:** ~70

---

## Цель

Реализовать расчёт статистических метрик точности предсказаний.

---

## Метрики

| Метрика | Формула | Что показывает |
|---------|---------|----------------|
| **MAE** | mean(\|predicted - actual\|) | Средняя ошибка в минутах |
| **MAPE** | mean(\|predicted - actual\| / actual) × 100 | Средняя ошибка в % |
| **Bias** | mean(predicted - actual) / mean(actual) × 100 | Систематическое отклонение |
| **RMSE** | sqrt(mean((predicted - actual)²)) | Чувствительна к большим ошибкам |

---

## Что создаём

```
backend/tools/calibration/
├── ...
└── metrics.py    # NEW
```

---

## Код

### `backend/tools/calibration/metrics.py`

```python
"""
Metrics calculation for backtesting.

Provides statistical measures of prediction accuracy.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from statistics import mean, median, stdev
from math import sqrt

from .calculators import RoutePredictions, SegmentPredictions


@dataclass
class MethodMetrics:
    """Accuracy metrics for one prediction method."""

    method_name: str

    # Core metrics
    mae_seconds: float      # Mean Absolute Error
    mae_minutes: float      # MAE in minutes (for readability)
    mape_percent: float     # Mean Absolute Percentage Error
    bias_percent: float     # Systematic over/under prediction
    rmse_seconds: float     # Root Mean Square Error

    # Distribution
    median_error_percent: float
    std_error_percent: float

    # Sample size
    n_samples: int


@dataclass
class GradientCategoryMetrics:
    """Metrics grouped by gradient category."""

    category: str
    gradient_range: Tuple[float, float]  # (min, max) percent

    n_segments: int
    total_distance_m: float

    # MAPE by method
    method_mape: Dict[str, float]


# Gradient categories (same as in UserRunProfile)
GRADIENT_CATEGORIES = {
    "steep_downhill": (-100, -15),
    "moderate_downhill": (-15, -8),
    "gentle_downhill": (-8, -2),
    "flat": (-2, 2),
    "gentle_uphill": (2, 8),
    "moderate_uphill": (8, 15),
    "steep_uphill": (15, 100),
}


class MetricsCalculator:
    """Calculate accuracy metrics from predictions."""

    def calculate_method_metrics(
        self,
        predictions: List[RoutePredictions],
        method: str
    ) -> MethodMetrics:
        """
        Calculate metrics for one method across all activities.

        Args:
            predictions: List of route predictions
            method: Method name (e.g., "strava_gap", "personalized")

        Returns:
            MethodMetrics for this method
        """
        errors_abs = []      # |predicted - actual|
        errors_percent = []  # |predicted - actual| / actual * 100
        errors_signed = []   # (predicted - actual) for bias

        for pred in predictions:
            actual = pred.actual_time_s
            predicted = getattr(pred, method, None)

            if predicted is None or actual <= 0:
                continue

            error_abs = abs(predicted - actual)
            error_pct = (error_abs / actual) * 100
            error_signed = predicted - actual

            errors_abs.append(error_abs)
            errors_percent.append(error_pct)
            errors_signed.append(error_signed)

        if not errors_abs:
            return MethodMetrics(
                method_name=method,
                mae_seconds=0, mae_minutes=0, mape_percent=0,
                bias_percent=0, rmse_seconds=0,
                median_error_percent=0, std_error_percent=0,
                n_samples=0,
            )

        # Calculate metrics
        mae_s = mean(errors_abs)
        mape = mean(errors_percent)
        rmse = sqrt(mean([e ** 2 for e in errors_abs]))

        # Bias: average signed error as percent of average actual
        total_actual = sum(p.actual_time_s for p in predictions if p.actual_time_s > 0)
        bias_pct = (sum(errors_signed) / total_actual) * 100 if total_actual > 0 else 0

        # Distribution
        median_err = median(errors_percent)
        std_err = stdev(errors_percent) if len(errors_percent) > 1 else 0

        return MethodMetrics(
            method_name=method,
            mae_seconds=round(mae_s, 1),
            mae_minutes=round(mae_s / 60, 1),
            mape_percent=round(mape, 1),
            bias_percent=round(bias_pct, 1),
            rmse_seconds=round(rmse, 1),
            median_error_percent=round(median_err, 1),
            std_error_percent=round(std_err, 1),
            n_samples=len(errors_abs),
        )

    def calculate_all_methods(
        self,
        predictions: List[RoutePredictions]
    ) -> Dict[str, MethodMetrics]:
        """Calculate metrics for all methods."""

        methods = [
            "strava_gap",
            "minetti_gap",
            "strava_minetti_gap",
            "personalized",
            "tobler",
            "naismith",
        ]

        return {
            method: self.calculate_method_metrics(predictions, method)
            for method in methods
        }

    def calculate_gradient_breakdown(
        self,
        predictions: List[RoutePredictions]
    ) -> Dict[str, GradientCategoryMetrics]:
        """
        Calculate per-gradient-category metrics.

        Groups all segments by gradient and calculates MAPE
        for each method in each category.
        """
        # Collect segments by category
        category_segments: Dict[str, List[SegmentPredictions]] = {
            cat: [] for cat in GRADIENT_CATEGORIES
        }

        for pred in predictions:
            for seg in pred.segments:
                cat = self._get_gradient_category(seg.gradient_percent)
                category_segments[cat].append(seg)

        # Calculate metrics per category
        result = {}
        for cat, (grad_min, grad_max) in GRADIENT_CATEGORIES.items():
            segments = category_segments[cat]

            if not segments:
                continue

            # Calculate MAPE for each method
            method_mape = {}
            for method in ["strava_gap", "minetti_gap", "strava_minetti_gap",
                          "personalized", "tobler", "naismith"]:
                errors = []
                for seg in segments:
                    actual = seg.actual_time_s
                    predicted = getattr(seg, method, None)

                    if predicted is not None and actual > 0:
                        error_pct = abs(predicted - actual) / actual * 100
                        errors.append(error_pct)

                if errors:
                    method_mape[method] = round(mean(errors), 1)

            result[cat] = GradientCategoryMetrics(
                category=cat,
                gradient_range=(grad_min, grad_max),
                n_segments=len(segments),
                total_distance_m=sum(s.distance_m for s in segments),
                method_mape=method_mape,
            )

        return result

    def _get_gradient_category(self, gradient: float) -> str:
        """Determine gradient category for a value."""
        for cat, (min_g, max_g) in GRADIENT_CATEGORIES.items():
            if min_g <= gradient < max_g:
                return cat
        # Edge cases
        if gradient >= 15:
            return "steep_uphill"
        if gradient <= -15:
            return "steep_downhill"
        return "flat"
```

---

## Проверка

```python
# test_metrics.py

from tools.calibration import RoutePredictions, SegmentPredictions
from tools.calibration.metrics import MetricsCalculator

# Mock data
predictions = [
    RoutePredictions(
        activity_id=1,
        activity_name="Test Run 1",
        actual_time_s=4500,  # 75 min
        strava_gap=4260,     # 71 min (-5.3%)
        minetti_gap=4080,    # 68 min (-9.3%)
        strava_minetti_gap=4200,  # 70 min (-6.7%)
        personalized=4440,   # 74 min (-1.3%)
        tobler=5520,         # 92 min (+22.7%)
        naismith=6480,       # 108 min (+44%)
        segments=[],
    ),
    RoutePredictions(
        activity_id=2,
        activity_name="Test Run 2",
        actual_time_s=3600,  # 60 min
        strava_gap=3420,     # 57 min (-5%)
        minetti_gap=3240,    # 54 min (-10%)
        strava_minetti_gap=3360,  # 56 min (-6.7%)
        personalized=3540,   # 59 min (-1.7%)
        tobler=4320,         # 72 min (+20%)
        naismith=5040,       # 84 min (+40%)
        segments=[],
    ),
]

calc = MetricsCalculator()
metrics = calc.calculate_all_methods(predictions)

print("Method Metrics:")
print("-" * 60)
for method, m in metrics.items():
    if m.n_samples > 0:
        print(f"{method:20} | MAE: {m.mae_minutes:5.1f}min | "
              f"MAPE: {m.mape_percent:5.1f}% | Bias: {m.bias_percent:+5.1f}%")
```

**Ожидаемый вывод:**

```
Method Metrics:
------------------------------------------------------------
strava_gap           | MAE:   4.5min | MAPE:   5.2% | Bias:  -5.2%
minetti_gap          | MAE:   7.5min | MAPE:   9.7% | Bias:  -9.7%
strava_minetti_gap   | MAE:   5.3min | MAPE:   6.7% | Bias:  -6.7%
personalized         | MAE:   1.2min | MAPE:   1.5% | Bias:  -1.5%
tobler               | MAE:  17.0min | MAPE:  21.3% | Bias: +21.3%
naismith             | MAE:  34.0min | MAPE:  42.0% | Bias: +42.0%
```

---

## Чеклист

- [ ] `metrics.py` создан
- [ ] `__init__.py` обновлён
- [ ] `calculate_method_metrics` работает
- [ ] `calculate_gradient_breakdown` работает
- [ ] Тест на mock данных проходит
