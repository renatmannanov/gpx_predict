# Обсуждение расчётов Trail Running

Дата: 2026-01-30

---

## Начало обсуждения

### User:
теперь сделаем для прогноза трейл раннинга

загружаю файл, выбираю "трейл ран", дальше

1 "🏃 Какой у тебя темп на ровном?

Выбери свой примерный темп бега на плоской поверхности.
Это будет базой для расчёта с учётом рельефа."
допустим 6:00

2 "🏃 Trail Run: Talgar_Trail

📍 Маршрут: 20.0 км
📈 Набор: +2323м / -691м

Настройки:
• GAP режим: Strava GAP
• Усталость: Нет
• Персонализация: Нет (6:00/км)

Нажми "Рассчитать!" или измени настройки."
Допустим тыкаю "Рассчитать"

3
Сообщение 1
gpx predictor, [1/30/2026 2:21 PM]
🏃 Прогноз Trail Run: Talgar_Trail
меняем на
🏃Беговой прогноз для маршрута:
Talgar_Trail

📍 Маршрут: 20.0 км, D+ 2322м, D- 690м
меняем на
📍Маршрут:
     19.99 км
     Подъём: 13.89 км (+2322 м)
     Спуск: 5.21 км (-690 м)

⏱ Время:
  • Strava GAP: 3ч 50мин
  • Minetti GAP: 3ч 41мин
  • tobler: 18мин
  • Персональный (бег): 3ч 50мин 🎯
  • Комбинированный: 4ч 8мин

меняем на
тут сначала мне нужно понять каждую строку что мы показываем и из какого рассчета, дай подробности

📊 Разбивка:
  • Бег: 19.6 км (98%) — 3ч 50мин
  • Ходьба: 0.4 км (2%) — 18мин
  • Порог ходьбы: 25%
* тут тоже

💪 Влияние рельефа: +66% к плоскому времени
* тут тоже обясни откуда и как считаем

