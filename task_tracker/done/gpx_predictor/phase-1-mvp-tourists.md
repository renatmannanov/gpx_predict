# Фаза 1: MVP для туристов

**Цель:** Работающий калькулятор времени похода для туристов

---

## Шаги реализации

### Шаг 1: Настройка проекта
- FastAPI scaffold
- PostgreSQL + Alembic setup
- Базовые модели данных

### Шаг 2: GPX Parser
- gpxpy интеграция
- Сегментация трассы
- Базовый elevation calculation

### Шаг 3: DEM Integration
- Open-Elevation API интеграция (MVP)
- Elevation correction
- Threshold filtering

> **Масштабирование:** При росте до 1000+ запросов/день перейти на srtm.py (self-hosted)

### Шаг 4: Алгоритм Нейсмита
- Базовая формула
- Корректировки Tranter
- Модификация для спусков

### Шаг 5: Профилирование туриста
- UI для сбора данных (опыт, рюкзак, группа)
- Коэффициенты по профилю
- Высотная корректировка

### Шаг 6: Safety Features
- Предупреждения о рисках
- Рекомендуемое время старта
- Время разворота
- Checklist перед походом

### Шаг 7: API Endpoints
- POST /predict/hike
- POST /gpx (upload)
- Validation & error handling

### Шаг 8: Basic Frontend
- Upload GPX form
- Профиль туриста (опыт, снаряжение)
- Results display с timeline

### Шаг 9: Testing & Deployment
- Unit tests for formulas
- Integration tests
- Railway setup
- Domain & SSL
- Monitoring (Sentry)

---

## Deliverables

- [ ] Калькулятор времени похода на базе Naismith
- [ ] Профилирование туриста (опыт/рюкзак/группа)
- [ ] Коррекция высоты через Open-Elevation API
- [ ] Предупреждения о безопасности
- [ ] Веб-страница с формой загрузки GPX

---

## Алгоритм Нейсмита

### Базовая формула (1892)

```python
def naismith_time(distance_km: float, elevation_gain_m: float) -> float:
    """
    Классическое правило Нейсмита:
    - 5 км/час по горизонтали
    - +1 час на каждые 600м набора высоты

    Returns: время в часах
    """
    horizontal_time = distance_km / 5.0
    vertical_time = elevation_gain_m / 600.0
    return horizontal_time + vertical_time
```

### С учётом спусков (Tranter, 1970)

```python
def naismith_with_descent(distance_km: float,
                          elevation_gain_m: float,
                          elevation_loss_m: float) -> float:
    """
    Крутой спуск замедляет примерно на 10 мин / 300м сброса
    """
    base_time = naismith_time(distance_km, elevation_gain_m)

    if elevation_loss_m > 0:
        descent_factor = elevation_loss_m / 300
        descent_time = descent_factor * (10/60)
        base_time += descent_time

    return base_time
```

---

## Профилирование туриста

### Модели данных

```python
class ExperienceLevel(Enum):
    BEGINNER = "beginner"      # Новичок → 1.5x
    CASUAL = "casual"          # Любитель → 1.2x
    REGULAR = "regular"        # Регулярно → 1.0x
    EXPERIENCED = "experienced" # Опытный → 0.85x

class BackpackWeight(Enum):
    LIGHT = "light"    # <5 кг → 1.0x
    MEDIUM = "medium"  # 5-10 кг → 1.1x
    HEAVY = "heavy"    # >10 кг → 1.25x

@dataclass
class HikerProfile:
    experience: ExperienceLevel
    backpack: BackpackWeight
    group_size: int
    max_altitude_m: float
    has_children: bool = False
    has_elderly: bool = False
    first_time_altitude: bool = False
```

### Коэффициенты

