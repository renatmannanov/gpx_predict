# Шаг 7: Деплой на прод

> Зависит от: step_6
> Статус: [ ] pending
> Агент: Deployer

## Задача

Залить пересобранные данные (athletex без дублей + AM) на прод. Race-данные
заменяем целиком, user-данные не трогаем.

## Контекст: на проде нет user-данных
Решение пользователя (2026-06-08, progress.md): на проде НЕТ реальных пользователей
и сохранённых ими данных. БД можно сносить. `user_race_results` под CASCADE — ОК
(пусто). Бэкап делаем всё равно (дёшево, страховка от опечатки), но церемоний по
сохранению user-привязок НЕ требуется.

## ⚠️ STOP-правило (из CLAUDE.md)
TRUNCATE на проде — деструктивная операция. Перед выполнением:
1. Сделать pg_dump прода (backup для отката)
2. Получить явное подтверждение пользователя
3. Только потом TRUNCATE + COPY

## Порядок (ЗАФИКСИРОВАН — на проде иначе, чем локально!)

**На проде НЕ нужен TRUNCATE до миграции** (в отличие от step_4): новый UNIQUE
с server_default='athletex' применяется к текущим данным без падения (NULL≠NULL).
Порядок:
1. Деплой кода+миграции (push в main → Railway билдит и применяет alembic)
2. Дождаться, что миграция 019 применилась на проде
3. Backup прода
4. TRUNCATE race-таблиц
5. COPY данных

### 1. Деплой кода + миграции (push в main)
```bash
# ФАКТ (проверено 2026-06-08): миграции применяет start.sh при старте контейнера —
#   start.sh: `python -m alembic upgrade head` ПЕРЕД запуском uvicorn, под `set -e`.
# Значит: push в main → Railway билдит образ → start.sh применяет миграцию 019 →
#   стартует API. Если миграция упадёт — `set -e` валит контейнер, healthcheck не
#   проходит, Railway откатывается на прошлый деплой (restartPolicy ON_FAILURE).
#   То есть битая миграция НЕ пустит сломанный код в прод — отдельной защиты не нужно.
# Сначала — мёрдж feature/unlock-am-data → dev → main по git-стратегии проекта.
```

### 1b. Проверить, что миграция применилась на проде
```bash
PGPASSWORD=<prod> psql -h trolley.proxy.rlwy.net -p 32647 -U postgres -d railway \
  -c "\d runners" | grep -i "source\|uq_runner_name_birth_source"
# Ожидаем: колонка source + новый constraint. Если нет — миграция не прошла, СТОП.
```

### 3. Бэкап прода (выполнять в Git Bash, не PowerShell — $(date))
```bash
pg_dump -h trolley.proxy.rlwy.net -p 32647 -U postgres -d railway \
  -F c -f prod_backup_before_am_$(date +%Y%m%d).dump
# (пароль в backend/.env)
```

### 4. Экспорт локальных race-таблиц (COPY CSV — НЕ --inserts)
```bash
for t in clubs runners races race_editions race_distances race_results \
         runner_name_aliases club_name_aliases; do
  PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor \
    -c "\copy $t TO '/tmp/$t.csv' CSV HEADER"
done
```

### 5. TRUNCATE race-таблиц на проде (после подтверждения!)
```bash
PGPASSWORD=<prod> psql -h trolley.proxy.rlwy.net -p 32647 -U postgres -d railway -c \
"TRUNCATE race_results, race_distances, race_editions, races, runner_name_aliases, club_name_aliases, runners, clubs RESTART IDENTITY CASCADE;"
# user_race_results попадёт под CASCADE — ОК (пусто, пользователей нет).
```

### 6. COPY на прод (порядок FK)
```bash
# clubs, runners → races → editions → distances → results → aliases
for t in clubs runners races race_editions race_distances race_results \
         runner_name_aliases club_name_aliases; do
  PGPASSWORD=<prod> psql -h trolley.proxy.rlwy.net -p 32647 -U postgres -d railway \
    -c "\copy $t FROM '/tmp/$t.csv' CSV HEADER"
done
```

### 6. Деплой фронта (если менялись _am_kz фильтры)
Push в main → Railway билдит фронт автоматически.

## Smoke test на проде
```bash
# Цифры совпадают с локалкой
PGPASSWORD=<prod> psql -h ... -c "SELECT source, COUNT(*) FROM runners GROUP BY source;"
```
На ayda.run вручную:
- [ ] Поиск «Каримов» → находит AM-профиль
- [ ] Поиск «Karimov» → находит
- [ ] AM-гонка открывается, результаты есть
- [ ] Старые athletex-гонки на месте, percentile считается
- [ ] Профиль бегуна чистый (нет смешанных чужих забегов)

## Критерии готовности
- [ ] Backup прода сделан ДО TRUNCATE
- [ ] Подтверждение пользователя получено перед TRUNCATE
- [ ] Миграция применена на проде
- [ ] Данные залиты через COPY (не inserts)
- [ ] Smoke test пройден на ayda.run
- [ ] При проблеме — откат через pg_dump протестирован/доступен
