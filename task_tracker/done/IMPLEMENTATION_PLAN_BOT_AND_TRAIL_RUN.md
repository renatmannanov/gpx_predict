# План реализации: Bot Onboarding + Trail Running интеграция

**Дата создания:** 2026-01-24
**Статус:** 📋 Готов к реализации
**Приоритет:** Высокий

---

## Обзор

Этот план объединяет две задачи:
1. **Bot Onboarding & Strava Auto-Sync** — полный онбординг для новых пользователей
2. **Trail Running Bot Integration** — интеграция существующего бэкенда trail running в бот

Задачи **независимы** и могут выполняться **параллельно**.

---

## Архитектура изменений

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            BACKEND                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  СУЩЕСТВУЕТ:                          НУЖНО ДОБАВИТЬ:                   │
│  ✅ TrailRunService                   📝 Notification модель            │
│  ✅ GAPCalculator                     📝 GET /notifications/{id}        │
│  ✅ HikeRunThresholdService           📝 User.preferred_activity_type   │
│  ✅ RunnerFatigueService              📝 User.onboarding_complete       │
│  ✅ /predict/trail-run/compare        📝 StravaSyncStatus расширение    │
│  ✅ UserRunProfile                    📝 Авто-создание уведомлений      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BOT                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  СУЩЕСТВУЕТ:                          НУЖНО ДОБАВИТЬ:                   │
│  ✅ handlers/common.py (/start)       📝 handlers/onboarding.py         │
│  ✅ handlers/strava.py                📝 handlers/trail_run.py          │
│  ✅ handlers/prediction.py            📝 handlers/profile.py            │
│  ✅ states/prediction.py              📝 states/onboarding.py           │
│  ✅ keyboards/prediction.py           📝 keyboards/onboarding.py        │
│  ✅ services/api_client.py            📝 keyboards/trail_run.py         │
│                                       📝 services/notifications.py      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Разбивка на части

| Часть | Содержание | Зависимости | Приоритет |
|-------|------------|-------------|-----------|
| **Part A** | Backend: Модели и API для онбординга | - | 🔴 Высокий |
| **Part B** | Bot: Онбординг flow | Part A | 🔴 Высокий |
| **Part C** | Bot: Trail Running интеграция | - | 🔴 Высокий |
| **Part D** | Bot: Уведомления и авто-sync | Part A | 🟡 Средний |
| **Part E** | Обновление prediction flow | Part B, C | 🟡 Средний |

```
        Part A (Backend)
             │
        ┌────┴────┐
        ▼         ▼
    Part B     Part D
  (Onboarding) (Notifications)
        │         │
        └────┬────┘
             ▼
         Part E
  (Updated Prediction)

    Part C (Trail Run)
         │
         ▼
      Part E
```

---

## Part A: Backend — Модели и API для онбординга

### A.1 Обновление модели User

**Файл:** `backend/app/models/user.py`

```python
# Добавить поля:
preferred_activity_type = Column(String(20), nullable=True)  # "hiking" | "running"
onboarding_complete = Column(Boolean, default=False)
```

### A.2 Обновление модели StravaSyncStatus

**Файл:** `backend/app/models/strava_activity.py`

```python
# Добавить поля:
total_activities_estimated = Column(Integer, nullable=True)
activities_with_splits = Column(Integer, default=0)
initial_sync_complete = Column(Boolean, default=False)
```

### A.3 Создание модели Notification

**Файл:** `backend/app/models/notification.py` (НОВЫЙ)

```python
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)  # profile_updated, sync_complete, etc.
    data = Column(JSON, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
```

**Типы уведомлений:**
- `profile_updated` — профиль пересчитан
- `profile_complete` — все 7 категорий заполнены
- `profile_incomplete` — есть пустые категории (с рекомендациями)
- `sync_complete` — синхронизация завершена
- `sync_progress` — прогресс синхронизации (каждые 30 активностей)

### A.4 Миграция 008

**Файл:** `backend/alembic/versions/008_add_onboarding_and_notifications.py`

