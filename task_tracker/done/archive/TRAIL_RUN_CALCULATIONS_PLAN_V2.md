# План рефакторинга расчётов Trail Running v2

**Дата:** 2026-01-30
**Статус:** Draft

---

## Цель

Переработать архитектуру расчётов trail running так, чтобы:
1. Все методы считали **весь маршрут** (не частично RUN или HIKE)
2. Вариации (персонализация, переход на шаг, усталость) применялись **явно и раздельно**
3. Вывод был **понятным и сравнимым** для тестирования точности формул

---

## Текущие проблемы

| # | Проблема | Файл:строки |
|---|----------|-------------|
| 1 | `totals["strava_gap"]` содержит время только для RUN сегментов | service.py:285-290 |
| 2 | `totals["tobler"]` содержит время только для HIKE сегментов | service.py:310 |
| 3 | Minetti GAP — гибрид (Minetti up + Strava down), а не чистый Minetti | gap.py:260-296 |
| 4 | Нет чистого "Strava+Minetti" метода | — |
| 5 | "combined" непрозрачен — mix методов по сегментам | service.py:296-340 |
| 6 | Fatigue применяется ко ВСЕМ методам в totals | service.py:339-350 |
| 7 | Вариант 2 (масштабирование по flat) не выделен отдельно | — |

---

## Целевая структура

### 3 базовых метода GAP (для RUN сегментов)

| Метод | Uphill | Downhill | Новый? |
|-------|--------|----------|--------|
| `strava_gap` | Strava | Strava | Существует |
| `minetti_gap` | Minetti | Minetti | **Нужно создать** (сейчас гибрид) |
| `strava_minetti_gap` | Minetti | Strava | **Нужно создать** (сейчас называется minetti_gap) |

### 2 метода Hiking (для HIKE сегментов или "всё пешком")

| Метод | Формула |
|-------|---------|
| `tobler` | Tobler's Hiking Function |
| `naismith` | Naismith + Langmuir corrections |

### 3 вариации расчёта

| Вариация | Описание | Применяется к |
|----------|----------|---------------|
| **Персонализация** | Lookup из профиля + fallback на Вариант 2 | Любому методу |
| **Переход на шаг** | После X% градиента — hiking формулы | GAP методам |
| **Усталость** | +% к времени после Y часов | Любому методу |

### 4 варианта расчёта (для каждого метода)

| Вариант | Название | Логика |
|---------|----------|--------|
| **1** | Базовый | Чистая формула |
| **2** | Масштабированный | Формула × (user_flat / standard_flat) |
| **3.5** | Персонализированный | Lookup + fallback на Вариант 2 |

---

## Целевой вывод (для тестирования)

```
📊 ВСЁ БЕГОМ (весь маршрут как бег):

  Базовые формулы:
    Strava GAP: 3ч 45м
    Minetti GAP: 3ч 52м
    Strava+Minetti: 3ч 48м

  Масштабированные (ваш flat 6:00/км):
    Strava GAP: 3ч 40м
    Minetti GAP: 3ч 47м
    Strava+Minetti: 3ч 43м

  Персонализированные (lookup):
    🎯 Strava GAP: 3ч 38м
    🎯 Minetti GAP: 3ч 44м
    🎯 Strava+Minetti: 3ч 41м

📊 БЕГ + ШАГ после 25% (Бег: 18.5км | Шаг: 1.5км):

  Strava + Tobler: 3ч 58м
  Strava + Naismith: 4ч 02м
  Minetti + Tobler: 4ч 05м
  Minetti + Naismith: 4ч 08м
  Strava+Minetti + Tobler: 4ч 01м
  Strava+Minetti + Naismith: 4ч 05м

  Персонализированные:
    🎯 Strava + Tobler: 3ч 52м
    🎯 Strava + Naismith: 3ч 54м
    ... (все комбинации)

😓 УСТАЛОСТЬ (дополнительно к любому методу):
  После 2ч: +5.8%
  После 4ч: +13%
  Итого добавка: ~12м
```

