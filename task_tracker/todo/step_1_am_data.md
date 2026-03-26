# Шаг 1: АМ данные — нормализация + парсинг + загрузка

> Агент: Data Engineer + Backend
> Зависит от: нет
> Статус: in_progress
> Дедлайн: до 5 апреля 2026

---

## Подход

Не лить всё сразу. Сначала:
1. Аудит текущих данных (CLAX) — убедиться что фундамент чистый
2. Создать таблицы алиасов и обкатать на текущих данных (латиница)
3. Добавить транслитерацию кириллица → латиница
4. Залить одну гонку АМ — проверить матчинг
5. Массовая загрузка + деплой

---

## Фаза A: Аудит текущих данных + таблицы алиасов

Цель — убедиться что фундамент чистый, создать таблицы алиасов и заполнить из текущих CLAX данных.

### A1. Аудит бегунов

```sql
-- Общая статистика
SELECT COUNT(*) as total_runners FROM runners;
SELECT COUNT(*) as runners_without_club FROM runners WHERE club_id IS NULL;
SELECT COUNT(*) as runners_zero_races FROM runners WHERE races_count = 0;

-- Дубли по name_normalized (точные)
SELECT name_normalized, COUNT(*) as cnt, array_agg(id || ': ' || name)
FROM runners
GROUP BY name_normalized
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 30;

-- Fuzzy дубли (pg_trgm)
-- Сначала проверить что расширение есть:
SELECT * FROM pg_extension WHERE extname = 'pg_trgm';
-- Если нет: CREATE EXTENSION pg_trgm;

SELECT a.id, a.name, a.races_count,
       b.id, b.name, b.races_count,
       similarity(a.name, b.name) as sim
FROM runners a
JOIN runners b ON a.id < b.id
  AND similarity(a.name, b.name) > 0.7
  AND a.name_normalized != b.name_normalized
ORDER BY sim DESC
LIMIT 30;

-- Формат имён: есть ли кириллица?
SELECT id, name, name_normalized
FROM runners
WHERE name ~ '[а-яА-ЯёЁ]'
LIMIT 20;

-- Формат имён: сколько слов в имени (1 слово = подозрительно)
SELECT LENGTH(name) - LENGTH(REPLACE(name, ' ', '')) + 1 as word_count,
       COUNT(*) as cnt
FROM runners
GROUP BY word_count
ORDER BY word_count;

-- Примеры имён (чтобы понять формат)
SELECT id, name, name_normalized, club, races_count
FROM runners
ORDER BY races_count DESC
LIMIT 20;
```

**Что ищем:**
- [x] Точные дубли `name_normalized` — 0 найдено ✓
- [x] Fuzzy дубли (Knyaz/Kniaz) — 55 пар смёрджены (коммит ef5e7ba)
- [x] Кириллические имена — 0 в CLAX данных ✓
- [x] Односложные имена — проверено, ок
- [x] Формат: "LastName FirstName" (CLAX стандарт)

### A2. Аудит клубов

```sql
-- Общая статистика
SELECT COUNT(*) as total_clubs FROM clubs;

-- Клубы с runners_count
SELECT id, name, name_normalized, runners_count
FROM clubs
ORDER BY runners_count DESC
LIMIT 40;

-- Клубы-города (НЕ должны быть клубами — это остатки от AM)
SELECT id, name, runners_count
FROM clubs
WHERE name IN (
  'Алматы', 'Астана', 'Москва', 'Шымкент', 'Бишкек',
  'Караганда', 'Актобе', 'Ташкент', 'Тараз', 'Атырау',
  'Павлодар', 'Семей', 'Усть-Каменогорск', 'Талдыкорган',
  'Almaty', 'Astana', 'Nur-Sultan'
);

-- Кириллические клубы
SELECT id, name, runners_count
FROM clubs
WHERE name ~ '[а-яА-ЯёЁ]'
ORDER BY runners_count DESC;

-- Подозрительные дубли клубов (похожие названия)
SELECT a.id, a.name, a.runners_count,
       b.id, b.name, b.runners_count,
       similarity(a.name, b.name) as sim
FROM clubs a
JOIN clubs b ON a.id < b.id
  AND similarity(a.name, b.name) > 0.6
ORDER BY sim DESC
LIMIT 30;

-- Клубы с 1 бегуном (шум)
SELECT COUNT(*) as clubs_with_1_runner
FROM clubs
WHERE runners_count = 1;
```

