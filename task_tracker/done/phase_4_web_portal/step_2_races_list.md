# Шаг 2: Страница списка гонок (`/races`)

## Цель

Grid карточек всех 16 гонок из API. Фильтр по типу (trail/road). Клик на карточку ведёт на страницу гонки.

**Зависит от:** Шаг 1 (дизайн-система, layout).

---

## Что делать

### 2.1 TypeScript интерфейсы

**Создать** `frontend/src/types/races.ts`:

Интерфейсы должны точно соответствовать Pydantic-схемам из `backend/app/api/v1/routes/races.py`:

```typescript
// === Список гонок ===

export interface RaceDistance {
  id: string;           // distance name used as ID
  name: string;
  distance_km: number | null;
  elevation_gain_m: number | null;
  start_altitude_m: number | null;
  finish_altitude_m: number | null;
  grade: string | null;
  has_gpx: boolean;
}

export interface RaceEdition {
  year: number;
  date: string | null;   // "2025-03-09"
  has_results: boolean;
  registration_url: string | null;
}

export interface Race {
  id: string;            // "alpine_race_kz"
  name: string;          // "Alpine Race"
  type: string | null;   // "trail_sky", "trail", "road", "ultra"
  location: string | null;
  distances: RaceDistance[];
  editions: RaceEdition[];
  next_date: string | null;  // ближайшая дата
}

// === Результаты ===

export interface TimeBucket {
  label: string;
  count: number;
  percent: number;
}

export interface RaceStats {
  finishers: number;
  best_time: string;     // "00:52:05"
  worst_time: string;
  median_time: string;
  p25_time: string;
  p75_time: string;
  time_buckets: TimeBucket[];
}

export interface RaceResult {
  name: string;
  name_local: string | null;
  time_s: number;
  time_formatted: string;
  place: number;
  category: string | null;
  gender: string | null;
  club: string | null;
  pace: string | null;
}

export interface DistanceResults {
  distance_name: string;
  distance_km: number | null;
  year: number;
  stats: RaceStats;
  results: RaceResult[];
}

// === Поиск ===

export interface SearchResult {
  year: number;
  result: RaceResult | null;
}
```

> **Сверка с бэкендом (races.py):** Типы выше точно соответствуют Pydantic-схемам.
> Добавлены поля, которых не было в первой версии плана:
> - `RaceDistance`: `start_altitude_m`, `finish_altitude_m`, `grade`
> - `RaceEdition`: `registration_url`
> - `Race`: `next_date`

### 2.2 API функции

**Создать** `frontend/src/api/races.ts`:

```typescript
import { api } from './client';
import type { Race, DistanceResults, SearchResult } from '../types/races';

export function fetchRaces(): Promise<Race[]> {
  return api.get<Race[]>('/races');
}

export function fetchRace(raceId: string): Promise<Race> {
  return api.get<Race>(`/races/${raceId}`);
}

export function fetchResults(raceId: string, year: number): Promise<DistanceResults[]> {
  return api.get<DistanceResults[]>(`/races/${raceId}/${year}/results`);
}

export function searchParticipant(raceId: string, name: string): Promise<SearchResult[]> {
  return api.get<SearchResult[]>(`/races/${raceId}/search?name=${encodeURIComponent(name)}`);
}
```

### 2.3 Хелпер для типа гонки

Добавить в `frontend/src/types/races.ts` или отдельный utils:

```typescript
export type RaceCategory = 'trail' | 'road' | 'other';

export function getRaceCategory(type: string | null): RaceCategory {
  if (!type) return 'other';
  if (type.includes('trail') || type.includes('sky') || type.includes('ultra'))
    return 'trail';
  if (type.includes('road') || type.includes('marathon'))
    return 'road';
  return 'other';
}

export function getRaceCategoryLabel(cat: RaceCategory): string {
  if (cat === 'trail') return 'Трейл';
  if (cat === 'road') return 'Шоссе';
  return 'Другое';
}
```

### 2.4 RaceFilters

**Создать** `frontend/src/components/races/RaceFilters.tsx`:

Сегментный контроль "Все / Трейл / Шоссе":
- Три кнопки в одной pill-обёртке
- Каждая кнопка показывает количество гонок в этой категории
- Активная кнопка: светлый фон `rgba(255,255,255,0.08)`, белый текст
- Неактивные: dim цвет

CSS уже есть в `components.css` (`.filter-bar`, `.filter-btn`, `.filter-btn.active`).

Props:
```typescript
interface RaceFiltersProps {
  selected: 'all' | 'trail' | 'road';
  counts: { all: number; trail: number; road: number };
  onChange: (filter: 'all' | 'trail' | 'road') => void;
}
```

### 2.5 RaceCard

**Создать** `frontend/src/components/races/RaceCard.tsx`:

Карточка гонки на основе `.card` из components.css:

Структура:
```
┌──────────────────────┐
│ TRAIL_SKY            │  ← тип badge (orange для trail, blue для road)
│ Alpine Race          │  ← название (bold, 15px)
│ Шымбулак             │  ← локация (dim, 12px)
│──────────────────────│
│ 3 дистанции · 5 лет  │  ← footer (dim, 12px)
│                   →  │
└──────────────────────┘
```

- Использовать `.card` класс из components.css (background, border, hover уже есть)
- Клик: `<Link to={/races/${race.id}}>` — вся карточка кликабельна
- Badge: использовать `.badge`, `.badge-trail` / `.badge-road` из components.css

Props:
```typescript
interface RaceCardProps {
  race: Race;
}
```

### 2.6 RacesPage

**Создать** `frontend/src/pages/RacesPage.tsx`:

Страница списка гонок:

```
┌─────────────────────────────────────────┐
│  page-eyebrow: "Athletex · MyRace"      │
│  h1: "Гонки"                            │
│  subtitle: "Все горные и шоссейные..."   │
│                                          │
│  [Все 16] [Трейл 12] [Шоссе 4]          │  ← RaceFilters
│                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐       │
│  │ card 1 │ │ card 2 │ │ card 3 │       │  ← grid
│  └────────┘ └────────┘ └────────┘       │
│  ┌────────┐ ┌────────┐ ...              │
│  └────────┘ └────────┘                  │
└─────────────────────────────────────────┘
```

Логика:
1. `useQuery(['races'], fetchRaces)` — загрузить все гонки
2. State: `filter: 'all' | 'trail' | 'road'`
3. Фильтровать на клиенте через `getRaceCategory(race.type)`
4. Grid: `grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))`
5. Loading state: показать "Загрузка..."
6. Error state: показать ошибку
7. React Error Boundary — обернуть страницу для перехвата ошибок рендера

Сортировка гонок: **по дате последнего edition** (descending, свежие наверху).

> **TODO (backlog):** Заменить "Загрузка..." на skeleton placeholders для лучшего UX.

### 2.7 ErrorBoundary

**Создать** `frontend/src/components/ErrorBoundary.tsx`:

React Error Boundary — class component (React не поддерживает error boundaries в хуках):
- Перехватывает ошибки рендера в дочерних компонентах
- Показывает fallback UI вместо белого экрана
- Кнопка "Попробовать снова" (сбрасывает state)
- Стили: `.error-text` из components.css

Обернуть `<Routes>` в `App.tsx` в `<ErrorBoundary>`.

### 2.8 NotFoundPage (404)

**Создать** `frontend/src/pages/NotFoundPage.tsx`:

Простая страница 404:
- Текст: "Страница не найдена"
- Ссылка "← На главную" → `/`
- Стили: `.page`, `.page-sub`

Добавить catch-all route в App.tsx:
```tsx
<Route path="*" element={<NotFoundPage />} />
```

### 2.9 Page title (document.title)

Установить `document.title` на каждой странице через `useEffect`:
- `/races` → "Гонки — ayda.run"
- `/` → "ayda.run — беговой портал Алматы"
- 404 → "Страница не найдена — ayda.run"
- (в будущих шагах: `/races/:raceId` → "{raceName} — ayda.run")

### 2.10 Обновить App.tsx

**Изменить** `frontend/src/App.tsx`:

Добавить routes:
```tsx
<ErrorBoundary>
  <Routes>
    <Route path="/" element={<Navigate to="/races" replace />} />
    <Route path="/races" element={<RacesPage />} />
    <Route path="/predict" element={<PredictPage />} />
    <Route path="*" element={<NotFoundPage />} />
  </Routes>
</ErrorBoundary>
```

---

## Файлы-референсы

- `backend/app/api/v1/routes/races.py` — Pydantic schemas (RaceSchema строки 52-60, RaceDistanceSchema строки 34-43)
- `docs/task_tracker/todo/races_portal_front/ayda-homepage-v2 (1).html` — `.race-card` стили (строки 214-236)
- `frontend/src/api/client.ts` — API client, используем `api.get()`
- `frontend/src/styles/components.css` — готовые CSS классы: `.card`, `.badge`, `.filter-bar`, `.loading-text`, `.error-text`

## Проверка

1. `cd frontend && npm run dev`
2. Открыть `localhost:5173/races`
3. ✅ Видно 16 карточек гонок из API (Network tab: `GET /api/v1/races`)
4. ✅ Карточки показывают тип, название, локацию, кол-во editions
5. ✅ Фильтр работает: при клике "Трейл" — только trail гонки
6. ✅ Клик на карточку → навигация на `/races/{raceId}` (страница пустая — ОК)
7. ✅ Nav bar: ссылка "Гонки" активна (подсвечена)
8. ✅ Несуществующий URL → страница 404
9. ✅ Ошибка рендера → ErrorBoundary fallback (не белый экран)
10. ✅ `document.title` корректно обновляется
11. ✅ `npx tsc --noEmit` проходит без ошибок
12. ✅ `npx vite build` проходит без ошибок