---

## План реализации

### Фаза 1: Рефакторинг GAPCalculator

**Файл:** `backend/app/features/trail_run/calculators/gap.py`

#### 1.1 Добавить enum для режимов GAP

```python
class GAPMode(str, Enum):
    STRAVA = "strava"           # Strava up + Strava down
    MINETTI = "minetti"         # Minetti up + Minetti down (НОВЫЙ)
    STRAVA_MINETTI = "strava_minetti"  # Minetti up + Strava down
```

**Изменения:**
- Переименовать текущий `GAPMode.MINETTI` → `GAPMode.STRAVA_MINETTI`
- Создать новый `GAPMode.MINETTI` (чистый Minetti для обоих направлений)

#### 1.2 Реализовать чистый Minetti для downhill

**Текущее состояние** (строки 260-286):
```python
def _calculate_minetti(self, gradient_percent: float) -> GAPResult:
    if gradient_percent >= 0:
        # Minetti для подъёма
        ...
    else:
        # Strava для спуска (!)
        return self._calculate_strava(gradient_percent)
```

**Новый код:**
```python
def _calculate_minetti_pure(self, gradient_percent: float) -> GAPResult:
    """Чистый Minetti для любого градиента."""
    energy_ratio = self._minetti_energy_cost(gradient_percent / 100)
    adjustment = energy_ratio ** 0.75
    adjusted_pace = self.flat_pace * adjustment
    return GAPResult(...)

def _calculate_strava_minetti(self, gradient_percent: float) -> GAPResult:
    """Гибрид: Minetti uphill + Strava downhill."""
    if gradient_percent >= 0:
        return self._calculate_minetti_pure(gradient_percent)
    else:
        return self._calculate_strava(gradient_percent)
```

#### 1.3 Обновить метод calculate()

```python
def calculate(self, gradient_percent: float) -> GAPResult:
    if self.mode == GAPMode.STRAVA:
        return self._calculate_strava(gradient_percent)
    elif self.mode == GAPMode.MINETTI:
        return self._calculate_minetti_pure(gradient_percent)
    else:  # STRAVA_MINETTI
        return self._calculate_strava_minetti(gradient_percent)
```

---

### Фаза 2: Создать MultiMethodCalculator

**Новый файл:** `backend/app/features/trail_run/calculators/multi_method.py`

Калькулятор, который считает **все методы сразу** для сегмента.

```python
@dataclass
class MultiMethodResult:
    """Результаты всех методов для одного сегмента."""
    segment: MacroSegment

    # GAP методы (базовые)
    strava_gap: float           # часы
    minetti_gap: float          # часы
    strava_minetti_gap: float   # часы

    # Hiking методы (базовые)
    tobler: float               # часы
    naismith: float             # часы

    # GAP персонализированные (Вариант 3.5)
    strava_gap_personalized: Optional[float]
    minetti_gap_personalized: Optional[float]
    strava_minetti_gap_personalized: Optional[float]

    # Hiking персонализированные (Вариант 3.5)
    tobler_personalized: Optional[float]
    naismith_personalized: Optional[float]


class MultiMethodCalculator:
    """Считает все методы для сегмента."""

    def __init__(
        self,
        flat_pace_min_km: float = 6.0,
        run_profile: Optional[UserRunProfile] = None,
        hike_profile: Optional[UserHikingProfile] = None,
    ):
        self._flat_pace = flat_pace_min_km

        # GAP калькуляторы
        self._strava_calc = GAPCalculator(GAPMode.STRAVA, flat_pace_min_km)
        self._minetti_calc = GAPCalculator(GAPMode.MINETTI, flat_pace_min_km)
        self._strava_minetti_calc = GAPCalculator(GAPMode.STRAVA_MINETTI, flat_pace_min_km)

        # Hiking калькуляторы
        self._tobler_calc = ToblerCalculator()
        self._naismith_calc = NaismithCalculator()

        # Персонализация
        self._run_pers = RunPersonalizationService(run_profile) if run_profile else None
        self._hike_pers = HikePersonalizationService(hike_profile) if hike_profile else None

    def calculate_segment(self, segment: MacroSegment) -> MultiMethodResult:
        """Рассчитать все методы для одного сегмента."""

        # GAP (базовые)
        strava = self._strava_calc.calculate_segment(segment).time_hours
        minetti = self._minetti_calc.calculate_segment(segment).time_hours
        strava_minetti = self._strava_minetti_calc.calculate_segment(segment).time_hours

        # Hiking (базовые)
        tobler = self._tobler_calc.calculate_segment(segment).time_hours
        naismith = self._naismith_calc.calculate_segment(segment).time_hours

        # Персонализация
        strava_pers = self._run_pers.calculate_segment(segment).time_hours if self._run_pers else None
        # ... аналогично для остальных

        return MultiMethodResult(
            segment=segment,
            strava_gap=strava,
            minetti_gap=minetti,
            strava_minetti_gap=strava_minetti,
            tobler=tobler,
            naismith=naismith,
            strava_gap_personalized=strava_pers,
            # ...
        )
```

