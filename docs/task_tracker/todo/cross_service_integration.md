# Кросс-сервисная интеграция: gpx_predictor ↔ ayda_run

## Контекст

Два проекта должны обмениваться данными:
- **ayda_run** (`C:\Users\renat\projects\02_ayda_run_v2`) — Telegram-бот для бегового сообщества, имеет одобренную Strava OAuth интеграцию
- **gpx_predictor** (`C:\Users\renat\projects\gpx-predictor`) — сервис прогнозов трейл-забегов и хайкинга, имеет Strava-синк и профилирование пользователей

### Зачем интеграция

| Сценарий | Направление | Описание |
|----------|-------------|----------|
| Strava-токены | ayda_run → gpx_predictor | gpx_predictor получает Strava-токены пользователей через ayda_run (одобренный OAuth) |
| Предикт трассы | ayda_run → gpx_predictor | ayda_run запрашивает прогноз для пользователя по GPX-файлу |
| Матчинг пользователей | ayda_run → gpx_predictor | ayda_run получает профили для подбора пар по уровню |
| Авто-профилирование | ayda_run → gpx_predictor | При OAuth авторизации в ayda_run — автоматический запуск синка и профилирования в gpx_predictor |

### Технические различия проектов

| | ayda_run | gpx_predictor |
|---|---|---|
| ORM | Sync SQLAlchemy (`Session`) | Async SQLAlchemy (`AsyncSession`) |
| Strava токены | Зашифрованы Fernet | Plaintext в `StravaToken` |
| Strava scope | `read,activity:read_all` | `activity:read` |
| telegram_id тип | `BigInteger` | `String` |
| API auth | Telegram WebApp HMAC | Нет (публичные endpoints) |

### Общий подход

- Один shared API-ключ: `CROSS_SERVICE_API_KEY` (в env обоих проектов)
- Проверка через header `X-API-Key`
- **telegram_id в API-контракте — всегда string** (ayda_run конвертирует `str(user.telegram_id)`, gpx_predictor принимает как есть)
- Каждый endpoint возвращает scope в ответе, чтобы вызывающая сторона знала что доступно

### Strava Rate Limits (общая квота)

Оба сервиса используют токены одного Strava OAuth приложения (ayda_run), значит делят одну квоту:

| Лимит | Всего | ayda_run | gpx_predictor | Буфер |
|-------|-------|----------|---------------|-------|
| Read / 15 мин | 300 | 100 | 200 | — |
| Read / день | 3000 | 1000 | 2000 | — |
| Overall / 15 мин | 600 | 200 | 400 | — |
| Overall / день | 6000 | 2000 | 4000 | — |

**Каждый сервис считает локально** (in-memory rate limiter). Координация через shared counter (Redis) — только если упрёмся в лимиты при масштабировании.

**gpx_predictor — основной потребитель** (синк активностей + сплитов), поэтому ему бОльшая доля.

---

## Шаг 1: Strava-токены через ayda_run

**Цель:** gpx_predictor получает Strava access_token по telegram_id через API ayda_run (вместо собственного OAuth).

### 1.1 [ayda_run] Endpoint для выдачи токена

**Файл:** `app/routers/internal_api.py` (новый)

```
GET /api/internal/strava/token?telegram_id={telegram_id}
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
```

**Параметр `telegram_id`:** принимать как string, конвертировать в int для поиска в БД (`int(telegram_id)`).

**Response 200:**
```json
{
  "access_token": "decrypted_token",
  "athlete_id": 12345,
  "scope": "read,activity:read_all"
}
```

**Response 404:** пользователь не найден или Strava не подключена

**Логика:**
1. Проверить `X-API-Key` == `settings.cross_service_api_key` → 401 если нет
2. Найти user по `telegram_id` (преобразовать в int) → 404 если нет
3. Проверить `user.strava_athlete_id` → 404 если Strava не подключена
4. Вызвать `StravaService(db).get_valid_token(user)` — автоматический refresh если истёк
5. Вернуть расшифрованный access_token, athlete_id, scope (`"read,activity:read_all"`)

**Что добавить:**