**Что ищем:**
- [x] Клубы-города — 0 найдено (AM данные были удалены ранее) ✓
- [x] Кириллические клубы — несколько найдены, ок (легитимные: "Бег с удовольствием", "Жүгірмектер")
- [x] Дубли клубов — 3 пары смёрджены + 4 ручных алиаса (коммит c92deb7)
- [x] Клубы с 1 бегуном — много, но это ок

### A3. AM данные в текущей БД

```sql
-- Есть ли AM данные?
SELECT r.id, r.name FROM races r WHERE r.id LIKE '%_am_kz';

-- Если есть — сколько результатов?
SELECT COUNT(*) as am_results
FROM race_results rr
JOIN race_distances rd ON rr.distance_id = rd.id
JOIN race_editions re ON rd.edition_id = re.id
WHERE re.race_id LIKE '%_am_kz';
```

**Результат:** AM данные отсутствуют в текущей БД ✓ (были удалены ранее).

### A4. Создать таблицы алиасов ✅

> Сделано: коммит 13420cc — миграция `018_add_name_aliases`, модели, batch_parse, search

Алиасы решают проблему множества написаний одного имени/клуба.
Каждый раз когда парсер видит новое написание — сохраняет как алиас.
Поиск идёт по алиасам — находит и кириллицу, и латиницу, и любые варианты.

**Миграция** `018_add_name_aliases`:

```sql
CREATE TABLE runner_name_aliases (
    id SERIAL PRIMARY KEY,
    runner_id INTEGER NOT NULL REFERENCES runners(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,          -- "KARIMOV Renat", "Karimov Renat", "Каримов Ренат"
    name_normalized VARCHAR(255) NOT NULL, -- "karimov renat" (lowercase, sorted)
    source VARCHAR(50) NOT NULL,          -- "clax", "am", "manual"
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_runner_aliases_runner_id ON runner_name_aliases(runner_id);
CREATE INDEX ix_runner_aliases_name_norm ON runner_name_aliases(name_normalized);
CREATE UNIQUE INDEX ix_runner_aliases_unique ON runner_name_aliases(runner_id, name_normalized);

CREATE TABLE club_name_aliases (
    id SERIAL PRIMARY KEY,
    club_id INTEGER NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,           -- "SRG", "S.R.G.", "Sky Run Group"
    name_normalized VARCHAR(255) NOT NULL, -- "srg", "s.r.g.", "sky run group"
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_club_aliases_club_id ON club_name_aliases(club_id);
CREATE INDEX ix_club_aliases_name_norm ON club_name_aliases(name_normalized);
CREATE UNIQUE INDEX ix_club_aliases_unique ON club_name_aliases(club_id, name_normalized);
```

**Модели** в `db_models.py`:

```python
class RunnerNameAlias(Base):
    __tablename__ = "runner_name_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    runner_id = Column(Integer, ForeignKey("runners.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    name_normalized = Column(String(255), nullable=False)
    source = Column(String(50), nullable=False)  # "clax", "am", "manual"
    created_at = Column(DateTime, default=datetime.utcnow)

class ClubNameAlias(Base):
    __tablename__ = "club_name_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    club_id = Column(Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    name_normalized = Column(String(255), nullable=False)
    source = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### A5. Заполнить алиасы из текущих данных (CLAX) ✅

> Сделано: 13346 runner aliases, 422 club aliases заполнены из race_results

Сейчас в `race_results` уже хранятся все варианты написания имени бегуна
(каждый результат = конкретное написание). Собрать уникальные:

```sql
-- Заполнить runner_name_aliases из существующих race_results
INSERT INTO runner_name_aliases (runner_id, name, name_normalized, source)
SELECT DISTINCT rr.runner_id, rr.name, rr.name_normalized, 'clax'
FROM race_results rr
WHERE rr.runner_id IS NOT NULL
  AND rr.name IS NOT NULL
  AND rr.name_normalized IS NOT NULL
ON CONFLICT (runner_id, name_normalized) DO NOTHING;

