# Фаза 0: Подготовка инфраструктуры

**Сложность:** Низкая
**Эффект:** Инфраструктура (блокирует Фазы 1-3)
**Оценка:** ~100-130 строк изменений

---

## Цель

Подготовить инфраструктуру для всех последующих фаз:
1. Убрать дублирование GRADIENT_THRESHOLDS (3 копии → 1 в shared/)
2. CLI команда для пересчёта профиля
3. Механизм сохранения snapshots профиля (история изменений)

---

## Часть 1: Вынести GRADIENT_THRESHOLDS в shared/

### Проблема

Одни и те же пороги градиентов определены в 3 файлах + идентичная функция classify:

| Файл | Имя | Функция |
|------|-----|---------|
| `backend/app/services/user_profile.py:29` | `GRADIENT_THRESHOLDS` | `_classify_gradient()` |
| `backend/app/features/hiking/calculators/personalization_base.py:21` | `GRADIENT_THRESHOLDS` | `_classify_gradient_extended()` |
| `backend/tools/calibration/metrics.py:51` | `GRADIENT_CATEGORIES` | `_get_gradient_category()` |

Все три — copy-paste с одинаковыми значениями и одинаковой логикой edge cases.

### Решение

Создать `backend/app/shared/gradients.py` **сразу с 11 категориями и новым неймингом** (объединено с Фазой 2 — чтобы не переписывать дважды).

Включает:
- `GRADIENT_THRESHOLDS` — 11 категорий
- `classify_gradient()` — единая функция классификации
- `LEGACY_CATEGORY_MAPPING` — маппинг 11 новых → 7 старых категорий
- `classify_gradient_legacy()` — для backward compatibility (возвращает старое имя)

```python
"""
Gradient classification for terrain categories.

Used by: profile calculation, personalization, calibration tools.
Single source of truth for gradient thresholds.

Naming convention: {direction}_{lower}_{upper} or {direction}_{bound}_over
  - direction: "up" or "down" (except "flat")
  - numbers: absolute gradient boundaries in percent
  - "over": unbounded extreme category
Examples: up_8_12 = uphill 8% to 12%, down_23_over = downhill steeper than -22%
"""

GRADIENT_THRESHOLDS = {
    'down_23_over': (-100.0, -23.0),   # < -23% (scrambling)
    'down_23_17':   (-23.0, -17.0),    # -23% to -17%
    'down_17_12':   (-17.0, -12.0),    # -17% to -12%
    'down_12_8':    (-12.0, -8.0),     # -12% to -8%
    'down_8_3':     (-8.0, -3.0),      # -8% to -3%
    'flat_3_3':     (-3.0, 3.0),       # -3% to +3%
    'up_3_8':       (3.0, 8.0),        # +3% to +8%
    'up_8_12':      (8.0, 12.0),       # +8% to +12%
    'up_12_17':     (12.0, 17.0),      # +12% to +17%
    'up_17_23':     (17.0, 23.0),      # +17% to +23%
    'up_23_over':   (23.0, 100.0),     # > +23% (scrambling)
}

# Маппинг 11 новых категорий → 7 старых (для backward compatibility)
LEGACY_CATEGORY_MAPPING = {
    'down_23_over': 'steep_downhill',
    'down_23_17':   'steep_downhill',
    'down_17_12':   'moderate_downhill',
    'down_12_8':    'moderate_downhill',
    'down_8_3':     'gentle_downhill',
    'flat_3_3':     'flat',
    'up_3_8':       'gentle_uphill',
    'up_8_12':      'moderate_uphill',
    'up_12_17':     'moderate_uphill',
    'up_17_23':     'steep_uphill',
    'up_23_over':   'steep_uphill',
}


def classify_gradient(gradient_percent: float) -> str:
    """Classify gradient into one of 11 categories."""
    for category, (min_grad, max_grad) in GRADIENT_THRESHOLDS.items():
        if min_grad <= gradient_percent < max_grad:
            return category
    if gradient_percent >= 23.0:
        return 'up_23_over'
    if gradient_percent <= -23.0:
        return 'down_23_over'
    return 'flat_3_3'


def classify_gradient_legacy(gradient_percent: float) -> str:
    """Classify gradient into one of 7 legacy categories (for backward compat)."""
    return LEGACY_CATEGORY_MAPPING[classify_gradient(gradient_percent)]
```

### Что менять в существующих файлах

