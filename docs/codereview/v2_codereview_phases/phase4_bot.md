# Phase 4: Bot Cleanup

> **Статус:** Не начато
> **Оценка:** ~300 строк изменений
> **Зависимости:** Phase 6 (API должен быть стабилен)
> **Ветка:** `refactor/phase-4-bot`
> **Цель:** Устранить дублирование в боте, разбить api_client.py

---

## Проблемы

1. **Дублирование форматтеров:**
   - `format_time()` в `prediction.py` и `trail_run.py`
   - `format_pace()` в `profile.py` и `trail_run.py`

2. **api_client.py — 907 строк!**

3. **Keyboards в handlers/strava.py** вместо keyboards/

4. **Дублирование Strava keyboards** в `handlers/strava.py` и `keyboards/onboarding.py`

---

## Задачи

### 4.1 Создать bot/utils/

**`bot/utils/__init__.py`:**
```python
from .formatters import format_time, format_pace, format_distance, format_elevation
from .callbacks import CallbackPrefix

__all__ = [
    "format_time",
    "format_pace",
    "format_distance",
    "format_elevation",
    "CallbackPrefix",
]
```

**`bot/utils/formatters.py`:**
```python
"""
Форматтеры для отображения данных в боте.

Единственный источник истины — НЕ дублировать в handlers!
"""


def format_time(hours: float) -> str:
    """
    Format hours as 'Xч Yмин'.

    Args:
        hours: Time in hours (e.g., 2.5)

    Returns:
        Formatted string (e.g., '2ч 30мин')
    """
    if hours < 0:
        return "—"

    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60

    if h == 0:
        return f"{m}мин"
    elif m == 0:
        return f"{h}ч"
    else:
        return f"{h}ч {m}мин"


def format_pace(pace_min_km: float | None) -> str:
    """
    Format pace as 'M:SS мин/км'.

    Args:
        pace_min_km: Pace in minutes per km (e.g., 6.5)

    Returns:
        Formatted string (e.g., '6:30 мин/км')
    """
    if pace_min_km is None:
        return "—"

    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)

    return f"{minutes}:{seconds:02d} мин/км"


def format_distance(km: float) -> str:
    """
    Format distance in km.

    Args:
        km: Distance in kilometers

    Returns:
        Formatted string (e.g., '12.5 км')
    """
    if km < 1:
        return f"{int(km * 1000)} м"
    return f"{km:.1f} км"


def format_elevation(meters: float) -> str:
    """
    Format elevation in meters.

    Args:
        meters: Elevation in meters

    Returns:
        Formatted string (e.g., '+850 м' or '-120 м')
    """
    if meters >= 0:
        return f"+{int(meters)} м"
    return f"{int(meters)} м"
```

**`bot/utils/callbacks.py`:**
```python
"""
Callback data prefixes для inline keyboards.

Формат: {prefix}:{action}:{param}
Пример: st:sync:123456
"""


class CallbackPrefix:
    """Префиксы для callback data."""

    ONBOARDING = "ob"      # Onboarding flow
    PREDICTION = "pr"      # Hiking prediction
    TRAIL_RUN = "tr"       # Trail run prediction
    STRAVA = "st"          # Strava integration
    PROFILE = "pf"         # Profile management
    ACTIVITIES = "act"     # Strava activities


# Примеры использования:
# f"{CallbackPrefix.STRAVA}:sync"
# f"{CallbackPrefix.PREDICTION}:experience:beginner"
# f"{CallbackPrefix.TRAIL_RUN}:gap:strava"
```

### 4.2 Разбить api_client.py (907 строк!)

Новая структура:
```
bot/services/
├── __init__.py
├── clients/
│   ├── __init__.py
│   ├── base.py           # BaseAPIClient (~100 строк)
│   ├── hiking.py         # HikingClient (~150 строк)
│   ├── trail_run.py      # TrailRunClient (~100 строк)
│   ├── strava.py         # StravaClient (~200 строк)
│   ├── users.py          # UsersClient (~150 строк)
│   └── gpx.py            # GPXClient (~100 строк)
└── notifications.py      # Без изменений
```

**`bot/services/clients/base.py`:**
```python
"""Base API client with common HTTP logic."""
import httpx
from typing import Any


class BaseAPIClient:
    """Base class for API clients."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    async def _get(self, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
```

**`bot/services/clients/hiking.py`:**
```python
"""Hiking prediction API client."""
from .base import BaseAPIClient
from dataclasses import dataclass


@dataclass
class HikePrediction:
    estimated_time: float
    safe_time: float
    # ... other fields


class HikingClient(BaseAPIClient):
    """Client for hiking prediction endpoints."""

    async def predict(
        self,
        gpx_id: str,
        telegram_id: str,
        experience: str,
        backpack: str,
        group_size: int,
        **kwargs
    ) -> HikePrediction:
        """Make hiking prediction."""
        data = await self._post(
            "/api/v1/predict/hike",
            json={
                "gpx_id": gpx_id,
                "telegram_id": telegram_id,
                "experience": experience,
                "backpack": backpack,
                "group_size": group_size,
                **kwargs
            }
        )
        return HikePrediction(**data)

    async def compare_methods(self, gpx_id: str, **kwargs) -> dict:
        """Compare prediction methods."""
        return await self._post(
            "/api/v1/predict/compare",
            json={"gpx_id": gpx_id, **kwargs}
        )
```

