# Ayda — Горный портал Алматы
## Agent Brief v1.1 | Февраль 2026

---

## 0. СТАТУС И РЕШЕНИЯ (обновлено 2026-02-24)

**Активная реализация:** `docs/task_tracker/todo/races_mvp/` — Фазы 0-2

### Принятые архитектурные решения:

1. **Контент отдельно от кода:**
   - `content/races/` — GPX, результаты (JSON), каталог (YAML)
   - `content/routes/` — (будущее) 15 вершин Алатау
   - `backend/app/features/races/` — код модуля (как features/hiking/)

2. **MVP через Telegram-бота, не лендинг:**
   - Бот уже работает, аудитория там
   - Лендинг / веб-портал — после валидации хуков через бота

3. **Strava OAuth — Вариант D (ayda_run делает OAuth, gpx_predictor делает backfill):**
   - ayda_run — единственный хозяин Strava OAuth (апрув есть)
   - gpx_predictor получает токены через API ayda_run
   - gpx_predictor сам ходит в Strava за данными (splits, activities)
   - Strava видит один client_id — легально

4. **Портал разворачивается внутри gpx_predict:**
   - Веб-портал (маршруты, гонки, дашборды) — часть gpx_predict
   - ayda_run и gpx_predict общаются через API (не shared DB)
   - ayda_run отдаёт токены Strava, gpx_predict — предсказания и контент

5. **Route matching отложен:**
   - Для Фазы 0-1 хватит ручной привязки маршрутов
   - Автоматический GPS matching — R&D задача для Фазы 2+
   - Проблемы: out-and-back, разные старты, частичные прохождения, GPS drift

6. **Результаты гонок — файлы, не БД:**
   - CLAX (XML) парсится в JSON, хранится в `content/races/results/`
   - 7 горных гонок × 3 года = ~20 файлов, БД не нужна
   - Статистика считается на лету

7. **Splits хранение — нормализованная таблица (не JSONB):**
   - `StravaActivitySplit` с отдельными полями — как сейчас в gpx_predictor
   - НЕ переходить на `splits_metric JSONB` из раздела 5 этого документа

### Что из этого документа актуально:

- ✅ Секции 1-4: Vision, Product Structure, Data Sources, ITRA — актуальны
- ⚠️ Секция 5 (Technical Architecture): частично устарела (см. решения выше)
- ✅ Секции 6-9: Grading, Implementation Sequence, Competitive, Risks — актуальны
- ⚠️ Секция 10 (Strava Technical): rate limits правильные (600/15min после апрува)
- ✅ Секции 11-13: Assets, Glossary, Open Questions — актуальны

---

## 1. VISION & POSITIONING

**Ayda — гид по горам Алматы, который знает твой уровень.**

Не альтернатива Strava. Не фитнес-приложение. Это домашняя страница горного бега и хайкинга Алматы — место где ты узнаёшь про вершины, маршруты, гонки, и свою готовность к ним.

**Ключевой differentiator:** Strava — глобальная платформа, ей плевать на конкретные тропы Алматы. Garmin/Coros — персональные трекеры без локального контекста. ITRA — только гонки. Ayda = локальная экспертиза + база маршрутов + предсказание времени с учётом рельефа + персональная оценка готовности.

**Целевая аудитория (по приоритету):**
1. Хайкеры Алматы (широкая аудитория, сотни тысяч) — хотят знать "готов ли я к Пику Фурманова"
2. Трейлраннеры Алматы (~500-1000 активных) — хотят предсказание времени на гонку/маршрут
3. Беговые клубы (тренеры, ~10-20 клубов) — координация тренировок (ayda_run)

---

## 2. PRODUCT STRUCTURE

### Три слоя, каждый самоценен:

### Слой 1: Публичный (без регистрации, SEO + трафик)

**Вершины и маршруты:**
- Каталог вершин (Пик Фурманова, Букреева, Кумбель, БАП, и т.д.) и трейловых маршрутов (Кок-Жайляу, Бутаковка, Кимасар...)
- Для каждого: GPX, набор высоты, расстояние, грейд сложности (цветовая шкала: 🟢🟡🟠🔴)
- Калькулятор времени без регистрации: "введи свой темп на плоскости → получи прогноз" (gpx_predictor, базовый режим)
- Типичное время для хайкеров и для бегунов
- Рекомендации по безопасности, окно выхода

