# Фаза 0: CLAX парсер + CLI просмотр

## Цель

Спарсить результаты Alpine Race из CLAX (XML), сохранить в JSON, посмотреть статистику в терминале. Найти Рената в результатах.

## Архитектура

```
content/
└── races/
    └── results/                     # Сюда сохраняем спарсенные JSON
        └── alpine_race_2025.json

backend/
├── app/features/races/              # Новый feature module
│   ├── __init__.py
│   ├── models.py                    # Dataclasses: RaceResult, RaceStats, etc.
│   ├── clax_parser.py               # CLAX XML → RaceEditionData
│   └── stats.py                     # Статистика + поиск по имени
│
└── scripts/
    └── parse_race.py                # CLI скрипт: парсинг + просмотр
```

## Reference: ayda_run analytics

В `C:\Users\renat\projects\02_ayda_run_v2\internal\analytics\race_cards\` есть:
- `models.py` — `ParticipantResult` (поля: bib, name, time, place, club, category, gender, pace, checkpoints, distance_km, elevation_gain). Использовать как чеклист полей.
- `parser.py` — `MyRaceParser` (Playwright-based). Мы НЕ копируем парсер (наш через XML), но полезен как reference для структуры данных myrace.
- `generator.py` + `templates/` — генерация PNG карточек. Пригодится позже для шеринга (Фаза 2+).

## Задачи

### Задача 1: Модели данных

**Файл:** `backend/app/features/races/models.py`

**Reference:** сверить с `ayda_run/internal/analytics/race_cards/models.py: ParticipantResult`

```python
@dataclass
class RaceResult:
    name: str               # "Иванов Алексей"
    time_seconds: int       # 2052
    place: int              # 1
    category: str | None    # "М 30-39"
    gender: str | None      # "M" / "F"
    club: str | None        # "SRG"
    bib: str | None         # "123"
    pace: str | None        # "5:08" мин/км (если есть в CLAX)

@dataclass
class RaceDistanceResults:
    distance_name: str      # "Skyrunning"
    distance_km: float | None
    elevation_gain_m: int | None
    results: list[RaceResult]

@dataclass
class RaceEditionData:
    race_name: str          # "Alpine Race"
    year: int               # 2025
    date: str | None        # "2025-03-01"
    distances: list[RaceDistanceResults]

@dataclass
class RaceStats:
    finishers: int
    best_time_s: int
    worst_time_s: int
    median_time_s: int
    p25_time_s: int         # топ-25% (быстрые)
    p75_time_s: int         # топ-75% (медленные)
    time_buckets: list[TimeBucket]

@dataclass
class TimeBucket:
    label: str              # "< 40 мин"
    min_s: int
    max_s: int
    count: int
    percent: float
```

**Критерий готовности:** Модели импортируются без ошибок.

### Задача 2: CLAX парсер

**Файл:** `backend/app/features/races/clax_parser.py`

Логика:
1. Скачать CLAX файл по URL (requests.get — это просто XML)
2. Распарсить XML (xml.etree.ElementTree)
3. Извлечь секции: `<Engages>` (участники), `<Resultats>` (результаты), `<Etapes>` (дистанции)
4. Смэтчить участников с результатами по номеру (bib/dos)
5. Вернуть `RaceEditionData`

```python
class ClaxParser:
    def parse_url(self, url: str) -> RaceEditionData:
        """Скачать и распарсить CLAX файл."""

    def parse_file(self, path: str) -> RaceEditionData:
        """Распарсить локальный CLAX файл."""

    def _parse_xml(self, xml_content: str) -> RaceEditionData:
        """Основная логика парсинга."""
