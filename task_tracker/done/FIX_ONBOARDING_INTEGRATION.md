# План исправления ошибок интеграции Onboarding & Trail Run

**Дата:** 2026-01-24
**Статус:** ✅ Исправлено
**Приоритет:** Критический

---

## Контекст

Предыдущий агент реализовал онбординг и trail run интеграцию по планам:
- `docs/todo/BOT_ONBOARDING_AND_SYNC.md` (663 строки)
- `docs/todo/IMPLEMENTATION_PLAN_BOT_AND_TRAIL_RUN.md` (805 строк)

Были допущены ошибки интеграции — компоненты созданы, но не подключены.

---

## Исправление 1: Показ уведомлений пользователю

**Проблема:** `NotificationService` создан, но никогда не вызывается.

**Файлы:**
- `bot/services/notifications.py` — сервис уже есть
- `bot/handlers/common.py` — добавить проверку

**Что сделать:**

1. В `bot/handlers/common.py` добавить импорт:
```python
from services.notifications import notification_service
```

2. В функции `cmd_start` после проверки онбординга добавить:
```python
# После строки 46 (await message.answer(WELCOME_BACK_TEXT...))
await notification_service.check_and_show_notifications(message, telegram_id)
```

3. Опционально: добавить проверку в `bot/handlers/prediction.py` после загрузки GPX (после строки 310).

---

## Исправление 2: Уведомление о подключении Strava в онбординге

**Проблема:** `notify_strava_connected()` создана, но не вызывается из strava callback.

**Файлы:**
- `bot/handlers/onboarding.py:305-318` — функция есть
- `bot/handlers/strava.py` — нужно добавить вызов

**Что сделать:**

1. Найти в `bot/handlers/strava.py` callback handler для Strava OAuth (функция обработки после редиректа).

2. Добавить импорт:
```python
from handlers.onboarding import notify_strava_connected
from states.onboarding import OnboardingStates
```

3. В callback handler добавить проверку состояния и вызов:
```python
# После успешного подключения Strava
current_state = await state.get_state()
if current_state == OnboardingStates.offering_strava.state:
    await notify_strava_connected(message, state)
```

---

## Исправление 3: Пропуск вопроса "Опыт" при персонализации

**Проблема:** Вопрос об опыте задаётся всегда, даже если есть профиль.

**Файл:** `bot/handlers/prediction.py`

**Что сделать:**

1. В `handle_activity_type` (строка ~347) после выбора hiking добавить проверку:

```python
# Вместо безусловного перехода к experience
telegram_id = str(callback.from_user.id)
hike_profile = await api_client.get_hike_profile(telegram_id)
has_profile = hike_profile and hike_profile.get("avg_flat_pace_min_km")

if has_profile:
    # Пропускаем вопрос об опыте, переходим к рюкзаку
    await state.update_data(experience="personalized")  # маркер
    await callback.message.edit_text(
        "Какой вес рюкзака?",
        reply_markup=get_backpack_keyboard()
    )
    await state.set_state(PredictionStates.selecting_backpack)
else:
    # Стандартный flow
    await callback.message.edit_text(
        "Какой у тебя опыт походов?",
        reply_markup=get_experience_keyboard()
    )
    await state.set_state(PredictionStates.selecting_experience)
```

---

## Исправление 4: Использование PROGRESS_NOTIFICATION_INTERVAL

**Проблема:** Константа создана, но не используется.

**Файл:** `backend/app/services/strava_sync.py`

**Что сделать:**

1. В методе `sync_user_activities` (после строки 241) добавить:

```python
# После sync_status.total_activities_synced += saved_count
# Проверяем нужно ли отправить уведомление о прогрессе
if (sync_status.total_activities_synced % SyncConfig.PROGRESS_NOTIFICATION_INTERVAL == 0
    and not sync_status.initial_sync_complete):
    self._create_notification(
        user_id=user_id,
        notification_type="sync_progress",
        data={
            "progress_percent": int(
                (sync_status.total_activities_synced /
                 (sync_status.total_activities_estimated or 100)) * 100
            ),
            "activities_synced": sync_status.total_activities_synced,
            "total_estimated": sync_status.total_activities_estimated or 0
        }
    )
```

---

## Исправление 5: recalculate_profile с учётом типа

**Проблема:** Всегда пересчитывает hiking профиль.

**Файл:** `bot/handlers/profile.py`

**Что сделать:**

1. В `handle_profile_callback` (строка ~223) изменить:

```python
if action == "recalculate":
    # Определить текущий тип профиля из контекста
    # Нужно сохранить current_type в callback_data или state

    # Временное решение: определить по тексту сообщения
    current_text = callback.message.text or ""
    profile_type = "running" if "бегуна" in current_text else "hiking"

    result = await api_client.recalculate_profile(telegram_id, profile_type)
```

