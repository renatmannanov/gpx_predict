# Фаза 1: 3 базовых метода GAP

**Статус:** Готово к реализации
**Зависимости:** Нет

---

## Цель

Каждый из 3 GAP методов считает **весь маршрут** (все сегменты как бег).

---

## Текущее состояние

```python
# gap.py - GAPMode enum
class GAPMode(str, Enum):
    STRAVA = "strava"    # Strava up + Strava down
    MINETTI = "minetti"  # НА САМОМ ДЕЛЕ: Minetti up + Strava down (гибрид!)
```

```python
# service.py - totals содержит частичные данные
totals = {
    "strava_gap": X.XX,    # Только RUN сегменты!
    "minetti_gap": Y.YY,   # Только RUN сегменты + это гибрид!
    "tobler": Z.ZZ,        # Только HIKE сегменты!
    "combined": A.AA,      # Микс всего
}
```

---

## Целевое состояние

### 3 метода GAP

| Метод | Uphill | Downhill | Изменение |
|-------|--------|----------|-----------|
| `strava_gap` | Strava | Strava | Без изменений |
| `strava_minetti_gap` | Minetti | Strava | **Переименовать** из `minetti_gap` |
| `minetti_gap` | Minetti | Minetti | **Создать новый** |

### Новый totals

```python
totals = {
    # Весь маршрут как бег (ВСЕ сегменты)
    "all_run_strava": 3.75,           # часы
    "all_run_minetti": 3.87,          # часы
    "all_run_strava_minetti": 3.80,   # часы
}
```

---

## План изменений

### 1.1 Добавить константу порога

**Файл:** `backend/app/shared/constants.py`

```python
# Trail Run Thresholds
DEFAULT_HIKE_THRESHOLD_PERCENT = 25.0  # Gradient above which we hike
```

### 1.2 Рефакторинг GAPMode enum

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

```python
class GAPMode(str, Enum):
    STRAVA = "strava"                    # Strava up + Strava down (без изменений)
    MINETTI = "minetti"                  # Minetti up + Minetti down (НОВЫЙ)
    STRAVA_MINETTI = "strava_minetti"    # Minetti up + Strava down (переименован)
```

### 1.3 Создать чистый Minetti для downhill

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

Текущий `_calculate_minetti()` на спуске вызывает Strava:
```python
def _calculate_minetti(self, gradient_percent: float) -> GAPResult:
    if gradient_percent >= 0:
        # Minetti uphill - OK
        ...
    else:
        # Strava downhill - это делает его гибридом!
        return self._calculate_strava(gradient_percent)
```

Нужно создать чистый Minetti:
```python
def _calculate_minetti_pure(self, gradient_percent: float) -> GAPResult:
    """Чистый Minetti для любого градиента (up и down)."""
    i = gradient_percent / 100  # gradient as decimal

    # Minetti energy cost polynomial (работает для up и down)
    energy_cost = 155.4*i**5 - 30.4*i**4 - 43.3*i**3 + 46.3*i**2 + 19.5*i + 3.6

    # Reference cost at 0% gradient
    ref_cost = 3.6  # J/(kg·m) at flat

    # Energy ratio
    energy_ratio = energy_cost / ref_cost

    # Pace adjustment (power law)
    adjustment = energy_ratio ** 0.75

    # Clamp для безопасности (не быстрее 2x flat на спусках)
    adjustment = max(0.5, min(adjustment, 3.0))

    adjusted_pace = self.flat_pace * adjustment

    return GAPResult(
        gradient_percent=gradient_percent,
        flat_pace_min_km=self.flat_pace,
        adjusted_pace_min_km=adjusted_pace,
        pace_adjustment_factor=adjustment,
        formula_used="minetti_pure",
        speed_kmh=60 / adjusted_pace,
    )
```

### 1.4 Переименовать текущий гибрид

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

```python
def _calculate_strava_minetti(self, gradient_percent: float) -> GAPResult:
    """Гибрид: Minetti uphill + Strava downhill."""
    if gradient_percent >= 0:
        return self._calculate_minetti_pure(gradient_percent)
    else:
        return self._calculate_strava(gradient_percent)
```

### 1.5 Обновить метод calculate()

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

```python
def calculate(self, gradient_percent: float) -> GAPResult:
    if self.mode == GAPMode.STRAVA:
        return self._calculate_strava(gradient_percent)
    elif self.mode == GAPMode.MINETTI:
        return self._calculate_minetti_pure(gradient_percent)
    else:  # STRAVA_MINETTI
        return self._calculate_strava_minetti(gradient_percent)
```

### 1.6 Обновить TrailRunService

**Файл:** `backend/app/features/trail_run/service.py`

Изменить `calculate_route()` чтобы все 3 метода считали **все сегменты**:

