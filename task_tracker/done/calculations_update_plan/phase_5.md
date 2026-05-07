# Фаза 5: Структура вывода и варианты 1/2/3.5

**Статус:** Ожидает Фазу 4
**Зависимости:** Фаза 4

---

## Цель

Финализировать структуру вывода:
1. Чёткое разделение вариантов расчёта (1/2/3.5)
2. Понятный и красивый формат для бота
3. Сегменты в отдельном сообщении с quote

---

## Варианты расчёта (напоминание)

| Вариант | Условие | Логика |
|---------|---------|--------|
| **1** | Нет профиля, стандартный flat (6:00/км) | Чистая формула |
| **2** | Пользователь ввёл свой flat | Формула × (user_flat / 6.0) |
| **3.5** | Есть Strava профиль | Lookup + fallback на Вариант 2 |

### Как это уже реализовано

- **Вариант 1:** `flat_pace_min_km = 6.0` (default)
- **Вариант 2:** `flat_pace_min_km = X` (параметр запроса) — уже работает!
- **Вариант 3.5:** Персонализация с fallback — добавлена в Фазе 3

---

## Финальная структура totals

```python
totals = {
    # ═══════════════════════════════════════════════════════
    # БЛОК 1: ВСЁ БЕГОМ
    # ═══════════════════════════════════════════════════════

    # Базовые формулы (Вариант 1 или 2, в зависимости от flat_pace)
    "all_run_strava": 3.75,
    "all_run_minetti": 3.87,
    "all_run_strava_minetti": 3.80,

    # Усталость для базовых
    "all_run_strava_fatigue": 0.32,
    "all_run_minetti_fatigue": 0.35,
    "all_run_strava_minetti_fatigue": 0.33,

    # Персонализированный (Вариант 3.5, если есть профиль)
    "all_run_personalized": 3.63,
    "all_run_personalized_fatigue": 0.28,

    # ═══════════════════════════════════════════════════════
    # БЛОК 2: БЕГ + ШАГ
    # ═══════════════════════════════════════════════════════

    # Базовые комбинации
    "run_hike_strava_tobler": 3.97,
    "run_hike_strava_naismith": 4.03,
    "run_hike_minetti_tobler": 4.08,
    "run_hike_minetti_naismith": 4.13,
    "run_hike_strava_minetti_tobler": 4.02,
    "run_hike_strava_minetti_naismith": 4.08,

    # Усталость для базовых комбинаций
    "run_hike_strava_tobler_fatigue": 0.38,
    "run_hike_strava_naismith_fatigue": 0.40,
    # ... для всех комбинаций

    # Персонализированные комбинации
    "run_hike_personalized_tobler": 3.87,
    "run_hike_personalized_naismith": 3.90,
    "run_hike_personalized_personalized": 3.82,

    # Усталость для персонализированных
    "run_hike_personalized_tobler_fatigue": 0.35,
    "run_hike_personalized_naismith_fatigue": 0.36,
    "run_hike_personalized_personalized_fatigue": 0.33,

    # Статистика разбивки
    "run_distance_km": 18.5,
    "hike_distance_km": 1.5,
    "run_percent": 92.5,
    "hike_percent": 7.5,
    "threshold_used": 25.0,

    # ═══════════════════════════════════════════════════════
    # МЕТАДАННЫЕ
    # ═══════════════════════════════════════════════════════

    # Информация о персонализации
    "personalized": True,
    "run_activities_used": 15,
    "hike_activities_used": 8,
    "run_profile_coverage": 0.85,
    "hike_profile_coverage": 0.60,

    # Информация об усталости
    "fatigue_enabled": True,
    "fatigue_threshold_hours": 2.0,

    # Используемый flat pace
    "flat_pace_used": 5.5,  # мин/км
    "calculation_variant": "3.5",  # "1", "2", или "3.5"
}
```

---

## Финальный формат вывода (бот)

### Сообщение 1: Результаты

