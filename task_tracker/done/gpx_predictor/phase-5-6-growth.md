# Фазы 5-6: Growth, Monetization, Crowdsourced

---

## Фаза 5: Growth & Monetization

**Цель:** Виральность, интеграция с Ayda Run, монетизация

### Шаги

#### Шаг 1: Share Features
- Картинка для шеринга (Pillow/Cairo)
- Shareable comparison images
- Social-friendly format

#### Шаг 2: Ayda Run Integration
- CTA to main app
- UTM tracking
- Cross-promotion
- Deep links

#### Шаг 3: Freemium модель
- Бесплатно: базовый прогноз
- Premium: детальный анализ, история, сравнения
- Payment integration

#### Шаг 4: Analytics & Optimization
- Usage analytics
- Conversion tracking
- A/B tests setup
- Performance optimization

### Deliverables

- [ ] Картинки для шеринга в соцсетях
- [ ] Интеграция с Ayda Run (CTA, deep links)
- [ ] Freemium subscription
- [ ] Analytics dashboard

---

## Фаза 6: Crowdsourced покрытие (опционально)

**Цель:** Улучшение точности через данные пользователей

> Эта фаза опциональна. Приоритет на формулах Naismith/Minetti,
> crowdsourced данные добавляем когда будет достаточно пользователей.

### Шаги

#### Шаг 1: Geo-indexed сегменты
- Geohash система
- PostgreSQL + PostGIS схема trail_segments
- Базовые CRUD операции

#### Шаг 2: Сбор отзывов
- UI формы отзыва после похода
- Выбор покрытия (multi-select)
- Отметка сложных участков на карте

#### Шаг 3: Агрегация данных
- Голосование за тип покрытия
- Сезонность (лето/зима)
- Пересчёт статистики (cron job)

#### Шаг 4: Matching GPX файлов
- Route fingerprinting
- Поиск похожих маршрутов
- Автоматическое обогащение

#### Шаг 5: Surface-aware прогноз
- Коэффициенты по покрытию
- Особая логика для спусков
- Confidence scoring

#### Шаг 6: OSM интеграция
- Fallback на OpenStreetMap
- Маппинг OSM тегов
- Комбинирование источников

#### Шаг 7 (опционально): Gamification
- Бейджи за отзывы ("Trail Scout")
- Топ контрибьюторов
- Персональная статистика

### Deliverables

- [ ] Сбор отзывов о покрытии от пользователей
- [ ] Привязка данных к геолокации (не к файлу)
- [ ] Сезонные данные (лето/зима)
- [ ] Surface-aware корректировки прогноза
- [ ] Интеграция с OSM как fallback
- [ ] Matching новых GPX к известным маршрутам

---

## Share Image Generator

### Пример вывода

```
┌─────────────────────────────────────────────────────────┐
│  🏔️ AYDA RUN PREDICTOR                                  │
│                                                          │
│  Маршрут: Кок-Жайляу                                    │
│  12 км  •  +680м  •  Средняя сложность                  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ [Профиль высоты - визуализация]                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Мой прогноз: 5:30                                      │
│  Рекомендуемый старт: 07:00                             │
│                                                          │
│  predictor.ayda.run                                     │
└─────────────────────────────────────────────────────────┘
```

### Реализация

```python
from PIL import Image, ImageDraw, ImageFont
import io

def generate_share_image(prediction: HikePrediction) -> bytes:
    """Генерирует картинку для шеринга"""

    # Размер для Instagram/Telegram
    width, height = 1080, 1080

    img = Image.new('RGB', (width, height), color='#1a1a2e')
    draw = ImageDraw.Draw(img)

    # Шрифты
    title_font = ImageFont.truetype("fonts/Roboto-Bold.ttf", 48)
    text_font = ImageFont.truetype("fonts/Roboto-Regular.ttf", 32)

    # Заголовок
    draw.text((50, 50), "AYDA RUN PREDICTOR", font=title_font, fill='#ffffff')

    # Маршрут
    draw.text((50, 150), prediction.route_name, font=title_font, fill='#4ecca3')

    # Метрики
    metrics = f"{prediction.distance_km} км  •  +{prediction.elevation_gain}м"
    draw.text((50, 220), metrics, font=text_font, fill='#cccccc')

    # Прогноз
    time_str = format_time(prediction.estimated_time_hours)
    draw.text((50, 400), f"Прогноз: {time_str}", font=title_font, fill='#ffffff')

    # Сохраняем
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
```

