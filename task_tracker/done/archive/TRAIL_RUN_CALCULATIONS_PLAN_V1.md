# План исправлений Trail Running расчётов

**Дата:** 2026-01-30
**Статус:** Черновик

---

## Цель

Переработать trail running предиктор для получения результатов в структуре:

- **3 базовых метода** (Strava GAP, Minetti GAP, Strava+Minetti)
- **3 вариации** (персонализация, переход на шаг, усталость)
- **3 варианта расчёта** (базовый, масштабированный, персонализированный)

---

## Часть 1: Добавить чистый Minetti GAP

### Проблема сейчас:
В `gap.py` Minetti GAP — это гибрид (Minetti uphill + Strava downhill).

### Что нужно:
| Метод | Uphill | Downhill |
|-------|--------|----------|
| Strava GAP | Strava | Strava |
| Minetti GAP | Minetti | Minetti |
| Strava+Minetti | Minetti | Strava |

### Изменения:

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

1. Добавить режим `GAPMode.MINETTI_PURE`:
```python
class GAPMode(Enum):
    STRAVA = "strava_gap"
    MINETTI_PURE = "minetti_gap"      # Minetti/Minetti
    STRAVA_MINETTI = "strava_minetti" # Minetti/Strava (текущий "minetti_gap")
```

2. Добавить метод `_calculate_minetti_downhill()`:
```python
def _calculate_minetti_downhill(self, gradient_percent: float) -> GAPResult:
    """Чистый Minetti для спусков (для сравнения)."""
    gradient_decimal = gradient_percent / 100
    energy_ratio = self._minetti_energy_cost(gradient_decimal)
    pace_adj = energy_ratio ** 0.75
    # ...
```

3. Обновить `_calculate_minetti()` для поддержки pure режима:
```python
def _calculate_minetti(self, gradient_percent: float, pure: bool = False) -> GAPResult:
    if gradient_percent >= 0:
        # Uphill: всегда Minetti
        return self._minetti_uphill(gradient_percent)
    else:
        if pure:
            # Pure Minetti для downhill
            return self._minetti_downhill(gradient_percent)
        else:
            # Гибрид: Strava для downhill
            return self._strava_downhill(gradient_percent)
```

---

## Часть 2: Считать ВСЕ методы для ВСЕГО маршрута

### Проблема сейчас:
- `totals["strava_gap"]` = только RUN сегменты
- `totals["tobler"]` = только HIKE сегменты
- Нет "полного" времени по методу для всего маршрута

### Что нужно:
Для каждого метода — время для ВСЕГО маршрута (независимо от RUN/HIKE решения).

### Изменения:

**Файл:** `backend/app/features/trail_run/service.py`

1. Новая структура totals:
```python
totals = {
    # Всё бегом (весь маршрут одним методом)
    "full_run": {
        "strava_gap": 0.0,
        "minetti_gap": 0.0,
        "strava_minetti": 0.0,
    },

    # Гибридные (RUN + HIKE после threshold)
    "hybrid": {
        "strava_tobler": 0.0,
        "strava_naismith": 0.0,
        "minetti_tobler": 0.0,
        "minetti_naismith": 0.0,
        "strava_minetti_tobler": 0.0,
        "strava_minetti_naismith": 0.0,
    },
}
```

2. Для каждого сегмента считать ВСЕ методы:
```python
for segment in segments:
    # Всегда считаем все running методы
    times["strava_gap"] = strava_calc.calculate(segment)
    times["minetti_gap"] = minetti_pure_calc.calculate(segment)
    times["strava_minetti"] = strava_minetti_calc.calculate(segment)

    # Всегда считаем все hiking методы
    times["tobler"] = tobler_calc.calculate(segment)
    times["naismith"] = naismith_calc.calculate(segment)

    # Накапливаем full_run (весь маршрут бегом)
    totals["full_run"]["strava_gap"] += times["strava_gap"]
    totals["full_run"]["minetti_gap"] += times["minetti_gap"]
    totals["full_run"]["strava_minetti"] += times["strava_minetti"]

    # Накапливаем hybrid (с учётом threshold)
    if decision.mode == RUN:
        totals["hybrid"]["strava_tobler"] += times["strava_gap"]
        totals["hybrid"]["strava_naismith"] += times["strava_gap"]
        # ...
    else:  # HIKE
        totals["hybrid"]["strava_tobler"] += times["tobler"]
        totals["hybrid"]["strava_naismith"] += times["naismith"]
        # ...
```

