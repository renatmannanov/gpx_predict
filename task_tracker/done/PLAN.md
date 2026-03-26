# План: Исправление Strava Sync Flow

## Проблемы

1. **Синхронизация останавливается после первого batch** — пользователь не добавляется обратно в очередь
2. **`total_activities_estimated` не заполняется** — checkpoints 30%/60% не работают
3. **Профиль не пересчитывается** — первый checkpoint = 5 активностей, а бывает меньше
4. **Много уведомлений** — каждые 10 активностей при 400 активностях = 40 уведомлений
5. **Медленная синхронизация** — 5 минут между batches, нет настройки для dev/prod

---

## Общая логика (ВАЖНО!)

### Два этапа синхронизации:

**Этап 1: Первый batch (сразу после OAuth)**
- Загружаем первые 10 активностей
- Считаем профиль
- Отправляем **ОДНО** уведомление с качеством профиля:
  - 0 активностей → "Нет подходящих активностей"
  - 1-4 активности → "Профиль приблизительный"
  - 5-10 активностей → "Профиль базовый"

**Этап 2: Фоновая загрузка (по процентам от total)**
- Продолжаем загружать в фоне
- При **30%** → пересчёт профиля + уведомление
- При **60%** → пересчёт профиля + уведомление
- При **100%** → финальный пересчёт + "Профиль полный, будет обновляться с каждой новой активностью"

### Итого: 4 уведомления за всю синхронизацию
1. После первого batch (сразу)
2. При 30%
3. При 60%
4. При 100% (финал)

---

## Решение

### Часть 1: Конфигурация (config.py)

**Новые параметры:**

```python
class SyncConfig:
    # === Существующие (без изменений) ===
    ACTIVITIES_PER_PAGE = 30
    ACTIVITIES_PER_USER_BATCH = 10
    USERS_PER_BATCH = 5
    MIN_SYNC_INTERVAL_HOURS = 6
    MAX_HISTORY_DAYS = 365
    API_CALL_DELAY = 1.5

    # === ИЗМЕНЕНО: Качество профиля после первого batch ===
    # Определяет ТЕКСТ сообщения после первого batch:
    # - 0: "Нет подходящих активностей"
    # - 1-4: "Профиль приблизительный"
    # - 5+: "Профиль базовый"
    FIRST_BATCH_QUALITY_THRESHOLD = 5  # граница между "приблизительный" и "базовый"

    # === ИЗМЕНЕНО: Checkpoints для пересчёта и уведомлений ===
    # После первого batch — пересчёт и уведомление при этих процентах от total
    SYNC_PROGRESS_CHECKPOINTS = [30, 60, 100]  # проценты

    # === ИЗМЕНЕНО: Post-Initial Sync ===
    POST_SYNC_RECALC_MIN_NEW_ACTIVITIES = 3  # без изменений

    # === НОВОЕ: Priority Sync Settings ===
    # Для dev: быстрая синхронизация
    # Для prod: соответствие rate limits
    PRIORITY_SYNC_BATCH_DELAY_SECONDS = 5  # dev: 5, prod: 60
    PRIORITY_SYNC_MAX_CONSECUTIVE_BATCHES = 10  # dev: 10, prod: 3
    BACKGROUND_SYNC_INTERVAL_SECONDS = 300  # 5 минут (без изменений)
```

**Удалено:**
- `INITIAL_RECALC_AFTER_N_ACTIVITIES = 5`
- `INITIAL_RECALC_PROGRESS_CHECKPOINTS = [30, 60]`
- `PROGRESS_NOTIFICATION_INTERVAL = 10`

---

### Часть 2: Заполнение total_activities_estimated (service.py)

**Где:** При первой синхронизации пользователя

**Как:**
1. Вызвать `get_athlete_stats()` для получения `all_run_totals.count`
2. Записать в `sync_status.total_activities_estimated`

**Ограничение:** Strava даёт только run/ride/swim totals, не hike. Поэтому estimate будет только для run-активностей.

**Изменения в `sync_user_activities()`:**

```python
# В начале sync_user_activities(), если это первый sync:
if sync_status.total_activities_estimated is None:
    try:
        stats = await self._fetch_athlete_stats(access_token, token.strava_athlete_id)
        # Берём run_totals как estimate (Strava не даёт hike totals)
        run_count = stats.get("all_run_totals", {}).get("count", 0)
        sync_status.total_activities_estimated = run_count
    except Exception as e:
        logger.warning(f"Failed to fetch athlete stats: {e}")
        # Fallback: оставляем None, логика checkpoints справится
```

