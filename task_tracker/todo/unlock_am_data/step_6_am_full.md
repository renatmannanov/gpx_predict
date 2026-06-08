# Шаг 6: Массовая загрузка всех гонок Алматы Марафон

> Зависит от: step_5 (пилот прошёл)
> Статус: [ ] pending

## Задача

Залить все доступные гонки almaty-marathon.kz и убрать legacy-фильтры `_am_kz`.

## 1. Подготовить catalog.yaml — БЛОКИРУЮЩИЙ prerequisite (до парсинга!)
Без этого шага `--all --force` не зальёт AM. Выполнить ПЕРЕД парсингом:
- Переименовать оставшиеся 5 AM-гонок в catalog.yaml: убрать суффикс `_am_kz`
  (winter_run, almaty_marathon, summer_relay, tau_jarys, almaty_copa_run).
  almaty_half_marathon уже переименован в step_5.
- Если есть гонки AM прошлых лет (2023/2024) — собрать URL с almaty-marathon.kz/ru/results
  и добавить editions к соответствующим id (с `source: almaty-marathon`, id БЕЗ `_am_kz`).
```bash
# Проверить, что _am_kz в каталоге не осталось:
grep -n "_am_kz" content/races/catalog.yaml
# Ожидаем: пусто
```

## 2. Парсинг
```bash
python backend/scripts/batch_parse.py --all --force
```
Парсит и CLAX (повторно, идемпотентно), и AM. AM изолированы по source.
**Внимание:** `--all --force` = полный reparse всей базы (CLAX + AM), может занять
заметное время. НЕ прерывать на полпути. Если нужно только AM — парсить пофайлово
через `--race-id` для каждой AM-гонки.

## 3. Убрать legacy-фильтры `_am_kz`
Старый суффикс `_am_kz` использовался чтобы прятать грязные AM-данные. Теперь
AM чистые → фильтры убрать. Найти и убрать:
```bash
grep -rn "_am_kz\|_am_" backend/app/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx"
```
Известные места (фронт-путь уточнён ревью: `types/races.ts`, НЕ `utils/races.ts`):
- `backend/app/api/v1/routes/stats.py` — фильтр в season stats
- `backend/app/api/v1/routes/races.py` — фильтр в списке гонок
- `frontend/src/types/races.ts` — getRaceCategory()
Не полагаться на этот список — grep выше найдёт все реальные вхождения.

## 4. Проверка клубов AM
Новые гонки AM (2025+) имеют поле «Клуб» → проходят через `_resolve_club`.
После загрузки проверить дубли клубов:
```bash
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT a.name, b.name, similarity(a.name, b.name) sim
FROM clubs a JOIN clubs b ON a.id < b.id
WHERE similarity(a.name, b.name) > 0.7 ORDER BY sim DESC LIMIT 20;"
# Дубли мёрджить через backend/scripts/merge_clubs.py (CLI остаётся рабочим)
```

## Команды для верификации
```bash
# Итоговые цифры
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT source, COUNT(*) FROM runners GROUP BY source;
SELECT COUNT(*) FROM race_results;
SELECT COUNT(*) FROM runner_name_aliases WHERE name ~ '[а-яА-Я]';"

# Не осталось _am_kz в коде
grep -rn "_am_kz" backend/app/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx"
# Ожидаем: пусто

# Кириллица только в алиасах, не в runners.name
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c \
  "SELECT COUNT(*) FROM runners WHERE name ~ '[а-яА-Я]';"
# Ожидаем: 0 (имя транслитерировано, кириллица — в алиасах)
```

## Критерии готовности
- [ ] Все гонки AM в catalog.yaml и залиты
- [ ] `_am_kz` фильтры убраны из backend и frontend
- [ ] Дубли клубов AM проверены/смёрджены
- [ ] Кириллица только в алиасах (0 в runners.name)
- [ ] Локальный портал показывает AM-гонки в общем каталоге
