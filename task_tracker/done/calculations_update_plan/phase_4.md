# Фаза 4: Усталость

**Статус:** Ожидает Фазу 3
**Зависимости:** Фаза 3

---

## Цель

Показывать усталость **отдельно** от базовых расчётов.
Усталость — это множитель, который можно применить к **любому** методу.

---

## Логика усталости

### Формула (Runner Fatigue)

```python
FATIGUE_THRESHOLD_HOURS = 2.0  # Когда начинается усталость
LINEAR_RATE = 0.05             # 5% за час после порога
QUADRATIC_RATE = 0.008         # Ускорение деградации

def fatigue_multiplier(elapsed_hours: float, is_downhill: bool = False) -> float:
    if elapsed_hours <= FATIGUE_THRESHOLD_HOURS:
        return 1.0

    extra = elapsed_hours - FATIGUE_THRESHOLD_HOURS
    base_mult = 1.0 + (LINEAR_RATE * extra) + (QUADRATIC_RATE * extra ** 2)

    if is_downhill:
        base_mult *= 1.5  # Спуски болезненнее при усталости

    return base_mult
```

### Примеры

| Время | Множитель | Добавка |
|-------|-----------|---------|
| 2ч | 1.00 | +0% |
| 3ч | 1.06 | +6% |
| 4ч | 1.13 | +13% |
| 5ч | 1.22 | +22% |
| 6ч | 1.33 | +33% |

---

## Как считать усталость для каждого метода

Усталость зависит от **времени на маршруте**, которое зависит от метода.

```python
# Для метода "all_run_strava" (3ч 45м = 3.75ч)
elapsed = 0
total_fatigue_addition = 0

for segment in segments:
    segment_time = segment.times["strava_gap"]
    elapsed += segment_time / 2  # Середина сегмента

    if elapsed > FATIGUE_THRESHOLD_HOURS:
        mult = fatigue_multiplier(elapsed)
        fatigue_addition = segment_time * (mult - 1)
        total_fatigue_addition += fatigue_addition

    elapsed += segment_time / 2  # Конец сегмента

# Итого с усталостью
all_run_strava_with_fatigue = all_run_strava + total_fatigue_addition
```

---

## Что добавляется в totals

```python
totals = {
    # Блок 1: Всё бегом (из Фазы 1)
    "all_run_strava": 3.75,
    "all_run_minetti": 3.87,
    "all_run_strava_minetti": 3.80,

    # Блок 1 с усталостью (НОВОЕ)
    "all_run_strava_fatigue": 0.32,           # Добавка в часах
    "all_run_minetti_fatigue": 0.35,
    "all_run_strava_minetti_fatigue": 0.33,

    # Блок 1 персонализированный (из Фазы 3)
    "all_run_personalized": 3.63,
    "all_run_personalized_fatigue": 0.28,     # НОВОЕ

    # Блок 2: Бег + Шаг (из Фазы 2)
    "run_hike_strava_tobler": 3.97,
    # ...

    # Блок 2 с усталостью (НОВОЕ)
    "run_hike_strava_tobler_fatigue": 0.38,
    "run_hike_strava_naismith_fatigue": 0.40,
    # ... для всех комбинаций

    # Общая информация об усталости
    "fatigue_enabled": True,
    "fatigue_threshold_hours": 2.0,
}
```

---

## План изменений

### 4.1 Создать FatigueCalculator

**Файл:** `backend/app/features/trail_run/calculators/fatigue.py`

```python
from dataclasses import dataclass
from typing import List, Dict

FATIGUE_THRESHOLD_HOURS = 2.0
LINEAR_RATE = 0.05
QUADRATIC_RATE = 0.008
DOWNHILL_PENALTY = 1.5


@dataclass
class FatigueResult:
    """Результат расчёта усталости для метода."""
    method_name: str
    base_time_hours: float
    fatigue_addition_hours: float
    fatigue_percent: float

    @property
    def total_with_fatigue(self) -> float:
        return self.base_time_hours + self.fatigue_addition_hours


class FatigueCalculator:
    """Рассчитывает добавку усталости для метода."""

    def __init__(self, threshold_hours: float = FATIGUE_THRESHOLD_HOURS):
        self._threshold = threshold_hours

    def calculate_for_method(
        self,
        method_name: str,
        segment_times: List[float],
        segment_gradients: List[float],
    ) -> FatigueResult:
        """
        Рассчитать усталость для метода.

        Args:
            method_name: Название метода (для отчёта)
            segment_times: Время каждого сегмента (часы)
            segment_gradients: Градиент каждого сегмента (%)
        """
        elapsed = 0.0
        total_fatigue = 0.0
        base_time = sum(segment_times)

        for seg_time, gradient in zip(segment_times, segment_gradients):
            # Время в середине сегмента
            mid_elapsed = elapsed + seg_time / 2

            if mid_elapsed > self._threshold:
                is_downhill = gradient < -5  # Крутой спуск
                mult = self._multiplier(mid_elapsed, is_downhill)
                fatigue_addition = seg_time * (mult - 1)
                total_fatigue += fatigue_addition

            elapsed += seg_time

        fatigue_percent = (total_fatigue / base_time * 100) if base_time > 0 else 0

        return FatigueResult(
            method_name=method_name,
            base_time_hours=base_time,
            fatigue_addition_hours=total_fatigue,
            fatigue_percent=fatigue_percent,
        )

    def _multiplier(self, elapsed_hours: float, is_downhill: bool = False) -> float:
        if elapsed_hours <= self._threshold:
            return 1.0

        extra = elapsed_hours - self._threshold
        base_mult = 1.0 + (LINEAR_RATE * extra) + (QUADRATIC_RATE * extra ** 2)

        if is_downhill:
            base_mult = 1.0 + (base_mult - 1.0) * DOWNHILL_PENALTY

        return base_mult
```

