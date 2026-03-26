# Шаг 5.5a: Бэкенд — API для Race Insights ✅ DONE

## Цель

Подготовить все API endpoints для фронтенд-шагов 5.5b-5.5e.
Один шаг бэкенда — все фронтенд-шаги зависят от него.

**Ветка:** `web-portal-step-5.5a`
**Зависит от:** Шаги 3, 5 (results API, search API).

---

## Порядок реализации

1. ✅ **A1** — Таблица `runners` + миграция + заполнение из race_results
2. ✅ **A2** — DNF: обновить модель, парсеры (только CLAX), миграция, перепарсинг
3. ✅ **A3** — Расширить stats (gender/category/club), учитывая status
4. ✅ **A4** — Обновить RaceStatsSchema + `name_normalized` в RaceResultSchema
5. ✅ **A5** — Search с персентилями
6. ✅ **A6** — total_finishers в RaceSchema
7. ✅ **A7** — Runner Profile endpoint (по runner_id) + register router
8. ✅ **A8** — Season stats endpoint
9. ✅ **A9** — Global search runners endpoint

---

## Что делать

### A1. Таблица `runners` — уникальная идентификация бегунов

Сейчас бегун идентифицируется только через `name_normalized` в `race_results`.
Это может давать коллизии (два разных "Иванов Иван").
Нужна отдельная таблица с уникальным ID.

**A1.1 Создать DB модель** (`backend/app/features/races/db_models.py`):
```python
class Runner(Base):
    """Unique runner across all races."""

    __tablename__ = "runners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)            # display name (из последнего результата)
    name_normalized = Column(String(255), nullable=False, unique=True, index=True)
    club = Column(String(255), nullable=True)             # последний известный клуб
    gender = Column(String(4), nullable=True)             # M / F
    category = Column(String(32), nullable=True)          # последняя категория
    birth_year = Column(Integer, nullable=True)
    races_count = Column(Integer, default=0)              # кэш: количество гонок
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    results = relationship("RaceResultDB", back_populates="runner")
```

**A1.2 Добавить FK в RaceResultDB:**
```python
class RaceResultDB(Base):
    # ... existing ...
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=True)  # nullable на время миграции
    runner = relationship("Runner", back_populates="results")
```

**A1.3 Alembic миграция** (`014_add_runners_table.py`):
1. Создать таблицу `runners`
2. Добавить колонку `runner_id` в `race_results` (nullable)
3. Заполнить `runners` из существующих данных:
   ```sql
   INSERT INTO runners (name, name_normalized, club, gender, category, birth_year, races_count)
   SELECT DISTINCT ON (name_normalized)
     name, name_normalized, club, gender, category, birth_year,
     (SELECT COUNT(DISTINCT d.edition_id)
      FROM race_results r2
      JOIN race_distances d ON r2.distance_id = d.id
      WHERE r2.name_normalized = race_results.name_normalized)
   FROM race_results
   WHERE name_normalized IS NOT NULL
   ORDER BY name_normalized, id DESC;  -- последний результат для name/club/etc
   ```
4. Обновить `race_results.runner_id` по `name_normalized`
5. Создать индекс на `race_results.runner_id`

**A1.4 Обновить парсеры** — при сохранении результата:
1. Найти runner по `name_normalized` → если есть, обновить club/category/gender
2. Если нет → создать нового runner
3. Записать `runner_id` в `race_result`

**A1.5 Обновить RaceRepository:**
```python
def get_or_create_runner(self, name_normalized: str, name: str, **kwargs) -> Runner:
    """Find or create a runner by normalized name."""
```

**Заметка:** В будущем disambiguation (два "Иванов Иван") можно решить через merge/split runners. Пока 1 name_normalized = 1 runner.

### A2. DNF: обновить модель и парсеры

Сейчас DNF/DNS участники отфильтровываются при парсинге. Нужно сохранять их в БД.

**A2.1 Обновить RaceResult dataclass** (`backend/app/features/races/models.py`):
```python
@dataclass
class RaceResult:
    # ... existing fields ...
    status: str = "finished"  # "finished" | "dnf" | "dns" | "dsq" | "over_time_limit"
```

Поле `over_time_limit: bool` — оставить как есть в dataclass для обратной совместимости, добавить `status` рядом.

**A2.2 Обновить DB модель** (`backend/app/features/races/db_models.py`):
```python
class RaceResultDB(Base):
    # ... existing ...
    status = Column(String(20), default="finished")  # finished/dnf/dns/dsq/over_time_limit
    # over_time_limit — НЕ УДАЛЯТЬ пока, оставить для backward compat
```

**A2.3 Alembic миграция** (`015_add_result_status.py`):
1. Добавить колонку `status` (default="finished")
2. `UPDATE race_results SET status = 'over_time_limit' WHERE over_time_limit = true`
3. НЕ удалять `over_time_limit` — удалим позже отдельной миграцией

