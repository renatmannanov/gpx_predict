# Настройка команды агентов для GPX Predict / Ayda Run

> **Статус:** v3 — после обсуждения
> **Дата:** 2026-03-14

---

## Зачем вообще агенты?

### Проблема "одного чата"

Сейчас один агент (Claude Code) делает всё: фронтенд, бэкенд, парсинг данных, деплой, дизайн, тесты. Это работает, но:

1. **Контекст размывается** — после 30 минут работы над CSS-анимациями агент "забывает" архитектуру бэкенда
2. **Нет специализации** — один промпт не может одновременно содержать гайды по React-паттернам И правила Alembic-миграций
3. **Нет проверки качества** — тот же агент, что написал код, не может его объективно ревьювить
4. **Нет UX-мышления** — агент не думает "а удобно ли это пользователю?", он думает "а работает ли код?"
5. **Деплой каждый раз как в первый раз** — повторяем одни и те же шаги с Railway/миграциями/COPY

---

## Как это работает: роли

### Кто есть кто

| Роль | Кто это | Модель |
|------|---------|--------|
| **Ренат (User)** | Ты. Принимаешь решения, ставишь задачи, утверждаешь результат | — |
| **Orchestrator** | Основной Claude Code в чате VSCode. Разбирает задачу, решает какого агента вызвать, координирует | **Opus** (наследует твои настройки) |
| **Frontend** | Субагент. React, TypeScript, Tailwind, дизайн-система | **Opus** |
| **Backend** | Субагент. FastAPI, калькуляторы, модели, API, тесты | **Opus** |
| **Data Engineer** | Субагент. Парсеры гонок, чистка данных, psql, batch-загрузка | **Opus** |
| **UX Advisor** | Субагент. Анализ UX по коду и документации, edge cases, приоритизация | **Opus** |
| **Deployer** | Субагент. Railway, деплой, smoke-test, миграция данных на прод | **Sonnet** |

> **Почему все на Opus?** Ты уже работаешь на Opus и доволен качеством. Экономить на субагентах — значит получать более слабый результат. Deployer на Sonnet, потому что его задачи детерминированные (чеклист из 8 шагов).

### Поток работы

```
  Ренат: "Хочу добавить фильтр по году на страницу гонок"
     │
     ▼
  Orchestrator (основной Claude Code в чате):
     │
     │  1. Понимает задачу
     │  2. Решает: нужен Backend (API) + Frontend (UI)
     │  3. Опционально: вызвать UX Advisor ДО или ПОСЛЕ
     │
     ├──► Backend: "Добавь query-параметр year в GET /races/{id}/results"
     │       └── Реализует, пишет тесты, обновляет docs
     │
     ├──► Frontend: "Добавь dropdown с годами, вызов API с ?year=2024"
     │       └── Реализует, проверяет TypeScript
     │
     └──► UX Advisor: "Проверь — понятен ли фильтр? Что если год только один?"
             └── Рекомендации → Orchestrator передаёт Frontend/Backend
```

**Важно:** Orchestrator (основной Claude Code) всегда решает:
- Какого агента вызвать
- В каком порядке
- Нужен ли UX Advisor до реализации, после, или и то и другое

Ренат может и напрямую попросить: "Вызови UX Advisor" или "Задеплой".

---

## Предлагаемые агенты

### 1. Frontend Developer

**Когда вызывается:** Работа с React-компонентами, страницами, стилями, TypeScript

```yaml
name: frontend
description: React/TypeScript фронтенд-разработчик для веб-портала ayda.run
tools: Read, Edit, Write, Bash, Glob, Grep
model: opus
```

