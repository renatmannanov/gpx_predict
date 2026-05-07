# Фаза 4: Strava интеграция

**Цель:** Автоматическое получение данных атлета

> **Требуется:** Approval в Strava Developer Program
> - Подать заявку: https://www.strava.com/settings/api
> - Email: developers@strava.com
> - Процесс: 1-4 недели
> - Начинается с "capacity of 1" (только ваш аккаунт)

---

## Шаги реализации

### Шаг 1: Strava OAuth
- OAuth 2.0 flow
- Token storage (encrypted)
- Token refresh

### Шаг 2: Strava API Client
- Get athlete stats
- Get activities (6 months)
- Rate limiting (in-memory для MVP)

### Шаг 3: Webhooks
- Webhook subscription
- Event handling (activity.create, deauthorize)
- Background processing

### Шаг 4: Data Processing
- Extract best efforts
- Aggregate training metrics
- Personal fatigue factor

### Шаг 5: Enhanced Prediction
- Use Strava data in prediction
- Training readiness indicator
- Comparison: manual vs Strava

### Шаг 6: User Management
- User accounts
- Prediction history
- Strava disconnect flow

### Шаг 7: Privacy & Compliance
- Privacy Policy page
- Consent flows
- Data deletion
- 7-day TTL for Strava cache

---

## Deliverables

- [ ] "Войти через Strava" кнопка
- [ ] Автоматическое получение best efforts
- [ ] Персональный fatigue factor
- [ ] История прогнозов пользователя
- [ ] Возможность отключить Strava

---

## OAuth 2.0 Flow

### Инициация авторизации

```python
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://predictor.ayda.run/api/auth/strava/callback"

@router.get("/auth/strava")
async def strava_auth():
    """Инициирует OAuth flow"""

    # Запрашиваем ТОЛЬКО нужные scopes
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=activity:read"
        f"&approval_prompt=auto"
    )

    return RedirectResponse(auth_url)
```

### Callback обработка

```python
@router.get("/auth/strava/callback")
async def strava_callback(code: str, scope: str):
    """Обрабатывает callback от Strava"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code"
            }
        )

    token_data = response.json()

    # Сохраняем токены (зашифрованные!)
    await save_strava_tokens(
        athlete_id=token_data["athlete"]["id"],
        access_token=encrypt(token_data["access_token"]),
        refresh_token=encrypt(token_data["refresh_token"]),
        expires_at=token_data["expires_at"]
    )

    return RedirectResponse("/app?strava=connected")
```

### Обновление токена

```python
async def refresh_strava_token(user_id: str) -> str:
    """Обновляет истёкший токен"""

    user = await get_user(user_id)
    refresh_token = decrypt(user["strava"]["refresh_token"])

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
        )

    token_data = response.json()
    await update_strava_tokens(user_id, token_data)

    return token_data["access_token"]
```

---

## Получение данных атлета

```python
async def fetch_athlete_data(user_id: str) -> dict:
    """
    Получает данные атлета из Strava.

    ВАЖНО:
    - НЕ сохраняем GPS/карты
    - Кэшируем сырые данные max 7 дней
    - Агрегированные метрики можно хранить дольше
    """

    access_token = await get_valid_token(user_id)

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}

        # 1. Статистика атлета
        stats_response = await client.get(
            f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats",
            headers=headers
        )

        # 2. Последние активности (6 месяцев)
        six_months_ago = datetime.now() - timedelta(days=180)
        activities_response = await client.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={
                "after": int(six_months_ago.timestamp()),
                "per_page": 100
            }
        )

    # Агрегируем
    best_efforts = extract_best_efforts(stats_response.json())
    training = aggregate_activities(activities_response.json())

    return {"best_efforts": best_efforts, "training": training}
```

### Извлечение best efforts

```python
def extract_best_efforts(stats: dict) -> dict:
    return {
        "5k": {
            "time_seconds": stats.get("best_5k", {}).get("elapsed_time"),
            "date": stats.get("best_5k", {}).get("start_date")
        },
        "10k": {
            "time_seconds": stats.get("best_10k", {}).get("elapsed_time"),
            "date": stats.get("best_10k", {}).get("start_date")
        },
        "half_marathon": {
            "time_seconds": stats.get("best_half_marathon", {}).get("elapsed_time"),
            "date": stats.get("best_half_marathon", {}).get("start_date")
        },
        "marathon": {
            "time_seconds": stats.get("best_marathon", {}).get("elapsed_time"),
            "date": stats.get("best_marathon", {}).get("start_date")
        }
    }
```