👤 Персонализировано на основе 11 активностей (добавь "и Х сплитов)

Сообщение 2
Задача *: показывать все сегменты и обернуть в quote
gpx predictor, [1/30/2026 2:21 PM]
📈 По сегментам:

1. 🏃 0.4км (+0%) — 2мин
2. 🏃 1.5км (+14%) — 18мин
3. 🏃 0.9км (-13%) — 5мин
4. 🏃 2.3км (+24%) — 43мин
5. 🏃 0.6км (+4%) — 5мин
6. 🏃 0.5км (+6%) — 4мин
7. 🏃 0.3км (-7%) — 2мин
8. 🏃 0.8км (+8%) — 7мин
9. 🏃 0.9км (-8%) — 6мин
10. 🏃 0.4км (+10%) — 4мин
... и ещё 10 сегментов

давай пока так
принимай задачу
дай инфу
ответь на вопросы
задай сввои

---

### Claude (первый ответ с объяснениями):

## Объяснение каждой строки прогноза

### ⏱ Время:

| Строка | Откуда | Описание |
|--------|--------|----------|
| **Strava GAP** | `gap.py:201-223` | Эмпирическая модель на основе данных 240k+ атлетов Strava. Lookup-таблица с интерполяцией по градиенту (-30% до +45%). На +10% градиенте темп ~1.38x медленнее. |
| **Minetti GAP** | `gap.py:260-296` | Научная формула энергозатрат Minetti для подъёмов, Strava для спусков. Более агрессивный на крутых подъёмах. |
| **tobler** | `tobler.py:44-79` | Tobler's Hiking Function (1993): `6 * exp(-3.5 * |gradient + 0.05|)` км/ч. **Только для HIKE сегментов** (где gradient >= threshold). |
| **Персональный (бег)** | `personalization.py` (run) | Реальный темп пользователя по категориям градиента из Strava Run/TrailRun активностей. 7 категорий (steep_downhill → steep_uphill). |
| **Комбинированный** | `service.py:296-340` | Итоговое время = персонализированный (если есть) или GAP (по режиму) + усталость. Основной прогноз. |

### 📊 Разбивка:

| Строка | Откуда | Описание |
|--------|--------|----------|
| **Бег: X км (Y%) — Zч** | `service.py:335` | Сумма дистанций и времён сегментов где `mode == RUN` (gradient < threshold) |
| **Ходьба: X км (Y%) — Zч** | `service.py:337` | Сумма дистанций и времён сегментов где `mode == HIKE` (gradient >= threshold) |
| **Порог ходьбы: 25%** | `hike_run_threshold.py` | Градиент, при котором переключается с бега на ходьбу. По умолчанию 25%. |

### 💪 Влияние рельефа:

**Формула** (`service.py:363-368`):
```python
flat_time = total_distance / (60 / flat_pace)  # Время если бы всё было плоское
elevation_impact = ((combined / flat_time) - 1) * 100
```
Пример: 20 км, темп 6:00/км → flat_time = 2ч. Реальное время 3ч 20м → impact = +66%

### 👤 Персонализация:

- **activities_used** = `run_profile.total_activities + hike_profile.total_activities_analyzed`
- **splits** = сумма sample_count по всем категориям градиента в `UserRunProfile`

---

## Мои вопросы:

1. **tobler: 18мин** в примере — это время только для HIKE сегментов (0.4 км ходьбы)? Или это баг и показывается неправильно?

2. **"Персональный (бег): 3ч 50мин"** — хочешь оставить это название или поменять? Например "📊 ваш темп (бег)"?

3. **Разделитель** как в hiking (`——————————————`) — добавлять между основной и дополнительной информацией?

4. **Порядок времён** — какой порядок показывать? Сейчас все методы в произвольном порядке из dict. Предлагаю:
   - Базовые: Strava GAP, Minetti GAP
   - Персонализированные (если есть): 📊 ваш темп (бег), 📊 ваш темп (ходьба)
   - Итого: Комбинированный

5. **Сегменты в quote** — показывать все сегменты или лимитировать (сейчас 10)?

---

### User (уточняющие вопросы — раунд 1):

Время
Strava GAP - откуда берем данные пользователя, чтобы рассчитать?
Minetti GAP - откуда берем данные пользователя, чтобы рассчитать?
tobler - почему отдельно? и почему применяется если у нас бег?
Персональный (бег) - чем отличается от GAP'ов?
Комбинированный - давай подробнее, какой именно персонализированный, какой GAP, сколько накидывается усталости

Разбивка:
Бег: X км (Y%) — Zч - по рассчету какой формулы?
Ходьба: X км (Y%) — Zч - по рассчету какой формулы?
Порог ходьбы: 25% - допустим

Влияние рельефа - зачем показываем? есть гдето объяснение и комменты?

1 не знаю, надо у тебя спросить как мы считаем)
2 пока хочу выяснить как считаем
3 пока нет
4 сначала дай вдетали котрые попросил выше
5 все

---

### User (уточняющие вопросы — раунд 2):

Время
Strava GAP - правильно понимаю, что мы для каждого сплита применяем эту формулу? потом показываем сумму?
Minetti GAP - тут мы для сплитов вверх применяем Minetti GAP, а для сплитов вниз Strava GAP, так?
Если не так, напиши подробно как

tobler
1 почему не использует данные пользователя?
2 и откуда берет данные?
3 почему берем именно tobler, если для хайкинга у нас есть еще 3: naismith и персонализированные naismith и tobler? распиши алгоритм, если есть
4 эти рассчеты включены в другие, Minetti GAP, Strava GAP и Персональный ?

"Составной. Для каждого сегмента выбирает "лучший" метод + накидывает усталость."
run_personalized → primary_time = run_personalized, что такое primary_time ?

Разбивка:
Бег: X км — Zч	Сумма adjusted_time - по какой формуле предикта?

Влияние рельефа давай уберем, запомни это,сделаем чуть позже

