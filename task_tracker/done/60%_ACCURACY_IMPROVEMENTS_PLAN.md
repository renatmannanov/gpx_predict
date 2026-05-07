# План улучшения точности предсказаний

**Создан:** 2026-01-17
**Обновлён:** 2026-01-22
**Статус:** Частично реализовано

## Обзор

Три направления улучшения:
1. **Градации градиента** — 7 категорий вместо 3 ✅ **РЕАЛИЗОВАНО**
2. **Fatigue factor** — учёт усталости на длинных маршрутах ✅ **РЕАЛИЗОВАНО**
3. **Парсинг чужих активностей** — для расширения датасета

---

## 1. Градации градиента (7 категорий) ✅ DONE

**Реализовано:** 2026-01-22
**Файлы:**
- `backend/app/models/user_profile.py` — добавлены 7 полей для каждой категории
- `backend/app/services/user_profile.py` — классификация splits по 7 категориям
- `backend/app/services/calculators/personalization.py` — флаг `use_extended_gradients`
- `backend/app/api/v1/routes/predict.py` — параметр `use_extended_gradients` в API

### 1.1 Текущее состояние

Сейчас в `PersonalizationService._get_pace_for_gradient()`:
```python
if gradient > 3%:    → uphill_pace
elif gradient < -3%: → downhill_pace
else:                → flat_pace
```

**Проблема:** Подъём 5% и подъём 25% — это совершенно разные скорости.

### 1.2 Научные данные (Tobler's Hiking Function)

| Градиент | Скорость (км/ч) | % от flat (5 км/ч) |
|----------|-----------------|---------------------|
| -20% | 3.54 | 70.8% |
| -15% | 4.20 | 84.0% |
| -10% | 4.88 | 97.6% |
| -5% | 6.00 | **120%** (оптимум) |
| 0% | 5.00 | 100% |
| +5% | 4.20 | 84.0% |
| +10% | 3.54 | 70.8% |
| +15% | 2.98 | 59.6% |
| +20% | 2.51 | 50.2% |
| +25% | 2.11 | 42.2% |
| +30% | 1.78 | 35.6% |

**Источник:** Tobler W. (1993), основано на данных швейцарской армии (Imhof, 1950)

### 1.3 Предлагаемые 7 категорий

| Категория | Градиент | Ожидаемый мультипликатор |
|-----------|----------|--------------------------|
| `steep_downhill` | < -15% | 0.70-0.84 (медленнее из-за торможения) |
| `moderate_downhill` | -15% to -8% | 0.90-1.00 |
| `gentle_downhill` | -8% to -3% | 1.00-1.20 (быстрее flat!) |
| `flat` | -3% to +3% | 1.00 |
| `gentle_uphill` | +3% to +8% | 0.70-0.90 |
| `moderate_uphill` | +8% to +15% | 0.50-0.70 |
| `steep_uphill` | > +15% | 0.36-0.50 |

### 1.4 Изменения в коде

#### A) Модель `UserPerformanceProfile`

```python
# Новые поля (nullable для обратной совместимости)
avg_steep_downhill_pace_min_km = Column(Float, nullable=True)
avg_moderate_downhill_pace_min_km = Column(Float, nullable=True)
avg_gentle_downhill_pace_min_km = Column(Float, nullable=True)
avg_flat_pace_min_km = Column(Float, nullable=True)  # уже есть
avg_gentle_uphill_pace_min_km = Column(Float, nullable=True)
avg_moderate_uphill_pace_min_km = Column(Float, nullable=True)
avg_steep_uphill_pace_min_km = Column(Float, nullable=True)
```

#### B) `UserProfileService.calculate_profile_with_splits()`

```python
# Новые границы
GRADIENT_THRESHOLDS = {
    'steep_downhill': (-100, -15),
    'moderate_downhill': (-15, -8),
    'gentle_downhill': (-8, -3),
    'flat': (-3, 3),
    'gentle_uphill': (3, 8),
    'moderate_uphill': (8, 15),
    'steep_uphill': (15, 100),
}
```

#### C) `PersonalizationService._get_pace_for_gradient()`

```python
def _get_pace_for_gradient(self, gradient_percent: float) -> float:
    if not self.use_extended_gradients:
        # Fallback к 3 категориям
        return self._get_pace_simple(gradient_percent)

    # 7 категорий
    if gradient_percent < -15:
        return self.profile.avg_steep_downhill_pace_min_km or self._fallback(...)
    elif gradient_percent < -8:
        return self.profile.avg_moderate_downhill_pace_min_km or self._fallback(...)
    # ... и т.д.
```

### 1.5 Флаг включения/выключения

```python
class PersonalizationService:
    def __init__(self, profile, use_extended_gradients: bool = False):
        self.use_extended_gradients = use_extended_gradients
```