| Фактор | Значение | Множитель |
|--------|----------|-----------|
| **Опыт** | | |
| Новичок | Редко ходит | 1.5x |
| Любитель | Несколько раз в год | 1.2x |
| Регулярно | Каждые выходные | 1.0x |
| Опытный | Многодневки | 0.85x |
| **Рюкзак** | | |
| Лёгкий | <5 кг | 1.0x |
| Средний | 5-10 кг | 1.1x |
| Тяжёлый | >10 кг | 1.25x |
| **Группа** | | |
| 1-2 чел | | 1.0x |
| 3-5 чел | | 1.1x |
| >5 чел | | 1.3x |
| **Высота** | | |
| <2500м | | 1.0x |
| 2500-3000м | | 1.1x |
| 3000-3500м | | 1.2x |
| >3500м | | 1.35x |
| **Дополнительно** | | |
| С детьми | | 1.4x |
| С пожилыми | | 1.3x |
| Первый раз на высоте | >3000м | 1.15x |

---

## API Endpoints

### POST /predict/hike

```python
@router.post("/predict/hike")
async def predict_hike(request: HikePredictRequest) -> HikePrediction:
    """
    Прогноз времени похода для туриста.
    """
    pass

class HikePredictRequest(BaseModel):
    gpx_file_id: str  # или gpx_content: str
    experience: ExperienceLevel
    backpack: BackpackWeight
    group_size: int = 1
    has_children: bool = False
    has_elderly: bool = False
    is_round_trip: bool = True

class HikePrediction(BaseModel):
    estimated_time_hours: float
    safe_time_hours: float          # +20% запас
    recommended_start: str
    recommended_turnaround: str
    warnings: List[Warning]
    segments: List[SegmentPrediction]
```

### POST /gpx

```python
@router.post("/gpx")
async def upload_gpx(file: UploadFile) -> GPXInfo:
    """
    Загрузка и парсинг GPX файла.
    """
    pass

class GPXInfo(BaseModel):
    id: str
    name: str
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_altitude_m: float
    min_altitude_m: float
```

---

## Safety Features

### Предупреждения

```python
class WarningLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"

WARNINGS = {
    "late_return": {
        "level": WarningLevel.DANGER,
        "message": "Возвращение после заката. Возьмите фонарик!"
    },
    "high_altitude": {
        "level": WarningLevel.WARNING,
        "message": "Маршрут выше 3000м. Возможна горная болезнь."
    },
    "long_hike": {
        "level": WarningLevel.INFO,
        "message": "Поход более 8 часов. Возьмите достаточно воды и еды."
    },
    "steep_descent": {
        "level": WarningLevel.WARNING,
        "message": "Крутой спуск. Используйте треккинговые палки."
    }
}
```

### Рекомендуемое время старта

```python
def calculate_start_time(
    estimated_hours: float,
    sunset: str = "20:00",
    safety_buffer_hours: float = 1.0
) -> str:
    """
    Рассчитывает рекомендуемое время старта.
    Цель: вернуться за час до заката.
    """
    sunset_hour = int(sunset.split(":")[0])
    target_return = sunset_hour - safety_buffer_hours

    # Добавляем 20% запас к прогнозу
    safe_duration = estimated_hours * 1.2

    start_hour = target_return - safe_duration

    if start_hour < 5:
        start_hour = 5  # Не раньше 5 утра

    return f"{int(start_hour):02d}:00"
```

---

## Структура проекта

```
services/
└── gpx-predictor/
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   │   ├── routes/
    │   │   │   ├── gpx.py
    │   │   │   └── predict.py
    │   │   └── deps.py
    │   ├── core/
    │   │   ├── config.py
    │   │   └── security.py
    │   ├── models/
    │   │   ├── gpx.py
    │   │   └── hiker.py
    │   ├── services/
    │   │   ├── gpx_parser.py
    │   │   ├── elevation.py
    │   │   └── prediction.py
    │   └── db/
    │       ├── base.py
    │       └── models.py
    ├── tests/
    ├── alembic/
    ├── requirements.txt
    └── Dockerfile
```

---

## Зависимости

```txt
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0
alembic>=1.12.0
asyncpg>=0.29.0
gpxpy>=1.6.0
httpx>=0.25.0
pydantic>=2.5.0
python-multipart>=0.0.6
```
