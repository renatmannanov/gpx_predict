# Шаг 5.5a: Бэкенд — API для Race Insights

## Цель

Подготовить все API endpoints для фронтенд-шагов 5.5b-5.5e.
Один шаг бэкенда — все фронтенд-шаги зависят от него.

**Ветка:** `web-portal-step-5.5a`
**Зависит от:** Шаги 3, 5 (results API, search API).

---

## Что делать

### A1. Расширить stats — gender/category distribution + club_stats

**Изменить** `backend/app/features/races/stats.py`:

Добавить вычисление в `calculate_stats()` (или отдельные функции):

**gender_distribution:**
```python
[{"gender": "M", "count": 180, "percent": 73.5},
 {"gender": "F", "count": 65, "percent": 26.5}]
```
- Считаем только непустые `gender` значения
- Если все `gender=None` → пустой список

**category_distribution:**
```python
[{"category": "M_30-39", "count": 52, "percent": 21.2},
 {"category": "M_20-29", "count": 45, "percent": 18.4}, ...]
```
- Считаем только непустые `category` значения
- Сортировка по count descending
- Если все `category=None` → пустой список

**club_stats:**
```python
[{"club": "SRG", "count": 12, "best_time_s": 3125, "best_time": "52:05",
  "avg_percentile": 18.3},
 {"club": "RUNFINITY", "count": 8, "best_time_s": 3252, "best_time": "54:12",
  "avg_percentile": 25.1}, ...]
```
- Группировка по `club` (непустые значения)
- Минимум 2 участника для попадания в рейтинг
- Сортировка по avg_percentile ascending (лучший клуб первый)
- avg_percentile = среднее от персентилей всех участников клуба
- Если все `club=None` → пустой список

**Добавить dataclass-ы** в `backend/app/features/races/models.py`:
```python
@dataclass
class GenderDistribution:
    gender: str
    count: int
    percent: float

@dataclass
class CategoryDistribution:
    category: str
    count: int
    percent: float

@dataclass
class ClubStats:
    club: str
    count: int
    best_time_s: int
    avg_percentile: float
```

**Расширить RaceStats dataclass:**
```python
@dataclass
class RaceStats:
    # ... existing fields ...
    gender_distribution: list[GenderDistribution] = field(default_factory=list)
    category_distribution: list[CategoryDistribution] = field(default_factory=list)
    club_stats: list[ClubStats] = field(default_factory=list)
```

### A2. Обновить RaceStatsSchema в API

**Изменить** `backend/app/api/v1/routes/races.py`:

Добавить новые поля в `RaceStatsSchema`:
```python
class RaceStatsSchema(BaseModel):
    # ... existing fields ...
    gender_distribution: list[dict] = []
    category_distribution: list[dict] = []
    club_stats: list[dict] = []
```

Обновить сериализацию в endpoint `get_results()` — передавать новые поля из stats.

### A3. Расширить search endpoint — персентили

**Изменить** `backend/app/api/v1/routes/races.py`:

Обновить `SearchResultSchema`:
```python
class SearchResultSchema(BaseModel):
    year: int
    result: Optional[RaceResultSchema] = None
    # NEW:
    percentile: Optional[float] = None          # 0-100, lower = faster
    total_finishers: Optional[int] = None
    gender_percentile: Optional[float] = None   # percentile within same gender
    category_rank: Optional[int] = None         # rank within category
    category_total: Optional[int] = None        # total in category
```

**Изменить** `search_results()` endpoint:
- После поиска участника — загрузить все результаты этого года/дистанции
- Вычислить персентиль (общий, по полу, по категории)
- Использовать существующую функцию `get_percentile()` из `stats.py`

Для gender_percentile:
- Отфильтровать results по тому же `gender`
- Вычислить персентиль внутри отфильтрованного списка

Для category_rank/category_total:
- Отфильтровать results по той же `category`
- rank = позиция в отфильтрованном списке
- total = длина отфильтрованного списка

### A4. Добавить total_finishers в RaceSchema

**Изменить** `backend/app/api/v1/routes/races.py`:

Добавить поле:
```python
class RaceSchema(BaseModel):
    # ... existing fields ...
    total_finishers: Optional[int] = None  # sum across all distances, latest year
```

**Изменить** `list_races()` и `get_race()`:
- Для последнего edition: посчитать сумму финишёров по всем дистанциям
- Использовать `repo.count_finishers(race_id, year)` или аналогичный метод

