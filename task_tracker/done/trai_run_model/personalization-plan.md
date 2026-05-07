# План персонализации предсказаний GPX Predictor

> Дата создания: 2026-01-16
> Статус: Фазы 1-2 завершены ✅

## Обзор

Цель: улучшить точность предсказаний времени прохождения маршрутов за счёт персонализации на основе реальных данных пользователя из Strava.

---

## Текущее состояние

### Что есть:
- Модели: User, StravaToken, StravaActivity, StravaSyncStatus, GPXFile, Prediction
- Синхронизация активностей из Strava (агрегированные метрики)
- Алгоритмы: Naismith, Tobler, множители профиля
- Профиль пользователя **НЕ хранится** — передаётся в каждом запросе

### Проблемы:
1. Опыт пользователя определяется субъективно ("как часто ходишь")
2. Нет калибровки на реальных данных конкретного человека
3. Не используются splits (отрезки) из Strava — а там есть темп по градиенту!
4. Нет обратной связи: prediction vs actual time

---

## Фазы реализации

### Фаза 1: Персональный профиль пользователя ✅
**Приоритет: HIGH**
**Статус: DONE** (2026-01-16)

**Реализовано:**
- ✅ Модель `UserPerformanceProfile` в `backend/app/models/user_profile.py`
- ✅ Relationship в `User` модели
- ✅ Миграция `004_add_user_performance_profile.py`
- ✅ Сервис `UserProfileService` в `backend/app/services/user_profile.py`
- ✅ Интеграция в `PredictionService.predict_hike()` с параметром `user_profile`

#### 1.1 Новая модель UserPerformanceProfile

```python
# backend/app/models/user_profile.py

class UserPerformanceProfile(Base):
    __tablename__ = "user_performance_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False)

    # === Базовые метрики темпа (вычисляются из splits) ===
    avg_flat_pace_min_km = Column(Float, nullable=True)      # Темп на равнине (gradient -3% to +3%)
    avg_uphill_pace_min_km = Column(Float, nullable=True)    # Темп на подъёме (gradient > +3%)
    avg_downhill_pace_min_km = Column(Float, nullable=True)  # Темп на спуске (gradient < -3%)

    # === Персональные коэффициенты ===
    # Насколько человек замедляется на подъёмах vs стандарт Naismith
    # 1.0 = стандартно, <1.0 = быстрее стандарта, >1.0 = медленнее
    vertical_ability = Column(Float, default=1.0)

    # === Статистика для расчётов ===
    total_activities_analyzed = Column(Integer, default=0)
    total_hike_activities = Column(Integer, default=0)
    total_distance_km = Column(Float, default=0.0)
    total_elevation_m = Column(Float, default=0.0)

    # === Метаданные ===
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="performance_profile")
```

#### 1.2 Сервис расчёта профиля

```python
# backend/app/services/user_profile.py

class UserProfileService:

    @staticmethod
    async def calculate_profile(
        user_id: str,
        db: AsyncSession
    ) -> UserPerformanceProfile:
        """
        Рассчитать/обновить профиль пользователя на основе его активностей.
        Базовая версия — без splits, использует общий темп.
        """
        # 1. Получить активности пользователя (Hike, Walk)
        activities = await get_user_activities(
            user_id,
            activity_types=["Hike", "Walk"],
            limit=50  # Последние 50 активностей
        )

        if len(activities) < 3:
            # Недостаточно данных для персонализации
            return None

        # 2. Базовый темп (без учёта рельефа)
        avg_pace = calculate_average_pace(activities)

        # 3. Создать/обновить профиль
        profile = UserPerformanceProfile(
            user_id=user_id,
            avg_flat_pace_min_km=avg_pace,  # Пока без splits — общий темп
            total_activities_analyzed=len(activities),
            total_hike_activities=len([a for a in activities if a.activity_type == "Hike"]),
            total_distance_km=sum(a.distance_m / 1000 for a in activities),
            total_elevation_m=sum(a.elevation_gain_m for a in activities),
            last_calculated_at=datetime.utcnow()
        )

        return profile

    @staticmethod
    def calculate_average_pace(activities: list[StravaActivity]) -> float:
        """Средний темп в мин/км."""
        total_time = sum(a.moving_time_s for a in activities)
        total_distance = sum(a.distance_m for a in activities)

        if total_distance == 0:
            return None

        pace_min_km = (total_time / 60) / (total_distance / 1000)
        return round(pace_min_km, 2)
```

