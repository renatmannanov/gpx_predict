# Code Review: GPX Predictor

**Дата:** 2025-01-17
**Обновлено:** 2026-01-17
**Версия:** 2.0

## Оглавление
1. [Критические проблемы](#1-критические-проблемы)
2. [Дублирование кода](#2-дублирование-кода)
3. [Архитектурные проблемы](#3-архитектурные-проблемы)
4. [Что сделано хорошо](#4-что-сделано-хорошо)
5. [Рекомендации по улучшению](#5-рекомендации-по-улучшению)
6. [План действий](#6-план-действий)

---

## 1. Критические проблемы

### 1.1 ~~Неверная логика персонализации~~ ✅ ИСПРАВЛЕНО

**Статус:** ИСПРАВЛЕНО в версии 2.0

**Что было:**
- `_calculate_personalized_time()` использовал "угаданные" ratios вместо реальных сегментов
- Ratios применялись к ПОЛНОЙ дистанции вместо реальных сегментов

**Что сделано:**
- Создан `PersonalizationService` в `calculators/personalization.py`
- Использует реальные `MacroSegment` из `RouteSegmenter`
- Интегрирован в `ComparisonService.compare_route()`
- Показывает `tobler_personalized` и `naismith_personalized` в сравнении

---

### 1.2 ~~Баг в классификации сегментов~~ ✅ ИСПРАВЛЕНО

**Статус:** ИСПРАВЛЕНО в версии 2.0

**Что было:**
- `RouteSegmenter._create_segment()` использовал переданный `direction` вместо реального градиента
- Сегмент с gradient=+2.1% мог быть помечен как "descent"

**Что сделано:**
- `_create_segment()` теперь определяет тип по фактическому `actual_gradient`
- Все сегменты корректно классифицируются (ascent/descent/flat)

---

### 1.3 Несогласованность типов Session (sync vs async)

**Проблема:** Смешение синхронных и асинхронных сессий SQLAlchemy.

| Файл | Тип сессии |
|------|------------|
| `prediction.py` | `Session` (sync) |
| `user_profile.py` | `AsyncSession` |
| `strava.py` | `AsyncSession` |
| `routes/strava.py` | `Session` (sync) |
| `routes/profile.py` | Mixed (async для calculate, sync для get) |

**Статус:** ЧАСТИЧНО ИСПРАВЛЕНО
- `routes/profile.py` теперь использует `AsyncSession` для `/profile/{id}/calculate` и `/strava/sync-splits/`
- `StravaSyncService` теперь поддерживает оба типа сессий через `_is_async` флаг

**Оставшееся:** `prediction.py` использует sync Session, но это работает.

---

## 2. Дублирование кода

### 2.1 Token Refresh — ИСПРАВЛЕНО ✅

**Статус:** Использовать только `StravaClient.get_valid_token()`.

---

### 2.2 Token Exchange — ИСПРАВЛЕНО ✅

**Статус:** Использовать только `StravaClient.exchange_code()`.

---

### 2.3 Haversine — ИСПРАВЛЕНО ✅

**Статус:** Вынесено в `utils/geo.py` с функцией `haversine()`.

---

### 2.4 Elevation Smoothing — ИСПРАВЛЕНО ✅

**Статус:** Вынесено в `utils/elevation.py` с функцией `smooth_elevations()`.

---

### 2.5 Дублирование Enum'ов — ИСПРАВЛЕНО ✅

**Статус:** Оставлено только в `schemas/prediction.py`, импортируется в naismith.

---

## 3. Архитектурные проблемы

### 3.1 Два разных Segmenter'а — ДОКУМЕНТИРОВАНО ✅

**Статус:** ДОКУМЕНТИРОВАНО — это не баг, а фича.

| Сегментер | Назначение | Где используется |
|-----------|------------|------------------|
| `GPXParserService` | Равномерные сегменты ~1км для UI | `_calculate_segments()` → API |
| `RouteSegmenter` | По направлению (подъём/спуск) | `ComparisonService` → Tobler/Naismith |

См. подробности в `docs/ARCHITECTURE.md` секция 5.6.

---

### 3.2 Смешение ответственностей в PredictionService

`prediction.py` делает слишком много:
- Загрузка GPX из БД
- Расчёт sun times
- Создание HikerProfile
- Базовый расчёт времени
- Применение multipliers
- Rest time, lunch time
- Генерация warnings
- Сегментация маршрута

**Статус:** TODO — рефакторинг желателен, но не критичен.

---

### 3.3 ~~Нет валидации профиля перед использованием~~ ✅ ИСПРАВЛЕНО

**Статус:** ИСПРАВЛЕНО

`PersonalizationService.is_profile_valid()` проверяет:
- Профиль не None
- `avg_flat_pace_min_km` не None
- `total_activities_analyzed >= MIN_ACTIVITIES_FOR_PROFILE`

---

## 4. Что сделано хорошо

### 4.1 Чёткое разделение Strava data policy ✅

### 4.2 Rate limiter с двумя окнами ✅

### 4.3 Langmuir corrections в calculator ✅

### 4.4 Разделение splits и activities ✅

### 4.5 Calculators как Strategy pattern ✅

### 4.6 Четыре метода расчёта ✅

- `tobler` — Tobler's Hiking Function (1993)
- `naismith` — Naismith + Langmuir corrections
- `tobler_personalized` — персонализация на основе Strava ✅ NEW
- `naismith_personalized` — персонализация на основе Strava ✅ NEW

### 4.7 PersonalizationService ✅ NEW

Правильная реализация персонализации:
- Использует реальные MacroSegment
- Применяет pace к фактической дистанции каждого сегмента
- Интегрирован в ComparisonService

---

## 5. Рекомендации по улучшению

### Приоритет 1: Улучшение точности

1. **Градации градиента** — 5 категорий вместо 3 (flat, moderate_up, steep_up, moderate_down, steep_down)
2. **Altitude correction** — замедление на высоте >2500м
3. **Fatigue factor** — замедление после 4-6 часов похода

### Приоритет 2: Архитектура

1. Унифицировать Session типы полностью
2. Разбить PredictionService на меньшие части

### Приоритет 3: UX

1. Показывать доверительный интервал (±X минут)
2. Рекомендации по подготовке на основе профиля

---

## 6. План действий

| # | Задача | Приоритет | Статус |
|---|--------|-----------|--------|
| 1 | Исправить персонализацию | High | ✅ DONE (PersonalizationService) |
| 2 | Исправить классификацию сегментов | High | ✅ DONE (RouteSegmenter) |
| 3 | Вынести общие утилиты (haversine, smoothing) | Medium | ✅ DONE |
| 4 | Унифицировать token management | Medium | ✅ DONE |
| 5 | Унифицировать Session типы | Medium | PARTIAL |
| 6 | Убрать дублирование Enum'ов | Low | ✅ DONE |
| 7 | Валидация профиля | Low | ✅ DONE |
| 8 | Документировать два сегментера | Low | ✅ DONE |
| 9 | Градации градиента (5 категорий) | Medium | TODO |
| 10 | Altitude correction | Medium | TODO |
| 11 | Fatigue factor | Low | TODO |

---

## Итоговая оценка

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| Структура проекта | 9/10 | Хорошее разделение + utils слой + PersonalizationService |
| Дублирование | 9/10 | Исправлено: haversine, token management, enums |
| Корректность расчётов | 9/10 | 4 метода работают, персонализация исправлена |
| Расширяемость | 9/10 | Calculator pattern + PersonalizationService + dual session |
| Документация | 9/10 | ARCHITECTURE.md + ARCHITECTURE_CALCULATIONS.md обновлены |
| Безопасность | 7/10 | CSRF state, rate limiting есть |

**Общая оценка: 8.7/10** — значительное улучшение после рефакторинга персонализации.

---

## История изменений

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2025-01-17 | 1.0 | Первоначальный ревью |
| 2025-01-17 | 1.1 | StravaSyncService поддержка async, документация сегментеров |
| 2026-01-17 | 2.0 | PersonalizationService, исправление RouteSegmenter, обновление документации |