4 "Splits (сплиты) — откуда взять количество?" а почему нет? откуда мы берем сплиты для хайкинг?

---

### Claude (ответы на раунд 2):

## Strava GAP
**Да, верно.** Для каждого сегмента (сплита) применяем формулу:
```
segment_pace = flat_pace × STRAVA_TABLE[gradient]
segment_time = segment_distance / (60 / segment_pace)
```
Потом суммируем все segment_time → получаем `totals["strava_gap"]`.

## Minetti GAP
**Да, верно.** Гибридная модель:
- **Сегменты вверх (gradient >= 0%)**: Minetti polynomial → `pace = flat_pace × (energy_cost^0.75)`
- **Сегменты вниз (gradient < 0%)**: Strava table → `pace = flat_pace × STRAVA_TABLE[gradient]`

Потом суммируем → `totals["minetti_gap"]`.

## tobler

### 1. Почему не использует данные пользователя?
Tobler's Hiking Function — это **универсальная научная формула** для скорости ходьбы человека (не бега). Она описывает "среднего человека" и не зависит от персональных данных. Формула:
```
speed = 6 × exp(-3.5 × |gradient + 0.05|)  км/ч
```
Это физиологический предел скорости ходьбы на разных уклонах.

### 2. Откуда берёт данные?
**Только из GPX:** дистанция сегмента и градиент. Никаких пользовательских данных.

### 3. Почему именно tobler, а не naismith/персонализированные?

**Алгоритм выбора для HIKE сегментов** (`service.py:304-321`):
```python
if decision.mode == HIKE:
    # 1. Всегда считаем Tobler
    tobler_result = self._tobler_calc.calculate_segment(segment)
    times["tobler"] = tobler_result.time_hours

    # 2. Если есть hike profile → считаем персонализированный
    if self._hike_pers:
        pers_result = self._hike_pers.calculate_segment(segment)
        times["hike_personalized"] = pers_result.time_hours

    # 3. Выбираем primary_time
    if self._hike_pers:
        primary_time = times["hike_personalized"]  # Приоритет персонализации
    else:
        primary_time = times["tobler"]  # Fallback на Tobler
```

**Почему не Naismith?** Видимо, решение разработчика — Tobler считается более точным для trail running (основан на энергозатратах), а Naismith больше для традиционного hiking.

### 4. Включены ли tobler расчёты в Strava GAP, Minetti GAP, Персональный?

**НЕТ!** Это полностью независимые расчёты:

| Метод | Применяется к | Включает tobler? |
|-------|--------------|------------------|
| Strava GAP | RUN сегменты | ❌ Нет |
| Minetti GAP | RUN сегменты | ❌ Нет |
| run_personalized | RUN сегменты | ❌ Нет |
| tobler | HIKE сегменты | ✅ Это и есть tobler |
| hike_personalized | HIKE сегменты | ❌ Отдельный расчёт |

**combined** — единственный метод, который **объединяет** RUN и HIKE:
```
combined = Σ(RUN сегменты: run_pers/GAP) + Σ(HIKE сегменты: hike_pers/tobler)
```

## primary_time

**primary_time** — это "главное время" для конкретного сегмента, которое:
1. Используется для расчёта усталости
2. Добавляется в `combined`
3. Влияет на `running_time` или `hiking_time`

```python
# Для RUN сегмента:
if есть run_personalized:
    primary_time = run_personalized  # Приоритет
elif gap_mode == STRAVA:
    primary_time = strava_gap
else:
    primary_time = minetti_gap

# Применяем усталость
adjusted_time = primary_time + fatigue_adjustment

# Добавляем в итоги
combined += adjusted_time
running_time += adjusted_time
```

## Разбивка — Бег: X км — Zч

**Формула:**
```
running_time = Σ adjusted_time для всех сегментов где mode == RUN
```

