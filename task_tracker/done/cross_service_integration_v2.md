# Кросс-сервисная интеграция: gpx_predictor ↔ ayda_run

## Контекст

Два проекта должны обмениваться данными:
- **ayda_run** (`C:\Users\renat\projects\02_ayda_run_v2`) — Telegram-бот для бегового сообщества, имеет одобренную Strava OAuth интеграцию
- **gpx_predictor** (`C:\Users\renat\projects\gpx-predictor`) — сервис прогнозов трейл-забегов и хайкинга, имеет Strava-синк и профилирование пользователей

### Зачем интеграция

| Сценарий | Направление | Описание |
|----------|-------------|----------|
| Strava-токены | ayda_run → gpx_predictor | gpx_predictor получает Strava-токены пользователей через ayda_run (одобренный OAuth) |
| Проксирование OAuth | gpx_predictor → ayda_run | Юзеры gpx_predictor подключают Strava через OAuth ayda_run (у которого есть апрув) |
| Авто-профилирование | ayda_run → gpx_predictor | При OAuth авторизации в ayda_run — автоматический запуск синка и профилирования в gpx_predictor |
| Предикт трассы | ayda_run → gpx_predictor | ayda_run запрашивает прогноз для пользователя по GPX-файлу |
| Матчинг пользователей | ayda_run → gpx_predictor | ayda_run получает профили для подбора пар по уровню |

### Технические различия проектов

| | ayda_run | gpx_predictor |
|---|---|---|
| ORM | Sync SQLAlchemy (`Session`) | Async SQLAlchemy (`AsyncSession`) |
| Strava токены | Зашифрованы Fernet | Plaintext в `StravaToken` |
| Strava scope | `read,activity:read_all` | `activity:read` |
| telegram_id тип | `BigInteger` | `BigInteger` (мигрировано в шаге 0) |
| API auth | Telegram WebApp HMAC | Нет (публичные endpoints) |

### Общий подход

- Один shared API-ключ: `CROSS_SERVICE_API_KEY` (в env обоих проектов)
- Проверка через header `X-API-Key`
- **telegram_id в API-контракте — integer** (оба проекта используют BigInteger после миграции шага 0)
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

## Шаг 2.5: Проксирование OAuth для внешних сервисов

**Цель:** Пользователи gpx_predictor подключают Strava через OAuth ayda_run (у которого есть апрув от Strava на внешних юзеров). gpx_predictor не имеет собственного апрува.

### Зачем

- У ayda_run есть одобренный Strava OAuth для внешних пользователей
- У gpx_predictor нет — его OAuth работает только для developer account
- Нужно чтобы юзеры gpx_predictor могли подключить Strava через ayda_run

### Flow

```
gpx_predictor бот: юзер жмёт "Подключить Strava"
  → бот вызывает ayda_run API: GET /api/internal/strava/auth?telegram_id=123
  → ayda_run: lazy create юзера по telegram_id, генерирует Strava OAuth URL
  → возвращает {"auth_url": "https://strava.com/oauth/authorize?..."}
  → бот показывает юзеру кнопку-ссылку с auth_url
  → юзер кликает, авторизуется в Strava
  → Strava callback → ayda_run сохраняет токены
  → ayda_run шлёт webhook в gpx_predictor (шаг 2, уже работает)
  → gpx_predictor запускает sync, берёт токены через API (шаг 1)
```

### 2.5.1 [ayda_run] Endpoint для генерации OAuth URL

**Файл:** `app/routers/internal_api.py` (дополнить)

```
GET /api/internal/strava/auth?telegram_id={telegram_id}
Headers: X-API-Key: {CROSS_SERVICE_API_KEY}
```

**Response 200:**
```json
{
  "auth_url": "https://www.strava.com/oauth/authorize?client_id=...&redirect_uri=...&state=user-uuid&scope=read,activity:read_all&response_type=code"
}
```

**Response 400:** Strava уже подключена для этого пользователя

**Логика:**
1. Проверить `X-API-Key` → 401
2. Найти или **создать** юзера по `telegram_id` (lazy create)
3. Если `user.strava_athlete_id` уже есть → 400 "Strava already connected"
4. Сгенерировать Strava OAuth URL:
   - `client_id` = `settings.strava_client_id`
   - `redirect_uri` = `{settings.base_url}/api/strava/callback`
   - `state` = `user.id` (UUID — как в существующем flow)
   - `scope` = `read,activity:read_all`
   - `response_type` = `code`
5. Вернуть `{"auth_url": url}`

**Важно:** Используется тот же callback (`/api/strava/callback`), что и для "родных" юзеров ayda_run. Callback уже делает save_tokens + webhook в gpx_predictor. Никаких изменений в callback не нужно.

**Lazy create юзера:**
```python
user = db.query(User).filter(User.telegram_id == telegram_id).first()
if not user:
    user = User(telegram_id=telegram_id)
    db.add(user)
    db.commit()
    db.refresh(user)
```

### 2.5.2 [gpx_predictor] Изменение OAuth flow в боте

**Файл:** Strava-хэндлер в боте gpx_predictor

**Изменение:** Вместо генерации собственного OAuth URL (`strava.com/oauth/authorize` с credentials gpx_predictor), бот:
1. Вызывает `ayda_run API: GET /api/internal/strava/auth?telegram_id={user.telegram_id}`
2. Получает `auth_url`
3. Отдаёт юзеру кнопку с этой ссылкой

**Fallback:** Если `AYDA_RUN_API_URL` не задан — использовать собственный OAuth (для dev-режима).

---

### Критерий готовности шага 2.5

- [ ] [ayda_run] Endpoint `/api/internal/strava/auth` возвращает OAuth URL
- [ ] [ayda_run] Lazy create юзера по telegram_id если не существует
- [ ] [ayda_run] Strava already connected → 400
- [ ] [gpx_predictor] Бот использует ayda_run OAuth URL вместо собственного
- [ ] [gpx_predictor] Fallback на собственный OAuth если `AYDA_RUN_API_URL` не задан
- [ ] Callback в ayda_run работает для "внешних" юзеров (webhook → gpx_predictor)

---

## ~~Шаг 3: Предикт трассы из ayda_run~~ → перенесён в бэклог

Перенесён в `docs/task_tracker/backlog/races_mvp.md` (пункт 5).

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

1. **Шаг 1** — Strava-токены (минимальная интеграция, ~150 строк, нужна для всего остального) ✅
2. **Шаг 2** — Авто-профилирование (~100 строк, зависит от шага 1) ✅
3. **Шаг 2.5** — Проксирование OAuth для gpx_predictor (~80 строк, зависит от шагов 1+2) ✅
4. ~~**Шаг 3** — Предикт трассы~~ → перенесён в бэклог (`backlog/races_mvp.md`)
5. **Шаг 4** — Матчинг (~150 строк, зависит от шага 2)

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
