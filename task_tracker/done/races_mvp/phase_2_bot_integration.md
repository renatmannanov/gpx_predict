# Фаза 2: Интеграция в Telegram-бота

## Цель

Пользователь бота может выбрать гонку, получить прогноз, найти свои результаты прошлых лет. Первая гонка — Alpine Race, архитектура масштабируется на все 7 горных гонок.

## Зависимости

- **Фаза 0 завершена** — парсер + результаты в JSON
- **Фаза 1 завершена** — RaceService + каталог + CLI работает
- Результаты Alpine Race протестированы на Ренате

## Архитектура

```
backend/app/
├── features/races/
│   ├── ... (из Фаз 0-1)
│   └── repository.py               # Загрузка каталога и результатов для API
└── api/v1/routes/
    └── races.py                     # API endpoints для бота

bot/
├── handlers/races.py                # Хэндлеры гонок
├── keyboards/races.py               # Inline keyboards
├── states/races.py                  # FSM states
└── services/clients/races.py        # API client
```

Контент остаётся в `content/races/` — бот читает через backend API.

## Задачи

### Задача 1: API endpoints

**Файл:** `backend/app/api/v1/routes/races.py`

```
GET  /api/v1/races                                    # Календарь горных гонок
GET  /api/v1/races/{race_id}                          # Карточка гонки
GET  /api/v1/races/{race_id}/{year}/results           # Результаты + статистика
GET  /api/v1/races/{race_id}/{year}/search?name=...   # Поиск по имени
POST /api/v1/races/{race_id}/predict                  # Прогноз (user_id или flat_pace)
```

Зарегистрировать в `api/v1/router.py`.

**Критерий готовности:** Все endpoints отвечают, тестируются через curl/httpie.

### Задача 2: Bot handlers

**Файл:** `bot/handlers/races.py`

Flow:

```
/races → Список горных гонок 2026
  → [Alpine Race — 1 мар]
    → Карточка: 4км ↑900м 🟠
    → [🔮 Мой прогноз]
       → Есть Strava? → персональный прогноз + перцентиль
       → Нет Strava? → "Введи темп" → базовый прогноз → "Подключи Strava"
    → [🔍 Найти себя в 2025]
       → "Введи имя как при регистрации"
       → Поиск → показать результат + перцентиль
    → [📊 Статистика 2025]
       → Финишёры, медиана, распределение
    → [📝 Регистрация]
       → Ссылка на athletex.kz
```

**Критерий готовности:** Полный flow в боте работает.

### Задача 3: Bot keyboards

**Файл:** `bot/keyboards/races.py`

- `races_calendar_keyboard()` — список гонок (inline buttons)
- `race_card_keyboard(race_id)` — действия с гонкой
- `race_distances_keyboard(race_id)` — выбор дистанции (если несколько)

### Задача 4: FSM states

**Файл:** `bot/states/races.py`

```python
class RaceStates(StatesGroup):
    waiting_for_pace = State()       # Ввод темпа (базовый прогноз)
    waiting_for_name = State()       # Ввод имени (поиск в результатах)
```

### Задача 5: Регистрация в боте

- Добавить router в `bot/main.py`
- Добавить кнопку "Гонки" в главное меню (если есть)
- Добавить API client в `bot/services/clients/races.py`

## Порядок реализации

1. Задача 1 — API endpoints
2. Задача 5 — регистрация router + API client
3. Задача 4 — FSM states
4. Задача 3 — keyboards
5. Задача 2 — handlers (основная работа)

## Масштабирование на другие гонки

После Alpine Race — добавление новой гонки:
1. Спарсить CLAX → JSON (скрипт из Фазы 0): `python backend/scripts/parse_race.py --url ... --save content/races/results/...`
2. Добавить GPX дистанции в `content/races/gpx/`
3. Добавить запись в `content/races/races.yaml`
4. Код не меняется

Горные гонки 2026 для добавления:
- Amangeldy Race (17-18 янв) — прошла
- Ak Bulak Night (21 фев) — прошла
- **Alpine Race (1 мар)** — MVP
- Tengri Ultra (1-3 мая)
- Tau Jarys (27 июн)
- Irbis Race (6 сен)
- Salomon Trail (18 окт)

## Что НЕ делаем в этой фазе

- Race cards / генерация картинок для шеринга (отдельная задача)
- Автоматический матчинг пользователя (сохранение race_name в БД)
- Прогресс год к году (автоматический)
- Push-уведомления о предстоящих гонках
- Шоссейные гонки (только горные с GPX)
- Лендинг / веб-портал