Где `adjusted_time` для каждого RUN сегмента:
```
1. Выбираем primary_time:
   - run_personalized (если есть профиль с >= 5 сплитами в этой категории градиента)
   - ИЛИ strava_gap (если gap_mode == STRAVA)
   - ИЛИ minetti_gap (если gap_mode == MINETTI)

2. Применяем усталость:
   adjusted_time = primary_time × fatigue_multiplier
   (если fatigue выключен, multiplier = 1.0)
```

---

### Claude (детальные объяснения — первая часть):

## Детали расчётов

### ⏱ Время:

| Метод | Откуда берём данные пользователя | Формула |
|-------|----------------------------------|---------|
| **Strava GAP** | `flat_pace_min_km` — либо из `UserRunProfile.avg_flat_pace_min_km` (если подключен Strava), либо ручной ввод (6:00/км по умолчанию). Далее умножается на коэффициент из таблицы Strava по градиенту. | `adjusted_pace = flat_pace × STRAVA_TABLE[gradient]` |
| **Minetti GAP** | То же самое — `flat_pace_min_km`. Для подъёмов использует формулу энергозатрат Minetti, для спусков — таблицу Strava. | Uphill: `pace = flat_pace × (energy_cost_ratio^0.75)` |
| **tobler** | **НЕ использует данные пользователя!** Это формула скорости ходьбы. Применяется **только для HIKE сегментов** (где gradient >= порог 25%). | `speed = 6 × exp(-3.5 × |gradient + 0.05|)` км/ч |
| **Персональный (бег)** | Из `UserRunProfile` — **реальные средние темпы пользователя по категориям градиента** из Strava Run/TrailRun активностей. 7 категорий: steep_downhill, moderate_downhill, gentle_downhill, flat, gentle_uphill, moderate_uphill, steep_uphill. Если < 5 сплитов в категории → fallback на Strava GAP. | Прямой lookup: `pace = profile.avg_{category}_pace` |
| **Комбинированный** | **Составной.** Для каждого сегмента выбирает "лучший" метод + накидывает усталость. | См. ниже |

### Комбинированный — подробно (`service.py:296-340`)

```
Для каждого сегмента:

ЕСЛИ режим == RUN (gradient < 25%):
    ЕСЛИ есть run_personalized → primary_time = run_personalized
    ИНАЧЕ ЕСЛИ gap_mode == STRAVA → primary_time = strava_gap
    ИНАЧЕ → primary_time = minetti_gap

ЕСЛИ режим == HIKE (gradient >= 25%):
    ЕСЛИ есть hike_personalized → primary_time = hike_personalized
    ИНАЧЕ → primary_time = tobler

primary_time += fatigue_adjustment
combined += primary_time
```

**Усталость** (`RunnerFatigueService`):
- Включается вручную через настройки
- Добавляет % к времени после ~2ч бега
- Зависит от накопленного времени и градиента
- Рекомендуется для дистанций >25км

---

### 📊 Разбивка:

| Строка | Формула | Откуда данные |
|--------|---------|---------------|
| **Бег: X км — Zч** | Сумма `adjusted_time` для всех сегментов где `mode == RUN`. `adjusted_time` = primary_time + fatigue | primary_time = run_personalized (если есть) или GAP (по режиму) |
| **Ходьба: X км — Zч** | Сумма `adjusted_time` для всех сегментов где `mode == HIKE` | primary_time = hike_personalized (если есть) или tobler |

---

### 💪 Влияние рельефа:

**Формула** (`service.py:364-367`):
```python
flat_speed_kmh = 60 / flat_pace          # Скорость на плоском
flat_time = total_distance / flat_speed_kmh  # Если бы всё было плоское
elevation_impact = ((combined / flat_time) - 1) * 100
```

**Зачем показываем?** Честно говоря, **нет комментария в коде зачем**. Это просто метрика "насколько рельеф замедляет" относительно идеальной плоскости. Можно:
- Оставить как есть (информативно)
- Убрать (не критично)
- Переименовать в "Замедление от рельефа"

---

## Ответ на вопрос 1 (tobler: 18мин)