**API:** Добавить параметр `use_extended_gradients` в `/predict/compare`

---

## 2. Fatigue Factor (учёт усталости) ✅ DONE

**Реализовано:** 2026-01-22
**Файлы:**
- `backend/app/services/calculators/fatigue.py` — FatigueService с per-segment расчётом
- `backend/app/services/calculators/comparison.py` — интеграция fatigue в сравнение
- `backend/app/api/v1/routes/predict.py` — параметр `apply_fatigue` в API

**Валидация:** На TalgarTrail25 Naismith+fatigue показал 8:28, реальное время друзей 8:30 (ошибка -0.4%)

### 2.1 Научные данные

| Параметр | Значение | Источник |
|----------|----------|----------|
| Порог усталости | 3-4 часа | Tranter's corrections |
| Замедление после порога | 3-5% в час | Эмпирические данные марафонов |
| Riegel exponent | 1.06 | Riegel (1981) |
| Марафонское замедление | 9-14% (2-я половина) | Frontiers in Psychology (2023) |

### 2.2 Модель с экспонентой

```python
def fatigue_multiplier(hours_elapsed: float) -> float:
    """
    Рассчитывает коэффициент замедления из-за усталости.

    После 3 часов: нелинейное замедление.
    - 5 часов → 1.08 (+8%)
    - 7 часов → 1.20 (+20%)
    - 10 часов → 1.46 (+46%)
    """
    FATIGUE_THRESHOLD_HOURS = 3.0

    if hours_elapsed <= FATIGUE_THRESHOLD_HOURS:
        return 1.0

    extra = hours_elapsed - FATIGUE_THRESHOLD_HOURS
    return 1 + (0.03 * extra) + (0.005 * extra ** 2)
```

### 2.3 Примеры расчёта

| Время похода | Множитель | Эффект |
|--------------|-----------|--------|
| 3 часа | 1.00 | без изменений |
| 4 часа | 1.035 | +3.5% |
| 5 часов | 1.08 | +8% |
| 6 часов | 1.135 | +13.5% |
| 7 часов | 1.20 | +20% |
| 8 часов | 1.275 | +27.5% |
| 10 часов | 1.46 | +46% |

### 2.4 Интеграция в расчёт

**Вариант A: Post-processing**
```python
base_time = calculate_route_time(segments)
fatigue_mult = fatigue_multiplier(base_time)
adjusted_time = base_time * fatigue_mult
```

**Вариант B: Per-segment (более точный)**
```python
cumulative_time = 0
for segment in segments:
    segment_time = calculate_segment_time(segment)
    fatigue_mult = fatigue_multiplier(cumulative_time + segment_time / 2)
    adjusted_segment_time = segment_time * fatigue_mult
    cumulative_time += adjusted_segment_time
```

### 2.5 Флаг включения/выключения

```python
class FatigueService:
    def __init__(self, enabled: bool = False, threshold_hours: float = 3.0):
        self.enabled = enabled
        self.threshold_hours = threshold_hours
```

**API:** Добавить параметр `apply_fatigue` в `/predict/compare`

---

## 3. Парсинг чужих активностей (анонимизированный датасет)

### 3.1 Проблема

Strava API **не позволяет** получать активности других пользователей по их athlete_id.

### 3.2 Решение: Парсинг публичных URL

Публичные активности доступны по URL:
```
https://www.strava.com/activities/{activity_id}
```

**Что можно извлечь (без авторизации):**
- Общая дистанция
- Время
- Набор/сброс высоты
- Splits (если публичные)
- Тип активности

**Что НЕ доступно:**
- GPS координаты
- Heartrate данные
- Имя атлета (можно анонимизировать)

### 3.3 Формат анонимизированных данных

```python
@dataclass
class AnonymousActivityData:
    anonymous_id: str  # "user_1_activity_3"
    activity_type: str  # "Hike"
    distance_m: float
    moving_time_s: int
    elevation_gain_m: float
    elevation_loss_m: float
    splits: list[AnonymousSplit]  # если доступны

@dataclass
class AnonymousSplit:
    split_number: int
    distance_m: float
    moving_time_s: int
    elevation_diff_m: float
    pace_min_km: float
    gradient_percent: float
```

### 3.4 Использование

1. Ты даёшь мне URL активностей
2. Я парсю публичные данные
3. Сохраняем как "Пользователь 1", "Пользователь 2"
4. Используем для валидации модели и расширения датасета

---

## 4. Синхронизация твоих Hike активностей

### 4.1 Текущее состояние

В `UserProfileService.HIKING_ACTIVITY_TYPES`:
```python
HIKING_ACTIVITY_TYPES = ["Hike", "Walk"]
```

Синхронизация уже фильтрует по этим типам.

### 4.2 Как запустить полную синхронизацию