---

### Часть 3: Логика после первого batch (service.py)

**После первого batch — ВСЕГДА пересчитываем профиль и отправляем уведомление:**

```python
async def _handle_first_batch_complete(self, user_id: str, sync_status: StravaSyncStatus):
    """
    Обработка завершения первого batch.

    Всегда пересчитывает профиль и отправляет уведомление с качеством.
    """
    activities_with_splits = sync_status.activities_with_splits or 0

    # Определяем качество профиля для сообщения
    if activities_with_splits == 0:
        quality = "none"
    elif activities_with_splits < SyncConfig.FIRST_BATCH_QUALITY_THRESHOLD:
        quality = "preliminary"  # 1-4 активности
    else:
        quality = "basic"  # 5-10 активностей

    # Пересчитываем профиль (если есть данные)
    if activities_with_splits > 0:
        await self._recalculate_profiles(user_id)

    # Отправляем уведомление
    await self._create_notification(
        user_id=user_id,
        notification_type="first_batch_complete",
        data={
            "quality": quality,
            "activities_with_splits": activities_with_splits,
            "total_synced": sync_status.total_activities_synced
        }
    )

    # Отмечаем что первый batch обработан
    sync_status.first_batch_notified = True
```

---

### Часть 4: Логика checkpoints 30%/60%/100% (service.py)

**После первого batch — уведомления при достижении процентов:**

```python
async def _check_progress_checkpoint(self, user_id: str, sync_status: StravaSyncStatus):
    """
    Проверяет, достигнут ли checkpoint для пересчёта и уведомления.

    Checkpoints: 30%, 60%, 100% от total_estimated.
    """
    # Пропускаем если первый batch ещё не обработан
    if not sync_status.first_batch_notified:
        return

    total_estimated = sync_status.total_activities_estimated
    if not total_estimated or total_estimated == 0:
        return

    current_percent = (sync_status.total_activities_synced / total_estimated) * 100
    last_checkpoint = sync_status.last_progress_checkpoint or 0

    for checkpoint in SyncConfig.SYNC_PROGRESS_CHECKPOINTS:
        if last_checkpoint < checkpoint <= current_percent:
            # Достигли нового checkpoint
            sync_status.last_progress_checkpoint = checkpoint

            # Пересчитываем профиль
            await self._recalculate_profiles(user_id)

            # Определяем тип уведомления
            if checkpoint == 100:
                notification_type = "sync_complete"
                quality = "full"
            else:
                notification_type = "sync_progress"
                quality = "improving"

            # Отправляем уведомление
            await self._create_notification(
                user_id=user_id,
                notification_type=notification_type,
                data={
                    "checkpoint_percent": checkpoint,
                    "activities_with_splits": sync_status.activities_with_splits,
                    "total_synced": sync_status.total_activities_synced,
                    "quality": quality
                }
            )

            break  # Один checkpoint за раз
```

---

### Часть 5: Новые поля в модели (models.py)

```python
class StravaSyncStatus(Base):
    # ... существующие поля ...

    # НОВОЕ: Флаг что первый batch обработан и уведомление отправлено
    first_batch_notified = Column(Integer, default=0)  # Boolean as int

    # НОВОЕ: Последний достигнутый checkpoint (30, 60, 100)
    last_progress_checkpoint = Column(Integer, default=0)
```

**Удалено/переименовано:**
- `last_recalc_checkpoint` → `last_progress_checkpoint` (другая семантика)

---

### Часть 6: Requeue после batch (background.py)

**Изменения в `_process_batch()`:**

```python
async def _process_batch(self):
    """Process one batch of users."""
    user_ids = await sync_queue.get_next_users(SyncConfig.USERS_PER_BATCH)

    if not user_ids:
        await self._refresh_queue()
        return

    logger.info(f"Processing sync batch: {len(user_ids)} users")

    for user_id in user_ids:
        try:
            async with self._db_factory() as db:
                service = StravaSyncService(db)
                result = await service.sync_user_activities(user_id)
                logger.debug(f"Sync result for {user_id}: {result}")

                # НОВОЕ: Requeue если initial sync не завершён
                if result.get("status") == "success":
                    sync_status = await self._get_sync_status(db, user_id)
                    if sync_status and not sync_status.initial_sync_complete:
                        await sync_queue.requeue_user(user_id)
                        logger.debug(f"Requeued user {user_id} (initial sync incomplete)")

            await asyncio.sleep(SyncConfig.API_CALL_DELAY)

        except Exception as e:
            logger.error(f"Error syncing user {user_id}: {e}")

        finally:
            await sync_queue.mark_complete(user_id)
```

