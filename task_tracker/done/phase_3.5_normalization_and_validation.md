# Phase 3.5: Нормализация клубов + валидация данных

## Контекст

После Phase 3 (batch parsing) у нас 53K+ результатов в БД из двух источников:
- **CLAX (myrace.info):** 27K результатов, 16 гонок — имена латиницей, клубы из XML
- **Almaty Marathon (almaty-marathon.kz):** 26K результатов, 6 гонок — имена кириллицей, поле "club" = город (не клуб!)

### Проблемы

1. **Клубы не нормализованы** — "SkyRunGroup", "Sky Run Group", "SRG", "Скай Ран Груп" = один клуб
2. **"Пусто"** — 124 записи с club="Пусто" (парсер сохранил русское слово вместо null)
3. **AM: city вместо club** — am_parser пишет город в поле club (`club=city`). Это не клуб, а город. Нужно разделить.
4. **Валидация** — нет способа убедиться, что данные в БД совпадают с оригиналом

### Что уже есть

- `name_utils.py` — `normalize_name()` для имён участников (lowercase + sort words)
- `batch_parse.py` — `save_to_db()` уже вызывает `normalize_name()` для `name_normalized`
- `db_models.py` — поле `club` в `RaceResultDB` (String(255), nullable, без индекса)
- `catalog.yaml` — все URL для re-parse

---

## Задача 1: Нормализация клубов

### 1.1 Справочник алиасов клубов

Создать `content/races/club_aliases.yaml`:

```yaml
# Нормализация названий клубов.
# Ключ — каноническое название, значение — список алиасов (lowercase).
clubs:
  SkyRunGroup:
    - skyrungroup
    - sky run group
    - sky running group
    - srg
    - скай ран груп
  HomeRun:
    - homerun
    - home run
    - хоум ран
    - хоумран
  # ...остальные клубы
```

**Как собрать:** SQL-запрос на все уникальные клубы → ручная группировка (с помощью AI).

### 1.2 Функция normalize_club()

В `name_utils.py` добавить:

```python
def normalize_club(club: str, aliases: dict[str, list[str]]) -> str | None:
    """Normalize club name using aliases dictionary.

    Returns canonical name or original (title-cased) if no alias found.
    Returns None for empty/garbage values.
    """
```

Логика:
1. strip + lowercase
2. Если пусто, "-", "пусто", "нет" → return None
3. Поиск в aliases → canonical name
4. Если не найден → original.strip() (оставляем как есть)

### 1.3 Поле club_normalized в БД

**Вариант A (простой):** Не добавлять колонку, нормализовать on-the-fly при чтении.
**Вариант B (правильный):** Добавить `club_normalized` колонку + индекс, заполнять при parse.

→ **Выбрать вариант B**, аналогично `name_normalized`. Alembic миграция.

### 1.4 Обновить batch_parse.py

В `save_to_db()` добавить:
```python
club_normalized=normalize_club(r.club, aliases)
```

### 1.5 Backfill: обновить существующие записи

Скрипт или команда в batch_parse.py: `--normalize-clubs` — пройти все записи, применить normalize_club().

---

## Задача 2: AM city vs club

В am_parser.py поле `club=city` — это город, не клуб.

### 2.1 Добавить поле city в модели

- `RaceResult` dataclass → добавить `city: str | None = None`
- `RaceResultDB` → добавить `city` Column(String(255))
- Alembic миграция

### 2.2 Обновить am_parser.py

Вместо `club=city` → `city=city, club=None`.

### 2.3 Обновить batch_parse.py

`save_to_db()` → сохранять `city` если есть.

### 2.4 Re-parse AM данных

```bash
python backend/scripts/batch_parse.py --all --force
```

Это перепарсит AM-гонки с правильным city/club разделением.

---

## Задача 3: Очистка мусорных значений

### 3.1 Garbage club values

При нормализации: "Пусто", "-", "нет", пустая строка → `club = None, club_normalized = None`.

### 3.2 Применить при backfill

Включить в скрипт нормализации (задача 1.5).

---

## Задача 4: Валидация данных (validate_data.py)

### 4.1 Скрипт validate_data.py

Для каждой edition в catalog.yaml с `status: parsed`:
1. Скачать оригинал (CLAX XML или AM HTML)
2. Спарсить заново
3. Загрузить из БД
4. Сравнить:

