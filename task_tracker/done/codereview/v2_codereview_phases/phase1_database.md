# Phase 1: Database & Infrastructure

> **Статус:** Не начато
> **Оценка:** ~250 строк изменений
> **Зависимости:** Phase 0a (можно делать параллельно с 0c-0f)
> **Ветка:** `refactor/phase-1-database`
> **Цель:** PostgreSQL с самого начала, исправить sync/async

---

## Проблемы

1. **Смешение sync/async в StravaSyncService** — `db.query()` внутри async функций
2. **Миграция зависит от auto-generated ID** — `537cb9c6ae39`
3. **Нет Docker для PostgreSQL**
4. **Нет connection pool настроек**

---

## Задачи

### 1.1 Docker для PostgreSQL
- [ ] Создать `docker-compose.yml`:
  ```yaml
  services:
    postgres:
      image: postgres:16
      environment:
        POSTGRES_DB: gpx_predictor
        POSTGRES_USER: gpx
        POSTGRES_PASSWORD: secret
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data

  volumes:
    postgres_data:
  ```
- [ ] Создать `docker-compose.dev.yml` (с hot reload)
- [ ] Обновить `.env.example`:
  ```
  # PostgreSQL (default for both dev and prod)
  DATABASE_URL=postgresql+asyncpg://gpx:secret@localhost:5432/gpx_predictor
  ```
- [ ] Добавить в `requirements.txt`:
  ```
  asyncpg>=0.29.0
  psycopg2-binary>=2.9.9
  ```

### 1.2 Исправление миграций
- [ ] Переименовать:
  ```
  537cb9c6ae39_add_sample_count_columns_to_user_run_.py
  →
  007a_add_sample_count_columns.py
  ```
- [ ] Обновить `down_revision` в `008_add_onboarding_and_notifications.py`:
  ```python
  down_revision = '007a_add_sample_count_columns'  # было '537cb9c6ae39'
  ```
- [ ] Проверить что цепочка миграций корректна

### 1.3 Полный async переход

**StravaSyncService** (после Phase 0 будет в `features/strava/sync/`):

Заменить все:
```python
# ❌ Было
user = self.db.query(User).filter(User.id == user_id).first()
token = self.db.query(StravaToken).filter(...).first()
activity = self.db.query(StravaActivity).filter(...).first()

# ✅ Стало
result = await self.db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

result = await self.db.execute(select(StravaToken).where(...))
token = result.scalar_one_or_none()
```

- [ ] Убрать `Union[Session, AsyncSession]` — только `AsyncSession`
- [ ] Убрать `self._is_async` проверки
- [ ] Все методы сделать async

### 1.4 Routes → async session
- [ ] `routes/strava.py`: `get_db` → `get_async_db`
- [ ] `routes/profile.py`: унифицировать (сейчас смешано)
- [ ] `routes/users.py`: проверить

### 1.5 Eager loading для relationships
- [ ] `StravaActivity.splits`:
  ```python
  splits = relationship(
      "StravaActivitySplit",
      back_populates="activity",
      lazy="selectin",  # добавить
      cascade="all, delete-orphan"
  )
  ```
- [ ] `User.notifications`:
  ```python
  notifications = relationship(
      "Notification",
      back_populates="user",
      lazy="selectin",  # изменить с "dynamic"
  )
  ```

### 1.6 Connection pool для PostgreSQL
- [ ] Обновить `backend/app/db/session.py`:
  ```python
  if settings.database_url.startswith("postgresql"):
      async_engine = create_async_engine(
          _async_url,
          pool_size=5,
          max_overflow=10,
          pool_timeout=30,
          pool_recycle=1800,  # 30 минут
      )
  ```

---

## Файлы для изменения

```
NEW:
docker-compose.yml
docker-compose.dev.yml (опционально)

RENAME:
backend/alembic/versions/537cb9c6ae39_*.py → 007a_add_sample_count_columns.py

UPDATE:
.env.example
requirements.txt
backend/alembic/versions/008_add_onboarding_and_notifications.py
backend/app/db/session.py
backend/app/features/strava/sync/service.py (или services/strava_sync.py если до Phase 0)
backend/app/features/strava/sync/activities.py
backend/app/features/strava/sync/splits.py
backend/app/features/strava/models.py (lazy settings)
backend/app/features/users/models.py (lazy settings)
backend/app/api/v1/routes/strava.py
backend/app/api/v1/routes/profile.py
```

---

## Тестирование

1. Запустить PostgreSQL:
   ```bash
   docker-compose up -d postgres
   ```

2. Применить миграции:
   ```bash
   cd backend
   alembic upgrade head
   ```

3. Проверить что приложение работает:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Проверить sync Strava (если есть токен)

---

## Критерии завершения

- [ ] Docker-compose запускает PostgreSQL
- [ ] Миграции применяются без ошибок
- [ ] Нет `db.query()` в async коде
- [ ] Все routes используют `get_async_db`
- [ ] Приложение работает с PostgreSQL

---

## После завершения

```bash
git add .
git commit -m "refactor: phase 1 - PostgreSQL and async database

- Add docker-compose.yml with PostgreSQL
- Fix migration naming (007a, 008)
- Convert all db.query() to async select()
- Update routes to use get_async_db
- Add connection pool settings

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git checkout main
git merge refactor/phase-1-database
```

Перейти к Phase 5.

---

*Phase 1 — Database & Infrastructure*