---

## Часть 3: Добавить NaismithCalculator для trail run

### Проблема сейчас:
Trail run использует только Tobler для HIKE сегментов.

### Что нужно:
Использовать и Tobler, и Naismith (как в hiking).

### Изменения:

**Файл:** `backend/app/features/trail_run/service.py`

1. Импортировать NaismithCalculator:
```python
from app.features.hiking.calculators import ToblerCalculator, NaismithCalculator
```

2. Инициализировать в `__init__`:
```python
self._tobler_calc = ToblerCalculator()
self._naismith_calc = NaismithCalculator()
```

3. Использовать в расчёте:
```python
times["tobler"] = self._tobler_calc.calculate_segment(segment)
times["naismith"] = self._naismith_calc.calculate_segment(segment)
```

---

## Часть 4: Реализовать 3 варианта персонализации

### Что нужно:

| Вариант | Логика |
|---------|--------|
| **1** | Чистая формула |
| **2** | Формула × (user_flat / standard_flat) |
| **3.5** | Lookup + fallback на Вариант 2 |

### Изменения:

**Файл:** `backend/app/features/trail_run/calculators/personalization.py`

1. Добавить метод для Варианта 2 (масштабирование):
```python
def calculate_segment_scaled(self, segment: MacroSegment, base_method: str) -> MethodResult:
    """Вариант 2: масштабирование формулы по flat pace."""

    if base_method == "strava_gap":
        base_pace = self._gap_calc.calculate(segment.gradient_percent)
        scale = self.profile.avg_flat_pace_min_km / 6.0
    elif base_method == "tobler":
        base_speed = tobler_hiking_speed(segment.gradient_percent / 100)
        scale = self.profile.flat_speed_kmh / 5.0
    # ...

    scaled_pace = base_pace * scale
    return MethodResult(...)
```

2. Обновить существующий `calculate_segment()` для явного Варианта 3.5:
```python
def calculate_segment(self, segment: MacroSegment) -> MethodResult:
    """Вариант 3.5: lookup + fallback на масштабирование."""

    category = self._classify_gradient(segment.gradient_percent)
    pace = self._get_pace_for_category(category)

    if pace is not None:
        # Вариант 3: прямой lookup
        return self._result_from_pace(pace, segment, "lookup")
    else:
        # Fallback на Вариант 2
        return self.calculate_segment_scaled(segment, self.fallback_method)
```

**Файл:** `backend/app/features/trail_run/service.py`

3. Считать все варианты персонализации:
```python
# Вариант 1: базовая формула (уже есть)
times["strava_gap"] = strava_calc.calculate(segment)

# Вариант 2: масштабированная формула
if run_profile:
    times["strava_gap_scaled"] = run_pers.calculate_segment_scaled(segment, "strava_gap")

# Вариант 3.5: lookup + fallback
if run_profile:
    times["strava_gap_personalized"] = run_pers.calculate_segment(segment)
```

---

## Часть 5: Отделить Fatigue от основных расчётов

### Проблема сейчас:
Fatigue применяется внутри цикла ко всем методам, смешивается с основными totals.

### Что нужно:
Fatigue как отдельный слой — показывать дополнительное время.

### Изменения:

**Файл:** `backend/app/features/trail_run/service.py`

1. Считать totals БЕЗ fatigue:
```python
# Основной цикл — без fatigue
for segment in segments:
    times = calculate_all_methods(segment)
    accumulate_totals(times)  # Без fatigue!
```

2. Применять fatigue отдельно в конце:
```python
# После основного цикла
if apply_fatigue:
    fatigue_additions = {}
    for method, base_time in totals["full_run"].items():
        adjusted_time = apply_fatigue_to_total(base_time)
        fatigue_additions[method] = adjusted_time - base_time

    result.fatigue_additions = fatigue_additions
```

3. Новая структура результата:
```python
@dataclass
class TrailRunResult:
    # Основные расчёты (без fatigue)
    full_run: Dict[str, float]      # Всё бегом
    hybrid: Dict[str, float]        # С переходом на шаг
    personalized: Dict[str, float]  # С персонализацией

    # Fatigue отдельно
    fatigue_additions: Dict[str, float]  # +X минут к каждому методу
```

