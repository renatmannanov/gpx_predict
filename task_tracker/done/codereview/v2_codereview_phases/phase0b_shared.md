# Phase 0b: Create Shared Utilities

> **Статус:** Не начато
> **Оценка:** ~100 строк
> **Зависимости:** Phase 0a
> **Ветка:** `refactor/phase-0b-shared`
> **Цель:** Вынести общие утилиты в shared/, устранить дублирование

---

## Проблема

Дублирование утилит в разных файлах:
- `haversine()` — в `gpx_parser.py` и `segmenter.py`
- `smooth_elevations()` — в нескольких местах
- Нет единого места для констант

---

## Задачи

### 0b.1 Создать shared/geo.py
- [ ] Создать файл с функциями:
  ```python
  """
  Geographic utility functions.

  This is the SINGLE SOURCE OF TRUTH for geographic calculations.
  DO NOT duplicate these functions elsewhere.
  """
  import math
  from typing import Tuple

  # Earth radius in kilometers
  EARTH_RADIUS_KM = 6371.0


  def haversine(
      lat1: float, lon1: float,
      lat2: float, lon2: float
  ) -> float:
      """
      Calculate great-circle distance between two points.

      Args:
          lat1, lon1: First point coordinates (degrees)
          lat2, lon2: Second point coordinates (degrees)

      Returns:
          Distance in kilometers
      """
      lat1_rad = math.radians(lat1)
      lat2_rad = math.radians(lat2)
      delta_lat = math.radians(lat2 - lat1)
      delta_lon = math.radians(lon2 - lon1)

      a = (
          math.sin(delta_lat / 2) ** 2 +
          math.cos(lat1_rad) * math.cos(lat2_rad) *
          math.sin(delta_lon / 2) ** 2
      )
      c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

      return EARTH_RADIUS_KM * c


  def calculate_gradient(
      distance_km: float,
      elevation_diff_m: float
  ) -> float:
      """
      Calculate gradient as decimal.

      Args:
          distance_km: Horizontal distance in km
          elevation_diff_m: Elevation difference in meters

      Returns:
          Gradient as decimal (0.10 = 10%)
      """
      if distance_km <= 0:
          return 0.0
      return elevation_diff_m / (distance_km * 1000)


  def gradient_to_percent(gradient: float) -> float:
      """Convert gradient decimal to percent."""
      return gradient * 100


  def gradient_to_degrees(gradient: float) -> float:
      """Convert gradient decimal to degrees."""
      return math.degrees(math.atan(gradient))
  ```

### 0b.2 Создать shared/elevation.py
- [ ] Создать файл:
  ```python
  """
  Elevation processing utilities.

  This is the SINGLE SOURCE OF TRUTH for elevation calculations.
  """
  from typing import List, Tuple


  def smooth_elevations(
      elevations: List[float],
      window_size: int = 5
  ) -> List[float]:
      """
      Smooth elevation data using moving average.

      Args:
          elevations: Raw elevation values
          window_size: Size of smoothing window (odd number recommended)

      Returns:
          Smoothed elevation values
      """
      if len(elevations) < window_size:
          return elevations

      smoothed = []
      half_window = window_size // 2

      for i in range(len(elevations)):
          start = max(0, i - half_window)
          end = min(len(elevations), i + half_window + 1)
          window = elevations[start:end]
          smoothed.append(sum(window) / len(window))

      return smoothed


  def calculate_elevation_changes(
      elevations: List[float]
  ) -> Tuple[float, float]:
      """
      Calculate total elevation gain and loss.

      Args:
          elevations: List of elevation values

      Returns:
          Tuple of (gain_m, loss_m)
      """
      gain = 0.0
      loss = 0.0

      for i in range(1, len(elevations)):
          diff = elevations[i] - elevations[i - 1]
          if diff > 0:
              gain += diff
          else:
              loss += abs(diff)

      return gain, loss
  ```

