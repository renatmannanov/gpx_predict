# Шаг 5: Поиск — GlobalSearch + TableFilter

## Цель

Два компонента поиска:
1. **GlobalSearch** в Navbar — глобальный поиск бегуна по имени → переход на `/runners/:name` (страница бегуна, шаг 5.5c). Виден на всех страницах.
2. **TableFilter** в ResultsTable — клиентская фильтрация/подсветка участников в таблице результатов гонки.

**Зависит от:** Шаги 1-4 (дизайн-система, страницы, Navbar).

---

## Что делать

### 5.1 useDebounce hook

**Создать** `frontend/src/hooks/useDebounce.ts`:

```typescript
import { useState, useEffect } from 'react';

export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
```

### 5.2 GlobalSearch в Navbar

**Создать** `frontend/src/components/layout/GlobalSearch.tsx` + `.css`:

Поисковая строка в navbar (desktop: инлайн между ссылками и кнопкой; mobile: под navbar).

```
Desktop Navbar:
┌──────────────────────────────────────────────────────────────────┐
│  ayda.run    Гонки    Предсказать время    [🔍 Найди себя...]    Войти  │
└──────────────────────────────────────────────────────────────────┘

Mobile: строка поиска отдельной полосой под navbar
┌──────────────────────────┐
│  ayda.run          Войти │
├──────────────────────────┤
│  [🔍 Найди себя...]      │
└──────────────────────────┘
```

**Логика:**
1. State: `query: string`, `isOpen: boolean` (для dropdown)
2. `useDebounce(query, 300)` → `debouncedQuery`
3. Пока бэкенд endpoint не готов (шаг 5.5a, задача A9) — показывать заглушку в dropdown: "Глобальный поиск скоро заработает. Используй поиск на странице гонки."
4. Когда бэкенд будет: `useQuery` → `GET /api/v1/runners/search?name=...` → dropdown с результатами
5. Клик на результат → navigate to `/runners/:nameNormalized`
6. Escape / клик вне → закрыть dropdown
7. Минимум 2 символа для запуска поиска

**Dropdown результатов (заготовка для будущего):**
```
┌──────────────────────────────┐
│  Baikashev Shyngys           │
│  RUNFINITY · 5 гонок         │
├──────────────────────────────┤
│  Baikasheva Aliya            │
│  — · 2 гонки                 │
└──────────────────────────────┘
```

**Стили:**
- Input: аналогичен `.search-input` из старого плана, но адаптирован под navbar
- Desktop: `max-width: 280px`, вписан в flex navbar
- Mobile: полная ширина, отдельная строка
- Dropdown: абсолютное позиционирование под input, `var(--card)` фон, `var(--border)` рамка

### 5.3 Интеграция GlobalSearch в Navbar

**Изменить** `frontend/src/components/layout/Navbar.tsx`:

Добавить `<GlobalSearch />` между навигационными ссылками и кнопкой "Войти".

### 5.4 TableFilter в ResultsTable

**Изменить** `frontend/src/components/races/ResultsTable.tsx`:

Добавить маленький input-фильтр в шапке таблицы результатов:

```
Результаты — Skyrunning 21km
┌──────────────────────────────────┐
│ 🔍 Фильтр по имени...           │  ← маленький input, часть таблицы
├──────────────────────────────────┤
│ #1  ██Iyemberdiyev██ D.  0:52:05│  ← подсвеченное совпадение
│ #2  Baikashev S.     0:54:12    │
│ ...                              │
└──────────────────────────────────┘
```

**Логика:**
1. State: `filterQuery: string` (без debounce — клиентская фильтрация мгновенная)
2. Фильтрация: `results.filter(r => r.name.toLowerCase().includes(query))`
3. Подсветка совпадения: обернуть совпавший текст в `<mark>`
4. Если фильтр не пустой и 0 результатов: "Не найдено"
5. При очистке фильтра — показать все результаты

**Стили:**
- Input маленький, неброский: меньше основного шрифта, без рамки (только border-bottom)
- `<mark>` подсветка: `background: rgba(232, 98, 42, 0.25)` (accent с прозрачностью)
- Не выглядит как "поисковая строка" — скорее как фильтр таблицы

---

## API используемые

- **GlobalSearch:** `GET /api/v1/runners/search?name=...` — НЕ СУЩЕСТВУЕТ пока. Бэкенд задача A9 в step_5_5a_backend.md. Фронт готов, показывает заглушку.
- **TableFilter:** Нет API — чисто клиентская фильтрация по уже загруженным данным.

## Файлы создаваемые/изменяемые

| Действие | Файл |
|----------|------|
| Создать | `frontend/src/hooks/useDebounce.ts` |
| Создать | `frontend/src/components/layout/GlobalSearch.tsx` |
| Создать | `frontend/src/components/layout/GlobalSearch.css` |
| Изменить | `frontend/src/components/layout/Navbar.tsx` |
| Изменить | `frontend/src/components/layout/Navbar.css` |
| Изменить | `frontend/src/components/races/ResultsTable.tsx` |
| Изменить | `frontend/src/components/races/ResultsTable.css` |
| Изменить | `frontend/src/index.css` (импорт GlobalSearch.css) |

## Проверка

### GlobalSearch
1. ✅ Поисковая строка видна в navbar на всех страницах (desktop)
2. ✅ На mobile — строка под navbar
3. ✅ Ввод текста → debounce → dropdown с заглушкой "скоро заработает"
4. ✅ Escape закрывает dropdown
5. ✅ Клик вне dropdown — закрывает

### TableFilter
6. Открыть `localhost:5173/races/alpine_race_kz`
7. ✅ Input фильтра виден в шапке таблицы результатов
8. ✅ Ввести "Baik" → таблица фильтруется, совпадение подсвечено
9. ✅ Ввести несуществующее имя → "Не найдено"
10. ✅ Очистить фильтр → все результаты снова видны
11. ✅ Фильтрация мгновенная (без debounce, клиентская)
