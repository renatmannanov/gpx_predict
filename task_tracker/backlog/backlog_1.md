# Backlog

Задачи на будущее, не критичные для текущего релиза.

---

## UX Improvements

### Hiking: показывать статус Strava (как в Trail Run)

**Приоритет:** Low
**Связано с:** Phase 1.2 (trail run Strava status)

Сейчас hiking flow:
- Есть hike profile → пропускаем вопрос об опыте
- Нет profile → спрашиваем опыт (beginner/regular/experienced)

Нет явного сообщения о статусе Strava. Для консистентности с trail run можно добавить:
- "Strava подключена, но недостаточно hiking данных"
- "Strava не подключена"

**Но:** Это менее критично чем для trail run, потому что hiking работает нормально через выбор опыта и нет путающего сообщения.

---

## Strava Sync

### Синхронизация должна начинаться с новых активностей

**Приоритет:** Medium
**Файл:** `backend/app/features/strava/sync/service.py:118-124`

**Проблема:**
Сейчас при первой синхронизации используется `after = now - 365 days`. Strava API с параметром `after` возвращает активности от старых к новым. В результате первыми загружаются активности годовой давности, а не свежие.

**Ожидаемое поведение:**
Пользователь хочет видеть свои последние активности сразу после подключения Strava.

**Решение:**
Поменять логику на `before` для первой синхронизации:
```python
# Первая синхронизация — от сейчас назад
if not sync_status.oldest_synced_date:
    before = datetime.utcnow()
    after = None
else:
    before = sync_status.oldest_synced_date
    after = None
```

Также потребуется добавить поле `oldest_synced_date` в `StravaSyncStatus`.

---

## Technical Debt

### Удалить debug logging после тестирования Phase 1.1

**Файлы:**
- `backend/app/api/v1/routes/predict.py:292-298`
- `backend/app/api/v1/routes/profiles.py:236-243`

Добавлено для отладки telegram_id и profile loading. Удалить после подтверждения что всё работает.

---