---

### Фаза 3: Создать RouteCalculationResult

**Новый файл:** `backend/app/features/trail_run/calculators/route_result.py`

Структура для хранения **всех вариантов** расчёта маршрута.

```python
@dataclass
class MethodTotals:
    """Итоги одного метода для всего маршрута."""
    base: float                    # Вариант 1: чистая формула
    scaled: Optional[float]        # Вариант 2: масштабированный
    personalized: Optional[float]  # Вариант 3.5: lookup + fallback


@dataclass
class AllRunTotals:
    """Блок 'ВСЁ БЕГОМ' — весь маршрут считается бегом."""
    strava_gap: MethodTotals
    minetti_gap: MethodTotals
    strava_minetti_gap: MethodTotals


@dataclass
class RunHikeTotals:
    """Блок 'БЕГ + ШАГ' — после порога переход на hiking."""

    # Комбинации: GAP метод + Hiking метод
    strava_tobler: MethodTotals
    strava_naismith: MethodTotals
    minetti_tobler: MethodTotals
    minetti_naismith: MethodTotals
    strava_minetti_tobler: MethodTotals
    strava_minetti_naismith: MethodTotals

    # Статистика разбивки
    run_distance_km: float
    run_percent: float
    hike_distance_km: float
    hike_percent: float
    threshold_used: float


@dataclass
class FatigueAddition:
    """Дополнительное время от усталости."""
    after_2h_percent: float
    after_4h_percent: float
    total_addition_hours: float


@dataclass
class RouteCalculationResult:
    """Полный результат расчёта маршрута."""

    # Метаданные
    total_distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float

    # Блоки расчётов
    all_run: AllRunTotals
    run_hike: RunHikeTotals
    fatigue: Optional[FatigueAddition]

    # Сегменты (для детального вывода)
    segments: List[MultiMethodResult]

    # Информация о персонализации
    run_activities_used: int
    hike_activities_used: int
    run_splits_used: int
```

---

### Фаза 4: Рефакторинг TrailRunService

**Файл:** `backend/app/features/trail_run/service.py`

#### 4.1 Новый метод calculate_all_methods()

```python
def calculate_all_methods(self, points: List[tuple]) -> RouteCalculationResult:
    """
    Рассчитать ВСЕ варианты для маршрута.

    Возвращает структуру со всеми блоками:
    - all_run: весь маршрут как бег
    - run_hike: бег + переход на шаг
    - fatigue: дополнительное время от усталости
    """

    segments = RouteSegmenter.segment_route(points)
    multi_calc = MultiMethodCalculator(
        flat_pace_min_km=self.flat_pace,
        run_profile=self._run_profile,
        hike_profile=self._hike_profile,
    )

    # Рассчитать все методы для каждого сегмента
    segment_results = [multi_calc.calculate_segment(seg) for seg in segments]

    # Блок 1: ВСЁ БЕГОМ
    all_run = self._calculate_all_run_block(segment_results)

    # Блок 2: БЕГ + ШАГ
    run_hike = self._calculate_run_hike_block(segment_results, segments)

    # Блок 3: Усталость
    fatigue = self._calculate_fatigue_block(all_run, run_hike)

    return RouteCalculationResult(
        total_distance_km=sum(s.segment.distance_km for s in segment_results),
        # ...
        all_run=all_run,
        run_hike=run_hike,
        fatigue=fatigue,
        segments=segment_results,
    )
```