---

### Часть 7: Priority Sync для быстрой синхронизации (background.py)

**Новый метод для priority users:**

```python
async def run_priority_sync(self, user_id: str):
    """
    Запускает ускоренную синхронизацию для priority user.

    Делает несколько batches подряд с минимальной паузой.
    Используется после OAuth или по запросу пользователя.
    """
    logger.info(f"Starting priority sync for user {user_id}")

    batches_done = 0
    max_batches = SyncConfig.PRIORITY_SYNC_MAX_CONSECUTIVE_BATCHES

    while batches_done < max_batches:
        async with self._db_factory() as db:
            service = StravaSyncService(db)
            result = await service.sync_user_activities(user_id)

            if result.get("status") != "success":
                logger.warning(f"Priority sync batch failed: {result}")
                break

            # Проверяем, завершена ли синхронизация
            sync_status = await self._get_sync_status(db, user_id)
            if sync_status and sync_status.initial_sync_complete:
                logger.info(f"Priority sync complete for user {user_id}")
                break

        batches_done += 1

        # Пауза между batches (настраиваемая)
        await asyncio.sleep(SyncConfig.PRIORITY_SYNC_BATCH_DELAY_SECONDS)

    logger.info(f"Priority sync finished for {user_id}: {batches_done} batches")
```

**Изменения в `trigger_user_sync()`:**

```python
async def trigger_user_sync(user_id: str, priority: bool = True):
    """
    Trigger sync for a user.

    If priority=True, runs immediate priority sync (multiple batches).
    Otherwise, adds to background queue.
    """
    if priority and background_sync._running:
        # Запускаем priority sync в отдельной task
        asyncio.create_task(background_sync.run_priority_sync(user_id))
    else:
        await sync_queue.add_user(user_id, priority=True)

    logger.info(f"Triggered {'priority' if priority else 'background'} sync for user {user_id}")
```

---

### Часть 8: Формат уведомлений (notification_formatter.py)

**Новый тип: first_batch_complete**

```python
def _format_first_batch_complete(data: dict) -> str:
    """
    Уведомление после первого batch.

    Качество:
    - none: 0 активностей
    - preliminary: 1-4 активности
    - basic: 5-10 активностей
    """
    quality = data.get("quality", "none")
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    if quality == "none":
        return (
            "<b>📥 Синхронизация Strava</b>\n\n"
            f"Загружено: {total_synced} активностей\n\n"
            "❌ Нет подходящих активностей для профиля бегуна.\n"
            "Нужны Run или TrailRun активности.\n\n"
            "Синхронизация продолжается..."
        )
    elif quality == "preliminary":
        return (
            "<b>📊 Профиль бегуна создан</b>\n\n"
            f"Проанализировано: {activities} активностей\n\n"
            "⚠️ Профиль приблизительный — нужно больше активностей\n\n"
            "Синхронизация продолжается — профиль будет улучшаться.\n"
            "👉 /profile — посмотреть профиль"
        )
    else:  # basic
        return (
            "<b>📊 Профиль бегуна создан</b>\n\n"
            f"Проанализировано: {activities} активностей\n\n"
            "📊 Профиль базовый\n\n"
            "Синхронизация продолжается — профиль будет улучшаться.\n"
            "👉 /profile — посмотреть профиль"
        )
```

**Обновлённый формат sync_progress (для 30%/60%):**

```python
def _format_sync_progress(data: dict) -> str:
    """
    Уведомление при достижении checkpoint (30%, 60%).
    """
    checkpoint = data.get("checkpoint_percent", 0)
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    return (
        "<b>📊 Профиль бегуна обновлён</b>\n\n"
        f"Проанализировано: {activities} активностей\n"
        f"Загружено: {total_synced} активностей ({checkpoint}%)\n\n"
        "Синхронизация продолжается — профиль будет улучшаться.\n"
        "👉 /profile — посмотреть профиль"
    )
```