2. Лучшее решение: изменить callback_data на `profile:recalculate:hiking` и `profile:recalculate:running`.

---

## Исправление 6 (опционально): Приоритет sync по activity_type

**Проблема:** Нет приоритета загрузки по preferred_activity_type.

**Файл:** `backend/app/services/strava_sync.py`

**Что сделать:**

В методе `sync_user_activities` после получения user добавить:

```python
# Определить приоритетные типы активностей
if user.preferred_activity_type == "running":
    priority_types = ACTIVITY_TYPES_FOR_RUN_PROFILE
else:
    priority_types = ACTIVITY_TYPES_FOR_HIKE_PROFILE
```

И использовать это при запросе или сортировке активностей.

**Примечание:** Это сложнее реализовать, т.к. Strava API не фильтрует по типу. Можно:
- Загружать все, но сначала синхронизировать splits для приоритетных
- Или оставить как есть (низкий приоритет)

---

## Чеклист для агента

После каждого исправления проверь:

- [ ] Код компилируется без ошибок
- [ ] Импорты добавлены
- [ ] Функция реально вызывается (проследи путь от user action)

После всех исправлений:

- [ ] Перечитай этот план
- [ ] Убедись что каждый пункт выполнен
- [ ] Создай отчёт:
  ```
  ✅ Исправлено: [список]
  ⚠️ Частично: [список]
  ❌ Не сделано: [причина]
  ```

---

## Исправление 7: Тексты и порядок онбординга

**Проблема:** Тексты упрощены, не соответствуют плану. Порядок шагов может быть неправильным.

**Эталон:** `docs/todo/BOT_ONBOARDING_AND_SYNC.md` — там полный flow с текстами.

**Файл:** `bot/handlers/onboarding.py`

**Что сделать:**

1. Открыть `docs/todo/BOT_ONBOARDING_AND_SYNC.md`
2. Сверить каждый шаг (1-7) с реализацией
3. Заменить тексты на соответствующие плану

**Ключевые расхождения:**

### Шаг 1 (WELCOME_TEXT, строка ~33):
Текущий текст слишком короткий. По плану должен быть:
- Описание двух режимов (хайкинг/трейл)
- Список "В разработке" (погода, покрытие, crowdsourced)
- "Давай познакомимся! Это займёт пару минут."

### Шаг 2 (ACTIVITY_TEXT, строка ~41):
По плану должен объяснять:
- Стандартный режим vs Персонализированный
- Два отдельных профиля (хайкера и бегуна)

### Шаг 3 (PERSONALIZATION_TEXT, строка ~55):
По плану разный текст для hiking и running:
- Для hiking: объяснение 7 категорий градиента
- Для running: объяснение GAP, проблема Strava predictions

### Шаг 4 (STRAVA_OFFER_TEXT, строка ~69):
По плану должен показывать "пустой профиль":
```
┌─────────────────────────────────────┐
│  Темп на ровном:     ❓ нет данных  │
│  Темп на подъёме:    ❓ нет данных  │
│  Темп на спуске:     ❓ нет данных  │
└─────────────────────────────────────┘
```

### Шаг 6 (USAGE_*_TEXT, строки ~110, ~129):
Проверить соответствие плану.

**Порядок шагов (проверить flow):**
1. Welcome → кнопка "Начать"
2. Выбор активности (hiking/running)
3. Объяснение персонализации (разное для hiking/running!)
4. Предложение Strava
5. Strava connected / skipped
6. Как пользоваться
7. Готово

**Важно:** Шаг 3 должен показывать РАЗНЫЙ текст в зависимости от выбора на шаге 2!

Проверить в коде:
- `handle_activity_selection` сохраняет `activity_type`
- `handle_personalization_continue` должен использовать `activity_type` для выбора текста

---

## Порядок выполнения

1. **Исправление 7** — тексты онбординга (сначала, чтобы понять flow)
2. **Исправление 1** — уведомления
3. **Исправление 2** — Strava callback в онбординге
4. **Исправление 3** — пропуск "Опыт"
5. **Исправление 5** — recalculate_profile
6. **Исправление 4** — progress notifications
7. **Исправление 6** — опционально

---

## Файлы для чтения (контекст)

Если нужен контекст, читай:
- `bot/handlers/common.py` — /start handler
- `bot/handlers/prediction.py` — GPX flow
- `bot/handlers/strava.py` — Strava OAuth callback
- `bot/handlers/profile.py` — /profile command
- `bot/services/notifications.py` — NotificationService
- `backend/app/services/strava_sync.py` — sync logic

---

## Время

Ориентировочно: 6 небольших правок, каждая на 5-10 строк кода.