```python
def upgrade():
    # User fields
    op.add_column('users', sa.Column('preferred_activity_type', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('onboarding_complete', sa.Boolean(), default=False))

    # StravaSyncStatus fields
    op.add_column('strava_sync_status', sa.Column('total_activities_estimated', sa.Integer(), nullable=True))
    op.add_column('strava_sync_status', sa.Column('activities_with_splits', sa.Integer(), default=0))
    op.add_column('strava_sync_status', sa.Column('initial_sync_complete', sa.Boolean(), default=False))

    # Notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )
```

### A.5 API endpoints

**Файл:** `backend/app/api/v1/routes/notifications.py` (НОВЫЙ)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/notifications/{telegram_id}` | GET | Получить непрочитанные уведомления |
| `/notifications/{telegram_id}/read` | POST | Отметить уведомления как прочитанные |
| `/notifications/{telegram_id}/all` | GET | Все уведомления (с пагинацией) |

**Файл:** `backend/app/api/v1/routes/users.py` (обновить)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/users/{telegram_id}/onboarding` | POST | Завершить онбординг |
| `/users/{telegram_id}/preferences` | PUT | Обновить preferred_activity_type |

### A.6 Обновление strava_sync.py

**Логика:**
1. При sync — учитывать `preferred_activity_type` для приоритета загрузки
2. После каждого batch — создавать `Notification` если профиль обновился
3. После завершения sync — создавать `sync_complete` уведомление

---

### Чеклист Part A

- [ ] Добавить поля в User (`preferred_activity_type`, `onboarding_complete`)
- [ ] Добавить поля в StravaSyncStatus
- [ ] Создать модель Notification
- [ ] Создать миграцию 008
- [ ] Создать `routes/notifications.py`
- [ ] Обновить `routes/users.py`
- [ ] Обновить `strava_sync.py` — создание уведомлений
- [ ] Обновить `strava_sync.py` — приоритет по activity_type
- [ ] Тесты для новых endpoints

---

## Part B: Bot — Онбординг flow

### B.1 FSM States

**Файл:** `bot/states/onboarding.py` (НОВЫЙ)

```python
from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    welcome = State()                    # Шаг 1: Приветствие
    selecting_activity = State()         # Шаг 2: Выбор активности
    explaining_personalization = State() # Шаг 3: Объяснение
    offering_strava = State()            # Шаг 4: Предложение Strava
    waiting_strava_callback = State()    # Шаг 5A: Ожидание подключения
    skipped_strava = State()             # Шаг 5B: Пропустили Strava
    showing_usage = State()              # Шаг 6: Как пользоваться
    complete = State()                   # Шаг 7: Завершение
```

### B.2 Keyboards

**Файл:** `bot/keyboards/onboarding.py` (НОВЫЙ)

| Функция | Назначение |
|---------|------------|
| `get_start_keyboard()` | Кнопка "🚀 Начать" |
| `get_activity_keyboard()` | "🥾 Хайкинг" / "🏃 Трейлраннинг" |
| `get_strava_keyboard()` | "🔗 Подключить Strava" / "⏭ Пропустить" |
| `get_continue_keyboard()` | "Далее →" |
| `get_finish_keyboard()` | "🎉 Готово, начать!" |

### B.3 Handler

**Файл:** `bot/handlers/onboarding.py` (НОВЫЙ)

**Функции:**

| Функция | Триггер | Действие |
|---------|---------|----------|
| `start_onboarding()` | FSM welcome | Показать приветствие |
| `handle_activity_selection()` | Callback `activity:*` | Сохранить выбор, объяснить персонализацию |
| `handle_strava_decision()` | Callback `strava:connect/skip` | Подключить или пропустить Strava |
| `handle_strava_callback()` | После OAuth | Показать статус подключения |
| `handle_continue()` | Callback `continue` | Переход к следующему шагу |
| `finish_onboarding()` | Callback `finish` | Сохранить, очистить FSM |

### B.4 Изменение /start

**Файл:** `bot/handlers/common.py` (изменить)

```python
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    telegram_id = str(message.from_user.id)

    # Проверить онбординг
    user_info = await api_client.get_user_info(telegram_id)

    if user_info and user_info.onboarding_complete:
        # Существующий пользователь — старое поведение
        await message.answer("👋 С возвращением! Отправь GPX файл...")
    else:
        # Новый пользователь — запустить онбординг
        await state.set_state(OnboardingStates.welcome)
        await start_onboarding(message, state)
```

### B.5 API Client обновления

