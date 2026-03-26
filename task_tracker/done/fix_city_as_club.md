# Fix: города в поле club

## Проблема
AM парсер (`am_parser.py:327`) пишет город участника в поле `club`:
```python
club=city,  # use city as club (closest equivalent)
```
В результате "Алматы" (15600 runners), "Астана" (872) и т.д. попали в таблицу `clubs` и считаются клубами в статистике на главной.

## Стратегия
1. Фиксим код (city поле + AM парсер + миграция)
2. Чистим города-клубы SQL на локалке (БЕЗ перепарса AM)
3. TRUNCATE + COPY на прод

AM гонки не перепарсим — они скрыты фильтром `_am_kz` и сейчас не нужны.

---

## Порядок реализации

### 1. Добавить поле `city` в модели и БД

**1.1** `backend/app/features/races/models.py` — RaceResult dataclass:
```python
city: str | None = None  # добавить после club
```

**1.2** `backend/app/features/races/db_models.py` — RaceResultDB:
```python
city = Column(String(255), nullable=True)  # добавить после club
```

**1.3** Alembic миграция `016_add_city`:
```python
op.add_column('race_results', sa.Column('city', sa.String(255), nullable=True))
```

### 2. Фикс AM парсера (для будущих парсов)

**2.1** `backend/app/features/races/am_parser.py` строка 327:
```python
# Было:
club=city,  # use city as club (closest equivalent)

# Стало:
club=None,
city=city,  # город — не клуб
```

### 3. Фикс batch_parse.py — сохранение city

**3.1** `backend/scripts/batch_parse.py` — в функции `save_to_db()`:
- При создании RaceResultDB добавить `city=r.city`

### 4. Коммит и деплой кода

**4.1** Коммит:
- `am_parser.py` — club=None, city=city
- `models.py` — city field
- `db_models.py` — city column
- `batch_parse.py` — save city
- Alembic миграция 016

**4.2** Push в main → Railway auto-deploy.
Миграция `016_add_city` пройдёт автоматически (start.sh → alembic upgrade head).

### 5. Чистка городов-клубов на локалке (SQL)

**5.1** Составить список city-club IDs — клубы, где `name` = название города:
```sql
-- Найти все клубы-города (кириллица + латиница)
SELECT id, name, runners_count FROM clubs
WHERE name IN (
  'Алматы','Астана','Москва','Шымкент','Бишкек','Караганда','Актобе',
  'Талдыкорган','Ташкент','Тараз','Атырау','Павлодар','Усть-Каменогорск',
  'Семей','Костанай','Актау','Кызылорда','Петропавловск','Туркестан',
  'Уральск','Кокшетау','Алматинская область',
  'Almaty','Astana','Moscow','Bishkek','Tashkent'
  -- ... + проверить clubs_export.csv на оставшиеся города
);
```

**5.2** Обнулить `club_id` у runners, привязанных к городам:
```sql
UPDATE runners SET club_id = NULL, club = NULL
WHERE club_id IN (<city_club_ids>);
```

**5.3** Удалить города из таблицы `clubs`:
```sql
DELETE FROM clubs WHERE id IN (<city_club_ids>);
```

**5.4** Пересчитать `runners_count` у оставшихся клубов:
```sql
UPDATE clubs SET runners_count = (
    SELECT COUNT(*) FROM runners WHERE runners.club_id = clubs.id
);
```

### 6. Проверка на локалке

**6.1** Топ клубов — должны быть настоящие клубы:
```sql
SELECT name, runners_count FROM clubs ORDER BY runners_count DESC LIMIT 20;
-- Ожидаем: Бег с удовольствием, HomeRun, SkyRunGroup, Alay.pro, ...
```

**6.2** Запустить фронт + бэкенд, проверить статистику на главной.

### 7. Полная перезаливка на прод (COPY)

**7.1** TRUNCATE на проде:
```sql
TRUNCATE race_results, race_distances, race_editions, races, runners, clubs CASCADE;
```

**7.2** Экспорт из локалки (порядок FK):
```bash
\copy clubs TO 'C:/tmp/clubs.csv' CSV HEADER
\copy runners TO 'C:/tmp/runners.csv' CSV HEADER
\copy races TO 'C:/tmp/races.csv' CSV HEADER
\copy race_editions TO 'C:/tmp/race_editions.csv' CSV HEADER
\copy race_distances TO 'C:/tmp/race_distances.csv' CSV HEADER
\copy race_results TO 'C:/tmp/race_results.csv' CSV HEADER
```

**7.3** Импорт на прод (в том же порядке):
```bash
\copy clubs FROM 'C:/tmp/clubs.csv' CSV HEADER
\copy runners FROM 'C:/tmp/runners.csv' CSV HEADER
\copy races FROM 'C:/tmp/races.csv' CSV HEADER
\copy race_editions FROM 'C:/tmp/race_editions.csv' CSV HEADER
\copy race_distances FROM 'C:/tmp/race_distances.csv' CSV HEADER
\copy race_results FROM 'C:/tmp/race_results.csv' CSV HEADER
```

**7.4** Обновить sequences:
```sql
SELECT setval('clubs_id_seq', (SELECT MAX(id) FROM clubs));
SELECT setval('runners_id_seq', (SELECT MAX(id) FROM runners));
SELECT setval('race_editions_id_seq', (SELECT MAX(id) FROM race_editions));
SELECT setval('race_distances_id_seq', (SELECT MAX(id) FROM race_distances));
SELECT setval('race_results_id_seq', (SELECT MAX(id) FROM race_results));
```

### 8. Верификация на проде

**8.1** Проверить `https://ayda.run` — статистика клубов корректная.
**8.2** Проверить страницы гонок и профили бегунов.
