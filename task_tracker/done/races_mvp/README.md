# Races MVP — модуль гонок для gpx-predictor

## Цель

CLI-инструмент для парсинга результатов гонок, матчинга с пользователем и прогнозирования времени. MVP — проверка на Alpine Race + данные Рената.

## Структура

```
gpx-predictor/
├── content/                        # Контент: данные, не код
│   └── races/
│       ├── races.yaml              # Каталог гонок
│       ├── gpx/                    # GPX файлы дистанций
│       │   └── alpine_race_skyrunning.gpx
│       └── results/                # Спарсенные результаты (JSON)
│           └── alpine_race_2025.json
│
├── backend/
│   ├── app/features/races/         # Код модуля (как features/hiking/)
│   │   ├── __init__.py
│   │   ├── models.py               # Dataclasses
│   │   ├── clax_parser.py          # Парсер CLAX XML
│   │   ├── stats.py                # Статистика
│   │   ├── catalog.py              # Загрузчик races.yaml
│   │   ├── matching.py             # Поиск по имени
│   │   └── service.py              # RaceService (Фаза 1)
│   └── scripts/
│       ├── parse_race.py           # CLI: парсинг CLAX
│       └── predict_race.py         # CLI: прогноз (Фаза 1)
│
└── bot/handlers/races.py           # Бот-интеграция (Фаза 2)
```

## Фазы

| Фаза | Файл | Описание | Статус |
|------|------|----------|--------|
| 0 | `phase_0_clax_parser.md` | Парсер CLAX + CLI просмотр | ✅ DONE |
| 1 | `phase_1_race_prediction.md` | Прогноз на гонку + сравнение с результатами | ✅ DONE |
| 2 | `phase_2_bot_integration.md` | Интеграция в Telegram-бота | ✅ DONE |
| 2.5 | `phase_2_5_personalization.md` | Персонализация (Strava через ayda_run API) | ⏸ позже |

**Продолжение:** `races_mvp_v2/` — клубы, дашборд, портал.

## Порядок реализации

Строго последовательно: 0 → 1 → 2. Каждая фаза самодостаточна и проверяема.

## Git стратегия

Каждая фаза — отдельная ветка от main:

```
main
 ├── feature/races-phase-0    # Парсер + CLI
 │   → PR → merge в main
 │
 ├── feature/races-phase-1    # Прогноз + каталог
 │   → PR → merge в main
 │
 └── feature/races-phase-2    # Бот-интеграция
     → PR → merge в main
```

Workflow:
1. Создать ветку `feature/races-phase-N` от main
2. Реализовать фазу, показать результат
3. Проверяем вместе, фиксим если нужно
4. Коммитим, мержим в main
5. Следующая фаза — новая ветка от обновлённого main

**Примечание:** docs/ в .gitignore — планы не коммитятся, только код и content/.

## Тестовые данные

**Alpine Race** — зимний скайраннинг, Шымбулак.
- Skyrunning: 4 км, +900м, 2200м → 3200м
- Тестовый пользователь: Ренат (есть Strava профиль в gpx_predictor)

## Ссылки на CLAX файлы

Заполни ссылки на результаты по годам:

```
alpine_race:
  2025: https://live.myrace.info/?f=bases/kz/2025/alpinrace2025/alpinrace2025.clax
  2024: https://live.myrace.info/?f=bases/kz/2024/alpinrace2024/alpra2024.clax
  2023: https://live.myrace.info/?f=bases/kz/2023/alpinerace2023/alpinerace2023.clax
  2022:
```

Другие гонки (добавлять по мере появления):

```
amangeldy_race:
  2026:
  2025:
  2024:

ak_bulak_night:
  2026:
  2025:

tengri_ultra:
  2025:
  2024:

tau_jarys:
  2025:
  2024:

irbis_race:
  2025:
  2024:

salomon_trail:
  2025:
  2024:
```

## GPX файлы дистанций

Положить сюда: `content/races/gpx/`

```
alpine_race_skyrunning.gpx:    [  ]  есть / нет
tengri_ultra_30km.gpx:         [  ]  есть / нет
irbis_race_20km.gpx:           [  ]  есть / нет
```
