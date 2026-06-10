# Progress Log — unlock_am_data

## Контекст для агента (то, что не найдёшь сам в коде)

### Какие документы — источник правды
- **Этот PLAN.md — единственный источник правды для реализации.**
- `task_tracker/todo/name_matching_redesign.md` — концепция-предок. Полезен для
  понимания «почему», НО его раздел про межисточниковую транслитерацию УСТАРЕЛ:
  мы пошли через изоляцию `source` вместо сопоставления кириллицы с латиницей.
- `task_tracker/todo/step_1_am_data.md` — СТАРЫЙ план, фаза C/D УСТАРЕЛИ
  (использовали fuzzy при импорте). НЕ выполнять его шаги. Фаза A там done.

### Главное архитектурное решение
**Изоляция источников через `runners.source` ('am' | 'athletex').**
AM-бегуны и athletex-бегуны НИКОГДА не сопоставляются. Матчинг только внутри
своего источника, по паре `(name_normalized, birth_year)`. birth_year IS NULL
→ всегда новый runner (фрагмент). Fuzzy при импорте ВЫКЛЮЧЕН.

Это сознательный компромисс: один человек, бегавший и AM, и трейлы, будет двумя
разными runner. Связать их сможет позже UI ручного мёрджа (НЕ в этом плане).

### Ключевые факты по коду (проверено 2026-06-08)
- `source` УЖЕ передаётся в `save_to_db(source=...)`, значения `clax` /
  `almaty-marathon` (из catalog.yaml поля `source`). Нормализуем:
  `almaty-marathon → am`, иначе `athletex`.
- Колонки `source` у runners НЕТ — добавляем (step_2).
- `Runner.name_normalized` сейчас `unique=True` (db_models.py:59) — снимаем.
- `_fuzzy_match_runner` (batch_parse.py:130) — НЕ удалять функцию, только убрать
  вызов из импорта. Переедет в merge-candidates API позже.
- `merge_runners.py` / `merge_clubs.py` — CLI ОСТАЮТСЯ рабочими (ручной мёрдж клубов).
- Последняя миграция: `018_add_name_aliases`. Новая → `019_runner_source`.
- psql локально: `"/c/Program Files/PostgreSQL/16/bin/psql.exe" -h localhost -U gpx_predictor -d gpx_predictor`, PGPASSWORD=secret
- Прод: `trolley.proxy.rlwy.net:32647`, user postgres, db railway (пароль в backend/.env)

### Данные на старте (локалка, 2026-06-08)
- 20711 runners, 7486 без birth_year
- `KIM YULIYA` (runner 8395) = склейка 5 женщин (1980/82/84/85/91) — должна распасться
- `Pavlov Alexandr` = 3 человека (1984/2000/2015)
- Сотни подобных склеек athletex — лечатся пересборкой (step_4)

### НЕ трогать (user-данные при TRUNCATE)
users, strava_tokens, strava_activities, strava_activity_splits,
user_performance_profiles, user_run_profiles, profile_snapshots, gpx_files,
notifications, strava_sync_status, alembic versions.

### РЕШЕНИЕ ПОЛЬЗОВАТЕЛЯ (2026-06-08): БД можно сносить
На проде НЕТ реальных пользователей и сохранённых ими данных. Поэтому:
- `user_race_results` можно потерять при TRUNCATE CASCADE — НЕ требуется
  экспорт/восстановление этой таблицы (она пуста). Находка C1 ревью снята.
- Деплой = простой TRUNCATE race-таблиц + COPY, без церемоний по сохранению
  user-привязок. Главное — не трогать сами user-аккаунты (users, strava_*),
  хотя их там тоже почти нет.

### Реальные имена объектов UNIQUE на runners (проверено \d runners 2026-06-08)
Существуют ДВА объекта, оба снять в миграции:
- индекс `ix_runners_name_normalized` (UNIQUE) → op.drop_index
- констрейнт `uq_runners_name_normalized` (UNIQUE CONSTRAINT) → op.drop_constraint
(НЕ `runners_name_normalized_key` — такого имени нет)

### Применение миграции — ЕДИНСТВЕННАЯ точка
Миграция `019_runner_source` применяется ТОЛЬКО в step_4, ПОСЛЕ TRUNCATE.
step_2 — только пишет код модели и файл миграции, НЕ применяет alembic.
Тесты step_3 работают на ОТДЕЛЬНОЙ тестовой БД (своя миграция/create_all),
не на dev-БД.

