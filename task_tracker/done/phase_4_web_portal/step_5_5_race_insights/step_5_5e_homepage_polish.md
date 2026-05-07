# Шаг 5.5e: Homepage Polish — реальные данные и улучшенные карточки

## Цель

Обновить homepage: SeasonStatsBox с реальными цифрами (бегуны, клубы), RaceCard с количеством финишёров, two-col layout (клубы + гонки).

**Ветка:** `web-portal-step-5.5e`
**Зависит от:** 5.5a (season stats endpoint, total_finishers в RaceSchema), 5.5b (ClubRanking компонент для переиспользования).

---

## Что делать

### E1. Обновить SeasonStatsBox — реальные данные

**Изменить** `frontend/src/components/dashboard/SeasonStatsBox.tsx`:

Было (вычислено из Race[]):
```
6 гонок   42 дистанции   5 с рез.
```

Стало (из API `/api/v1/stats/season/{year}`):
```
6 гонок    1847 бегунов    18 клубов
```

**Логика:**
- `useQuery(['seasonStats', selectedYear], () => fetchSeasonStats(selectedYear))`
- Fallback на текущий расчёт из Race[] если API не доступен
- Числа: total_races, total_finishers (уникальные бегуны по runner_id), total_clubs

### E2. Обновить RaceCard — количество финишёров

**Изменить** `frontend/src/components/races/RaceCard.tsx`:

Было: `3 дистанции · 5 лет`
Стало: `245 финишёров · 3 дистанции · 5 лет` (если `total_finishers` есть)

Данные: `race.total_finishers` из обновлённого API (5.5a).

### E3. TopClubsPreview на homepage

**Создать** `frontend/src/components/dashboard/TopClubsPreview.tsx` + `.css`:

```
КЛУБЫ 2025
#1  SRG          42 бегуна   top-18%
#2  RUNFINITY    28 бегунов  top-25%
#3  TRC ALMATY   19 бегунов  top-35%
#4  ARR          15 бегунов  top-40%
#5  SPORTLIFE    12 бегунов  top-45%
```

Данные: из season stats API (`top_clubs`). Top-5 клубов, компактный стиль.

### E4. Two-col layout на homepage

**Изменить** `frontend/src/components/dashboard/RacesPreview.tsx` и `DashboardPage.tsx`:

```
┌──────────────────┬──────────────────────────────┐
│ КЛУБЫ 2025       │ ГОНКИ 2025     Все гонки →   │
│ #1 SRG      42   │ ┌────────┐ ┌────────┐        │
│ #2 RUNFINITY 28  │ │ card 1 │ │ card 2 │        │
│ #3 TRC       19  │ └────────┘ └────────┘        │
│                   │ ┌────────┐ ┌────────┐        │
│                   │ │ card 3 │ │ card 4 │        │
└──────────────────┴──────────────────────────────┘
```

Grid: `grid-template-columns: 280px 1fr` на desktop, single column на mobile.
Гонки: `repeat(auto-fill, minmax(240px, 1fr))`.
Если клубов нет → только гонки в полную ширину.

### E5. Обновить TypeScript types и API client

**Изменить** `frontend/src/types/races.ts`:

```typescript
interface SeasonStats {
  year: number;
  total_races: number;
  total_finishers: number;
  total_clubs: number;
  top_runners?: SeasonRunner[];
  top_clubs?: SeasonClub[];
}

interface SeasonClub {
  club: string;
  runner_count: number;
  avg_percentile: number;
}

interface SeasonRunner {
  name: string;
  name_normalized: string;
  runner_id: number;
  race_count: number;
  avg_percentile: number;
}

// Обновить Race
interface Race {
  // ... existing ...
  total_finishers?: number;
}
```

**Изменить** `frontend/src/api/races.ts`:

```typescript
export async function fetchSeasonStats(year: number): Promise<SeasonStats> {
  const { data } = await api.get(`/stats/season/${year}`);
  return data;
}
```

---

## Проверка

1. Открыть `localhost:5173/`
2. ✅ SeasonStatsBox: "6 гонок / 1847 бегунов / 18 клубов" (реальные данные)
3. ✅ Переключение года → данные обновляются
4. ✅ Секция клубов: top-5 слева
5. ✅ Секция гонок: карточки в 2 колонки справа
6. ✅ RaceCard: "245 финишёров · 3 дистанции · 5 лет"
7. ✅ Mobile: single column (клубы сверху, гонки снизу)
8. ✅ Если API не доступен → fallback на текущие данные
9. ✅ Если клубов нет → секция клубов скрыта, гонки full width

---

## Заметки

- Season stats: кэшировать на бэкенде (тяжёлый запрос с COUNT DISTINCT)
- Top runners: >= 3 гонок в сезоне, при равенстве — по avg_percentile
- Fallback гарантирует что homepage не сломается если endpoint упадёт