**Календарь гонок:**
- Все беговые/трейловые гонки Алматы (парсинг + ручное добавление)
- Дата, дистанция, набор высоты, грейд сложности, ссылка на регистрацию
- Грейд по ITRA Mountain Level (рассчитывается по формуле из GPX)

**Результаты гонок:**
- Исторические результаты (парсинг с сайтов организаторов)
- Поиск по имени
- Статистика гонки: количество участников, средний/лучший/худший результат

### Слой 2: Персональный (после подключения Strava/Garmin)

**Хук для подключения (по силе):**
1. "Предскажи своё время на [маршрут/вершину/гонку]" — персонально, на основе твоих данных. Главный хук.
2. "Готов ли ты к [вершине]?" — оценка готовности: 🟢 готов / 🟡 с оговорками / 🔴 не готов, сначала сходи на X
3. "Какие маршруты Алматы ты уже пробежал" — discovery и лёгкая геймификация

**После подключения (backfill всей истории):**
- Автоматическое определение "ты бегал маршрут X, Y раз, за Z время"
- Матчинг GPS-треков пробежек к базе маршрутов Алматы
- Персональный прогноз времени на любой маршрут из каталога (gpx_predictor, персональный режим)
- Прогресс на маршрутах: "Кок-Жайляу: первый раз 3:20, лучший 2:38"
- Оценка готовности к вершинам и гонкам
- "Твои горы": набор высоты за сезон, количество маршрутов

### Слой 3: Клубы (ayda_run интеграция)

- Календарь тренировок клуба
- Запись на тренировки через Telegram Mini App
- GPX маршруты из каталога для каждой тренировки
- Тренер видит профили участников (Strava Community Application exception)

---

## 3. DATA SOURCES & INTEGRATIONS

### 3.1 Strava API

**Статус:** Интеграция одобрена для ayda_run.

**Текущий скоуп:** `read,activity:read_all` ✅
- `read` — чтение публичного профиля
- `activity:read_all` — чтение ВСЕХ активностей (включая приватные) с privacy zones
- Backfill всей истории: ✅ готово, никаких дополнительных действий не нужно

**Не запрашиваем (не нужно):**
- `read_all` — приватные маршруты/сегменты/события
- `profile:read_all` — полный профиль скрытых пользователей
- `profile:write` — запись в профиль
- `activity:write` — создание/редактирование активностей

**Что получаем из API:**
- Профиль: city, state, country
- Список всех активностей (backfill): distance, moving_time, elapsed_time, total_elevation_gain, start_latlng, end_latlng, timezone, map.summary_polyline
- Activity streams (детальные): latlng, altitude, heartrate, time, distance — с высокой частотой
- Из polyline/streams можно восстановить полный GPS-трек для матчинга к маршрутам

**Rate limits:**
- Overall: 600 requests / 15 min, 6,000 / day
- Read: 300 requests / 15 min, 3,000 / day
- **Athlete Capacity: 999** — максимум подключённых юзеров. После 999 нужно запрашивать увеличение у Strava.
- Backfill стратегия: при 50 активностях на страницу, юзер с 500 активностями = 10 запросов на список + N запросов на streams. При 300 read/15min — можно backfill ~30 юзеров за 15 минут.

**API Agreement ключевые ограничения (октябрь 2025):**
- Данные юзера показывать ТОЛЬКО этому юзеру (кроме Community Applications)
- Community Application: приложение для организации групповых активностей, <9,999 юзеров. ayda_run подходит.
- Запрещено: агрегация/аналитика Strava Data для показа третьим лицам
- Запрещено: использование для AI/ML training
- Запрещено: создание конкурирующего с Strava продукта

**gpx_predictor:** Отдельный сервис, но БЕЗ собственной Strava-интеграции. Читает activities + splits_metric из shared Postgres. ayda_run — единственный "хозяин" Strava OAuth и backfill. gpx_predict использует те же данные через shared DB.

### 3.2 Garmin Connect API

**Статус:** НЕ одобрена ещё. Подать заявку после запуска сайта.

**Что даёт:** FIT-файлы с полным GPS + пульс + каденс + высота + running dynamics. Данные богаче чем Strava.
**Архитектура:** Push-based — данные приходят автоматически после синхронизации часов.
**Terms:** Гораздо мягче чем Strava. Нет запрета на aggregated analytics. **Использовать Garmin как primary source для агрегаций.**
**Доступ:** Бесплатно для разработчиков (раньше $5,000). Заявка на developer.garmin.com, ревью ~2 рабочих дня.
**Рынок:** 70%+ трейлраннеров Алматы на Garmin.

