# Backlog: Гранулярные данные для точного профиля

**Приоритет:** Средний (после обкатки текущей системы)
**Сложность:** Средняя-Высокая
**Эффект:** Потенциально высокий — замена ~1km сплитов на посекундные данные

Два пути получения гранулярных данных:
1. **Strava Streams API** — посекундные данные через API (ограничения: 7-day cache, rate limits)
2. **FIT/GPX файлы напрямую с часов** — полные данные без ограничений Strava

---

## Проблема

Текущий профиль строится из **Strava splits** — агрегированных ~1km сегментов:

```
Split #5: distance=1002m, elevation_diff=+45m, pace=8.2 min/km
→ gradient = +4.5% → категория up_3_8
```

Но внутри 1km сплита рельеф может быть разным:
- 300м подъём +15% → 400м флет → 300м спуск -10%
- Средний градиент ≈ +2% (flat), реальность — три разных категории

Это **загрязняет профиль**: pace 8.2 min/km попадает в `flat_3_3`, хотя реально там был подъём и спуск. IQR фильтр частично справляется, но не полностью.

## Решение: Strava Streams API

### Что даёт

`GET /activities/{id}/streams` возвращает **посекундные** данные:

| Stream | Данные | Пример |
|--------|--------|--------|
| `time` | Секунды от старта | [0, 1, 2, 3, ...] |
| `latlng` | GPS координаты | [[43.23, 76.94], ...] |
| `distance` | Кумулятивная дистанция (м) | [0, 3.2, 6.5, ...] |
| `altitude` | Высота (м) | [1200, 1205, 1203, ...] |
| `velocity_smooth` | Сглаженная скорость (м/с) | [2.8, 3.1, 2.9, ...] |
| `grade_smooth` | Сглаженный градиент (%) | [2.5, 3.1, -1.2, ...] |
| `heartrate` | ЧСС (bpm) | [145, 148, 150, ...] |
| `cadence` | Каденс (spm) | [170, 172, 171, ...] |
| `moving` | Движется ли | [true, true, false, ...] |
| `temp` | Температура (°C) | [15, 16, 15, ...] |
| `watts` | Мощность (W) | если есть датчик |

**Все стримы одной длины** — индекс N в одном стриме = тот же момент в другом.

### Плотность данных

- GPS устройства обычно записывают **1 точку/секунду**
- "Smart recording" может пропускать точки → 30-50% меньше
- Типичная активность:
  - 1 час бега → ~3,600 точек
  - 5 часов хайкинга → ~18,000 точек
  - Trail run 2 часа → ~7,200 точек

### Сравнение со сплитами

| Аспект | Splits (~1km) | Streams (посекундно) |
|--------|--------------|---------------------|
| Точек на 20km | ~20 | ~7,000+ |
| Градиент | Средний на 1km | Точный в каждой точке |
| Pace | Средний на 1km | Мгновенный (сглаженный) |
| Классификация | 1 категория на 1km | Точная категория на каждые ~3м |
| HR зоны | Средний HR на 1km | Точный HR в каждой точке |
| Остановки | Скрыты в elapsed_time | Видны через `moving=false` |

---

## Что это даёт для профиля

### 1. Точная классификация градиента

Вместо одного градиента на 1km — градиент в каждой точке:

```
Сплит: 1km, elevation_diff=+20m → gradient=+2% → flat_3_3 ← НЕТОЧНО

Streams:
  point 0-300: gradient +12% → up_8_12
  point 300-700: gradient +1% → flat_3_3
  point 700-1000: gradient -8% → down_8_3
```

Каждый отрезок попадает в **правильную** категорию.

### 2. Точный pace для каждого градиента

`velocity_smooth` + `grade_smooth` → точный pace на каждом градиенте:

```python
# Из streams: pace=10.5 min/km при grade=+12% → up_8_12
# Из splits: pace=8.2 min/km при grade=+2% → flat_3_3 (НЕПРАВИЛЬНАЯ категория!)
```

### 3. Фильтрация остановок

`moving=false` точно показывает, когда атлет стоял. Сейчас остановки "размазываются" по сплиту и завышают pace.

### 4. HR зоны для effort level

`heartrate` в каждой точке → точное определение effort:
- HR Zone 4 → Race effort (подтверждает P25)
- HR Zone 2-3 → Moderate (подтверждает P50)
- HR Zone 1-2 → Easy (подтверждает P75)

### 5. Fatigue curve