### Git-стратегия
Ветка от dev: `feature/unlock-am-data`. Коммиты по шагам, Conventional Commits, English.

## Learnings

### КЛЮЧЕВОЕ ИЗМЕНЕНИЕ КУРСА (step_4/5, 2026-06-08): нормализация в родном алфавите
Решение пользователя: УБРАТЬ транслитерацию кириллица→латиница из `normalize_name`.
Причина: перевод кир→лат всегда лоссовый (Ким/Kim, двойные ss, казахские имена) и
давал путаницу — `name`=кириллица, а `name_normalized`=кривой транслит.
- Теперь `name_utils.normalize_name` канонизирует имя В ЕГО АЛФАВИТЕ:
  кириллица → канон-кириллица (lowercase+сорт слов, БЕЗ транслита и БЕЗ латинской фонетики),
  латиница → канон-латиница (+ фонетика как была).
- `transliterate_cyrillic` остаётся в коде, но `normalize_name` его больше НЕ зовёт.
- Источники изолированы по source → межалфавитный матчинг не нужен архитектурно.
- Цена (та же, что в плане): человек в AM(кир) и трейле(лат) = 2 runner, поиск
  латиницей не найдёт его AM-профиль. Решит ручной мёрдж позже.
- ОБНОВИТЬ при завершении: step_5/6 критерий «кириллица только в алиасах, 0 в
  runners.name» БОЛЬШЕ НЕ ВЕРЕН — теперь кириллица И в name, И в name_normalized для AM.
  Это правильно. Старый критерий относился к транслит-подходу.

### Баг дубль-алиаса (step_4, 2026-06-08) — ПОФИКШЕН
`ix_runner_aliases_unique` падал: два одинаковых имени в одной гонке (напр. два
`ABZHAPAROV Nurgeldi` в Tengri) → DB select не видит pending-алиас первого →
второй вставляет дубль → UniqueViolation отравляет всю сессию, остаток гонок падает.
Фикс: set `seen_aliases` в `save_to_db` дедупит pending-алиасы в рамках edition.
Регресс-тест: test_duplicate_name_in_same_race_no_alias_violation.

### Windows-консоль cp1252 (NB на будущее)
`show_summary` и любой print кириллицы падает UnicodeEncodeError в Windows-консоли.
Это НЕ баг данных. Для проверки кириллицы в БД — Python с `PYTHONIOENCODING=utf-8
python -X utf8`, НЕ psql `~ '[а-я]'` (psql-литерал тоже бьётся о cp1252, даёт ложный 0).


### Тестовая БД (step_3, 2026-06-08)
- Роль `gpx_predictor` изначально БЕЗ права CREATEDB. Пользователь выдал
  `ALTER ROLE gpx_predictor CREATEDB` под суперюзером postgres (вручную).
- Создана `gpx_predictor_test` (OWNER gpx_predictor). Схема строится через
  `Base.metadata.create_all` в `tests/conftest.py` — без alembic.
- `conftest.py` САМ выводит имя `<db>_test` из app database_url, поэтому
  `pytest tests/` работает из коробки и НЕ трогает dev-БД. Можно переопределить
  env `TEST_DATABASE_URL`.
- Тесты гоняют РЕАЛЬНЫЙ `scripts.batch_parse.save_to_db` (не копию логики),
  изоляция — транзакция + rollback на каждый тест.
- Факт нормализации: `Pavlov Alexandr` → `aleksandr pavlov` (x→ks), не `alexandr`.
- Результат: 5/5 матчинг-тестов + вся сюита 253 passed.

### Деплой/миграции (step_7 prep, 2026-06-08)
- `start.sh` запускает `python -m alembic upgrade head` под `set -e` ПЕРЕД
  uvicorn. Railway откатывает деплой при падении миграции (ON_FAILURE). Значит
  на проде миграция применится сама при push в main.
- Реальные имена UNIQUE-объектов на runners подтверждены `\d runners`:
  `ix_runners_name_normalized` (UNIQUE index) + `uq_runners_name_normalized`
  (UNIQUE constraint). Миграция 019 дропает оба.
---
