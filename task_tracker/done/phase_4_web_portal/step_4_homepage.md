# Шаг 4: Главная страница (`/`)

## Цель

Homepage по дизайну `ayda-homepage-v2 (1).html`: hero с сезонной статистикой, top гонки, GPX predict CTA. Переиспользуем RaceCard из шага 2.

**Зависит от:** Шаги 1-2 (дизайн-система, RaceCard, API).

---

## Что делать

### 4.1 SeasonStatsBox

**Создать** `frontend/src/components/dashboard/SeasonStatsBox.tsx`:

Правая колонка hero — box с сезонной статистикой:

```
┌────────────────────────────────┐
│ Сезон гонок 2025       АЛМАТЫ │
│────────────────────────────────│
│   16        47        203     │
│ гонок    editions  дистанций  │
│────────────────────────────────│
│ Все гонки — 16 рас →          │
└────────────────────────────────┘
```

- Header: title + year badge (accent)
- 3 stat числа в grid (большие, 32px, accent для первого)
- Footer: ссылка на `/races`
- Стиль: `.season-box` из мокапа homepage (строки 99-130)

Данные вычисляем из массива Race[] (обязательно `useMemo` чтобы не пересчитывать при каждом ре-рендере):
```typescript
const stats = useMemo(() => {
  const currentYear = new Date().getFullYear();
  const editionsThisYear = races.flatMap(r =>
    r.editions.filter(e => e.year === currentYear)
  );
  return {
    totalRaces: races.length,
    totalEditions: races.reduce((sum, r) => sum + r.editions.length, 0),
    totalDistances: races.reduce((sum, r) => sum + r.distances.length, 0),
  };
}, [races]);
```

Props:
```typescript
interface SeasonStatsBoxProps {
  races: Race[];
}
```

### 4.2 HeroSection

**Создать** `frontend/src/components/dashboard/HeroSection.tsx`:

Двухколоночный hero:

Левая колонка:
- Badge: "БЕГОВОЙ ПОРТАЛ АЛМАТЫ" (11px, uppercase, accent)
- h1: "Сквозная аналитика всех горных **гонок Алматы**" (em = accent)
- Subtitle: описание (dim, 15px)
- Две кнопки: "Все гонки" (btn-fill) → `/races`, "Предсказать моё время →" (btn-ghost) → `/predict`

Правая колонка:
- `<SeasonStatsBox races={races} />`

Стиль из мокапа homepage (`.hero`, `.hero-top`, строки 60-96).
Grid: `grid-template-columns: 1fr 1fr`, gap 48px.
Mobile (< 860px): одна колонка.

Props:
```typescript
interface HeroSectionProps {
  races: Race[];
}
```

### 4.3 RacesPreview

**Создать** `frontend/src/components/dashboard/RacesPreview.tsx`:

Секция с карточками последних гонок:

```
┌───────────────────────────────────────────┐
│ ГОНКИ 2025                  Все гонки →   │
│                                            │
│ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │ card 1 │ │ card 2 │ │ card 3 │          │
│ └────────┘ └────────┘ └────────┘          │
│ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │ card 4 │ │ card 5 │ │ card 6 │          │
│ └────────┘ └────────┘ └────────┘          │
└───────────────────────────────────────────┘
```

- Заголовок секции + ссылка "Все гонки →" (`.sec-head`, `.sec-title`, `.sec-link`)
- Показать 6 гонок: **отсортированных по дате ближайшего edition** (descending, свежие первые)
- Переиспользовать `<RaceCard>` из шага 2
- Grid: одна колонка (как в мокапе — `grid-template-columns: 1fr`)

Props:
```typescript
interface RacesPreviewProps {
  races: Race[];
}
```

### 4.4 PredictCTA

**Создать** `frontend/src/components/dashboard/PredictCTA.tsx`:

Карточка "Предскажи своё время":

```
┌──────────────────────────────────────────────────┐
│  GPX PREDICT                                      │
│  Сколько ты пройдёшь этот маршрут?               │
│  Подключи Strava — предскажем твоё финишное      │
│  время на любом трейле Алматы.                   │
│                                   [Предсказать]   │
└──────────────────────────────────────────────────┘
```

- Flex layout: текст слева, кнопка справа
- Border: `1px solid rgba(232,98,42,0.2)` — accent tint
- Кнопка: btn-fill → `/predict`
- Стиль из мокапа (`.predict-cta`, строки 239-251)

### 4.5 DashboardPage

**Создать** `frontend/src/pages/DashboardPage.tsx`:

Собирает все компоненты:

```typescript
export default function DashboardPage() {
  const { data: races, isLoading } = useQuery({
    queryKey: ['races'],
    queryFn: fetchRaces,
  });

  if (isLoading) return <div className="page">Загрузка...</div>;

  return (
    <div>
      <div className="hero">
        <HeroSection races={races || []} />
      </div>
      <div className="section">
        <RacesPreview races={races || []} />
      </div>
      <PredictCTA />
    </div>
  );
}
```

### 4.6 Обновить App.tsx

**Изменить** `frontend/src/App.tsx`:

Заменить старый HomePage:
```tsx
import DashboardPage from './pages/DashboardPage'
// ...
<Route path="/" element={<DashboardPage />} />
```

Можно удалить `frontend/src/pages/HomePage.tsx` (старый).

---

## Файлы-референсы

- `docs/task_tracker/todo/races_portal_front/ayda-homepage-v2 (1).html` — полный дизайн homepage
  - Hero: строки 297-335
  - Races: строки 349-356
  - Predict CTA: строки 360-367
  - CSS: строки 9-279
- `frontend/src/components/races/RaceCard.tsx` — переиспользовать из шага 2

## Проверка

1. Открыть `localhost:5173/`
2. ✅ Hero: заголовок, subtitle, две кнопки
3. ✅ Season box справа: 3 числа из API
4. ✅ Кнопка "Все гонки" → `/races`
5. ✅ Секция гонок: 6 карточек, ссылка "Все гонки →"
6. ✅ Predict CTA: карточка с кнопкой → `/predict`
7. ✅ Mobile: одна колонка