`velocity_smooth` + `time` → как падает скорость по ходу активности. Точнее текущей модели усталости (которая считает по сплитам).

---

## Ограничения и риски

### Strava API Agreement (критично!)

**Правило 7 дней:**
> "No Strava Data shall remain in your cache longer than seven days."

**Запрет на ML/AI:**
> "You may not use the Strava API Materials for any model training related to artificial intelligence, machine learning or similar applications." (November 2024)

**Запрет на аналитику:**
> Data cannot be processed "for the purposes of analytics, analyses, customer insights generation."

### Как работать в рамках правил

**Подход: "process and discard"**

1. Fetch streams для активности
2. **Немедленно** вычислить производные метрики:
   - Pace per gradient category (как для профиля)
   - HR zone distribution
   - Fatigue curve parameters
3. Сохранить **только производные метрики** (агрегированные, не raw data)
4. Удалить raw streams data

**Юридическая интерпретация:**
- Raw streams (GPS, секундные данные) → **нельзя хранить >7 дней**
- Производные метрики (средний pace по категории, HR zone %) → **агрегированные данные пользователя**, аналогично текущим splits
- Мы НЕ тренируем ML модель — калибровка профиля для конкретного пользователя ≠ "model training"
- Данные показываются **только самому пользователю**

### Rate Limits

| Лимит | Значение | Текущее использование |
|-------|----------|----------------------|
| 15 мин (read) | 100 запросов | ~20 на sync |
| Дневной (read) | 1,000 запросов | ~100-200 на sync |
| 15 мин (overall) | 200 запросов | — |
| Дневной (overall) | 2,000 запросов | — |

**Streams для калибровки:**
- 50 активностей = 51 запрос (1 list + 50 streams) → укладывается в 1 batch
- 100 активностей = 101 → нужно 2 x 15-минутных окна (read limit 100/15min)
- **Важно:** текущий `StravaRateLimiter` не отслеживает отдельный read лимит!

### Scope

Текущий scope: `activity:read` — не видит приватные активности.

Для streams калибровки нужен `activity:read_all` — чтобы пользователь мог использовать все свои активности, включая приватные.

---

## Архитектура реализации

### Вариант A: Streams при sync (постоянно)

```
Strava Sync Flow:
  1. Fetch activity list
  2. Fetch activity detail (splits)
  3. NEW: Fetch streams → process → save derived metrics → delete raw
  4. Recalculate profile
```

**Плюсы:** Профиль всегда основан на streams данных
**Минусы:** +1 API запрос на активность, замедляет sync, rate limits

### Вариант B: Streams для калибровки (по запросу) — РЕКОМЕНДУЕТСЯ

```
Normal Sync: как сейчас (splits only)

Calibration (manual trigger):
  1. Fetch streams для N активностей
  2. Классифицировать gradient в каждой точке → pace per category
  3. Рассчитать streams-based профиль
  4. Сохранить как "precise profile" рядом с splits-based profile
  5. Удалить raw streams
```

**Плюсы:** Не влияет на sync, пользователь контролирует когда запускать
**Минусы:** Два профиля (splits-based и streams-based)

### Вариант C: Streams → агрегированные мини-сплиты (гибрид)

```
При sync или калибровке:
  1. Fetch streams
  2. Порезать на мини-сегменты по рельефу (как RouteSegmenter)
  3. Каждый мини-сегмент: {gradient, pace, hr, distance}
  4. Сохранить мини-сегменты как StravaActivityMicroSplit
  5. Удалить raw streams

  Мини-сегмент = агрегированный, БЕЗ GPS → можно хранить!
```

**Плюсы:** Максимальная точность, хранение compliant
**Минусы:** Больше данных в БД, сложнее реализация

---

## Что менять (высокий уровень)

### 1. Strava Client

```python
# backend/app/features/strava/client.py

async def get_activity_streams(
    self,
    access_token: str,
    activity_id: int,
    keys: list[str] = None,
) -> dict:
    """
    Fetch time-series streams for an activity.

    Returns dict: {stream_type: [values, ...]}

    WARNING: Raw stream data contains GPS — do NOT store >7 days!
    Process immediately and save only derived metrics.
    """
    if keys is None:
        keys = ["time", "distance", "altitude", "velocity_smooth",
                "grade_smooth", "heartrate", "moving"]

    data = await self._api_request(
        "GET",
        f"/activities/{activity_id}/streams",
        access_token,
        params={"keys": ",".join(keys), "key_by_type": "true"}
    )

    # Convert array response to dict
    return {stream["type"]: stream["data"] for stream in data}
```