### 3.3 Другие устройства (lower priority)

**Polar:** Открытый бесплатный API (Polar Open AccessLink). OAuth2, регистрация через Polar Flow → developer account. Подключить можно за день. Отдаёт тренировки, daily activity, HR, сон.

**Suunto:** Закрытый API, заявка через apizone.suunto.com. Бесплатно, но только для компаний. Ревью еженедельно. Описать business case.

**Coros:** Самый закрытый. Приватная документация, заявка через support.coros.com. Альтернатива: неофициальные GitHub библиотеки (coros-connect), но могут сломаться.

**Terra API (tryterra.co):** Единый API для всех устройств (Garmin + Coros + Polar + Suunto + 500 других). Решает мульти-device проблему, но добавляет зависимость и стоимость. Рассмотреть позже если нужен Coros.

### 3.4 Календарь гонок и результаты

**Базовый источник календаря:** Telegram-канал @mystartkz (7,946 подписчиков) — агрегатор всех стартов Казахстана (бег, плавание, MTB, триатлон, все города). Формат — текстовые посты, ручное обновление. Парсить не нужно — используем как baseline.

**Стратегия ayda:** Только Алматы + только бег/трейл/хайк. Для горных стартов — глубокая карточка (GPX, грейд, предсказание, результаты). Для шоссейных — дата/ссылка. Ссылка на mystart для стартов в других городах.

#### Алматинские старты 2026 (из календаря mystart)

**Горные/трейловые (приоритет — полные карточки с GPX, грейдом, предсказанием):**
| Дата | Событие | Тип |
|------|---------|-----|
| 17-18.01 | Amangeldy Race | Trail/Sky winter |
| 21.02 | Ak bulak Night Race | Trail/Night |
| 1.03 | Alpine Race | Trail/Sky |
| 1-3.05 | Tengri Ultra | Ultra/Trail |
| 27.06 | Tau Jarys | Trail |
| 6.09 | Irbis Race | Trail |
| 18.10 | Salomon Trail | Trail |

**Шоссейные/городские (дата + ссылка, без глубокой карточки):**
| Дата | Событие | Тип |
|------|---------|-----|
| 15.02 | Winter Run | Road |
| 22.03 | Backyard Ultra | Ultra |
| 29.03 | Copa Speed Race | Road |
| 4.04 | Road Race | Road |
| 19.04 | Almaty Half Marathon | Road |
| 11.07 | BAO ITT | Road/TT |
| 18.07 | Summer Relay | Road |
| 20.09 | Road Race | Road |
| 27.09 | Almaty Marathon | Road |
| 8.11 | City Run | Road |

**Другое (MTB, OCR — не наш фокус):**
| Дата | Событие | Тип |
|------|---------|-----|
| 23.03 | Nauryz Bike | MTB |
| 12.04 | Red Planet MTB | MTB |
| 25.07 | Kazakhstan Adventure Race | Adventure |
| 8-9.08 | Race Nation Kazakhstan | OCR |

**Источники результатов прошлых гонок:** Нужно определить конкретные URL. Вероятные источники:
- Сайты гонок: irbisrace.kz, tengriultra.com и т.д.
- Протоколы в PDF/Google Sheets у организаторов
- Платформы тайминга (если используются)
- ITRA (itra.run) — для гонок с ITRA-сертификацией

**Формат данных результатов:** Имя, время, дистанция, набор высоты, место, возрастная группа, дата гонки.

### 3.5 База маршрутов (GPX)

**Первичный источник:** Собрать руками 15-20 маршрутов.
- Собственные пробежки Рената
- GPX от тренеров SRG, RUNFINITY (они и так раздают в чатах)
- Записать специально недостающие маршруты

**НЕ из Strava:** Не извлекать маршруты из Strava-пробежек юзеров. Стравовские данные — только для матчинга к уже существующим маршрутам.

**Для каждого маршрута рассчитать:**
- km-effort (эквивалентная плоская дистанция = реальная дистанция + набор высоты * коэффициент)
- Грейд сложности (аналог ITRA Mountain Level: соотношение набор/дистанция + средняя высота + макс подъём)
- Finisher level (минимальный уровень подготовки для безопасного прохождения)
- Предсказанное время для разных уровней (базовый gpx_predictor)