#### 1.3 Интеграция в prediction

```python
# backend/app/services/prediction.py

class PredictionService:

    @staticmethod
    async def predict_hike_personalized(
        gpx_id: str,
        experience: ExperienceLevel,
        backpack: BackpackWeight,
        group_size: int,
        # ... other params
        db: AsyncSession,
        user_id: Optional[str] = None  # NEW: для персонализации
    ) -> HikePrediction:

        # Получить персональный профиль (если есть)
        personal_profile = None
        if user_id:
            personal_profile = await UserProfileService.get_profile(user_id, db)

        # Базовая скорость
        if personal_profile and personal_profile.avg_flat_pace_min_km:
            # Используем реальный темп пользователя
            base_speed_kmh = 60 / personal_profile.avg_flat_pace_min_km
        else:
            # Fallback на стандартный Naismith
            base_speed_kmh = 5.0

        # Корректировка множителя опыта
        experience_mult = get_experience_multiplier(experience)
        if personal_profile:
            # Если есть данные — уменьшаем влияние субъективного опыта
            experience_mult = 1.0 + (experience_mult - 1.0) * 0.5

        # Остальной расчёт...
```

#### 1.4 Миграция Alembic

```python
# 004_add_user_performance_profile.py

def upgrade():
    op.create_table(
        'user_performance_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', UUID(), sa.ForeignKey('users.id'), unique=True, nullable=False),

        # Pace metrics
        sa.Column('avg_flat_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_downhill_pace_min_km', sa.Float(), nullable=True),

        # Coefficients
        sa.Column('vertical_ability', sa.Float(), default=1.0),

        # Stats
        sa.Column('total_activities_analyzed', sa.Integer(), default=0),
        sa.Column('total_hike_activities', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Float(), default=0.0),
        sa.Column('total_elevation_m', sa.Float(), default=0.0),

        # Meta
        sa.Column('last_calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
    )

    op.create_index('ix_user_performance_profiles_user_id', 'user_performance_profiles', ['user_id'])

def downgrade():
    op.drop_table('user_performance_profiles')
```

---

### Фаза 2: Сбор Splits из Strava ✅
**Приоритет: HIGH**
**Статус: DONE** (2026-01-16)

**Реализовано:**
- ✅ Модель `StravaActivitySplit` в `backend/app/models/strava_activity.py`
- ✅ Флаг `splits_synced` и relationship в `StravaActivity`
- ✅ Миграция `005_add_strava_activity_splits.py`
- ✅ Метод `get_activity_with_splits()` в `StravaClient`
- ✅ Методы `sync_activity_splits()` и `sync_splits_for_user()` в `StravaSyncService`
- ✅ Метод `calculate_profile_with_splits()` в `UserProfileService`

#### 2.1 Новая модель StravaActivitySplit

```python
# backend/app/models/strava_activity.py (добавить)

class StravaActivitySplit(Base):
    """
    Splits (отрезки ~1км) из Strava активности.
    Содержит агрегированные метрики — можно хранить долгосрочно.
    """
    __tablename__ = "strava_activity_splits"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("strava_activities.id"), nullable=False)

    # Split info
    split_number = Column(Integer, nullable=False)  # 1, 2, 3...
    distance_m = Column(Float, nullable=False)      # обычно ~1000м

    # Time
    moving_time_s = Column(Integer, nullable=False)
    elapsed_time_s = Column(Integer, nullable=False)

    # КЛЮЧЕВОЕ: высота на сплите
    elevation_diff_m = Column(Float, nullable=True)  # +/- метры

    # Performance
    average_speed_mps = Column(Float, nullable=True)
    average_heartrate = Column(Float, nullable=True)
    pace_zone = Column(Integer, nullable=True)

    # Вычисляемые свойства
    @property
    def pace_min_km(self) -> Optional[float]:
        if self.distance_m and self.moving_time_s:
            return (self.moving_time_s / 60) / (self.distance_m / 1000)
        return None

    @property
    def gradient_percent(self) -> Optional[float]:
        if self.distance_m and self.elevation_diff_m:
            return (self.elevation_diff_m / self.distance_m) * 100
        return None

    # Relationship
    activity = relationship("StravaActivity", back_populates="splits")
```