### 0b.3 Создать shared/formatters.py
- [ ] Создать файл:
  ```python
  """
  Formatting utilities for display.

  Used by both backend and bot.
  """


  def format_time_hours(hours: float) -> str:
      """
      Format hours as 'Xч Yмин'.

      Args:
          hours: Time in hours (e.g., 2.5)

      Returns:
          Formatted string (e.g., '2ч 30мин')
      """
      if hours < 0:
          return "—"

      total_minutes = int(hours * 60)
      h = total_minutes // 60
      m = total_minutes % 60

      if h == 0:
          return f"{m}мин"
      elif m == 0:
          return f"{h}ч"
      else:
          return f"{h}ч {m}мин"


  def format_pace(pace_min_km: float | None) -> str:
      """
      Format pace as 'M:SS мин/км'.

      Args:
          pace_min_km: Pace in minutes per km

      Returns:
          Formatted string (e.g., '6:30 мин/км')
      """
      if pace_min_km is None:
          return "—"

      minutes = int(pace_min_km)
      seconds = int((pace_min_km - minutes) * 60)

      return f"{minutes}:{seconds:02d} мин/км"


  def format_distance_km(km: float) -> str:
      """
      Format distance.

      Args:
          km: Distance in kilometers

      Returns:
          Formatted string (e.g., '12.5 км' or '850 м')
      """
      if km < 1:
          return f"{int(km * 1000)} м"
      return f"{km:.1f} км"


  def format_elevation(meters: float) -> str:
      """
      Format elevation with sign.

      Args:
          meters: Elevation in meters

      Returns:
          Formatted string (e.g., '+850 м')
      """
      if meters >= 0:
          return f"+{int(meters)} м"
      return f"{int(meters)} м"
  ```

### 0b.4 Обновить shared/__init__.py
- [ ] Экспортировать все функции:
  ```python
  """
  Shared utilities (NOT business logic).

  Usage:
      from app.shared import haversine, smooth_elevations
      from app.shared.formatters import format_time_hours
  """
  from .geo import (
      haversine,
      calculate_gradient,
      gradient_to_percent,
      gradient_to_degrees,
      EARTH_RADIUS_KM,
  )
  from .elevation import (
      smooth_elevations,
      calculate_elevation_changes,
  )
  from .formatters import (
      format_time_hours,
      format_pace,
      format_distance_km,
      format_elevation,
  )

  __all__ = [
      # geo
      "haversine",
      "calculate_gradient",
      "gradient_to_percent",
      "gradient_to_degrees",
      "EARTH_RADIUS_KM",
      # elevation
      "smooth_elevations",
      "calculate_elevation_changes",
      # formatters
      "format_time_hours",
      "format_pace",
      "format_distance_km",
      "format_elevation",
  ]
  ```

---

## Файлы для создания

```
NEW:
backend/app/shared/geo.py
backend/app/shared/elevation.py
backend/app/shared/formatters.py

UPDATE:
backend/app/shared/__init__.py
```

---

## Критерии завершения

- [ ] `shared/geo.py` создан с `haversine()`
- [ ] `shared/elevation.py` создан с `smooth_elevations()`
- [ ] `shared/formatters.py` создан
- [ ] `shared/__init__.py` экспортирует все функции
- [ ] Приложение запускается

---

## Важно

На этом этапе мы НЕ меняем импорты в существующем коде. Это будет сделано в следующих фазах (0c-0f) при переносе модулей.

---

## Проверка

```bash
cd backend
python -c "from app.shared import haversine; print(haversine(43.0, 76.0, 43.1, 76.1))"
# Должно вывести ~14.7 км
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0b - create shared utilities

- Add shared/geo.py with haversine()
- Add shared/elevation.py with smooth_elevations()
- Add shared/formatters.py
- Export all from shared/__init__.py

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0b-shared
```

Перейти к Phase 0c (или 0c + 0d параллельно).

---

*Phase 0b — Create Shared Utilities*
