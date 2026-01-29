# Claude Code Rules for GPX Predictor

## Перед началом работы

1. **ВСЕГДА** читай `docs/ARCHITECTURE.md` для понимания структуры проекта
2. **ВСЕГДА** читай `docs/ARCHITECTURE_CALCULATIONS.md` перед изменением расчётов
3. **ВСЕГДА** проверяй `docs/CODE_REVIEW.md` для известных проблем

---

## Структура проекта (после рефакторинга v2)

```
backend/app/
├── api/v1/routes/           # API endpoints
├── features/                # Feature-based modules (NEW!)
│   ├── gpx/                 # GPX parsing & storage
│   │   ├── parser.py        # GPXParserService
│   │   ├── segmenter.py     # RouteSegmenter
│   │   ├── repository.py    # GPXRepository
│   │   └── models.py        # GPXFile model
│   │
│   ├── hiking/              # Hiking predictions
│   │   ├── calculators/     # Tobler, Naismith calculators
│   │   │   ├── tobler.py
│   │   │   ├── naismith.py
│   │   │   └── personalization.py
│   │   └── models.py        # UserPerformanceProfile
│   │
│   ├── trail_run/           # Trail running predictions
│   │   ├── calculators/     # GAP, fatigue calculators
│   │   │   ├── gap_calculator.py
│   │   │   ├── hike_run_threshold.py
│   │   │   └── runner_fatigue.py
│   │   └── models.py        # UserRunProfile
│   │
│   ├── strava/              # Strava integration
│   │   ├── client.py        # StravaClient
│   │   ├── sync/            # Background sync
│   │   └── models.py        # StravaToken, StravaActivity
│   │
│   └── users/               # User management
│       └── models.py        # User, Notification
│
├── shared/                  # Shared utilities (NEW!)
│   ├── geo.py               # haversine(), calculate_total_distance()
│   ├── elevation.py         # smooth_elevations()
│   ├── calculator_types.py  # MacroSegment, SegmentType, RouteComparison
│   └── formulas.py          # tobler_hiking_speed(), etc.
│
├── services/                # Cross-feature services (legacy location)
│   ├── prediction.py        # Main prediction orchestrator
│   ├── naismith.py          # old_naismith (3rd calculation method!)
│   ├── sun.py               # Sunrise/sunset calculations
│   ├── user_profile.py      # Profile calculation service
│   └── calculators/
│       ├── base.py          # Base calculator classes
│       └── comparison.py    # ComparisonService
│
├── models/                  # SQLAlchemy models (re-exports)
├── schemas/                 # Pydantic schemas
└── repositories/            # Data access (re-exports)
```

---

## Калькуляторы времени

В проекте **3 метода расчёта hiking** (все нужны, НЕ удалять и НЕ объединять):

| Метод | Файл | Описание |
|-------|------|----------|
| `tobler` | `features/hiking/calculators/tobler.py` | Tobler's Hiking Function (1993) |
| `naismith` | `features/hiking/calculators/naismith.py` | Naismith + Langmuir corrections |
| `old_naismith` | `services/naismith.py` | Naismith + Tranter's corrections |

Они дают **разные результаты** — это нормально:
```
tobler:       5ч 28мин
naismith:     5ч 15мин
old_naismith: 6ч 26мин
```

**Trail Running** использует:
- `features/trail_run/calculators/gap_calculator.py` — Grade Adjusted Pace

---

## Запреты

- **НЕ** дублировать утилиты — использовать существующие из `shared/`:
  - `haversine` → `shared/geo.py`
  - `elevation smoothing` → `shared/elevation.py`
  - `tobler_hiking_speed` → `shared/formulas.py`

- **НЕ** создавать новые методы для token refresh/exchange — использовать `StravaClient`

- **НЕ** смешивать sync/async Session без явной необходимости

- **НЕ** удалять или объединять калькуляторы без явного указания

---

## Импорты: новые пути

