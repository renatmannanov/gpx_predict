# Улучшение персонализированного профиля и расчётов (Trail Running)

**Дата:** 2026-02-03 (обновлён 2026-02-13)
**Статус:** Планирование
**Ветка:** `feature/profile-improvements` (от `feature/calibration-tools`)

---

## Контекст и проблема

Калибровка показала, что персонализированный метод расчёта работает плохо:

| Активность | Тип | Personalized Error |
|------------|-----|-------------------|
| Morning Asphalt Sky Run (21.7km, +928m) | Асфальт | **+35.8%** (завышает) |
| Irbis Race / Talgar (20.2km, +2417m) | Trail гонка | **-13.6%** (занижает) |
| Talgar trail check (21.4km, +2525m) | Hiking | **-49.6%** (сильно занижает) |

Для сравнения: Minetti GAP даёт -0.1% на асфальте и -17.2% на trail.

### Корневые причины

1. **Аномалии в данных:** В одном грейде (-10% to -12%) pace разброс от 4.47 до 36.86 min/km (в 8 раз)
2. **Среднее vs медиана:** Mean на спусках на 22-31% выше median из-за выбросов (ходьба/скремблинг)
3. **Один профиль на всё:** Асфальт и технический trail усредняются вместе — нет понятия "effort level"
4. **Профиль не пересчитан:** DB profile на 59 активностях, а загружено уже 107 Run
5. **Слишком широкие категории:** steep up (>+15%) и steep down (<-15%) объединяют power hike и скремблинг — pace от 11 до 55 min/km

### Экспериментальные результаты (сессия 2026-02-03)

**6 вариантов профиля протестированы:**

| Category | Raw Mean | Raw Median | IQR Mean | IQR Median |
|----------|----------|------------|----------|------------|
| Steep down (<-15%) | 13.09 | 10.70 | **10.37** | **10.21** |
| Mod down (-15/-8) | 9.28 | 7.08 | **7.96** | **6.93** |
| Gentle down (-8/-3) | 8.16 | 6.47 | **7.06** | **6.27** |
| Flat (-3/+3) | 6.87 | 6.40 | **6.39** | **6.30** |
| Gentle up (+3/+8) | 10.03 | 8.61 | **9.17** | **8.54** |
| Mod up (+8/+15) | 14.21 | 12.87 | **12.85** | **12.60** |
| Steep up (>+15%) | 21.87 | 19.82 | **20.79** | **19.77** |

**Threshold фильтр (flat_pace * 1.8 = 12.3 min/km) ОТКЛОНЁН:**
- Вырезает 57% moderate uphill и 98% steep uphill данных — слишком агрессивный

**IQR фильтр — рекомендуемый:**
- Вырезает 5-11% аномалий в каждой категории
- Адаптивный: свой порог для каждой категории

**Калибровка с IQR профилем:**

| Метод | Asphalt Sky Run | Irbis Race (trail) |
|-------|-----------------|--------------------|
| Minetti GAP | -8.2% | -23.9% |
| DB Current (old profile) | +16.3% | -20.0% |
| IQR Mean | +24.3% | **-7.6%** |
| IQR Median | +15.5% | -11.8% |

**Вывод:** IQR Mean лучший для trail (-7.6%), но завышает на асфальте (+24%). Нужны перцентили для разных effort levels.

### Данные для калибровки

```
User: 2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16
Activities synced: 170 / 391
Run with splits: 107 (106 with splits)
Flat pace (current): 6.85 min/km
```

Тестовые активности:
- **ID 494** — Morning Asphalt Sky Run (асфальт, 21.7km, +928m) — road test
- **ID 570** — Irbis Race / Talgar (trail гонка, 20.2km, +2417m) — trail race test
- **ID 563** — Irbis / Talgar Check #2 (fast hiking, 20.6km, +2426m) — hiking-style test

---

## Фазы реализации