#### 4.2 Метод _calculate_all_run_block()

```python
def _calculate_all_run_block(
    self,
    segment_results: List[MultiMethodResult]
) -> AllRunTotals:
    """Блок 'ВСЁ БЕГОМ' — суммируем GAP методы для всех сегментов."""

    strava_base = sum(r.strava_gap for r in segment_results)
    minetti_base = sum(r.minetti_gap for r in segment_results)
    strava_minetti_base = sum(r.strava_minetti_gap for r in segment_results)

    # Масштабированные (Вариант 2)
    # TODO: реализовать через scale factor

    # Персонализированные (Вариант 3.5)
    strava_pers = sum(r.strava_gap_personalized or r.strava_gap for r in segment_results)
    # ...

    return AllRunTotals(
        strava_gap=MethodTotals(base=strava_base, scaled=..., personalized=strava_pers),
        # ...
    )
```

#### 4.3 Метод _calculate_run_hike_block()

```python
def _calculate_run_hike_block(
    self,
    segment_results: List[MultiMethodResult],
    segments: List[MacroSegment],
) -> RunHikeTotals:
    """Блок 'БЕГ + ШАГ' — по порогу выбираем GAP или Hiking."""

    decisions = self._threshold_service.process_route(segments, ...)

    strava_tobler_total = 0.0
    # ...

    for result, decision in zip(segment_results, decisions):
        if decision.mode == MovementMode.RUN:
            strava_tobler_total += result.strava_gap
        else:
            strava_tobler_total += result.tobler

    # Аналогично для всех комбинаций

    return RunHikeTotals(
        strava_tobler=MethodTotals(base=strava_tobler_total, ...),
        # ...
        run_distance_km=...,
        hike_distance_km=...,
        threshold_used=self._threshold_service.base_uphill_threshold,
    )
```

---

### Фаза 5: Обновить API и форматирование

**Файлы:**
- `backend/app/api/v1/routes/predict.py`
- `bot/handlers/trail_run.py`

#### 5.1 Новый endpoint для полного расчёта

```python
@router.post("/trail-run/full-compare")
async def trail_run_full_compare(
    request: TrailRunFullRequest,
    db: AsyncSession = Depends(get_db),
) -> TrailRunFullResponse:
    """Полное сравнение всех методов trail running."""

    service = TrailRunService(...)
    result = service.calculate_all_methods(points)

    return TrailRunFullResponse(
        all_run=result.all_run,
        run_hike=result.run_hike,
        fatigue=result.fatigue,
        # ...
    )
```

#### 5.2 Форматирование для Telegram

```python
def format_full_trail_run_result(result: RouteCalculationResult) -> str:
    """Форматировать полный результат для Telegram."""

    lines = []

    # Блок 1: ВСЁ БЕГОМ
    lines.append("📊 ВСЁ БЕГОМ (весь маршрут как бег):")
    lines.append("")
    lines.append("  Базовые формулы:")
    lines.append(f"    Strava GAP: {format_time(result.all_run.strava_gap.base)}")
    lines.append(f"    Minetti GAP: {format_time(result.all_run.minetti_gap.base)}")
    lines.append(f"    Strava+Minetti: {format_time(result.all_run.strava_minetti_gap.base)}")
    # ...

    # Блок 2: БЕГ + ШАГ
    lines.append("")
    lines.append(f"📊 БЕГ + ШАГ после {result.run_hike.threshold_used}%:")
    lines.append(f"   (Бег: {result.run_hike.run_distance_km:.1f}км | Шаг: {result.run_hike.hike_distance_km:.1f}км)")
    # ...

    return "\n".join(lines)
```

