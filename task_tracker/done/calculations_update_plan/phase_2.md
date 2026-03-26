# Фаза 2: Переход на шаг (Tobler/Naismith)

**Статус:** Ожидает Фазу 1
**Зависимости:** Фаза 1

---

## Цель

После порога X% градиента использовать hiking формулы (Tobler/Naismith) вместо GAP.

---

## Что добавляется

### Блок "Бег + Шаг" в totals

6 комбинаций: 3 GAP метода × 2 Hiking метода

```python
totals = {
    # Блок 1: Всё бегом (из Фазы 1)
    "all_run_strava": ...,
    "all_run_minetti": ...,
    "all_run_strava_minetti": ...,

    # Блок 2: Бег + Шаг (НОВЫЙ)
    "run_hike_strava_tobler": ...,
    "run_hike_strava_naismith": ...,
    "run_hike_minetti_tobler": ...,
    "run_hike_minetti_naismith": ...,
    "run_hike_strava_minetti_tobler": ...,
    "run_hike_strava_minetti_naismith": ...,

    # Статистика разбивки
    "run_distance_km": 18.5,
    "hike_distance_km": 1.5,
    "run_percent": 92.5,
    "hike_percent": 7.5,
    "threshold_used": 25.0,
}
```

---

## План изменений

### 2.1 Импортировать NaismithCalculator

**Файл:** `backend/app/features/trail_run/service.py`

```python
from app.features.hiking.calculators import ToblerCalculator, NaismithCalculator
```

### 2.2 Добавить hiking калькуляторы в calculate_route()

**Файл:** `backend/app/features/trail_run/service.py`

```python
def calculate_route(self, points: List[tuple]) -> TrailRunResult:
    segments = RouteSegmenter.segment_route(points)

    # GAP калькуляторы (из Фазы 1)
    strava_calc = GAPCalculator(GAPMode.STRAVA, self.flat_pace)
    minetti_calc = GAPCalculator(GAPMode.MINETTI, self.flat_pace)
    strava_minetti_calc = GAPCalculator(GAPMode.STRAVA_MINETTI, self.flat_pace)

    # Hiking калькуляторы (НОВОЕ)
    tobler_calc = ToblerCalculator()
    naismith_calc = NaismithCalculator()

    # Threshold service для определения RUN/HIKE
    threshold = self._walk_threshold_override or DEFAULT_HIKE_THRESHOLD_PERCENT
    decisions = self._threshold_service.process_route(segments)

    # Инициализация totals
    # Блок 1: Всё бегом
    all_run_strava = 0.0
    all_run_minetti = 0.0
    all_run_strava_minetti = 0.0

    # Блок 2: Бег + Шаг (6 комбинаций)
    run_hike_strava_tobler = 0.0
    run_hike_strava_naismith = 0.0
    run_hike_minetti_tobler = 0.0
    run_hike_minetti_naismith = 0.0
    run_hike_strava_minetti_tobler = 0.0
    run_hike_strava_minetti_naismith = 0.0

    # Статистика
    run_distance_km = 0.0
    hike_distance_km = 0.0

    segment_results = []

    for segment, decision in zip(segments, decisions):
        # GAP времена (для всех сегментов)
        strava_time = strava_calc.calculate_segment(segment).time_hours
        minetti_time = minetti_calc.calculate_segment(segment).time_hours
        strava_minetti_time = strava_minetti_calc.calculate_segment(segment).time_hours

        # Hiking времена (для всех сегментов)
        tobler_time = tobler_calc.calculate_segment(segment).time_hours
        naismith_time = naismith_calc.calculate_segment(segment).time_hours

        # Блок 1: Всё бегом (все сегменты как бег)
        all_run_strava += strava_time
        all_run_minetti += minetti_time
        all_run_strava_minetti += strava_minetti_time

        # Блок 2: Бег + Шаг (по решению threshold)
        if decision.mode == MovementMode.RUN:
            run_distance_km += segment.distance_km
            run_hike_strava_tobler += strava_time
            run_hike_strava_naismith += strava_time
            run_hike_minetti_tobler += minetti_time
            run_hike_minetti_naismith += minetti_time
            run_hike_strava_minetti_tobler += strava_minetti_time
            run_hike_strava_minetti_naismith += strava_minetti_time
        else:  # HIKE
            hike_distance_km += segment.distance_km
            run_hike_strava_tobler += tobler_time
            run_hike_strava_naismith += naismith_time
            run_hike_minetti_tobler += tobler_time
            run_hike_minetti_naismith += naismith_time
            run_hike_strava_minetti_tobler += tobler_time
            run_hike_strava_minetti_naismith += naismith_time

        segment_results.append(SegmentResult(
            segment=segment,
            movement=decision,
            times={
                "strava_gap": strava_time,
                "minetti_gap": minetti_time,
                "strava_minetti_gap": strava_minetti_time,
                "tobler": tobler_time,
                "naismith": naismith_time,
            },
        ))

    total_distance = run_distance_km + hike_distance_km

    totals = {
        # Блок 1
        "all_run_strava": all_run_strava,
        "all_run_minetti": all_run_minetti,
        "all_run_strava_minetti": all_run_strava_minetti,
        # Блок 2
        "run_hike_strava_tobler": run_hike_strava_tobler,
        "run_hike_strava_naismith": run_hike_strava_naismith,
        "run_hike_minetti_tobler": run_hike_minetti_tobler,
        "run_hike_minetti_naismith": run_hike_minetti_naismith,
        "run_hike_strava_minetti_tobler": run_hike_strava_minetti_tobler,
        "run_hike_strava_minetti_naismith": run_hike_strava_minetti_naismith,
        # Статистика
        "run_distance_km": run_distance_km,
        "hike_distance_km": hike_distance_km,
        "run_percent": (run_distance_km / total_distance * 100) if total_distance > 0 else 100,
        "hike_percent": (hike_distance_km / total_distance * 100) if total_distance > 0 else 0,
        "threshold_used": threshold,
    }

    return TrailRunResult(...)
```

