# Фаза 4: Валидация и калибровка

**Сложность:** Низкая
**Зависимости:** Выполняется после каждой фазы (0-3)

---

## Цель

После каждой фазы прогонять калибровку на тестовых активностях, фиксировать результаты, сравнивать с baseline. Каждый пересчёт профиля сохраняет snapshot.

## Тестовые активности

| ID | Название | Тип | Дист. | D+ | Время |
|----|----------|-----|-------|-----|-------|
| 494 | Morning Asphalt Sky Run | Road | 21.7km | 928m | 164 min |
| 570 | Irbis Race / Talgar | Trail race | 20.2km | 2417m | 269 min |
| 563 | Irbis / Talgar Check #2 | Fast hiking | 20.6km | 2426m | 328 min |

**Примечание:** Effort для теста не фиксируется заранее. Калибровка показывает все 3 effort levels — по результатам определяем, какой ближе к факту.

## Процедура валидации

### После каждой фазы:

```bash
cd backend

# 1. Сохранить snapshot (если ещё не сохранён при пересчёте)
python -m tools.calibration.cli recalculate-profile \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16 \
    --reason "phase_N_description"

# 2. Прогнать калибровку
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16 \
    --min-elevation 100

# 3. После Фазы 3: прогнать — все 3 effort levels для каждой активности
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 494   # покажет race/moderate/easy
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 570
python -m tools.calibration.cli backtest \
    --user-id 2f07778a-... --activity-id 563

# 4. Записать результаты в calibration_results.md
```

## Критерии успеха

### После Фаз 0-2 (без effort level, используется avg/P50)

| Активность | Текущий лучший | Цель |
|------------|---------------|------|
| Asphalt Sky Run | Minetti -0.1% | Personalized < 15% |
| Irbis Race | Personalized -13.6% | Personalized < 10% |
| Talgar Check #2 | Personalized -28.1% | Personalized < 25% |

### После Фазы 3 (с effort level)

Для каждой активности показываем все 3 effort — определяем лучший по факту:

| Активность | Тип | Race (P25) | Moderate (P50) | Easy (P75) | Лучший |
|------------|-----|-----------|----------------|-----------|--------|
| Asphalt Sky Run | Road | ? | ? | ? | Ожидаем Race |
| Irbis Race | Trail race | ? | ? | ? | TBD |
| Talgar Check #2 | Fast hiking | ? | ? | ? | Ожидаем Easy |

**Цель:** хотя бы один из effort levels даёт ошибку < 10% для каждой активности.

## Profile Snapshots — обязательно!

Каждый пересчёт профиля = snapshot в БД. Это позволяет:
- Видеть динамику: baseline → phase_1_iqr → phase_2_percentiles → ...
- Откатиться если что-то пошло не так
- Сравнивать "до/после" по конкретным категориям

### Ожидаемая цепочка snapshots

```
1. baseline                     — текущий профиль (59 activities, 7 categories, mean)
2. phase_0_recalc               — пересчёт на 107 activities (7 categories, mean)
3. phase_1_iqr                  — IQR фильтрация (7 categories, IQR mean)
4. phase_2_categories_percents  — 11 categories + P25/P50/P75
5. phase_3_effort               — после тестов с effort levels (если были корректировки)
```

## Результаты фиксировать в `calibration_results.md`

Заполнять таблицы после каждой фазы — шаблоны уже готовы в файле.
