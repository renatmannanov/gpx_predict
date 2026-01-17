# Claude Code Rules for GPX Predictor

## Перед началом работы

1. **ВСЕГДА** читай `docs/ARCHITECTURE.md` для понимания структуры проекта
2. **ВСЕГДА** читай `docs/ARCHITECTURE_CALCULATIONS.md` перед изменением расчётов
3. **ВСЕГДА** проверяй `docs/CODE_REVIEW.md` для известных проблем

## Калькуляторы времени

В проекте **3 метода расчёта** (все нужны, НЕ удалять и НЕ объединять):

| Метод | Файл | Описание |
|-------|------|----------|
| `tobler` | `calculators/tobler.py` | Tobler's Hiking Function (1993) |
| `naismith` | `calculators/naismith.py` | Naismith + Langmuir corrections |
| `old_naismith` | `services/naismith.py` | Naismith + Tranter's corrections |

Они дают **разные результаты** — это нормально:
```
tobler:       5ч 28мин
naismith:     5ч 15мин
old_naismith: 6ч 26мин
```

## Запреты

- **НЕ** дублировать утилиты — использовать существующие:
  - `haversine` — в `gpx_parser.py` или `segmenter.py`
  - `elevation smoothing` — в `gpx_parser.py` или `segmenter.py`

- **НЕ** создавать новые методы для token refresh/exchange — использовать `StravaClient`

- **НЕ** смешивать sync/async Session без явной необходимости

- **НЕ** удалять или объединять калькуляторы без явного указания

## Документирование

При любых изменениях в коде:

1. **Изменения в расчётах** → обновить `docs/ARCHITECTURE_CALCULATIONS.md`
2. **Изменения в структуре** → обновить `docs/ARCHITECTURE.md`
3. **Исправление проблем из ревью** → обновить статус в `docs/CODE_REVIEW.md`
4. **Новые сервисы/модели** → добавить в `docs/ARCHITECTURE.md`

## Структура проекта

```
backend/app/
├── api/v1/routes/     # API endpoints
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic schemas
├── services/          # Business logic
│   └── calculators/   # Калькуляторы времени
└── repositories/      # Data access
```

## Известные проблемы (TODO)

См. `docs/CODE_REVIEW.md` для полного списка. Ключевые:

1. Персонализация требует рефакторинга (отдельная задача)
2. Дублирование token management в routes/strava.py
3. Дублирование haversine и elevation smoothing
4. Смешение sync/async Session