-- Заполнить club_name_aliases из существующих race_results
INSERT INTO club_name_aliases (club_id, name, name_normalized, source)
SELECT DISTINCT r.club_id, rr.club, LOWER(TRIM(rr.club)), 'clax'
FROM race_results rr
JOIN runners r ON rr.runner_id = r.id
WHERE rr.club IS NOT NULL
  AND rr.club != ''
  AND r.club_id IS NOT NULL
ON CONFLICT (club_id, name_normalized) DO NOTHING;

-- Проверить: сколько алиасов получилось?
SELECT COUNT(*) as total_runner_aliases FROM runner_name_aliases;
SELECT runner_id, COUNT(*) as cnt
FROM runner_name_aliases
GROUP BY runner_id
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 20;
-- ^ Бегуны с >1 алиасом = разные написания в разных гонках

SELECT COUNT(*) as total_club_aliases FROM club_name_aliases;
SELECT club_id, COUNT(*) as cnt
FROM club_name_aliases
GROUP BY club_id
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 10;
```

### A6. Обновить batch_parse.py — запись алиасов ✅

> Сделано: коммит 13420cc

При сохранении результата добавлять алиас (если ещё нет):

```python
# В save_to_db(), после создания/обновления runner:
alias_norm = normalize_name(r.name)
existing_alias = db.execute(
    select(RunnerNameAlias).where(
        RunnerNameAlias.runner_id == runner.id,
        RunnerNameAlias.name_normalized == alias_norm,
    )
).scalar_one_or_none()
if not existing_alias:
    db.add(RunnerNameAlias(
        runner_id=runner.id,
        name=r.name,
        name_normalized=alias_norm,
        source=source,  # "clax" или "am"
    ))

# Аналогично для клубов
```

### A7. Обновить поиск — искать по алиасам ✅

> Сделано: коммит 13420cc — search_runners() JOIN с RunnerNameAlias

В `repository.py`:

```python
def search_runners(self, name: str, limit: int = 10) -> list[Runner]:
    norm = normalize_name(name)
    norm_words = norm.split()

    # Ищем по алиасам: любой вариант написания
    alias_filters = [RunnerNameAlias.name_normalized.contains(word) for word in norm_words]

    return self.db.execute(
        select(Runner)
        .join(RunnerNameAlias, RunnerNameAlias.runner_id == Runner.id)
        .where(*alias_filters)
        .group_by(Runner.id)
        .order_by(Runner.races_count.desc())
        .limit(limit)
    ).scalars().all()
```

Поиск теперь находит бегуна по **любому** из его алиасов.
Когда добавим кириллические алиасы (фаза C) — поиск "Каримов" заработает автоматически.

### A8. Критерии "фаза A done"

- [x] 0 точных дублей `name_normalized`
- [x] 0 клубов-городов (Алматы, Астана и т.д.)
- [x] 0 кириллических имён в runners
- [x] Fuzzy дубли — 55 пар смёрджены, 3 пары клубов смёрджены
- [x] AM данные удалены
- [x] Таблицы `runner_name_aliases` и `club_name_aliases` созданы
- [x] Алиасы заполнены из текущих CLAX данных
- [x] `batch_parse.py` пишет алиасы при сохранении
- [x] Поиск работает через алиасы
- [x] Бегуны с несколькими вариантами написания — находятся по любому
- [x] Резолв клубов через алиасы в batch_parse.py (SRG → SkyRunGroup)
- [x] Клубы у бегунов исправлены по последнему результату (394 обновлены)

### A9. Fuzzy check в batch_parse — предотвращение дублей ✅

> Сделано: коммит 9b82d8b — _fuzzy_match_runner() в batch_parse.py

В `save_to_db()`: после exact match по `name_normalized`, если не нашёл бегуна
и есть `birth_year` → fuzzy check через pg_trgm:
- similarity > 0.85 + birth_year = → авто-мёрдж
- similarity 0.7-0.85 + birth_year = → warning в консоль для ручной проверки
- Без birth_year → пропуск (слишком рискованно)

Проверено на данных: 24 существующих дубля при 0.85, все реальные, 0 ложных.

---

## Фаза B: Транслитерация кириллица → латиница

Цель — добавить конвертацию, чтобы "Каримов Ренат" → "karimov renat" совпало с CLAX.

### B1. Ресёрч: какую транслитерацию использует CLAX

**Проблема:** один и тот же кириллический текст можно транслитерировать по-разному:
- Ш → Sh (ISO 9) или Sh (BGN/PCGN) или S (паспортная)
- Ж → Zh или J (казахская)
- Х → H или Kh
- Ю → Yu или Iu
- Я → Ya или Ia

**Задача:**
1. [ ] Найти 10-20 бегунов с результатами на обоих сайтах (AM и CLAX)
2. [ ] Сравнить написание: кириллица на AM vs латиница на CLAX
3. [ ] Определить таблицу транслитерации CLAX
4. [ ] Проверить казахские буквы (Ә, Ғ, Қ, Ң, Ө, Ұ, Ү, Һ, І)

**Примеры для проверки** (на almaty-marathon.kz и myrace.info):
- "Каримов Ренат" → ?
- "Бакашев Шынгыс" → ?
- "Кунаев Данияр" → ?

### B2. Казахские буквы

Казахский алфавит содержит буквы, которых нет в русском:
- Ә → A или Ae
- Ғ → G или Gh
- Қ → K или Q
- Ң → N или Ng
- Ө → O или Oe
- Ұ → U
- Ү → U или Ue
- Һ → H
- І → I

Нужно учесть, т.к. многие участники АМ — казахи.

### B3. Реализация

```python
# name_utils.py — добавить

