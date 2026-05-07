# Шаг 5.5d: Search Insights + Сравнение участников

## Цель

Расширить поиск "Найди себя" персентилями и Y-o-Y прогрессом.
Добавить возможность сравнить 2-4 участников из таблицы результатов.

**Ветка:** `web-portal-step-5.5d`
**Зависит от:** 5.5a (search с персентилями), 5.5c (PercentileBadge, навигация по runner_id).

---

## Что делать

### D1. Расширить SearchResultRow — персентили

**Изменить** `frontend/src/components/search/SearchResultRow.tsx`:

Было:
```
2025   Baikashev Shyngys   0:54:12   #2
```

Стало:
```
2025   Baikashev Shyngys   0:54:12   #2 из 245   top-1%
       Среди мужчин top-1% · В M_20-29: 1 из 18
```

- Первая строка: год, имя (ссылка на `/runners/{runner_id}`), время, место/total, PercentileBadge
- Вторая строка (dim, мелкий): gender percentile + category rank (если данные есть)

Данные из расширенного search API (5.5a): `percentile`, `total_finishers`, `gender_percentile`, `category_rank`, `category_total`.

### D2. Y-o-Y прогресс в поиске

**Изменить** `frontend/src/components/search/ParticipantSearch.tsx`:

Когда найдено > 1 года — показать таблицу прогресса:

```
Прогресс: Skyrunning 21km
┌─────┬──────────┬──────┬─────────┬──────────┐
│ Год │  Время   │Место │Персент. │ Динамика │
│2025 │ 0:54:12  │  #2  │ top-1%  │ ▲ -1:28  │
│2024 │ 0:55:40  │  #3  │ top-1%  │ ▲ -0:48  │
│2023 │ 0:56:28  │  #5  │ top-2%  │ первый   │
└─────┴──────────┴──────┴─────────┴──────────┘
```

- Динамика = разница time_s с предыдущим годом
- `▲ -1:28` (зелёный) = улучшение, `▼ +2:05` (красный) = ухудшение
- "первый" (dim) = первый год участия

### D3. CompareCheckbox в ResultsTable

**Изменить** `frontend/src/components/races/ResultsTable.tsx`:

Добавить чекбоксы для выбора участников:

```
☐  #1  Iyemberdiyev D.  0:52:05  SRG
☑  #2  Baikashev S.     0:54:12  RUNFINITY
☑  #3  Abenov N.        0:56:30  SRG
```

State: `selectedForCompare: Set<number>` (runner_id).
Максимум 4 участника.

При выборе >= 2 → плавающая кнопка "Сравнить (N)" (fixed/sticky внизу).

Props:
```typescript
interface ResultsTableProps {
  results: RaceResult[];
  showAll?: boolean;
  compareEnabled?: boolean;
  selectedRunnerIds?: Set<number>;
  onToggleCompare?: (runnerId: number) => void;
}
```

State `selectedForCompare` живёт в DistanceResults, передаётся вниз.

### D4. ComparePanel

**Создать** `frontend/src/components/races/ComparePanel.tsx` + `.css`:

Панель сравнения (модалка или inline):

```
Сравнение — Skyrunning 21km
┌──────────────┬────────────────┬────────────────┬────────────────┐
│              │ Iyemberdiyev D.│ Baikashev S.   │ Abenov N.      │
│ 2025         │ 0:52:05 (#1)   │ 0:54:12 (#2)   │ 0:56:30 (#3)   │
│ 2024         │ 0:55:10 (#2)   │ 0:53:40 (#1)   │ —              │
│ 2023         │ 0:57:22 (#3)   │ 0:56:50 (#2)   │ 0:59:15 (#5)   │
│──────────────│────────────────│────────────────│────────────────│
│ Лучшее время │ 0:52:05 (2025) │ 0:53:40 (2024) │ 0:56:30 (2025) │
│ Прогресс     │ ▲ -5:17        │ ▲ -2:38        │ ▲ -2:45        │
│ Клуб         │ SRG            │ RUNFINITY      │ SRG            │
└──────────────┴────────────────┴────────────────┴────────────────┘
```

**Данные:** Параллельные запросы `GET /races/{raceId}/search?name=...` для каждого выбранного участника. Для MVP 2-4 запроса — нормально.

**Логика:**
1. `useQueries` → search по каждому имени
2. Объединить: уникальные годы → строки, участники → колонки
3. Вычислить: лучшее время, прогресс

**UX:**
- Горизонтальный scroll на mobile
- Имена — ссылки на `/runners/{runner_id}`
- Кнопки "✕" для удаления и "Закрыть"

```typescript
interface ComparePanelProps {
  raceId: string;
  distanceName: string;
  selectedRunnerIds: number[];
  selectedNames: string[];  // для search API
  onClose: () => void;
  onRemove: (runnerId: number) => void;
}
```

### D5. Обновить TypeScript types

**Изменить** `frontend/src/types/races.ts`:

```typescript
interface SearchResult {
  year: number;
  result: RaceResult | null;
  percentile?: number;
  total_finishers?: number;
  gender_percentile?: number;
  category_rank?: number;
  category_total?: number;
}
```

---

## Проверка

1. Поиск "Найди себя" → ввести имя
2. ✅ Каждый результат показывает персентиль (PercentileBadge)
3. ✅ "Среди мужчин top-X%" и "В M_30: Y из Z" (если данные есть)
4. ✅ Несколько лет → таблица прогресса с динамикой
5. ✅ Имя = ссылка на профиль бегуна (по runner_id)
6. В таблице результатов:
7. ✅ Чекбоксы рядом с каждым участником
8. ✅ При выборе 2+ → кнопка "Сравнить (N)"
9. ✅ Максимум 4 (5-й не выбирается)
10. ✅ "Сравнить" → панель с таблицей по годам
11. ✅ Можно удалить участника из сравнения (✕)
12. ✅ Имена — ссылки на профиль
13. ✅ Mobile: горизонтальный scroll