---

## 4. ITRA INTEGRATION

### Формула ITRA Race Score (публично документирована)

**Что мы можем воспроизвести:**
- km-effort = дистанция + набор высоты (с весовым коэффициентом)
- Mountain Level (0-12): соотношение набор/дистанция + средняя высота
- Finisher Level: минимальный PI для финиша в cutoff time
- Estimated Race Score: время юзера vs теоретическое лучшее время для данного km-effort

**Что мы НЕ можем воспроизвести точно:**
- Коэффициент корректировки на условия гонки (рассчитывается статистически по всем участникам конкретной гонки в базе ITRA из 8+ млн результатов). У нас нет этой базы.
- Точный PI (нужны результаты сертифицированных гонок)

**Что делаем:**
- "Estimated ITRA score" для тренировочных пробежек — не точный PI, а приблизительная оценка уровня на основе km-effort и времени юзера. Полезно как индикатор, с дисклеймером что это estimate.
- Для местных гонок которые есть в ITRA (Irbis Race, Tengri Ultra) — парсить результаты с itra.run для показа Finisher Level и рекомендаций.
- Для оценки готовности к вершинам — свой грейд на основе ITRA Mountain Level формулы.

---

## 5. TECHNICAL ARCHITECTURE

> **⚠️ УСТАРЕЛО:** Этот раздел описывал варианты архитектуры до принятия решения.
> **Принятое решение (см. секцию 0.4):** Портал разворачивается внутри gpx_predict. Два сервиса общаются через API, НЕ через shared DB. Описание ниже оставлено как исторический контекст.

### ~~Рекомендация: два сервиса, одна БД~~

**Контекст:** Сейчас ayda_run и gpx_predict — два отдельных FastAPI-сервиса с отдельными Strava-интеграциями. Полное слияние в один сервис = большой рефакторинг работающего кода. Прагматичный подход — минимальные изменения для устранения дублирования.

#### ~~Вариант A: Два сервиса, shared Postgres~~ (отвергнут)

```
┌─────────────────────────────────────────────────────┐
│              Web Portal (React/TS) — новый           │
│  маршруты, вершины, гонки, предсказания, профиль     │
└──────┬──────────────────────────────┬────────────────┘
       │                              │
       ▼                              ▼
┌──────────────┐          ┌───────────────────┐
│  ayda_run    │          │  gpx_predict      │
│  (FastAPI)   │          │  (FastAPI)        │
│              │          │                   │
│  - clubs     │          │  - gradient-pace  │
│  - events    │          │    model          │
│  - Strava    │          │  - predictions    │
│    OAuth ✅  │          │  - route calc     │
│  - backfill  │          │                   │
│  - routes    │          │  Strava удалён ❌ │
│  - races     │          │  Читает из        │
│  - profiles  │          │  shared DB        │
└──────┬───────┘          └────────┬──────────┘
       │                           │
       ▼                           ▼
┌──────────────────────────────────────────────┐
│           Shared Postgres                     │
│                                               │
│  users, activities (+ splits_metric),         │
│  routes, races, race_results,                 │
│  clubs, club_events, predictions              │
└───────────────────────────────────────────────┘

📱 Telegram Mini App (ayda_run) → тот же ayda_run backend
```

**Что меняется для gpx_predict:**
- Удаляет свой Strava OAuth flow и sync module
- Читает activities + splits_metric из shared Postgres
- Модель prediction остаётся как есть
- Свой API остаётся (/predict/route, /predict/race)

**Что меняется для ayda_run:**
- Backfill теперь скачивает splits_metric (доп. GET /activities/{id} для горных активностей)
- Новые таблицы: routes, races, race_results
- Новые endpoints для web-портала

**Плюсы:** Минимальный рефакторинг. gpx_predict не переписывается, только удаляет Strava-код и меняет source данных.
**Минусы:** Два сервиса на одной БД — нужна дисциплина с миграциями.

#### Вариант B: Один бэкенд (full merge)

