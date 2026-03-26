# Шаг 3: Детали гонки + результаты (`/races/:raceId`)

## Цель

Страница гонки с инфо, дистанциями, выбором года, таблицей результатов, статистикой и гистограммой распределения времён. Это самая важная страница портала.

**Зависит от:** Шаги 1-2 (дизайн-система, types, api).

---

## Что делать

### 3.1 YearTabs

**Создать** `frontend/src/components/races/YearTabs.tsx`:

Горизонтальный ряд кнопок для выбора года:
- Кнопки с годами из `race.editions`, отсортированы по убыванию (новые слева)
- Активный год: accent background
- Неактивные: ghost style
- Стиль аналогичный `.filter-btn` из шага 2

```typescript
interface YearTabsProps {
  years: number[];
  selected: number;
  onChange: (year: number) => void;
}
```

### 3.2 StatsCard

**Создать** `frontend/src/components/races/StatsCard.tsx`:

Карточка со сводной статистикой дистанции:

```
┌─────────┬─────────┬─────────┬─────────┐
│   245   │ 0:52:05 │ 1:28:30 │ 2:45:10 │
│финишеров│ лучший  │ медиана │ худший  │
└─────────┴─────────┴─────────┴─────────┘
```

- Grid 4 колонки (или 3 на мобильном)
- Числа крупные (24-28px, font-weight 900)
- Подписи мелкие (11px, dim цвет)
- Background: `var(--card)`, border, border-radius 12px
- Стиль из `.snum` паттерна homepage мокапа (строки 119-130)

Props:
```typescript
interface StatsCardProps {
  stats: RaceStats;  // из types/races.ts
}
```

### 3.3 TimeHistogram

> **Стратегия:** Сначала реализовать основные компоненты (3.1, 3.2, 3.4-3.6) без гистограммы.
> Посмотреть как выглядит страница, потом решить подход к гистограмме.
> Гистограмма — отдельная итерация после основного шага 3.

**Создать** `frontend/src/components/races/TimeHistogram.tsx`:

Canvas-компонент, рисующий гистограмму из `stats.time_buckets`:

- Горизонтальные бары (или вертикальные — на усмотрение)
- Каждый бар: label (временной диапазон), count, percent
- Цвет: accent с прозрачностью (gradient от ярче к бледнее)
- Размеры: 100% ширина контейнера, ~200px высота
- `devicePixelRatio` для crisp rendering
- `ResizeObserver` или `window.resize` для адаптивности

> **TODO (mobile):** Canvas гистограмма плохо адаптируется под мобилку.
> Для mobile рассмотреть fallback: простой div-based bar chart или скрыть гистограмму.
> Большинство пользователей будут открывать с мобильного — mobile-first!

Данные `time_buckets` приходят как:
```json
[
  { "label": "< 1:00", "count": 45, "percent": 18.4 },
  { "label": "1:00 — 1:30", "count": 82, "percent": 33.5 },
  ...
]
```

Canvas подход (из мокапов — Canvas API, без библиотек):
1. Ref на `<canvas>` элемент
2. `useEffect` для рисования при изменении данных или размера
3. Очистить canvas → нарисовать бары + labels + значения

Props:
```typescript
interface TimeHistogramProps {
  buckets: TimeBucket[];
}
```

### 3.4 ResultsTable

**Создать** `frontend/src/components/races/ResultsTable.tsx`:

Таблица результатов дистанции:

```
│ #  │ Имя               │ Время    │ Кат.   │ Пол │ Клуб      │
│────│───────────────────│──────────│────────│─────│───────────│
│ 🥇 │ ○ Iyemberdiyev D. │ 0:52:05  │ M_30   │ M   │ SRG       │
│ 🥈 │ ○ Baikashev S.    │ 0:54:12  │ M_20   │ M   │ RUNFINITY │
│ 🥉 │ ○ Abenov N.       │ 0:56:30  │ M_30   │ M   │ SRG       │
│ 4  │ ○ Smith J.        │ 0:58:45  │ M_40   │ M   │ —         │
│ ...│                   │          │        │     │           │
```