#### 2.2 Расширение StravaClient

```python
# backend/app/services/strava.py (добавить метод)

async def get_activity_with_splits(
    self,
    access_token: str,
    activity_id: int
) -> dict:
    """
    Получить детальную активность со splits.

    Returns:
        {
            "id": 123,
            "name": "Morning Hike",
            "splits_metric": [
                {
                    "split": 1,
                    "distance": 1007.7,
                    "elapsed_time": 171,
                    "moving_time": 170,
                    "elevation_difference": 25.8,
                    "average_speed": 5.93,
                    "average_heartrate": 138.79,
                    "pace_zone": 0
                },
                ...
            ]
        }
    """
    return await self._api_request(
        "GET",
        f"/activities/{activity_id}",
        access_token,
        params={"include_all_efforts": "false"}
    )
```

#### 2.3 Расширение StravaSyncService

```python
# backend/app/services/strava_sync.py (модифицировать)

async def sync_activity_splits(
    self,
    user_id: str,
    activity_id: int,
    db: AsyncSession
) -> list[StravaActivitySplit]:
    """
    Синхронизировать splits для конкретной активности.
    Вызывается после основной синхронизации активностей.
    """
    token = await self.strava_client.get_valid_token(user_id)
    if not token:
        raise StravaAuthError("No valid token")

    # Получить детальную активность
    activity_data = await self.strava_client.get_activity_with_splits(
        token,
        activity_id
    )

    splits_data = activity_data.get("splits_metric", [])
    if not splits_data:
        return []

    # Найти нашу активность в БД
    activity = await db.execute(
        select(StravaActivity).where(StravaActivity.strava_id == activity_id)
    )
    activity = activity.scalar_one_or_none()

    if not activity:
        return []

    # Сохранить splits
    splits = []
    for split_data in splits_data:
        split = StravaActivitySplit(
            activity_id=activity.id,
            split_number=split_data.get("split"),
            distance_m=split_data.get("distance"),
            moving_time_s=split_data.get("moving_time"),
            elapsed_time_s=split_data.get("elapsed_time"),
            elevation_diff_m=split_data.get("elevation_difference"),
            average_speed_mps=split_data.get("average_speed"),
            average_heartrate=split_data.get("average_heartrate"),
            pace_zone=split_data.get("pace_zone")
        )
        db.add(split)
        splits.append(split)

    await db.commit()
    return splits
```

#### 2.4 Улучшенный расчёт профиля с splits

```python
# backend/app/services/user_profile.py (улучшить)

@staticmethod
async def calculate_profile_with_splits(
    user_id: str,
    db: AsyncSession
) -> UserPerformanceProfile:
    """
    Расчёт профиля на основе splits — точный темп по рельефу.
    """
    # Получить все splits пользователя
    splits = await db.execute(
        select(StravaActivitySplit)
        .join(StravaActivity)
        .where(StravaActivity.user_id == user_id)
        .where(StravaActivity.activity_type.in_(["Hike", "Walk"]))
    )
    splits = splits.scalars().all()

    if len(splits) < 10:
        # Недостаточно данных — использовать базовый расчёт
        return await calculate_profile(user_id, db)

    # Классифицировать splits по рельефу
    flat_splits = []      # gradient -3% to +3%
    uphill_splits = []    # gradient > +3%
    downhill_splits = []  # gradient < -3%

    for split in splits:
        gradient = split.gradient_percent
        if gradient is None:
            continue

        if -3 <= gradient <= 3:
            flat_splits.append(split)
        elif gradient > 3:
            uphill_splits.append(split)
        else:
            downhill_splits.append(split)

    # Рассчитать средний темп по категориям
    avg_flat_pace = mean([s.pace_min_km for s in flat_splits]) if flat_splits else None
    avg_uphill_pace = mean([s.pace_min_km for s in uphill_splits]) if uphill_splits else None
    avg_downhill_pace = mean([s.pace_min_km for s in downhill_splits]) if downhill_splits else None

    # Vertical ability: насколько замедляется на подъёмах vs Naismith
    # Naismith: +1 час на 600м ≈ +10 мин на 100м ≈ темп растёт на ~2 мин/км при 10% градиенте
    vertical_ability = 1.0
    if avg_flat_pace and avg_uphill_pace:
        # Реальное замедление vs ожидаемое
        expected_uphill_pace = avg_flat_pace * 1.5  # Naismith expectation
        actual_ratio = avg_uphill_pace / avg_flat_pace
        expected_ratio = 1.5
        vertical_ability = actual_ratio / expected_ratio

    profile = UserPerformanceProfile(
        user_id=user_id,
        avg_flat_pace_min_km=avg_flat_pace,
        avg_uphill_pace_min_km=avg_uphill_pace,
        avg_downhill_pace_min_km=avg_downhill_pace,
        vertical_ability=vertical_ability,
        total_activities_analyzed=len(set(s.activity_id for s in splits)),
        last_calculated_at=datetime.utcnow()
    )

    return profile
```

