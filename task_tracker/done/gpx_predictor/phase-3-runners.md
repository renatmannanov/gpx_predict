# Фаза 3: Режим для бегунов

**Цель:** Расширение на беговую аудиторию (без Strava)

---

## Шаги реализации

### Шаг 1: Беговые алгоритмы
- Riegel formula
- Minetti/Strava GAP model
- Confidence intervals

### Шаг 2: Prediction Engine для бегунов
- POST /predict/run (manual input)
- Ввод времени на 10К
- Elevation-adjusted pace

### Шаг 3: UI для бегунов
- Переключатель турист/бегун
- Посегментная раскладка темпа
- Сравнение с плоской трассой

### Шаг 4: Public Courses Database
- Course submission flow
- Moderation (manual)
- Search by location

### Шаг 5: Result Tracking
- "Enter actual result" flow
- Accuracy feedback
- Personal progress chart

---

## Deliverables

- [ ] Расчёт прогноза на основе времени 10К
- [ ] Посегментная раскладка темпа для бегунов
- [ ] База публичных трасс Казахстана
- [ ] Ввод реальных результатов

---

## Формула Riegel

**Источник:** Riegel, P.S. (1981). "Athletic Records and Human Endurance"

```python
def riegel_prediction(
    known_time: float,
    known_distance: float,
    target_distance: float,
    fatigue_factor: float = 1.06
) -> float:
    """
    Прогнозирует время на целевой дистанции.

    Args:
        known_time: Известное время в секундах (10К за 3000 сек)
        known_distance: Известная дистанция в км (10)
        target_distance: Целевая дистанция в км (42.195)
        fatigue_factor: Коэффициент усталости (1.03-1.15)

    Формула: T2 = T1 × (D2/D1)^fatigue_factor

    Пример: 10К за 50 мин → марафон за ~3:48
    """
    return known_time * (target_distance / known_distance) ** fatigue_factor
```

### Персональный fatigue factor

```python
def calculate_personal_fatigue_factor(results: list[dict]) -> float:
    """
    Вычисляет персональный коэффициент на основе нескольких результатов.

    Args:
        results: [{"distance": 5, "time": 1320}, ...]

    Returns:
        Персональный factor (обычно 1.03-1.15)
    """
    from math import log

    factors = []
    sorted_results = sorted(results, key=lambda x: x["distance"])

    for i in range(len(sorted_results) - 1):
        r1 = sorted_results[i]
        r2 = sorted_results[i + 1]

        factor = log(r2["time"] / r1["time"]) / log(r2["distance"] / r1["distance"])
        factors.append(factor)

    return sum(factors) / len(factors) if factors else 1.06
```

---

## Формула Minetti (GAP)

**Источник:** Minetti, A.E. et al. (2002). "Energy cost of walking and running"

```python
def minetti_energy_cost(gradient: float) -> float:
    """
    Коэффициент энергозатрат на уклоне.

    Args:
        gradient: Уклон в долях (0.10 = 10%)

    Returns:
        Коэффициент (1.0 = плоская поверхность)
    """
    g = gradient

    # Полином 5-й степени из исследования
    cost = (155.4 * g**5
            - 30.4 * g**4
            - 43.3 * g**3
            + 46.3 * g**2
            + 19.5 * g
            + 3.6)

    flat_cost = 3.6
    return cost / flat_cost
```

### Улучшенный GAP (Strava)

```python
def strava_adjusted_gap(gradient: float) -> float:
    """
    Модель GAP от Strava (2017).
    Корректирует проблему Minetti с крутыми спусками.

    Отличия от Minetti:
    - Минимальное ускорение на спуске: -10% (не -50%)
    - Оптимальный спуск: -9% градиент (не -20%)
    """
    if gradient >= 0:
        # Подъём: +12% на каждые 1% уклона
        return 1 + (gradient * 12)
    else:
        # Спуск: максимум -12% при -9%
        optimal_descent = -0.09
        max_benefit = 0.88

        if gradient >= optimal_descent:
            return 1 + (gradient / optimal_descent) * (1 - max_benefit)
        else:
            overshoot = gradient - optimal_descent
            return max_benefit + abs(overshoot) * 1.3
```