### 2. Streams Processor

```python
# backend/app/features/strava/streams/processor.py

class StreamsProcessor:
    """Process raw streams into gradient-classified micro-segments."""

    def process(self, streams: dict) -> list[MicroSegment]:
        """
        Convert raw streams to micro-segments by terrain.

        Each micro-segment: {gradient_category, pace, hr, distance}
        This is aggregated data — safe to store long-term.
        """
        # 1. Zip streams by index
        # 2. Group consecutive points by gradient category
        # 3. Calculate avg pace, HR for each group
        # 4. Return list of MicroSegment
```

### 3. Rate Limiter Update

Добавить отслеживание read rate limit (100/15min, 1000/day) отдельно от overall.

### 4. OAuth Scope

Опционально предложить upgrade до `activity:read_all` для калибровки.

### 5. CLI команда

```bash
python -m tools.calibration.cli streams-calibrate \
    --user-id 2f07778a-... \
    --max-activities 50 \
    --min-elevation 100
```

---

## Оценка эффекта

### Ожидаемые улучшения

| Метрика | Сейчас (splits) | Ожидание (streams) | Почему |
|---------|-----------------|-------------------|--------|
| MAPE overall | 14.5% | 10-12% | Точная классификация градиента |
| Bias | -3.2% (Easy) | ±2% | Нет "загрязнения" категорий |
| Steep up accuracy | 17.5% MAPE | 12-15% | Крутые подъёмы точно классифицированы |
| Steep down accuracy | 27.8% MAPE | 18-22% | Спуски без "размазывания" остановок |

### Как быстро проверить гипотезу

**Минимальный эксперимент (1-2 часа):**

1. Взять 3 тестовые активности (494, 570, 563)
2. Fetch streams вручную (3 API запроса)
3. Классифицировать gradient в каждой точке → pace per category
4. Сравнить streams-based профиль vs splits-based профиль
5. Прогнать предсказание на тех же маршрутах → сравнить ошибку

Если ошибка уменьшается на >2% MAPE — стоит реализовывать.

---

## Дополнительные возможности (не в первой итерации)

### HR-based Effort Detection

```python
# Из streams: HR в каждой точке
# Можно автоматически определять effort level:
if avg_hr > hr_zone_4_threshold:
    effort = "race"
elif avg_hr > hr_zone_2_threshold:
    effort = "moderate"
else:
    effort = "easy"
```

Это заменит ручной выбор effort level объективными HR данными.

### Surface Detection (экспериментально)

Высокая вариабельность `grade_smooth` на коротких отрезках → trail/technical terrain.
Низкая вариабельность → road/smooth trail.

### Fatigue Model v2

Посекундный `velocity_smooth` + `heartrate` → точная модель утомления:
- Cardiac drift (HR растёт при том же pace)
- Pace degradation curve

---

---

## Альтернатива: FIT/GPX файлы напрямую с часов

### Зачем

Strava Streams API имеет жёсткие ограничения (7-day cache, rate limits, API agreement Nov 2024). Прямой импорт файлов с часов **снимает все эти ограничения** — данные принадлежат пользователю, можно хранить и обрабатывать как угодно.

### Форматы по брендам

| Бренд | Нативный формат | Запись по умолчанию | Running Power | Running Dynamics | FIT экспорт |
|-------|----------------|--------------------|----|---|---|
| **Garmin** | FIT | Smart (~3-6с) | Wrist/HRM-Pro+ | С HRM-Pro+ | Нативный |
| **Suunto** | FIT (новые) / SML (старые) | 1с (Performance mode) | Да | Ограниченно | Нативный (новые) |
| **COROS** | FIT | 1с | Wrist | Wrist | Нативный |
| **Polar** | Проприетарный | 1с (High mode) | Vantage V3/Grit X2 Pro | Нет | **Нет** (TCX/GPX) |

### FIT файл — что внутри

FIT (Flexible and Interoperable Data Transfer) — компактный бинарный формат от Garmin/ANT+, де-факто стандарт. Структура:

**Record messages (каждую секунду или Smart):**
- `position_lat` / `position_long` — GPS координаты (semicircles, точнее float32)
- `enhanced_altitude` — высота (м)
- `enhanced_speed` — скорость (м/с)
- `heart_rate` — ЧСС (bpm)
- `cadence` — каденс (spm)
- `power` — мощность (W)
- `temperature` — температура (°C)
- `distance` — кумулятивная дистанция (м)
- `vertical_oscillation` — вертикальные колебания (см)
- `ground_contact_time` — время контакта с землёй (мс)
- `stance_time_percent` — % времени на опоре
- `stride_length` — длина шага (м)

**Lap messages (по кругам/километрам):**
- Аналог Strava splits, но с полными данными

**Session message (итог):**
- Общая статистика: дистанция, время, средний HR, max HR и т.д.

### Плотность данных

| Режим записи | Точек/час | На 2ч trail run | Размер FIT |
|-------------|-----------|-----------------|------------|
| Smart (~3-6с) | ~600-1,200 | ~1,200-2,400 | 100-300 KB |
| Every Second | ~3,600 | ~7,200 | 300 KB - 1 MB |
| Every Second + Dynamics + HRV | ~3,600+ | ~7,200+ | 1-3 MB |

**Важно:** Smart Recording пропускает точки на прямых отрезках → деградирует точность grade/pace анализа. Для профиля предпочтителен 1-second recording.

### GPX — что теряется при экспорте из FIT

GPX сохраняет:
- lat/lon, elevation, time
- HR, cadence, temperature (через Garmin TrackPointExtension)

GPX **теряет**:
- Running power
- Running dynamics (ground contact, vertical oscillation, stride length)
- Lap/session summaries
- Device/sensor info
- Cumulative distance (нужно пересчитывать из координат)
- High-resolution HR / RR intervals

### Способы получения файлов

| Способ | Garmin | Suunto | COROS | Polar |
|--------|--------|--------|-------|-------|
| USB (mass storage) | FIT из `Garmin/ACTIVITY/` | Нет | Нет | Нет |
| Мобильное приложение | FIT/TCX/GPX | FIT/GPX | FIT/TCX/GPX | TCX/GPX/CSV |
| Web платформа | FIT/TCX/GPX/CSV/KML | Через API | FIT/TCX (bulk) | TCX/GPX/CSV |
| API платформы | FIT (бизнес) | FIT (бизнес) | Приватный | TCX/GPX (открытый) |
| Полный экспорт данных | GDPR export | Через API | Help Center | GDPR export |

### API платформ — сравнение

| Платформа | Доступность | Формат данных | Ограничения |
|-----------|------------|---------------|-------------|
| **Garmin Connect** | Только бизнес (~2 дня review) | FIT download | OAuth2, webhooks |
| **Suunto API** | Только бизнес (~2 недели review) | FIT download | Azure hosted |
| **COROS API** | Приватная документация | Неизвестно | По запросу |
| **Polar AccessLink** | **Открытый для всех** | TCX/GPX (не FIT!) | OAuth2, JSON/XML |

**Polar — исключение:** нет FIT экспорта нигде. Для Polar пользователей — TCX fallback.

### Python библиотеки для парсинга

**FIT:**

| Библиотека | Статус | Примечание |
|-----------|--------|-----------|
| `fitdecode` | Активная, рекомендуется | Thread-safe, MIT. `pip install fitdecode` |
| `fitparse` | Legacy | Оригинальная, fitdecode лучше |
| `garmin-fit-sdk` | Официальный Garmin SDK | `pip install garmin-fit-sdk` |
| `fit2gpx` | Утилита конвертации | FIT → GPX/DataFrame |

**GPX:**

| Библиотека | Примечание |
|-----------|-----------|
| `gpxpy` | **Уже используется в проекте!** `pip install gpxpy` |

**Пример парсинга FIT:**

```python
import fitdecode

with fitdecode.FitReader('activity.fit') as fit:
    for frame in fit:
        if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
            lat = frame.get_value('position_lat')
            lon = frame.get_value('position_long')
            hr = frame.get_value('heart_rate')
            speed = frame.get_value('enhanced_speed')
            altitude = frame.get_value('enhanced_altitude')
            power = frame.get_value('power')
            cadence = frame.get_value('cadence')
            # Semicircles → degrees
            if lat and lon:
                lat_deg = lat * (180 / 2**31)
                lon_deg = lon * (180 / 2**31)
```

---

## FIT upload vs Strava Streams — сравнение подходов