**Это баг в отображении!** В `format_trail_run_result` показывается `totals["tobler"]` — но tobler считается **только для HIKE сегментов**. Если на маршруте 0.4 км ходьбы, tobler покажет время только для этих 0.4 км (18 мин), а не для всего маршрута.

**Варианты:**
1. **Убрать tobler из списка времён** — он не релевантен для бега
2. **Показывать только если есть HIKE сегменты** и пояснить "(только ходьба)"

---

### Claude (мои вопросы после детальных объяснений):

1. **tobler в списке времён** — убрать или оставить с пояснением?

2. **Влияние рельефа** — оставить, убрать, или переименовать?

3. **Структура сообщения** — хочешь как в hiking (разделитель между основной и дополнительной инфой)?

4. **Splits (сплиты)** — откуда взять количество? В `UserRunProfile` есть `sample_count` по категориям, но нет общего `total_splits`. Могу посчитать сумму sample_count по всем категориям. Показывать?

---

### User (ответы на мои вопросы):

Влияние рельефа давай уберем, запомни это, сделаем чуть позже

4 "Splits (сплиты) — откуда взять количество?" а почему нет? откуда мы берем сплиты для хайкинг?

---

### Claude (ответ):

## Сплиты (splits)

### UserRunProfile (для trail run):
**Есть sample_count по каждой категории!** (`user_run_profile.py:40-47`)
```python
flat_sample_count = Column(Integer, default=0)
gentle_uphill_sample_count = Column(Integer, default=0)
moderate_uphill_sample_count = Column(Integer, default=0)
steep_uphill_sample_count = Column(Integer, default=0)
gentle_downhill_sample_count = Column(Integer, default=0)
moderate_downhill_sample_count = Column(Integer, default=0)
steep_downhill_sample_count = Column(Integer, default=0)
```

**Общее количество сплитов** = сумма всех sample_count:
```python
total_splits = (
    profile.flat_sample_count +
    profile.gentle_uphill_sample_count +
    profile.moderate_uphill_sample_count +
    profile.steep_uphill_sample_count +
    profile.gentle_downhill_sample_count +
    profile.moderate_downhill_sample_count +
    profile.steep_downhill_sample_count
)
```

### UserHikingProfile (для hiking):
**НЕТ sample_count!** Есть только `total_activities_analyzed`. Это количество активностей, но не сплитов.

Для hiking мы можем показывать только "X активностей", без сплитов.

---

## Резюме — что показывать:

| Профиль | Активности | Сплиты |
|---------|------------|--------|
| **Trail Run** | `total_activities` | Сумма всех `*_sample_count` |
| **Hiking** | `total_activities_analyzed` | ❌ Нет данных |

---

### User (ещё уточнения):

primary_time - на основе каких данных мы его получаем?

про сплиты
вот для этого же маргруты мы показываем все сплиты

"Разбивка по участкам:

1. → Ровный
  0.38 км, +1 м
  Градиент: 0.3%
  [naismith] 4мин
  [tobler] 4мин

2. ↑ Подъём
  1.48 км, +208 м
  Градиент: 14.1%
  [naismith] 39мин
  [tobler] 29мин

3. ↓ Спуск
  0.89 км, -118 м
  Градиент: -13.3%
  [naismith] 6мин
  [tobler] 12мин
... (20 сегментов)"

откуда мы их берем то? и почему не можем взять для трейл раннинга?)

---

### Claude (финальное объяснение):

## Откуда берутся сегменты (сплиты маршрута)

**Сегменты берутся из GPX файла!** `RouteSegmenter.segment_route()` разбивает маршрут на участки по направлению:
- Подъём (gradient > 3%)
- Спуск (gradient < -3%)
- Ровный (-3% to +3%)

**Это одинаково работает для hiking И trail run!**

Смотри в `trail_run/service.py:234`:
```python
segments = RouteSegmenter.segment_route(points)  # Те же самые сегменты!
```

И в hiking prediction тоже используется тот же `RouteSegmenter`.

