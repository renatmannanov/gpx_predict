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

## Technical Debt

### Удалить debug logging после тестирования Phase 1.1

**Файлы:**
- `backend/app/api/v1/routes/predict.py:292-298`
- `backend/app/api/v1/routes/profiles.py:236-243`

Добавлено для отладки telegram_id и profile loading. Удалить после подтверждения что всё работает.

---