**Файл:** `bot/services/api_client.py` (добавить методы)

```python
# Новые dataclasses
@dataclass
class UserInfo:
    telegram_id: str
    onboarding_complete: bool
    preferred_activity_type: Optional[str]
    strava_connected: bool

# Новые методы
async def get_user_info(self, telegram_id: str) -> Optional[UserInfo]
async def complete_onboarding(self, telegram_id: str, activity_type: str) -> bool
async def update_preferences(self, telegram_id: str, activity_type: str) -> bool

# Для /profile
async def get_hike_profile(self, telegram_id: str) -> Optional[HikeProfile]
async def get_run_profile(self, telegram_id: str) -> Optional[RunProfile]
async def recalculate_profile(self, telegram_id: str, profile_type: str) -> bool
```

---

### B.6 Команда /profile

**Файл:** `bot/handlers/profile.py` (НОВЫЙ)

Показывает текущий профиль пользователя с возможностью переключения между hiking и running.

**Команда:** `/profile`

**Логика:**
1. Загрузить оба профиля (hike + run)
2. Показать приоритетный профиль (по `preferred_activity_type`)
3. Дать кнопку для переключения на другой профиль

**Формат вывода для hiking:**
```
📊 Твой профиль хайкера

Проанализировано: 47 активностей (312 сплитов)

┌─────────────────────────────────────────────┐
│  Крутой спуск (<-15%):     9.8 мин/км  (23) │
│  Умеренный спуск:          10.2 мин/км (45) │
│  Пологий спуск:            10.8 мин/км (38) │
│  Ровный участок:           11.2 мин/км (67) │
│  Пологий подъём:           13.5 мин/км (52) │
│  Умеренный подъём:         16.8 мин/км (49) │
│  Крутой подъём (>15%):     21.3 мин/км (38) │
└─────────────────────────────────────────────┘

Вертикальная способность: 0.92
(чуть быстрее среднего на вертикали)

[🏃 Показать профиль бегуна]  [🔄 Пересчитать]
```

**Формат вывода для running:**
```
📊 Твой профиль бегуна

Проанализировано: 35 активностей (187 сплитов)

┌─────────────────────────────────────────────┐
│  Крутой спуск (<-15%):     4.2 мин/км  (12) │
│  Умеренный спуск:          4.5 мин/км  (28) │
│  Пологий спуск:            4.8 мин/км  (31) │
│  Ровный участок:           5.2 мин/км  (45) │
│  Пологий подъём:           6.1 мин/км  (34) │
│  Умеренный подъём:         7.8 мин/км  (25) │
│  Крутой подъём (>15%):     12.5 мин/км (12) │
└─────────────────────────────────────────────┘

Порог перехода на шаг: 22%
(на подъёмах круче 22% ты переходишь на шаг)

[🥾 Показать профиль хайкера]  [🔄 Пересчитать]
```

**Если профиль пустой:**
```
📊 Профиль бегуна

❌ Нет данных для профиля

Для персонализации нужно:
1. Подключить Strava (/strava)
2. Иметь хотя бы 1 Run/TrailRun активность
3. Дождаться синхронизации

[🔗 Подключить Strava]
```

**Keyboards:**
```python
def get_profile_keyboard(current_type: str, has_other_profile: bool):
    """Клавиатура для /profile."""
    buttons = []
    if current_type == "hiking" and has_other_profile:
        buttons.append(InlineKeyboardButton(text="🏃 Профиль бегуна", callback_data="profile:running"))
    elif current_type == "running" and has_other_profile:
        buttons.append(InlineKeyboardButton(text="🥾 Профиль хайкера", callback_data="profile:hiking"))
    buttons.append(InlineKeyboardButton(text="🔄 Пересчитать", callback_data="profile:recalculate"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
```

---

### Чеклист Part B

- [ ] Создать `states/onboarding.py`
- [ ] Создать `keyboards/onboarding.py`
- [ ] Создать `handlers/onboarding.py`
- [ ] Реализовать шаги 1-7 онбординга
- [ ] Изменить `/start` в `handlers/common.py`
- [ ] Создать `handlers/profile.py` с командой /profile
- [ ] Добавить методы в `api_client.py`
- [ ] Зарегистрировать роутеры в `main.py`
- [ ] Тестирование flow

---

