# Фаза 2: 11 категорий + JSON профиль + перцентили

**Сложность:** Средняя
**Эффект:** Высокий
**Зависимости:** Фаза 1 (IQR фильтрация)
**Оценка:** ~200-250 строк изменений (модель + расчёт + миграция + калькуляторы)

---

## Цель

Два изменения в одной фазе (одна миграция БД):

1. **JSON поля** вместо отдельных колонок — для расширяемости
2. **Перцентили P25/P50/P75** — основа для effort level (Фаза 3)

**Примечание:** 11 категорий и новый нейминг уже реализованы в `shared/gradients.py` (Фаза 0). Здесь мы добавляем хранение (JSON) и расчёт перцентилей.

---

## Примечание: 11 категорий уже в Фазе 0

`shared/gradients.py` с 11 категориями, `classify_gradient()`, `classify_gradient_legacy()` и `LEGACY_CATEGORY_MAPPING` уже создан в Фазе 0. Здесь используется как есть.

---

## Часть 2: JSON поля в модели профиля

### Проблема: "колоночный ад"

Текущий профиль — 7 полей `avg_*` + 7 полей `*_sample_count` = 14 колонок.
С 11 категориями + 3 перцентилями: 11 × (1 avg + 1 count + 2 percentile) = **44 колонки**.

### Решение: 2 JSON поля

Добавить в `UserRunProfile`:

```python
# Pace data per gradient category
gradient_paces = Column(JSON, nullable=True)

# Percentiles per gradient category (P25/P50/P75 after IQR filtering)
gradient_percentiles = Column(JSON, nullable=True)
```

### Формат gradient_paces

```json
{
    "down_23_over": {"avg": 18.50, "samples": 5},
    "down_23_17":   {"avg": 10.37, "samples": 13},
    "down_17_12":   {"avg": 8.77,  "samples": 21},
    "down_12_8":    {"avg": 7.96,  "samples": 42},
    "down_8_3":     {"avg": 7.06,  "samples": 86},
    "flat_3_3":     {"avg": 6.39,  "samples": 629},
    "up_3_8":       {"avg": 9.17,  "samples": 119},
    "up_8_12":      {"avg": 11.50, "samples": 60},
    "up_12_17":     {"avg": 14.20, "samples": 24},
    "up_17_23":     {"avg": 19.50, "samples": 34},
    "up_23_over":   {"avg": 28.50, "samples": 16}
}
```

### Формат gradient_percentiles

```json
{
    "down_23_over": {"p25": 12.50, "p50": 18.50, "p75": 24.00},
    "down_23_17":   {"p25": 8.20,  "p50": 10.37, "p75": 12.80},
    "down_17_12":   {"p25": 7.00,  "p50": 8.77,  "p75": 10.50},
    "down_12_8":    {"p25": 6.01,  "p50": 6.93,  "p75": 10.87},
    "down_8_3":     {"p25": 5.85,  "p50": 6.27,  "p75": 8.83},
    "flat_3_3":     {"p25": 5.90,  "p50": 6.30,  "p75": 7.00},
    "up_3_8":       {"p25": 7.74,  "p50": 8.54,  "p75": 10.98},
    "up_8_12":      {"p25": 10.00, "p50": 11.50, "p75": 13.20},
    "up_12_17":     {"p25": 12.00, "p50": 14.20, "p75": 16.50},
    "up_17_23":     {"p25": 16.18, "p50": 19.50, "p75": 23.00},
    "up_23_over":   {"p25": 22.00, "p50": 28.50, "p75": 35.00}
}
```

### Backward compatibility: avg_ поля остаются

Существующие 7 полей `avg_*_pace_min_km` и 7 полей `*_sample_count` **не удаляем**. Они продолжают заполняться через `LEGACY_CATEGORY_MAPPING` для обратной совместимости. JSON поля дополняют, не заменяют.

Калькуляторы для effort level (Фаза 3) читают из `gradient_percentiles`. Legacy калькуляторы продолжают читать `avg_*`.

---

## Часть 3: Перцентили P25/P50/P75

### Зачем

Один pace на категорию не позволяет различать гонку и прогулку. Перцентили дают 3 уровня:

| Перцентиль | Значение | Пример для flat_3_3 |
|------------|----------|---------------------|
| **P25** | 25% тренировок быстрее | 5.90 min/km |
| **P50** | Медиана (типичная тренировка) | 6.30 min/km |
| **P75** | 75% тренировок быстрее | 7.00 min/km |

### Расчёт перцентилей

В `user_profile.py`, перцентили считаются на **уже отфильтрованных** данных (IQR применён один раз в основном flow, не повторно):

```python
import statistics

def calculate_percentiles(filtered_paces: list[float]) -> dict | None:
    """
    Calculate P25, P50 (median), P75 from already IQR-filtered data.

    IMPORTANT: Takes pre-filtered paces. Do NOT call filter_outliers_iqr() inside —
    IQR is already applied once in the main calculation flow.
    """
    if not filtered_paces:
        return None

    if len(filtered_paces) < 3:
        median = statistics.median(filtered_paces)
        return {'p25': median, 'p50': median, 'p75': median}

    q1, q2, q3 = statistics.quantiles(filtered_paces, n=4)
    return {
        'p25': q1,
        'p50': q2,
        'p75': q3,
    }
```

---

## Что менять (все файлы)

### 1. `models/user_run_profile.py`

Добавить 2 JSON колонки:

