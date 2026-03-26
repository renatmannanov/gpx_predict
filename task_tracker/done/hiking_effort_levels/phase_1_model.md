# Фаза 1: Модель UserHikingProfile + миграция

**~150 строк кода**

## Задачи

### 1.1 Добавить JSON поля и sample counts в UserHikingProfile

**Файл:** `backend/app/models/user_profile.py`

Добавить по аналогии с `UserRunProfile`:

```python
# === Sample counts per category (for confidence assessment) ===
flat_sample_count = Column(Integer, default=0)
gentle_uphill_sample_count = Column(Integer, default=0)
moderate_uphill_sample_count = Column(Integer, default=0)
steep_uphill_sample_count = Column(Integer, default=0)
gentle_downhill_sample_count = Column(Integer, default=0)
moderate_downhill_sample_count = Column(Integer, default=0)
steep_downhill_sample_count = Column(Integer, default=0)

# === 11-category gradient data (JSON) ===
gradient_paces = Column(JSON, nullable=True)
gradient_percentiles = Column(JSON, nullable=True)
```

### 1.2 Добавить хелпер-методы

В тот же файл, по аналогии с `UserRunProfile`:

- `get_sample_count(category)` — legacy 7-cat
- `get_pace_for_category(category)` — JSON (11-cat), fallback на legacy column
- `get_percentile(category, percentile)` — P25/P50/P75
- `get_sample_count_extended(category)` — JSON, fallback на legacy
- Обновить `to_dict()` — включить `gradient_paces`, `gradient_percentiles`

### 1.3 Alembic миграция

Создать миграцию для новых полей:
- 7 x Integer (sample counts)
- 2 x JSON (gradient_paces, gradient_percentiles)

```bash
cd backend && alembic revision --autogenerate -m "add gradient_paces and sample_counts to hiking profile"
```

## Проверка

- [ ] Миграция применяется без ошибок
- [ ] `UserHikingProfile` имеет все новые поля
- [ ] Хелпер-методы работают (JSON → fallback → None)
- [ ] `to_dict()` возвращает новые поля
- [ ] Существующие тесты не ломаются
