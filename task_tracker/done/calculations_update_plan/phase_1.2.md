# Phase 1.2: Улучшение UX сообщений о Strava статусе

**Статус:** Готов к реализации
**Зависимости:** Phase 1.1 (исправлен telegram_id)

---

## Проблема

Текущее поведение в боте:
```python
run_profile = await api_client.get_run_profile(telegram_id)
if run_profile and run_profile.get("avg_flat_pace_min_km"):
    # "👤 Твой темп на ровном: X:XX/км"
else:
    # "⚠️ У тебя не подключена Strava..." ← НЕТОЧНО!
```

**Проблема:** Сообщение "не подключена Strava" показывается когда:
1. Strava действительно не подключена — OK
2. Strava подключена, но нет беговых активностей — НЕТОЧНО
3. Strava подключена, есть бег, но < 5 splits — НЕТОЧНО

Пользователь с подключённой Strava видит "не подключена" — это путает.

---

## Решение

Разделить три сценария с разными сообщениями:

| Сценарий | Сообщение | Клавиатура |
|----------|-----------|------------|
| Есть run profile с темпом | "👤 Твой темп: X:XX/км (N активностей)" | `[Strava X:XX] [5:30] [6:00] ...` |
| Strava подключена, но нет run profile | "⚠️ Strava подключена, но недостаточно беговых данных" | `[5:00] [5:30] [6:00] ...` |
| Strava не подключена | "⚠️ Strava не подключена" | `[5:00] [5:30] [6:00] ...` |

**Клавиатура одинаковая** для сценариев 2 и 3 — стандартные темпы без кнопки Strava.

---

## План изменений

### 1. Bot: `start_trail_run_flow()` в `trail_run.py`

**Файл:** `bot/handlers/trail_run.py`

**Текущий код (строки 174-223):**
```python
async def start_trail_run_flow(...):
    telegram_id = user_id or str(message.from_user.id)

    run_profile = await api_client.get_run_profile(telegram_id)

    strava_pace = None
    activities_count = 0

    if run_profile and run_profile.get("avg_flat_pace_min_km"):
        strava_pace = run_profile.get("avg_flat_pace_min_km")
        activities_count = run_profile.get("total_activities", 0)

    # ... save to state ...

    if strava_pace:
        text = "👤 Твой темп на ровном: ..."
        keyboard = get_flat_pace_keyboard(strava_pace=strava_pace)
    else:
        text = "⚠️ У тебя не подключена Strava..."  # ← НЕТОЧНО
        keyboard = get_flat_pace_keyboard()
```

**Новый код:**
```python
async def start_trail_run_flow(...):
    telegram_id = user_id or str(message.from_user.id)

    # 1. Check Strava connection status
    strava_status = await api_client.get_strava_status(telegram_id)
    strava_connected = strava_status and strava_status.get("connected", False)

    # 2. Check run profile (only if Strava connected)
    strava_pace = None
    activities_count = 0

    if strava_connected:
        run_profile = await api_client.get_run_profile(telegram_id)
        if run_profile and run_profile.get("avg_flat_pace_min_km"):
            strava_pace = run_profile.get("avg_flat_pace_min_km")
            activities_count = run_profile.get("total_activities", 0)

    # Save to state
    await state.update_data(
        gpx_id=gpx_id,
        gpx_info=gpx_info,
        activity_type="trail_run",
        gap_mode="strava_gap",
        apply_fatigue=False,
        flat_pace_min_km=None,
        strava_pace=strava_pace,
        strava_activities_count=activities_count,
        strava_connected=strava_connected,  # NEW
    )

    await state.set_state(TrailRunStates.selecting_flat_pace)

    # 3. Build message based on scenario
    if strava_pace:
        # Scenario 1: Has run profile with pace
        pace_formatted = format_pace(strava_pace)
        text = (
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            f"<blockquote>👤 Твой темп на ровном: {pace_formatted}/км\n"
            f"На основе {activities_count} активностей из Strava</blockquote>\n\n"
            "Используй темп из Strava или введи свой."
        )
        keyboard = get_flat_pace_keyboard(strava_pace=strava_pace)

    elif strava_connected:
        # Scenario 2: Strava connected but no run profile
        text = (
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            "<blockquote>⚠️ Strava подключена, но недостаточно беговых данных "
            "для расчёта твоего темпа.\n\n"
            "Нужно минимум 5 км бега с GPS для анализа.</blockquote>\n\n"
            "Выбери свой примерный темп или введи вручную."
        )
        keyboard = get_flat_pace_keyboard()

    else:
        # Scenario 3: Strava not connected
        text = (
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            "<blockquote>⚠️ Strava не подключена — расчёт будет "
            "на основе выбранного темпа.</blockquote>\n\n"
            "Выбери свой примерный темп бега на плоской поверхности.\n"
            "Это будет базой для расчёта с учётом рельефа."
        )
        keyboard = get_flat_pace_keyboard()

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
```

### 2. Проверить `get_strava_status` в API client

**Файл:** `bot/services/clients/__init__.py` или `bot/services/clients/strava.py`

Убедиться что метод существует и возвращает `{"connected": bool, ...}`.

```python
# Ожидаемый интерфейс:
strava_status = await api_client.get_strava_status(telegram_id)
# Returns: {"connected": True/False, "athlete_name": "...", ...} or None
```

---

## Файлы для изменения

| Файл | Изменение | Строки |
|------|-----------|--------|
| `bot/handlers/trail_run.py` | Добавить проверку strava_connected | ~20 строк |

**Итого:** ~20 строк изменений

---

## Проверка перед реализацией

- [ ] Метод `api_client.get_strava_status(telegram_id)` существует
- [ ] Возвращает dict с полем `connected: bool`
- [ ] Работает для пользователей без Strava (возвращает `None` или `{"connected": False}`)

---

## Тест-кейсы

### Сценарий 1: Есть run profile
**Условие:** Пользователь с Strava, ≥5 беговых splits
**Ожидание:**
- Текст: "👤 Твой темп на ровном: 5:30/км"
- Клавиатура: `[Strava 5:30] [5:30] [6:00] [6:30] [Свой]`

### Сценарий 2: Strava есть, run profile нет
**Условие:** Пользователь с Strava, но без бега или <5 splits
**Ожидание:**
- Текст: "⚠️ Strava подключена, но недостаточно беговых данных"
- Клавиатура: `[5:00] [5:30] [6:00] [6:30] [7:00] [Свой]`

### Сценарий 3: Strava не подключена
**Условие:** Пользователь без Strava
**Ожидание:**
- Текст: "⚠️ Strava не подключена"
- Клавиатура: `[5:00] [5:30] [6:00] [6:30] [7:00] [Свой]`

---

## Дополнительно (опционально)

После Phase 1.2 можно добавить:
- Кнопку "Подключить Strava" для сценария 3
- Кнопку "Синхронизировать бег" для сценария 2

Но это не критично для MVP — можно сделать позже.

---

## Чеклист после реализации

- [ ] Сценарий 1 работает (есть run profile → показывает темп)
- [ ] Сценарий 2 работает (Strava есть, профиля нет → правильное сообщение)
- [ ] Сценарий 3 работает (Strava нет → правильное сообщение)
- [ ] Клавиатура одинаковая для сценариев 2 и 3
- [ ] Backend dual results работает (если есть run profile)
- [ ] Удалён debug logging из predict.py и profiles.py