1. **`user_profile.py`:** удалить `GRADIENT_THRESHOLDS` и `_classify_gradient()`, импортировать из shared. Hiking метод `calculate_profile_with_splits()` использует `classify_gradient_legacy()`. Run метод `calculate_run_profile_with_splits()` использует `classify_gradient()` (11 категорий) + `LEGACY_CATEGORY_MAPPING` для заполнения legacy avg_ полей.
2. **`personalization_base.py`:** удалить `GRADIENT_THRESHOLDS` и `_classify_gradient_extended()`, импортировать из shared
3. **`calibration/metrics.py`:** удалить `GRADIENT_CATEGORIES` и `_get_gradient_category()`, импортировать из shared
4. **`shared/__init__.py`:** добавить re-export

**ПРИМЕЧАНИЕ:** Hiking профиль (`calculate_profile_with_splits`) продолжает писать в legacy `avg_*` поля через `classify_gradient_legacy()`. JSON поля `gradient_paces`/`gradient_percentiles` — только для Run (Фаза 2). Hiking получит JSON позже, после обкатки на Run.

---

## Часть 2: CLI для пересчёта профиля

### Проблема

Нет способа вручную пересчитать профиль. Профиль считается только при Strava sync — чтобы увидеть эффект IQR фильтрации, нужен ручной триггер.

### Решение

Добавить команду в `backend/tools/calibration/cli.py` (или отдельный `backend/tools/profile/cli.py`):

```bash
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16
```

Команда:
1. Загружает все Run-активности пользователя со сплитами
2. Пересчитывает профиль (с текущей логикой)
3. Сохраняет snapshot "before" (см. Часть 3)
4. Обновляет профиль в БД
5. Сохраняет snapshot "after"
6. Выводит diff: было → стало

### Пример вывода

```
Profile recalculated for user 2f07778a...
Activities used: 107 (was 59)
Splits processed: 1094

                    Before    After     Diff
flat                6.85      6.87      +0.02
gentle_uphill       8.89      10.03     +1.14
moderate_uphill     11.95     14.21     +2.26
steep_uphill        14.56     21.87     +7.31  ← significant
gentle_downhill     6.52      8.16      +1.64
moderate_downhill   7.32      9.28      +1.96
steep_downhill      9.80      13.09     +3.29

Snapshot saved: profile_snapshot_2026-02-13_before.json
Snapshot saved: profile_snapshot_2026-02-13_after.json
```

---

## Часть 3: Profile Snapshots

### Цель

Сохранять каждую версию профиля для отслеживания динамики: до/после IQR, до/после перцентилей, до/после расширения категорий.

### Вариант A: Таблица в БД

```python
class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    profile_type = Column(String(20))  # "run" или "hiking"
    reason = Column(String(100))       # "phase_1_iqr", "manual_recalc", "strava_sync"
    profile_data = Column(JSON)        # полный snapshot профиля
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Вариант B: JSON файлы

```
backend/data/profile_snapshots/
├── 2f07778a_run_2026-02-13_baseline.json
├── 2f07778a_run_2026-02-13_phase1_iqr.json
├── 2f07778a_run_2026-02-14_phase2_percentiles.json
└── ...
```

**Рекомендация:** Вариант A (таблица) — удобнее для сравнения, можно загружать через API. JSON файлы легко теряются при деплое.

### Формат snapshot

```json
{
    "user_id": "2f07778a-...",
    "profile_type": "run",
    "reason": "phase_1_iqr",
    "timestamp": "2026-02-13T15:30:00",
    "activities_count": 107,
    "profile": {
        "avg_flat_pace_min_km": 6.87,
        "avg_gentle_uphill_pace_min_km": 10.03,
        "...": "...",
        "gradient_paces": { "...JSON если уже есть..." },
        "gradient_percentiles": { "...JSON если уже есть..." }
    }
}
```

---

## Чеклист

- [x] `shared/gradients.py` создан с 11 категориями, classify_gradient(), classify_gradient_legacy(), LEGACY_CATEGORY_MAPPING
- [x] `shared/__init__.py` обновлён (re-export)
- [x] `user_profile.py` — импорт из shared, удалён дубликат. Hiking → classify_gradient_legacy(). Run → classify_gradient() (11 категорий)
- [x] `personalization_base.py` — импорт из shared, удалён дубликат
- [x] `calibration/metrics.py` — импорт из shared, удалён дубликат
- [x] CLI команда `recalculate-profile` работает
- [x] Таблица `profile_snapshots` + миграция Alembic
- [x] Snapshot сохраняется при пересчёте профиля
- [x] Тесты не сломаны (все калькуляторы работают как раньше)

## Зависимости

- Нет внешних зависимостей. Чистый рефакторинг + инфраструктура.
- Градиенты сразу 11 категорий с новым неймингом (объединено с частью Фазы 2 для избежания двойного рефакторинга)
- Hiking профиль продолжает использовать legacy 7-категорий через classify_gradient_legacy()
