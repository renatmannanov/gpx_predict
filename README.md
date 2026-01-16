# GPX Predictor

Сервис прогнозирования времени походов и забегов с учётом рельефа.

## Быстрый старт

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env

# Миграции
alembic upgrade head

# Запуск
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Структура проекта

```
gpx-predictor/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Settings
│   │   ├── api/v1/routes/    # API endpoints
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── repositories/     # Data access
│   │   ├── services/         # Business logic
│   │   └── db/               # Database setup
│   ├── tests/
│   └── alembic/
│
├── frontend/
│   └── src/
│       ├── api/              # API client
│       ├── components/       # React components
│       ├── hooks/            # Custom hooks
│       └── pages/            # Page components
│
└── docs/                     # Documentation
```

## Технологии

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL + PostGIS
- Alembic
- gpxpy

### Frontend
- React 18
- TypeScript
- React Query
- Tailwind CSS
- Vite

## Фазы разработки

1. **MVP для туристов** — Naismith, профилирование, safety
2. **Расширение** — Группы, база маршрутов, Telegram
3. **Бегуны** — Riegel, GAP
4. **Strava** — OAuth, Webhooks
5. **Growth** — Monetization, Share

## Документация

- [Фаза 1: MVP](docs/phase-1-mvp.md)
- [Архитектура](docs/architecture.md)
- [API Reference](docs/api.md)

## License

Private