---

## Часть 6: Обновить формат вывода

### Целевой вывод:

```
📊 ВСЁ БЕГОМ (весь маршрут):
  Strava GAP: 3ч 45м
  Minetti GAP: 3ч 52м
  Strava+Minetti: 3ч 48м

📊 ВСЁ БЕГОМ + персонализация:
  Strava GAP (масштаб.): 3ч 40м
  Strava GAP (ваш темп): 3ч 38м
  Minetti GAP (масштаб.): 3ч 47м
  Minetti GAP (ваш темп): 3ч 44м
  ...

📊 БЕГ + ШАГ после 25%:
  Бег: 18.5 км | Шаг: 1.5 км

  Strava + Tobler: 3ч 58м
  Strava + Naismith: 4ч 02м
  Minetti + Tobler: 4ч 05м
  Minetti + Naismith: 4ч 08м
  ...

📊 БЕГ + ШАГ + персонализация:
  🎯 Strava + Tobler (ваш темп): 3ч 52м
  🎯 Strava + Naismith (ваш темп): 3ч 54м
  ...

😓 УСТАЛОСТЬ (дополнительно):
  Strava GAP: +12м
  Minetti GAP: +14м
  ...
```

### Изменения:

**Файл:** `bot/handlers/trail_run.py`

1. Обновить форматирование результата:
```python
def format_trail_run_result(result: TrailRunResult) -> str:
    lines = []

    # Блок 1: Всё бегом
    lines.append("📊 ВСЁ БЕГОМ (весь маршрут):")
    for method, hours in result.full_run.items():
        lines.append(f"  {method}: {format_time(hours)}")

    # Блок 2: Персонализация
    if result.personalized:
        lines.append("\n📊 ВСЁ БЕГОМ + персонализация:")
        for method, hours in result.personalized_full_run.items():
            lines.append(f"  {method}: {format_time(hours)}")

    # Блок 3: Гибридные
    lines.append(f"\n📊 БЕГ + ШАГ после {result.threshold}%:")
    lines.append(f"  Бег: {result.run_km} км | Шаг: {result.hike_km} км")
    for method, hours in result.hybrid.items():
        lines.append(f"  {method}: {format_time(hours)}")

    # Блок 4: Fatigue
    if result.fatigue_additions:
        lines.append("\n😓 УСТАЛОСТЬ (дополнительно):")
        for method, delta in result.fatigue_additions.items():
            lines.append(f"  {method}: +{format_time(delta)}")

    return "\n".join(lines)
```

---

## Порядок реализации

| Шаг | Описание | Файлы | Приоритет |
|-----|----------|-------|-----------|
| 1 | Добавить чистый Minetti GAP | `gap.py` | Высокий |
| 2 | Добавить NaismithCalculator | `service.py` | Высокий |
| 3 | Считать ВСЕ методы для ВСЕГО маршрута | `service.py` | Высокий |
| 4 | Реализовать Вариант 2 (масштабирование) | `personalization.py` | Средний |
| 5 | Отделить Fatigue | `service.py` | Средний |
| 6 | Обновить структуру результата | `service.py`, schemas | Средний |
| 7 | Обновить форматирование в боте | `bot/handlers/trail_run.py` | Низкий |

---

## Оценка объёма

| Часть | Примерно строк | Сложность |
|-------|----------------|-----------|
| Часть 1 (Minetti pure) | ~50 | Низкая |
| Часть 2 (все методы) | ~100 | Средняя |
| Часть 3 (Naismith) | ~20 | Низкая |
| Часть 4 (персонализация) | ~80 | Средняя |
| Часть 5 (fatigue) | ~50 | Низкая |
| Часть 6 (вывод) | ~60 | Низкая |
| **Итого** | **~360** | Средняя |

---

## Риски и вопросы

1. **Minetti downhill** — формула даёт нереалистичные результаты для крутых спусков. Нужно ли ограничение?

2. **Персонализация hiking для trail run** — если у пользователя нет hike профиля, что использовать для HIKE сегментов? Fallback на Tobler?

3. **Threshold по умолчанию** — оставить 25% или понизить до 15-18%?

4. **Количество выводимых методов** — для тестирования показываем все, для production нужно выбрать основные.
