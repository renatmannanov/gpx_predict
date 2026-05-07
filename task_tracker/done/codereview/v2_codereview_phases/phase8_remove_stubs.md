# Phase 8: Remove Stubs

> **Сложность:** 🟢 Низкая
> **Время:** ~5 минут
> **Строк:** ~30
> **Файлов:** 2
> **Зависимости:** Нет

---

## Проблема

В `features/hiking/service.py` есть stub класс `HikingPredictionService` с `NotImplementedError`:

```python
class HikingPredictionService:
    async def predict(self, request: HikePredictRequest) -> HikePrediction:
        raise NotImplementedError("Will be implemented in Phase 6")
```

**Почему это плохо:**
- Создаёт путаницу - какой сервис использовать?
- Реальная логика в `services/prediction.py`
- Stub никогда не будет реализован (prediction - кросс-фичёвый)

---

## Решение

Удалить stub, оставить только re-export схем.

---

## Чеклист

### 1. Обновить features/hiking/service.py

- [ ] Открыть `backend/app/features/hiking/service.py`
- [ ] Удалить класс `HikingPredictionService`
- [ ] Оставить импорт схем для удобства

**До:**
```python
"""
Hiking prediction service.

Main entry point for hiking time predictions.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import HikePredictRequest, HikePrediction


class HikingPredictionService:
    """..."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def predict(self, request: HikePredictRequest) -> HikePrediction:
        raise NotImplementedError("Will be implemented in Phase 6")
```

**После:**
```python
"""
Hiking module exports.

For predictions, use app.services.prediction.PredictionService
which orchestrates both hiking and trail_run calculations.
"""

# Re-export schemas for convenience
from .schemas import HikePredictRequest, HikePrediction

__all__ = ["HikePredictRequest", "HikePrediction"]
```

### 2. Обновить features/hiking/__init__.py

- [ ] Убрать импорт `HikingPredictionService` если есть
- [ ] Проверить что остальные экспорты работают

### 3. Проверка

- [ ] `python -m pytest tests/ -v` - все тесты проходят
- [ ] Grep по коду: нет импортов `HikingPredictionService`

```bash
grep -r "HikingPredictionService" backend/
# Должно быть пусто
```

---

## Файлы для изменения

| Файл | Действие |
|------|----------|
| `backend/app/features/hiking/service.py` | Удалить stub класс |
| `backend/app/features/hiking/__init__.py` | Убрать экспорт если есть |

---

## Результат

- ✅ Нет путаницы между двумя "prediction service"
- ✅ Документация указывает на правильный сервис
- ✅ Меньше кода = меньше путаницы

---

*Phase 8 of v2.1 cleanup*