---

### Фаза 3: Матчинг GPX ↔ Strava Activity
**Приоритет: MEDIUM**
**Статус: TODO**

#### 3.1 Сервис матчинга

```python
# backend/app/services/activity_matcher.py

class ActivityMatcherService:
    """
    Сопоставление GPX маршрутов с реальными активностями из Strava.
    """

    # Пороги для матчинга
    DISTANCE_THRESHOLD_M = 500      # ±500м
    ELEVATION_THRESHOLD_M = 100     # ±100м

    @staticmethod
    async def find_matching_activity(
        gpx: GPXFile,
        user_id: str,
        db: AsyncSession,
        date_hint: Optional[date] = None
    ) -> Optional[StravaActivity]:
        """
        Найти активность, которая соответствует GPX маршруту.

        Args:
            gpx: GPX файл с маршрутом
            user_id: ID пользователя
            date_hint: Примерная дата прохождения (если известна)

        Returns:
            Matching StravaActivity или None
        """
        # Запрос активностей
        query = (
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(["Hike", "Walk"]))
        )

        if date_hint:
            # Искать в диапазоне ±3 дня от указанной даты
            query = query.where(
                StravaActivity.start_date.between(
                    date_hint - timedelta(days=3),
                    date_hint + timedelta(days=3)
                )
            )

        result = await db.execute(query.order_by(StravaActivity.start_date.desc()))
        activities = result.scalars().all()

        gpx_distance_m = gpx.distance_km * 1000
        gpx_elevation_m = gpx.elevation_gain_m

        for activity in activities:
            # Проверка по дистанции
            distance_diff = abs(activity.distance_m - gpx_distance_m)
            if distance_diff > ActivityMatcherService.DISTANCE_THRESHOLD_M:
                continue

            # Проверка по набору высоты
            elevation_diff = abs(activity.elevation_gain_m - gpx_elevation_m)
            if elevation_diff > ActivityMatcherService.ELEVATION_THRESHOLD_M:
                continue

            # Нашли совпадение!
            return activity

        return None

    @staticmethod
    async def find_similar_activities(
        gpx: GPXFile,
        user_id: str,
        db: AsyncSession,
        limit: int = 5
    ) -> list[StravaActivity]:
        """
        Найти похожие активности (по дистанции и набору высоты).
        Полезно для предсказания на основе похожих маршрутов.
        """
        query = (
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(["Hike", "Walk"]))
            # Фильтр по дистанции ±30%
            .where(StravaActivity.distance_m.between(
                gpx.distance_km * 1000 * 0.7,
                gpx.distance_km * 1000 * 1.3
            ))
            # Фильтр по набору высоты ±50%
            .where(StravaActivity.elevation_gain_m.between(
                gpx.elevation_gain_m * 0.5,
                gpx.elevation_gain_m * 1.5
            ))
            .order_by(StravaActivity.start_date.desc())
            .limit(limit)
        )

        result = await db.execute(query)
        return result.scalars().all()
```

#### 3.2 API endpoint для матчинга

