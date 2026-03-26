# Фаза 3: Персонализация

**Статус:** Готово к реализации
**Зависимости:** Фаза 2 ✅

---

## Цель

Добавить персонализированные расчёты в вывод trail running:
- Персональный метод как 4-й в ряду со Strava/Minetti/S+M
- Комбинации Перс + Tobler и Перс + Naismith для блока "Бег + Шаг"
- Мета-информация о профиле (км, активности, сплиты, заполненность)

---

## Важно: Персонализация уже реализована!

Сервисы персонализации **уже существуют** и работают:
- `RunPersonalizationService` — 7-категорийная система с fallback на GAP
- `HikePersonalizationService` — 7-категорийная система с fallback на Tobler
- Интеграция в `TrailRunService` — уже есть `run_personalized` и `hike_personalized`

**Что нужно сделать в этой фазе:**
1. Добавить недостающие totals-ключи для комбинаций
2. Добавить мета-информацию о профиле в totals
3. Обновить вывод в боте
4. Исправить иконку хайкинга на 🥾

---

## Итоговый формат вывода

```
🏃 Trail Run: Маршрут

📍 20.0 км | D+ 1200м | D- 1200м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 ВСЁ БЕГОМ:
  Strava GAP       3ч 15мин
  Minetti GAP      2ч 57мин
  Strava+Minetti   3ч 4мин
  🎯 Персональный  3ч 8мин

━━━━━━━━━━━━━━━━━━━━━━━━

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🥾 1.5км (8%)

  Strava + Tobler    4ч 55мин
  Strava + Naismith  6ч 4мин
  Minetti + Tobler   4ч 50мин
  Minetti + Naismith 5ч 59мин
  S+M + Tobler       4ч 57мин
  S+M + Naismith     6ч 6мин
  🎯 Перс + Tobler   5ч 2мин
  🎯 Перс + Naismith 6ч 10мин

━━━━━━━━━━━━━━━━━━━━━━━━

📈 Персонализация: 127 км, 15 активностей, 892 сплита, профиль 5 из 7
```

**Примечания:**
- 🥾 вместо 🚶 для хайкинга (заметнее и понятнее)
- Персональный метод в обоих блоках (всё бегом + бег/шаг)
- Мета-информация внизу: км → активности → сплиты → заполненность профиля

---

## Что добавляется в totals

```python
totals = {
    # Блок 1: Всё бегом (из Фазы 1)
    "all_run_strava": ...,
    "all_run_minetti": ...,
    "all_run_strava_minetti": ...,

    # Блок 1 персонализированный (НОВОЕ)
    "all_run_personalized": ...,  # = текущий run_personalized

    # Блок 2: Бег + Шаг (из Фазы 2)
    "run_hike_strava_tobler": ...,
    "run_hike_strava_naismith": ...,
    "run_hike_minetti_tobler": ...,
    "run_hike_minetti_naismith": ...,
    "run_hike_strava_minetti_tobler": ...,
    "run_hike_strava_minetti_naismith": ...,

    # Блок 2 персонализированный (НОВОЕ)
    "run_hike_personalized_tobler": ...,    # Run: персональный, Hike: Tobler
    "run_hike_personalized_naismith": ...,  # Run: персональный, Hike: Naismith

    # Информация о персонализации (НОВОЕ/РАСШИРИТЬ)
    "personalized": True,
    "run_profile": {
        "total_distance_km": 127.0,
        "total_activities": 15,
        "total_splits": 892,
        "categories_filled": 5,  # из 7
        "categories_total": 7,
    },
}
```

---

## План изменений

### 3.1 Обновить TrailRunService — добавить персонализированные комбинации

**Файл:** `backend/app/features/trail_run/service.py`

