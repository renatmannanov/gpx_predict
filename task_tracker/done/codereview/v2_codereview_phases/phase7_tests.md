# Phase 7: Update Tests

> **Статус:** Не начато
> **Оценка:** ~150 строк изменений
> **Зависимости:** Все предыдущие фазы
> **Ветка:** `refactor/phase-7-tests`
> **Цель:** Обновить тесты под новую структуру, убедиться что всё работает

---

## Текущие тесты

```
backend/tests/
├── __init__.py
└── calculators/
    ├── __init__.py
    ├── test_personalization.py      # HikePersonalizationService
    ├── test_gap_calculator.py       # GAPCalculator
    ├── test_hike_run_threshold.py   # HikeRunThresholdService
    ├── test_runner_fatigue.py       # RunnerFatigueService
    ├── test_personalization_run.py  # RunPersonalizationService
    └── test_trail_run_service.py    # TrailRunService
```

---

## Задачи

### 7.1 Обновить импорты в тестах

**Текущие импорты (устаревшие):**
```python
from app.services.calculators.base import MacroSegment, SegmentType
from app.services.calculators.personalization import PersonalizationService
from app.services.calculators.trail_run import GAPCalculator
```

**Новые импорты:**
```python
from app.features.gpx.segmenter import MacroSegment, SegmentType
from app.features.hiking.calculators import HikePersonalizationService
from app.features.trail_run.calculators import GAPCalculator
```

### 7.2 Обновить каждый тестовый файл

- [ ] `test_personalization.py`:
  ```python
  # Было
  from app.services.calculators.personalization_base import (
      BasePersonalizationService,
      GRADIENT_THRESHOLDS,
  )
  from app.services.calculators.personalization import (
      PersonalizationService,
      HikePersonalizationService,
  )

  # Стало
  from app.features.hiking.calculators.personalization_base import (
      BasePersonalizationService,
      GRADIENT_THRESHOLDS,
  )
  from app.features.hiking.calculators import (
      HikePersonalizationService,
      PersonalizationService,  # alias for backward compat
  )
  ```

- [ ] `test_gap_calculator.py`:
  ```python
  # Было
  from app.services.calculators.trail_run.gap_calculator import GAPCalculator, GAPMethod

  # Стало
  from app.features.trail_run.calculators import GAPCalculator, GAPMethod
  ```

- [ ] `test_hike_run_threshold.py`:
  ```python
  # Было
  from app.services.calculators.trail_run.hike_run_threshold import HikeRunThresholdService

  # Стало
  from app.features.trail_run.calculators import HikeRunThresholdService
  ```

- [ ] `test_runner_fatigue.py`:
  ```python
  # Было
  from app.services.calculators.trail_run.runner_fatigue import RunnerFatigueService

  # Стало
  from app.features.trail_run.calculators import RunnerFatigueService
  ```

- [ ] `test_personalization_run.py`:
  ```python
  # Было
  from app.services.calculators.personalization_run import RunPersonalizationService

  # Стало
  from app.features.trail_run.calculators import RunPersonalizationService
  ```

- [ ] `test_trail_run_service.py`:
  ```python
  # Было
  from app.services.calculators.trail_run import TrailRunService

  # Стало
  from app.features.trail_run import TrailRunService
  ```

### 7.3 Реорганизовать структуру тестов (опционально)

Можно оставить как есть, но для консистентности:

```
backend/tests/
├── __init__.py
├── conftest.py                      # Общие fixtures
├── features/
│   ├── __init__.py
│   ├── hiking/
│   │   ├── __init__.py
│   │   └── test_calculators.py      # Все hiking тесты
│   └── trail_run/
│       ├── __init__.py
│       └── test_calculators.py      # Все trail_run тесты
└── shared/
    └── test_formulas.py             # Тесты shared функций
```

### 7.4 Добавить тесты для shared модуля

