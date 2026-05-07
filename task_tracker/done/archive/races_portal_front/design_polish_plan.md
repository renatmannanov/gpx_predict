# Design Polish: Race Header + Runner Profile

Мокапы:
- `race-stats-demo.html` — новый хедер + stats страницы гонки (вариант Г)
- `ayda-runner-profile.html` — новый профиль бегуна

---

## A. Race Header Redesign

### Что меняется (vs текущее)

| Элемент | Сейчас | Мокап |
|---------|--------|-------|
| Год | YearTabs (горизонтальные таблетки) | **Dropdown** "2025 ▾" рядом с названием |
| Заголовок | Badge сверху → H1 → location | Одна строка: H1 + year-dropdown + badge |
| Дистанции | `flex-wrap` карточки (name + km) | **Pills** в горизонтальном скролле с fade |
| Stats | StatsCard (полный блок внутри DistanceResults) | **Dist stats** — двухуровневый блок (вариант Г) |

### Dist stats (вариант Г) — структура:
```
Верх:  "Canicross · 3 км ↑ 150 м"     "16 финишёров" (accent)
       ─────────────────────────────────────────────
Низ:   лучший  медиана  последний  |   2 DNF   1 DNS
```

### Задачи

**A1. Title row + YearDropdown** (средне)
- `RaceDetailPage.tsx`: H1 + YearDropdown + badge в одну строку
- Новый компонент `YearDropdown.tsx` (заменяет `YearTabs`)
- Кнопка "2025 ▾" → dropdown с годами, текущий помечен "сейчас"
- Клик вне → закрытие
- Файлы: `YearDropdown.tsx`, `YearDropdown.css`, правки в `RaceDetailPage.tsx/.css`

**A2. Distance pills с scroll** (средне)
- Рефакторинг `.distance-tabs` → `.dist-wrap` с горизонтальным скроллом
- Fade-край справа (gradient ::after)
- Pills: компактнее — `padding: 7px 14px`, `font-size: 13px`, `border-radius: 8px`
- Name + km в одну кнопку: "Nordic Sprint 7 · 7км"
- Файлы: правки в `RaceDetailPage.tsx/.css`

**A3. Dist stats block** (средне)
- Заменяет StatsCard в шапке дистанции
- Верх: название + расстояние + набор высоты СЛЕВА, "N финишёров" СПРАВА (accent)
- Низ (strip): лучший/медиана/последний СЛЕВА | DNF/DNS СПРАВА
- StatsCard убираем из DistanceResults (или заменяем на этот блок)
- Гистограмма, гендер, категории — остаются ниже в DistanceResults
- Файлы: новый `DistStatsBlock.tsx/.css`, правки в `DistanceResults.tsx`

**Итого A:** 3 задачи. **Сложность: средняя.**

---

## B. Runner Profile Redesign

### Что меняется (vs текущее)

| Элемент | Сейчас | Мокап |
|---------|--------|-------|
| Header | Имя → subtitle (клуб · категория) → stats-row | Имя СЛЕВА + top-X% СПРАВА, метаданные в 2 колонки |
| Прогресс | Нет | **Sparkline** (canvas) — график percentile по сезонам |
| Результаты | RunnerResultCard (карточки) | **Grid-строки** (гонка / время+место / tag / trend) |

### Задачи

**B1. Runner header redesign** (средне)
- `RunnerSummary.tsx`:
  - Top: имя слева, `top-X%` справа (accent, крупно)
  - Strip: клуб/категория/лет СЛЕВА | гонок/в 202X/лучшее место СПРАВА
- Данные "гонок в текущем году" и "лучшее место" — считаем на фронте из results[]
- Файлы: `RunnerSummary.tsx/.css`

**B2. Sparkline** (сложно)
- Новый компонент `SeasonSparkline.tsx`
- Canvas: линия + area fill + dots + grid lines
- Tooltip при hover
- Badge "+X% за N лет"
- **Бэкенд:** добавить `seasons[]` в `RunnerProfileResponse`
- Файлы: `SeasonSparkline.tsx/.css`, бэкенд `runners.py`, `models.py`, `schemas.py`

**B3. Result rows** (средне)
- `RunnerResultCard.tsx` → grid-строки
- Grid: `1fr auto auto auto` (гонка / время+место / tag / trend)
- Подсветка top-0% и top-1% строк
- Файлы: `RunnerResultCard.tsx/.css`

**Итого B:** 3 задачи. **Сложность: высокая** (sparkline + бэкенд).

---

## Порядок реализации

1. **A1** — Title row + YearDropdown
2. **A2** — Distance pills
3. **A3** — Dist stats block
4. **B1** — Runner header
5. **B3** — Result rows
6. **B2** — Sparkline (последний, требует бэкенд)