```
🏃 TRAIL RUN: Talgar Trail

📍 20.0 км | D+ 2323м | D- 2323м
⚙️ Темп flat: 5:30/км | Вариант: персональный

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 ВСЁ БЕГОМ:

  Базовые формулы:
    Strava GAP:       3ч 45м (+19м)
    Minetti GAP:      3ч 52м (+21м)
    Strava+Minetti:   3ч 48м (+20м)

  🎯 Персональный (15 активностей, 85%):
    3ч 38м (+17м)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 БЕГ + ШАГ (порог 25%):
  🏃 18.5км (92%) | 🚶 1.5км (8%)

  Базовые:
    Strava + Tobler:    3ч 58м (+23м)
    Strava + Naismith:  4ч 02м (+24м)
    Minetti + Tobler:   4ч 05м (+25м)
    Minetti + Naismith: 4ч 08м (+26м)
    S+M + Tobler:       4ч 01м (+24м)
    S+M + Naismith:     4ч 05м (+25м)

  🎯 Персональные:
    Pers + Tobler:      3ч 52м (+21м)
    Pers + Naismith:    3ч 54м (+22м)
    Pers + Pers:        3ч 49м (+20м)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

😓 Усталость включена (после 2ч)
👤 На основе 15 run + 8 hike активностей
```

### Сообщение 2: Сегменты (в quote)

```
> 📊 СЕГМЕНТЫ (23):
>
> 1.  🏃 0.0-1.2км   | +5%   | 7м
> 2.  🏃 1.2-2.8км   | -8%   | 8м
> 3.  🏃 2.8-4.5км   | +12%  | 14м
> 4.  🚶 4.5-5.3км   | +28%  | 18м
> 5.  🏃 5.3-7.1км   | +6%   | 11м
> 6.  🏃 7.1-9.0км   | -15%  | 9м
> 7.  🚶 9.0-9.8км   | +32%  | 20м
> 8.  🏃 9.8-11.5км  | +4%   | 10м
> 9.  🏃 11.5-13.2км | -10%  | 8м
> 10. 🏃 13.2-14.8км | +7%   | 10м
> 11. 🚶 14.8-15.6км | +26%  | 17м
> 12. 🏃 15.6-17.3км | -5%   | 9м
> 13. 🏃 17.3-18.9км | +3%   | 10м
> 14. 🏃 18.9-20.0км | -12%  | 5м
> ...
```

---

## План изменений

### 5.1 Добавить calculation_variant в response

**Файл:** `backend/app/features/trail_run/service.py`

```python
def _determine_calculation_variant(self) -> str:
    """Определить какой вариант расчёта используется."""
    if self._run_profile:
        return "3.5"  # Персонализация
    elif self.flat_pace != 6.0:
        return "2"    # Пользовательский flat
    else:
        return "1"    # Стандартный

# В calculate_route():
totals["calculation_variant"] = self._determine_calculation_variant()
totals["flat_pace_used"] = self.flat_pace
```

### 5.2 Рефакторинг форматирования

**Файл:** `bot/handlers/trail_run.py`

Разбить на функции:

```python
def format_trail_run_result(result: dict, gpx_name: str) -> str:
    """Главная функция форматирования."""
    lines = []
    lines.extend(_format_header(result, gpx_name))
    lines.extend(_format_all_run_block(result))
    lines.extend(_format_run_hike_block(result))
    lines.extend(_format_footer(result))
    return "\n".join(lines)


def _format_header(result: dict, gpx_name: str) -> List[str]:
    """Заголовок с метаданными."""
    totals = result.get("totals", {})
    summary = result.get("summary", {})

    variant_names = {
        "1": "базовый",
        "2": "свой темп",
        "3.5": "персональный",
    }
    variant = totals.get("calculation_variant", "1")
    flat_pace = totals.get("flat_pace_used", 6.0)

    return [
        f"🏃 TRAIL RUN: {gpx_name}",
        "",
        f"📍 {summary.get('total_distance_km', 0):.1f} км | "
        f"D+ {summary.get('total_elevation_gain_m', 0):.0f}м | "
        f"D- {summary.get('total_elevation_loss_m', 0):.0f}м",
        f"⚙️ Темп flat: {format_pace(flat_pace)} | Вариант: {variant_names[variant]}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]


def _format_all_run_block(result: dict) -> List[str]:
    """Блок 'Всё бегом'."""
    totals = result.get("totals", {})
    fatigue = totals.get("fatigue_enabled", False)
    personalized = totals.get("personalized", False)

    lines = [
        "",
        "📊 ВСЁ БЕГОМ:",
        "",
        "  Базовые формулы:",
    ]

    # Базовые методы
    for method, key in [
        ("Strava GAP", "all_run_strava"),
        ("Minetti GAP", "all_run_minetti"),
        ("Strava+Minetti", "all_run_strava_minetti"),
    ]:
        time_str = _format_time_with_fatigue(
            totals.get(key, 0),
            totals.get(f"{key}_fatigue", 0) if fatigue else 0,
        )
        lines.append(f"    {method:17} {time_str}")

    # Персонализированный
    if personalized:
        run_acts = totals.get("run_activities_used", 0)
        coverage = totals.get("run_profile_coverage", 0) * 100
        time_str = _format_time_with_fatigue(
            totals.get("all_run_personalized", 0),
            totals.get("all_run_personalized_fatigue", 0) if fatigue else 0,
        )
        lines.extend([
            "",
            f"  🎯 Персональный ({run_acts} активностей, {coverage:.0f}%):",
            f"    {time_str}",
        ])

    return lines


def _format_run_hike_block(result: dict) -> List[str]:
    """Блок 'Бег + Шаг'."""
    totals = result.get("totals", {})
    fatigue = totals.get("fatigue_enabled", False)
    personalized = totals.get("personalized", False)

    threshold = totals.get("threshold_used", 25)
    run_km = totals.get("run_distance_km", 0)
    run_pct = totals.get("run_percent", 0)
    hike_km = totals.get("hike_distance_km", 0)
    hike_pct = totals.get("hike_percent", 0)

    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📊 БЕГ + ШАГ (порог {threshold:.0f}%):",
        f"  🏃 {run_km:.1f}км ({run_pct:.0f}%) | 🚶 {hike_km:.1f}км ({hike_pct:.0f}%)",
        "",
        "  Базовые:",
    ]

    # Базовые комбинации
    combinations = [
        ("Strava + Tobler", "run_hike_strava_tobler"),
        ("Strava + Naismith", "run_hike_strava_naismith"),
        ("Minetti + Tobler", "run_hike_minetti_tobler"),
        ("Minetti + Naismith", "run_hike_minetti_naismith"),
        ("S+M + Tobler", "run_hike_strava_minetti_tobler"),
        ("S+M + Naismith", "run_hike_strava_minetti_naismith"),
    ]

    for label, key in combinations:
        time_str = _format_time_with_fatigue(
            totals.get(key, 0),
            totals.get(f"{key}_fatigue", 0) if fatigue else 0,
        )
        lines.append(f"    {label:18} {time_str}")

    # Персонализированные комбинации
    if personalized:
        lines.extend([
            "",
            "  🎯 Персональные:",
        ])
        pers_combinations = [
            ("Pers + Tobler", "run_hike_personalized_tobler"),
            ("Pers + Naismith", "run_hike_personalized_naismith"),
        ]

        # Добавляем Pers + Pers только если есть hike профиль
        if totals.get("hike_activities_used", 0) > 0:
            pers_combinations.append(
                ("Pers + Pers", "run_hike_personalized_personalized")
            )

        for label, key in pers_combinations:
            time_str = _format_time_with_fatigue(
                totals.get(key, 0),
                totals.get(f"{key}_fatigue", 0) if fatigue else 0,
            )
            lines.append(f"    {label:18} {time_str}")

    return lines


def _format_footer(result: dict) -> List[str]:
    """Подвал с метаинформацией."""
    totals = result.get("totals", {})
    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if totals.get("fatigue_enabled"):
        threshold = totals.get("fatigue_threshold_hours", 2)
        lines.append(f"😓 Усталость включена (после {threshold:.0f}ч)")

    if totals.get("personalized"):
        run_acts = totals.get("run_activities_used", 0)
        hike_acts = totals.get("hike_activities_used", 0)
        lines.append(f"👤 На основе {run_acts} run + {hike_acts} hike активностей")

    return lines


def format_segments(result: dict) -> str:
    """Форматирует ВСЕ сегменты в quote блок."""
    segments = result.get("segments", [])

    lines = [f"📊 СЕГМЕНТЫ ({len(segments)}):"]
    lines.append("")

    for seg in segments:
        num = seg.get("segment_number", 0)
        start_km = seg.get("start_km", 0)
        end_km = seg.get("end_km", 0)
        gradient = seg.get("gradient_percent", 0)
        movement = seg.get("movement", {})
        mode = movement.get("mode", "run")

        # Emoji по режиму
        emoji = "🚶" if mode == "hike" else "🏃"

        # Время (primary метод)
        times = seg.get("times", {})
        if mode == "hike":
            time_hours = times.get("tobler", 0)
        else:
            time_hours = times.get("strava_gap", 0)
        time_min = int(time_hours * 60)

        # Форматирование с выравниванием
        line = (
            f"{num:2d}. {emoji} "
            f"{start_km:5.1f}-{end_km:5.1f}км | "
            f"{gradient:+4.0f}% | "
            f"{time_min:2d}м"
        )
        lines.append(line)

    # Оборачиваем в quote
    return "\n".join(f"> {line}" for line in lines)


def _format_time_with_fatigue(base_hours: float, fatigue_hours: float) -> str:
    """Форматирует время с добавкой усталости."""
    base_str = format_hours(base_hours)
    if fatigue_hours > 0.01:  # Порог для показа
        fatigue_min = int(fatigue_hours * 60)
        return f"{base_str} (+{fatigue_min}м)"
    return base_str


def format_pace(pace_min_km: float) -> str:
    """Форматирует темп в M:SS/км."""
    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/км"
```