_CYRILLIC_TO_LATIN = {
    # Определить на основе анализа B1
    'а': 'a', 'б': 'b', 'в': 'v', ...
    # Казахские
    'ә': 'a', 'ғ': 'g', 'қ': 'k', ...
}

def transliterate_cyrillic(name: str) -> str:
    """Transliterate Cyrillic name to Latin.

    Uses the same transliteration standard as CLAX/myrace.info
    for consistent matching.
    """
    result = []
    for char in name:
        lower = char.lower()
        if lower in _CYRILLIC_TO_LATIN:
            trans = _CYRILLIC_TO_LATIN[lower]
            result.append(trans.upper() if char.isupper() else trans)
        else:
            result.append(char)
    return ''.join(result)
```

### B4. Интеграция транслитерации в normalize_name

```python
def normalize_name(name: str) -> str:
    """Normalize a participant name for matching.

    Steps:
    1. If Cyrillic — transliterate to Latin
    2. Strip whitespace, collapse multiple spaces
    3. Lowercase
    4. Sort words alphabetically
    """
    if any('\u0400' <= c <= '\u04FF' for c in name):
        name = transliterate_cyrillic(name)
    name = re.sub(r"\s+", " ", name.strip()).lower()
    parts = sorted(name.split())
    return " ".join(parts)