```
┌──────────────────────────────┬──────────────────────┐
│  Web Portal (React/TS)       │  Telegram Mini App    │
└──────────────┬───────────────┴──────────┬───────────┘
               │                          │
               ▼                          ▼
┌─────────────────────────────────────────────────────┐
│              AYDA BACKEND (FastAPI)                   │
│                                                       │
│  /api/v1/auth/strava/*     ← OAuth, token mgmt      │
│  /api/v1/activities/*      ← backfill, sync         │
│  /api/v1/routes/*          ← каталог маршрутов      │
│  /api/v1/races/*           ← календарь, результаты  │
│  /api/v1/predict/*         ← gpx_predict module     │
│  /api/v1/clubs/*           ← ayda_run клубы         │
│  /api/v1/users/*           ← профили                │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│              Postgres                                │
└─────────────────────────────────────────────────────┘
```

**Плюсы:** Одна кодовая база, нет проблем с shared DB, один деплой.
**Минусы:** Большой рефакторинг, перенос всей логики gpx_predict.

#### Решение: Вариант A сейчас, Вариант B потом (если нужно)

Начать с Варианта A — быстро, минимальный рефакторинг. Если со временем два сервиса на одной БД создают проблемы — объединить в один. Но скорее всего не понадобится при текущем масштабе.

---

### Strava Integration (единая, в ayda_run)

**Один OAuth flow, scope:** `read,activity:read_all`

**Backfill процесс (при подключении юзера):**
1. Fetch all activities: `GET /athlete/activities?per_page=50&page=N`
2. Фильтр по Almaty region: `start_latlng` в пределах (42.8-43.6°N, 76.3-77.5°E)
3. Для горных активностей — fetch detail с splits: `GET /activities/{id}`
4. Сохранить в Postgres: activity + `splits_metric` + polyline
5. Route Matching → привязка к маршрутам из каталога
6. gpx_predict → читает splits из Postgres, строит gradient-pace профиль

**Ongoing sync:** Strava webhooks (или periodic polling) для новых активностей.

### gpx_predict module

**Перестаёт ходить в Strava напрямую.** Читает из shared Postgres.

**Два режима:**
1. **Базовый (без авторизации):** Юзер вводит темп → gpx_predict рассчитывает по GPX профилю высот с дефолтным gradient-pace профилем.
2. **Персональный (после подключения Strava/Garmin):** Берёт splits_metric из таблицы activities → строит персональный gradient-pace профиль → предсказание точнее.

**Как строится gradient-pace профиль:**
- Из `splits_metric` каждой активности: `elevation_difference / distance` = gradient %
- 11 категорий градиента: от -30% до +30% (шаг ~5-6%)
- Для каждой категории — медианный темп юзера по всем его горным активностям
- При предсказании: GPX маршрута → разбить на сегменты → каждому присвоить gradient → персональный темп → суммировать

**Что хранится для gpx_predict:**
- `splits_metric` в таблице activities (pace, distance, elevation_difference per km)
- Computed gradient-pace profile в таблице users (кэш, пересчитывается при новых активностях)

### Unified Activity Storage

При скачивании активности из ЛЮБОГО источника — единый формат в Postgres:

```sql
CREATE TABLE activities (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  source VARCHAR(20) NOT NULL,        -- 'strava' | 'garmin' | 'manual'
  source_id VARCHAR(100),              -- original activity ID
  date TIMESTAMPTZ NOT NULL,
  type VARCHAR(20),                    -- 'run' | 'hike' | 'trail_run'
  distance_m FLOAT,
  elevation_gain_m FLOAT,
  moving_time_s INTEGER,
  elapsed_time_s INTEGER,
  start_lat FLOAT,
  start_lng FLOAT,
  polyline TEXT,
  splits_metric JSONB,                 -- [{split, distance, moving_time, elevation_difference}, ...]
  has_hr BOOLEAN DEFAULT FALSE,
  avg_hr INTEGER,
  matched_route_id INTEGER REFERENCES routes(id),
  city_region VARCHAR(50)              -- 'almaty' | null
);
```

**Критично:** Поле `source` позволяет строить агрегации из Garmin/manual данных, избегая нарушения Strava API Agreement. Агрегации из multi-source таблицы = данные ayda, не Strava Data.

### Route Matching Engine

Юзерская пробежка → сравнение GPS-трека с базой маршрутов ayda.
**Алгоритм:** Декодирование polyline → сравнение с эталонными маршрутами. Fuzzy matching (GPS drift на трейлах до 10-30м). Порог совпадения ~80% точек трека в пределах 50м от эталона.
**Результат:** activity привязывается к `matched_route_id` из каталога, или помечается как NULL.

