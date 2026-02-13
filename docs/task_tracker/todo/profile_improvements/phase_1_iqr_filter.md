# Фаза 1: IQR фильтрация аномалий в профиле

**Сложность:** Низкая
**Эффект:** Высокий
**Зависимости:** Фаза 0 (shared gradients, CLI recalculate)
**Scope:** Только trail running (hiking — позже, после обкатки)
**Оценка:** ~50-80 строк изменений

---

## Цель

При расчёте run-профиля отфильтровывать аномальные сплиты (ходьба, скремблинг, остановки) используя IQR метод — отдельно для каждой категории градиента.

## Почему IQR, а не threshold

Протестировали оба подхода:

| Метод | Steep up (>+15%) | Mod up (+8/+15%) | Проблема |
|-------|-----------------|------------------|----------|
| Threshold (flat_pace*1.8=12.3) | Вырезал **98%** данных | Вырезал **57%** | Уничтожает данные на подъёмах |
| IQR | Вырезал **5%** | Вырезал **8%** | Адекватно |

## Что менять

### Файл: `backend/app/services/user_profile.py`

#### Шаг 1: Увеличить PACE_MAX_THRESHOLD_RUN

```python
# Было:
PACE_MAX_THRESHOLD_RUN = 15.0   # min/km - slower than this is walking

# Стало:
PACE_MAX_THRESHOLD_RUN = 30.0   # min/km - санитарный порог (GPS-ошибки, остановки)
```

Старое значение 15.0 отрезало нормальные данные на крутых подъёмах (pace 16-25 min/km — это нормальный бег в гору). Новое 30.0 — двойная защита: сначала отрезаем явный мусор (>30 min/km ≈ 2 км/ч — фактически стояние), потом IQR чистит оставшиеся аномалии в каждой категории.

#### Шаг 2: В методе `calculate_run_profile_with_splits`

**Добавить функцию IQR фильтрации:**

```python
def filter_outliers_iqr(paces: list[float]) -> list[float]:
    """
    Remove outliers using IQR method.

    Interquartile Range (IQR) = Q3 - Q1.
    Outliers: values below Q1 - 1.5*IQR or above Q3 + 1.5*IQR.
    Applied per gradient category — each category has its own thresholds.
    """
    if len(paces) < 4:
        return paces  # too few data points for IQR

    q1, _, q3 = statistics.quantiles(paces, n=4)  # exact quartiles with interpolation
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return [p for p in paces if lower <= p <= upper]
```

**Применить перед расчётом среднего:**

```python
# Сейчас:
for category, paces in category_paces.items():
    profile[category] = mean(paces)

# Станет:
for category, paces in category_paces.items():
    filtered = filter_outliers_iqr(paces)
    profile[category] = mean(filtered)
    # Сохраняем filtered count для диагностики
    logger.info(f"{category}: {len(paces)} → {len(filtered)} samples "
                f"({len(paces) - len(filtered)} outliers removed)")
```

### ВАЖНО: только trail running

Hiking профиль (`calculate_profile_with_splits`) пока не трогаем. Обкатаем IQR на trail running (107 runs, много данных), потом применим для hiking.

## Процедура

```bash
# 1. Сохранить snapshot текущего профиля (Фаза 0 CLI)
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16 \
    --reason "phase_1_before"

# 2. Применить IQR фильтрацию (код)

# 3. Пересчитать профиль
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16 \
    --reason "phase_1_iqr"

# 4. Прогнать калибровку
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16 \
    --min-elevation 100
```

## Ожидаемый результат

На основе экспериментальных данных (сессия 2026-02-03):

| Категория | До (mean) | После IQR (mean) | Изменение |
|-----------|-----------|-------------------|-----------|
| Steep down | 13.09 | ~10.37 | -20.8% |
| Moderate down | 9.28 | ~7.96 | -14.2% |
| Gentle down | 8.16 | ~7.06 | -13.5% |
| Flat | 6.87 | ~6.39 | -7.0% |
| Gentle up | 10.03 | ~9.17 | -8.6% |
| Moderate up | 14.21 | ~12.85 | -9.6% |
| Steep up | 21.87 | ~20.79 | -4.9% |

Основной эффект — на спусках (steep/moderate down), где аномалии от ходьбы/скремблинга сильнее всего завышали среднее.

## Чеклист

- [x] `PACE_MAX_THRESHOLD_RUN` увеличен с 15.0 до 30.0 min/km
- [x] `filter_outliers_iqr()` добавлена
- [x] Применена в `calculate_run_profile_with_splits()`
- [x] Snapshot "before" сохранён
- [x] Профиль пересчитан
- [x] Snapshot "after" сохранён
- [x] Калибровка прогнана, результаты записаны в `calibration_results.md`
