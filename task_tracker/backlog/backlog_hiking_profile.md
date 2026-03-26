# Backlog: Hiking Profile Improvements

**Дата:** 2026-02-13
**Приоритет:** Средний
**Статус:** ➡️ Перенесено в `docs/task_tracker/todo/hiking_effort_levels/`
**Блокируется:** Завершением trail running profile improvements (Фазы 0-3) ✅ Завершено

---

## Проблема

Калибровка показала, что hiking-предикт работает плохо:

| Активность | Тип | Personalized Error |
|------------|-----|-------------------|
| Talgar trail check (21.4km, +2525m) | Hiking | **-49.6%** (сильно занижает) |

Hiking профиль имеет те же проблемы, что и trail running до улучшений:
- Нет IQR фильтрации аномалий
- Используется mean вместо median
- 7 категорий (или даже 3 legacy) — слишком грубо
- Нет перцентилей / effort levels
- Мало данных (3 hike, 4 walk)

## Что нужно сделать

После обкатки IQR + перцентилей + effort levels на trail running (107 runs):

1. **Применить IQR фильтрацию** к `calculate_profile_with_splits()` (hiking)
2. **Перевести на 11 категорий** (`classify_gradient()` вместо `classify_gradient_legacy()`)
3. **Добавить JSON поля** (`gradient_paces`, `gradient_percentiles`) в `UserHikingProfile`
4. **Добавить effort levels** в hiking prediction API
5. **Пересчитать hiking профиль** и прогнать калибровку

## Зависимости

- Trail running Фазы 0-3 завершены и валидированы
- `shared/gradients.py` уже создан (Фаза 0)
- `filter_outliers_iqr()` уже реализован (Фаза 1)
- JSON поля + перцентили уже обкатаны на Run (Фаза 2)

## Заметки

- У hiking значительно меньше данных (3-4 активности vs 107 runs) — IQR может быть менее эффективен
- Возможно стоит подождать больше hiking-активностей перед пересчётом
- Hiking и trail running используют разные калькуляторы-fallback (Tobler vs GAP)