**A2.4 Обновить CLAX парсер** (`backend/app/features/races/clax_parser.py`):
- `np="1"` (non-partant / DNS) → сохранять с `status="dns"`, `time_seconds=0`
- `hd="1"` (hors-delai / over time limit) → `status="over_time_limit"`
- Нет времени финиша → `status="dnf"`, `time_seconds=0`
- Нормальный финиш → `status="finished"`

Ключевое изменение: **убрать `continue`** на фильтрации DNS и отсутствия времени. Вместо этого — сохранять с правильным status.

**A2.5 AM парсер** (`backend/app/features/races/am_parser.py`):
- Оставить `status="finished"` по умолчанию
- DNF/DNS данные в AM формате нужно исследовать отдельно (не в этом шаге)

**A2.6 Обновить stats** (`backend/app/features/races/stats.py`):
- `calculate_stats()` — считать только `status in ("finished", "over_time_limit")`
- Добавить в RaceStats:
  ```python
  total_participants: int   # все (finished + dnf + dns + dsq + over_time_limit)
  dnf_count: int           # только dnf
  dns_count: int           # только dns
  ```
- DNF rate = `dnf_count / (total_participants - dns_count) * 100`

**A2.7 Перепарсить все гонки:**
- Запустить `parse_race.py` заново для всех гонок (CLAX-парсер)
- Проверить что DNF/DNS записи появились в БД
- Обновить `runner_id` для новых записей

### A3. Расширить stats — gender/category distribution + club_stats

**Изменить** `backend/app/features/races/stats.py`:

Добавить вычисление в `calculate_stats()` (или отдельные функции):

**gender_distribution:**
```python
[{"gender": "M", "count": 180, "percent": 73.5},
 {"gender": "F", "count": 65, "percent": 26.5}]
```
- Считаем только непустые `gender` значения
- Только `status in ("finished", "over_time_limit")`
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
- avg_percentile = среднее от персентилей всех финишировавших участников клуба
- Если все `club=None` → пустой список
- **Важно:** `best_time` — форматировать через `format_time()`, возвращать и `best_time_s` (int) и `best_time` (str)

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
    best_time: str        # format_time(best_time_s)
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
    total_participants: int = 0
    dnf_count: int = 0
    dns_count: int = 0
```

### A4. Обновить API schemas

**Изменить** `backend/app/api/v1/routes/races.py`:

**RaceStatsSchema** — добавить новые поля:
```python
class RaceStatsSchema(BaseModel):
    # ... existing fields ...
    gender_distribution: list[dict] = []
    category_distribution: list[dict] = []
    club_stats: list[dict] = []
    total_participants: int = 0
    dnf_count: int = 0
    dns_count: int = 0
    dnf_rate: Optional[float] = None
```

**RaceResultSchema** — добавить:
```python
class RaceResultSchema(BaseModel):
    # ... existing ...
    name_normalized: Optional[str] = None    # для ссылок на профиль бегуна
    runner_id: Optional[int] = None          # уникальный ID бегуна
    status: str = "finished"                 # finished/dnf/dns/dsq/over_time_limit
```

Обновить сериализацию в endpoint `get_results()` — передавать новые поля.

### A5. Расширить search endpoint — персентили

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

### A6. Добавить total_finishers в RaceSchema

**Изменить** `backend/app/api/v1/routes/races.py`:

Добавить поле:
```python
class RaceSchema(BaseModel):
    # ... existing fields ...
    total_finishers: Optional[int] = None  # sum across all distances, latest year
```

**Изменить** `list_races()` и `get_race()`:
- Для последнего edition: посчитать сумму финишёров по всем дистанциям
- Считать только `status in ("finished", "over_time_limit")`

**Добавить в RaceRepository:**
```python
def count_finishers(self, race_id: str, year: int) -> int:
    """Count total finishers (status=finished/over_time_limit) across all distances."""
```

### A7. Runner Profile endpoint (по runner_id)

**Добавить** новый router `backend/app/api/v1/routes/runners.py`:

```python
@router.get("/{runner_id}", response_model=RunnerProfileResponse)
async def get_runner_profile(runner_id: int, db: Session = Depends(get_db)):
    """Get runner profile with all race results across all races."""
```

**Schemas:**
```python
class RunnerProfileSchema(BaseModel):
    id: int
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
    status: str = "finished"

class RunnerProfileResponse(BaseModel):
    profile: RunnerProfileSchema
    results: list[RunnerRaceResultSchema]
    total_races: int
    years_active: int
    median_percentile: Optional[float] = None