| Файл | Изменение |
|------|-----------|
| `app/routers/internal_api.py` | **Новый.** Endpoint + API-key dependency |
| `config.py` | Добавить `cross_service_api_key: Optional[str]` |
| `api_server.py` | Зарегистрировать `internal_api.router` |

**API-key dependency** (в том же файле):
```python
def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if not settings.cross_service_api_key:
        raise HTTPException(status_code=503, detail="Internal API not configured")
    if x_api_key != settings.cross_service_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
```

**Scope:** `"read,activity:read_all"` — хардкод, т.к. ayda_run всегда запрашивает этот scope. Scope `activity:read_all` — суперсет `activity:read`, поэтому gpx_predictor получает полный доступ.

---

### 1.2 [gpx_predictor] Клиент для ayda_run

**Файл:** `backend/app/features/strava/ayda_client.py` (новый)

**Класс:** `AydaRunClient`

```python
class AydaRunClient:
    """Получает Strava-токены через ayda_run API."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._token_cache: dict[str, tuple[dict, float]] = {}  # telegram_id → (token_data, expires_at)
        self.CACHE_TTL = 30 * 60  # 30 минут

    async def get_strava_token(self, telegram_id: str) -> Optional[dict]:
        """
        Returns: {"access_token": "...", "athlete_id": 123, "scope": "..."} or None
        Кеширует результат на 30 минут (Strava токены живут ~6 часов).
        """
```

**Логика:**
1. Проверить in-memory кеш → если есть и не истёк, вернуть из кеша
2. `GET {api_url}/api/internal/strava/token?telegram_id={telegram_id}`
3. Header: `X-API-Key: {api_key}`
4. Timeout: 10 секунд
5. 200 → сохранить в кеш, вернуть dict
6. 404 → вернуть None (не кешировать — пользователь может подключить Strava)
7. Другое / timeout / ошибка → залогировать warning, вернуть None

**Почему in-memory кеш обязателен:**
- Во время синка gpx_predictor делает десятки/сотни запросов к Strava за один сеанс
- Без кеша каждый API-вызов к Strava → HTTP-запрос в ayda_run за тем же токеном
- Strava токены живут ~6 часов, кеш на 30 минут — безопасно

---

### 1.3 [gpx_predictor] Fallback в sync service

**Изменение:** в **sync service**, а не в `get_valid_token()` — не ломаем сигнатуру существующего метода.

**Файл:** `backend/app/features/strava/sync/service.py`

**Flow в sync service:**
```
1. token = await strava_client.get_valid_token(user_id)  # локальный токен
2. if not token and ayda_client:
     token_data = await ayda_client.get_strava_token(user.telegram_id)
     if token_data:
       token = token_data["access_token"]
3. if not token: skip user (log warning)
4. Использовать token для Strava API вызовов
```

**Почему fallback в sync service, а не в `get_valid_token()`:**
- `get_valid_token(user_id)` принимает internal UUID, а для ayda_run нужен telegram_id
- Sync service уже имеет доступ к user объекту с telegram_id
- Чистое разделение ответственности: `StravaClient` работает с токенами, sync service решает откуда их брать

**Инициализация `AydaRunClient`:**
- Создавать при старте sync service (если `settings.ayda_run_api_url` задан)
- Передавать как optional dependency

---

### 1.4 [gpx_predictor] Конфигурация

**Файл:** `backend/app/config.py`

Добавить:
```python
cross_service_api_key: Optional[str] = Field(default=None)
ayda_run_api_url: Optional[str] = Field(default=None)
```

---

### Критерий готовности шага 1

- [ ] [ayda_run] Endpoint `/api/internal/strava/token` работает, отдаёт расшифрованный токен
- [ ] [ayda_run] Endpoint защищён API-ключом
- [ ] [ayda_run] Автоматический token refresh перед отдачей
- [ ] [gpx_predictor] `AydaRunClient` с in-memory кешем на 30 мин
- [ ] [gpx_predictor] Sync service делает fallback на ayda_run если нет локального токена
- [ ] [gpx_predictor] Без `AYDA_RUN_API_URL` — работает как раньше (локальные токены)
- [ ] [gpx_predictor] Rate limiter обновлён: 200 read/15мин, 2000 read/день
- [ ] Оба проекта: env переменная `CROSS_SERVICE_API_KEY`

