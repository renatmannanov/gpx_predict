# Phase 1.1: UX и Dual Results для Trail Run

## Проблема

### Текущее поведение
1. Бот спрашивает темп у ВСЕХ пользователей одинаково
2. НЕ показываем подключён пользователь к Strava или нет
3. НЕ показываем какой у него темп из Strava (если есть)
4. Если Strava не подключена — не мотивируем подключить
5. Выбранный вручную темп **игнорируется** в пользу профиля (баг в `service.py:174-178`)

### Желаемое поведение
1. **Показывать статус Strava** — подключена или нет
2. **Если есть Strava** — показывать темп из профиля
3. **Если нет Strava** — предупреждать что расчёт приблизительный
4. **Всегда** давать выбор темпа
5. Показывать **оба** варианта расчёта (Strava-based + выбранный)

---

## Анализ сложности

### Вариант 1: Показывать 6 GAP результатов (3 Strava + 3 Manual)

**Как это работает:**

Два вызова одного и того же `TrailRunService` с разным `flat_pace_min_km`:
```python
# Расчёт 1: темп из Strava профиля (если есть)
service_strava = TrailRunService(flat_pace_min_km=5.5, ...)  # из профиля
result_strava = service_strava.calculate_route(points)

# Расчёт 2: темп выбранный/введённый пользователем
service_manual = TrailRunService(flat_pace_min_km=6.0, ...)  # выбранный
result_manual = service_manual.calculate_route(points)
```

Никаких новых моделей — просто два прогона с разным базовым темпом.
Получаем два набора `totals` с 3 GAP методами в каждом.

**Что нужно изменить:**

#### Backend (`predict.py`, `service.py`)
- **Сложность: СРЕДНЯЯ**
- Два вызова TrailRunService (как выше)
- Новая структура response с двумя наборами totals

#### API Schema (`prediction.py`)
- **Сложность: НИЗКАЯ**
- Добавить поля для dual results:
  ```python
  totals_strava: Dict[str, float]  # 3 GAP на основе Strava pace
  totals_manual: Dict[str, float]  # 3 GAP на основе введённого темпа
  strava_flat_pace: Optional[float]
  manual_flat_pace: float
  ```

#### Bot Handler (`trail_run.py`)
- **Сложность: СРЕДНЯЯ**
- Обновить flow:
  - Всегда показывать информацию о Strava профиле (если есть)
  - Всегда спрашивать темп (с подсказкой из Strava)
- Обновить форматирование результата

#### Bot Formatter
- **Сложность: СРЕДНЯЯ**
- Показывать две секции или сравнительную таблицу

**Общая оценка: ~4-6 часов работы**

---

### Вариант 2: Показывать 3 GAP с переключением источника темпа

**Что нужно изменить:**

#### Backend
- **Сложность: НИЗКАЯ**
- Один расчёт, но с выбором источника темпа
- Добавить флаг `use_profile_pace: bool` в request

#### Bot Handler
- **Сложность: НИЗКАЯ**
- Добавить кнопку переключения "Темп из Strava" / "Мой темп"
- При смене пересчитывать

**Общая оценка: ~2-3 часа работы**

---

## Рекомендация

**Рекомендую Вариант 1** по следующим причинам:

1. **Для тестирования** — сразу видно разницу между Strava и введённым темпом
2. **UX** — пользователь сам решает, какой темп ему ближе
3. **Валидация** — можно проверить, насколько Strava профиль соответствует реальности
4. **Нет пересчёта** — все данные сразу, не нужно ждать повторного расчёта

---

## Детальный план реализации (Вариант 1)

### 1. Bot: UX Flow изменения

#### 1.1. Start flow (`start_trail_run_flow`)

**Для пользователя БЕЗ Strava:**
```
🏃 Какой у тебя темп на ровном?

<blockquote>⚠️ У тебя не подключена Strava, поэтому расчёт будет приблизительный</blockquote>

Выбери свой примерный темп бега на плоской поверхности или введи вручную.
Это будет базой для расчёта с учётом рельефа.

[5:00] [5:30] [6:00] [6:30] [7:00] [Свой...]
```

**Для пользователя С Strava профилем:**
```
🏃 Какой у тебя темп на ровном?

<blockquote>👤 Твой темп на ровном: {strava_pace}/км
На основе {activities_count} активностей из Strava</blockquote>

Используй темп из Strava или введи свой, если не согласен или хочешь получить другой результат.

[Использовать {strava_pace}] [5:30] [6:00] [6:30] [Свой...]
```

#### 1.2. Summary перед расчётом

```
🏃 Trail Run: {name}

📍 Маршрут: {distance} км
📈 Набор: +{gain}м / -{loss}м

📊 Буду считать для:
• Strava темп: {strava_pace}/км ({activities} активностей)
• Твой темп: {manual_pace}/км

⚙️ Настройки:
• GAP режим: {gap_mode}
• Усталость: {fatigue}

[Рассчитать!] [Настройки] [Отмена]
```