**Обновлённый формат sync_complete (для 100%):**

```python
def _format_sync_complete(data: dict) -> str:
    """
    Финальное уведомление при 100% синхронизации.
    """
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    return (
        "<b>✅ Синхронизация Strava завершена!</b>\n\n"
        f"Загружено: {total_synced} активностей\n"
        f"Проанализировано для профиля: {activities}\n\n"
        "✅ Профиль полный — прогнозы максимально точные!\n\n"
        "Теперь профиль будет обновляться автоматически "
        "с каждой новой активностью.\n\n"
        "👉 /profile — посмотреть профиль\n"
        "👉 /predict — сделать прогноз"
    )
```

---

### Часть 9: Миграция БД

**Новые поля:**
```python
# В StravaSyncStatus
first_batch_notified = Column(Integer, default=0)  # Boolean as int
last_progress_checkpoint = Column(Integer, default=0)  # 0, 30, 60, 100
```

**Миграция:**
```python
# alembic revision
def upgrade():
    op.add_column(
        'strava_sync_status',
        sa.Column('first_batch_notified', sa.Integer(), default=0)
    )
    op.add_column(
        'strava_sync_status',
        sa.Column('last_progress_checkpoint', sa.Integer(), default=0)
    )
    # Удаляем старое поле (если нужно)
    # op.drop_column('strava_sync_status', 'last_recalc_checkpoint')

def downgrade():
    op.drop_column('strava_sync_status', 'first_batch_notified')
    op.drop_column('strava_sync_status', 'last_progress_checkpoint')
```

---

## Файлы для изменения

| Файл | Изменения |
|------|-----------|
| `backend/app/features/strava/sync/config.py` | Новые параметры конфигурации |
| `backend/app/features/strava/sync/service.py` | Логика first_batch + checkpoints, заполнение estimated |
| `backend/app/features/strava/sync/background.py` | Requeue, priority sync |
| `backend/app/features/strava/models.py` | Новые поля `first_batch_notified`, `last_progress_checkpoint` |
| `backend/app/shared/notification_formatter.py` | Новые форматы сообщений |
| `alembic/versions/xxx_sync_status_fields.py` | Миграция |
| `docs/ARCHITECTURE.md` | Обновить документацию |

---

## Порядок реализации

1. **Миграция БД** — добавить поля `first_batch_notified`, `last_progress_checkpoint`
2. **config.py** — новые параметры
3. **models.py** — новые поля в StravaSyncStatus
4. **service.py** — логика first_batch + checkpoints + estimated
5. **background.py** — requeue и priority sync
6. **notification_formatter.py** — форматы сообщений
7. **ARCHITECTURE.md** — документация
8. **Тестирование**

---

## Ожидаемый результат

### До:
```
"Прогресс синхронизации
Загружено: 10 из ~0 активностей (10%)
Синхронизация продолжается в фоне..."

[Тишина 5 минут]
[Синхронизация остановилась]
[Профиль не пересчитался]
```

### После (пример для пользователя с 400 активностями):

**Уведомление 1 (сразу после OAuth, первый batch):**
```
📊 Профиль бегуна создан

Проанализировано: 7 активностей

📊 Профиль базовый

Синхронизация продолжается — профиль будет улучшаться.
👉 /profile — посмотреть профиль
```

**Уведомление 2 (при 30% = ~120 активностей):**
```
📊 Профиль бегуна обновлён

Проанализировано: 95 активностей
Загружено: 120 активностей (30%)

Синхронизация продолжается — профиль будет улучшаться.
👉 /profile — посмотреть профиль
```

**Уведомление 3 (при 60% = ~240 активностей):**
```
📊 Профиль бегуна обновлён

Проанализировано: 190 активностей
Загружено: 240 активностей (60%)

Синхронизация продолжается — профиль будет улучшаться.
👉 /profile — посмотреть профиль
```

**Уведомление 4 (при 100% = все 400 активностей):**
```
✅ Синхронизация Strava завершена!

Загружено: 400 активностей
Проанализировано для профиля: 350

✅ Профиль полный — прогнозы максимально точные!

Теперь профиль будет обновляться автоматически с каждой новой активностью.

👉 /profile — посмотреть профиль
👉 /predict — сделать прогноз
```
