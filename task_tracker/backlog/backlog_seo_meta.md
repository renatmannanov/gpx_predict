# SEO & Meta Tags — Бэклог

> **Частично сделано 2026-06-11:** серверная подстановка `<title>` + OG-тегов
> (og:title/description/url, twitter:card, meta description) для `/races/:id`
> и `/runners/:id` — `backend/app/services/seo_meta.py` + SPA-фоллбэк в `main.py`.
> Дефолтные теги для остальных страниц — в `frontend/index.html`.
> Осталось: og:image (нужен PNG, мессенджеры не едят SVG), SSG/prerender при росте.

## Проблема

SPA (React) не генерирует правильные `<meta>` теги для страниц бегунов и гонок.
Поисковики и превью в мессенджерах видят только generic title/description.

## Что нужно

### 1. `document.title` (уже частично)
- ✅ `document.title` обновляется на страницах (5.5c: "{name} — ayda.run")
- Нужно для: DashboardPage, RacesPage, RaceDetailPage

### 2. `<meta description>` для каждой страницы
- Страница бегуна: "Baikashev Shyngys — 8 гонок, top-15%. Результаты Alpine Race, Tengri Ultra."
- Страница гонки: "Alpine Race 2025 — 245 финишёров, лучшее время 0:52:05"
- Homepage: "ayda.run — результаты и аналитика трейл-гонок Казахстана"

### 3. Open Graph / Twitter Cards
- `og:title`, `og:description`, `og:image`
- Для шеринга в мессенджерах и соцсетях

### Возможные решения
1. **react-helmet-async** — обновлять `<head>` из компонентов (просто, но бесполезно для ботов)
2. **SSR (Next.js / Remix)** — миграция на SSR фреймворк (масштабно)
3. **Prerender** — сервис типа prerender.io для ботов (быстро, но платно)
4. **SSG для ключевых страниц** — генерировать HTML для /runners/:id и /races/:id

### Приоритет
Низкий — пока трафик органический (ссылки в чатах/клубах), SEO не критичен.
Станет актуальным при росте до публичного сервиса.
