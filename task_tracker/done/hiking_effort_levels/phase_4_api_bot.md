# Фаза 4: API + бот

**~150 строк кода**

## Задачи

### 4.1 API: gradient_paces в HikingProfileResponse

**Файл:** `backend/app/api/v1/routes/profiles.py`

1. **`HikingProfileResponse`** (строка 39) — добавить:
   ```python
   # 11-category gradient data (JSON)
   gradient_paces: Optional[dict] = None
   gradient_percentiles: Optional[dict] = None
   ```

2. **GET handler** `get_hiking_profile()` (строка 128) — добавить в return:
   ```python
   gradient_paces=profile.gradient_paces,
   gradient_percentiles=profile.gradient_percentiles,
   ```

### 4.2 Бот: 11 категорий в format_hike_profile

**Файл:** `bot/handlers/profile.py`

**`format_hike_profile()`** (строка 24) — обновить для 11 категорий.

Аналогично тому, как сделано в `format_run_profile()` (строка 98):

```python
def format_hike_profile(profile: dict) -> str:
    # Try 11-category from gradient_paces JSON
    gradient_paces = profile.get("gradient_paces")
    if gradient_paces:
        for key, label in _HIKE_GRADIENT_CATEGORIES:  # 11-cat list
            cat_data = gradient_paces.get(key, {})
            pace = cat_data.get("avg")
            samples = cat_data.get("samples", 0)
            ...
    else:
        # Fallback to legacy 7 categories (existing code)
        ...
```

Добавить константу `_HIKE_GRADIENT_CATEGORIES` (переиспользовать `_RUN_GRADIENT_CATEGORIES` — те же 11 категорий, те же русские лейблы).

### 4.3 Бот: effort levels в hiking prediction output

**Файл:** `bot/handlers/prediction.py`

**`format_full_prediction()`** (строка 97) — после существующих `tobler_personalized` и `naismith_personalized`, добавить effort breakdown:

```python
# Effort levels (if available)
if "tobler_personalized_fast" in totals:
    result += "\n🎯 <b>Персональный (по уровню нагрузки):</b>\n"
    result += f"  🔥 Fast:     tobler {format_time(totals['tobler_personalized_fast'])} "
    result += f"| naismith {format_time(totals['naismith_personalized_fast'])}\n"
    result += f"  ⚡ Moderate:  tobler {format_time(totals['tobler_personalized_moderate'])} "
    result += f"| naismith {format_time(totals['naismith_personalized_moderate'])}\n"
    result += f"  🚶 Easy:     tobler {format_time(totals['tobler_personalized_easy'])} "
    result += f"| naismith {format_time(totals['naismith_personalized_easy'])}\n"

    result += "\n"
    result += "🔥 Fast — быстрый / гоночный темп\n"
    result += "   ⚡ Moderate — обычная тренировка\n"
    result += "   🚶 Easy — лёгкий / разведка\n"
```

### 4.4 НЕ трогать

- `format_run_profile()` — уже обновлён
- `format_trail_run_result()` — уже обновлён
- `HikingClient` / `HikePrediction` — не нужно менять (effort приходит через comparison)
- Onboarding тексты — уже обновлены для 11 категорий

## Проверка

- [ ] GET `/profiles/{id}/hiking` возвращает `gradient_paces` и `gradient_percentiles`
- [ ] `/profile` в боте показывает 11 категорий (если JSON доступен) или 7 (fallback)
- [ ] Hiking prediction показывает effort levels (Fast/Moderate/Easy) если профиль есть
- [ ] HTML-escaping работает (`&lt;`, `&gt;` в gradient labels)
- [ ] Существующие тесты не ломаются
