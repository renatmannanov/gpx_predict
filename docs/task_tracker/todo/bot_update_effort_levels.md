# План: Bot Update + Race→Fast rename

## Контекст

После Phase 0-3 (IQR, 11 категорий, перцентили, effort levels) бот не обновлён:
- Показывает 7 категорий вместо 11
- Не показывает effort levels (Fast/Moderate/Easy)
- Enum до сих пор называет Race вместо Fast
- Онбординг описывает 7 категорий
- API не возвращает gradient_paces/gradient_percentiles

## Задачи

### 1. Rename Race → Fast (backend)

**Файлы:**
- `backend/app/shared/calculator_types.py` — enum `RACE="race"` → `FAST="fast"`, dict key `"race"` → `"fast"`
- `backend/app/features/trail_run/service.py` — ключи totals: `all_run_personalized_race` → `all_run_personalized_fast`, аналогично для `run_hike_*_race`
- `backend/tools/calibration/calculators.py` — dataclass fields `personalized_race` → `personalized_fast`, `EffortLevel.RACE` → `EffortLevel.FAST`
- `backend/tools/calibration/report.py` — display names: "P.Race"→"P.Fast", "Pers. Race"→"Pers. Fast", header и CSV
- `backend/tools/calibration/service.py` — mode presets: `"personalized_race"` → `"personalized_fast"`
- `backend/tools/calibration/cli.py` — click.Choice: `"race"` → `"fast"`

### 2. Бот — вывод предсказания trail run

**Файл:** `bot/handlers/trail_run.py`

Текущий `_format_gap_results()` (строка 28) добавляет один `🎯 Персональный`. Нужно:

**`_format_gap_results()`** — убрать строку с одним персональным, вместо этого добавить блок:
```
🎯 ПЕРСОНАЛЬНЫЙ:
  🔥 Fast             3:57
  ⚡ Moderate          4:29
  🚶 Easy             5:14
```
Ключи из totals: `all_run_personalized_fast`, `all_run_personalized_moderate`, `all_run_personalized_easy`.

**`_format_run_hike_results()`** (строка 48) — оставить `🎯 Перс + Tobler` и `🎯 Перс + Naismith` как есть (Moderate по умолчанию), добавить блок с effort levels после них:
```
  🎯 Перс + Tobler     4:37
  🎯 Перс + Naismith   4:37
  🎯 Перс + Tobler (effort):
     🔥 Fast           3:57
     ⚡ Moderate        4:37
     🚶 Easy           5:14
```
Ключи: `run_hike_personalized_tobler_fast`, `run_hike_personalized_tobler_moderate`, `run_hike_personalized_tobler_easy`.

**`format_trail_run_result()`** (строка 73):
- Внизу, после персонализации, добавить легенду:
```
💡 Fast — гоночный/асфальтовый темп
   Moderate — обычная тренировка
   Easy — лёгкий бег / разведка
```

**`_format_gradient_profile()`** (строка 204) — обновить для 11 категорий:
- Брать данные из `run_profile.gradient_paces` JSON (11 категорий) вместо 7-cat legacy
- Если JSON недоступен, fallback на текущие 7 категорий

**`_build_run_profile_info()`** в `service.py` (строка 536) — обновить для 11 категорий:
- Читать из `gradient_paces` JSON
- Менять `categories_total` с 7 на 11
- Обновить labels для 11 категорий

### 3. Бот — профиль (/profile)

**Файл:** `bot/handlers/profile.py`

**`format_run_profile()`** (строка 71):
- Показывать 11 категорий вместо 7
- Брать данные из `gradient_paces` JSON (через API)
- Русские labels: "Экстремальный спуск (<-23%)", "Крутой спуск (-23% до -17%)", и т.д.

**`format_hike_profile()`** (строка 24):
- Пока оставить 7 категорий (hiking profile ещё не обновлён)

### 4. API — добавить gradient_paces в response

**Файл:** `backend/app/api/v1/routes/profiles.py`

**`TrailRunProfileResponse`** (строка 74) — добавить поля:
```python
gradient_paces: Optional[dict] = None       # {category: {avg, samples}}
gradient_percentiles: Optional[dict] = None  # {category: {p25, p50, p75}}
```

**GET handler** (строка 255) — добавить эти поля при формировании response.

### 5. Онбординг — тексты

**Файл:** `bot/handlers/onboarding.py`

**`PERSONALIZATION_HIKING_TEXT`** (строка 70):
- Заменить 7 категорий на 11 с новыми русскими названиями

**`PERSONALIZATION_RUNNING_TEXT`** (строка 96):
- Заменить "но с важным отличием:" на "но со своими доработками"
- Убрать блок "Strava скажет..." — "Я это исправляю!..." (строки 101-109)
- Добавить после пункта 5 ("Строю модель усталости"):
  - Список 11 категорий
  - Описание 3 effort levels (Fast/Moderate/Easy)

## Порядок реализации

1. ✅ **Race → Fast** (backend enum + calibration tools) — commit 30fb526
2. ✅ **API: gradient_paces в response** — commit 274e04e
3. ✅ **service.py: _build_run_profile_info → 11 категорий** — commit 274e04e
4. ✅ **Бот: trail_run.py** — effort levels, убран gradient profile и сегменты — commit 7792de0
5. ✅ **Бот: profile.py** — 11 категорий из JSON — commit 7792de0
6. ✅ **Бот: onboarding.py** — тексты — commit 15a9a14

## Русские названия 11 категорий

| Ключ | Русский | Диапазон |
|------|---------|----------|
| down_23_over | Экстр. спуск | < -23% |
| down_23_17 | Крутой спуск | -23% до -17% |
| down_17_12 | Умеренный спуск | -17% до -12% |
| down_12_8 | Лёгкий спуск | -12% до -8% |
| down_8_3 | Пологий спуск | -8% до -3% |
| flat_3_3 | Ровный участок | -3% до +3% |
| up_3_8 | Пологий подъём | +3% до +8% |
| up_8_12 | Лёгкий подъём | +8% до +12% |
| up_12_17 | Умеренный подъём | +12% до +17% |
| up_17_23 | Крутой подъём | +17% до +23% |
| up_23_over | Экстр. подъём | > +23% |

## Верификация

1. `pytest backend/tests/ -x -q` — существующие тесты не ломаются
2. Запустить бота, загрузить GPX, проверить вывод trail run prediction
3. `/profile` — проверить 11 категорий
4. CLI backtest: `python -m tools.calibration backtest --effort fast` — работает