---

## Разница между "сплитами маршрута" и "сплитами профиля"

| Термин | Откуда | Для чего |
|--------|--------|----------|
| **Сегменты маршрута** (20 участков в твоём примере) | GPX файл → `RouteSegmenter` | Разбивка конкретного маршрута для расчёта времени |
| **Сплиты профиля** (`sample_count`) | Strava активности пользователя | Статистика для персонализации (сколько км пользователь пробежал на разных градиентах) |

**Для trail run у нас ЕСТЬ сегменты маршрута!** Смотри `service.py:352-357`:
```python
results.append(SegmentResult(
    segment=segment,        # Это MacroSegment (участок маршрута)
    movement=decision,      # RUN или HIKE
    times=times,            # Времена по методам
    fatigue_multiplier=multiplier
))
```

И в API ответе все сегменты возвращаются:
```python
return TrailRunResult(
    segments=results,  # Все сегменты маршрута!
    ...
)
```

---

## Почему показываем "... и ещё 10 сегментов"?

В `bot/handlers/trail_run.py:103` есть **искусственное ограничение**:
```python
for i, seg in enumerate(segments[:10], 1):  # Limit to 10 segments
```

**Это просто лимит в боте, а не отсутствие данных!**

---

## primary_time — на основе каких данных?

**primary_time** — это выбранное время для конкретного сегмента. Зависит от:

1. **Тип сегмента** (RUN или HIKE)
2. **Наличие профиля пользователя**
3. **Выбранный режим GAP**

```python
# ДЛЯ RUN СЕГМЕНТА:
if есть run_profile с >= 5 сплитами в этой категории градиента:
    primary_time = run_personalized
    # Данные: UserRunProfile.avg_{category}_pace (из Strava Run активностей)
elif gap_mode == STRAVA:
    primary_time = strava_gap
    # Данные: flat_pace (ручной ввод или из профиля) × STRAVA_TABLE[gradient]
else:
    primary_time = minetti_gap
    # Данные: flat_pace × Minetti formula

# ДЛЯ HIKE СЕГМЕНТА:
if есть hike_profile:
    primary_time = hike_personalized
    # Данные: UserHikingProfile.avg_{category}_pace (из Strava Hike активностей)
else:
    primary_time = tobler
    # Данные: только GPX (дистанция, градиент) → формула Tobler
```

---

## Итоговые решения из обсуждения:

1. ✅ **Strava GAP** — для каждого сплита применяем формулу, потом сумма
2. ✅ **Minetti GAP** — Minetti для подъёмов, Strava для спусков
3. ✅ **tobler** — не использует данные пользователя (универсальная формула), берёт только GPX, используется как fallback для HIKE сегментов
4. ✅ **tobler НЕ включён** в Strava GAP, Minetti GAP, run_personalized — это независимые расчёты
5. ✅ **primary_time** — главное время сегмента для расчёта усталости и combined
6. ✅ **Бег: X км — Zч** — сумма adjusted_time (primary_time × fatigue) для RUN сегментов
7. ✅ **Влияние рельефа** — УБИРАЕМ (решение пользователя)
8. ✅ **Сплиты** — для trail run есть (сумма sample_count), для hiking нет
9. ✅ **Сегменты маршрута** — показывать ВСЕ (убрать лимит 10) и обернуть в quote

---

## Ключевые файлы:

- `backend/app/features/trail_run/service.py` — основной сервис расчёта
- `backend/app/features/trail_run/calculators/gap.py` — Strava GAP и Minetti GAP
- `backend/app/features/trail_run/calculators/personalization.py` — персонализация бега
- `backend/app/features/hiking/calculators/tobler.py` — формула Tobler
- `backend/app/features/gpx/segmenter.py` — разбивка маршрута на сегменты
- `backend/app/models/user_run_profile.py` — модель профиля бегуна (с sample_count)
- `bot/handlers/trail_run.py` — форматирование и отправка в Telegram
