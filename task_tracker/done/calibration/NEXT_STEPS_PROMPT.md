# Промпт для следующего агента: Подготовка данных для калибровки

## Контекст

Мы создали систему калибровки расчётов в `backend/tools/calibration/`. Она работает, но для тестирования нужны данные.

## Текущее состояние базы

```
User: 3d535116-92ab-4784-b2fc-404e28348531

Sync Status:
- Total synced: 28 активностей
- With splits: 9
- Initial sync complete: FALSE (!)

Activities:
- Run: 9 (8 with splits)
- TrailRun: 0
- Hike: 0

Trail Run candidates (D+ >= 100m): только 1

Profile: 5/7 категорий, на основе 8 активностей
```

## Проблема

Данных недостаточно для калибровки trail running формул:
1. Синхронизация не завершена
2. Нет TrailRun/Hike активностей
3. Почти нет активностей с набором высоты

## Задача

### Шаг 1: Проверить и исправить синхронизацию

1. Проверить почему `initial_sync_complete = False`
2. Посмотреть сколько активностей реально есть в Strava у пользователя
3. Если нужно — запустить полную ресинхронизацию

### Шаг 2: Убедиться что загружаются splits

Splits критичны для калибровки — без них нет данных по градиентам.

### Шаг 3: После синхронизации — прогнать калибровку

```bash
cd backend

# Посмотреть что загрузилось
python -m tools.calibration.cli list-activities --user-id 3d535116-92ab-4784-b2fc-404e28348531

# Запустить калибровку (с пониженным порогом если мало горных активностей)
python -m tools.calibration.cli backtest \
    --user-id 3d535116-92ab-4784-b2fc-404e28348531 \
    --mode trail-run \
    --min-elevation 50

# Экспорт результатов
python -m tools.calibration.cli backtest \
    --user-id 3d535116-92ab-4784-b2fc-404e28348531 \
    --output all \
    --output-dir ./reports
```

## Файлы для изучения

- Strava sync: `backend/app/features/strava/sync/`
- Sync status model: `backend/app/features/strava/models.py` → `StravaSyncStatus`
- Calibration CLI: `backend/tools/README.md`

## Ожидаемый результат

1. Полная синхронизация Strava (все активности + splits)
2. Backtesting report с достаточным количеством активностей
3. Понимание точности наших формул (MAPE, Bias по методам)
