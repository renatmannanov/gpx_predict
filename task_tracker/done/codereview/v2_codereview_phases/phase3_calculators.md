# Phase 3: Calculator Cleanup

> **Статус:** Не начато
> **Оценка:** ~150 строк изменений
> **Зависимости:** Phase 0c
> **Ветка:** `refactor/phase-3-calculators`
> **Цель:** Устранить дублирование, документировать калькуляторы

---

## Проблемы

1. **Дублирование `_tobler_speed()`:**
   - `features/hiking/calculators/tobler.py:81-95`
   - `features/hiking/calculators/personalization.py:135-149`
   - Идентичный код в двух местах

2. **Недостаточная документация калькуляторов**

---

## Задачи

### 3.1 Вынести tobler_speed в shared

Создать `backend/app/shared/formulas.py`:

```python
"""
Математические формулы для расчёта времени прохождения маршрутов.

Эти формулы используются разными калькуляторами.
"""
import math


def tobler_hiking_speed(gradient_decimal: float) -> float:
    """
    Calculate walking speed using Tobler's Hiking Function (1993).

    Formula: v = 6 * exp(-3.5 * |s + 0.05|)

    Args:
        gradient_decimal: Slope as decimal (0.10 = 10%, -0.05 = -5%)
                         Positive = uphill, Negative = downhill

    Returns:
        Speed in km/h

    Notes:
        - Maximum speed (6 km/h) at -5% gradient (slight downhill)
        - Speed decreases exponentially with steeper gradients
        - Works well for typical hiking terrain

    References:
        Tobler, W. (1993). Three Presentations on Geographical Analysis
        and Modeling. NCGIA Technical Report 93-1.
    """
    OPTIMAL_GRADIENT = -0.05  # Slight downhill is optimal
    MAX_SPEED_KMH = 6.0
    DECAY_RATE = 3.5

    exponent = -DECAY_RATE * abs(gradient_decimal - OPTIMAL_GRADIENT)
    return MAX_SPEED_KMH * math.exp(exponent)


def naismith_base_time(distance_km: float, elevation_gain_m: float) -> float:
    """
    Calculate base hiking time using Naismith's Rule (1892).

    Rule: 5 km/h + 1 hour per 600m of ascent

    Args:
        distance_km: Horizontal distance in kilometers
        elevation_gain_m: Total elevation gain in meters

    Returns:
        Time in hours

    Notes:
        - Does not account for descent
        - Use with corrections for real-world estimates
    """
    BASE_SPEED_KMH = 5.0
    METERS_PER_HOUR_ASCENT = 600.0

    horizontal_time = distance_km / BASE_SPEED_KMH
    ascent_time = elevation_gain_m / METERS_PER_HOUR_ASCENT

    return horizontal_time + ascent_time
```

### 3.2 Обновить ToblerCalculator

В `features/hiking/calculators/tobler.py`:

```python
from app.shared.formulas import tobler_hiking_speed

class ToblerCalculator(PaceCalculator):
    # ... existing code ...

    def _tobler_speed(self, gradient: float) -> float:
        """Delegate to shared formula."""
        return tobler_hiking_speed(gradient)
```

### 3.3 Обновить PersonalizationService

В `features/hiking/calculators/personalization.py`:

```python
from app.shared.formulas import tobler_hiking_speed

class HikePersonalizationService:
    # ... existing code ...

    def _estimate_pace_for_gradient(self, gradient: float) -> float:
        """Estimate pace using Tobler's function scaled by user's flat pace."""
        tobler_speed = tobler_hiking_speed(gradient)
        # ... rest of the method
```

### 3.4 Документировать калькуляторы

Создать/обновить README в каждом calculator модуле:

**`features/hiking/calculators/README.md`:**
```markdown
# Hiking Calculators

## Обзор

Три метода расчёта времени для пеших маршрутов:

| Метод | Класс | Когда использовать |
|-------|-------|-------------------|
| Tobler | ToblerCalculator | По умолчанию, горные маршруты |
| Naismith | NaismithCalculator | Альтернатива, классический метод |
| Personalized | HikePersonalizationService | Если есть Strava профиль |

## Tobler's Hiking Function

**Файл:** `tobler.py`
**Формула:** `v = 6 * exp(-3.5 * |s + 0.05|)`

- Максимальная скорость 6 км/ч при -5% уклона
- Экспоненциальное замедление на крутых участках
- Хорошо работает для горных маршрутов

## Naismith's Rule

**Файл:** `naismith.py`
**Формула:** 5 км/ч + 1 час на каждые 600м подъёма

- Классический метод (1892)
- С коррекциями Langmuir для спуска
- Хорош для плоских маршрутов

## Personalization

**Файл:** `personalization.py`
**Использует:** Профиль пользователя из Strava

- 7 категорий уклона
- Fallback на Tobler если нет данных
- Требует минимум 1 активность

## Fatigue

**Файл:** `fatigue.py`
**Эффект:** Замедление на длинных маршрутах

- Начинается после 3 часов (hiking)
- Линейный + квадратичный рост
```

**`features/trail_run/calculators/README.md`:**
```markdown
# Trail Run Calculators

## Обзор

| Метод | Класс | Когда использовать |
|-------|-------|-------------------|
| GAP Strava | GAPCalculator(STRAVA) | По умолчанию |
| GAP Minetti | GAPCalculator(MINETTI) | Научный метод |
| Threshold | HikeRunThresholdService | Авто-переключение бег/ходьба |
| Personalized | RunPersonalizationService | Если есть профиль |

## GAP (Grade Adjusted Pace)

**Файл:** `gap.py`

Два режима:
- **Strava:** Эмпирический (240k атлетов)
- **Minetti:** Научный (подъёмы) + Strava (спуски)

## Threshold

**Файл:** `threshold.py`

Определяет когда переходить с бега на ходьбу:
- Динамический: из данных пользователя
- Ручной: пользователь задаёт порог

## Fatigue

**Файл:** `fatigue.py`

Усиленная модель для бегунов:
- Начинается после 2 часов (vs 3 для hiking)
- Больший рост усталости
```

---

## Файлы для изменения

```
NEW:
backend/app/shared/formulas.py
backend/app/features/hiking/calculators/README.md
backend/app/features/trail_run/calculators/README.md

UPDATE:
backend/app/features/hiking/calculators/tobler.py (use shared formula)
backend/app/features/hiking/calculators/personalization.py (use shared formula)
backend/app/shared/__init__.py (export formulas)
```

---

## Критерии завершения

- [ ] `shared/formulas.py` создан с `tobler_hiking_speed()`
- [ ] Нет дублирования `_tobler_speed()`
- [ ] README.md есть в обоих calculator модулях
- [ ] Тесты калькуляторов проходят

---

## Проверка

```bash
cd backend

# Тесты калькуляторов
pytest tests/calculators/ -v

# Приложение
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 3 - calculator cleanup

- Create shared/formulas.py with tobler_hiking_speed()
- Remove duplicate _tobler_speed() implementations
- Add README.md for hiking and trail_run calculators

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-3-calculators
```

Перейти к Phase 5.

---

*Phase 3 — Calculator Cleanup*