```bash
# 1. Через API
POST /api/v1/strava/sync/{telegram_id}

# 2. Затем синхронизировать splits
POST /api/v1/strava/sync-splits/{telegram_id}

# 3. Пересчитать профиль
POST /api/v1/profile/{telegram_id}/calculate
```

После этого все 10 Hike активностей (1 текущая + 9 новых) будут в профиле.

---

## 5. План реализации

### Фаза 1: Градации градиента (7 категорий) ✅ DONE

| # | Задача | Файлы | Статус |
|---|--------|-------|--------|
| 1.1 | Добавить поля в модель | `models/user_profile.py` | ✅ |
| 1.2 | Миграция БД | `alembic/versions/` | ✅ |
| 1.3 | Обновить `calculate_profile_with_splits()` | `services/user_profile.py` | ✅ |
| 1.4 | Обновить `PersonalizationService` с флагом | `calculators/personalization.py` | ✅ |
| 1.5 | Добавить параметр в API | `routes/predict.py` | ✅ |
| 1.6 | Тесты | `tests/` | ⏳ Частично |

### Фаза 2: Fatigue Factor ✅ DONE

| # | Задача | Файлы | Статус |
|---|--------|-------|--------|
| 2.1 | Создать `FatigueService` | `calculators/fatigue.py` | ✅ |
| 2.2 | Интегрировать в `ComparisonService` | `calculators/comparison.py` | ✅ |
| 2.3 | Добавить параметр в API | `routes/predict.py` | ✅ |
| 2.4 | Тесты | `tests/` | ⏳ Частично |

### Фаза 3: Данные ⏳ В ПРОЦЕССЕ

| # | Задача | Статус |
|---|--------|--------|
| 3.1 | Синхронизировать Hike/Walk активностей | ✅ 14 активностей |
| 3.2 | Синхронизировать splits | ✅ Все splits загружены |
| 3.3 | Валидировать модель на TalgarTrail25 | ✅ См. PREDICTION_TUNING_INSIGHTS.md |
| 3.4 | Создать скрипт парсинга публичных активностей | ⏳ Не начато |
| 3.5 | Собрать анонимизированный датасет | ⏳ Не начато |

### Фаза 4: Тонкая настройка (NEW)

На основе валидации выявлены улучшения — см. `docs/todo/PREDICTION_TUNING_INSIGHTS.md`:

| # | Задача | Приоритет | Статус |
|---|--------|-----------|--------|
| 4.1 | Gradient-aware fatigue multiplier | High | ⏳ |
| 4.2 | Skip first 1-2 km in profile (GPS warmup) | Medium | ⏳ |
| 4.3 | Confidence intervals for low-data categories | Medium | ⏳ |
| 4.4 | Altitude adjustment factor | Medium | ⏳ |
| 4.5 | Activity-length weighting | Low | ⏳ |
| 4.6 | Running prediction model | Future | ⏳ |

---

## 6. Решения и результаты

1. **Градации:** 7 категорий сразу ✅ **РЕАЛИЗОВАНО**
2. **Fatigue:** Per-segment (более точный) ✅ **РЕАЛИЗОВАНО**
3. **Порядок:** Градации → Fatigue → Данные ✅ **ВЫПОЛНЕНО**

### Результаты валидации на TalgarTrail25

| Метод | Прогноз | Факт | Ошибка |
|-------|---------|------|--------|
| Naismith | 7:52 | 8:05 | -2.7% |
| Naismith + fatigue | 8:28 | 8:30 | **-0.4%** |
| Tobler | 6:24 | ~6:30 | ~-1.5% |
| Personalized | 5:13 | 5:28 | -4.6% |
| Personalized + fatigue | 5:18 | 5:28 | -3.0% |

**Вывод:** Hiking predictions работают с точностью 3-5%

---

## Источники

### Градиент и скорость
- Tobler W. (1993) "Three presentations on geographical analysis and modeling"
- Wikipedia: [Tobler's Hiking Function](https://en.wikipedia.org/wiki/Tobler's_hiking_function)
- Imhof E. (1950) "Geländedarstellung"
- PMC: [Improved prediction of hiking speeds (2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10727444/)

### Усталость
- Riegel P. (1981) "Athletic Records and Human Endurance"
- Tranter P. "Tranter's Corrections for Naismith's Rule"
- Frontiers: [Pacing differences in marathon runners (2023)](https://www.frontiersin.org/articles/10.3389/fpsyg.2023.1273451)
- TrainingPeaks: [TSS Documentation](https://help.trainingpeaks.com/hc/en-us/articles/204071744)

### Strava API
- [Strava API Reference](https://developers.strava.com/docs/reference/)
- [API Agreement Updates (Nov 2024)](https://press.strava.com/articles/updates-to-stravas-api-agreement)