```python
def calculate_route(self, points: List[tuple]) -> TrailRunResult:
    # ... существующий код ...

    # Новые аккумуляторы для персонализированных комбинаций
    all_run_personalized = 0.0
    run_hike_personalized_tobler = 0.0
    run_hike_personalized_naismith = 0.0

    for segment, decision in zip(segments, decisions):
        # ... существующий код для GAP и Hiking ...

        # Персонализация (уже есть в коде)
        if self._run_pers:
            run_pers_result = self._run_pers.calculate_segment(segment)
            run_pers_time = run_pers_result.time_hours
        else:
            run_pers_time = strava_minetti_time  # Fallback

        # Блок 1: Всё бегом персонализированный
        all_run_personalized += run_pers_time

        # Блок 2: Бег + Шаг персонализированный (НОВОЕ)
        if decision.mode == MovementMode.RUN:
            run_hike_personalized_tobler += run_pers_time
            run_hike_personalized_naismith += run_pers_time
        else:  # HIKE
            run_hike_personalized_tobler += tobler_time
            run_hike_personalized_naismith += naismith_time

    # Добавляем в totals
    if self._run_pers:
        totals.update({
            "all_run_personalized": all_run_personalized,
            "run_hike_personalized_tobler": run_hike_personalized_tobler,
            "run_hike_personalized_naismith": run_hike_personalized_naismith,
            "run_profile": self._build_run_profile_info(),
        })
```

### 3.2 Добавить метод для сбора информации о профиле

**Файл:** `backend/app/features/trail_run/service.py`

```python
def _build_run_profile_info(self) -> dict:
    """Собрать информацию о run профиле для вывода."""
    if not self._run_profile:
        return None

    # Подсчёт заполненных категорий
    categories = [
        self._run_profile.avg_steep_uphill_pace_min_km,
        self._run_profile.avg_moderate_uphill_pace_min_km,
        self._run_profile.avg_gentle_uphill_pace_min_km,
        self._run_profile.avg_flat_pace_min_km,
        self._run_profile.avg_gentle_downhill_pace_min_km,
        self._run_profile.avg_moderate_downhill_pace_min_km,
        self._run_profile.avg_steep_downhill_pace_min_km,
    ]
    categories_filled = sum(1 for c in categories if c is not None)

    return {
        "total_distance_km": self._run_profile.total_distance_km or 0,
        "total_activities": self._run_profile.total_activities or 0,
        "total_splits": self._get_total_splits(),
        "categories_filled": categories_filled,
        "categories_total": 7,
    }

def _get_total_splits(self) -> int:
    """Подсчитать общее количество сплитов в профиле."""
    if not self._run_profile:
        return 0

    return sum([
        self._run_profile.flat_sample_count or 0,
        self._run_profile.gentle_uphill_sample_count or 0,
        self._run_profile.moderate_uphill_sample_count or 0,
        self._run_profile.steep_uphill_sample_count or 0,
        self._run_profile.gentle_downhill_sample_count or 0,
        self._run_profile.moderate_downhill_sample_count or 0,
        self._run_profile.steep_downhill_sample_count or 0,
    ])
```

### 3.3 Обновить форматирование в боте

**Файл:** `bot/handlers/trail_run.py`