```

### B5. Критерии "фаза B done"

- [ ] Таблица транслитерации определена (на основе сравнения AM ↔ CLAX)
- [ ] `transliterate_cyrillic()` реализована в `name_utils.py`
- [ ] `normalize_name()` вызывает транслитерацию для кириллицы
- [ ] Тесты: 10+ примеров кириллица → латиница совпадают с CLAX

---

## Фаза C: Пилот — одна гонка АМ

Цель — залить одну гонку АМ и проверить качество матчинга.

### C1. Выбрать гонку

Лучший кандидат: **Алматы Полумарафон 2024** (или Winter Run 2025).
- Много участников → хороший тест матчинга
- Многие из них бегали CLAX гонки → можно проверить мёрдж

### C2. Обновить am_parser.py

**Важно:** AM сайт использует **разные форматы таблиц** для разных гонок!

Старый формат (маршруты типа Half Marathon до ~2024):
```
Место | Участник | Страна | Город | Номер | [splits...] | Финиш | Чип время | Сертификат
```

Новый формат (Copa Run 2025, Half Marathon 2025):
```
Место | ФИО | Стартовый номер | Финиш время | Возрастная категория | Клуб | Страна | Дистанция
```

Парсер должен определять формат по заголовкам таблицы и парсить соответственно.

Задачи:
1. [ ] Определение формата по заголовкам (`<th>`) таблицы
2. [ ] Парсинг нового формата — клуб, возрастная категория, дистанция
3. [ ] Парсинг birth_year из возрастной категории (напр. "30-39" + год гонки → примерный birth_year)
4. [ ] После парсинга имени → `transliterate_cyrillic(name)` для `name` в результате
5. [ ] Сохранять **оригинальное кириллическое имя** — оно попадёт в алиас автоматически
   (batch_parse сохранит и транслитерированный вариант как name, и кириллический как алиас)
6. [ ] Клуб из AM парсить в `club` поле (если есть, если "null" → None)

### C3. Двойной алиас при парсинге AM

При парсинге AM гонки batch_parse должен сохранять **два алиаса**:
- Кириллический оригинал: "Каримов Ренат" (source="am")
- Транслитерированный: "Karimov Renat" (source="am")

Транслитерированный используется для матчинга (normalize_name → поиск runner).
Кириллический сохраняется как алиас — для поиска на портале.

### C4. Парсинг пилотной гонки

```bash
python backend/scripts/batch_parse.py --race-id almaty_half_marathon_kz --force
```

### C5. Проверка качества матчинга

```sql
-- Сколько бегунов АМ сматчились с существующими CLAX
WITH am_results AS (
  SELECT DISTINCT rr.runner_id, rr.name, rr.name_normalized
  FROM race_results rr
  JOIN race_distances rd ON rr.distance_id = rd.id
  JOIN race_editions re ON rd.edition_id = re.id
  WHERE re.race_id = 'almaty_half_marathon_kz'
)
SELECT
  COUNT(*) as total_am_runners,
  COUNT(CASE WHEN runner_id IN (
    SELECT DISTINCT rr2.runner_id
    FROM race_results rr2
    JOIN race_distances rd2 ON rr2.distance_id = rd2.id
    JOIN race_editions re2 ON rd2.edition_id = re2.id
    WHERE re2.race_id NOT LIKE '%_am_%'
      AND rr2.runner_id IS NOT NULL
  ) THEN 1 END) as matched_with_clax
FROM am_results;

-- Ручная проверка: 20 случайных бегунов — проверить глазами
SELECT r.id, r.name, r.name_normalized, r.club, r.races_count
FROM runners r
JOIN race_results rr ON rr.runner_id = r.id
JOIN race_distances rd ON rr.distance_id = rd.id
JOIN race_editions re ON rd.edition_id = re.id
WHERE re.race_id = 'almaty_half_marathon_kz'
AND r.races_count > 1  -- бегуны с гонками и из CLAX и из AM
ORDER BY RANDOM()
LIMIT 20;

-- Возможные ложные мёрджи: birth_year расхождение
SELECT r.id, r.name,
       rr_clax.birth_year as clax_by, rr_am.birth_year as am_by
FROM runners r
JOIN race_results rr_clax ON rr_clax.runner_id = r.id
JOIN race_distances rd_clax ON rr_clax.distance_id = rd_clax.id
JOIN race_editions re_clax ON rd_clax.edition_id = re_clax.id
JOIN race_results rr_am ON rr_am.runner_id = r.id
JOIN race_distances rd_am ON rr_am.distance_id = rd_am.id
JOIN race_editions re_am ON rd_am.edition_id = re_am.id
WHERE re_clax.race_id NOT LIKE '%_am_%'
  AND re_am.race_id = 'almaty_half_marathon_kz'
  AND rr_clax.birth_year IS NOT NULL
  AND rr_am.birth_year IS NOT NULL
  AND rr_clax.birth_year != rr_am.birth_year
LIMIT 20;