- [ ] Создать `tests/shared/test_formulas.py`:
  ```python
  """Tests for shared formulas."""
  import pytest
  from app.shared.formulas import tobler_hiking_speed, naismith_base_time


  class TestToblerHikingSpeed:
      """Tests for tobler_hiking_speed function."""

      def test_optimal_gradient(self):
          """Speed should be max (6 km/h) at -5% gradient."""
          speed = tobler_hiking_speed(-0.05)
          assert abs(speed - 6.0) < 0.01

      def test_flat_terrain(self):
          """Speed should be ~5 km/h on flat terrain."""
          speed = tobler_hiking_speed(0.0)
          assert 4.9 < speed < 5.1

      def test_steep_uphill(self):
          """Speed should decrease on steep uphill."""
          speed = tobler_hiking_speed(0.20)  # 20% grade
          assert speed < 3.0

      def test_steep_downhill(self):
          """Speed should decrease on steep downhill."""
          speed = tobler_hiking_speed(-0.20)  # -20% grade
          assert speed < 4.5


  class TestNaismithBaseTime:
      """Tests for naismith_base_time function."""

      def test_flat_5km(self):
          """5km flat should take 1 hour."""
          time = naismith_base_time(5.0, 0.0)
          assert abs(time - 1.0) < 0.01

      def test_with_elevation(self):
          """10km + 600m should take 3 hours."""
          time = naismith_base_time(10.0, 600.0)
          assert abs(time - 3.0) < 0.01
  ```

- [ ] Создать `tests/shared/test_geo.py`:
  ```python
  """Tests for geographic functions."""
  import pytest
  from app.shared.geo import haversine, calculate_gradient


  class TestHaversine:
      """Tests for haversine function."""

      def test_same_point(self):
          """Distance between same point should be 0."""
          dist = haversine(43.0, 76.0, 43.0, 76.0)
          assert dist == 0.0

      def test_known_distance(self):
          """Test with known distance (Almaty to Astana ~1200km)."""
          dist = haversine(43.238949, 76.945465, 51.169392, 71.449074)
          assert 1100 < dist < 1300


  class TestCalculateGradient:
      """Tests for calculate_gradient function."""

      def test_zero_distance(self):
          """Zero distance should return 0 gradient."""
          grad = calculate_gradient(0.0, 100.0)
          assert grad == 0.0

      def test_10_percent(self):
          """100m rise over 1km = 10% = 0.10."""
          grad = calculate_gradient(1.0, 100.0)
          assert abs(grad - 0.10) < 0.001
  ```

### 7.5 Запустить все тесты

```bash
cd backend
pytest tests/ -v --tb=short
```

---

## Файлы для изменения

```
UPDATE:
backend/tests/calculators/test_personalization.py
backend/tests/calculators/test_gap_calculator.py
backend/tests/calculators/test_hike_run_threshold.py
backend/tests/calculators/test_runner_fatigue.py
backend/tests/calculators/test_personalization_run.py
backend/tests/calculators/test_trail_run_service.py

NEW (optional):
backend/tests/shared/__init__.py
backend/tests/shared/test_formulas.py
backend/tests/shared/test_geo.py
backend/tests/conftest.py
```

---

## Критерии завершения

- [ ] Все существующие тесты обновлены под новые импорты
- [ ] `pytest tests/ -v` проходит без ошибок
- [ ] Добавлены тесты для shared/formulas.py
- [ ] Добавлены тесты для shared/geo.py

---

## Проверка

```bash
cd backend

# Все тесты
pytest tests/ -v

# Только calculators
pytest tests/calculators/ -v

# Только shared
pytest tests/shared/ -v

# С coverage
pytest tests/ -v --cov=app --cov-report=html
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 7 - update tests for new structure

- Update all calculator test imports to features/
- Add tests for shared/formulas.py
- Add tests for shared/geo.py
- All tests passing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-7-tests
```

---

## Финальная проверка рефакторинга

После Phase 7:

```bash
# 1. Все тесты проходят
cd backend && pytest tests/ -v

# 2. Backend запускается
uvicorn app.main:app --reload

# 3. Bot запускается
cd ../bot && python main.py

# 4. PostgreSQL работает
docker-compose up -d
alembic upgrade head
```

Если всё работает — рефакторинг завершён!

---

*Phase 7 — Update Tests*