#### 1.3. Результат с dual output

```
🏃 Trail Run: {name}

📍 {distance} км | D+ {gain}м | D- {loss}м

━━━━━━━━━━━━━━━━━━━━━━━━

📊 НА ОСНОВЕ STRAVA ({strava_pace}/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP      {time}
  Minetti GAP     {time}
  Strava+Minetti  {time}

━━━━━━━━━━━━━━━━━━━━━━━━

📊 НА ОСНОВЕ ТВОЕГО ТЕМПА ({manual_pace}/км):

⏱ ВСЁ БЕГОМ:
  Strava GAP      {time}
  Minetti GAP     {time}
  Strava+Minetti  {time}
```

**Примечание:** Если у пользователя нет Strava — показываем только одну секцию с выбранным темпом.

### 2. Backend изменения

#### 2.1. Schema (`prediction.py`)

```python
class TrailRunCompareRequest(BaseModel):
    # ... existing fields ...
    flat_pace_min_km: Optional[float] = None  # Manual pace (always required now)
    include_strava_comparison: bool = True     # NEW: include Strava-based results

class TrailRunCompareResponse(BaseModel):
    # ... existing fields ...

    # NEW: Dual results
    strava_pace_used: Optional[float] = None
    manual_pace_used: float

    totals_strava: Optional[Dict[str, float]] = None  # Results with Strava pace
    totals_manual: Dict[str, float]                    # Results with manual pace

    # Keep 'totals' for backwards compatibility (= totals_manual)
```

#### 2.2. Route (`predict.py`)

```python
@router.post("/trail-run/compare")
async def compare_trail_run_methods(request, db):
    # ... get profiles ...

    # Always calculate with manual pace
    service_manual = TrailRunService(
        flat_pace_min_km=request.flat_pace_min_km or 6.0,
        run_profile=None,  # Don't use profile for GAP
        ...
    )
    result_manual = service_manual.calculate_route(points)

    # Optionally calculate with Strava pace
    result_strava = None
    strava_pace = None
    if run_profile and run_profile.avg_flat_pace_min_km:
        strava_pace = run_profile.avg_flat_pace_min_km
        if request.include_strava_comparison:
            service_strava = TrailRunService(
                flat_pace_min_km=strava_pace,
                run_profile=None,  # Just pace, no personalization yet
                ...
            )
            result_strava = service_strava.calculate_route(points)

    return TrailRunCompareResponse(
        totals=result_manual.totals,  # Backwards compat
        totals_manual=result_manual.totals,
        totals_strava=result_strava.totals if result_strava else None,
        manual_pace_used=request.flat_pace_min_km or 6.0,
        strava_pace_used=strava_pace,
        ...
    )
```

#### 2.3. Service (`service.py`)

Исправить баг с приоритетом:
```python
def __init__(self, ..., flat_pace_min_km, run_profile=None, ...):
    # Use provided flat_pace, NOT from profile
    # Profile is for personalization coefficients, not base pace
    self.flat_pace = flat_pace_min_km

    # Profile used only for personalization (future phase)
    self.run_profile = run_profile
```

### 3. Bot Client изменения

```python
async def predict_trail_run(
    self,
    gpx_id: str,
    telegram_id: Optional[str] = None,
    gap_mode: str = "strava_gap",
    flat_pace_min_km: float = 6.0,  # Now required
    apply_fatigue: bool = False,
    include_strava_comparison: bool = True,  # NEW
) -> Optional[dict]:
```

---

## Файлы для изменения

| Файл | Изменения | Сложность |
|------|-----------|-----------|
| `backend/app/schemas/prediction.py` | Добавить dual fields | Низкая |
| `backend/app/api/v1/routes/predict.py` | Dual calculation logic | Средняя |
| `backend/app/features/trail_run/service.py` | Fix pace priority bug | Низкая |
| `bot/services/clients/trail_run.py` | Add include_strava_comparison | Низкая |
| `bot/handlers/trail_run.py` | UX flow + formatting | Средняя |
| `bot/keyboards/trail_run.py` | Update keyboards | Низкая |

---

## Альтернатива: Отложить dual results

Если dual results слишком сложно сейчас, можно:

1. **Исправить только баг с приоритетом** — manual pace всегда используется
2. **Показывать Strava pace как информацию** — но не считать по нему
3. **Добавить dual results в Phase 2** — когда появится Run+Hike

Это займёт ~1-2 часа и решит основную проблему (выбор темпа не работает).

---

## Вопросы к пользователю

1. **Какой вариант предпочтительнее?**
   - A) Полный dual results (6 чисел: 3 Strava + 3 Manual) — если есть Strava
   - B) Простое исправление (только manual работает, Strava показывается как инфо)

2. **Формат вывода dual results:**
   - A) Две отдельные секции (как в плане выше)
   - B) Два отдельных сообщения