```python
# backend/app/api/v1/routes/predict.py (добавить)

@router.post("/match-activity")
async def match_gpx_to_activity(
    request: MatchActivityRequest,
    db: AsyncSession = Depends(get_db)
) -> MatchActivityResponse:
    """
    Найти активность из Strava, соответствующую GPX маршруту.
    """
    gpx = await GPXRepository.get_by_id(request.gpx_id, db)
    if not gpx:
        raise HTTPException(404, "GPX not found")

    user = await get_user_by_telegram_id(request.telegram_id, db)
    if not user:
        raise HTTPException(404, "User not found")

    activity = await ActivityMatcherService.find_matching_activity(
        gpx=gpx,
        user_id=str(user.id),
        db=db,
        date_hint=request.date_hint
    )

    if activity:
        return MatchActivityResponse(
            found=True,
            activity_id=activity.strava_id,
            activity_name=activity.name,
            activity_date=activity.start_date,
            actual_time_hours=activity.moving_time_s / 3600,
            distance_diff_m=abs(activity.distance_m - gpx.distance_km * 1000),
            elevation_diff_m=abs(activity.elevation_gain_m - gpx.elevation_gain_m)
        )

    return MatchActivityResponse(found=False)
```

---

### Фаза 4: Self-Learning система
**Приоритет: MEDIUM**
**Статус: BACKLOG**

#### 4.1 Модель для истории точности

```python
# backend/app/models/prediction.py (добавить)

class PredictionAccuracy(Base):
    """
    История точности предсказаний для обучения.
    """
    __tablename__ = "prediction_accuracy"

    id = Column(Integer, primary_key=True)
    prediction_id = Column(UUID, ForeignKey("predictions.id"), nullable=False)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)

    # Время
    predicted_time_hours = Column(Float, nullable=False)
    actual_time_hours = Column(Float, nullable=False)
    error_ratio = Column(Float, nullable=False)  # actual / predicted

    # Характеристики маршрута
    distance_km = Column(Float)
    elevation_gain_m = Column(Float)
    max_altitude_m = Column(Float)

    # Условия (опционально)
    weather_temp_c = Column(Float, nullable=True)
    weather_conditions = Column(String, nullable=True)  # sunny, rainy, etc.

    # Фидбэк от пользователя
    user_feedback = Column(String, nullable=True)  # "устал", "было жарко", etc.

    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 4.2 Обновление профиля после обратной связи

```python
# backend/app/services/user_profile.py (добавить)

@staticmethod
async def learn_from_actual(
    prediction_id: str,
    actual_time_hours: float,
    user_feedback: Optional[str],
    db: AsyncSession
):
    """
    Обновить профиль пользователя на основе реального времени прохождения.
    """
    # Получить prediction
    prediction = await db.get(Prediction, prediction_id)
    if not prediction:
        return

    predicted_time = prediction.estimated_time_hours
    error_ratio = actual_time_hours / predicted_time

    # Сохранить для аналитики
    accuracy = PredictionAccuracy(
        prediction_id=prediction_id,
        user_id=prediction.user_id,
        predicted_time_hours=predicted_time,
        actual_time_hours=actual_time_hours,
        error_ratio=error_ratio,
        distance_km=prediction.gpx_file.distance_km,
        elevation_gain_m=prediction.gpx_file.elevation_gain_m,
        user_feedback=user_feedback
    )
    db.add(accuracy)

    # Обновить профиль если много ошибок в одну сторону
    profile = await get_user_profile(prediction.user_id, db)
    if profile:
        # Взвешенное обновление (не резко менять)
        # Если error_ratio > 1 — был медленнее чем предсказано
        # Если error_ratio < 1 — был быстрее

        # Простое скользящее среднее
        alpha = 0.1  # вес нового наблюдения
        new_factor = profile.endurance_factor * (1 - alpha) + error_ratio * alpha
        profile.endurance_factor = round(new_factor, 3)

    await db.commit()
```

---

### Фаза 5: Weather интеграция
**Приоритет: LOW**
**Статус: BACKLOG**

#### Заметки:
- Использовать Open-Meteo API (бесплатный)
- Получать прогноз на дату похода по координатам GPX
- Множители: температура, дождь, ветер
- Исторические данные для анализа (какая была погода когда прошёл маршрут)

```python
# Примерные множители погоды
def get_weather_multiplier(weather: Weather) -> float:
    multiplier = 1.0

    if weather.temperature < 0:
        multiplier *= 1.1  # Холод замедляет
    if weather.temperature > 30:
        multiplier *= 1.15  # Жара тоже
    if weather.rain_mm > 5:
        multiplier *= 1.2  # Дождь = скользко
    if weather.wind_speed > 40:
        multiplier *= 1.1  # Сильный ветер

    return multiplier