```python
# Правильно (новые пути)
from app.features.hiking.calculators import ToblerCalculator, NaismithCalculator
from app.features.trail_run.calculators import GAPCalculator
from app.features.gpx import GPXParserService, RouteSegmenter
from app.features.strava import StravaClient
from app.shared import haversine
from app.shared.formulas import tobler_hiking_speed

# Устаревшие (работают через re-export, но лучше не использовать)
from app.services.calculators import ToblerCalculator  # → re-export
from app.models.user_profile import UserPerformanceProfile  # → re-export
```

---

## Документирование

При любых изменениях в коде:

1. **Изменения в расчётах** → обновить `docs/ARCHITECTURE_CALCULATIONS.md`
2. **Изменения в структуре** → обновить `docs/ARCHITECTURE.md`
3. **Исправление проблем из ревью** → обновить статус в `docs/CODE_REVIEW.md`
4. **Новые сервисы/модели** → добавить в `docs/ARCHITECTURE.md`

---

## Правила реализации больших фич

### Ограничение размера плана

**КРИТИЧНО:** Перед началом реализации проверь размер плана:
- Если план > 300 строк — **ОБЯЗАТЕЛЬНО** предупреди пользователя
- Предложи разбить на независимые части (максимум 200-300 строк каждая)
- Каждая часть должна быть самодостаточной и тестируемой

Сообщение пользователю:
```
⚠️ План слишком большой ({N} строк).
Рекомендую разбить на части:
- Part 1: {название} (~X строк)
- Part 2: {название} (~Y строк)
...
Реализовать по частям с проверкой каждой?
```

### Чеклист интеграции компонентов

При создании нового сервиса/функции **ОБЯЗАТЕЛЬНО** проверь:

1. **Где вызывается?**
   - [ ] Найти все места, где компонент должен использоваться
   - [ ] Добавить вызовы в эти места
   - [ ] Проверить импорты

2. **Кто вызывает его?**
   - [ ] Если это callback/hook — убедиться, что он зарегистрирован
   - [ ] Если это middleware — добавить в цепочку

3. **Интеграция между модулями:**
   - [ ] Если функция в модуле A должна вызываться из модуля B — проверить оба модуля

### Условная логика

Если в плане есть условия типа:
- "пропустить шаг если..."
- "показать только когда..."
- "использовать если есть..."

**ОБЯЗАТЕЛЬНО:**
1. Явно реализовать проверку условия
2. Добавить обе ветки (if/else)
3. Протестировать оба сценария

### Верификация после реализации

После завершения реализации **ОБЯЗАТЕЛЬНО:**

1. Перечитать исходный план
2. Для каждого пункта плана проверить:
   - [ ] Реализован ли функционал?
   - [ ] Подключен ли к основному flow?
   - [ ] Работает ли интеграция?

3. Создать краткий отчёт:
```
✅ Реализовано: [список]
⚠️ Частично: [список с причинами]
❌ Не реализовано: [список с причинами]
```

### Правило "не забудь подключить"

Создал файл/функцию → Проверь:
- [ ] Добавлен ли import в `__init__.py`?
- [ ] Зарегистрирован ли router в main.py?
- [ ] Вызывается ли функция там, где нужно?
- [ ] Есть ли путь от user action до этого кода?

### Константы и конфигурация

Если создал константу (например, `PROGRESS_NOTIFICATION_INTERVAL = 30`):
- [ ] Убедись, что она **используется** в коде
- [ ] Константа без использования = забытая логика

---

## Известные проблемы (TODO)

См. `docs/CODE_REVIEW.md` для полного списка. Ключевые:

1. **Персонализация требует рефакторинга** (отдельная задача)
2. **Legacy re-exports** — старые пути работают через re-export, но новый код должен использовать `features/` и `shared/`

---

## История рефакторинга

- **v2.0** (2026-01-27): Feature-based structure, shared utilities
- **v2.1** (2026-01-28): Async migration, cleanup
- **v2.2** (2026-01-28): Post-refactor analysis

См. `docs/codereview/v2_codereview_phases/` для детальной истории.