### 5.3 Отправка двух сообщений

**Файл:** `bot/handlers/trail_run.py`

```python
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    # ... получение result ...

    # Сообщение 1: Результаты
    result_text = format_trail_run_result(result, gpx_name)
    await callback.message.answer(result_text, parse_mode="HTML")

    # Сообщение 2: Сегменты (в quote)
    segments_text = format_segments(result)
    await callback.message.answer(segments_text, parse_mode="HTML")
```

---

## Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `backend/app/features/trail_run/service.py` | ~10 строк (calculation_variant) |
| `bot/handlers/trail_run.py` | ~150 строк (рефакторинг форматирования) |

**Итого:** ~160 строк изменений

---

## Чеклист проверки

- [ ] `calculation_variant` корректно определяется (1/2/3.5)
- [ ] Заголовок показывает flat pace и вариант
- [ ] Все методы отформатированы с выравниванием
- [ ] Усталость показывается в скобках
- [ ] Персональные методы выделены эмодзи 🎯
- [ ] Сегменты в отдельном сообщении
- [ ] Все сегменты показываются (не ограничено)
- [ ] Quote форматирование работает в Telegram

---

## Итоговая структура проекта (после всех фаз)

```
backend/app/
├── features/
│   ├── trail_run/
│   │   ├── calculators/
│   │   │   ├── gap.py            # 3 режима GAP
│   │   │   ├── fatigue.py        # FatigueCalculator
│   │   │   ├── personalization.py # С fallback логикой
│   │   │   └── threshold.py      # HikeRunThreshold
│   │   └── service.py            # TrailRunService
│   │
│   └── hiking/
│       └── calculators/
│           ├── tobler.py
│           ├── naismith.py
│           └── personalization.py
│
├── shared/
│   └── constants.py              # DEFAULT_HIKE_THRESHOLD_PERCENT
│
└── schemas/
    └── prediction.py             # GAPModeEnum с 3 значениями

bot/
└── handlers/
    └── trail_run.py              # Рефакторенное форматирование
```

---

## Общий объём изменений по фазам

| Фаза | Строк | Файлов |
|------|-------|--------|
| 1 | ~120 | 5 |
| 2 | ~90 | 2 |
| 3 | ~150 | 4 |
| 4 | ~130 | 3 |
| 5 | ~160 | 2 |
| **Итого** | **~650** | **~10 уникальных** |