- Место 1-3: медальные цвета (gold #D4A742, silver #A0AAB8, bronze #A0724A)
- Аватар-инициалы: кружок 28px с первыми буквами имени (паттерн `.rr-ava`)
- Строки: border-bottom 1px solid border color
- Hover на строке: чуть светлее фон
- Показать первые 50 строк, кнопка "Показать всех (245)" для раскрытия

Props:
```typescript
interface ResultsTableProps {
  results: RaceResult[];
  showAll?: boolean;
}
```

State внутри: `expanded: boolean` — показывать все или первые 50.

### 3.5 DistanceResults

**Создать** `frontend/src/components/races/DistanceResults.tsx`:

Секция результатов для одной дистанции. Объединяет StatsCard + TimeHistogram + ResultsTable:

```
┌─────────────────────────────────────────────────┐
│  Skyrunning · 21 км · +1840 м                   │  ← заголовок дистанции
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ 245 финиш. │ 0:52:05 лучш. │ 1:28 мед.  │    │  ← StatsCard
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ ████████░░░░░  < 1:00  (45, 18%)        │    │  ← TimeHistogram
│  │ ████████████░  1:00-1:30 (82, 33%)      │    │
│  │ ██████░░░░░░░  1:30-2:00 (58, 24%)      │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ # │ Имя │ Время │ Кат. │ Пол │ Клуб    │    │  ← ResultsTable
│  │ ...                                      │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

Props:
```typescript
interface DistanceResultsProps {
  data: DistanceResults;  // из API
}
```

### 3.6 RaceDetailPage

**Создать** `frontend/src/pages/RaceDetailPage.tsx`:

Основная страница. Загружает данные и компонует всё:

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  ← Все гонки                                    │  ← back link
│                                                  │
│  TRAIL_SKY                                       │  ← тип badge
│  Alpine Race                                     │  ← h1
│  📍 Шымбулак                                    │  ← локация
│                                                  │
│  ┌─────────┐ ┌────────┐ ┌──────────────┐        │
│  │Sky 21km │ │VK 1000 │ │Trail Run 10k │        │  ← distance cards
│  │+1840m   │ │+850m   │ │+650m         │        │
│  └─────────┘ └────────┘ └──────────────┘        │
│                                                  │
│  [2025] [2024] [2023]                            │  ← YearTabs
│                                                  │
│  — Skyrunning 21 km —                            │
│  [StatsCard] [TimeHistogram] [ResultsTable]      │  ← DistanceResults
│                                                  │
│  — VK 1000 —                                     │
│  [StatsCard] [TimeHistogram] [ResultsTable]      │  ← DistanceResults
│                                                  │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

**Логика:**
1. `useParams()` → `raceId`
2. `useQuery(['race', raceId], () => fetchRace(raceId))` → инфо + editions
3. State: `selectedYear` — default = latest edition year
4. `useQuery(['results', raceId, selectedYear], () => fetchResults(raceId, selectedYear))` → результаты
5. При смене года → перезагрузить результаты
6. Loading/Error states для обоих запросов

**Distance cards** (инлайн, не отдельный компонент):
- Горизонтальный scroll или flex wrap
- Каждая карточка: название, km, elevation_gain
- Маленькие, padding 12px 16px

**Back link:** `← Все гонки` — ссылка на `/races`

### 3.7 Обновить App.tsx

**Изменить** `frontend/src/App.tsx`:

Добавить route:
```tsx
<Route path="/races/:raceId" element={<RaceDetailPage />} />
```

---

## API используемые

- `GET /api/v1/races/{raceId}` → Race (инфо + дистанции + editions)
- `GET /api/v1/races/{raceId}/{year}/results` → DistanceResults[] (stats + results + buckets)

## Файлы-референсы

- `backend/app/api/v1/routes/races.py` — schemas: DistanceResultsSchema (строки 84-89), RaceResultSchema (72-82), RaceStatsSchema (62-70)
- `docs/task_tracker/todo/races_portal_front/ayda-homepage-v2 (1).html` — стили таблиц (`.runner-row` строки 132-162)
- `docs/task_tracker/todo/races_portal_front/ayda-season-v5.html` — стили таблицы рейтинга (подробная таблица)

## Порядок реализации

1. Сначала: 3.1 (YearTabs), 3.2 (StatsCard), 3.4 (ResultsTable), 3.5 (DistanceResults), 3.6 (RaceDetailPage), 3.7 (App.tsx)
2. Посмотреть результат, убедиться что основа работает
3. Потом: 3.3 (TimeHistogram) — отдельная итерация

## TODO (из шага 2)

- **Количество участников на RaceCard:** Добавить `total_finishers` в бэкенд `RaceSchema` (подсчёт при выдаче каталога). Показать на карточке гонки в footer, например "245 участников · 3 дистанции · 5 лет". Требует изменения API endpoint `GET /api/v1/races`.

## Заметки по UX

- **Поиск участника (шаг 5):** будет добавлен между header/year tabs и секцией результатов — inline, не заменяет таблицу
- **404 для несуществующей гонки:** если API вернул 404 → показать "Гонка не найдена" + ссылку на /races
- **`document.title`:** установить "{raceName} — ayda.run" через useEffect
- **Mobile:** все компоненты должны быть адаптивны (single column < 860px)

## Проверка

1. Открыть `localhost:5173/races/alpine_race_kz`
2. ✅ Название "Alpine Race", тип "trail_sky", локация
3. ✅ Карточки дистанций (Skyrunning 21km, VK 1000 и т.д.)
4. ✅ Year tabs: кнопки 2023, 2024, 2025
5. ✅ При выборе года загружаются результаты (Network tab: `GET /api/v1/races/alpine_race_kz/2025/results`)
6. ✅ StatsCard: финишёры, лучшее/медианное/худшее время
7. ✅ TimeHistogram: Canvas гистограмма с 5 бакетами (отдельная итерация)
8. ✅ ResultsTable: таблица с именами, временем, местом, клубом
9. ✅ Кнопка "Показать всех" раскрывает полную таблицу
10. ✅ Back link "← Все гонки" ведёт на `/races`
11. ✅ Несуществующая гонка → "Гонка не найдена"
12. ✅ `document.title` обновляется