```python
def format_trail_run_result(result: dict, gpx_name: str) -> str:
    totals = result.get("totals", {}) or result.get("totals_manual", {})
    summary = result.get("summary", {})

    # ... header ...

    lines = [
        f"🏃 <b>Trail Run: {gpx_name}</b>",
        "",
        f"📍 {distance:.1f} км | D+ {gain:.0f}м | D- {loss:.0f}м",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "📊 <b>ВСЁ БЕГОМ:</b>",
        f"  Strava GAP       {format_time(totals.get('all_run_strava', 0))}",
        f"  Minetti GAP      {format_time(totals.get('all_run_minetti', 0))}",
        f"  Strava+Minetti   {format_time(totals.get('all_run_strava_minetti', 0))}",
    ]

    # Персональный (если есть)
    if totals.get("all_run_personalized"):
        lines.append(f"  🎯 Персональный  {format_time(totals['all_run_personalized'])}")

    # Блок Бег + Шаг
    threshold = totals.get("threshold_used", 25)
    run_dist = totals.get("run_distance_km", 0)
    hike_dist = totals.get("hike_distance_km", 0)
    run_pct = totals.get("run_percent", 0)
    hike_pct = totals.get("hike_percent", 0)

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📊 <b>БЕГ + ШАГ</b> (порог {threshold:.0f}%):",
        f"  🏃 {run_dist:.1f}км ({run_pct:.0f}%) | 🥾 {hike_dist:.1f}км ({hike_pct:.0f}%)",
        "",
        f"  Strava + Tobler    {format_time(totals.get('run_hike_strava_tobler', 0))}",
        f"  Strava + Naismith  {format_time(totals.get('run_hike_strava_naismith', 0))}",
        f"  Minetti + Tobler   {format_time(totals.get('run_hike_minetti_tobler', 0))}",
        f"  Minetti + Naismith {format_time(totals.get('run_hike_minetti_naismith', 0))}",
        f"  S+M + Tobler       {format_time(totals.get('run_hike_strava_minetti_tobler', 0))}",
        f"  S+M + Naismith     {format_time(totals.get('run_hike_strava_minetti_naismith', 0))}",
    ])

    # Персональные комбинации (если есть)
    if totals.get("run_hike_personalized_tobler"):
        lines.extend([
            f"  🎯 Перс + Tobler   {format_time(totals['run_hike_personalized_tobler'])}",
            f"  🎯 Перс + Naismith {format_time(totals['run_hike_personalized_naismith'])}",
        ])

    # Мета-информация о персонализации
    run_profile = totals.get("run_profile")
    if run_profile:
        km = run_profile.get("total_distance_km", 0)
        acts = run_profile.get("total_activities", 0)
        splits = run_profile.get("total_splits", 0)
        filled = run_profile.get("categories_filled", 0)
        total = run_profile.get("categories_total", 7)

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📈 Персонализация: {km:.0f} км, {acts} активностей, {splits} сплитов, профиль {filled} из {total}",
        ])

    return "\n".join(lines)


def format_segments(result: dict) -> str:
    """Format segments with 🥾 for hike."""
    segments = result.get("segments", [])
    if not segments:
        return ""

    lines = [f"<blockquote>📊 СЕГМЕНТЫ ({len(segments)}):"]
    lines.append("")

    for i, seg in enumerate(segments, 1):
        distance = seg.get("distance_km", 0)
        gradient = seg.get("gradient_percent", 0)
        movement = seg.get("movement", {})
        mode = movement.get("mode", "run")
        times = seg.get("times", {})

        if mode == "hike":
            time_hours = times.get("tobler", 0)
            mode_icon = "🥾"  # Сапог для хайкинга
        else:
            time_hours = times.get("strava_gap", 0)
            mode_icon = "🏃"

        gradient_sign = "+" if gradient > 0 else ""

        lines.append(
            f"{i}. {mode_icon} {distance:.1f}км ({gradient_sign}{gradient:.0f}%) — {format_time(time_hours)}"
        )

    lines.append("</blockquote>")
    return "\n".join(lines)
```

---

## Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `backend/app/features/trail_run/service.py` | ~40 строк (персонализированные комбинации + profile info) |
| `bot/handlers/trail_run.py` | ~30 строк (обновить вывод + 🥾) |

**Итого:** ~70 строк изменений

---

## Чеклист проверки

- [ ] `all_run_personalized` появляется в totals (если есть профиль)
- [ ] `run_hike_personalized_tobler` и `run_hike_personalized_naismith` появляются
- [ ] `run_profile` содержит km, activities, splits, categories_filled
- [ ] Бот показывает 🎯 Персональный в блоке "Всё бегом"
- [ ] Бот показывает 🎯 Перс + Tobler/Naismith в блоке "Бег + Шаг"
- [ ] Мета-строка внизу: "📈 Персонализация: X км, Y активностей, Z сплитов, профиль N из 7"
- [ ] Иконка 🥾 вместо 🚶 для хайкинга везде
- [ ] Без профиля: персонализированные строки не показываются

---

## Тест-кейсы

### Кейс 1: Пользователь с run профилем

```
📊 ВСЁ БЕГОМ:
  Strava GAP       3ч 15мин
  Minetti GAP      2ч 57мин
  Strava+Minetti   3ч 4мин
  🎯 Персональный  3ч 8мин

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🥾 1.5км (8%)

  Strava + Tobler    4ч 55мин
  ...
  🎯 Перс + Tobler   5ч 2мин
  🎯 Перс + Naismith 6ч 10мин

📈 Персонализация: 127 км, 15 активностей, 892 сплита, профиль 5 из 7
```

### Кейс 2: Пользователь без профиля

```
📊 ВСЁ БЕГОМ:
  Strava GAP       3ч 15мин
  Minetti GAP      2ч 57мин
  Strava+Minetti   3ч 4мин

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🥾 1.5км (8%)

  Strava + Tobler    4ч 55мин
  ...
```

Без профиля — нет 🎯 строк и нет мета-информации.

---

## Что НЕ делаем в этой фазе

- ❌ Не меняем логику персонализации (она уже работает)
- ❌ Не добавляем `Перс + Перс` (hike персонализация) — пока достаточно Tobler/Naismith
- ❌ Не трогаем HikePersonalizationService
