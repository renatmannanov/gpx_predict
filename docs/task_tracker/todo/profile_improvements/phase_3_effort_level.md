# Фаза 3: Effort Level в расчётах и API

**Сложность:** Средняя
**Эффект:** Высокий
**Зависимости:** Фаза 2 (перцентили в профиле)
**Оценка:** ~100-120 строк изменений (калькуляторы + API + CLI)

---

## Цель

Добавить параметр "effort level" в персонализированный расчёт:

| Effort | Перцентиль | Описание |
|--------|-----------|----------|
| **Race** | P25 | Ваш темп в верхних 25% тренировок. Гонки, забеги с целью на время. |
| **Moderate** | P50 (median) | Ваш типичный тренировочный темп. Половина тренировок быстрее, половина медленнее. |
| **Easy** | P75 | Ваш расслабленный темп. Длинные маршруты, разведка, технический рельеф, бег без гонки за временем. |

**Важно:** effort level — это про интенсивность усилий, НЕ про тип поверхности. Race на trail и Race на асфальте — оба P25, просто на trail P25 будет медленнее из-за рельефа.

## Зачем

Калибровка показала: один профиль не может предсказать и асфальт (+15-24% ошибка), и trail гонку (-8-12% ошибка). Перцентили решают:

- Асфальтовый забег на время → **Race (P25)** → быстрые пейсы
- Обычная тренировка в горах → **Moderate (P50)** → средние пейсы
- Длинная техничная разведка → **Easy (P75)** → консервативные пейсы

## Что менять

### 1. Enum + конфигурация: `backend/app/shared/calculator_types.py`

```python
from enum import Enum

# Конфигурируемые перцентили для effort levels.
# Можно подкрутить после калибровки (например race → 0.20 или 0.30)
# без изменения логики в калькуляторах.
EFFORT_PERCENTILES = {
    "race": 0.25,       # P25 — верхние 25% тренировок
    "moderate": 0.50,   # P50 — типичный темп
    "easy": 0.75,       # P75 — расслабленный темп
}


class EffortLevel(str, Enum):
    RACE = "race"           # Fast — race effort
    MODERATE = "moderate"   # Normal — typical training (default)
    EASY = "easy"           # Conservative — easy/exploratory

    @property
    def percentile_key(self) -> str:
        """Map effort level to percentile key in JSON (p25/p50/p75)."""
        pct = EFFORT_PERCENTILES[self.value]
        return f'p{int(pct * 100)}'

    @property
    def percentile_value(self) -> float:
        """Get raw percentile value (0.0-1.0) for calculations."""
        return EFFORT_PERCENTILES[self.value]
```

**Зачем конфигурируемые значения:** Калибровка может показать, что P25 слишком быстро или медленно для "race". Вместо хардкода P25/P50/P75, значения вынесены в `EFFORT_PERCENTILES` — меняется одна строка, без изменения enum или калькуляторов.

**Важно:** Если значения перцентилей изменятся (например race → P20), нужно:
1. Обновить `EFFORT_PERCENTILES`
2. Пересчитать профили (CLI `recalculate-profile`) — чтобы JSON содержал нужные ключи p20
3. Или: хранить в JSON массив значений, а не фиксированные p25/p50/p75

**Рекомендация на будущее:** Если калибровка покажет, что P25/P50/P75 недостаточно — перейти на хранение полного массива pace значений в JSON и вычислять любой перцентиль on-the-fly. Но для MVP — P25/P50/P75 достаточно.

### 2. Персонализированный калькулятор

`features/trail_run/calculators/personalization.py`:

```python
class RunPersonalizationService(BasePersonalizationService):
    def __init__(self, profile, effort: EffortLevel = EffortLevel.MODERATE, ...):
        super().__init__(profile, ...)
        self._effort = effort

    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """Get pace based on effort level."""
        sample_count = self._profile.get_sample_count_extended(category)
        if sample_count < MIN_SAMPLES_FOR_CATEGORY:
            return None

        # Try percentile first
        percentile_key = self._effort.percentile_key
        pace = self._profile.get_percentile(category, percentile_key)
        if pace:
            return pace

        # Fallback to avg (no percentiles available)
        return self._profile.get_pace_for_category(category)
```

### 3. Comparison Service — все 3 effort levels сразу

`services/calculators/comparison.py` — вместо одного effort, считать все три:

```python
def compare_route(self, segments, ...):
    # Для персонализированного метода — 3 расчёта параллельно
    for effort in EffortLevel:
        personalization = RunPersonalizationService(
            run_profile,
            effort=effort,
            ...
        )
        result = personalization.calculate(segments)
        results[f"personalized_{effort.value}"] = result
```

API возвращает все 3 варианта в одном ответе. Пользователь видит диапазон и выбирает сам:
```json
{
    "personalized_race": {"total_time": 240, "...": "..."},
    "personalized_moderate": {"total_time": 280, "...": "..."},
    "personalized_easy": {"total_time": 330, "...": "..."}
}
```

### 4. API: `api/v1/routes/predict.py`

**Не добавляем query parameter effort.** API всегда возвращает все 3 варианта. Фронт показывает их рядом — пользователь сам решает, какой ему ближе.

### 5. Калибровочные инструменты: `tools/calibration/cli.py`

Добавить `--effort` параметр для бэктестинга (для сравнения конкретного расчёта с фактом):

```bash
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... \
    --effort race \
    --min-elevation 100
```

В отчёте показывать все 3 effort levels для каждой активности — чтобы видеть, какой ближе к факту.

### 6. Фронт (отдельная задача)

В UI trail running расчёта показывать 3 варианта:
- **Race** (P25) — "быстрый темп, гонки"
- **Moderate** (P50) — "типичная тренировка"
- **Easy** (P75) — "расслабленный темп, разведка"

---

## Проверка

Прогнать калибровку — для каждой активности показать все 3 effort levels:

### Ожидаемые результаты

Для каждой тестовой активности смотрим, какой effort даёт минимальную ошибку:

| Активность | Тип | Race (P25) | Moderate (P50) | Easy (P75) | Лучший |
|------------|-----|-----------|----------------|-----------|--------|
| Morning Asphalt Sky Run | Road | ? | ? | ? | Ожидаем Race |
| Irbis Race / Talgar | Trail race | ? | ? | ? | TBD |
| Talgar trail check #2 | Fast hiking | ? | ? | ? | Ожидаем Easy |

**Главный вопрос:** какой effort лучше подходит для trail race? Это покажет калибровка.

### Команды

```bash
# Для каждой активности — все 3 effort
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 494  # покажет race/moderate/easy

python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 570

python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 563
```

---

## Будущее: HR зоны

Effort level — упрощённый proxy. В будущем можно дополнить/заменить реальными HR данными из Strava:

- Race ~ HR Zone 3-4
- Moderate ~ HR Zone 2-3
- Easy ~ HR Zone 1-2

Это отдельная задача, не в этом плане.

## Чеклист

- [x] `EffortLevel` enum добавлен в `shared/calculator_types.py`
- [x] `RunPersonalizationService` принимает effort, читает из перцентилей
- [x] `ComparisonService` прокидывает effort — N/A (hiking only, no percentile data yet)
- [x] API (TrailRunService) возвращает все 3 effort levels в одном ответе (без query param)
- [x] Калибровочный CLI поддерживает `--effort`
- [x] Калибровка с effort=race/moderate/easy, результаты в `calibration_results.md`
