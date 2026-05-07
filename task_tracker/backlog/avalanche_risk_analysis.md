# Анализ лавинной опасности маршрута по GPX

> Приоритет: низкий (на будущее, ~зима 2026-2027)
> Актуальность: 90% зимних маршрутов в Алматы лавиноопасны

---

## Приложения с лавинными данными

### Топ (полный анализ маршрута)

| Приложение | Что умеет | Покрытие |
|-----------|-----------|----------|
| **Skitourenguru** | Лучшая система — расчёт риска для каждой точки маршрута по методу SLABS, загрузка GPX, светофор риска | Альпы (CH, AT, FR, IT, DE) |
| **onX Backcountry** | ATES-классификация (5 уровней), зоны схода, углы склонов, прогнозы | США (23M акров) |
| **White Risk** (SLF) | Официальное швейцарское приложение, автоматически отмечает опасные участки на маршруте | Швейцария, Франция, Австрия |

### Средний уровень (визуализация склонов)

| Приложение | Что умеет |
|-----------|-----------|
| **Outmap** | 3D-карта + слои: углы склонов, экспозиция, лавинный риск |
| **Strava** (ex-FATMAP) | 3D-карта, слой Avalanche Gradient (25-45+°) |
| **Gaia GPS** | Глобальные углы склонов (SRTM 30м), без прогнозов |
| **CalTopo** | Углы склонов + наблюдения лавинных центров (США) |
| **Trailforks** | Глобальная лавинная карта углов склонов |

### Нишевые

| Приложение | Что умеет |
|-----------|-----------|
| **Avanet** (Avatech) | Краудсорсинг наблюдений + terrain analysis, Park City UT |
| **ATESmaps** | ATES-классификация Пиренеев, open source на GitHub |
| **Backtrack** | LiDAR 1м slope angle, США |

---

## Открытые API и данные

### Прогнозы лавин

| Источник | API | Формат | Покрытие |
|----------|-----|--------|----------|
| **EAWS / ALBINA** | `https://api.avalanche.report/albina/api/bulletins` | JSON, CAAML (XML) | Европа (20+ стран) |
| **Avalanche Canada** | `docs.avalanche.ca` | JSON, GeoJSON | Канада |
| **avalanche.org** | JSON API по центрам | JSON | США |
| **pyAvaCore** | Python-библиотека | Парсит бюллетени EAWS | Европа |

- GeoJSON регионов прогнозов: `https://regions.avalanches.org/`
- CAAML стандарт обмена: `caaml.org`
- GitHub ALBINA server: `github.com/albina-euregio/albina-server`

### DEM (цифровые модели рельефа)

| Источник | Разрешение | Доступ |
|----------|-----------|--------|
| **Copernicus DEM GLO-30** | 30м, глобально | S3: `s3://copernicus-dem-30m/`, Sentinel Hub API |
| **NASA SRTM** | 30м, глобально | OpenTopography, Google Earth Engine |
| **Open Topo Data API** | Разные | `GET https://api.opentopodata.org/v1/{dataset}?locations={lat},{lon}` |
| **USGS 3DEP** | 1-3м (LiDAR) | США |

### ATES (классификация лавинного рельефа)

- **AutoATES v2.0** — open source: `github.com/AutoATES/AutoATES-v2.0`
  - Генерирует ATES-карту из DEM + данных о лесном покрове
  - Python, 5-30м DEM, output: растр с классами 0-4
  - Validated F1 scores 71-77%
- **AutoATES v1.0** (Норвегия) — зависит от ArcGIS (проприетарный)

### Расчёт slope/aspect из DEM (Python)

```python
# richdem
import richdem as rd
dem = rd.LoadGDAL("dem.tif")
slope = rd.TerrainAttribute(dem, attrib='slope_degrees')
aspect = rd.TerrainAttribute(dem, attrib='aspect')

# numpy
slope = np.pi/2. - np.arctan(np.sqrt(x*x + y*y))
aspect = np.arctan2(-x, y)
```

Другие инструменты: GRASS GIS (`r.slope.aspect`), QGIS, Google Earth Engine, pyDEM.

---

## Как мэтчить GPX с лавинными зонами

### Подход Skitourenguru (SLABS) — state of the art