**Добавить в RaceRepository:**
```python
def count_finishers(self, race_id: str, year: int) -> int:
    """Count total finishers across all distances for a race edition."""
```

### A5. Новый endpoint — Runner Profile

**Добавить** новый router `backend/app/api/v1/routes/runners.py`:

```python
@router.get("/{name_normalized}", response_model=RunnerProfileResponse)
async def get_runner_profile(name_normalized: str, db: Session = Depends(get_db)):
    """Get runner profile with all race results across all races."""
```

**Schemas:**
```python
class RunnerProfileSchema(BaseModel):
    name: str
    name_normalized: str
    club: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None

class RunnerRaceResultSchema(BaseModel):
    race_id: str
    race_name: str
    distance_name: str
    distance_km: Optional[float] = None
    year: int
    time_s: int
    time_formatted: str
    place: int
    total_finishers: int
    percentile: float
    category: Optional[str] = None
    club: Optional[str] = None

class RunnerProfileResponse(BaseModel):
    profile: RunnerProfileSchema
    results: list[RunnerRaceResultSchema]
    total_races: int
    years_active: int
    median_percentile: Optional[float] = None
```

**Логика:**
1. Нормализовать `name_normalized` (на случай URL-кодирования)
2. Запросить все `race_results` WHERE `name_normalized = :norm` (JOIN distances, editions, races)
3. Для каждого результата: посчитать total_finishers и percentile в рамках той же дистанции/года
4. Собрать profile из последнего результата (club, category, gender)
5. Вычислить years_active, total_races, median_percentile
6. Отсортировать results: year DESC, race_name ASC

**Добавить в RaceRepository** (или создать RunnerRepository):
```python
def get_runner_results(self, name_normalized: str) -> list[tuple]:
    """Get all results for a runner across all races."""
```

### A6. Зарегистрировать runners router

**Изменить** `backend/app/main.py` (или `api/v1/__init__.py`):

```python
from app.api.v1.routes.runners import router as runners_router
app.include_router(runners_router, prefix="/api/v1/runners", tags=["runners"])
```

### A7. DNF: обновить парсеры и модель

Сейчас DNF/DNS участники отфильтровываются при парсинге. Нужно сохранять их в БД.

**A7.1 Обновить RaceResult dataclass** (`backend/app/features/races/models.py`):
```python
@dataclass
class RaceResult:
    # ... existing fields ...
    status: str = "finished"  # "finished" | "dnf" | "dns" | "dsq" | "over_time_limit"
```

Поле `over_time_limit: bool` → заменить на `status`. Миграция: `over_time_limit=True` → `status="over_time_limit"`.

**A7.2 Обновить DB модель** (`backend/app/features/races/db_models.py`):
```python
class RaceResultDB(Base):
    # ... existing ...
    status = Column(String(20), default="finished")  # finished/dnf/dns/dsq/over_time_limit
    # Remove: over_time_limit = Column(Boolean, ...)
```

Миграция: добавить колонку `status`, заполнить из `over_time_limit`, удалить старую колонку.

**A7.3 Обновить CLAX парсер** (`backend/app/features/races/clax_parser.py`):
- `np="1"` (non-partant / DNS) → сохранять с `status="dns"`, `time_seconds=0`
- `hd="1"` (hors-delai / over time limit) → `status="over_time_limit"`
- Нет времени финиша → `status="dnf"`, `time_seconds=0`
- Нормальный финиш → `status="finished"`

Ключевое изменение: **убрать `continue` на строке 157** (фильтрация DNS) и **убрать `continue` на строке 178** (фильтрация без времени). Вместо этого — сохранять с правильным status.

**A7.4 Обновить AM парсер** (`backend/app/features/races/am_parser.py`):
- Проверить наличие признаков DNF/DNS в HTML (надо исследовать формат данных)
- Если нет данных о DNF — оставить `status="finished"` по умолчанию

**A7.5 Обновить stats** (`backend/app/features/races/stats.py`):
- `calculate_stats()` — считать только `status="finished"` (и `over_time_limit`)
- Добавить в RaceStats:
  ```python
  total_participants: int   # все (finished + dnf + dns + dsq + over_time_limit)
  dnf_count: int           # только dnf
  dns_count: int           # только dns
  ```
- DNF rate = `dnf_count / (total_participants - dns_count) * 100`

**A7.6 Обновить API schemas**:
- `RaceStatsSchema` — добавить `total_participants`, `dnf_count`, `dns_count`, `dnf_rate`
- `RaceResultSchema` — добавить `status: str`
- Фронтенд показывает DNF-участников отдельно (серым, внизу таблицы или в отдельной секции)