### 4.2 Интегрировать в TrailRunService

**Файл:** `backend/app/features/trail_run/service.py`

```python
def calculate_route(self, points: List[tuple]) -> TrailRunResult:
    # ... существующий код из Фаз 1-3 ...

    # Усталость (НОВОЕ)
    if self._apply_fatigue:
        fatigue_calc = FatigueCalculator()

        # Собираем времена и градиенты для каждого метода
        gradients = [seg.gradient_percent for seg in segments]

        # Блок 1: Всё бегом
        methods_to_calculate = [
            ("all_run_strava", [r.times["strava_gap"] for r in segment_results]),
            ("all_run_minetti", [r.times["minetti_gap"] for r in segment_results]),
            ("all_run_strava_minetti", [r.times["strava_minetti_gap"] for r in segment_results]),
        ]

        if totals.get("personalized"):
            methods_to_calculate.append(
                ("all_run_personalized", [r.times["run_personalized"] for r in segment_results])
            )

        # Блок 2: Бег + Шаг (нужно учитывать movement)
        run_hike_methods = self._collect_run_hike_times(segment_results, decisions)
        methods_to_calculate.extend(run_hike_methods)

        # Рассчитываем усталость для каждого метода
        for method_name, times in methods_to_calculate:
            fatigue_result = fatigue_calc.calculate_for_method(
                method_name=method_name,
                segment_times=times,
                segment_gradients=gradients,
            )
            totals[f"{method_name}_fatigue"] = fatigue_result.fatigue_addition_hours

        totals["fatigue_enabled"] = True
        totals["fatigue_threshold_hours"] = FATIGUE_THRESHOLD_HOURS
    else:
        totals["fatigue_enabled"] = False
```

### 4.3 Обновить форматирование в боте

**Файл:** `bot/handlers/trail_run.py`

```python
def format_hours_with_fatigue(base_hours: float, fatigue_hours: float) -> str:
    """Форматирует время с добавкой усталости в скобках."""
    base_str = format_hours(base_hours)
    if fatigue_hours > 0:
        fatigue_min = int(fatigue_hours * 60)
        return f"{base_str} (+{fatigue_min}м)"
    return base_str


def format_trail_run_result(result: dict, gpx_name: str) -> str:
    totals = result.get("totals", {})
    fatigue_enabled = totals.get("fatigue_enabled", False)

    # ... header ...

    lines.extend([
        "",
        "📊 ВСЁ БЕГОМ:",
        "",
        "  Базовые формулы:",
    ])

    if fatigue_enabled:
        lines.extend([
            f"    Strava GAP:       {format_hours_with_fatigue(totals.get('all_run_strava', 0), totals.get('all_run_strava_fatigue', 0))}",
            f"    Minetti GAP:      {format_hours_with_fatigue(totals.get('all_run_minetti', 0), totals.get('all_run_minetti_fatigue', 0))}",
            f"    Strava+Minetti:   {format_hours_with_fatigue(totals.get('all_run_strava_minetti', 0), totals.get('all_run_strava_minetti_fatigue', 0))}",
        ])
    else:
        lines.extend([
            f"    Strava GAP:       {format_hours(totals.get('all_run_strava', 0))}",
            f"    Minetti GAP:      {format_hours(totals.get('all_run_minetti', 0))}",
            f"    Strava+Minetti:   {format_hours(totals.get('all_run_strava_minetti', 0))}",
        ])

    # Аналогично для персонализированных и Бег + Шаг...

    # Легенда усталости
    if fatigue_enabled:
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"😓 УСТАЛОСТЬ (после {totals.get('fatigue_threshold_hours', 2):.0f}ч):",
            "  Добавка показана в скобках (+Xм)",
        ])

    return "\n".join(lines)
```

---

## Пример вывода

```
📊 ВСЁ БЕГОМ:

  Базовые формулы:
    Strava GAP:       3ч 45м (+19м)
    Minetti GAP:      3ч 52м (+21м)
    Strava+Minetti:   3ч 48м (+20м)

  🎯 Персональный (15 активностей):
    3ч 38м (+17м)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🚶 1.5км (8%)

  Базовые:
    Strava + Tobler:    3ч 58м (+23м)
    Strava + Naismith:  4ч 02м (+24м)
    ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

😓 УСТАЛОСТЬ (после 2ч):
  Добавка показана в скобках (+Xм)
```

---

## Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `backend/app/features/trail_run/calculators/fatigue.py` | ~60 строк (FatigueCalculator) |
| `backend/app/features/trail_run/service.py` | ~40 строк (интеграция) |
| `bot/handlers/trail_run.py` | ~30 строк (форматирование с усталостью) |

**Итого:** ~130 строк изменений

---

## Чеклист проверки

- [ ] `*_fatigue` поля появляются когда `apply_fatigue=True`
- [ ] Усталость = 0 для маршрутов < 2ч
- [ ] Усталость растёт нелинейно (больше для длинных маршрутов)
- [ ] Спуски имеют больший штраф усталости
- [ ] Усталость показывается в скобках рядом с каждым методом
- [ ] Можно включить/выключить усталость (параметр запроса)

---

## Тест-кейс

Маршрут: 20 км, +2000м, ~4ч базового времени

```
  Strava GAP:       3ч 45м (+19м)  ← 3.75 + 0.32 = 4.07ч
  Minetti GAP:      3ч 52м (+21м)  ← 3.87 + 0.35 = 4.22ч
```

Для коротких маршрутов (<2ч):
```
  Strava GAP:       1ч 30м         ← нет добавки, время < threshold
```
