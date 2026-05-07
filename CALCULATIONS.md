# Расчёты времени прохождения маршрута

**Последнее обновление:** 2026-02-02 (sample_count fix + gradient profile breakdown)

---

## Оглавление

1. [Hiking](#hiking)
2. [Trail Running](#trail-running)
3. [Формулы](#формулы)
4. [7 категорий градиента](#7-категорий-градиента)
5. [Файлы](#файлы)

---

## Hiking

### Вывод пользователю

```
tobler: 6ч 31мин
naismith: 8ч 3мин
🎯 tobler (ваш темп): 5ч 33мин
🎯 naismith (ваш темп): 5ч 33мин
```

### Как считается

| Метод | Логика |
|-------|--------|
| `tobler` | Формула Tobler, стандартные параметры |
| `naismith` | Формула Naismith, стандартные параметры |
| `tobler (ваш темп)` | Lookup из профиля + fallback на масштабированный Tobler |
| `naismith (ваш темп)` | Lookup из профиля + fallback на масштабированный Naismith |

**Примечание:** Персонализированные методы (`ваш темп`) появляются только если у пользователя есть Strava профиль с hiking данными.

### Варианты расчёта

| Вариант | Название | Логика | Когда |
|---------|----------|--------|-------|
| **1** | Базовый | Чистая формула (Tobler или Naismith) | Нет профиля |
| **2** | Масштабированный | Формула × (user_flat / standard_flat) | Есть flat_pace, нет данных для категории |
| **3** | Персонализированный | Lookup темпа из профиля + fallback на Вариант 2 | Есть профиль с данными |

---

## Trail Running

### Архитектура расчётов (v3)

Trail Running использует многоуровневую систему расчётов:

```
┌─────────────────────────────────────────────────────────┐
│  Блок 1: ВСЁ БЕГОМ (all_run_*)                          │
│  ─────────────────────────────────────────────          │
│  3 GAP метода считают ВЕСЬ маршрут как бег              │
│  • all_run_strava                                        │
│  • all_run_minetti                                       │
│  • all_run_strava_minetti                                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Блок 2: БЕГ + ШАГ (run_hike_*)                         │
│  ─────────────────────────────────────────────          │
│  Сегменты с градиентом >15% считаются как hiking        │
│  6 комбинаций = 3 GAP × 2 Hiking методов:               │
│  • run_hike_strava_tobler                                │
│  • run_hike_strava_naismith                              │
│  • run_hike_minetti_tobler                               │
│  • run_hike_minetti_naismith                             │
│  • run_hike_strava_minetti_tobler                        │
│  • run_hike_strava_minetti_naismith                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Dual Results (API)                                      │
│  ─────────────────────────────────────────────          │
│  Если есть Strava профиль — два набора totals:          │
│  • totals_strava — расчёт с Strava темпом               │
│  • totals_manual — расчёт с выбранным темпом            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Блок 3: Персонализация (Phase 3)                       │
│  ─────────────────────────────────────────────          │
│  Если есть run_profile с данными:                       │
│  • all_run_personalized — весь маршрут персонализирован │
│  • run_hike_personalized_tobler — бег перс + шаг Tobler │
│  • run_hike_personalized_naismith — бег перс + шаг Nai  │
│  • run_profile — мета-информация о профиле              │
└─────────────────────────────────────────────────────────┘
```

### 3 базовых метода GAP

| Метод | Uphill | Downhill | Особенности |
|-------|--------|----------|-------------|
| **Strava GAP** | Strava | Strava | Эмпирическая таблица (240k атлетов) |
| **Minetti GAP** | Minetti | Minetti | Чистая научная формула |
| **Strava+Minetti** | Minetti | Strava | Гибрид: Minetti up + Strava down |

**Ключевое отличие v3:** Все 3 метода считают **весь маршрут** как бег, независимо от градиента. Это позволяет сравнивать методы напрямую.

### Переход на шаг (Phase 2)

Для сегментов с градиентом выше порога (по умолчанию **15%**, из `DEFAULT_HIKE_THRESHOLD_PERCENT`) используются hiking формулы:

```
Если gradient > threshold:
    время = Tobler или Naismith
Иначе:
    время = GAP (Strava/Minetti/Strava+Minetti)
```

**6 комбинаций "Бег + Шаг":**

| Комбинация | GAP метод (бег) | Hiking метод (шаг) |
|------------|-----------------|---------------------|
| `run_hike_strava_tobler` | Strava | Tobler |
| `run_hike_strava_naismith` | Strava | Naismith |
| `run_hike_minetti_tobler` | Minetti | Tobler |
| `run_hike_minetti_naismith` | Minetti | Naismith |
| `run_hike_strava_minetti_tobler` | Strava+Minetti | Tobler |
| `run_hike_strava_minetti_naismith` | Strava+Minetti | Naismith |

### Dual Results

Если у пользователя есть Strava профиль с `avg_flat_pace_min_km`, API делает **два расчёта**:

1. **totals_strava** — с темпом из Strava профиля
2. **totals_manual** — с темпом, выбранным/введённым пользователем

Это позволяет пользователю сравнить:
- Прогноз на основе его реальных данных (Strava)
- Прогноз на основе желаемого/целевого темпа

### Структура totals (полная)

```python
totals = {
    # ═══ Блок 1: Весь маршрут как бег ═══
    "all_run_strava": 3.75,           # часы
    "all_run_minetti": 3.87,
    "all_run_strava_minetti": 3.80,

    # ═══ Блок 2: Бег + Шаг (6 комбинаций) ═══
    "run_hike_strava_tobler": 3.95,
    "run_hike_strava_naismith": 4.02,
    "run_hike_minetti_tobler": 4.05,
    "run_hike_minetti_naismith": 4.12,
    "run_hike_strava_minetti_tobler": 4.00,
    "run_hike_strava_minetti_naismith": 4.07,

    # ═══ Hiking времена (весь маршрут) ═══
    "tobler": 5.50,
    "naismith": 6.20,

    # ═══ Статистика разбивки ═══
    "run_distance_km": 14.8,
    "hike_distance_km": 5.2,
    "run_percent": 74.0,
    "hike_percent": 26.0,
    "threshold_used": 15.0,  # DEFAULT_HIKE_THRESHOLD_PERCENT

    # ═══ Legacy ═══
    "combined": 4.10,  # primary с threshold + fatigue

    # ═══ Phase 3: Персонализация (если есть run_profile) ═══
    "all_run_personalized": 3.72,           # весь маршрут с персональным профилем
    "run_hike_personalized_tobler": 3.92,   # бег персонализирован + шаг Tobler
    "run_hike_personalized_naismith": 3.98, # бег персонализирован + шаг Naismith
    "run_profile": {                        # мета-информация о профиле
        "total_distance_km": 450,
        "total_activities": 32,
        "total_splits": 285,
        "categories_filled": 6,             # Только категории с ≥5 сэмплов!
        "categories_total": 7,
        "min_samples_threshold": 5,
        "gradient_profile": [               # Детальная разбивка
            {"category": "flat", "pace": 5.50, "samples": 180, "is_personal": True},
            # ... 7 категорий с pace, samples, is_personal
        ]
    },

    # ═══ Per-segment персонализация ═══
    "run_personalized": 3.65,   # только если run_profile valid
    "hike_personalized": 0.25,  # только если hike_profile valid
}
```

### Пример вывода в боте

```
🏃 Trail Run: Маршрут

📍 20.0 км | D+ 2000м | D- 2000м

━━━━━━━━━━━━━━━━━━━━━━━━

👤 НА ОСНОВЕ STRAVA (5:30/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP       3ч 38м
  Minetti GAP      3ч 44м
  Strava+Minetti   3ч 41м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 НА ОСНОВЕ ТВОЕГО ТЕМПА (6:00/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP       3ч 58м
  Minetti GAP      4ч 05м
  Strava+Minetti   4ч 01м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 БЕГ + ШАГ (порог 15%):
  🏃 14.8км (74%) | 🥾 5.2км (26%)

  Strava + Tobler    4ч 10м
  Strava + Naismith  4ч 15м
  Minetti + Tobler   4ч 18м
  Minetti + Naismith 4ч 22м
  S+M + Tobler       4ч 14м
  S+M + Naismith     4ч 18м
  🎯 Перс + Tobler   3ч 55м
  🎯 Перс + Naismith 3ч 58м

━━━━━━━━━━━━━━━━━━━━━━━━

📈 Персонализация: 450 км, 32 активностей, 285 сплитов, профиль 6 из 7

> 📊 Профиль по градиентам (✓ свой / GAP формула):
>
>   steep_up (+15%↑)       —   ( 0) GAP
>   moderate_up (+8-15%)  8.50 (12) ✓
>   gentle_up (+3-8%)     7.20 (45) ✓
>   flat (-3 to +3%)      5.50 (180) ✓
>   gentle_down (-3-8%)   5.00 (38) ✓
>   moderate_dn (-8-15%)  4.80 ( 8) ✓
>   steep_down (-15%↓)    5.20 ( 2) GAP
```

### UX: Strava статус

Бот показывает разные сообщения в зависимости от статуса Strava:

| Сценарий | Сообщение |
|----------|-----------|
| Есть run profile с темпом | "👤 Твой темп: 5:30/км (15 активностей)" |
| Strava подключена, но нет run profile | "⚠️ Strava подключена, но недостаточно беговых данных" |
| Strava не подключена | "⚠️ Strava не подключена — расчёт на основе выбранного темпа" |

---

## Формулы

### Tobler (Hiking)

```
Speed = 6 × exp(-3.5 × |gradient + 0.05|) км/ч
```

- Максимум 6 км/ч при -5% уклоне (лёгкий спуск)
- 5 км/ч на ровной местности
- Основана на данных швейцарской армии

### Naismith (Hiking)

```
Time = distance/5 + elevation_gain/600 часов

Langmuir corrections для спуска:
- Пологий (5-12°): -10 мин на 300м (быстрее)
- Крутой (>12°): +10 мин на 300м (медленнее)
```

### Strava GAP (Trail Running)

```
Pace = flat_pace × STRAVA_TABLE[gradient]
```

Lookup таблица на основе данных 240,000 атлетов Strava:

| Градиент | Коэффициент |
|----------|-------------|
| -30% | 1.15 |
| -9% | 0.88 (оптимум) |
| 0% | 1.00 |
| +10% | 1.38 |
| +20% | 2.15 |
| +30% | 3.30 |

### Minetti GAP (Trail Running)

```
Cost = 155.4i^5 - 30.4i^4 - 43.3i^3 + 46.3i^2 + 19.5i + 3.6
где i = gradient / 100

Pace = flat_pace × (Cost / 3.6)^0.75
```

Научная формула на основе метаболических измерений (Minetti et al., 2002).

### Сравнение GAP методов (6:00/km flat pace)

| Градиент | Strava | Minetti | Strava+Minetti |
|----------|--------|---------|----------------|
| -15% | 5:24 | ~5:06 | 5:24 |
| -9% | 5:17 | ~5:00 | 5:17 |
| 0% | 6:00 | 6:00 | 6:00 |
| +10% | 8:17 | ~8:06 | ~8:06 |
| +20% | 12:54 | ~11:30 | ~11:30 |
| +30% | 19:48 | ~15:00 | ~15:00 |

**Вывод:** Minetti более оптимистичен на подъёмах, Strava более реалистичен на спусках.

---

## Порог перехода на шаг (Threshold)

**Константа:** `shared/constants.py → DEFAULT_HIKE_THRESHOLD_PERCENT = 15.0`

**Логика:**
- По умолчанию: **15%** градиента
- Может быть персонализирован из Strava данных (детекция скачка темпа)
- Хранится в `user_run_profiles.walk_threshold_percent`

**Хранение в БД:**
- `NULL` → используется константа (автоматически обновляется при изменении)
- Число → персонализированный порог из данных пользователя

**Детекция из данных:**
- Требуется ≥10 uphill splits (gradient > 5%)
- Ищется максимальный скачок темпа (pace derivative)
- Clamp в диапазон [15%, 35%]

---

## 7 категорий градиента

| Категория | Диапазон |
|-----------|----------|
| steep_downhill | < -15% |
| moderate_downhill | -15% to -8% |
| gentle_downhill | -8% to -3% |
| flat | -3% to +3% |
| gentle_uphill | +3% to +8% |
| moderate_uphill | +8% to +15% |
| steep_uphill | > +15% |

---

## Персонализация и Fallback логика

### Когда используется персональный темп

Для каждой из 7 категорий градиента проверяется:
1. Есть ли `pace` для категории (не None)
2. Есть ли достаточно сэмплов: `sample_count >= MIN_SAMPLES_FOR_CATEGORY (5)`

Если оба условия выполнены → используется персональный темп из профиля.

### Когда используется GAP Fallback

Если хотя бы одно условие не выполнено → используется **Strava GAP** с базой `flat_pace` из профиля:

```python
# В RunPersonalizationService.__init__:
flat_pace = profile.avg_flat_pace_min_km  # например, 5.50 мин/км
self._gap_calculator = GAPCalculator(flat_pace, GAPMode.STRAVA)

# При расчёте сегмента с градиентом 15%:
result = self._gap_calculator.calculate(15)  # → 5.50 × 1.70 = 9.35 мин/км
```

### Пример

Профиль с данными:
```
flat:           5.50 мин/км (180 сэмплов) → ✓ персональный
gentle_uphill:  7.20 мин/км (45 сэмплов)  → ✓ персональный
moderate_uphill: 8.50 мин/км (3 сэмпла)   → GAP fallback (< 5 сэмплов)
steep_uphill:    —   (0 сэмплов)          → GAP fallback
```

Для сегмента с градиентом +12% (moderate_uphill):
- `sample_count = 3 < 5` → fallback
- `GAP: 5.50 × 1.50 = 8.25 мин/км` (вместо 8.50 из профиля)

### Константа

```python
# features/trail_run/calculators/personalization.py
MIN_SAMPLES_FOR_CATEGORY = 5
```

---

## Файлы

| Компонент | Файл |
|-----------|------|
| Tobler | `features/hiking/calculators/tobler.py` |
| Naismith | `features/hiking/calculators/naismith.py` |
| Hike Personalization | `features/hiking/calculators/personalization.py` |
| GAP Calculator (3 режима) | `features/trail_run/calculators/gap.py` |
| Run Personalization | `features/trail_run/calculators/personalization.py` |
| Trail Run Service | `features/trail_run/service.py` |
| Hike/Run Threshold | `features/trail_run/calculators/threshold.py` |
| Runner Fatigue | `features/trail_run/calculators/fatigue.py` |
| **Constants** | `shared/constants.py` (DEFAULT_HIKE_THRESHOLD_PERCENT) |
| API Route | `api/v1/routes/predict.py` |
| Bot Handler | `bot/handlers/trail_run.py` |