### Stack

- **Frontend (portal):** React/TypeScript — новый web-проект
- **Frontend (ayda_run):** React/TypeScript — существующий Telegram Mini App
- **Backend (ayda_run):** Python FastAPI — расширяется новыми endpoints для портала
- **Backend (gpx_predict):** Python FastAPI — существующий, удаляет Strava-код, читает из shared DB
- **Database:** Postgres (существующий) — новые таблицы: routes, races, race_results
- **Integrations:** Strava OAuth2 (existing, единый в ayda_run), Garmin (future), Telegram Bot API (existing)

### Authentication Architecture

**Два auth middleware на одном бэкенде (ayda_run):**

1. **TMA auth** (существующий): Telegram Mini App init data → верификация подписи → telegram_id → user
2. **Web auth** (новый): JWT в httpOnly cookie → decode → user_id → user

**Способы входа на портал:**
- **Strava OAuth** (основной) — одно действие = авторизация + подключение данных
- **Telegram Login Widget** (альтернативный) — для существующих ayda_run юзеров и тех кто без Strava

**User record (связывание аккаунтов):**
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE,
  strava_athlete_id BIGINT UNIQUE,
  garmin_user_id VARCHAR(100) UNIQUE,
  name VARCHAR(200),
  strava_access_token TEXT,            -- encrypted
  strava_refresh_token TEXT,           -- encrypted
  strava_token_expires_at BIGINT,
  gradient_pace_profile JSONB,         -- cached, for gpx_predict
  linked_at JSONB                      -- {"telegram": "2025-01-15", "strava": "2025-02-20"}
);
```

Юзер может войти через Telegram ИЛИ Strava. При первом подключении второго провайдера → prompt связывания → один профиль, два входа.

### Strava Data Flow

```
1. Юзер нажимает "Подключить Strava" (портал или TMA)
2. OAuth redirect → Strava → callback на ayda_run бэкенд
3. Бэкенд сохраняет access/refresh tokens в users table
4. Фоновая задача (background worker): backfill
   a. GET /athlete/activities?per_page=50 (пагинация по всей истории)
   b. Фильтр: is_almaty_activity(start_lat, start_lng)
   c. Для алматинских: GET /activities/{id} (detail + splits_metric)
   d. Route matching → сохранение в activities table
   e. Расчёт gradient-pace profile → кэш в users table
5. Strava Webhook: push-уведомления о новых активностях
   → POST callback → скачать → матчить → обновить профиль