1. Для каждой точки маршрута — запросить DEM в буфере (рельеф **выше/вокруг**, не только в точке)
2. Рассчитать slope angle, aspect, elevation band
3. Сопоставить с бюллетенем: уровень опасности для данной высоты + экспозиции
4. SLABS: нелинейная зависимость от угла склона + линейная от уровня опасности, высоты, экспозиции
5. Агрегировать по маршруту → Risk-Indicator (светофор)

Калиброван на 57,800 км GPS-треков и 1,250 аварий за 20 швейцарских зимних сезонов.

### Практичный подход для реализации

```
GPX маршрут
    │
    ▼
Для каждой точки: запросить DEM в буфере ~100-500м (особенно выше по склону)
    │
    ▼
Рассчитать: угол склона, экспозицию, высоту
    │
    ▼
Найти стартовые зоны лавин (склоны 30-45°)
    │
    ▼
Моделирование зоны схода (Flow-Py или alpha-angle метод)
    │
    ▼
Классификация каждого сегмента (ATES: Simple → Extreme)
    │
    ▼
Получить прогноз лавин для региона/даты
    │
    ▼
Объединить рельеф + прогноз → риск на сегмент
    │
    ▼
Итоговый индикатор: зелёный / жёлтый / красный
```

**Ключевой нюанс:** анализируется не точка трека, а рельеф выше/вокруг точки. Маршрут может идти по плоскому дну ущелья, но быть смертельно опасным из-за склонов 35° сверху.

---

## Ситуация в Алматы / Иле-Алатау

### Что есть

- **ingeo.kz** — экспериментальный бюллетень (с декабря 2020), нейросеть на 20 годах данных
  - Покрытие: бассейны Большой и Малой Алматинки
  - Точность: 90% текущий уровень, 80% прогноз
  - Распространение: Telegram + сайт, **нет API**
- **КазГидроМет** — только штормовые предупреждения, нет структурированных данных
- **Казселезащита** — превентивные спуски лавин (с 1974), не публичный сервис

### Чего нет

- Нет ATES-картирования для Иле-Алатау
- Нет машиночитаемого API лавинных прогнозов
- Нет slope angle overlays для региона в существующих приложениях

### Статистика

- 143 человека попали в лавины за 55 лет в Иле-Алатау, 67 погибших
- 90% — лыжники/туристы/альпинисты
- 85% лавин — февраль-март
- Критическая высота: >2600м, снежный покров 80-170 см

---

## План реализации (фазы)

### Phase 1: Terrain-only анализ (минимум)

- Скачать Copernicus DEM GLO-30 для зоны Иле-Алатау
- Для каждой точки GPX считать углы склонов в буфере
- Показывать "лавиноопасные участки" где маршрут проходит через/под склонами 30-45°
- Python: `richdem` или `numpy` для slope/aspect

### Phase 2: ATES-классификация

- Запустить AutoATES v2.0 для региона
- Нужна карта лесного покрова (Copernicus Tree Cover Density)
- Мэтчить GPX с ATES-классами (Simple → Extreme)

### Phase 3: Интеграция с прогнозом

- Парсить бюллетень ingeo.kz (скрейпинг Telegram/сайта)
- Комбинировать terrain + forecast → итоговый риск

---

## Open source проекты и ссылки

- **AutoATES v2.0**: github.com/AutoATES/AutoATES-v2.0
- **Flow-Py**: моделирование зон схода лавин
- **pyAvaCore**: gitlab.com/albina-euregio/pyAvaCore — парсинг европейских бюллетеней
- **OpenAvalancheProject**: github.com/scottcha/OpenAvalancheProject — ML для прогнозов
- **ATESmaps**: github.com/Atesmaps/ — open source ATES для Пиренеев
- **gpxpy**: github.com/tkrajina/gpxpy — Python GPX парсер
- **python-srtm**: pypi.org/project/python-srtm/ — чтение SRTM данных

### Академические работы

- Schmudlach (2024): "SLABS: An improved probabilistic method to assess the avalanche risk on backcountry ski tours"
- ISSW 2024: "A Routing Algorithm for Backcountry Ski Tours"
- Toft et al. (2024): "AutoATES v2.0: Automated Avalanche Terrain Exposure Scale mapping"
- Sykes et al. (2024): "Automated ATES mapping — local validation in western Canada"

---

## Вывод

Terrain-based анализ (Phase 1) реализуем с открытыми данными уже сейчас. Для Казахстана такого продукта нет — это уникальная фича. Полная интеграция с прогнозами упирается в отсутствие API у ingeo.kz.