```python
from sqlalchemy import JSON

gradient_paces = Column(JSON, nullable=True)
gradient_percentiles = Column(JSON, nullable=True)
```

Добавить методы:

```python
def get_pace_for_category(self, category: str) -> Optional[float]:
    """Get avg pace from JSON, fallback to column field."""
    if self.gradient_paces and category in self.gradient_paces:
        return self.gradient_paces[category].get('avg')
    # Fallback to legacy column (old naming)
    legacy_name = LEGACY_CATEGORY_MAPPING.get(category)
    if legacy_name:
        field = f"avg_{legacy_name}_pace_min_km"
        return getattr(self, field, None)
    return None

def get_percentile(self, category: str, percentile: str) -> Optional[float]:
    """Get percentile (p25/p50/p75) for a gradient category."""
    if not self.gradient_percentiles:
        return None
    cat_data = self.gradient_percentiles.get(category)
    if not cat_data:
        return None
    return cat_data.get(percentile)

def get_sample_count_extended(self, category: str) -> int:
    """Get sample count from JSON, fallback to column field."""
    if self.gradient_paces and category in self.gradient_paces:
        return self.gradient_paces[category].get('samples', 0)
    # Fallback to legacy column
    legacy_name = LEGACY_CATEGORY_MAPPING.get(category)
    if legacy_name:
        return self.get_sample_count(legacy_name)
    return 0
```

### 2. `services/user_profile.py`

В `calculate_run_profile_with_splits()`:

```python
from app.shared.gradients import classify_gradient, LEGACY_CATEGORY_MAPPING

# После IQR фильтрации (Фаза 1), для каждой категории:
gradient_paces_json = {}
gradient_percentiles_json = {}

for category, paces in category_paces.items():
    filtered = filter_outliers_iqr(paces)
    if not filtered:
        continue

    avg_pace = mean(filtered)
    percentiles = calculate_percentiles(filtered)  # already filtered, no double IQR!

    gradient_paces_json[category] = {
        'avg': round(avg_pace, 2),
        'samples': len(filtered),
    }
    if percentiles:
        gradient_percentiles_json[category] = {
            'p25': round(percentiles['p25'], 2),
            'p50': round(percentiles['p50'], 2),
            'p75': round(percentiles['p75'], 2),
        }

# Сохранить в профиль
profile.gradient_paces = gradient_paces_json
profile.gradient_percentiles = gradient_percentiles_json

# Legacy avg_ поля — взвешенное среднее для 7 оригинальных категорий
legacy_paces = {}  # {legacy_name: [(avg, samples), ...]}
for new_cat, data in gradient_paces_json.items():
    legacy_name = LEGACY_CATEGORY_MAPPING.get(new_cat)
    if legacy_name:
        legacy_paces.setdefault(legacy_name, []).append(
            (data['avg'], data['samples'])
        )

for legacy_name, entries in legacy_paces.items():
    total_samples = sum(s for _, s in entries)
    if total_samples > 0:
        weighted_avg = sum(avg * s for avg, s in entries) / total_samples
        setattr(profile, f"avg_{legacy_name}_pace_min_km", round(weighted_avg, 2))
```

### 3. Персонализированный калькулятор

`features/trail_run/calculators/personalization.py` — обновить `_get_pace_for_category()`:

```python
def _get_pace_for_category(self, category: str) -> Optional[float]:
    """Get pace from profile, with confidence check."""
    # Try JSON first (supports 11 categories)
    sample_count = self._profile.get_sample_count_extended(category)
    if sample_count < MIN_SAMPLES_FOR_CATEGORY:
        return None  # Fallback to GAP

    return self._profile.get_pace_for_category(category)
```

### 4. Миграция Alembic

```bash
cd backend
alembic revision --autogenerate -m "add gradient_paces and gradient_percentiles JSON fields"
alembic upgrade head
```

---

## Проверка

```bash
# 1. Snapshot before
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-... --reason "phase_2_before"

# 2. Пересчитать с 11 категориями + перцентилями
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-... --reason "phase_2_11cat_percentiles"

# 3. Проверить JSON в БД
# gradient_paces: 11 категорий с avg + samples
# gradient_percentiles: 11 категорий с p25/p50/p75

# 4. Калибровка
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --min-elevation 100
```

## Ожидаемый результат

- Профиль содержит 11 категорий вместо 7
- Крутые уклоны (>12%) разбиты на тонкие ~5% корзины
- Перцентили P25/P50/P75 рассчитаны для каждой категории
- Legacy avg_ поля продолжают работать (взвешенное среднее из новых категорий)
- Калькулятор использует JSON для 11 категорий, fallback на legacy + GAP

## Чеклист

- [x] `UserRunProfile` — добавлены `gradient_paces` и `gradient_percentiles` JSON поля
- [x] `UserRunProfile` — добавлены методы `get_pace_for_category()`, `get_percentile()`, `get_sample_count_extended()`
- [x] `user_profile.py` — расчёт заполняет JSON поля + legacy поля (взвешенное среднее)
- [x] `user_profile.py` — добавлена `calculate_percentiles(filtered_paces)` (без двойного IQR!)
- [x] Персонализированный калькулятор — использует JSON через новые методы
- [x] Миграция Alembic создана и применена
- [x] Snapshot "before" и "after" сохранены
- [x] Калибровка прогнана, результаты в `calibration_results.md`

**Примечание:** `shared/gradients.py` с 11 категориями и `LEGACY_CATEGORY_MAPPING` — уже в Фазе 0.
