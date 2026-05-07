# Шаг 5.5b: Демография, клубы, DNF на странице дистанции

## Цель

Добавить визуализации на страницу дистанции: M/F распределение, категории, рейтинг клубов, гистограмма времён, DNF отображение. Пользователь сразу видит "портрет" дистанции.

**Ветка:** `web-portal-step-5.5b`
**Зависит от:** 5.5a (бэкенд с новыми полями в stats, status, runner_id).

---

## Что делать

### B1. TimeHistogram (div-based, НЕ Canvas)

**Создать** `frontend/src/components/races/TimeHistogram.tsx` + `.css`:

Горизонтальные бары на CSS (без Canvas — работает на mobile):

```
Распределение времён
< 52:05      ████████████░░░░░░  45  (18%)
52:05-1:10   █████████████████░  82  (33%)
1:10-1:28    ██████████████░░░░  58  (24%)
1:28-1:46    █████████░░░░░░░░░  35  (14%)
> 1:46       ██████░░░░░░░░░░░░  25  (10%)
```

Реализация:
- Каждый бар = `div` с `width: {percent}%` и `background: var(--accent)` с прозрачностью
- Максимальный бар = 100% ширины, остальные пропорционально
- Label слева, count/percent справа
- Высота каждого бара 28-32px, gap 4px

```typescript
interface TimeHistogramProps {
  buckets: TimeBucket[];
}
```

Данные `time_buckets` уже приходят с API (5 бакетов).

### B2. GenderChart (donut/pie)

**Создать** `frontend/src/components/races/GenderChart.tsx` + `.css`:

Простой donut chart M/F. Варианты: CSS `conic-gradient` или inline SVG.

Рядом с donut — legend: цветной кружок + "M 180 (73%)" / "F 65 (27%)".
Цвета: M = `var(--accent)`, F = `var(--accent-road)`.

```typescript
interface GenderChartProps {
  distribution: GenderDistribution[];
}
```

Если `distribution` пустой → компонент не рендерится.

### B3. CategoryBars

**Создать** `frontend/src/components/races/CategoryBars.tsx` + `.css`:

Горизонтальные бары по категориям (аналогично TimeHistogram).
- Цвет: accent для M-категорий, accent-road для F-категорий
- Максимум 8 категорий, остальные в "Другие"

Если пустой → не рендерится.

### B4. ClubRanking

**Создать** `frontend/src/components/races/ClubRanking.tsx` + `.css`:

Таблица клубов:

```
#  Клуб         Бегунов  Лучший   Средний перс.
1  SRG          12       0:52:05  top-18%
2  RUNFINITY     8       0:54:12  top-25%
3  TRC ALMATY    6       1:01:30  top-35%
```

- Стиль как ResultsTable
- Первые 3 места — accent цвет
- "Средний перс." с цветом: green < 25%, yellow 25-50%, dim > 50%

Если пустой → не рендерится.

### B5. DNF-индикатор в StatsCard

**Изменить** `frontend/src/components/races/StatsCard.tsx`:

Добавить 5-й показатель если `dnf_count > 0`:

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│   245    │  0:52:05 │  1:28:30 │  2:45:10 │  15 DNF  │
│финишёров │  лучший  │  медиана │  худший  │   (6%)   │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

Цвет DNF: dim (серый). Grid: 5 или 4 колонок.

### B6. DNF-участники в ResultsTable

**Изменить** `frontend/src/components/races/ResultsTable.tsx`:

- DNF/DNS результаты (`status != "finished"` и `!= "over_time_limit"`) показывать **внизу таблицы**, отделённые визуально
- Стиль DNF-строк: серый текст, вместо времени — "DNF" / "DNS"
- DNF-строки не имеют места (#)

### B7. Интеграция в DistanceResults

**Изменить** `frontend/src/components/races/DistanceResults.tsx`:

```
[StatsCard]               ← уже есть (+ DNF в B5)
[TimeHistogram]           ← NEW (B1)
[GenderChart + CategoryBars]  ← NEW (B2, B3) — grid 2 col desktop, стак mobile
[ClubRanking]             ← NEW (B4)
[ResultsTable]            ← уже есть (+ DNF внизу — B6)
```

### B8. Обновить TypeScript types

**Изменить** `frontend/src/types/races.ts`:

```typescript
interface GenderDistribution {
  gender: string;
  count: number;
  percent: number;
}

interface CategoryDistribution {
  category: string;
  count: number;
  percent: number;
}

interface ClubStatsData {
  club: string;
  count: number;
  best_time_s: number;
  best_time: string;
  avg_percentile: number;
}

// Расширить RaceStats
interface RaceStats {
  // ... existing ...
  gender_distribution: GenderDistribution[];
  category_distribution: CategoryDistribution[];
  club_stats: ClubStatsData[];
  total_participants?: number;
  dnf_count?: number;
  dns_count?: number;
  dnf_rate?: number;
}

// Расширить RaceResult
interface RaceResult {
  // ... existing ...
  name_normalized?: string;
  runner_id?: number;
  status: string;  // "finished" | "dnf" | "dns" | "dsq" | "over_time_limit"
}
```

---

## Проверка

1. Открыть `/races/alpine_race_kz` → выбрать год с результатами
2. ✅ TimeHistogram: 5 горизонтальных баров
3. ✅ GenderChart: donut M/F (если данные есть)
4. ✅ CategoryBars: горизонтальные бары (если данные есть)
5. ✅ ClubRanking: таблица клубов (если данные есть)
6. ✅ StatsCard: DNF показан если есть
7. ✅ ResultsTable: DNF-участники внизу серым
8. ✅ Пустые данные → компоненты скрыты, страница не ломается
9. ✅ Mobile: одна колонка, бары читаемы
