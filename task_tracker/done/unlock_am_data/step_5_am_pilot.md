# Шаг 5: Пилот — одна гонка Алматы Марафон

> Зависит от: step_4
> Статус: [x] done — пилот Summer Relay прошёл, затем все AM залиты (step_6).
>   Поиск Каримов→am, Karimov→athletex. Нормализация изменена: кириллица
>   остаётся кириллицей (см. progress.md «изменение курса»).

## Задача

Залить ОДНУ гонку AM (полумарафон) и проверить глазами качество перед массовой
загрузкой. Это контрольная точка — если что-то не так, чиним парсер до step_6.

## Подготовка

### 1. Проверить am_parser на форматах таблиц
AM использует РАЗНЫЕ форматы HTML-таблиц (старый/новый, см. am_parser.py).
Парсер должен определять формат по заголовкам. Проверить на выбранной гонке:
```bash
python backend/scripts/parse_race.py <am_url>  # dry-run одной гонки, глазами
```

### 2. Переименовать AM-гонки в catalog.yaml (убрать суффикс _am_kz)
В catalog.yaml УЖЕ есть 6 AM-гонок с суффиксом `_am_kz` (winter_run_am_kz,
almaty_marathon_am_kz, summer_relay_am_kz, tau_jarys_am_kz,
almaty_half_marathon_am_kz, almaty_copa_run_am_kz), все с `source: almaty-marathon`
и готовыми URL. Суффикс `_am_kz` раньше прятал грязные данные — теперь данные чистые.

**Решение: переименовать (убрать `_am_kz`), НЕ удалять** — URL уже собраны, парсер настроен.
Для пилота переименовать одну гонку:
```yaml
# Было: id: almaty_half_marathon_am_kz
# Стало:
- id: almaty_half_marathon
  name: Almaty Half Marathon
  source: almaty-marathon   # ← триггерит AlmatyMarathonParser + source=am
  editions:
    - year: 2025
      url: https://almaty-marathon.kz/ru/results/almaty_half_marathon_2025
```
(Остальные 5 переименуем в step_6 при массовой загрузке.)

### 3. Парсинг пилота
```bash
python backend/scripts/batch_parse.py --race-id almaty_half_marathon --force
```

## Проверка качества (глазами + SQL)

```bash
# AM-бегуны помечены source=am, изолированы от athletex
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c \
  "SELECT source, COUNT(*) FROM runners GROUP BY source;"
# Ожидаем: athletex (старые) + am (новые), два набора

# Нет склеек AM с athletex: один name_normalized не должен иметь оба source
# под одним runner_id (это невозможно по constraint, но проверим распределение)
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT name_normalized, COUNT(DISTINCT source) FROM runners
GROUP BY name_normalized HAVING COUNT(DISTINCT source) > 1 LIMIT 10;"
# Ожидаем: могут быть строки (один человек в обоих источниках = 2 runner) — это ОК,
# это и есть изоляция. Главное — это РАЗНЫЕ runner.id.

# Кириллические алиасы сохранены (для поиска по-русски)
PGPASSWORD=secret "...psql.exe" -h localhost -U gpx_predictor -d gpx_predictor -c "
SELECT name, source FROM runner_name_aliases WHERE name ~ '[а-яА-Я]' LIMIT 10;"
# Ожидаем: кириллические имена с source=am
```

## Smoke на портале (локально)
- [ ] Поиск «Каримов» (кириллица) → находит AM-бегуна
- [ ] Поиск «Karimov» (латиница) → находит (через транслит-алиас)
- [ ] Карточка AM-гонки открывается, результаты на месте
- [ ] Профиль AM-бегуна показывает только его AM-забеги (не смешано с чужими)

## Критерии готовности
- [ ] Гонка AM залита, парсер отработал формат таблицы корректно
- [ ] AM-бегуны имеют source='am'
- [ ] Поиск по-русски и по-английски работает
- [ ] Профили чистые (нет смешения чужих забегов)
- [ ] Глазами проверено ~20 случайных AM-бегунов — адекватно