---

## Freemium модель

### Тарифы

| Функция | Free | Premium |
|---------|------|---------|
| Базовый прогноз | ✅ | ✅ |
| Загрузка GPX | 3/месяц | ∞ |
| Посегментный анализ | ❌ | ✅ |
| История прогнозов | 5 | ∞ |
| Групповой прогноз | 2 чел | ∞ |
| Share images | Watermark | Без watermark |
| Strava интеграция | ❌ | ✅ |

### Ценообразование

| План | Цена (KZT) | Цена (USD) |
|------|------------|------------|
| Free | 0 | 0 |
| Monthly | 1990 | ~4 |
| Annual | 14990 | ~30 |

---

## Crowdsourced Trail Data

### Модель данных

```python
@dataclass
class TrailSegment:
    id: str
    geohash: str              # Geo-индекс
    center_lat: float
    center_lon: float
    surface_votes: dict       # {"gravel": 5, "rock": 2}
    difficulty_votes: dict    # {"easy": 3, "hard": 1}
    seasonal_data: dict       # {"summer": {...}, "winter": {...}}
    last_updated: datetime
    contributors_count: int

class SurfaceType(Enum):
    ASPHALT = "asphalt"       # 1.0x
    GRAVEL = "gravel"         # 1.05x
    DIRT = "dirt"             # 1.1x
    GRASS = "grass"           # 1.15x
    ROCK = "rock"             # 1.2x
    SNOW = "snow"             # 1.4x
    MUD = "mud"               # 1.5x
```

### Сбор отзывов

```python
class TrailFeedback(BaseModel):
    gpx_file_id: str
    segments: List[SegmentFeedback]
    overall_difficulty: str
    conditions: str           # "dry", "wet", "snowy"
    date: date

class SegmentFeedback(BaseModel):
    start_km: float
    end_km: float
    surface: SurfaceType
    difficulty: str           # "easy", "moderate", "hard"
    notes: Optional[str]

@router.post("/feedback/trail")
async def submit_trail_feedback(feedback: TrailFeedback):
    """Сохраняет отзыв о покрытии маршрута"""

    for segment in feedback.segments:
        geohash = calculate_geohash(segment.start_km, gpx_file_id)

        await upsert_trail_segment(
            geohash=geohash,
            surface=segment.surface,
            difficulty=segment.difficulty,
            date=feedback.date
        )
```

### Geohash система

```python
import geohash

def calculate_geohash(lat: float, lon: float, precision: int = 7) -> str:
    """
    Precision 7 = ~150m x 150m квадрат
    Достаточно для trail segments
    """
    return geohash.encode(lat, lon, precision)

def get_nearby_segments(lat: float, lon: float) -> List[TrailSegment]:
    """Находит сегменты в радиусе"""

    center_hash = calculate_geohash(lat, lon)
    neighbors = geohash.neighbors(center_hash)

    return await db.trail_segments.find({
        "geohash": {"$in": [center_hash] + neighbors}
    }).to_list()
```

---

## Чеклист перед запуском

### Технический

```
□ HTTPS везде
□ Токены Strava зашифрованы (при интеграции)
□ Rate limiting на API (in-memory для MVP)
□ Error handling и logging
□ Backup базы данных (PostgreSQL)
□ Мониторинг (Sentry, uptime)
□ Open-Elevation API fallback при ошибках
```

### Юридический (для Strava)

```
□ Privacy Policy опубликована
□ Consent screen для Strava OAuth
□ Кнопка "Удалить мои данные"
□ Кнопка "Отключить Strava"
□ 7-day TTL для Strava кэша
□ Соответствие API Agreement проверено
□ Анонимность crowdsourced данных
```

### Продуктовый

```
□ Работает без Strava (fallback)
□ Режим для туристов работает
□ Режим для бегунов работает
□ Групповой прогноз работает
□ Share images генерируются
□ Telegram Mini App работает
```
