# Hiking Profile: 11 категорий + IQR + Effort Levels (минимальный подход)

**Дата:** 2026-02-14
**Ветка:** `feature/calibration-tools` (текущая)
**Подход:** Минимальный — без рефакторинга архитектуры, без создания HikingService

## Контекст

Для trail running реализовано:
- IQR фильтрация аномалий per category
- 11 категорий градиента вместо 7
- Перцентили P25/P50/P75
- Effort Levels (Fast/Moderate/Easy)
- Всё отображается в боте и API

Для hiking ничего из этого нет. Нужно перенести, минимальным способом.

## Фазы

| # | Фаза | Файл | ~Строк кода |
|---|-------|------|-------------|
| 1 | Модель + миграция | `phase_1_model.md` | ~150 |
| 2 | Расчёт профиля (IQR + 11-cat + percentiles) | `phase_2_profile_calc.md` | ~200 |
| 3 | Персонализация + effort levels в comparison | `phase_3_personalization.md` | ~250 |
| 4 | API + бот | `phase_4_api_bot.md` | ~150 |

## Что переиспользуется (уже есть)

- `filter_outliers_iqr()` — `services/user_profile.py`
- `calculate_percentiles()` — `services/user_profile.py`
- `EffortLevel` enum — `shared/calculator_types.py`
- `classify_gradient()` (11-cat) — `shared/gradients.py`
- `GRADIENT_THRESHOLDS` — `shared/gradients.py`
- `LEGACY_CATEGORY_MAPPING` — `shared/gradients.py`

## Порядок реализации

1. [ ] Фаза 1 — Модель + миграция
2. [ ] Фаза 2 — Расчёт профиля
3. [ ] Фаза 3 — Персонализация + effort в comparison
4. [ ] Фаза 4 — API + бот

## Бэклог (на потом)

- Полноценный `HikingService` по образцу `TrailRunService` → `docs/task_tracker/backlog/backlog_hiking_service_refactor.md`