## Part C: Bot — Trail Running интеграция

### C.1 FSM States

**Файл:** `bot/states/trail_run.py` (НОВЫЙ)

```python
class TrailRunStates(StatesGroup):
    waiting_for_gpx = State()
    selecting_route_type = State()      # oneway/roundtrip
    selecting_gap_mode = State()        # strava_gap/minetti_gap (опционально)
    selecting_flat_pace = State()       # Если нет профиля
    confirming = State()
```

### C.2 Keyboards

**Файл:** `bot/keyboards/trail_run.py` (НОВЫЙ)

| Функция | Назначение |
|---------|------------|
| `get_gap_mode_keyboard()` | "Strava GAP" / "Minetti GAP" / "Авто" |
| `get_flat_pace_keyboard()` | Предустановленные темпы (5:00, 5:30, 6:00, ...) |
| `get_fatigue_keyboard()` | "С учётом усталости" / "Без усталости" |

### C.3 Handler

**Файл:** `bot/handlers/trail_run.py` (НОВЫЙ)

**Функции:**

| Функция | Триггер | Действие |
|---------|---------|----------|
| `handle_trail_run_gpx()` | GPX файл + activity_type=trail_run | Загрузить GPX |
| `handle_route_type()` | Callback `rt:*` | Сохранить тип маршрута |
| `handle_gap_mode()` | Callback `gap:*` | Выбор режима GAP |
| `handle_flat_pace()` | Callback `pace:*` | Ввод темпа (если нет профиля) |
| `calculate_trail_run()` | После всех выборов | Вызов API, форматирование |

### C.4 Форматирование результата

```
🏃 Прогноз Trail Run: {route_name}

📍 Маршрут: {distance} км, D+ {elevation}м

⏱ Время:
  • Strava GAP: {time}
  • С вашим темпом: {personalized_time} 🎯

📊 Разбивка:
  • Бег: {run_distance} км ({run_time})
  • Ходьба: {hike_distance} км ({hike_time})
  • Порог ходьбы: {threshold}%

💪 Влияние рельефа: +{elevation_impact}% к плоскому времени

{fatigue_info если применено}
```

### C.5 API Client обновления

**Файл:** `bot/services/api_client.py` (добавить)

```python
@dataclass
class TrailRunPrediction:
    totals: Dict[str, float]           # strava_gap, minetti_gap, etc.
    summary: Dict[str, Any]            # distance, elevation, running_time, hiking_time
    personalized: bool
    walk_threshold_used: float
    gap_mode: str
    fatigue_applied: bool
    fatigue_info: Optional[Dict]

async def predict_trail_run(
    self,
    gpx_id: str,
    telegram_id: str,
    gap_mode: str = "strava_gap",
    flat_pace_min_km: Optional[float] = None,
    apply_fatigue: bool = False,
    walk_threshold_override: Optional[float] = None
) -> TrailRunPrediction
```

---

### Чеклист Part C

- [ ] Создать `states/trail_run.py`
- [ ] Создать `keyboards/trail_run.py`
- [ ] Создать `handlers/trail_run.py`
- [ ] Реализовать flow расчёта trail run
- [ ] Добавить форматирование результата
- [ ] Добавить `predict_trail_run()` в api_client
- [ ] Зарегистрировать роутер в main.py
- [ ] Тестирование

---

## Part D: Bot — Уведомления

### D.1 Сервис уведомлений

**Файл:** `bot/services/notifications.py` (НОВЫЙ)

```python
class NotificationService:
    """Polling-based notification service."""

    async def check_notifications(self, telegram_id: str) -> List[Notification]:
        """Проверить непрочитанные уведомления."""
        pass

    async def format_notification(self, notification: Notification) -> str:
        """Форматировать уведомление для отображения."""
        pass

    async def mark_as_read(self, telegram_id: str, notification_ids: List[int]):
        """Отметить как прочитанные."""
        pass
```

### D.2 Интеграция в handlers

**Где вызывать `check_notifications()`:**

1. **В начале любого handler'а** (middleware подход):
   ```python
   @router.message()
   async def any_message(message: Message):
       # Сначала проверяем уведомления
       notifications = await notification_service.check_notifications(telegram_id)
       if notifications:
           await show_notifications(message, notifications)
   ```