-- Проверить кириллические алиасы
SELECT rna.name, rna.name_normalized, rna.source, r.name as runner_display_name
FROM runner_name_aliases rna
JOIN runners r ON rna.runner_id = r.id
WHERE rna.name ~ '[а-яА-ЯёЁ]'
LIMIT 20;
```

### C6. Проверка поиска на кириллице

На портале:
- [ ] Поиск "Каримов" → находит бегуна (через кириллический алиас)
- [ ] Поиск "Karimov" → находит того же бегуна (через латинский алиас)
- [ ] Профиль бегуна показывает и CLAX и AM результаты

### C7. Критерии "пилот прошёл"

- [ ] >50% бегунов АМ, которые бегали CLAX, сматчились корректно
- [ ] <5% ложных мёрджей (проверка по birth_year, gender)
- [ ] Нет дублей клубов
- [ ] Поиск на портале работает для кириллицы и латиницы
- [ ] Кириллические алиасы сохранены в runner_name_aliases

---

## Фаза D: Массовая загрузка

Только после успешного пилота (фаза C).

### D1. Парсинг всех гонок АМ

```yaml
# catalog.yaml — добавить (БЕЗ суффикса _am_kz):
- id: almaty_marathon_kz
  name: Almaty Marathon
  source: almaty-marathon
  editions:
    - year: 2023
      url: https://almaty-marathon.kz/ru/results/almaty_marathon_2023
    - year: 2024
      url: https://almaty-marathon.kz/ru/results/almaty_marathon_2024
    # и т.д. для всех доступных годов
```

1. [ ] Собрать все URL гонок с almaty-marathon.kz
2. [ ] Добавить в catalog.yaml
3. [ ] Парсить: `python backend/scripts/batch_parse.py --all --force`

### D2. Нормализация клубов АМ

У новых гонок AM (2025+) **есть поле "Клуб"** в таблице результатов.
У старых гонок AM клуба нет (city ≠ club).

Клубы из AM проходят через `_resolve_club()` в batch_parse:
- Если клуб уже есть в `clubs` или `club_name_aliases` → привяжет к каноническому
- Если новый клуб → создаст
- "null" в данных AM → club=None (не создаёт клуб)

После загрузки: проверить новые клубы на дубли с CLAX клубами.

### D3. Убрать фильтры _am_kz из кода

1. [ ] Убрать фильтры `_am_kz` из:
   - `backend/app/api/v1/routes/stats.py` — фильтр в season stats
   - `backend/app/api/v1/routes/races.py` — фильтр в списке гонок
   - `frontend/src/utils/races.ts` — `getRaceCategory()`
2. [ ] Удалить старые AM данные с `_am_kz` суффиксом (если ещё есть)

### D4. Финальная проверка

```sql
-- Общая статистика после загрузки
SELECT COUNT(*) as runners FROM runners;
SELECT COUNT(*) as results FROM race_results;
SELECT COUNT(*) as clubs FROM clubs;
SELECT COUNT(*) as runner_aliases FROM runner_name_aliases;
SELECT COUNT(*) as club_aliases FROM club_name_aliases;

-- Дубли — не должно быть новых
SELECT name_normalized, COUNT(*) as cnt
FROM runners
GROUP BY name_normalized
HAVING COUNT(*) > 1
ORDER BY cnt DESC;

-- Кириллица в runners.name — не должно быть (только в алиасах)
SELECT COUNT(*) FROM runners WHERE name ~ '[а-яА-ЯёЁ]';

-- Кириллические алиасы — должны быть
SELECT COUNT(*) FROM runner_name_aliases WHERE name ~ '[а-яА-ЯёЁ]';
```

### D5. Dump перед деплоем + деплой на прод

1. [ ] **Dump текущей продовой БД** (на случай отката):
   ```bash
   pg_dump -h <prod_host> -p <prod_port> -U postgres -d railway -F c -f prod_backup_before_am.dump
   ```
2. [ ] Экспорт из локальной БД (COPY CSV) — включая таблицы алиасов
3. [ ] TRUNCATE на проде (порядок FK: results → distances → editions → races → runner_aliases → club_aliases → runners → clubs)
4. [ ] Импорт на прод (COPY CSV)
5. [ ] Smoke test: поиск "Каримов", поиск "Karimov", профиль, гонка

---

## Чеклист готовности (для всего шага 1)

- [ ] Фаза A: данные чистые, алиасы созданы и заполнены, поиск через алиасы
- [ ] Фаза B: транслитерация работает, совпадает с CLAX
- [ ] Фаза C: пилот одной гонки АМ прошёл, кириллический поиск работает
- [ ] Фаза D: все гонки АМ загружены, _am_kz убран
- [ ] Задеплоено на прод (с бэкапом перед деплоем)
- [ ] Smoke test на проде: поиск "Каримов" → находит профиль с CLAX + АМ результатами
