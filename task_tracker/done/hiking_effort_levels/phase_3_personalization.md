# Фаза 3: Персонализация с effort levels + ComparisonService

**~250 строк кода**

## Задачи

### 3.1 Добавить effort levels в HikePersonalizationService

**Файл:** `backend/app/features/hiking/calculators/personalization.py`

Текущая версия — нет параметра `effort`, нет чтения перцентилей, только 7-cat.

**Изменения:**

1. **Конструктор** — добавить `effort: EffortLevel = EffortLevel.MODERATE`:
   ```python
   from app.shared.calculator_types import EffortLevel

   def __init__(
       self,
       profile: UserHikingProfile,
       use_extended_gradients: bool = False,
       effort: EffortLevel = EffortLevel.MODERATE,
   ):
       super().__init__(use_extended_gradients)
       self.profile = profile
       self._effort = effort
       self.use_11_categories = bool(
           profile and getattr(profile, 'gradient_paces', None)
       )
   ```

2. **`_get_pace_for_category()`** — читать перцентили по effort level:
   ```python
   MIN_SAMPLES_FOR_CATEGORY = 5

   def _get_pace_for_category(self, category: str) -> Optional[float]:
       # Check sample count
       sample_count = self.profile.get_sample_count_extended(category)
       if sample_count < MIN_SAMPLES_FOR_CATEGORY:
           return None  # Fall back to Tobler

       # Try percentile first (based on effort level)
       percentile_key = self._effort.percentile_key  # "p25", "p50", "p75"
       pace = self.profile.get_percentile(category, percentile_key)
       if pace is not None:
           return pace

       # Fallback to avg (no percentiles available)
       return self.profile.get_pace_for_category(category)
   ```

   Текущий `_get_pace_for_category()` (строка 80) напрямую маппит на `self.profile.avg_*` поля. Новая версия вызывает хелпер-метод, который проверяет JSON → fallback.

### 3.2 Добавить effort levels в ComparisonService

**Файл:** `backend/app/services/calculators/comparison.py`

Текущая версия (строка 130-137) создаёт один `PersonalizationService`. Нужно создать 3 (по одному на effort level).

**Изменения в `compare_route()`:**

1. **Создать 3 personalization service** (вместо одного):
   ```python
   personalization_by_effort = {}
   if PersonalizationService.is_profile_valid(user_profile):
       for effort in EffortLevel:
           personalization_by_effort[effort] = PersonalizationService(
               user_profile, use_extended_gradients, effort=effort
           )
       # Default (MODERATE) for backward compat
       personalization = personalization_by_effort[EffortLevel.MODERATE]
       is_personalized = True
       activities_used = user_profile.total_activities_analyzed
   ```

2. **Добавить effort totals** в `method_totals`:
   ```python
   if personalization_by_effort:
       for effort in EffortLevel:
           method_totals[f"tobler_personalized_{effort.value}"] = 0.0
           method_totals[f"naismith_personalized_{effort.value}"] = 0.0
   ```

3. **В цикле по сегментам** — считать для каждого effort:
   ```python
   for effort, pers in personalization_by_effort.items():
       for base_method in ["tobler", "naismith"]:
           result = pers.calculate_segment(segment, base_method)
           key = f"{base_method}_personalized_{effort.value}"
           method_totals[key] += result.time_hours
           # Сохранять в SegmentComparison.methods только MODERATE
           # (чтобы не раздувать сегменты)
   ```

4. **Легаси ключи** `tobler_personalized`, `naismith_personalized` — оставить (= MODERATE).

5. **Обновить descriptions** — добавить effort descriptions.

### 3.3 НЕ трогать

- `PredictionService.predict_hike()` — оставить как есть (использует старую персонализацию)
- `TrailRunService` — не трогать
- `RunPersonalizationService` — не трогать

## Проверка

- [ ] `HikePersonalizationService(profile, effort=EffortLevel.FAST)` — использует P25
- [ ] `ComparisonService.compare_route()` — возвращает totals с `*_fast`, `*_moderate`, `*_easy`
- [ ] Legacy ключи `tobler_personalized`, `naismith_personalized` — работают (= moderate)
- [ ] Fallback на Tobler когда `sample_count < 5`
- [ ] Существующие тесты не ломаются
