# Фаза 2: Расчёт hiking профиля (IQR + 11-cat + percentiles)

**~200 строк кода**

## Задачи

### 2.1 Переписать `calculate_profile_with_splits()` для hiking

**Файл:** `backend/app/services/user_profile.py`

Текущая версия (строка 209) использует только 7-cat классификацию, без IQR и перцентилей.
Переписать по образцу `calculate_run_profile_with_splits()` (строка 507).

**Что изменить:**

1. **Добавить 11-cat классификацию** (параллельно с legacy 7-cat):
   ```python
   splits_by_category_11 = {cat: [] for cat in GRADIENT_THRESHOLDS}

   for split in splits:
       # Existing 7-cat classification stays
       # Add:
       category_11 = classify_gradient(gradient)
       splits_by_category_11[category_11].append(pace)
   ```

2. **Применить IQR фильтрацию per 11-category** (уже есть `filter_outliers_iqr()`):
   ```python
   gradient_paces_json = {}
   gradient_percentiles_json = {}

   for category, paces in splits_by_category_11.items():
       if not paces:
           continue
       filtered = filter_outliers_iqr(paces)
       if not filtered:
           continue

       avg_pace = mean(filtered)
       percentiles = calculate_percentiles(filtered)

       gradient_paces_json[category] = {
           'avg': round(avg_pace, 2),
           'samples': len(filtered),
       }
       if percentiles:
           gradient_percentiles_json[category] = percentiles
   ```

3. **Legacy 7-cat через weighted average** (как в run):
   ```python
   legacy_paces = {}
   for new_cat, data in gradient_paces_json.items():
       legacy_name = LEGACY_CATEGORY_MAPPING.get(new_cat)
       if legacy_name:
           legacy_paces.setdefault(legacy_name, []).append(
               (data['avg'], data['samples'])
           )

   # Weighted average
   extended_paces = {}
   legacy_sample_counts = {}
   for legacy_name, entries in legacy_paces.items():
       total_samples = sum(s for _, s in entries)
       if total_samples > 0:
           weighted_avg = sum(avg * s for avg, s in entries) / total_samples
           extended_paces[legacy_name] = round(weighted_avg, 2)
           legacy_sample_counts[legacy_name] = total_samples
   ```

4. **Сохранять JSON + sample counts** в профиль:
   ```python
   profile.gradient_paces = gradient_paces_json
   profile.gradient_percentiles = gradient_percentiles_json
   profile.flat_sample_count = legacy_sample_counts.get('flat', 0)
   # ... etc для остальных 6 legacy categories
   ```

### 2.2 НЕ трогать

- `calculate_profile()` (basic, без splits) — оставить как есть
- `_classify_gradient()` — оставить (legacy 7-cat для обратной совместимости)
- `_calculate_vertical_ability()` — оставить

## Проверка

- [ ] `calculate_profile_with_splits()` сохраняет `gradient_paces` JSON с 11 категориями
- [ ] `gradient_percentiles` JSON содержит P25/P50/P75
- [ ] Legacy 7-cat avg_* поля заполняются через weighted average
- [ ] Sample counts заполняются
- [ ] IQR фильтрация применяется (видно в логах)
- [ ] Существующие тесты не ломаются