---

## Шаг 2: Авто-профилирование при OAuth

**Цель:** Когда пользователь подключает Strava через ayda_run, автоматически запускается синк и профилирование в gpx_predictor.

### 2.1 [gpx_predictor] Webhook endpoint для триггера синка

**Файл:** `backend/app/api/v1/routes/internal.py` (новый)

```
POST /api/v1/internal/strava/connected
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
Body: {"telegram_id": "123456", "athlete_id": 12345}
```

**Response 200:**
```json
{"status": "sync_triggered", "user_id": "uuid"}
```

**Логика:**
1. Проверить API-ключ
2. Найти или создать пользователя по telegram_id
3. Сохранить athlete_id в User модель (для будущего матчинга)
4. Вызвать `trigger_user_sync(user.id, priority=True)` — запускает фоновый синк
5. Синк сам запросит токен: `get_valid_token()` → None → fallback на ayda_run API

### 2.2 [ayda_run] Вызов webhook при OAuth callback

**Файл:** `app/routers/strava.py` — в существующий callback handler

**Изменение:** После успешного сохранения токенов, в background task:
```python
# После strava_service.save_tokens(user, token_data):
if settings.cross_service_api_key and settings.gpx_predictor_api_url:
    background_tasks.add_task(
        notify_gpx_predictor_strava_connected,
        telegram_id=user.telegram_id,
        athlete_id=token_data["athlete"]["id"]
    )
```

**Функция (с обязательным try/except + logging):**
```python
async def notify_gpx_predictor_strava_connected(telegram_id: int, athlete_id: int):
    """Fire-and-forget уведомление gpx_predictor о новом Strava-подключении."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.gpx_predictor_api_url}/api/v1/internal/strava/connected",
                json={"telegram_id": str(telegram_id), "athlete_id": athlete_id},
                headers={"X-API-Key": settings.cross_service_api_key},
                timeout=10.0
            )
            resp.raise_for_status()
            logger.info("Notified gpx_predictor about Strava connection for %s", telegram_id)
    except Exception as e:
        logger.warning("Failed to notify gpx_predictor: %s", e)
```

### 2.3 [ayda_run] Конфигурация

**Файл:** `config.py`

Добавить:
```python
gpx_predictor_api_url: Optional[str] = Field(default=None)
```
(`cross_service_api_key` уже добавлен в шаге 1.1)

---

### Критерий готовности шага 2

- [ ] [gpx_predictor] Webhook `/api/v1/internal/strava/connected` принимает уведомление
- [ ] [gpx_predictor] Автоматически создаёт пользователя и запускает синк
- [ ] [ayda_run] OAuth callback отправляет уведомление в gpx_predictor (с try/except)
- [ ] [ayda_run] Уведомление fire-and-forget (не блокирует callback)
- [ ] Без `GPX_PREDICTOR_API_URL` — ayda_run работает как раньше

---

## Шаг 3: Предикт трассы из ayda_run

**Цель:** ayda_run может запросить прогноз прохождения GPX-трассы для пользователя.

### 3.1 [gpx_predictor] API endpoint для предикта

**Файл:** `backend/app/api/v1/routes/internal.py` (дополнить)

```
POST /api/v1/internal/predict
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
Body: {
  "telegram_id": "123456",
  "gpx_file_id": "uuid-of-gpx",       // ИЛИ
  "race_id": "uuid-of-race",          // ИЛИ
  "distance_id": "uuid-of-distance",
  "mode": "trail_run",                // trail_run | hiking
  "flat_pace": 330                    // опционально, секунд/км
}
```

**Response 200:**
```json
{
  "personalized": true,
  "times": {
    "fast": "1:10:00",
    "moderate": "1:21:00",
    "easy": "1:31:00"
  },
  "gap_time": "1:15:00",
  "profile_stats": {
    "total_km": 1091,
    "total_activities": 111,
    "gradient_coverage": "11/11"
  }
}
```