2. **В команде `/start`** — после проверки онбординга

3. **После загрузки GPX** — перед показом результата

### D.3 Форматирование уведомлений

```
📊 Обновление профиля

Загружено: 35 активностей
Проанализировано: 187 сплитов

🏃 Профиль бегуна обновлён:
┌────────────────────────────┐
│ Ровный:      5.8 мин/км    │
│ Лёгкий подъём: 6.9 мин/км  │
│ Крутой подъём: 9.2 мин/км  │
│ Порог ходьбы: 24%          │
└────────────────────────────┘

Теперь прогнозы trail run персонализированы!
```

---

### Чеклист Part D

- [ ] Создать `services/notifications.py`
- [ ] Добавить проверку в key handlers
- [ ] Форматирование разных типов уведомлений
- [ ] Отметка как прочитанные
- [ ] API клиент для notifications

---

## Part E: Обновление Prediction Flow

### E.1 Добавить выбор типа активности

**Файл:** `bot/handlers/prediction.py` (изменить)

После загрузки GPX — спросить тип активности:

```
Какой прогноз нужен?

[🥾 Хайкинг]  [🏃 Трейлраннинг]
```

### E.2 Изменить flow в зависимости от типа

**Hiking flow (существующий):**
```
GPX → Тип активности → Тип маршрута → Опыт → Рюкзак → Группа → Дети → Пожилые → РЕЗУЛЬТАТ
```

**Trail Run flow (новый):**
```
GPX → Тип активности → Тип маршрута → (Темп если нет профиля) → РЕЗУЛЬТАТ
```

### E.3 Использовать preferred_activity_type

Если пользователь уже выбрал тип в онбординге — предзаполнить выбор:

```python
user_info = await api_client.get_user_info(telegram_id)
if user_info.preferred_activity_type == "running":
    # По умолчанию выбрать Trail Run
    # Но дать возможность переключить
```

### E.4 Пропускать вопросы при персонализации

**Для Hiking:**
- Пропустить "Опыт" если есть hike_profile

**Для Trail Run:**
- Пропустить "Темп" если есть run_profile
- Автоматически использовать walk_threshold из профиля

---

### Чеклист Part E

- [ ] Добавить выбор типа активности после GPX
- [ ] Разветвить flow: hiking vs trail_run
- [ ] Интегрировать `handlers/trail_run.py`
- [ ] Использовать `preferred_activity_type` для дефолтов
- [ ] Пропускать вопросы при наличии профиля
- [ ] Тестирование обоих flows

---

## Структура файлов после реализации

```
bot/
├── config.py
├── main.py                           # Обновить: регистрация роутеров
│
├── handlers/
│   ├── __init__.py
│   ├── common.py                     # ИЗМЕНИТЬ: /start → проверка онбординга
│   ├── strava.py                     # Без изменений
│   ├── prediction.py                 # ИЗМЕНИТЬ: выбор типа активности
│   ├── onboarding.py                 # НОВЫЙ: flow онбординга
│   ├── trail_run.py                  # НОВЫЙ: trail running prediction
│   └── profile.py                    # НОВЫЙ: /profile команда (hike + run профили)
│
├── states/
│   ├── __init__.py
│   ├── prediction.py                 # Без изменений
│   ├── onboarding.py                 # НОВЫЙ
│   └── trail_run.py                  # НОВЫЙ
│
├── keyboards/
│   ├── __init__.py
│   ├── prediction.py                 # ИЗМЕНИТЬ: добавить activity_type
│   ├── onboarding.py                 # НОВЫЙ
│   └── trail_run.py                  # НОВЫЙ
│
└── services/
    ├── __init__.py
    ├── api_client.py                 # ИЗМЕНИТЬ: новые методы
    └── notifications.py              # НОВЫЙ

backend/app/
├── models/
│   ├── user.py                       # ИЗМЕНИТЬ: новые поля
│   ├── strava_activity.py            # ИЗМЕНИТЬ: StravaSyncStatus поля
│   └── notification.py               # НОВЫЙ
│
├── api/v1/routes/
│   ├── notifications.py              # НОВЫЙ
│   └── users.py                      # ИЗМЕНИТЬ
│
├── services/
│   └── strava_sync.py                # ИЗМЕНИТЬ: уведомления, приоритет
│
└── alembic/versions/
    └── 008_add_onboarding_and_notifications.py  # НОВЫЙ
```

