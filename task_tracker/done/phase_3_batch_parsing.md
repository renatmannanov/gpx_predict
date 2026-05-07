# Фаза 3: Batch-парсинг всех гонок

> Детальный план реализации для `races_mvp_v2/phase_3_more_parsers.md`

## Контекст

- 16 гонок, ~50 CLAX-ссылок в `content/races/races_links_athletex.md`
- CLAX-парсер работает (`ClaxParser`), проверен на Alpine Race и Amangeldy Race
- catalog.yaml создан — мастер-каталог ссылок и статусов ✅

## Принятые решения

1. **Парсим ВСЕ гонки и ВСЕ дистанции** (не только алматинские горные)
2. **race_id** = `{slug_название}_kz` (например `alpine_race_kz`, `tengri_ultra_kz`)
3. **Результаты хранятся в БД** (PostgreSQL), не в JSON-файлах
4. **catalog.yaml** — мастер-каталог ссылок и статусов (ручной, git-tracked)
5. **races/*.yaml** — не нужны (метаданные гонок тоже в БД)
6. **Одна БД** (общая с gpx_predict) — users, strava, races в одном месте

---

## Схема БД

### Таблицы

```
races
├── id: String PK ("alpine_race_kz")
├── name: String ("Alpine Race")
├── name_aliases: JSON (["Alpine Race", "Almaty Alpine Race", "25th Alpine Race"])
├── type: String nullable ("trail_sky")
├── location: String nullable ("Шымбулак")
├── created_at: DateTime

race_editions
├── id: Integer PK auto
├── race_id: String FK → races.id
├── year: Integer
├── date: String nullable ("2025-03-09")
├── source_url: String nullable (CLAX URL)
├── parsed_at: DateTime
├── unique(race_id, year)

race_distances
├── id: Integer PK auto
├── edition_id: Integer FK → race_editions.id
├── name: String ("Skyrunning")
├── distance_km: Float nullable
├── elevation_gain_m: Integer nullable
├── unique(edition_id, name)

race_results
├── id: Integer PK auto
├── distance_id: Integer FK → race_distances.id
├── name: String ("Iyemberdiyev Diyas")
├── name_normalized: String ("iyemberdiyev diyas") — lowercase, trimmed, "фамилия имя"
├── time_seconds: Integer
├── place: Integer
├── category: String nullable ("M_30-39")
├── gender: String nullable ("M")
├── club: String nullable ("Run Vertical Team")
├── bib: String nullable ("274")
├── birth_year: Integer nullable
├── nationality: String nullable ("KAZ")
├── over_time_limit: Boolean default false
├── index(name_normalized) — для поиска и матчинга
├── index(distance_id)

user_race_results
├── id: Integer PK auto
├── user_id: String FK → users.id
├── race_result_id: Integer FK → race_results.id
├── matched_by: String ("auto" | "manual")
├── confirmed: Boolean default false
├── unique(user_id, race_result_id)
```

### Связи

```
Race 1──* RaceEdition 1──* RaceDistance 1──* RaceResult
User 1──* UserRaceResult *──1 RaceResult
```

---

## Что остаётся на файловой системе

```
content/races/
├── catalog.yaml      # Мастер-каталог ссылок и статусов (ручной)
└── gpx/              # GPX файлы дистанций (для прогнозов)
```

`catalog.yaml` — единственный файл, который Ренат редактирует руками.
Всё остальное (результаты, метаданные гонок, дистанции) — в БД.

---

## Порядок реализации

### Шаг 1: catalog.yaml ✅ DONE

- [x] 1.1. Определить race_id для 16 гонок
- [x] 1.2. Создать catalog.yaml со всеми editions и URL-ами
- [x] 1.3. Пометить no_results / parsed / upcoming

---

### Шаг 2: SQLAlchemy модели + Alembic миграция ✅ DONE

Модели в `backend/app/features/races/db_models.py`, миграция `012_add_race_tables`.

- [x] 2.1. Создать SQLAlchemy модели: `Race`, `RaceEdition`, `RaceDistance`, `RaceResultDB`, `UserRaceResult`
- [x] 2.2. Зарегистрировать модели в `db/session.py` → `init_db()`
- [x] 2.3. Alembic миграция (revision id: `012_add_race_tables`)
- [x] 2.4. Применить миграцию, проверить что таблицы созданы

---

### Шаг 3: Переписать batch_parse.py → БД ✅ DONE

batch_parse.py переписан: CLAX → БД. Поддерживает `--race-id`, `--all`, `--force`, `--dry-run`, `--summary`, `--import-json`.

- [x] 3.1. save_to_db() — прямая запись в БД (без отдельного repository)
- [x] 3.2. Переписать batch_parse.py: парсинг → БД
- [x] 3.3. Импортировать существующие данные (Alpine Race 3 JSON + Amangeldy 5 JSON)
- [x] 3.4. Проверить через `--summary`

---

### Шаг 4: Парсинг остальных гонок ✅ DONE

Все 16 гонок спарсены. Итого: 16 races, 47 editions, 203 distances, 27,100 results.

- [x] 4.1-4.14. Все гонки спарсены, 0 ошибок

---

### Шаг 5: Нормализация имён участников ✅ DONE

`name_utils.py`: `normalize_name()` — lowercase, trim, sort words alphabetically.
Миграция `013_add_name_norm`: колонка `name_normalized`, индекс, nationality varchar(32).
Все 47 editions перепарсены с нормализацией.

- [x] 5.1. Добавить колонку `name_normalized` в `race_results` (миграция 013)
- [x] 5.2. Написать `normalize_name()` в `name_utils.py`
- [x] 5.3. Обновить `batch_parse.py` — нормализовать при вставке
- [x] 5.4. Индекс: `ix_race_results_name_normalized`
- [x] 5.5. Перепарсить все гонки (`--all --force`)
- [x] 5.6. Проверено: Baikashev/Vizuete/Janzakov/Medeu — все варианты написания найдены

---

### Шаг 6: Адаптация RaceCatalog / Service / API ✅ DONE

`RaceRepository` создан для данных из БД. `RaceCatalog` оставлен только для GPX lookup.
API endpoints переписаны на чтение из БД. `RaceService` принимает `db: Session` для comparison stats.
Все endpoints проверены: list (16 рас), get, results, search (с нормализацией), predict.

- [x] 6.1. `RaceRepository`: list_races, get_race, get_results, search_by_name, get_stats
- [x] 6.2. Обновить API endpoints — читать из БД через repository
- [x] 6.3. Обновить бот — через API (ничего не должно сломаться)
- [x] 6.4. `RaceService.predict_by_pace` — адаптировать (берёт comparison stats из БД)

---

### Шаг 7: Проверка и cleanup ✅ DONE

- [x] 7.1. Проверить API: все гонки, результаты, поиск — 16 рас, search с нормализацией ОК
- [x] 7.2. Проверить бот: бот работает через REST API, не зависит от backend internals
- [x] 7.3. Удалить JSON-файлы из `content/races/results/` — удалено 8 файлов + директория
- [x] 7.4. `races.yaml`: оставлен для GPX mapping, убраны editions, исправлен race_id → `alpine_race_kz`, case-insensitive matching в catalog.py
- [x] 7.5. `content/races/races/` — не существовала
- [x] 7.6. Обновить `docs/ARCHITECTURE.md` — добавлены db_models, repository, name_utils, обновлён data flow

---

## Файлы для создания

| Файл | Описание |
|------|----------|
| `backend/app/features/races/db_models.py` | SQLAlchemy модели ✅ |
| `backend/app/features/races/name_utils.py` | normalize_name() для нормализации имён |
| `backend/app/features/races/repository.py` | RaceRepository (CRUD для БД) |
| `backend/alembic/versions/012_add_race_tables.py` | Alembic миграция ✅ |
| `backend/alembic/versions/013_add_name_normalized.py` | Миграция: колонка name_normalized |

## Файлы для модификации

| Файл | Что меняется |
|------|-------------|
| `backend/scripts/batch_parse.py` | CLAX → БД ✅, + нормализация имён при вставке |
| `backend/app/db/session.py` | Зарегистрировать новые модели ✅ |
| `backend/app/features/races/db_models.py` | Добавить name_normalized |
| `backend/app/api/v1/routes/races.py` | Читать из БД через repository |
| `backend/app/features/races/service.py` | Comparison stats из БД |
| `backend/app/features/races/catalog.py` | Оставить только для GPX lookup |

## Результат

- БД: 27,100 строк в race_results (16 гонок, 47 editions, 203 distances)
- `name_normalized` — нормализованные имена для поиска и auto-матчинга
- `catalog.yaml` — мастер-каталог ссылок (ручной)
- API и бот работают со всеми гонками через БД
- Workflow: добавил ссылку → `batch_parse.py --race-id xxx` → готово

## Риски

- Разные названия дистанций между годами → `name_aliases` на Race, нормализация дистанций позже
- Backyard Ultra — специфический формат (петли) → может потребовать спец. обработки
- Миграция существующего кода (catalog/service/API) → делаем постепенно (шаг 6)
