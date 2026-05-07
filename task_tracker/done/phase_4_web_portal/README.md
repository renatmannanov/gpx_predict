# Phase 4: Веб-портал ayda.run

## Контекст

Phase 3 завершена: 16 гонок, 47 editions, 203 distances, 27K+ результатов в БД.
API endpoints готовы (`backend/app/api/v1/routes/races.py`).
Нужна веб-морда для аналитики гонок athletex.kz/myrace.info.

## Стек

- **Frontend:** React 18 + Vite + TypeScript + TanStack React Query
- **Стили:** CSS custom properties (тёмная тема ayda.run) + Tailwind для layout-утилит
- **Шрифт:** Manrope (Google Fonts)
- **Графики:** Canvas API (без Chart.js)
- **Деплой:** FastAPI раздаёт `frontend/dist/` (уже работает в `backend/app/main.py`)
- **Ветка:** `web-portal`

## Дизайн-система

Из мокапов в `docs/task_tracker/todo/races_portal_front/`:

| Токен | Значение |
|-------|----------|
| --bg | `#252628` |
| --accent | `#E8622A` (orange) |
| --accent-road | `#5B8DEF` (blue) |
| --text | `#EDEEF0` |
| --dim | `#7A8394` |
| --card | `rgba(255,255,255,0.04)` |
| --card-hover | `rgba(255,255,255,0.07)` |
| --border | `rgba(255,255,255,0.08)` |
| font | Manrope 400-900 |
| border-radius | 12-14px cards, 8px buttons |

**Тёмная тема only.** Без light mode.

## API endpoints (уже готовы)

| Метод | URL | Что возвращает |
|-------|-----|---------------|
| GET | `/api/v1/races` | Список всех гонок (id, name, type, location, distances[], editions[]) |
| GET | `/api/v1/races/{raceId}` | Одна гонка |
| GET | `/api/v1/races/{raceId}/{year}/results` | Результаты: distances[] → stats + results[] + time_buckets[] |
| GET | `/api/v1/races/{raceId}/search?name=...` | Поиск участника по имени (normalized) по всем годам |
| POST | `/api/v1/races/{raceId}/predict` | Прогноз времени по flat pace |

## Существующий фронтенд

Папка `frontend/` уже содержит:
- React + Vite + TS проект (package.json, vite.config.ts, tsconfig.json)
- API client: `src/api/client.ts` — `api.get()`, `api.post()`, и т.д.
- 2 страницы: HomePage (landing), PredictPage (GPX prediction wizard)
- Tailwind CSS с зелёной темой — **будет заменена**

## Шаги реализации

| Шаг | Файл | Описание | Зависит от |
|-----|------|----------|-----------|
| 1 | `step_1_design_system.md` | Дизайн-система + каркас (Nav, Footer, тема) | — |
| 2 | `step_2_races_list.md` | Страница списка гонок `/races` | Шаг 1 |
| 3 | `step_3_race_detail.md` | Детали гонки + результаты `/races/:raceId` | Шаги 1-2 |
| 4 | `step_4_homepage.md` | Главная страница `/` | Шаги 1-2 |
| 5 | `step_5_search.md` | Поиск участника "Найди себя" | Шаги 1-3 |
| 5.5 | `step_5_5_race_insights.md` + [папка step_5_5_race_insights/](step_5_5_race_insights/) | Race Insights (5 подшагов: backend+DNF, demographics, runner profile, search+compare, homepage) | Шаги 1-3, 5 |
| 6 | `step_6_deploy.md` | Деплой на Railway | Шаги 1-5.5 |

## Общие решения (из ревью плана)

| # | Решение | Где |
|---|---------|-----|
| 1 | TS типы сверены с Pydantic-схемами — добавлены `grade`, `start/finish_altitude_m`, `registration_url`, `next_date` | Шаг 2.1 |
| 2 | Сортировка гонок: по дате последнего edition (descending) | Шаги 2.6, 4.3 |
| 3 | Гистограмма: div-based (не Canvas) — mobile-friendly, без JS | Шаг 5.5b |
| 4 | Mobile-first: большинство пользователей с телефона | Все шаги |
| 5 | SeasonStatsBox обязательно в `useMemo` | Шаг 4.1 |
| 6 | Error Boundary + 404 page | Шаг 2.7, 2.8 |
| 7 | Loading: "Загрузка..." на MVP, skeleton placeholders — backlog | Шаг 2.6 |
| 8 | `document.title` на каждой странице | Шаг 2.9 |
| 9 | Deploy через Dockerfile (уже настроен на проде) | Шаг 6.3 |
| 10 | Бургер-меню для mobile nav — backlog | — |
| 11 | Поиск (шаг 5) inline между header и results, не заменяет таблицу | Шаг 3 заметки |
| 12 | Race Insights (шаг 5.5): категории показываем "как есть" от организатора, без нормализации | Шаг 5.5 |
| 13 | Нормализация возрастных категорий (из birth_year) — бэклог, для сквозной аналитики | Бэклог |
| 14 | DNF-анализ: доработка парсеров + перепарсинг — реализуется в **5.5a** (бэкенд) | Шаг 5.5a |
| 15 | Сравнение участников: multi-select 2-4 (как GSMArena), не 1-vs-1 | Шаг 5.5 |
| 16 | GPX треки: пока только 1 (Alpine Race), фичи на GPX — в бэклог | — |
| 17 | Страница бегуна `/runners/:nameNormalized` — публичная, без авторизации, кросс-гоночный профиль | Шаг 5.5 |

## Git-стратегия

- Основная ветка портала: `web-portal`
- **Каждый шаг — в отдельной ветке** от `web-portal`:
  1. Создать ветку `web-portal-step-N` от `web-portal`
  2. Реализовать шаг
  3. Дать пользователю проверить результат
  4. После подтверждения — коммит и merge в `web-portal`
- Merge `web-portal` в `main` когда MVP готов

## Дизайн-референсы

| Файл | Описание |
|------|----------|
| `docs/task_tracker/todo/races_portal_front/ayda-homepage-v2 (1).html` | Homepage дизайн, все CSS стили |
| `docs/task_tracker/todo/races_portal_front/ayda-season-v5.html` | Season rankings, bubble chart, таблица рейтинга |
| `docs/task_tracker/todo/races_portal_front/ayda-clubs.html` | Clubs page, bubble chart, club cards |
| `docs/task_tracker/todo/races_portal_front/ayda-tz.md` | Полное ТЗ с дизайн-системой |