```

### Backfill Budget (rate limit planning)

Per user backfill:
- Activity list: ~10 requests (500 activities / 50 per page)
- Almaty filter: ~40% are mountain runs → ~200 activities
- Detail + splits for each: 200 requests
- **Total per user: ~210 requests**
- Daily limit: 2000 req/day → ~9 юзеров/день при full backfill
- **При массовом подключении: очередь, backfill в фоне, юзер видит результат через 5-30 минут**

---

## 6. ROUTE & SUMMIT GRADING SYSTEM

### Грейд сложности маршрута/вершины

На основе ITRA Mountain Level (0-12), адаптированный для UX:

**🟢 Зелёный (ML 0-3):** Доступно начинающим. Примеры: Медеу — Шымбулак по дороге, Бутаковка до первого водопада.
**🟡 Жёлтый (ML 4-6):** Средний уровень, нужен опыт горных походов. Примеры: Кок-Жайляу, Бутаковка до верхних водопадов.
**🟠 Оранжевый (ML 7-9):** Продвинутый. Длинный день, значительный набор. Примеры: Пик Фурманова, Кумбель.
**🔴 Красный (ML 10-12):** Экспертный. Альпинистский опыт. Примеры: Большой Алматинский Пик, сложные перевалы.

### Оценка готовности ("Готов ли ты?")

**Без авторизации:** Чеклист для каждого грейда — "Если ты можешь пройти 15 км с набором 1000м за X часов — ты готов к жёлтому грейду".

**С авторизацией:** На основе backfill данных:
- Максимальный набор высоты за одну активность за последние 3 месяца
- Максимальная дистанция за одну активность
- Частота горных выходов (раз в неделю?)
- Средний темп на подъёмах

→ Сопоставление с требованиями маршрута → 🟢/🟡/🔴 + рекомендация "для подготовки пройди сначала маршрут X"

---

## 7. IMPLEMENTATION SEQUENCE

### Фаза 0: Landing Page + Validation (1-2 недели)

**Цель:** Проверить хуки, получить первых подключений Strava.

**Что делаем:**
- Одностраничник "Ayda — горы Алматы"
- 5-7 самых популярных маршрутов/вершин с GPX, грейдами, калькулятором времени (базовый gpx_predictor)
- Кнопка "Подключи Strava → узнай своё время на [маршрут]" для персонального прогноза
- Backfill при подключении → персональный результат
- Минимальный календарь гонок (ручной, 5-10 ближайших)

**Метрики:** Конверсия "зашёл на страницу маршрута" → "подключил Strava". Цель: 10%+.

### Фаза 1: Полный каталог + парсеры (2-4 недели)

**Что делаем:**
- 15-20 маршрутов/вершин в каталоге
- Парсеры для 3-4 сайтов гонок (календарь + результаты)
- Route Matching Engine (автоматическое определение маршрутов из backfill)
- Персональная страница юзера: "твои маршруты, прогресс, предсказания"
- Оценка готовности для каждой вершины ("готов ли ты?")
- Расширить OAuth scope до `activity:read_all`

### Фаза 2: Garmin + Глубокая аналитика (4-6 недель)

**Что делаем:**
- Подать и получить одобрение Garmin API
- Подключение Garmin как второй source
- Агрегированная статистика маршрутов (из Garmin data, без Strava restrictions)
- ITRA estimated scores для тренировочных пробежек
- Персональный gpx_predictor (модель на основе истории юзера)

### Фаза 3: Интеграция ayda_run + Клубы (6-8 недель)

**Что делаем:**
- ayda_run как клубная секция портала
- GPX маршруты из каталога в тренировки клуба
- Профили участников видны тренеру (Community Application exception)
- Подать заявки: Polar, Suunto, Coros

---

## 8. COMPETITIVE LANDSCAPE & MOATS

### Что Strava не делает и не будет:
- Привязка к конкретным местным маршрутам Алматы
- Предсказание времени с учётом рельефа (их predictions = flat terrain)
- Оценка готовности к вершинам
- Безопасность: "ты не готов к БАПу, сходи сначала на Фурманова"
- Локальный календарь гонок Алматы

### Что Garmin/Coros не делают:
- Нет групповой функциональности
- Нет локальной базы маршрутов
- Race predictor игнорирует рельеф (хронически оптимистичен)

### Что ITRA не делает:
- Только гонки, не тренировки
- Нет GPS-интеграции
- Нет маршрутной аналитики
- Нет предсказаний

### Конкурентные моаты ayda:
1. **Локальная экспертиза** — глобальные платформы не будут делать базу трейлов Алматы
2. **gpx_predictor** — уникальная модель предсказания с учётом рельефа
3. **Community Application status** — Strava разрешает групповую функциональность для <9,999 юзеров
4. **Multi-source data** — Strava + Garmin + manual → агрегации без юридических рисков
5. **Сетевой эффект** — чем больше юзеров подключается, тем точнее матчинг маршрутов и статистика

---

## 9. KEY RISKS & MITIGATIONS

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Strava отзывает API доступ | Низкая (Community App, <100 юзеров) | Garmin как primary source, manual GPX import |
| Strava меняет API Agreement ещё раз | Средняя | Не зависеть от Strava для core value. Маршруты, gpx_predictor, календарь работают без Strava |
| Мало подключений Strava (хук не работает) | Средняя | Фаза 0 = validation. Тестируем разные хуки до вложения в полный портал |
| Route matching неточный (GPS drift на трейлах) | Средняя | Fuzzy matching с широким порогом (50м). Ручная коррекция для первых юзеров |
| Парсеры гонок ломаются при изменении сайтов | Высокая | Ручной fallback. Гонок ~20-30 в год, можно добавлять вручную |
| Garmin не одобряет API | Низкая (бесплатно, процесс стандартный) | Terra API как backup |

---

## 10. STRAVA API TECHNICAL REFERENCE

### OAuth2 Flow
```
1. Redirect user to:
   https://www.strava.com/oauth/authorize?
   client_id={CLIENT_ID}&
   response_type=code&
   redirect_uri={REDIRECT_URI}&
   approval_prompt=auto&
   scope=read,activity:read_all

2. User authorizes → redirect with code

