# Backlog: HikingService — полноценный оркестратор по образцу TrailRunService

**Дата:** 2026-02-14
**Приоритет:** Низкий
**Блокируется:** Завершением hiking effort levels (минимальный подход)

---

## Проблема

Текущий подход к hiking prediction:
- `PredictionService.predict_hike()` — монолитный метод с примитивной персонализацией
- `ComparisonService.compare_route()` — отдельный сервис для сравнения методов
- Effort levels добавлены в `ComparisonService`, но не в основной predict flow
- Нет per-segment effort расчёта (effort применяется к totals, а не к каждому сегменту)
- Нет fatigue per-effort
- Нет run/hike threshold (в хайкинге не нужен, но может быть полезен для scrambling detection)

Trail running имеет полноценный `TrailRunService` с:
- Сегментным расчётом с effort accumulators
- Per-segment fatigue
- Все 3 effort levels для каждого сегмента
- Totals dict с детальной разбивкой
- Profile info блок

## Что нужно сделать

1. **Создать `HikingService`** в `backend/app/features/hiking/service.py`:
   - По образцу `TrailRunService`
   - Tobler + Naismith как base calculators (вместо GAP)
   - 3 effort levels для персонализации
   - Per-segment fatigue через `HikeFatigueService`
   - Totals dict с `tobler_personalized_{fast,moderate,easy}`, `naismith_personalized_{...}`

2. **Обновить API endpoint** для hiking prediction:
   - Использовать `HikingService` вместо `PredictionService`
   - Или добавить новый endpoint `/predict/hike/v2`

3. **Обновить бот handler** для hiking:
   - По образцу `format_trail_run_result()`
   - С effort breakdown per Tobler и Naismith

4. **Перенести multipliers** (experience, backpack, group) в `HikingService`:
   - Сейчас они в `PredictionService` — нужно перенести или интегрировать

## Зависимости

- Hiking effort levels (минимальный подход) завершён
- `HikePersonalizationService` уже поддерживает effort levels
- `HikeFatigueService` уже существует в `features/hiking/calculators/fatigue.py`

## Оценка

- ~500-700 строк нового кода
- Требует обновления бот-хендлеров, API, тестов
- Рекомендуется разбить на 3-4 фазы