**`bot/services/clients/__init__.py`:**
```python
"""API clients for backend communication."""
from .base import BaseAPIClient
from .hiking import HikingClient
from .trail_run import TrailRunClient
from .strava import StravaClient
from .users import UsersClient
from .gpx import GPXClient


class APIClient:
    """Unified API client with all sub-clients."""

    def __init__(self, base_url: str):
        self.hiking = HikingClient(base_url)
        self.trail_run = TrailRunClient(base_url)
        self.strava = StravaClient(base_url)
        self.users = UsersClient(base_url)
        self.gpx = GPXClient(base_url)

    async def close(self):
        await self.hiking.close()
        await self.trail_run.close()
        await self.strava.close()
        await self.users.close()
        await self.gpx.close()


__all__ = ["APIClient", "HikingClient", "TrailRunClient", "StravaClient", "UsersClient", "GPXClient"]
```

### 4.3 Переместить Strava keyboards

Создать `bot/keyboards/strava.py`:
```python
"""Keyboards for Strava integration."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.callbacks import CallbackPrefix


def get_strava_connect_keyboard(auth_url: str) -> InlineKeyboardMarkup:
    """Keyboard with Strava connect button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 Подключить Strava",
            url=auth_url
        )]
    ])


def get_strava_connected_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for connected Strava account."""
    prefix = CallbackPrefix.STRAVA
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data=f"{prefix}:stats")],
        [InlineKeyboardButton(text="🏃 Мои активности", callback_data=f"{prefix}:activities")],
        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data=f"{prefix}:sync")],
        [InlineKeyboardButton(text="❌ Отключить Strava", callback_data=f"{prefix}:disconnect")]
    ])


def get_confirm_disconnect_keyboard() -> InlineKeyboardMarkup:
    """Keyboard to confirm Strava disconnect."""
    prefix = CallbackPrefix.STRAVA
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отключить", callback_data=f"{prefix}:confirm_disconnect"),
            InlineKeyboardButton(text="Отмена", callback_data=f"{prefix}:cancel")
        ]
    ])


def get_activities_keyboard(
    has_more: bool,
    offset: int,
    activity_type: str | None
) -> InlineKeyboardMarkup:
    """Keyboard for activities list with filters and pagination."""
    prefix = CallbackPrefix.ACTIVITIES
    buttons = []

    # Filters row
    filters = []
    for filter_type, label in [("run", "🏃 Бег"), ("hike", "🥾 Поход"), ("all", "Все")]:
        is_active = activity_type == filter_type or (filter_type == "all" and not activity_type)
        text = f"• {label}" if is_active else label
        filters.append(InlineKeyboardButton(
            text=text,
            callback_data=f"{prefix}:filter:{filter_type}"
        ))
    buttons.append(filters)

    # Pagination
    if has_more:
        buttons.append([
            InlineKeyboardButton(
                text="Показать ещё →",
                callback_data=f"{prefix}:more:{offset}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

### 4.4 Обновить handlers

Удалить дублирование из handlers, использовать `bot/utils/`:

```python
# Было (в каждом handler)
def format_time(hours: float) -> str:
    ...

# Стало
from bot.utils import format_time, format_pace
```

Удалить keyboards из `handlers/strava.py`:
```python
# Было
def get_strava_connected_keyboard():
    ...

# Стало
from bot.keyboards.strava import get_strava_connected_keyboard
```

### 4.5 Обновить keyboards/__init__.py

```python
from .onboarding import *
from .prediction import *
from .profile import *
from .trail_run import *
from .strava import *  # Добавить
```

---

## Файлы для изменения

```
NEW:
bot/utils/__init__.py
bot/utils/formatters.py
bot/utils/callbacks.py
bot/services/clients/__init__.py
bot/services/clients/base.py
bot/services/clients/hiking.py
bot/services/clients/trail_run.py
bot/services/clients/strava.py
bot/services/clients/users.py
bot/services/clients/gpx.py
bot/keyboards/strava.py

DELETE:
bot/services/api_client.py (после переноса)

UPDATE:
bot/keyboards/__init__.py (add strava)
bot/handlers/prediction.py (use formatters, new api_client)
bot/handlers/trail_run.py (use formatters, new api_client)
bot/handlers/profile.py (use formatters, new api_client)
bot/handlers/strava.py (remove keyboards, use formatters, new api_client)
bot/handlers/onboarding.py (use new api_client)
bot/services/__init__.py
```

---

## Критерии завершения

- [x] `bot/utils/formatters.py` создан
- [x] `bot/utils/callbacks.py` создан
- [x] `api_client.py` разбит на `clients/*.py`
- [x] Keyboards вынесены из `handlers/strava.py`
- [x] Нет дублирования `format_time`, `format_pace`
- [x] Бот работает

---

*Phase 4 — Bot Cleanup*