3. Exchange code for tokens:
   POST https://www.strava.com/oauth/token
   {client_id, client_secret, code, grant_type: "authorization_code"}
   
4. Response: {access_token, refresh_token, expires_at, athlete: {...}}

5. Refresh when expired:
   POST https://www.strava.com/oauth/token
   {client_id, client_secret, refresh_token, grant_type: "refresh_token"}
```

### Key Endpoints

**List activities (backfill):**
```
GET /api/v3/athlete/activities?per_page=50&page=1&after=UNIX_TIMESTAMP
```
Returns: id, name, distance, moving_time, total_elevation_gain, type, sport_type, start_date, start_latlng, end_latlng, timezone, map.summary_polyline

**Activity detail:**
```
GET /api/v3/activities/{id}
```
Returns: full detail including splits, laps, gear, calories

**Activity streams (GPS track):**
```
GET /api/v3/activities/{id}/streams?keys=latlng,altitude,heartrate,time,distance&key_type=time
```
Returns: arrays of coordinate, elevation, HR data points

**Athlete profile:**
```
GET /api/v3/athlete
```
Returns: id, firstname, lastname, city, state, country, profile photo

### Rate Limits
- Overall: 600 requests per 15 minutes, 6,000 per day
- Read: 300 requests per 15 minutes, 3,000 per day
- Athlete Capacity: 999 connected users (request increase from Strava when approaching)
- Backfill strategy: fetch activity list first (50 per page), then fetch streams only for activities matching Almaty region (start_latlng near 43.2°N, 76.9°E)

### Almaty Region Filter
```python
ALMATY_CENTER = (43.238949, 76.945465)
ALMATY_RADIUS_KM = 80  # covers all mountain trails around Almaty

def is_almaty_activity(start_latlng):
    if not start_latlng:
        return False
    lat, lng = start_latlng
    # Simple distance check (Haversine for precision later)
    return (42.8 < lat < 43.6) and (76.3 < lng < 77.5)
```

---

## 11. EXISTING ASSETS

| Asset | Status | Notes |
|-------|--------|-------|
| ayda_run (Telegram Mini App) | Live, pilot with SRG + RUNFINITY | 42 users, React/TS + FastAPI + Postgres |
| Strava integration (ayda_run) | Approved, scope: read,activity:read_all ✅ | Full backfill ready, no changes needed |
| gpx_predictor | Working model, separate FastAPI service | Prediction based on GPX + gradient-pace profile. Will drop own Strava integration, read from shared Postgres |
| SRG club relationship | Active | Trail/mountain running, beginner group |
| RUNFINITY club relationship | Active | Beginner runners, 10 users |
| Nike Running Club Almaty | Potential | 22,300 Facebook members |
| Running community knowledge | 7-8 years experience | Ultramarathons, trails, local race knowledge |

---

## 12. GLOSSARY

- **Backfill** — импорт всей исторической истории тренировок юзера при первом подключении Strava/Garmin. Даёт мгновенный wow-эффект.
- **km-effort** — эквивалентная плоская дистанция = реальная дистанция + набор высоты. Формула ITRA для сравнения маршрутов разной сложности.
- **ITRA Performance Index (PI)** — рейтинг трейлраннера 0-1000, средневзвешенное 5 лучших результатов за 36 месяцев.
- **ITRA Mountain Level** — сложность маршрута 0-12, соотношение набор/дистанция + высота.
- **Finisher Level** — минимальный PI для финиша в cutoff time гонки.
- **Community Application** — исключение Strava API для приложений организации групповых активностей <9,999 юзеров. Разрешает показывать данные юзеров друг другу.
- **Route Matching** — автоматическое сопоставление GPS-трека пробежки юзера с эталонным маршрутом из базы ayda.
- **gpx_predictor** — модель предсказания времени на маршрут с учётом профиля высот и (опционально) персональных данных юзера.

---

## 13. OPEN QUESTIONS

1. Конкретные URL сайтов гонок и результатов для парсинга — нужны от Рената
2. Список первых 15-20 маршрутов для каталога — составить с Ренатом
3. Garmin API: подать заявку после запуска landing page
4. Дизайн landing page: стиль, брендинг (Ayda? Ayda.run? Новый бренд?)
5. Домен для портала
6. Монетизация: бесплатный портал → где revenue? (спонсорство гонок? premium фичи? корпоративные wellness?)
