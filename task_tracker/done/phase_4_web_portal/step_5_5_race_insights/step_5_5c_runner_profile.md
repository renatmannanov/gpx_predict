# Шаг 5.5c: Страница бегуна (Runner Profile)

## Цель

Публичная страница бегуна `/runners/:runnerId`. При клике на имя в любой таблице — переход на профиль с кросс-гоночными результатами.

**Ветка:** `web-portal-step-5.5c`
**Зависит от:** 5.5a (runner profile endpoint, таблица runners).

---

## Что делать

### C1. RunnerProfilePage

**Создать** `frontend/src/pages/RunnerProfilePage.tsx`:

```
┌─────────────────────────────────────────────────┐
│  ← Назад                                        │
│                                                  │
│  Baikashev Shyngys                              │
│  RUNFINITY · M_20-29                            │
│                                                  │
│  ┌──────────┬──────────┬──────────┐             │
│  │    8     │  top-15% │  3 года  │             │
│  │  гонок   │  средний │  на сцене│             │
│  └──────────┴──────────┴──────────┘             │
│                                                  │
│  ── 2025 ──────────────────────────             │
│  [RunnerResultCard]                              │
│  [RunnerResultCard]                              │
│  ── 2024 ──────────────────────────             │
│  [RunnerResultCard]                              │
└─────────────────────────────────────────────────┘
```

**Логика:**
1. `useParams()` → `runnerId` (число)
2. `useQuery(['runner', runnerId], () => fetchRunnerProfile(runnerId))`
3. Группировка results по year (year DESC)
4. Loading / Error / NotFound states
5. `document.title` = "{name} — ayda.run"
6. Back link: `useNavigate(-1)` или `/races`

### C2. RunnerSummary

**Создать** `frontend/src/components/runners/RunnerSummary.tsx` + `.css`:

- Имя: h1
- Клуб + категория: dim, под именем (если есть)
- 3 stat числа (grid, стиль StatsCard):
  - total_races
  - median_percentile → "top-X%"
  - years_active

### C3. RunnerResultCard

**Создать** `frontend/src/components/runners/RunnerResultCard.tsx` + `.css`:

```
┌─────────────────────────────────────────────────┐
│  Alpine Race · Skyrunning 21km          →       │  ← ссылка на гонку
│  0:54:12 · #2 из 245 · top-1%                  │
│  ▲ -1:28 vs 2024                                │  ← динамика
└─────────────────────────────────────────────────┘
```

- Первая строка: race_name + distance_name (ссылка на `/races/:raceId`)
- Вторая строка: время, место/total, PercentileBadge
- Третья строка: динамика vs предыдущий год на той же race+distance
  - `▲ -1:28` = улучшение (зелёный), `▼ +2:05` = ухудшение (красный)
  - Вычисляется на фронтенде из списка results
- DNF-результаты: вместо времени показать "DNF", без места и персентиля

```typescript
interface RunnerResultCardProps {
  result: RunnerRaceResult;
  previousResult?: RunnerRaceResult;  // для динамики
}
```

### C4. PercentileBadge (shared компонент)

**Создать** `frontend/src/components/shared/PercentileBadge.tsx` + `.css`:

Бейдж "top-15%" с цветовым кодированием:
- top-10%: зелёный (яркий)
- top-25%: зелёный (обычный)
- top-50%: жёлтый
- top-75%: оранжевый
- top-100%: dim

```typescript
interface PercentileBadgeProps {
  percentile: number;  // 0-100, lower = better
  compact?: boolean;   // true = только "15%", false = "top-15%"
}
```

Используется в: RunnerResultCard, SearchResults (5.5d), ClubRanking (5.5b).

### C5. Навигация — клик на имя → профиль по runner_id

**Изменить** `frontend/src/components/races/ResultsTable.tsx`:

Имя участника → ссылка на `/runners/${result.runner_id}`:

```tsx
{result.runner_id ? (
  <Link to={`/runners/${result.runner_id}`}>{result.name}</Link>
) : (
  <span>{result.name}</span>
)}
```

Данные `runner_id` приходят из обновлённого API (шаг 5.5a, A4).

### C6. API client

**Изменить** `frontend/src/api/races.ts`:

```typescript
export async function fetchRunnerProfile(runnerId: number): Promise<RunnerProfileResponse> {
  const { data } = await api.get(`/runners/${runnerId}`);
  return data;
}
```

### C7. Route в App.tsx

**Изменить** `frontend/src/App.tsx`:

```tsx
<Route path="/runners/:runnerId" element={<RunnerProfilePage />} />
```

### C8. TypeScript types

**Изменить** `frontend/src/types/races.ts`:

```typescript
interface RunnerProfile {
  id: number;
  name: string;
  name_normalized: string;
  club: string | null;
  category: string | null;
  gender: string | null;
}

interface RunnerRaceResult {
  race_id: string;
  race_name: string;
  distance_name: string;
  distance_km: number | null;
  year: number;
  time_s: number;
  time_formatted: string;
  place: number;
  total_finishers: number;
  percentile: number;
  category: string | null;
  club: string | null;
  status: string;
}

interface RunnerProfileResponse {
  profile: RunnerProfile;
  results: RunnerRaceResult[];
  total_races: number;
  years_active: number;
  median_percentile: number | null;
}
```

---

## Проверка

1. Открыть `/races/alpine_race_kz` → кликнуть на имя в таблице результатов
2. ✅ Переход на `/runners/42` (по runner_id)
3. ✅ Шапка: имя, клуб, категория
4. ✅ 3 числа: количество гонок, средний персентиль, лет на сцене
5. ✅ Результаты сгруппированы по годам (2025 сверху)
6. ✅ Каждый результат: гонка (ссылка), время, место, персентиль (PercentileBadge)
7. ✅ Динамика: "▲ -1:28 vs 2024" для повторных гонок
8. ✅ DNF-результаты: показаны как "DNF", без персентиля
9. ✅ Клик на гонку → возврат на `/races/:raceId`
10. ✅ Несуществующий ID → "Бегун не найден" + ссылка на `/races`
11. ✅ `document.title` = "Baikashev Shyngys — ayda.run"
12. ✅ Mobile: карточки читаемы, одна колонка