---

## API Endpoints

### POST /predict/run

```python
class RunPredictRequest(BaseModel):
    gpx_file_id: str
    known_time_seconds: int   # Время на известной дистанции
    known_distance_km: float  # 5, 10, 21.1, 42.195

class RunPrediction(BaseModel):
    predicted_time_seconds: int
    flat_equivalent_seconds: int
    elevation_impact_percent: float
    segments: List[SegmentPrediction]
    pace_chart: List[PacePoint]

class SegmentPrediction(BaseModel):
    start_km: float
    end_km: float
    distance_km: float
    elevation_change_m: float
    gradient_percent: float
    predicted_pace: str       # "5:30/km"
    flat_pace: str            # "5:00/km"
    gap_factor: float

@router.post("/predict/run")
async def predict_run(request: RunPredictRequest) -> RunPrediction:
    pass
```

### POST /results

```python
class ResultInput(BaseModel):
    prediction_id: str
    actual_time_seconds: int
    conditions: Optional[str]  # "windy", "hot", "perfect"
    notes: Optional[str]

@router.post("/results")
async def submit_result(request: ResultInput) -> AccuracyFeedback:
    """
    Пользователь вводит реальный результат после забега.
    """
    pass

class AccuracyFeedback(BaseModel):
    prediction_time: int
    actual_time: int
    difference_seconds: int
    difference_percent: float
    accuracy_rating: str  # "excellent", "good", "fair", "poor"
```

---

## Посегментная раскладка

### Пример вывода

```
┌─────────────────────────────────────────────────────────────┐
│  🏃 ПРОГНОЗ: Алматинский марафон                            │
├─────────────────────────────────────────────────────────────┤
│  Ваш результат 10К: 50:00                                   │
│  Плоский марафон:   3:48:00                                 │
│  С учётом рельефа:  4:32:00 (+44 мин)                       │
├─────────────────────────────────────────────────────────────┤
│  ПОСЕГМЕНТНАЯ РАСКЛАДКА                                     │
│                                                              │
│  Км 0-5:    +120м  ▲  темп 5:45  (плоский эквивалент 5:00) │
│  Км 5-10:   +180м  ▲▲ темп 6:15  (плоский эквивалент 5:00) │
│  Км 10-15:  -50м   ▼  темп 4:45  (плоский эквивалент 5:00) │
│  Км 15-21:  +320м  ▲▲▲ темп 7:00 (плоский эквивалент 5:05) │
│  ...                                                         │
│                                                              │
│  📊 Профиль высоты: [график]                                │
└─────────────────────────────────────────────────────────────┘
```

---

## База публичных трасс

### Модель

```python
@dataclass
class RaceCourse:
    id: str
    name: str
    location: str
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    gpx_file: str
    verified: bool
    submitted_by: Optional[str]
    race_date: Optional[date]
    official_website: Optional[str]
```

### Начальный список (Казахстан)

| Забег | Дистанция | Набор |
|-------|-----------|-------|
| Алматинский марафон | 42.2 км | +847м |
| Алматы полумарафон | 21.1 км | +420м |
| Medeu Trail | 21 км | +1100м |
| Shymbulak Ultra | 50 км | +2800м |
| Burabay Trail | 30 км | +600м |
| Astana Marathon | 42.2 км | +50м |

---

## Result Tracking

### Flow

1. Пользователь делает прогноз перед забегом
2. Сохраняем prediction_id
3. После забега — предлагаем ввести результат
4. Показываем точность прогноза
5. Используем для улучшения персонального fatigue factor

### Accuracy Categories

| Разница | Категория | Описание |
|---------|-----------|----------|
| <3% | Excellent | Идеальный прогноз |
| 3-7% | Good | Хороший прогноз |
| 7-15% | Fair | Приемлемый |
| >15% | Poor | Требует калибровки |