| Аспект | Strava Streams API | FIT файл upload |
|--------|-------------------|-----------------|
| **Данные** | 11 стримов (без power на бег) | Все поля включая power, dynamics |
| **Хранение** | Max 7 дней (raw) | Без ограничений (данные пользователя) |
| **Rate limits** | 100 read/15min, 1000/day | Нет |
| **Авторизация** | OAuth + scope upgrade | Файл upload (нет OAuth) |
| **Покрытие** | Все Strava пользователи | Garmin, Suunto, COROS (не Polar для FIT) |
| **Автоматизация** | Полная (при sync) | Полная (webhook + API) или ручной upload |
| **Юридические риски** | API Agreement restrictions | Нет (данные пользователя) |
| **Реализация** | Средняя (API client, rate limiter) | Простая (file upload + fitdecode) |

### Автоматизация: прямые интеграции с платформами часов

FIT upload — не обязательно ручной. Можно интегрироваться напрямую с платформами:

| Платформа | Автоматизация | Webhooks | Формат | Доступность |
|-----------|--------------|----------|--------|-------------|
| **Garmin Connect API** | Полная (webhook → FIT download) | Да | FIT | Бизнес, бесплатный (~2 дня review) |
| **Suunto API** | Полная (webhook → FIT download) | Да | FIT | Бизнес (~2 нед review) |
| **COROS API** | Полная (используют Intervals.icu, Tredict) | Вероятно | FIT? | Приватная документация |
| **Polar AccessLink** | Полная (OAuth, polling) | Нет | TCX/GPX | Открытый для всех |

**Garmin** — самый перспективный: webhook при новой активности → автоматически скачать FIT → обработать → обновить профиль. Без Strava как посредника, с полными данными (power, dynamics, temperature).

### Рекомендация

**Для быстрого старта:** FIT file upload (ручной) — минимум работы, проверка гипотезы.
**Для продакшена:** Garmin Connect API (webhook + FIT download) — автоматический, полные данные.
**Параллельно:** Strava splits для повседневного sync (уже работает), FIT для точного профиля.
**Fallback:** Strava Streams API — если прямая интеграция с часами невозможна.

---

## Зависимости

- Текущая система (Phases 0-3) должна быть стабильна
- Для Strava Streams: rate limiter нужно обновить (read limit tracking)
- Для FIT upload: добавить `fitdecode` в зависимости
- Опционально: scope upgrade до `activity:read_all`

## Ссылки

### Strava
- [Strava API Streams Reference](https://developers.strava.com/docs/reference/#api-Streams-getActivityStreams)
- [Strava API Rate Limits](https://developers.strava.com/docs/rate-limits/)
- [Strava API Agreement (2024)](https://www.strava.com/legal/api)
- [DCRainmaker: Strava API Changes (Nov 2024)](https://www.dcrainmaker.com/2024/11/stravas-changes-to-kill-off-apps.html)

### FIT / часы
- [Garmin FIT Protocol](https://developer.garmin.com/fit/protocol/)
- [Garmin FIT Activity Files](https://developer.garmin.com/fit/file-types/activity/)
- [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/)
- [Suunto API](https://apizone.suunto.com/)
- [COROS Export](https://support.coros.com/hc/en-us/articles/360043975752)
- [Polar AccessLink API](https://www.polar.com/accesslink-api/)

### Python
- [fitdecode (PyPI)](https://pypi.org/project/fitdecode/)
- [gpxpy (PyPI)](https://pypi.org/project/gpxpy/)
- [python-garminconnect (GitHub)](https://github.com/cyberjunky/python-garminconnect)

## Чеклист (при реализации)

### Strava Streams путь
- [ ] Strava Client: метод `get_activity_streams()`
- [ ] StreamsProcessor: raw streams → micro-segments
- [ ] Rate Limiter: отдельный read limit tracking (100/15min, 1000/day)
- [ ] CLI: `streams-calibrate` команда
- [ ] Опционально: scope upgrade `activity:read_all`

### FIT upload путь
- [ ] Добавить `fitdecode` в зависимости
- [ ] FIT parser: record messages → unified data points
- [ ] API endpoint: POST /upload/fit (multipart file upload)
- [ ] CLI: `calibrate-from-fit --file activity.fit`
- [ ] Обработка Smart Recording (детекция sparse data, предупреждение)
- [ ] TCX fallback для Polar пользователей

### Общее
- [ ] Эксперимент: 3 тестовые активности, FIT vs splits профиль
- [ ] Если эффект >2% MAPE: полная реализация
- [ ] Опционально: HR-based effort detection
- [ ] Опционально: running power для grade adjustment