```

**Логика:**
1. Найти runner по `id` в таблице `runners`
2. Запросить все `race_results` WHERE `runner_id = :id` (JOIN distances, editions, races)
3. Для каждого результата: посчитать total_finishers и percentile в рамках той же дистанции/года
4. Вычислить years_active, total_races, median_percentile
5. Отсортировать results: year DESC, race_name ASC
6. DNF/DNS результаты включать, но они НЕ участвуют в median_percentile

**Добавить в RaceRepository (или создать RunnerRepository):**
```python
def get_runner_by_id(self, runner_id: int) -> Runner | None:
    """Get runner by ID."""

def get_runner_results(self, runner_id: int) -> list[tuple]:
    """Get all results for a runner across all races."""
```

### A8. Зарегистрировать runners router

**Изменить** `backend/app/main.py` (или `api/v1/__init__.py`):

```python
from app.api.v1.routes.runners import router as runners_router
app.include_router(runners_router, prefix="/api/v1/runners", tags=["runners"])
```

### A9. Season stats endpoint

**Добавить** в отдельный router или в runners:

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
    total_finishers: int        # unique runners (by runner_id) across all races
    total_clubs: int            # unique clubs
    top_runners: list[dict]     # top-5 by number of races or avg percentile
    top_clubs: list[dict]       # top-5 clubs by runner_count + avg_percentile
```

Логика:
- Использовать `runner_id` для подсчёта уникальных бегунов (вместо `DISTINCT name_normalized`)
- Кэшировать результат (тяжёлый запрос с агрегацией)
- Только `status in ("finished", "over_time_limit")`

### A10. Глобальный поиск бегуна (для GlobalSearch в Navbar)

**Добавить** в runners router:

```python
@router.get("/search")
async def search_runners(name: str, db: Session = Depends(get_db)):
    """Global search: find runners by name across all races."""
```

Response:
```python
class RunnerSearchResult(BaseModel):
    id: int                           # runner_id
    name: str
    name_normalized: str
    club: Optional[str] = None
    races_count: int
    last_race: Optional[str] = None
    last_year: Optional[int] = None
```

Логика:
1. Нормализовать запрос (lowercase + sort words) — использовать `normalize_name()`
2. `SELECT * FROM runners WHERE name_normalized LIKE :pattern`
3. Сортировка по races_count DESC (активные бегуны первые)
4. Лимит 10 результатов
5. Для last_race/last_year — JOIN с race_results + editions (или кэшировать в runners)

**Фронтенд:** GlobalSearch в Navbar вызывает этот endpoint вместо заглушки.

---

## Проверка

Тестировать через Swagger UI (`/docs`) или curl:

1. `GET /api/v1/races/alpine_race_kz/2025/results`
   - ✅ `stats.gender_distribution` — массив с M/F и процентами
   - ✅ `stats.category_distribution` — массив категорий
   - ✅ `stats.club_stats` — массив клубов с avg_percentile, best_time и best_time_s
   - ✅ `stats.total_participants` > `stats.finishers` (если есть DNF/DNS)
   - ✅ `stats.dnf_count`, `stats.dns_count` заполнены
   - ✅ Каждый result содержит `name_normalized`, `runner_id`, `status`
   - ✅ DNF-участники в `results` с `status="dnf"`, `time_s=0`
2. `GET /api/v1/races/alpine_race_kz/search?name=Baikashev`
   - ✅ `percentile`, `total_finishers` заполнены для каждого года
   - ✅ `gender_percentile` заполнен (если gender есть)
   - ✅ `category_rank`, `category_total` заполнены (если category есть)
3. `GET /api/v1/races` — каждая гонка содержит `total_finishers`
4. `GET /api/v1/runners/42` (по ID)
   - ✅ Профиль: id, имя, клуб, категория
   - ✅ Результаты по всем гонкам с персентилями
   - ✅ total_races, years_active, median_percentile
5. `GET /api/v1/runners/999999` → 404
6. `GET /api/v1/stats/season/2025` → season stats (total_finishers = unique runners by runner_id)
7. `GET /api/v1/runners/search?name=baik`
   - ✅ Найден бегун с races_count и last_race
8. После перепарсинга: проверить что DNF/DNS записи появились для CLAX-гонок

---

## Заметки

- Персентиль: 0% = лучший, 100% = худший. Показываем как "top-X%": если percentile=5 → "top-5%" (быстрее 95%).
- `runner_id` — основной идентификатор бегуна. URL: `/runners/{runner_id}` (int).
- `name_normalized` остаётся для поиска и matching, но не используется как URL-идентификатор.
- DNF/DNS участники НЕ участвуют в расчёте персентилей и медианы — только `status in ("finished", "over_time_limit")`.
- `total_finishers` = count(finished + over_time_limit). `total_participants` = count(all statuses except dns).
- AM парсер: DNF/DNS — отдельная задача, сейчас оставляем `status="finished"`.
- `over_time_limit` колонка в БД: не удалять сейчас, удалим отдельной миграцией после полного перехода на `status`.