---

## Порядок реализации

### Фаза 1: Подготовка (можно параллельно)

| Задача | Зависимости | Исполнитель |
|--------|-------------|-------------|
| Part A: Backend модели и миграция | - | Backend |
| Part C: Trail Run handlers (без интеграции) | - | Bot |

### Фаза 2: Основной функционал

| Задача | Зависимости | Исполнитель |
|--------|-------------|-------------|
| Part A: API endpoints | Part A миграция | Backend |
| Part B: Онбординг flow | Part A API | Bot |
| Part C: Trail Run интеграция | - | Bot |

### Фаза 3: Интеграция

| Задача | Зависимости | Исполнитель |
|--------|-------------|-------------|
| Part D: Уведомления | Part A, B | Bot |
| Part E: Unified prediction flow | Part B, C | Bot |

### Фаза 4: Тестирование и документация

| Задача | Зависимости |
|--------|-------------|
| E2E тесты онбординга | Part B |
| E2E тесты trail run | Part C |
| E2E тесты уведомлений | Part D |
| Обновить ARCHITECTURE.md | All |

---

## Оценка объёма

| Часть | Новые файлы | Изменённые файлы | Сложность |
|-------|-------------|------------------|-----------|
| Part A | 2 | 4 | Средняя |
| Part B | 3 | 2 | Высокая |
| Part C | 3 | 1 | Средняя |
| Part D | 1 | 2 | Низкая |
| Part E | 0 | 2 | Средняя |
| **Итого** | **9** | **11** | - |

---

## Критические замечания и корректировки к исходному плану

### 1. Разделение профилей ✅ УЖЕ СДЕЛАНО

**Исходный план (BOT_ONBOARDING):** предлагал переименовать `user_performance_profiles` → `user_hike_profiles`

**Текущее состояние:**
- `user_performance_profiles` — уже существует и работает для hiking
- `user_run_profiles` — уже создана в миграции 007 (из TRAIL_RUNNING_PART2)

**Решение:** Оставить как есть, разделение уже выполнено:
- `user_performance_profiles` → для hiking (модель `UserPerformanceProfile`)
- `user_run_profiles` → для running (модель `UserRunProfile`)

Не нужно переименовывать таблицы — это сломает обратную совместимость без реальной пользы.

### 2. API endpoint для Trail Run

**Исходный план (TRAIL_RUNNING_PART3):** Расширить `/predict/compare` с `activity_type`

**Текущий статус:** Уже создан отдельный `/predict/trail-run/compare`

**Решение:** Использовать существующий endpoint, не переделывать.

### 3. Уведомления

**Исходный план:** Polling + webhook как опции.

**Выбор пользователя:** Polling при взаимодействии.

**Реализация:** Проверять уведомления в начале каждого значимого handler'а, не создавать отдельный background task.

### 4. Текст онбординга

**Исходный план:** Много текста с эмодзи и форматированием.

**Решение:** Оставить эмодзи только для функциональных элементов:
- Иконок типов активности (🥾 🏃)
- Статусов (✅ ⚠️ ❌)
- Ключевых акцентов (📊 🎯 💡)

Тексты оставить как в BOT_ONBOARDING_AND_SYNC.md — редактировать после просмотра в Telegram.

---

## Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Strava rate limits при массовой регистрации | Средняя | Очередь с приоритетом, batch processing |
| Пользователь не завершает онбординг | Высокая | Напоминание через /start, возможность продолжить |
| Конфликт FSM состояний | Низкая | Чёткое разделение states groups |
| Медленная синхронизация Strava | Средняя | Уведомления о прогрессе, асинхронность |

---

## Языки интерфейса

**Текущий этап:** Только русский язык.

Все тексты бота (онбординг, уведомления, результаты) — на русском.

---

## Следующие шаги после этого плана

1. **Weather impact** — учёт погодных условий
2. **Terrain crowdsourcing** — данные о сложности участков от пользователей
3. **Push notifications** — переход на webhook для мгновенных уведомлений
4. **Multi-language** — поддержка английского языка

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2026-01-24 | Создан начальный план на основе BOT_ONBOARDING_AND_SYNC.md и TRAIL_RUNNING_* |