```

---

## Порядок реализации

| # | Фаза | Задачи | Зависимости | Статус |
|---|------|--------|-------------|--------|
| 1 | **Персональный профиль** | Модель + сервис + миграция | - | ✅ DONE |
| 2 | **Splits** | Модель + sync + расчёт | Фаза 1 | ✅ DONE |
| 3 | **GPX ↔ Activity** | Матчинг + API | Фазы 1, 2 | TODO |
| 4 | **Self-Learning** | Accuracy + обновление | Фазы 1, 2, 3 | BACKLOG |
| 5 | **Weather** | API + множители | Фазы 1-4 | BACKLOG |

---

## Файлы для создания/изменения

### Созданные файлы ✅:
- ✅ `backend/app/models/user_profile.py` — модель UserPerformanceProfile
- ✅ `backend/app/services/user_profile.py` — сервис расчёта профиля
- ✅ `backend/alembic/versions/004_add_user_performance_profile.py` — миграция профиля
- ✅ `backend/alembic/versions/005_add_strava_activity_splits.py` — миграция splits

### Изменённые файлы ✅:
- ✅ `backend/app/models/strava_activity.py` — добавлен StravaActivitySplit, splits_synced
- ✅ `backend/app/models/user.py` — добавлен relationship к profile
- ✅ `backend/app/models/__init__.py` — экспорты новых моделей
- ✅ `backend/app/services/strava.py` — метод get_activity_with_splits()
- ✅ `backend/app/services/strava_sync.py` — sync_activity_splits(), sync_splits_for_user()
- ✅ `backend/app/services/prediction.py` — интеграция с профилем
- ✅ `backend/app/services/naismith.py` — добавлена константа NAISMITH_BASE_SPEED_KMH

### Ещё нужно (Фаза 3):
- `backend/app/services/activity_matcher.py` — сервис матчинга
- `backend/app/api/v1/routes/predict.py` — новые endpoints
- `backend/app/schemas/prediction.py` — новые схемы для матчинга

---

## Вопросы для уточнения

1. ✅ Хранить splits долгосрочно? — **Да**
2. ✅ Типы активностей для профиля? — **Hike, Walk (Run позже)**
3. ⏸️ Feedback loop через бота? — **Позже**
4. ⏸️ Weather? — **Бэклог**

---

## Бэклог (на потом)

### * endurance_factor — коэффициент выносливости
**Статус:** Требует дополнительного исследования

**Идея:** Насколько падает темп к концу длинных маршрутов (1.0 = не падает, >1.0 = устаёт).

**Проблема:** Сложно корректно вычислить, потому что:
- Маршруты часто "вверх в начале, вниз в конце" — нельзя просто сравнить первые и последние splits
- Нужно нормализовать по градиенту, но это усложняет логику
- На горных маршрутах может быть мало flat splits для сравнения

**Возможные решения:**
1. Сравнивать только flat splits (gradient -3% to +3%) в начале vs конце
2. Нормализовать темп по градиенту и сравнивать "эффективность"
3. Собрать больше данных и проанализировать паттерны

**Когда делать:** После MVP, когда соберём реальные данные пользователей.

---

### * fitness_trend — тренд формы
**Статус:** Отложено

**Идея:** Показывать пользователю improving / stable / declining на основе сравнения темпа за последние 2 недели vs предыдущие 2 недели.

**Зачем:** Информативно для пользователя ("ты в форме!"), но не влияет на предсказание.

**Когда делать:** Как nice-to-have фича для UI, после основного функционала.

---

### * recent_training_load — тренировочная нагрузка
**Статус:** Отложено

**Идея:** Сумма (distance_km × (1 + elevation_gain/1000)) за последние 4 недели.

**Зачем:** Может влиять на прогноз — если человек много тренировался, он в лучшей форме.

**Когда делать:** После валидации базовой персонализации.

---

## Ссылки

- [Strava API Reference](https://developers.strava.com/docs/reference/)
- [Strava API Agreement](https://www.strava.com/legal/api)
- [Open-Meteo Weather API](https://open-meteo.com/)
- [Intervals.icu](https://intervals.icu/) — пример хранения данных