| Метрика | Проверка |
|---------|----------|
| Кол-во дистанций | exact match |
| Финишёры на дистанцию | exact match |
| 1-е место: имя + время | exact match |
| Последнее место: имя + время | exact match |
| Кол-во уникальных клубов | exact match |
| Людей с клубами | exact match |

### 4.2 Вывод

```
✅ alpine_race_kz 2025: OK (3 dist, 1847 results)
❌ tengri_ultra_kz 2024: MISMATCH
   - Skyrunning: source=245 finishers, DB=243 finishers
   - 1st place: source="Iyemberdiyev Diyas" 00:52:05, DB="Iyemberdiyev Diyas" 00:52:05 ✓
```

### 4.3 --fix flag

Опционально: если MISMATCH — предложить re-parse (`--fix` пересохраняет из source).

---

## Порядок реализации

1. **Задача 2** (city vs club) — сначала, чтобы не нормализовать города как клубы
2. **Задача 1** (нормализация клубов) — после разделения city/club
3. **Задача 3** (мусор) — вместе с задачей 1
4. **Задача 4** (валидация) — последней, чтобы проверить всё вместе

**Оценка:** ~200 строк нового кода + миграция + YAML-справочник.

---

## Зависимости

- От Phase 3: ✅ завершена
- Блокирует Phase 5 (клубы из результатов): нужны нормализованные клубы
- Не блокирует Phase 4 (веб-дашборд): дашборд не показывает клубы

---

## Задача 5: Нормализация таблицы clubs (NEW — step 5.5a)

### Контекст

В step 5.5a создана таблица `clubs` с `name_normalized = LOWER(TRIM(name))`.
Ручной мерж дублей уже сделан (step 5.5a, 2026-03-01):

| Target | Поглощённые | Причина |
|--------|-------------|---------|
| SkyRunGroup (160) | "Sky Run Group" (16), "SRG" (4) | слитно/раздельно + акроним |
| Iron City Kokshetau (9) | "Ironcity Kokshetau" (2) | слитно/раздельно |
| Uralsk Runners (10) | "Uralskrunners" (4) | слитно/раздельно |
| Oi-Qaragai (1) | "Oi Qaragai" (1) | дефис/пробел |

"Sky Run Girls" (2 runners) — оставлена отдельно (другой клуб).

### Что нужно сделать

1. **Улучшить `normalize_club()` для clubs таблицы:**
   - Текущая: `LOWER(TRIM(name))` — ловит только регистр и пробелы по краям
   - Нужно: убирать лишние пробелы, дефисы→пробелы, точки в аббревиатурах
   - Но: агрессивная нормализация может создать ложные слияния (e.g. "Run" vs "R.U.N.")

2. **Кириллица в клубах:**
   - Казахские/русские клубы: "Бег с удовольствием", "Экстремальная Атлетика"
   - Потенциальные дубли: кириллица↔латиница ("Скай Ран Груп" vs "SkyRunGroup")
   - Нужна транслитерация для cross-script matching (задача 1.1 club_aliases.yaml)

3. **Справочник алиасов** (задача 1.1) должен покрывать и клубы в таблице `clubs`:
   - При batch_parse: `get_or_create_club()` должен использовать алиасы
   - При мерже: скрипт для объединения дублей в `clubs` + обновления `runners.club_id`

---

## Открытые вопросы

1. **Справочник клубов:** Нужно вручную свести ~460 уникальных названий. Сколько реальных клубов получится — неизвестно (оценка: 200-300).
2. **AM city:** Стоит ли показывать city в будущем UI? Если да — нужно поле. Если нет — можно просто обнулить club для AM.
3. **Кириллица в именах AM:** normalize_name() работает с кириллицей (lowercase + sort), но матчинг кириллица↔латиница не делаем (это отдельная задача, транслитерация).
4. **Кириллица в клубах:** Транслитерация клубов (кириллица↔латиница) — решать вместе с задачей 1.1 (справочник алиасов).
5. **Историчность клубов у runners:** В таблице `runners` хранится только последний известный клуб (`club`, `club_id`). Но бегун мог менять клубы — например, из 166 человек, когда-либо бегавших за SkyRunGroup, только 96 сейчас числятся в этом клубе (остальные сменили клуб или бегали позже без клуба). Нужно решить:
   - Показывать ли историю клубов бегуна? (через `race_results.club`)
   - Как считать `runners_count` для клуба — текущих участников или всех, кто когда-либо бегал?
   - Нужна ли отдельная таблица `runner_club_history` для отслеживания переходов?
