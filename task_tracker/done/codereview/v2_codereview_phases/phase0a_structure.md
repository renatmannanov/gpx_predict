# Phase 0a: Create Directory Structure

> **Статус:** Не начато
> **Оценка:** ~50 строк (создание папок и __init__.py)
> **Зависимости:** Нет
> **Ветка:** `refactor/phase-0a-structure`
> **Цель:** Создать структуру папок для feature-based архитектуры

---

## Проблема

Текущая структура:
```
backend/app/
├── services/          # Всё в одном месте (1125 + 716 + 692 + 532 строк)
├── models/            # Все модели вместе
└── api/v1/routes/     # Толстые routes
```

AI-агенту приходится читать много файлов, чтобы понять один модуль.

---

## Целевая структура

```
backend/app/
├── features/                    # Бизнес-модули
│   ├── __init__.py
│   ├── hiking/                  # Phase 0c
│   │   ├── __init__.py
│   │   └── calculators/
│   │       └── __init__.py
│   ├── trail_run/               # Phase 0d
│   │   ├── __init__.py
│   │   └── calculators/
│   │       └── __init__.py
│   ├── strava/                  # Phase 0e
│   │   ├── __init__.py
│   │   └── sync/
│   │       └── __init__.py
│   ├── gpx/                     # Phase 0f
│   │   └── __init__.py
│   └── users/                   # Phase 0f
│       └── __init__.py
│
├── shared/                      # Phase 0b
│   └── __init__.py
│
├── services/                    # Останется (для обратной совместимости)
├── models/                      # Останется (для обратной совместимости)
└── api/v1/routes/               # Останется
```

---

## Задачи

### 0a.1 Создать features/
- [ ] Создать `backend/app/features/__init__.py`:
  ```python
  """
  Feature modules for GPX Predictor.

  Each feature is a self-contained module with:
  - models.py - SQLAlchemy models
  - schemas.py - Pydantic schemas
  - service.py - Business logic
  - repository.py - Data access (optional)
  - calculators/ - Calculation logic (optional)
  """
  ```

### 0a.2 Создать hiking/
- [ ] Создать `backend/app/features/hiking/__init__.py`:
  ```python
  """
  Hiking prediction module.

  Provides time prediction for hiking routes using:
  - Tobler's Hiking Function
  - Naismith's Rule with Langmuir corrections
  - Personalization based on Strava data
  """
  ```
- [ ] Создать `backend/app/features/hiking/calculators/__init__.py`:
  ```python
  """Hiking time calculators."""
  ```

### 0a.3 Создать trail_run/
- [ ] Создать `backend/app/features/trail_run/__init__.py`:
  ```python
  """
  Trail running prediction module.

  Provides time prediction for trail running using:
  - Grade Adjusted Pace (GAP)
  - Hike/Run threshold detection
  - Runner fatigue model
  """
  ```
- [ ] Создать `backend/app/features/trail_run/calculators/__init__.py`:
  ```python
  """Trail running calculators."""
  ```

### 0a.4 Создать strava/
- [ ] Создать `backend/app/features/strava/__init__.py`:
  ```python
  """
  Strava integration module.

  Provides:
  - OAuth flow
  - API client
  - Activity synchronization
  """
  ```
- [ ] Создать `backend/app/features/strava/sync/__init__.py`:
  ```python
  """Strava sync services."""
  ```

### 0a.5 Создать gpx/
- [ ] Создать `backend/app/features/gpx/__init__.py`:
  ```python
  """
  GPX file handling module.

  Provides:
  - GPX parsing
  - Route segmentation
  - File storage
  """
  ```

### 0a.6 Создать users/
- [ ] Создать `backend/app/features/users/__init__.py`:
  ```python
  """
  User management module.

  Provides:
  - User CRUD
  - Notifications
  """
  ```

### 0a.7 Создать shared/
- [ ] Создать `backend/app/shared/__init__.py`:
  ```python
  """
  Shared utilities (NOT business logic).

  Contains:
  - geo.py - Geographic calculations (haversine)
  - elevation.py - Elevation smoothing
  - constants.py - Enums and constants
  - formatters.py - Time/pace formatters
  - repository.py - Base repository class
  """
  ```

---

## Файлы для создания

```
NEW:
backend/app/features/__init__.py
backend/app/features/hiking/__init__.py
backend/app/features/hiking/calculators/__init__.py
backend/app/features/trail_run/__init__.py
backend/app/features/trail_run/calculators/__init__.py
backend/app/features/strava/__init__.py
backend/app/features/strava/sync/__init__.py
backend/app/features/gpx/__init__.py
backend/app/features/users/__init__.py
backend/app/shared/__init__.py
```

---

## Критерии завершения

- [ ] Все папки созданы
- [ ] Все `__init__.py` имеют docstrings
- [ ] Приложение запускается (ничего не сломано)
- [ ] `git status` показывает только новые файлы

---

## Проверка

```bash
cd backend
# Должно запуститься без ошибок (импорты не изменились)
uvicorn app.main:app --reload
```

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 0a - create features/ and shared/ structure

- Create backend/app/features/ directory
- Create backend/app/shared/ directory
- Add __init__.py with docstrings for each module
- No code changes, just structure

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-0a-structure
```

Перейти к Phase 0b.

---

*Phase 0a — Create Directory Structure*