---

### Фаза 6: Добавить Naismith в trail running

**Текущее состояние:** Trail running использует только Tobler для HIKE сегментов.

**Изменения:**

1. Импортировать `NaismithCalculator` из `features/hiking/calculators/`
2. Добавить в `MultiMethodCalculator`
3. Добавить в комбинации `RunHikeTotals`

---

### Фаза 7: Реализовать Вариант 2 (масштабирование)

**Проблема:** Сейчас есть только Вариант 1 (базовый) и Вариант 3.5 (lookup). Нет промежуточного варианта.

**Решение:** Добавить метод `calculate_scaled()` в калькуляторы.

```python
class GAPCalculator:
    def calculate_scaled(
        self,
        gradient_percent: float,
        user_flat_pace: float,
        standard_flat_pace: float = 6.0,  # "средний" атлет
    ) -> GAPResult:
        """Вариант 2: формула × (user_flat / standard_flat)."""

        base_result = self.calculate(gradient_percent)
        scale = standard_flat_pace / user_flat_pace  # Быстрее = меньше времени

        return GAPResult(
            adjusted_pace_min_km=base_result.adjusted_pace_min_km * scale,
            # ...
        )
```

---

## Порядок реализации

| # | Фаза | Файлы | Приоритет |
|---|------|-------|-----------|
| 1 | Рефакторинг GAPCalculator | gap.py | HIGH |
| 2 | MultiMethodCalculator | multi_method.py (новый) | HIGH |
| 3 | RouteCalculationResult | route_result.py (новый) | HIGH |
| 4 | Рефакторинг TrailRunService | service.py | HIGH |
| 5 | API и форматирование | predict.py, trail_run.py | MEDIUM |
| 6 | Добавить Naismith | multi_method.py | MEDIUM |
| 7 | Вариант 2 (масштабирование) | gap.py, tobler.py, naismith.py | LOW |

---

## Обратная совместимость

Старый метод `calculate_route()` остаётся для совместимости:

```python
def calculate_route(self, points: List[tuple]) -> TrailRunResult:
    """Legacy метод — делегирует к новому."""
    full_result = self.calculate_all_methods(points)
    return self._convert_to_legacy_result(full_result)
```

---

## Тестирование

После реализации проверить на реальном маршруте (Talgar Trail, 20 км, +2323м):

1. **Все числа — для всего маршрута** (не частичные)
2. **Strava GAP ≠ Minetti GAP ≠ Strava+Minetti** (разные значения)
3. **Персонализированные < Базовых** (если профиль быстрее среднего)
4. **БЕГ+ШАГ > ВСЁ БЕГОМ** (ходьба медленнее)
5. **Усталость показывается отдельно** (+N минут)

---

## Открытые вопросы

1. **Как масштабировать Minetti?** У него нет "стандартного flat pace" — это энергетическая модель.
2. **Показывать ли все 18+ комбинаций?** Или группировать/скрывать редко используемые?
3. **Как обрабатывать случай "нет hiking профиля"?** Fallback только на Tobler базовый?

---

## Связанные файлы

| Файл | Что менять |
|------|-----------|
| `backend/app/features/trail_run/calculators/gap.py` | Добавить чистый Minetti |
| `backend/app/features/trail_run/calculators/multi_method.py` | Создать новый файл |
| `backend/app/features/trail_run/calculators/route_result.py` | Создать новый файл |
| `backend/app/features/trail_run/service.py` | Новый метод calculate_all_methods() |
| `backend/app/features/trail_run/schemas.py` | Новые Pydantic схемы |
| `backend/app/api/v1/routes/predict.py` | Новый endpoint |
| `bot/handlers/trail_run.py` | Новое форматирование |
| `docs/ARCHITECTURE_CALCULATIONS.md` | Документация |
