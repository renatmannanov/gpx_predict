# Шаг 0: Выравнивание типов БД перед кросс-сервисной интеграцией

## Цель

Привести типы `telegram_id` и `strava_athlete_id` к `BigInteger` для совместимости с ayda_run и корректности (это числа, не строки).

## Что менять

### 1. Модели SQLAlchemy

| Файл | Поле | Было | Станет |
|------|------|------|--------|
| `backend/app/features/users/models.py:28` | `telegram_id` | `String(20)` | `BigInteger` |
| `backend/app/features/users/models.py:36` | `strava_athlete_id` | `String(20)` | `BigInteger` |
| `backend/app/features/strava/models.py:34` | `strava_athlete_id` | `String(20)` | `BigInteger` |

### 2. Pydantic схемы

| Файл | Поле | Было | Станет |
|------|------|------|--------|
| `backend/app/features/users/schemas.py:15` | `telegram_id` | `Optional[str]` | `Optional[int]` |
| `backend/app/features/users/schemas.py:24` | `telegram_id` | `Optional[str]` | `Optional[int]` |
| `backend/app/api/v1/routes/users.py:22` | `telegram_id` | `str` | `int` (UserInfoSchema) |

### 3. Repository type hints

| Файл | Метод | Было | Станет |
|------|-------|------|--------|
| `backend/app/features/users/repository.py:21` | `get_by_telegram_id` | `telegram_id: str` | `telegram_id: int` |
| `backend/app/features/users/repository.py:33` | `get_with_profiles` | `telegram_id: str` | `telegram_id: int` |
| `backend/app/features/users/repository.py:53` | `get_or_create` | `telegram_id: str` | `telegram_id: int` |
| `backend/app/features/users/repository.py:74` | `update_strava_connection` | `athlete_id: str` | `athlete_id: int` |
| `backend/app/features/strava/repository.py:34` | `get_by_athlete_id` | `athlete_id: str` | `athlete_id: int` |

### 4. API route параметры

| Файл | Параметр | Было | Станет |
|------|----------|------|--------|
| `backend/app/api/v1/routes/users.py` | path param `telegram_id` (6 мест) | `str` | `int` |
| `backend/app/api/v1/routes/notifications.py` | path param `telegram_id` (3 места) | `str` | `int` |
| `backend/app/api/v1/routes/profiles.py` | path param `telegram_id` (5 мест) | `str` | `int` |
| `backend/app/api/v1/routes/strava.py` | query param `telegram_id` | `str` | `int` |
| `backend/app/api/v1/routes/predict.py:50` | `telegram_id` в CompareRequest | `Optional[str]` | `Optional[int]` |
| `backend/app/api/v1/routes/races.py:99` | `telegram_id` в PredictRequest | `Optional[str]` | `Optional[int]` |

### 5. Bot handlers — убрать str()

| Файл | Строка | Было | Станет |
|------|--------|------|--------|
| `bot/handlers/common.py:39` | `telegram_id = str(message.from_user.id)` | `str(...)` | просто `message.from_user.id` |
| `bot/handlers/onboarding.py:290` | `telegram_id = str(callback.from_user.id)` | `str(...)` | `callback.from_user.id` |
| `bot/handlers/onboarding.py:373` | `telegram_id = str(callback.from_user.id)` | `str(...)` | `callback.from_user.id` |
| `bot/handlers/prediction.py:297` | `telegram_id = str(callback.from_user.id)` | `str(...)` | `callback.from_user.id` |
| `bot/handlers/prediction.py:421` | `telegram_id = str(callback.from_user.id)` | `str(...)` | `callback.from_user.id` |
| Другие handlers | аналогично | `str(...)` | убрать |

### 6. Bot API clients — type hints

| Файл | Параметр | Было | Станет |
|------|----------|------|--------|
| `bot/services/clients/strava.py:60` | `telegram_id: str` | `str` | `int` |
| `bot/services/clients/users.py` | `telegram_id: str` (5 методов) | `str` | `int` |
| `bot/services/clients/profiles.py` | `telegram_id: str` (4 метода) | `str` | `int` |
| `bot/services/clients/hiking.py:50` | `telegram_id: Optional[str]` | `Optional[str]` | `Optional[int]` |
| `bot/services/notifications.py:23` | `telegram_id: str` | `str` | `int` |
| `bot/services/clients/__init__.py:61` | `telegram_id: str` | `str` | `int` |

### 7. Alembic миграция

Создать новую миграцию:
```python
# Change telegram_id and strava_athlete_id from String to BigInteger
op.alter_column('users', 'telegram_id', type_=sa.BigInteger(), postgresql_using='telegram_id::bigint')
op.alter_column('users', 'strava_athlete_id', type_=sa.BigInteger(), postgresql_using='strava_athlete_id::bigint')
op.alter_column('strava_tokens', 'strava_athlete_id', type_=sa.BigInteger(), postgresql_using='strava_athlete_id::bigint')
```

## Что НЕ менять

- URL path/query construction (f-strings работают с int автоматически)
- JSON payload construction (JSON нативно поддерживает int)
- Logging (f-strings работают с обоими типами)
- Архитектуру хранения токенов (отдельная таблица strava_tokens — правильнее)
- `expires_at` как unix timestamp — стандарт OAuth
- `strava_connected` как Boolean column — ок

## Порядок реализации

1. Модели SQLAlchemy (3 файла)
2. Alembic миграция
3. Pydantic схемы
4. Repository type hints
5. API route параметры
6. Bot handlers (убрать str())
7. Bot API clients (type hints)

## Критерий готовности

- [ ] Все `telegram_id` и `strava_athlete_id` — BigInteger в моделях
- [ ] Миграция создана
- [ ] Нигде нет `str(message.from_user.id)` или `str(callback.from_user.id)`
- [ ] Type hints обновлены
