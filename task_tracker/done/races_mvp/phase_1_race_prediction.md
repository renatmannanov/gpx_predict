# Фаза 1: Прогноз на гонку + сравнение с результатами

## Цель

Для пользователя с Strava-профилем — дать прогноз времени на дистанцию гонки и показать, в каком перцентиле он окажется относительно прошлых результатов. Проверить на Ренате: прогноз vs реальный результат.

## Зависимости

- **Фаза 0 завершена** — CLAX парсер работает, результаты Alpine Race в JSON
- **GPX файл дистанции** — Alpine Race Skyrunning (Ренат должен предоставить)
- **Strava профиль Рената** — уже есть в gpx_predictor

## Архитектура

```
content/
└── races/
    ├── races.yaml                    # Каталог гонок
    ├── gpx/
    │   └── alpine_race_skyrunning.gpx
    └── results/
        └── alpine_race_2025.json     # Из Фазы 0

backend/
├── app/features/races/
│   ├── ... (из Фазы 0)
│   ├── catalog.py                    # Загрузчик races.yaml
│   ├── matching.py                   # Поиск по имени
│   └── service.py                    # RaceService: прогноз + перцентиль
│
└── scripts/
    └── predict_race.py               # CLI: прогноз на гонку
```

## Задачи

### Задача 1: Каталог гонок (YAML)

**Файл:** `content/races/races.yaml`

```yaml
races:
  - id: alpine_race
    name: Alpine Race
    type: trail_sky
    location: Шымбулак
    distances:
      - id: skyrunning
        name: Skyrunning
        distance_km: 4.0
        elevation_gain_m: 900
        start_altitude_m: 2200
        finish_altitude_m: 3200
        gpx_file: alpine_race_skyrunning.gpx
        grade: orange
    editions:
      - year: 2026
        date: "2026-03-01"
        registration_url: https://athletex.kz/competitions/AlpineRace2026
      - year: 2025
        date: "2025-03-01"
        results_file: alpine_race_2025.json
```

**Файл:** `backend/app/features/races/catalog.py`

```python
class RaceCatalog:
    def __init__(self, content_dir: Path):
        self.content_dir = content_dir

    def load(self) -> list[Race]:
        """Загрузить каталог из YAML."""

    def get_race(self, race_id: str) -> Race | None:

    def get_distance(self, race_id: str, distance_id: str) -> RaceDistance | None:

    def get_gpx_path(self, race_id: str, distance_id: str) -> Path | None:
        """Полный путь к GPX файлу дистанции."""

    def get_results_path(self, race_id: str, year: int) -> Path | None:
        """Полный путь к JSON результатов."""
```

Путь к content/ через конфиг:
```python
# app/config.py — добавить
CONTENT_DIR = Path(__file__).parent.parent.parent.parent / "content"
```

**Критерий готовности:** `RaceCatalog(CONTENT_DIR).get_race("alpine_race")` возвращает данные.

### Задача 2: RaceService — прогноз

**Файл:** `backend/app/features/races/service.py`

```python
class RaceService:
    def predict_for_user(
        self,
        race_id: str,
        distance_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> RacePrediction:
        """
        Персональный прогноз на дистанцию гонки.

        1. Загрузить GPX дистанции из каталога (content/races/gpx/)
        2. Загрузить профиль пользователя из БД
        3. Вызвать существующий PredictionService / TrailRunService
        4. Загрузить результаты прошлых лет (content/races/results/)
        5. Рассчитать перцентиль прогноза
        6. Вернуть RacePrediction
        """

    def predict_by_pace(
        self,
        race_id: str,
        distance_id: str,
        flat_pace_min_km: float,
    ) -> RacePrediction:
        """Базовый прогноз по темпу на плоскости (без Strava)."""
```

```python
@dataclass
class RacePrediction:
    race_name: str
    distance_name: str
    predicted_time_s: int
    method: str                     # "tobler_personalized" / "tobler_base"
    percentile: float | None        # 28.5 = топ-28% (если есть результаты)
    bucket_label: str | None        # "Быстрый (топ-25%)"
    past_result: RaceResult | None  # результат этого юзера (если нашли)
    stats: RaceStats | None         # статистика дистанции
```

**Важно:** `predict_for_user` внутри вызывает **существующий** `PredictionService.predict_hike()` или `TrailRunService`. Не дублируем логику расчёта.

**Критерий готовности:** `RaceService().predict_for_user("alpine_race", "skyrunning", renat_user_id)` возвращает прогноз.

### Задача 3: Матчинг пользователя с результатами

**Файл:** `backend/app/features/races/matching.py`

```python
def find_user_in_results(
    results: list[RaceResult],
    name: str,
) -> list[RaceResult]:
    """
    Поиск по имени (fuzzy):
    - Регистронезависимый
    - Частичное совпадение ("Ренат" → "Кайратов Ренат")
    - Обе раскладки не обрабатываем (пока ручной ввод)
    """

def find_across_years(
    catalog: RaceCatalog,
    race_id: str,
    distance_id: str,
    name: str,
) -> dict[int, RaceResult | None]:
    """
    Поиск по всем годам:
    {2023: RaceResult(...), 2024: None, 2025: RaceResult(...)}
    """
```

**Критерий готовности:** `find_user_in_results(results, "Ренат")` находит результат.

### Задача 4: CLI скрипт прогноза

**Файл:** `backend/scripts/predict_race.py`

```bash
# Персональный прогноз (Strava профиль)
python backend/scripts/predict_race.py \
    --race alpine_race \
    --distance skyrunning \
    --user-id <renat_user_id>

# Базовый прогноз (по темпу)
python backend/scripts/predict_race.py \
    --race alpine_race \
    --distance skyrunning \
    --flat-pace 5:30

# С поиском в результатах
python backend/scripts/predict_race.py \
    --race alpine_race \
    --distance skyrunning \
    --user-id <renat_user_id> \
    --search-name "Ренат"
```

Вывод:

```
=== Alpine Race 2026 — Skyrunning ===
4 км, +900м, Шымбулак (2200м → 3200м)
Грейд: 🟠 Сложный

--- Твой прогноз ---
Метод: Tobler (персонализированный)
Профиль: 47 горных тренировок
Прогноз: 47:20

--- Сравнение с Alpine Race 2025 ---
43 финишёра | Лучший: 34:12 | Медиана: 1:02:40

Твой прогноз 47:20 → топ-19% (8 место из 43)
  < 40 мин   ████░░░░░░  5   Элита
  40-55 мин  ██████░░░░  9   Быстрый      ← ТЫ ТУТ
  55-75 мин  ████████░░ 14   Средний
  75-100 мин ██████░░░░ 10   Медленный
  > 100 мин  ████░░░░░░  5   Финишёр

--- Твой результат 2025 ---
Кайратов Ренат: 58:12, 12 место (топ-28%)

--- Прогресс ---
2025 результат: 58:12
2026 прогноз:   47:20
Разница:        -10:52 🔥
```

**Критерий готовности:** Полный вывод работает для Рената.

## Порядок реализации

1. Задача 1 — каталог YAML + загрузчик + конфиг CONTENT_DIR
2. Задача 2 — RaceService (прогноз)
3. Задача 3 — матчинг по имени
4. Задача 4 — CLI скрипт

## Что НЕ делаем в этой фазе

- API endpoints (это Фаза 2)
- Бот-интеграция (это Фаза 2)
- Race cards / картинки
- Автоматическое определение race_name из Strava
- Хранение матчей в БД (пока поиск каждый раз)
- Множественные гонки (только Alpine Race для проверки)
