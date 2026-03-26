# План реализации предсказания времени для трейлраннеров

**Дата создания:** 2026-01-23
**Последнее обновление:** 2026-01-23
**Статус:** Разбит на части, готов к реализации

---

## Обзор

Этот план разбит на **3 части** для удобства работы и контроля контекста:

| Часть | Содержание | Файл | Статус |
|-------|------------|------|--------|
| **Part 1** | Фаза 0 (рефакторинг) + Фаза 1 (GAP Calculator) | [TRAIL_RUNNING_PART1.md](./TRAIL_RUNNING_PART1.md) | 📋 Ready |
| **Part 2** | Фазы 2-4 (threshold, персонализация, усталость) | [TRAIL_RUNNING_PART2.md](./TRAIL_RUNNING_PART2.md) | 📋 Ready |
| **Part 3** | API, тестирование, документация | [TRAIL_RUNNING_PART3.md](./TRAIL_RUNNING_PART3.md) | 📋 Ready |

---

## Ключевые решения (обсуждено 2026-01-23)

### 1. Структура файлов персонализации

**Решение:** Отдельные файлы в `calculators/` (не директория)

```
calculators/
├── personalization_base.py     # BasePersonalizationService
├── personalization.py          # HikePersonalizationService (+ alias)
└── personalization_run.py      # RunPersonalizationService
```

### 2. GAP модель

**Решение:** Два режима на выбор

- `strava_gap` — чистый Strava (lookup table, рекомендуется)
- `minetti_gap` — гибрид Minetti (подъёмы) + Strava (спуски)

### 3. API endpoint

**Решение:** Расширить существующий `/predict/compare`

```python
POST /predict/compare
{
    "activity_type": "hike" | "trail_run",
    ...
}
```

### 4. Модель данных профилей

**Решение:** Разделить на две таблицы

```
users
├── user_hike_profiles (1:1)
└── user_run_profiles (1:1)
```

### 5. Дефолтные значения

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| Walk threshold | **25%** | Консервативно для большинства (элита: 30%) |
| Fatigue threshold (run) | **2.0 часа** | vs 3.0 для hiking |
| GAP mode | `strava_gap` | Эмпирические данные 240k атлетов |

---

## Порядок реализации

```
Part 1 (Фазы 0-1)
    │
    ├── Рефакторинг PersonalizationService
    │   ├── personalization_base.py
    │   ├── personalization.py (HikePersonalizationService)
    │   └── Тесты: обратная совместимость
    │
    └── GAP Calculator
        ├── trail_run/gap_calculator.py
        ├── Strava mode + Minetti mode
        └── Тесты: оба режима
    │
    ▼
Part 2 (Фазы 2-4)
    │
    ├── Hike/Run Threshold
    │   ├── trail_run/hike_run_threshold.py
    │   └── Тесты: статический + динамический
    │
    ├── Run Персонализация
    │   ├── Миграция: split user_profiles
    │   ├── models/user_run_profile.py
    │   ├── personalization_run.py
    │   └── Расширение strava_sync.py
    │
    └── Runner Fatigue
        ├── trail_run/runner_fatigue.py
        └── Тесты: ультра-дистанции
    │
    ▼
Part 3 (API + Docs)
    │
    ├── API
    │   ├── Расширение /predict/compare
    │   ├── TrailRunService оркестратор
    │   └── Интеграционные тесты
    │
    ├── Документация
    │   ├── ARCHITECTURE.md
    │   ├── ARCHITECTURE_CALCULATIONS.md
    │   └── CODE_REVIEW.md
    │
    └── Валидация
        └── Тесты на реальных GPX
```

---

## Научные источники

1. [Minetti et al. (2002)](https://pubmed.ncbi.nlm.nih.gov/12183501/) — Energy cost at extreme slopes
2. [Strava GAP (2017)](https://medium.com/strava-engineering/an-improved-gap-model-8b07ae8886c3) — Improved GAP model
3. [Fellrnr](https://fellrnr.com/wiki/Grade_Adjusted_Pace) — GAP formulas comparison
4. [PickleTech/COROS](https://pickletech.eu/blog-gap/) — Kilian Jornet GAP analysis
5. [UTMB Pacing Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7578994/) — Ultra-trail fatigue
6. [Colorado Boulder](https://www.runnersworld.com/trail-running/a37134334/power-hiking-walking-uphill-while-trail-running/) — Walk vs Run threshold

---

## Быстрый старт

Для начала работы:

1. Прочитать [Part 1](./TRAIL_RUNNING_PART1.md)
2. Выполнить чеклист Part 1
3. Протестировать
4. Перейти к Part 2

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2026-01-23 | Создан начальный план |
| 2026-01-23 | Обсуждение, принятие решений |
| 2026-01-23 | Разбит на 3 части |