### 2.3 Обновить форматирование в боте

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
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "📊 ВСЁ БЕГОМ:",
        f"  Strava GAP:       {format_hours(totals.get('all_run_strava', 0))}",
        f"  Minetti GAP:      {format_hours(totals.get('all_run_minetti', 0))}",
        f"  Strava+Minetti:   {format_hours(totals.get('all_run_strava_minetti', 0))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📊 БЕГ + ШАГ (порог {totals.get('threshold_used', 25):.0f}%):",
        f"  🏃 {totals.get('run_distance_km', 0):.1f}км ({totals.get('run_percent', 0):.0f}%) | "
        f"🚶 {totals.get('hike_distance_km', 0):.1f}км ({totals.get('hike_percent', 0):.0f}%)",
        "",
        f"  Strava + Tobler:    {format_hours(totals.get('run_hike_strava_tobler', 0))}",
        f"  Strava + Naismith:  {format_hours(totals.get('run_hike_strava_naismith', 0))}",
        f"  Minetti + Tobler:   {format_hours(totals.get('run_hike_minetti_tobler', 0))}",
        f"  Minetti + Naismith: {format_hours(totals.get('run_hike_minetti_naismith', 0))}",
        f"  S+M + Tobler:       {format_hours(totals.get('run_hike_strava_minetti_tobler', 0))}",
        f"  S+M + Naismith:     {format_hours(totals.get('run_hike_strava_minetti_naismith', 0))}",
    ]

    return "\n".join(lines)


def format_segments(result: dict) -> str:
    """Форматирует сегменты в quote блок."""
    segments = result.get("segments", [])

    lines = [f"📊 СЕГМЕНТЫ ({len(segments)}):"]

    for seg in segments:
        num = seg.get("segment_number", 0)
        dist_start = seg.get("start_km", 0)
        dist_end = seg.get("end_km", 0)
        gradient = seg.get("gradient_percent", 0)
        movement = seg.get("movement", {})
        mode = movement.get("mode", "run")

        # Время из primary метода
        times = seg.get("times", {})
        if mode == "hike":
            time_hours = times.get("tobler", 0)
            emoji = "🚶"
        else:
            time_hours = times.get("strava_gap", 0)
            emoji = "🏃"

        time_min = int(time_hours * 60)

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
| `backend/app/features/trail_run/service.py` | ~60 строк (hiking калькуляторы + 6 комбинаций) |
| `bot/handlers/trail_run.py` | ~30 строк (блок "Бег + Шаг") |

**Итого:** ~90 строк изменений

---

## Чеклист проверки

- [ ] NaismithCalculator импортирован и работает
- [ ] Все 6 комбинаций считаются корректно
- [ ] `run_distance_km` + `hike_distance_km` = total_distance
- [ ] Процент разбивки корректен
- [ ] Сегменты показывают правильный emoji (🏃/🚶)
- [ ] Блок "Бег + Шаг" > блок "Всё бегом" (ходьба медленнее бега)

---

## Тест-кейс

Маршрут: 20 км, +2000м (с участками >25%)

Ожидаемый результат (примерно):
```
📊 ВСЁ БЕГОМ:
  Strava GAP:       3ч 45м
  Minetti GAP:      3ч 52м
  Strava+Minetti:   3ч 48м

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🚶 1.5км (8%)

  Strava + Tobler:    3ч 58м   ← больше чем 3ч 45м
  Strava + Naismith:  4ч 02м
  ...
```

Все комбинации "Бег + Шаг" должны быть **больше** соответствующих "Всё бегом".