| Фаза | Описание | Файл плана | Сложность | Эффект |
|------|----------|-----------|-----------|--------|
| 0 | Подготовка: shared gradients (сразу 11 категорий), CLI recalculate, profile snapshots | [phase_0_preparation.md](phase_0_preparation.md) | Низкая-Средняя | Инфраструктура |
| 1 | IQR фильтрация аномалий (trail running) | [phase_1_iqr_filter.md](phase_1_iqr_filter.md) | Низкая | Высокий |
| 2 | JSON профиль + перцентили P25/P50/P75 | [phase_2_categories_percentiles.md](phase_2_categories_percentiles.md) | Средняя | Высокий |
| 3 | Effort level (Race/Moderate/Easy) с конфигурируемыми перцентилями | [phase_3_effort_level.md](phase_3_effort_level.md) | Средняя | Высокий |
| 4 | Валидация и калибровка | [phase_4_validation.md](phase_4_validation.md) | Низкая | — |

### Ключевые решения (2026-02-13)

1. **JSON вместо колонок** — перцентили и pace хранятся в JSON полях, а не в отдельных колонках. Расширение категорий = ноль миграций.
2. **11 категорий вместо 7** — равномерные ~5% диапазоны. Нейминг: `{direction}_{lower}_{upper}` (например `up_8_12`, `down_23_over`). Граница extreme = 23% (не 22%), чтобы нейминг совпадал с edge case.
3. **avg_ поля сохраняются** — backward compatibility. JSON поля дополняют, не заменяют.
4. **Trail running first** — IQR и перцентили сначала для trail running, hiking позже (см. backlog).
5. **Profile snapshots** — перед каждым пересчётом сохранять snapshot для отслеживания динамики.
6. **Градиенты сразу в Phase 0** — `shared/gradients.py` создаётся сразу с 11 категориями (объединено из Phase 0 + Phase 2), чтобы не переписывать дважды. Phase 2 фокусируется на JSON полях и перцентилях.
7. **Конфигурируемые перцентили** — `EFFORT_PERCENTILES` вынесен в константы, можно подкрутить после калибровки (например race → P20) без изменения кода.
8. **Hiking профиль через classify_gradient_legacy()** — хайкинг продолжает писать в 7 legacy-категорий, JSON и 11 категорий — только для Run. Hiking получит позже.
9. **Без двойного IQR** — перцентили считаются на уже отфильтрованных данных, IQR не вызывается повторно внутри `calculate_percentiles()`.

### Дополнительные решения (ревью плана)

10. **PACE_MAX_THRESHOLD_RUN = 30** (не 45) — двойная защита: сначала отрезаем явный мусор (>30 min/km ≈ 2 км/ч), потом IQR чистит аномалии по категориям.
11. **`statistics.quantiles()`** вместо ручного `sorted[int(n*0.25)]` — точнее для малых выборок (интерполяция).
12. **API возвращает все 3 effort levels** — без query parameter. Пользователь видит Race/Moderate/Easy рядом и выбирает сам.
13. **Effort маппинг не фиксируется** — калибровка показывает все 3 варианта для каждой активности, лучший определяется по факту.
14. **Hiking improvements в backlog** — отдельная задача после обкатки trail running (см. `backlog/backlog_hiking_profile.md`).

---

## Связанные документы

- [calibration_results.md](calibration_results.md) — результаты калибровки (baseline + прогресс)
- [calibration_backlog.md](../../backlog/calibration_backlog.md) — выводы калибровки
- [ANOMALY_DETECTION_PLAN.md](../ANOMALY_DETECTION_PLAN.md) — план детекции аномалий (hiking, частично актуален)
- [ACCURACY_IMPROVEMENTS_PLAN.md](../../todo/ACCURACY_IMPROVEMENTS_PLAN.md) — реализованные улучшения (7 категорий, fatigue)

## Связанные backlog-задачи (не блокирующие)

Из `docs/task_tracker/backlog/`:
- **backlog_1.md:** Strava sync порядок загрузки (от новых к старым) — **актуально**
- **BACKLOG_2.md:** Profile History (snapshots) — **включено в Фазу 0**
- **calibration_backlog.md** — детальные выводы калибровки — **включено в этот план**
- **backlog_hiking_profile.md** — hiking profile improvements — **после обкатки trail running**
