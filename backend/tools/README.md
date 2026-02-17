# Development Tools

Инструменты разработки для GPX Predictor. Не являются частью production кода.

---

## Calibration (Backtesting)

Инструмент для проверки точности формул расчёта времени на реальных данных Strava.

### Использование

```bash
cd backend

# Trail running калибровка (по умолчанию)
python -m tools.calibration.cli backtest --user-id <user_id>

# Hiking калибровка
python -m tools.calibration.cli backtest --user-id <user_id> --mode hiking

# С пониженными фильтрами (для пользователей без горных активностей)
python -m tools.calibration.cli backtest --user-id <user_id> --min-elevation 50

# Ограничить количество активностей
python -m tools.calibration.cli backtest --user-id <user_id> --limit 10

# Экспорт в JSON
python -m tools.calibration.cli backtest --user-id <user_id> --output json --output-dir ./reports

# Экспорт всё (console + json + csv)
python -m tools.calibration.cli backtest --user-id <user_id> --output all

# Список активностей пользователя
python -m tools.calibration.cli list-activities --user-id <user_id>
```

### Режимы

| Режим | Активности | Min D+ | Основные методы |
|-------|-----------|--------|-----------------|
| `trail-run` | TrailRun, Run | 200м | Strava GAP, Minetti GAP, S+M GAP, Personalized |
| `hiking` | Hike | 100м | Tobler, Naismith, Personalized |

### Метрики

- **MAE** — Mean Absolute Error (средняя ошибка в минутах)
- **MAPE** — Mean Absolute Percentage Error (средняя ошибка в %)
- **Bias** — систематическое отклонение (+завышаем, -занижаем)

### Пример вывода

```
======================================================================
                BACKTESTING REPORT (Trail Running)
======================================================================

User ID:        3d535116...
Activities:     5 (skipped: 0)
Total distance: 45.2 km
Total D+:       1,230 m

----------------------------------------------------------------------
                    PRIMARY METHODS
----------------------------------------------------------------------

Method               | MAE (min) |  MAPE  |  Bias  | Samples
---------------------|-----------|--------|--------|--------
Strava GAP           |       8.2 |   6.1% |  -4.2% |       5
Minetti GAP          |      12.1 |   9.3% |  -8.1% |       5
Strava+Minetti       |       9.5 |   7.2% |  -5.8% |       5
Personalized         |       4.1 |   3.2% |  +0.8% |       5

Best method: personalized (MAPE 3.2%)
======================================================================
```

### Структура

```
backend/tools/calibration/
├── cli.py            # CLI интерфейс
├── service.py        # BacktestingService
├── calculators.py    # Адаптеры калькуляторов
├── metrics.py        # Расчёт MAE, MAPE, Bias
├── report.py         # Генерация отчётов
└── virtual_route.py  # Конвертация splits → segments
```