**A7.7 Перепарсить все гонки:**
- Запустить `parse_race.py` заново для всех гонок
- Проверить что DNF/DNS записи появились в БД

### A8. Добавить season stats endpoint

**Добавить** в runners router или отдельно:

```python
@router.get("/api/v1/stats/season/{year}")
async def get_season_stats(year: int, db: Session = Depends(get_db)):
    """Aggregate stats for a season: total runners, total clubs, top runners."""
```

Response:
```python
class SeasonStatsResponse(BaseModel):
    year: int
    total_races: int
    total_finishers: int        # unique runners across all races
    total_clubs: int            # unique clubs
    top_runners: list[dict]     # top-5 by number of races or avg percentile
```

Нужен SQL: `SELECT DISTINCT name_normalized FROM race_results JOIN ... WHERE year = :year`

---

## Проверка

Тестировать через Swagger UI (`/docs`) или curl:

1. `GET /api/v1/races/alpine_race_kz/2025/results`
   - ✅ `stats.gender_distribution` — массив с M/F и процентами
   - ✅ `stats.category_distribution` — массив категорий
   - ✅ `stats.club_stats` — массив клубов с avg_percentile
2. `GET /api/v1/races/alpine_race_kz/search?name=Baikashev`
   - ✅ `percentile`, `total_finishers` заполнены для каждого года
   - ✅ `gender_percentile` заполнен (если gender есть)
   - ✅ `category_rank`, `category_total` заполнены (если category есть)
3. `GET /api/v1/races` — каждая гонка содержит `total_finishers`
4. `GET /api/v1/runners/baikashev+shyngys`
   - ✅ Профиль: имя, клуб, категория
   - ✅ Результаты по всем гонкам с персентилями
   - ✅ total_races, years_active, median_percentile
5. `GET /api/v1/runners/nonexistent+name` → 404
6. `GET /api/v1/stats/season/2025` → season stats
7. `GET /api/v1/races/alpine_race_kz/2025/results`
   - ✅ `stats.total_participants` > `stats.finishers` (если есть DNF/DNS)
   - ✅ `stats.dnf_count`, `stats.dns_count` заполнены
   - ✅ DNF-участники в `results` с `status="dnf"`, `time_s=0`
8. После перепарсинга: проверить что DNF/DNS записи появились для гонок, где они были

---

## Порядок реализации внутри шага

1. **A7** (DNF) — начинаем с модели и парсеров, чтобы данные были корректны
2. **A1-A2** (stats extensions) — расширяем stats, учитывая новый status
3. **A3** (search percentiles)
4. **A4** (total_finishers в RaceSchema)
5. **A5-A6** (runner profile endpoint)
6. **A8** (season stats)

### A9. Глобальный поиск бегуна (для GlobalSearch в Navbar)

**Добавить** в runners router:

```python
@router.get("/api/v1/runners/search")
async def search_runners(name: str, db: Session = Depends(get_db)):
    """Global search: find runners by name across all races."""
```

Response:
```python
class RunnerSearchResult(BaseModel):
    name: str
    name_normalized: str
    club: Optional[str] = None
    races_count: int          # number of unique races
    last_race: Optional[str] = None   # name of last race
    last_year: Optional[int] = None   # year of last race
```

Логика:
1. Нормализовать запрос (lowercase + sort words) — использовать `normalize_name()`
2. `SELECT DISTINCT name_normalized, name, club FROM race_results WHERE name_normalized LIKE :pattern`
3. Группировка по `name_normalized` → count races, last race/year
4. Сортировка по races_count DESC (активные бегуны первые)
5. Лимит 10 результатов

**Фронтенд (Step 5):** GlobalSearch в Navbar вызывает этот endpoint. Пока endpoint не готов — фронтенд показывает "Поиск скоро заработает" заглушку.

---

## Заметки

- Персентиль: 0% = лучший, 100% = худший. Но показываем как "top-X%": если percentile=5 → "top-5%" (быстрее 95%).
- `name_normalized` в URL: пробелы заменяются на `+` или `%20`. Бэкенд должен обработать оба варианта.
- DNF/DNS участники НЕ участвуют в расчёте персентилей и медианы — только `status="finished"` и `status="over_time_limit"`.
- `total_finishers` = count(finished + over_time_limit). `total_participants` = count(all statuses except dns).
