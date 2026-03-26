# Шаг 5.5: Race Insights — план реализации

## Обзор

5 шагов, каждый в отдельной ветке от `web-portal`.

| Шаг | Ветка | Что делаем | Зависит от |
|-----|-------|-----------|------------|
| **5.5a** | `web-portal-step-5.5a` | Бэкенд: таблица runners (ID), DNF (модель + CLAX парсер), stats extensions, search percentiles, runner profile endpoint, season stats, global search | 3, 5 |
| **5.5b** | `web-portal-step-5.5b` | Страница дистанции: TimeHistogram (div), GenderChart, CategoryBars, ClubRanking, DNF в StatsCard и ResultsTable | 5.5a |
| **5.5c** | `web-portal-step-5.5c` | Страница бегуна: `/runners/:runnerId`, RunnerSummary, RunnerResultCard, PercentileBadge, клик на имя | 5.5a |
| **5.5d** | `web-portal-step-5.5d` | Search insights: персентили в поиске, Y-o-Y прогресс, сравнение 2-4 участников (ComparePanel) | 5.5a, 5.5c |
| **5.5e** | `web-portal-step-5.5e` | Homepage polish: SeasonStatsBox с реальными данными, RaceCard с финишёрами, TopClubsPreview, two-col layout | 5.5a, 5.5b |

## Порядок внутри 5.5a (бэкенд)

```
A1  Таблица runners + миграция + заполнение
A2  DNF: status в модели, CLAX парсер, миграция, перепарсинг
A3  Stats extensions (gender/category/club)
A4  API schemas (name_normalized, runner_id, status в response)
A5  Search с персентилями
A6  total_finishers в RaceSchema
A7  Runner Profile endpoint (по runner_id)
A8  Season stats endpoint
A9  Global search runners
```

## Что видит пользователь после каждого шага

**5.5a** — Визуально ничего (API готов, DNF в БД, runners в таблице).

**5.5b** — На странице дистанции: гистограмма времён, pie M/F, бары категорий, рейтинг клубов, DNF в stats и таблице результатов.

**5.5c** — Клик на имя → страница бегуна `/runners/42` со всеми гонками, персентилями, динамикой.

**5.5d** — Поиск "Найди себя" показывает персентили и Y-o-Y прогресс. Чекбоксы → "Сравнить" → таблица.

**5.5e** — Homepage: "1847 бегунов / 18 клубов", карточки с финишёрами, секция клубов.

## Ключевые изменения vs исходный план

1. **Таблица `runners`** — отдельная сущность с auto-increment ID. URL профиля: `/runners/{id}` (не name_normalized)
2. **DNF: backward compat** — колонка `status` добавляется рядом с `over_time_limit`, старое поле удалится позже
3. **DNF: только CLAX** — AM парсер оставляем как есть (DNF в AM — отдельная задача)
4. **A9 в порядке реализации** — Global search включён в основной flow
5. **`best_time` в ClubStats** — возвращаем и `best_time_s` (int) и `best_time` (str)
6. **`name_normalized` + `runner_id`** — оба поля в RaceResultSchema

## Детали по каждому шагу

- [step_5_5a_backend.md](step_5_5a_backend.md) — бэкенд
- [step_5_5b_demographics_clubs.md](step_5_5b_demographics_clubs.md) — демография + клубы + DNF на фронтенде
- [step_5_5c_runner_profile.md](step_5_5c_runner_profile.md) — страница бегуна (по runner_id)
- [step_5_5d_search_compare.md](step_5_5d_search_compare.md) — search insights + сравнение
- [step_5_5e_homepage_polish.md](step_5_5e_homepage_polish.md) — homepage polish

## Бэклог

Подробный бэклог — в основном файле [step_5_5_race_insights.md](../step_5_5_race_insights.md) (секция "Бэклог").