**Знает:**
- Дизайн-систему (accent #E8622A, dark theme, Manrope, border-radius)
- Структуру страниц (Dashboard, Races, RaceDetail, RunnerProfile, Predict)
- Паттерны: React Query для данных, Tailwind для стилей, react-router v6
- Типы из `frontend/src/types/`
- API-клиенты из `frontend/src/api/`

**Доступ к файлам:**
- **Читает и пишет:** `frontend/` — полный доступ
- **Читает (read-only):** `backend/app/api/` — чтобы видеть API-контракты (URL, параметры, response schema)
- **Читает (read-only):** `backend/app/schemas/` — Pydantic-схемы для типизации
- **НЕ трогает:** `backend/app/features/`, `backend/app/services/`, `bot/`, `alembic/`

**Bash:** `npm run build`, `npm run dev`, `npx tsc --noEmit`

---

### 2. Backend Developer

**Когда вызывается:** API эндпоинты, бизнес-логика, модели, миграции, Strava, тесты

```yaml
name: backend
description: FastAPI/Python бэкенд-разработчик. API, калькуляторы, БД, Strava, Telegram-бот
tools: Read, Edit, Write, Bash, Glob, Grep
model: opus
```

**Знает:**
- Feature-based структуру (`features/hiking`, `features/trail_run`, `features/races`)
- 3 калькулятора хайкинга (Tobler, Naismith, old_naismith) — **не объединять!**
- GAP-калькулятор для trail run
- Shared утилиты (`shared/geo.py`, `shared/formulas.py`)
- Alembic: ID <= 32 символов, формат `NNN_description`
- PostgreSQL only, async/sync сессии
- Telegram-бот (bot/) — часть бэкенда, общие модели

**Доступ к файлам:**
- **Читает и пишет:** `backend/`, `bot/`
- **Читает (read-only):** `frontend/src/api/`, `frontend/src/types/` — чтобы видеть как фронт вызывает API
- **НЕ трогает:** `frontend/src/components/`, `frontend/src/pages/`, CSS, стили

**Bash:** `pytest`, `alembic revision`, `alembic upgrade head`, `python -m scripts.*`

**Что делает с деплоем:** Backend НЕ деплоит сам. Но при подготовке к деплою:
- Проверяет что миграции работают (`alembic upgrade head` локально)
- Проверяет что тесты проходят (`pytest`)
- Готовит commit
- Дальше передаёт Deployer-у

---

### 3. Data Engineer

**Когда вызывается:** Парсинг результатов гонок, чистка/нормализация данных, работа с данными в БД

```yaml
name: data-engineer
description: Парсинг данных гонок, чистка, загрузка, анализ данных. CLAX/AM парсеры, psql (локал + прод SELECT)
tools: Read, Edit, Write, Bash, Glob, Grep
model: opus
```

**Зачем отдельный агент (а не часть Backend)?**

Профит от выделения:
1. **Специфичные знания** — форматы CLAX, AM, myrace.info, fuzzy matching имён, FK-зависимости загрузки. Backend-у это не нужно
2. **Изолированная работа** — Data Engineer может часами парсить и чистить данные, не засоряя контекст Backend-а
3. **Разные инструменты** — Data Engineer работает с psql напрямую, сырыми CSV/XML, скриптами. Backend работает с SQLAlchemy и API
4. **Разный уровень риска** — Data Engineer может сломать данные в БД (DELETE, TRUNCATE). Backend меняет код. Разные зоны ошибок

**Знает:**
- Парсеры: `am_parser.py`, `clax_parser.py`, `batch_parse.py`
- Структуру race_results, runners, clubs, race_editions, race_distances
- FK-зависимости загрузки: clubs -> races -> editions -> distances -> results
- COPY-формат (НИКОГДА `--inserts`)
- `_am_kz` — грязные данные Алматы Марафона (не на прод)
- Дедупликацию бегунов (fuzzy matching 0.79+)
- psql-команды для экспорта/импорта

**Доступ к БД:**
- **Локальная БД** — полный доступ (SELECT, INSERT, UPDATE, DELETE, TRUNCATE)
- **Продовая БД** — только SELECT (анализ, проверка данных, сравнение с локалкой)
- **WRITE на прод** — НЕ делает, это задача Deployer-а

Зачем доступ к проду? Портал ayda.run работает на продовой БД. Data Engineer должен уметь:
- Проверить что данные корректно загрузились (`SELECT COUNT(*) FROM race_results WHERE ...`)
- Сравнить локалку с продом (сколько записей, есть ли расхождения)
- Найти проблемы с данными на проде (дубли, пустые поля)
- Анализировать реальные данные для UX Advisor ("сколько бегунов с >3 гонками?")

**Доступ к файлам:**
- **Пишет:** `backend/scripts/batch_parse.py`, `backend/scripts/parse_race.py`, `backend/app/features/races/` (парсеры, matching)
- **НЕ трогает:** API-эндпоинты, фронтенд, бот

**Bash:** `psql` (локал + прод SELECT), `python -m scripts.*`

**Граница Data Engineer vs Deployer:**
- **Data Engineer** = парсинг, чистка, загрузка в **локальную** БД, SELECT на **проде** для анализа
- **Deployer** = WRITE на **прод** (COPY данных), деплой приложения, smoke-test

---

### 4. UX Advisor

**Когда вызывается:** Анализ фичи ДО или ПОСЛЕ реализации

```yaml
name: ux-advisor
description: UX-аналитик. Анализирует фичи по коду/документации с точки зрения пользователя-бегуна
tools: Read, Glob, Grep, WebFetch, WebSearch
model: opus
permissionMode: plan  # только читает и анализирует, не может редактировать
```

**Почему Opus:** UX-анализ — это НЕ шаблонная проверка. Это глубокое понимание:
- Контекста (бегуны горных трейлов в КЗ, не программисты)
- Приоритетов (что важно для 80% пользователей vs 5%)
- Edge cases (имя на кириллице в одной гонке, латиница в другой)
- Эмоций (мотивация, сравнение с другими, гордость за результат)

Sonnet даст поверхностный чеклист. Opus даст инсайты.

**Как работает, если не может "потрогать" приложение?**

UX Advisor анализирует **код и документацию** — это его "глаза":
1. **Читает React-компоненты** — видит что рендерится, какие данные показываются, какие условия
2. **Читает API-ответы** — видит какие данные приходят с бэкенда
3. **Читает TypeScript-типы** — видит структуру данных
4. **WebFetch на ayda.run** — может загрузить реальную страницу и увидеть HTML/данные
5. **Читает docs/** — знает архитектуру и расчёты

Пример: UX Advisor читает `RunnerProfilePage.tsx` и видит:
```
if (runner.results.length === 0) return <div>Нет результатов</div>
```
→ Рекомендация: "Пустой экран демотивирует. Покажите подсказку: 'Этот бегун пока не участвовал в гонках на нашей платформе'"

**Два режима работы:**

| Режим | Когда | Что делает |
|-------|-------|-----------|
| **ДО реализации** | Ренат хочет новую фичу | Анализирует: актуально ли? для кого? какие edge cases? как должно выглядеть? |
| **ПОСЛЕ реализации** | Фича написана | Проверяет: понятно ли? удобно ли? что забыли? какие пустые состояния? |

**Как вызвать:**
- Orchestrator решает сам (видит что задача сложная / неочевидная)
- Ренат просит: "Спроси UX-а что думает" или "Пусть UX проверит"

---

### 5. Deployer

**Когда вызывается:** Деплой приложения на Railway, загрузка данных на прод

```yaml
name: deployer
description: Деплой веб-портала и Telegram-бота на Railway, миграция данных на прод
tools: Read, Bash, Glob, Grep, Edit
model: sonnet  # детерминированные шаги, чеклист — sonnet достаточно
```

**Знает:**
- Railway: `gpxpredict-production.up.railway.app`, домен `ayda.run`
- Прод БД: `trolley.proxy.rlwy.net:32647`, user postgres, db railway
- Dockerfile: multi-stage build (node + python), один деплой = и портал, и бот
- start.sh: `alembic upgrade head && uvicorn` (бот запускается внутри FastAPI)
- COPY-формат для загрузки данных
- Порядок FK: clubs -> races -> editions -> distances -> results
- `_am_kz` — НЕ загружать на прод

**Два типа деплоя:**

| Тип | Описание | Шаги |
|-----|----------|------|
| **Quick deploy** | Маленький фикс, нет миграций | git push → Railway build → health check → done |
| **Full deploy** | Новые фичи, миграции, данные | pre-checks → push → build → health → migrations → data load → smoke-test |

**Чеклист Full Deploy:**
1. `git status` — чисто?
2. `pytest` — тесты проходят?
3. `alembic upgrade head` — миграция на локалке ок?
4. `git push origin main`
5. Railway build — проверить логи
6. `curl https://ayda.run/health` — 200?
7. Smoke-test: `/api/v1/races`, `/api/v1/runners/1`
8. Миграция данных (если нужна): COPY из локалки на прод
9. Финальная проверка на проде

**Граница с Data Engineer (чтобы не было конфликтов):**
- **Data Engineer** готовит данные (парсит, чистит, загружает в локальную БД, экспортирует CSV)
- **Deployer** берёт готовые CSV и загружает на прод через COPY
- Если нужно и то и другое — Orchestrator вызывает сначала Data Engineer, потом Deployer

---

## Scripts и Tools — кому принадлежат

Текущие скрипты:

```
backend/scripts/
├── analyze_run_profile.py          → Backend (анализ trail run профилей)
├── analyze_segments.py             → Backend (анализ сегментов маршрута)
├── analyze_specific_activities.py  → Backend (анализ конкретных Strava-активностей)
├── analyze_threshold_comparison.py → Backend (сравнение порогов hike/run)
├── batch_parse.py                  → Data Engineer (batch-парсинг гонок)
├── calculate_run_profile.py        → Backend (расчёт run-профиля)
├── experiment_fine_gradients.py    → Backend (эксперименты с градиентами)
├── parse_race.py                   → Data Engineer (парсинг одной гонки)
├── predict_race.py                 → Backend (предсказание по гонке)
├── recalculate_run_profile_smart.py → Backend (перерасчёт профилей)
├── test_talgar_trail.py            → Backend (тест trail run)
├── test_talgar_trail_part2.py      → Backend (тест trail run)
└── test_trail_run_service.py       → Backend (тест сервиса)

backend/tools/calibration/
├── calculators.py                  → Backend (калибровка калькуляторов)
├── cli.py                          → Backend (CLI калибровки)
├── metrics.py                      → Backend (метрики)
├── report.py                       → Backend (отчёты)
├── service.py                      → Backend (сервис калибровки)
├── test_phase*.py                  → Backend (тесты калибровки)
└── virtual_route.py                → Backend (виртуальные маршруты)
```

**Итого:** Data Engineer владеет только `batch_parse.py` и `parse_race.py`. Остальное — Backend.

---

## Зоны ответственности

> **Чтение:** Все агенты могут ЧИТАТЬ любые файлы проекта. Ограничения ниже — только на ЗАПИСЬ.

### Frontend Developer — пишет:
- React-компоненты, страницы (`frontend/src/`)
- CSS / Tailwind стили
- TypeScript типы, API-клиенты
- npm build / tsc проверки
- Раздел "Frontend" в `ARCHITECTURE.md`

### Backend Developer — пишет:
- API-эндпоинты (`backend/app/api/`)
- SQLAlchemy-модели, Pydantic-схемы
- Alembic-миграции
- Калькуляторы (tobler, naismith, GAP)
- Strava-интеграция
- Telegram-бот (`bot/`)
- pytest тесты
- Скрипты анализа и калибровки (`scripts/`, `tools/`)
- `ARCHITECTURE.md`, `CALCULATIONS.md`

### Data Engineer — пишет:
- Парсеры гонок (`am_parser.py`, `clax_parser.py`)
- `batch_parse.py`, `parse_race.py`
- Чистка/нормализация данных
- psql на локальной БД (полный доступ)
- psql на продовой БД (только SELECT — анализ, проверка)
- Экспорт CSV для деплоя

### UX Advisor — НЕ пишет код, только анализирует:
- Анализ фичи ДО реализации (актуальность, edge cases, UX)
- Ревью фичи ПОСЛЕ реализации (удобство, пустые состояния)
- Приоритизация фичей
- Рекомендации для Frontend/Backend

### Deployer — делает:
- git push → Railway build
- Health check, smoke-test на проде
- COPY данных на прод (WRITE на продовую БД)
- Проверка логов Railway

---

## Разрешение конфликтов

### Когда непонятно какой агент нужен

| Ситуация | Решение |
|----------|---------|
| Задача на стыке фронта и бэка | Orchestrator разбивает на 2 подзадачи |
| Нужен новый API + UI | Сначала Backend (API), потом Frontend (UI) |
| Парсинг + новая модель | Data Engineer парсит, Backend добавляет модель |
| "Задеплой" + "загрузи данные" | Deployer делает всё (и push, и COPY) |
| "Нужна ли эта фича?" | UX Advisor анализирует, Ренат решает |
| Ренат говорит "просто сделай" | Orchestrator делает сам, без субагентов |

### Правило: Orchestrator всегда решает

Субагенты не вызывают друг друга. Только Orchestrator решает кого вызвать и в каком порядке. Это предотвращает:
- Бесконечные цепочки делегирования
- Дублирование работы
- Конфликты между агентами

---

## Сценарии из реальной жизни

### Сценарий 1: "Добавь фильтр по году"

```
Ренат: "Добавь фильтр по году на страницу гонок"

Orchestrator думает:
  - Нужен API (Backend) + UI (Frontend)
  - UX вопрос: а если год один? показывать dropdown из 1 элемента?

Порядок:
  1. UX Advisor (ДО): "Как должен работать фильтр? Что если 1 год?"
     → Рекомендация: "Если 1 год — не показывать dropdown, просто текст"
  2. Backend: "Добавь ?year= параметр в GET /races/{id}/results"
     → Готово, тесты пройдены
  3. Frontend: "Добавь dropdown с годами, скрой если год один"
     → Готово, TypeScript ок
  4. (опционально) UX Advisor (ПОСЛЕ): "Проверь результат"
```

### Сценарий 2: "Загрузи новую гонку"

```
Ренат: "Вот файл результатов Tengri Ultra 2025, загрузи"

Orchestrator:
  1. Data Engineer: "Распарси, почисти, загрузи в локальную БД"
     → 450 результатов загружено, 3 дубля объединены
  2. Deployer: "Экспорт CSV → COPY на прод → smoke-test"
     → На проде, /races/tengri-ultra/editions/2025 работает
```

### Сценарий 3: "Быстрый фикс на проде"

```
Ренат: "На проде сломался расчёт перцентилей, пофикси и задеплой"

Orchestrator:
  1. Backend: "Найди и пофикси баг в расчёте"
     → Фикс + тест
  2. Deployer (Quick Deploy): "Push → build → health check"
     → Задеплоено за 3 минуты
```

### Сценарий 4: "Хочу новую фичу, насколько она актуальна?"

```
Ренат: "Хочу добавить сравнение двух бегунов бок о бок. Стоит ли?"

Orchestrator:
  1. UX Advisor (ДО): Анализирует:
     - Целевая аудитория: бегуны хотят сравнивать себя с друзьями? Да, это мотивация
     - Данные: достаточно ли пересечений гонок для сравнения? Проверяет БД
     - Сложность: нужен новый API + новая страница
     → Рекомендация: "Актуально для ~30% пользователей. MVP: таблица общих гонок
       с разницей времён. Полноценная страница — фаза 2"
  2. Ренат решает: "Ок, делаем MVP"
  3. Backend → Frontend → UX Advisor (ПОСЛЕ)
```

---

## Файловая структура

```
.claude/
├── agents/
│   ├── frontend/
│   │   └── SKILL.md          # ~80 строк
│   ├── backend/
│   │   └── SKILL.md          # ~100 строк
│   ├── data-engineer/
│   │   └── SKILL.md          # ~70 строк
│   ├── ux-advisor/
│   │   └── SKILL.md          # ~90 строк
│   └── deployer/
│       └── SKILL.md          # ~70 строк
│
├── settings.json             # (существует)
└── settings.local.json       # (существует)
```

---

## Порядок реализации

### Фаза 1: Создание агентов
1. Создать `.claude/agents/frontend/SKILL.md`
2. Создать `.claude/agents/backend/SKILL.md`
3. Создать `.claude/agents/data-engineer/SKILL.md`
4. Создать `.claude/agents/ux-advisor/SKILL.md`
5. Создать `.claude/agents/deployer/SKILL.md`

### Фаза 2: Тестирование
1. Frontend: "Добавь tooltip на кнопку фильтра"
2. Backend: "Добавь параметр limit в GET /races"
3. UX Advisor: "Проверь страницу RunnerProfile"
4. Deployer: "Сделай quick deploy"
5. Убедиться что агенты не лезут за пределы своей зоны

### Фаза 3: Итерация
- По результатам тестов — доработать промпты
- Добавить/убрать знания из SKILL.md
- Настроить ограничения

---

## Что НЕ делаем (и почему)

### Отдельный "Tester"
Тесты тесно связаны с кодом. Backend пишет pytest, Frontend проверяет TypeScript. UX Advisor покрывает user-facing проверки.

### Отдельный "Дизайнер"
Дизайн-система устоялась. Frontend следует паттернам. Новые паттерны предлагает UX Advisor.

### Отдельный "Архитектор"
Архитектурные решения принимает Ренат + Orchestrator. Слишком стратегический уровень для субагента.

### Отдельный "Bot Developer"
Бот — часть бэкенда (общие модели, API-клиент). Backend Developer справляется.

---

## Открытые вопросы

1. **UX Advisor: вызывать автоматически или по запросу?**
   - Автоматически после каждой фичи = больше токенов, но выше качество
   - По запросу = экономия, но можно забыть
   - **Предложение:** по запросу + Orchestrator предлагает когда видит сложную фичу

2. **Нужен ли hook для auto-format после Frontend?**
   - `PostToolUse` → `npx prettier --write` после Edit/Write в `frontend/`
   - Можно добавить позже если понадобится

---

## Следующие шаги

После утверждения этого документа:
1. Создаю все 5 SKILL.md файлов
2. Тестируем на реальных задачах
3. Итерируем промпты по результатам