**Логика:** Переиспользовать существующий `RaceService.predict_by_pace()` / `TrailRunService`, добавив API-обёртку.

### 3.2 [ayda_run] Клиент для предикта

**Файл:** `app/services/gpx_predictor_client.py` (новый)

```python
class GPXPredictorClient:
    async def predict_race(self, telegram_id: int, race_id: str, distance_id: str, mode: str) -> Optional[dict]:
        """Запрос прогноза из gpx_predictor."""
```

---

### Критерий готовности шага 3

- [ ] [gpx_predictor] Endpoint `/api/v1/internal/predict` работает
- [ ] [ayda_run] Клиент может запросить прогноз
- [ ] Персонализированный прогноз если есть профиль, GAP-only если нет

---

## Шаг 4: Матчинг пользователей по профилю

**Цель:** ayda_run получает данные профиля для подбора пар по уровню подготовки.

### 4.1 [gpx_predictor] API endpoint для профиля

**Файл:** `backend/app/api/v1/routes/internal.py` (дополнить)

```
GET /api/v1/internal/profile?telegram_id={telegram_id}&type=trail_run
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
```

**Response 200:**
```json
{
  "telegram_id": "123456",
  "type": "trail_run",
  "has_profile": true,
  "flat_pace_p50": 330,
  "total_activities": 111,
  "total_km": 1091,
  "gradient_coverage": 11,
  "level": "intermediate"
}
```

### 4.2 [gpx_predictor] Batch endpoint для матчинга

```
POST /api/v1/internal/profiles/batch
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
Body: {"telegram_ids": ["123", "456", "789"], "type": "trail_run"}
```

**Response:** Массив профилей — для сравнения и группировки.

### 4.3 [ayda_run] Клиент для матчинга

**Файл:** `app/services/gpx_predictor_client.py` (дополнить)

---

### Критерий готовности шага 4

- [ ] [gpx_predictor] Endpoint для одного профиля
- [ ] [gpx_predictor] Batch endpoint для нескольких профилей
- [ ] [ayda_run] Клиент может запрашивать профили

---

## Порядок реализации

1. **Шаг 1** — Strava-токены (минимальная интеграция, ~150 строк, нужна для всего остального)
2. **Шаг 2** — Авто-профилирование (~100 строк, зависит от шага 1)
3. **Шаг 3** — Предикт трассы (~200 строк, зависит от шага 1)
4. **Шаг 4** — Матчинг (~150 строк, зависит от шага 2)

**Шаги 3 и 4 независимы друг от друга** — можно делать в любом порядке.

---

## Env переменные (итог)

### ayda_run (.env)
```
CROSS_SERVICE_API_KEY=shared_secret_here
GPX_PREDICTOR_API_URL=http://localhost:8000    # или продакшн URL
```

### gpx_predictor (.env)
```
CROSS_SERVICE_API_KEY=shared_secret_here       # тот же ключ
AYDA_RUN_API_URL=http://localhost:8001          # или продакшн URL
```

---

## Known Limitations

1. **Shared Strava rate limit** — оба сервиса расходуют квоту одного Strava OAuth приложения. Лимиты распределены статически (см. таблицу выше). При масштабировании → shared counter через Redis.
2. **In-memory token cache** — при рестарте gpx_predictor кеш сбрасывается. Первые запросы после рестарта пойдут в ayda_run API. Не проблема при текущем масштабе.
3. **Локальные rate limiter'ы** — не координированы между сервисами. При одновременной высокой нагрузке возможно превышение общей квоты Strava.
4. **Hardcoded callback URL** в gpx_predictor (`strava.py:342`) — `http://localhost:8000/...`. Не связано с интеграцией, но сломается при деплое. Отдельная задача.

---

## Что НЕ делаем

- Удаление локального OAuth из gpx_predictor (оставить как fallback)
- Синхронизацию БД пользователей между проектами (только lazy create по telegram_id)
- Общую систему аутентификации (каждый проект сохраняет свою)
- gRPC или message queue (HTTP достаточно для текущего масштаба)
- Shared rate limiter через Redis (overengineering на текущем масштабе)
