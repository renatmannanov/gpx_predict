# Claude Code Rules for GPX Predict

## Вопрос ≠ задача

- Если пользователь задаёт вопрос — **ОТВЕЧАЙ** на вопрос (ресерч, данные, анализ)
- **НЕ** начинай писать/менять код пока пользователь явно не скажет "сделай", "добавь", "поменяй"
- Если хочешь предложить решение — опиши словами, дождись подтверждения

---

## Перед началом работы

1. **ВСЕГДА** читай `docs/ARCHITECTURE.md` для понимания структуры проекта
2. **ВСЕГДА** читай `docs/CALCULATIONS.md` перед изменением расчётов

---

## Выполнение планов

- Если план записан в файле (`docs/task_tracker/todo/`), **ВСЕГДА** иди по файлу как единственному источнику правды
- Выполняй задачи **в порядке из файла**, а не по памяти
- После каждого шага перечитывай файл плана, чтобы убедиться что делаешь следующий шаг правильно
- Не путай нумерацию разделов ("Задачи") с порядком реализации ("Порядок реализации")

## После compaction контекста

- **ОБЯЗАТЕЛЬНО** перечитай файл плана, по которому работаешь
- **ОБЯЗАТЕЛЬНО** перечитай файлы, которые активно модифицируешь
- Сверь текущее состояние с планом перед продолжением работы

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

- **НЕ** делать Alembic revision ID длиннее 32 символов — Alembic хранит их в `varchar(32)` по умолчанию. Формат: `NNN_краткое_описание` (например `008_add_onboarding`, не `008_add_onboarding_and_notifications`)

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

## Git Commits

**Commit messages must be in English only.**

Format: [Conventional Commits](https://www.conventionalcommits.org/)
```
<type>(<scope>): <description>

[optional body]
```

Examples:
```
feat(trail-run): add GAP calculation for entire route
fix(strava): handle token refresh edge case
refactor(hiking): extract shared utilities
docs: update ARCHITECTURE.md
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

---

## Навигация по docs/

```
docs/
├── ARCHITECTURE.md          # Структура проекта (читать ВСЕГДА)
├── CALCULATIONS.md          # Детали расчётов (читать при изменении расчётов)
├── insights/                # Справочные данные (результаты гонок, аналитика) — МОЖНО читать
├── shareable/               # Промпты/шаблоны для других проектов — НЕ читать без запроса
└── task_tracker/
    ├── todo/                # Текущие задачи и планы — МОЖНО читать
    ├── backlog/             # Отложенные задачи — МОЖНО читать
    ├── done/                # Выполненное — НЕ читать без запроса пользователя
    └── archieve/            # Неактуальное — НЕ читать без запроса пользователя
```

**КРИТИЧНО:** НЕ заходить в `docs/task_tracker/done/` и `docs/task_tracker/archieve/` самостоятельно — только по прямому запросу пользователя. Это экономит контекст и токены.

---

## Документирование

При любых изменениях в коде:

1. **Изменения в расчётах** → обновить `docs/CALCULATIONS.md`
2. **Изменения в структуре** → обновить `docs/ARCHITECTURE.md`
3. **Новые сервисы/модели** → добавить в `docs/ARCHITECTURE.md`

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

### Смена подхода / переделка реализации

**КРИТИЧНО:** При смене подхода к реализации (например, с варианта А на вариант Б):

1. **Удалить код от предыдущего подхода:**
   - [ ] Найти ВСЕ изменения, сделанные для предыдущего варианта
   - [ ] Удалить функции/handlers, которые больше не нужны
   - [ ] Удалить неиспользуемые импорты
   - [ ] Проверить, что не осталось "мёртвого кода"

2. **Перед реализацией нового подхода:**
   - [ ] Убедиться, что кодовая база "чистая" от предыдущих попыток
   - [ ] Не оставлять код "на всякий случай"

3. **Проверка после переделки:**
   ```
   Удалено от предыдущего подхода:
   - [файл:строки] — описание

   Добавлено для нового подхода:
   - [файл:строки] — описание
   ```

---

## Финальный чеклист (после завершения фичи)

**КРИТИЧНО:** После завершения любой фичи пройди этот чеклист:

### Код
- [ ] Все новые файлы добавлены в соответствующие `__init__.py`
- [ ] Новые роуты зарегистрированы в `main.py` / `router.py`
- [ ] Новые функции вызываются там, где нужно (есть путь от user action до кода)
- [ ] Все созданные константы реально используются в коде

### Документация
- [ ] `docs/ARCHITECTURE.md` обновлён (структура, новые сервисы/модели)
- [ ] `docs/CALCULATIONS.md` обновлён (если менялись расчёты)
- [ ] Внешние интеграции добавлены в секцию "Внешние интеграции"

### Отчёт
После завершения — краткий отчёт:
```
✅ Реализовано: [список]
⚠️ Частично: [список с причинами]
❌ Не реализовано: [список с причинами]
📝 Документация: обновлена/не требуется
```

---

## Деплой и миграция данных

### Railway
- **Сервис:** `gpxpredict-production.up.railway.app`
- **Кастомный домен:** `ayda.run`
- **Автодеплой:** push в `main` → Railway билдит из Dockerfile
- **DATABASE_PUBLIC_URL** хранится в `backend/.env`

### Миграция данных local → prod

**ВСЕГДА используй COPY формат (CSV), НИКОГДА `--inserts`.**
`--inserts` = 1 запрос на строку по сети = часы. COPY = потоком = секунды.

```bash
# 1. Экспорт из локальной БД (с фильтрацией если нужно)
PGPASSWORD=secret psql -h localhost -U gpx_predictor -d gpx_predictor -c "\copy (SELECT * FROM races WHERE id NOT LIKE '%_am_kz') TO '/tmp/races.csv' CSV HEADER"

# 2. Импорт на прод
PGPASSWORD=<prod_password> psql -h <prod_host> -p <prod_port> -U postgres -d railway -c "\copy races FROM '/tmp/races.csv' CSV HEADER"
```

Порядок загрузки (FK зависимости):
1. `clubs`, `runners` (независимые)
2. `races`
3. `race_editions` (→ races)
4. `race_distances` (→ race_editions)
5. `race_results` (→ race_distances, runners)

Перед повторной загрузкой: `TRUNCATE race_results, race_distances, race_editions, races, runners, clubs CASCADE`

### Гонки Алматы Марафон
- ID с суффиксом `_am_kz` — **НЕ загружать на прод** (данные грязные)
- На фронте отфильтрованы в API, но лучше не засорять продовую БД

---

## Известные проблемы (TODO)

1. **Персонализация требует рефакторинга** (отдельная задача)
2. **Legacy re-exports** — старые пути работают через re-export, но новый код должен использовать `features/` и `shared/`