---

## Rate Limiting

### Лимиты Strava API

| Лимит | Значение |
|-------|----------|
| Short (15 min) | 200 запросов |
| Daily | 2000 запросов |
| Developer Program | 30000/day |

### In-memory Rate Limiter (MVP)

```python
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class InMemoryRateLimiter:
    """Rate limiter без Redis для MVP"""

    def __init__(self):
        self.short_counts = defaultdict(list)  # user_id -> timestamps
        self.daily_counts = defaultdict(int)
        self.daily_date = datetime.now().date()
        self._lock = asyncio.Lock()

    async def check_and_increment(self, user_id: str) -> bool:
        async with self._lock:
            now = datetime.now()

            # Reset daily counter if new day
            if now.date() != self.daily_date:
                self.daily_counts.clear()
                self.daily_date = now.date()

            # Clean old timestamps (>15 min)
            cutoff = now - timedelta(minutes=15)
            self.short_counts[user_id] = [
                ts for ts in self.short_counts[user_id]
                if ts > cutoff
            ]

            # Check limits
            if len(self.short_counts[user_id]) >= 200:
                return False
            if self.daily_counts[user_id] >= 2000:
                return False

            # Increment
            self.short_counts[user_id].append(now)
            self.daily_counts[user_id] += 1

            return True
```

---

## Webhooks

### Создание подписки

```python
async def create_webhook_subscription():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/api/v3/push_subscriptions",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "callback_url": f"{BASE_URL}/api/strava/webhook",
                "verify_token": WEBHOOK_VERIFY_TOKEN
            }
        )
    return response.json()
```

### Верификация endpoint

```python
@router.get("/api/strava/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
        return {"hub.challenge": hub_challenge}
    return Response(status_code=403)
```

### Обработка событий

```python
class StravaWebhookEvent(BaseModel):
    object_type: str      # "activity" | "athlete"
    object_id: int
    aspect_type: str      # "create" | "update" | "delete"
    owner_id: int         # Strava athlete ID
    subscription_id: int
    event_time: int

@router.post("/api/strava/webhook")
async def handle_webhook(event: StravaWebhookEvent):
    # Отвечаем быстро (< 2 сек)
    asyncio.create_task(process_webhook_event(event))
    return {"status": "ok"}

async def process_webhook_event(event: StravaWebhookEvent):
    user = await get_user_by_strava_id(event.owner_id)
    if not user:
        return

    if event.object_type == "activity" and event.aspect_type == "create":
        await invalidate_athlete_metrics_cache(user["id"])

    elif event.aspect_type == "deauthorize":
        await handle_deauthorization(user["id"])
```

---

## API Agreement ограничения

### Что МОЖНО

- Получать best efforts пользователя
- Агрегировать тренировочные метрики
- Хранить агрегированные данные бессрочно
- Показывать прогнозы пользователю

### Что НЕЛЬЗЯ

- Хранить GPS координаты и карты
- Кэшировать сырые данные > 7 дней
- Использовать данные для ML на других пользователях
- Агрегировать данные между пользователями
- Искать "похожих атлетов" по Strava данным

### Privacy Compliance

```python
async def handle_deauthorization(user_id: str):
    """Пользователь отозвал доступ в Strava"""

    # Удаляем токены
    await delete_strava_tokens(user_id)

    # Удаляем кэш Strava данных
    await delete_strava_cache(user_id)

    # Помечаем что Strava отключён
    await update_user_strava_status(user_id, connected=False)
```

---

## Privacy Policy требования

### Обязательные пункты

1. **Какие данные получаем:**
   - Best efforts на стандартных дистанциях
   - Агрегированные метрики активностей

2. **Что НЕ получаем:**
   - GPS координаты
   - Карты маршрутов
   - Данные сегментов

3. **Сроки хранения:**
   - Кэш Strava данных: до 7 дней
   - Агрегированные метрики: пока подключён Strava

4. **Права пользователя:**
   - Отключить Strava в любой момент
   - Удалить все данные
   - Запросить копию данных

---

## Чеклист перед релизом

```
□ OAuth flow работает
□ Токены зашифрованы
□ Rate limiting настроен
□ Webhooks подписка создана
□ Privacy Policy опубликована
□ Consent screen готов
□ Кнопка "Отключить Strava" работает
□ 7-day TTL на кэш настроен
□ Deauthorization webhook обрабатывается
□ Strava Developer Program approval получен
```
