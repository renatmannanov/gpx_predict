# Шаг 6: Деплой и финализация

## Цель

Production build работает. SPA routing корректен. Railway деплоит фронт вместе с бэкендом.

**Зависит от:** Шаги 1-5.

---

## Что делать

### 6.1 Проверить production build

```bash
cd frontend
npm run build    # tsc && vite build
```

Убедиться:
- `frontend/dist/index.html` существует
- `frontend/dist/assets/` содержит JS и CSS бандлы
- Нет TS ошибок

### 6.2 Проверить SPA через FastAPI

Бэкенд уже монтирует фронт (`backend/app/main.py` строки 156-158):

```python
_frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
```

`html=True` — SPA mode: любой маршрут, не соответствующий файлу, возвращает `index.html`.

Проверка:
```bash
cd backend
python -m uvicorn app.main:app --port 8000
```

Открыть:
- `http://localhost:8000/` → homepage
- `http://localhost:8000/races` → races page
- `http://localhost:8000/races/alpine_race_kz` → race detail (прямой URL!)
- `http://localhost:8000/api/v1/races` → JSON API (не перехватывается SPA)

### 6.3 Railway build command

Текущий Railway деплоит только бэкенд. Нужно добавить шаг сборки фронтенда.

**Вариант A: Nixpacks (Railway default)**

Если Railway использует Nixpacks, нужен `railway.json` или `nixpacks.toml` в корне:

```json
{
  "build": {
    "builder": "nixpacks",
    "buildCommand": "cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

**Вариант B: Custom Dockerfile**

Если уже есть Dockerfile — добавить Node.js step:

```dockerfile
# Frontend build
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Backend
FROM python:3.11-slim
WORKDIR /app
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist/
RUN pip install -r backend/requirements.txt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Решение:** Используем Dockerfile (вариант B) — уже настроен на проде, не меняем чтобы ничего не сломать.

### 6.4 Переменные окружения

Для production фронт и API на одном домене → CORS не нужен.
Vite proxy (`/api → localhost:8000`) работает только в dev mode — в production запросы идут на тот же origin.

Убедиться что `frontend/src/api/client.ts` использует относительный URL:
```typescript
const BASE_URL = '/api/v1'  // ✅ уже так
```

### 6.5 Финальный чеклист

- [ ] `npm run build` проходит без ошибок
- [ ] `frontend/dist/index.html` существует после build
- [ ] FastAPI раздаёт SPA: `localhost:8000/` → homepage
- [ ] Прямые URL работают: `localhost:8000/races/alpine_race_kz` → detail page
- [ ] API работает: `localhost:8000/api/v1/races` → JSON
- [ ] Railway build command включает frontend build
- [ ] Деплой на Railway успешен
- [ ] Production URL открывает портал

---

## Файлы-референсы

- `backend/app/main.py` — StaticFiles mount (строки 156-158)
- `frontend/vite.config.ts` — proxy и build config
- `frontend/src/api/client.ts` — BASE_URL = '/api/v1'

## Проверка

1. ✅ `npm run build` — нет ошибок
2. ✅ `uvicorn app.main:app` → `localhost:8000/` показывает SPA
3. ✅ Прямой заход на `/races/alpine_race_kz` работает
4. ✅ API доступен по `/api/v1/races`
5. ✅ Push в `web-portal` → Railway деплоит → production работает
