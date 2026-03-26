# Шаг 5.5: Race Insights — аналитика и визуализации

## Цель

Добавить уникальную аналитику на страницу гонки, которой нет в Strava/Garmin/ITRA.
Цель — чтобы участники и клубы регулярно возвращались на портал.

**Зависит от:** Шаги 1-3, 5 (дизайн-система, страница гонки, поиск).

---

## Подшаги реализации

Детальные планы в папке [step_5_5_race_insights/](step_5_5_race_insights/):

| Шаг | Файл | Описание | Ветка | Зависит от |
|-----|------|----------|-------|------------|
| 5.5a | [step_5_5a_backend.md](step_5_5_race_insights/step_5_5a_backend.md) | Бэкенд: таблица `runners` (ID), DNF (модель + CLAX), stats extensions, search percentiles, runner profile, season stats, global search | `web-portal-step-5.5a` | 3, 5 |
| 5.5b | [step_5_5b_demographics_clubs.md](step_5_5_race_insights/step_5_5b_demographics_clubs.md) | Страница дистанции: TimeHistogram, GenderChart, CategoryBars, ClubRanking, DNF в StatsCard + ResultsTable | `web-portal-step-5.5b` | 5.5a |
| 5.5c | [step_5_5c_runner_profile.md](step_5_5_race_insights/step_5_5c_runner_profile.md) | Страница бегуна `/runners/:runnerId`: сводка, все гонки с персентилями, динамика | `web-portal-step-5.5c` | 5.5a |
| 5.5d | [step_5_5d_search_compare.md](step_5_5_race_insights/step_5_5d_search_compare.md) | Search insights: персентили в поиске, Y-o-Y прогресс, сравнение 2-4 участников | `web-portal-step-5.5d` | 5.5a, 5.5c |
| 5.5e | [step_5_5e_homepage_polish.md](step_5_5_race_insights/step_5_5e_homepage_polish.md) | Homepage polish: SeasonStatsBox с реальными данными, RaceCard с финишёрами, TopClubsPreview, two-col layout | `web-portal-step-5.5e` | 5.5a, 5.5b |

---

## Что видит пользователь после каждого шага

**5.5a** — Визуально ничего. API готов, DNF в БД, таблица `runners` с ID.

**5.5b** — На странице дистанции: гистограмма времён, pie M/F, бары категорий, рейтинг клубов, DNF в stats и таблице результатов.

**5.5c** — Клик на имя → `/runners/42` — страница бегуна со всеми гонками, персентилями, динамикой.

**5.5d** — Поиск "Найди себя" показывает персентили и Y-o-Y прогресс. Чекбоксы → "Сравнить" → таблица.

**5.5e** — Homepage: "1847 бегунов / 18 клубов", карточки с финишёрами, секция top-5 клубов.

---

## Заметки из шага 4 (Homepage)

Эти элементы были в мокапе homepage, но не вошли в Step 4. Реализуются в **5.5e**:

1. **SeasonStatsBox — реальные данные:** "6 гонок / 1847 бегунов / 18 клубов" вместо "16 гонок / 47 editions / 203 дистанции"
2. **Двухколоночный layout:** клубы слева, гонки справа
3. **Grid гонок в 2 колонки:** `repeat(auto-fill, minmax(240px, 1fr))`
4. **Селектор сезонов:** уже реализован в Step 4, в 5.5e — более богатая статистика
5. **Более информативные RaceCard:** количество финишёров + дата ближайшего edition
6. **Количество финишёров:** новое поле `total_finishers` в API `GET /races`

---

## Бэклог (не в MVP)

### Нормализация возрастных категорий (сквозная аналитика)

Сейчас категории нестандартизированы (каждая гонка свои: `M_30-39`, `M_30`, `Senior`...).
Для сквозного сравнения между гонками нужно:

1. **Вычислять единую возрастную группу** из `birth_year` + `race_year`:
   - 18-29, 30-39, 40-49, 50-59, 60+
2. **Хранить как отдельное поле** `normalized_age_group` (не заменять `category`)
3. Позволяет: кросс-гоночный рейтинг по возрастным группам, сезонная статистика

**Блокер:** `birth_year` есть не у всех парсеров (Almaty Marathon — нет). Нужна доработка парсеров.

### Другие фичи бэклога

| Фича | Что нужно | Приоритет |
|------|----------|-----------|
| Кросс-гоночное сравнение | Race difficulty score + нормализация | Средний |
| Топ-N сезонный рейтинг | Агрегация по всем гонкам за сезон | Средний |
| Клубный dashboard | Отдельная страница `/clubs/:clubId` | Средний |
| Race Flow / Position Trace | Split-данные по чекпоинтам | Низкий |
| Fatigue Curve | GPS-треки участников (не гонки) | Низкий |
| Weather-adjusted performance | Погодные API + исторические данные | Низкий |
| Aid Station Dwell Time | GPS-треки участников | Низкий |
| Climb/Descent efficiency | GPX трек дистанции + время участника | Низкий (1 GPX пока) |
| Predict page redesign | Обновить стили PredictPage под дизайн-систему ayda.run + возможный редирект на Telegram-бота | Средний |
