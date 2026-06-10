# Шаг 4: Пересборка athletex локально с нуля

> Зависит от: step_1, step_2, step_3 (тесты должны быть зелёные)
> Статус: [x] done — 39826 runners (am 26296 / athletex 13530), 60734 results,
>   Юлия Ким 1→5, 0 склеек birth_year, 56 editions parsed, 0 errors

## Задача

Пересобрать race-данные athletex/CLAX с нуля новым кодом, чтобы существующие
ложные склейки (Юлия Ким ×5 и др.) распались на правильных runners.

## Что НЕ трогаем (user-данные)
`users`, `strava_tokens`, `strava_activities`, `strava_activity_splits`,
`user_performance_profiles`, `user_run_profiles`, `profile_snapshots`,
`gpx_files`, `notifications`, `strava_sync_status`, alembic versions.

## Порядок

> Решение пользователя (2026-06-08): ручные алиасы НЕ сохраняем. Пересобираем
> с нуля «как есть» — что reparse создал из данных, то и канон. На локалке всего
> 0 runner + 4 club manual-алиасов, ими сознательно жертвуем. Ручной мёрдж клубов
> вернётся отдельной задачей вместе с вводом клубов AM.

### 1. TRUNCATE + применить миграцию (ЕДИНСТВЕННАЯ точка применения миграции)
```bash
# Бэкап локальной БД перед TRUNCATE (на всякий)
PGPASSWORD=secret "/c/Program Files/PostgreSQL/16/bin/pg_dump.exe" \
  -h localhost -U gpx_predictor -d gpx_predictor -F c -f /tmp/local_before_rebuild.dump

# TRUNCATE только race-таблиц (порядок FK). user_race_results тоже попадёт под
# CASCADE — это ОК (пусто, пользователей нет; решение пользователя в progress.md).
PGPASSWORD=secret "/c/Program Files/PostgreSQL/16/bin/psql.exe" \
  -h localhost -U gpx_predictor -d gpx_predictor -c \
  "TRUNCATE race_results, race_distances, race_editions, races, runner_name_aliases, club_name_aliases, runners, clubs RESTART IDENTITY CASCADE;"

# ТЕПЕРЬ применить миграцию 019 (таблицы пустые — новый UNIQUE не упадёт).
# Это единственное место, где запускается alembic upgrade для этой фичи.
cd backend && alembic upgrade head

# Проверить, что миграция применилась
PGPASSWORD=secret "/c/Program Files/PostgreSQL/16/bin/psql.exe" \
  -h localhost -U gpx_predictor -d gpx_predictor -c "\d runners" \
  | grep -i "source\|uq_runner_name_birth_source"
```

### 2. Пересобрать все athletex/CLAX гонки
```bash
python backend/scripts/batch_parse.py --all --force
```
(catalog.yaml содержит только CLAX-гонки на этот момент; AM добавляется в step_5/6)

### 3. Проверить, что Юлия Ким распалась
```bash
PGPASSWORD=secret "/c/Program Files/PostgreSQL/16/bin/psql.exe" \
  -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT name, COUNT(*) FROM runners WHERE name_normalized = 'kim yuliya' GROUP BY name;
"
# Ожидаем: ≥4 runner (а не 1)
```

## Команды для верификации
```bash
# У всех runners проставлен source='athletex'
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c \
  "SELECT source, COUNT(*) FROM runners GROUP BY source;"
# Ожидаем: только athletex (am ещё не залит)

# Нет runner с конфликтующими birth_year в результатах (склеек)
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT COUNT(*) FROM (
  SELECT r.id FROM runners r JOIN race_results rr ON rr.runner_id=r.id
  WHERE rr.birth_year IS NOT NULL
  GROUP BY r.id HAVING COUNT(DISTINCT rr.birth_year) > 1
) t;"
# Ожидаем: 0 (или близко — остаточные случаи где у одного человека опечатка в годе)

# Общие цифры адекватны (было ~20K runners, станет больше из-за распада дублей)
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c \
  "SELECT (SELECT COUNT(*) FROM runners) runners, (SELECT COUNT(*) FROM race_results) results;"
```

## Критерии готовности
- [ ] Миграция применена на чистых таблицах без ошибок
- [ ] Все CLAX-гонки пересобраны (`--all --force` без падений)
- [ ] `kim yuliya` → ≥4 разных runner
- [ ] 0 runners с конфликтующими birth_year в результатах
- [ ] Все runners имеют source='athletex'
- [ ] Портал локально открывается, поиск работает (smoke вручную)