```python
def calculate_route(self, points: List[tuple]) -> TrailRunResult:
    segments = RouteSegmenter.segment_route(points)

    # Создаём калькуляторы для всех 3 методов
    strava_calc = GAPCalculator(GAPMode.STRAVA, self.flat_pace)
    minetti_calc = GAPCalculator(GAPMode.MINETTI, self.flat_pace)
    strava_minetti_calc = GAPCalculator(GAPMode.STRAVA_MINETTI, self.flat_pace)

    # Инициализация totals
    all_run_strava = 0.0
    all_run_minetti = 0.0
    all_run_strava_minetti = 0.0

    segment_results = []

    for segment in segments:
        # Считаем ВСЕ методы для КАЖДОГО сегмента
        strava_time = strava_calc.calculate_segment(segment).time_hours
        minetti_time = minetti_calc.calculate_segment(segment).time_hours
        strava_minetti_time = strava_minetti_calc.calculate_segment(segment).time_hours

        all_run_strava += strava_time
        all_run_minetti += minetti_time
        all_run_strava_minetti += strava_minetti_time

        segment_results.append(SegmentResult(
            segment=segment,
            times={
                "strava_gap": strava_time,
                "minetti_gap": minetti_time,
                "strava_minetti_gap": strava_minetti_time,
            },
            # movement пока не определяем (это Фаза 2)
        ))

    totals = {
        "all_run_strava": all_run_strava,
        "all_run_minetti": all_run_minetti,
        "all_run_strava_minetti": all_run_strava_minetti,
    }

    return TrailRunResult(
        segments=segment_results,
        totals=totals,
        summary=self._calculate_summary(segments, totals),
        # ...
    )
```

### 1.7 Обновить схемы

**Файл:** `backend/app/schemas/prediction.py`

Добавить новый режим в enum:
```python
class GAPModeEnum(str, Enum):
    STRAVA = "strava_gap"
    MINETTI = "minetti_gap"
    STRAVA_MINETTI = "strava_minetti_gap"  # НОВЫЙ
```

### 1.8 Обновить форматирование в боте

**Файл:** `bot/handlers/trail_run.py`

```python
def format_trail_run_result(result: dict, gpx_name: str) -> str:
    totals = result.get("totals", {})
    summary = result.get("summary", {})

    lines = [
        f"🏃 TRAIL RUN: {gpx_name}",
        "",
        f"📍 {summary.get('total_distance_km', 0):.1f} км | "
        f"D+ {summary.get('total_elevation_gain_m', 0):.0f}м | "
        f"D- {summary.get('total_elevation_loss_m', 0):.0f}м",
        "",
        "⏱ ВРЕМЯ (всё бегом):",
        f"  Strava GAP:       {format_hours(totals.get('all_run_strava', 0))}",
        f"  Minetti GAP:      {format_hours(totals.get('all_run_minetti', 0))}",
        f"  Strava+Minetti:   {format_hours(totals.get('all_run_strava_minetti', 0))}",
    ]

    return "\n".join(lines)


def format_segments(result: dict) -> str:
    """Форматирует сегменты в quote блок."""
    segments = result.get("segments", [])

    lines = ["📊 СЕГМЕНТЫ:"]

    for seg in segments:
        num = seg.get("segment_number", 0)
        dist_start = seg.get("start_km", 0)
        dist_end = seg.get("end_km", 0)
        gradient = seg.get("gradient_percent", 0)

        # Время берём из strava_gap (primary для этой фазы)
        time_hours = seg.get("times", {}).get("strava_gap", 0)
        time_min = int(time_hours * 60)

        # Эмодзи пока всегда бег (нет movement в Фазе 1)
        emoji = "🏃"

        lines.append(
            f"{num}. {emoji} {dist_start:.1f}-{dist_end:.1f}км | "
            f"{gradient:+.0f}% | {time_min}м"
        )

    # Оборачиваем в quote
    return "\n".join(f"> {line}" for line in lines)
```

---

## Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `backend/app/shared/constants.py` | +3 строки (константа) |
| `backend/app/features/trail_run/calculators/gap.py` | ~50 строк (новый метод + рефакторинг) |
| `backend/app/features/trail_run/service.py` | ~30 строк (новая логика totals) |
| `backend/app/schemas/prediction.py` | +1 строка (новый enum) |
| `bot/handlers/trail_run.py` | ~40 строк (форматирование) |

**Итого:** ~120 строк изменений

---

## Чеклист проверки

После реализации:

- [ ] GAPMode имеет 3 значения: STRAVA, MINETTI, STRAVA_MINETTI
- [ ] `_calculate_minetti_pure()` работает для up и down
- [ ] `_calculate_strava_minetti()` использует Minetti up + Strava down
- [ ] API возвращает 3 значения в totals: `all_run_strava`, `all_run_minetti`, `all_run_strava_minetti`
- [ ] Все 3 значения считают ВСЕ сегменты (не частичные)
- [ ] Бот показывает 3 времени в формате "⏱ ВРЕМЯ (всё бегом)"
- [ ] Сегменты показываются в quote блоке
- [ ] Minetti и Strava+Minetti дают **разные** значения

---

## Тест-кейс

Маршрут: 10 км, +500м, -500м

Ожидаемый результат (примерно):
```
⏱ ВРЕМЯ (всё бегом):
  Strava GAP:       1ч 12м
  Minetti GAP:      1ч 18м   ← должен быть медленнее на спусках
  Strava+Minetti:   1ч 15м   ← между ними
```

Minetti GAP должен быть **медленнее** чем Strava+Minetti, потому что чистый Minetti консервативнее на спусках.
