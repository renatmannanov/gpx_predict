# Шаг 1: Дизайн-система + каркас

## Цель

Заменить зелёную светлую тему на тёмную ayda.run. Создать общий layout (Nav + Footer + PageLayout). После этого шага приложение открывается с правильным дизайном, nav bar, footer. Существующий `/predict` продолжает работать.

---

## Что делать

### 1.1 CSS custom properties

**Создать** `frontend/src/styles/variables.css`:

```css
:root {
  --bg: #252628;
  --bg-nav: rgba(37,38,40,0.95);
  --accent: #E8622A;
  --accent-trail: #E8622A;
  --accent-road: #5B8DEF;
  --text: #EDEEF0;
  --dim: #7A8394;
  --card: rgba(255,255,255,0.04);
  --card-hover: rgba(255,255,255,0.07);
  --border: rgba(255,255,255,0.08);
  --danger: #ef4444;
  --success: #3CC77A;
  --nav-height: 56px;
  --radius-card: 14px;
  --radius-btn: 8px;
  --max-width: 1100px;
}
```

### 1.2 Base styles

**Создать** `frontend/src/styles/base.css`:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Manrope', sans-serif;
  -webkit-font-smoothing: antialiased;
}

a { color: inherit; text-decoration: none; }

@keyframes page-up {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: none; }
}

.page {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: calc(var(--nav-height) + 24px) 40px 64px;
  animation: page-up 0.35s ease;
}
```

Включить стили для `h1`, `h2`, `.section`, `.sec-head`, `.sec-title`, `.sec-link` из мокапа `ayda-homepage-v2 (1).html`.

### 1.3 Component styles

**Создать** `frontend/src/styles/components.css`:

Перенести из мокапов CSS-классы для:
- `.btn`, `.btn-fill`, `.btn-ghost` — кнопки (из homepage мокапа строки 85-96)
- `.race-card`, `.rc-tag`, `.rc-name`, `.rc-date`, `.rc-footer` — карточки гонок (строки 219-236)
- `.stat-item`, `.stat-n`, `.stat-l` — stat плашки (из clubs мокапа строки 37-41)
- `.page-eyebrow` — верхний badge страницы (11px uppercase accent)

### 1.4 Navbar

**Создать** `frontend/src/components/layout/Navbar.tsx`:

React-компонент на основе `<nav>` из мокапа (homepage строки 284-295):
- Fixed position, height 56px, backdrop-filter blur(16px)
- Logo: `ayda` + `.run` в accent цвете. Ссылка на `/`
- Nav links: Гонки (`/races`), Рейтинг (disabled/coming soon), Маршруты (disabled), Предсказать (`/predict`)
- Правая сторона: кнопка "Войти" (заглушка, стиль `.btn-nav`)
- Использовать `<Link>` из react-router-dom
- Активная ссылка подсвечена (`.on` класс) — определять через `useLocation()`
- Mobile: скрыть nav-links при ширине < 860px

**CSS** для nav — перенести из мокапа (строки 30-57).

### 1.5 Footer

**Создать** `frontend/src/components/layout/Footer.tsx`:

Простой footer из мокапа (строки 257-265):
- Logo `ayda.run`
- Копирайт: "2025 · Алматы, Казахстан"

### 1.6 PageLayout

**Создать** `frontend/src/components/layout/PageLayout.tsx`:

Обёртка:
```tsx
export default function PageLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <main>{children}</main>
      <Footer />
    </>
  );
}
```

### 1.7 Обновить index.html

**Изменить** `frontend/index.html`:

- Добавить `<link>` для Google Fonts Manrope (weights 400-900)
- Изменить `<title>` на `ayda.run — беговой портал Алматы`
- Добавить `lang="ru"`

### 1.8 Обновить index.css

**Изменить** `frontend/src/index.css`:

Заменить содержимое на:
```css
@import './styles/variables.css';
@import './styles/base.css';
@import './styles/components.css';

@tailwind utilities;
```

Убрать `@tailwind base` и `@tailwind components` — используем свои стили.
Оставить `@tailwind utilities` для утилит (flex, grid, p-*, m-*, и т.д.).

### 1.9 Обновить App.tsx

**Изменить** `frontend/src/App.tsx`:

- Обернуть Routes в `<PageLayout>`
- Убрать `className="min-h-screen bg-gray-50"` — фон теперь через CSS

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import PageLayout from './components/layout/PageLayout'
import PredictPage from './pages/PredictPage'

function App() {
  return (
    <BrowserRouter>
      <PageLayout>
        <Routes>
          <Route path="/predict" element={<PredictPage />} />
          {/* Временно: главная редиректит на /races */}
        </Routes>
      </PageLayout>
    </BrowserRouter>
  )
}
```

### 1.10 Обновить tailwind.config.js

**Изменить** `frontend/tailwind.config.js`:

Убрать зелёную палитру, добавить тёмные цвета для утилит:
```js
colors: {
  accent: '#E8622A',
  'accent-road': '#5B8DEF',
  dim: '#7A8394',
  surface: 'rgba(255,255,255,0.04)',
}
```

---

## Файлы-референсы

- `docs/task_tracker/todo/races_portal_front/ayda-homepage-v2 (1).html` — CSS строки 9-279
- `docs/task_tracker/todo/races_portal_front/ayda-tz.md` — дизайн-система, навигация

## Проверка

1. `cd frontend && npm run dev`
2. Открыть `localhost:5173`
3. ✅ Тёмный фон #252628
4. ✅ Шрифт Manrope
5. ✅ Nav bar с логотипом ayda.run, ссылками, кнопкой "Войти"
6. ✅ Footer
7. ✅ `/predict` работает (может быть с поломанными стилями старых компонентов — ок)
8. ✅ Нет ошибок в консоли