```

**Важно:** CLAX — XML формат myrace.info. Нет публичного API, но XML скачивается напрямую по URL из параметра `?f=`. Playwright НЕ нужен.

Структура XML (предположительно):
- `<Epreuve>` — метаданные гонки
- `<Etapes>` — этапы/дистанции
- `<Engages>` — участники (dos=номер, nom=имя, sx=пол, cat=категория)
- `<Resultats>` — результаты (temps=время, pl=место)

Точная структура станет ясна после скачивания первого файла. Парсер должен быть устойчив к отсутствующим полям.

**Критерий готовности:** `ClaxParser().parse_url(alpine_race_url)` возвращает `RaceEditionData` с результатами.

### Задача 3: Статистика и поиск

**Файл:** `backend/app/features/races/stats.py`

```python
def calculate_stats(results: list[RaceResult]) -> RaceStats:
    """Посчитать статистику по результатам дистанции."""
    # median, p25, p75
    # time_buckets: автоматическое разбиение на 5 бакетов

def search_by_name(results: list[RaceResult], query: str) -> list[RaceResult]:
    """Fuzzy поиск по имени (регистронезависимый, частичное совпадение)."""

def get_percentile(results: list[RaceResult], time_seconds: int) -> float:
    """В каком перцентиле находится данное время (0-100, где 0 = лучший)."""
```

**Критерий готовности:** `calculate_stats()` возвращает корректную статистику для тестовых данных.

### Задача 4: CLI скрипт

**Файл:** `backend/scripts/parse_race.py`

```bash
# Парсинг и сохранение
python backend/scripts/parse_race.py \
    --url "https://live.myrace.info/?f=bases/kz/2025/alpinrace2025/alpinrace2025.clax" \
    --save content/races/results/alpine_race_2025.json

# Поиск по имени
python backend/scripts/parse_race.py \
    --file content/races/results/alpine_race_2025.json \
    --search "Ренат"

# Статистика по дистанции
python backend/scripts/parse_race.py \
    --file content/races/results/alpine_race_2025.json \
    --stats --distance "Skyrunning"
```

Вывод в терминале:

```
=== Alpine Race 2025 — Skyrunning ===
Финишёров: 43
Лучший:    34:12 (Иванов Алексей)
Медиана:   1:02:40
Худший:    1:48:30

Распределение:
  < 40 мин    ██░░░░░░░░  5 (12%)   Элита
  40-55 мин   ████░░░░░░  9 (21%)   Быстрый
  55-75 мин   ██████░░░░ 14 (33%)   Средний
  75-100 мин  ████░░░░░░  10 (23%)  Медленный
  > 100 мин   ██░░░░░░░░  5 (12%)   Финишёр

🔍 Поиск "Ренат":
  #12  Кайратов Ренат  58:12  М 30-39  (топ-28%)
```

**Критерий готовности:** Скрипт работает end-to-end с реальным CLAX файлом Alpine Race.

### Задача 5: Сохранение результатов в JSON

**Директория:** `content/races/results/`

После парсинга сохранять JSON:

```json
{
  "race_name": "Alpine Race",
  "year": 2025,
  "date": "2025-03-01",
  "source_url": "https://live.myrace.info/...",
  "parsed_at": "2026-02-24T15:00:00",
  "distances": [
    {
      "name": "Skyrunning",
      "distance_km": 4.0,
      "elevation_gain_m": 900,
      "finishers": 43,
      "results": [
        {"name": "Иванов Алексей", "time_s": 2052, "place": 1, "category": "М 30-39", "gender": "M"},
        ...
      ],
      "stats": {
        "median_s": 3760,
        "p25_s": 2900,
        "p75_s": 4800
      }
    }
  ]
}
```

**Критерий готовности:** JSON файл сохраняется и загружается обратно без потерь.

## Порядок реализации

1. Задача 1 — модели
2. Задача 2 — CLAX парсер (основная работа — разобраться с форматом XML)
3. Задача 3 — статистика и поиск
4. Задача 4 — CLI скрипт
5. Задача 5 — сохранение JSON

## Зависимости

- `requests` — уже есть в requirements.txt
- `xml.etree.ElementTree` — стандартная библиотека
- Никаких новых зависимостей не нужно

## Что НЕ делаем в этой фазе

- Модели в БД (пока dataclasses + JSON файлы)
- Интеграцию с ботом
- Прогнозы на гонку (это Фаза 1)
- Route matching
- Race cards / генерацию картинок
