# Система калибровки расчётов (Backtesting)

**Дата:** 2026-02-03
**Статус:** Планирование

---

## Цель

Инструмент для проверки точности формул расчёта времени на реальных данных Strava.

**Отвечает на вопросы:**
1. Какой метод (Strava GAP / Minetti / S+M / Personalized) точнее?
2. Есть ли системный bias (занижаем/завышаем)?
3. На каких градиентах формулы ошибаются больше всего?

---

## Архитектура

```
backend/tools/calibration/
├── __init__.py
├── virtual_route.py    # Фаза 1: Конвертация splits → segments
├── calculators.py      # Фаза 2: Адаптеры калькуляторов
├── metrics.py          # Фаза 3: Расчёт MAE, MAPE, Bias
├── service.py          # Фаза 4: Основной сервис
├── report.py           # Фаза 5: Отчёты
└── cli.py              # Фаза 5: CLI интерфейс
```

---

## Фазы реализации

| Фаза | Файл плана | Строк кода | Проверка |
|------|------------|------------|----------|
| 1 | [phase_1_structure.md](phase_1_structure.md) | ~80 | Unit test: splits → segments |
| 2 | [phase_2_calculators.md](phase_2_calculators.md) | ~100 | Прогон одной активности |
| 3 | [phase_3_metrics.md](phase_3_metrics.md) | ~70 | Расчёт метрик на mock данных |
| 4 | [phase_4_service.md](phase_4_service.md) | ~120 | Полный прогон на твоих данных |
| 5 | [phase_5_reports_cli.md](phase_5_reports_cli.md) | ~150 | CLI работает, отчёт генерируется |

**Всего:** ~520 строк, но по частям с проверкой каждой.

---

## Git-стратегия

```
feature/trail-run-calculations  (текущая)
         │
         └── feature/calibration-tools  (новая ветка)
                    │
                    ├── commit: "feat(tools): phase 1 - virtual route builder"
                    ├── commit: "feat(tools): phase 2 - calculator adapters"
                    ├── commit: "feat(tools): phase 3 - metrics calculation"
                    ├── commit: "feat(tools): phase 4 - backtesting service"
                    └── commit: "feat(tools): phase 5 - reports and CLI"
```

После завершения — merge в `feature/trail-run-calculations`.

---

## Режимы калибровки

| Режим | Активности | Min D+ | Основные методы |
|-------|-----------|--------|-----------------|
| `trail-run` | TrailRun, Run | 200м | Strava GAP, Minetti GAP, S+M GAP, Personalized |
| `hiking` | Hike | 100м | Tobler, Naismith, Personalized |

---

## Использование (после реализации)

```bash
# Из корня backend/
cd backend

# Trail running калибровка (по умолчанию)
python -m tools.calibration.cli backtest --user-id <user_id>

# Hiking калибровка
python -m tools.calibration.cli backtest --user-id <user_id> --mode hiking

# С переопределением фильтров
python -m tools.calibration.cli backtest \
    --user-id <user_id> \
    --mode trail-run \
    --min-elevation 300

# Экспорт в JSON
python -m tools.calibration.cli backtest \
    --user-id <user_id> \
    --output json
```

---

## Пример вывода

```
══════════════════════════════════════════════════════════════
                    BACKTESTING REPORT
══════════════════════════════════════════════════════════════

User: abc-123 | Activities: 15 | Distance: 127 km | D+: 4,230 m

Method               │ MAE (min) │  MAPE  │  Bias
─────────────────────┼───────────┼────────┼────────
Strava GAP           │    8.2    │  6.1%  │  -4.2%
Minetti GAP          │   12.1    │  9.3%  │  -8.1%
Strava+Minetti       │    9.5    │  7.2%  │  -5.8%
🎯 Personalized      │    4.1    │  3.2%  │  +0.8%

🏆 Best method: Personalized (MAPE 3.2%)
══════════════════════════════════════════════════════════════
```
