# План разработки GPX Predictor

**Создан:** 2025-01-15
**Обновлён:** 2026-01-17
**Статус:** В работе

---

## Контекст

Сервис прогнозирования времени походов/забегов с учётом рельефа.
Приоритет: **Туристы → Бегуны → Strava**

### Решения из обсуждения:
- БД: **PostgreSQL** везде (локально и Railway)
- Бот: **Отдельный сервис**, вызывает API бэкенда
- Аутентификация: **Telegram ID** как идентификатор пользователя
- Sunrise/sunset: библиотека **astral** по координатам
- Segment breakdown: по **градиенту + дистанции**
- Фронтенд: пока не приоритет, фокус на бэкенд + бот

---

## Что уже готово в коде

| Компонент | Статус | Файл |
|-----------|--------|------|
| FastAPI scaffold | ✅ | `backend/app/main.py` |
| SQLAlchemy модели | ✅ | `backend/app/models/` |
| GPX парсинг | ✅ | `backend/app/services/gpx_parser.py` |
| Naismith алгоритм | ✅ | `backend/app/services/calculators/naismith.py` |
| Tobler алгоритм | ✅ | `backend/app/services/calculators/tobler.py` |
| PersonalizationService | ✅ | `backend/app/services/calculators/personalization.py` |
| Множители профиля | ✅ | `backend/app/services/naismith.py` |
| Predict hike логика | ✅ | `backend/app/services/prediction.py` |
| Predict group логика | ✅ | `backend/app/services/prediction.py` |
| GPX upload endpoint | ✅ | Парсит и сохраняет в БД |
| Predict endpoint | ✅ | `/predict/hike`, `/predict/compare` |

---

## Этап 1: Backend — БД интеграция ✅ ГОТОВО

### 1.1 GPX upload → сохранение в БД
- [x] Создать GPX репозиторий (`backend/app/repositories/gpx.py`)
- [x] Сохранять метаданные GPX в таблицу `gpx_files`
- [x] Сохранять сам файл (в БД как bytes) — колонка `gpx_content`
- [x] Возвращать `gpx_id` после загрузки
- [x] Endpoint GET `/gpx/{gpx_id}` — получение инфо

### 1.2 Predict → загрузка GPX из БД
- [x] Загружать GPX данные по `gpx_id` в `predict_hike()`
- [x] Загружать GPX данные по `gpx_id` в `predict_group()`
- [x] Убрать hardcoded dummy данные

### 1.3 Segment breakdown
- [x] Функция сегментации GPX по градиенту + дистанции
- [x] Расчёт времени на каждый сегмент
- [x] Добавить в ответ `HikePrediction.segments`

### 1.4 Sunrise/sunset
- [x] Добавить `astral` в requirements.txt
- [x] Функция `get_sun_times(lat, lon, date)`
- [x] Интегрировать в warnings

### 1.5 Alembic миграции
- [x] Проверить/создать initial migration
- [x] Настроить для PostgreSQL

---

## Этап 2: Telegram бот — MVP ✅ ГОТОВО

### 2.1 Scaffold
- [x] Создать директорию `bot/`
- [x] `bot/main.py` — entry point
- [x] `bot/config.py` — BOT_TOKEN, BACKEND_URL
- [x] `bot/requirements.txt`
- [x] `bot/.env.example`

### 2.2 Базовые команды
- [x] `/start` — приветствие
- [x] `/help` — справка
- [x] `/cancel` — отмена

### 2.3 GPX upload flow
- [x] Handler для получения файла
- [x] Валидация (расширение, размер)
- [x] Отправка в backend API
- [x] Показ инфо о маршруте

### 2.4 Профиль через inline keyboards
- [x] FSM states (`bot/states/prediction.py`)
- [x] Keyboards для выбора опыта
- [x] Keyboards для выбора рюкзака
- [x] Keyboards для размера группы
- [x] Вопросы про детей/пожилых

### 2.5 Результат
- [x] Вызов backend `/predict/compare`
- [x] Форматирование ответа
- [x] Показ warnings
- [x] Рекомендуемое время старта

### 2.6 API клиент
- [x] `bot/services/api_client.py`
- [x] Методы: `upload_gpx()`, `predict_hike()`, `compare_methods()`
- [x] Обработка ошибок

---

## Этап 3: Strava интеграция ✅ ГОТОВО

### 3.1 OAuth
- [x] `/auth/strava` — начало OAuth
- [x] `/auth/strava/callback` — callback
- [x] Сохранение токенов в БД
- [x] Refresh токенов при истечении

### 3.2 Синхронизация активностей
- [x] `StravaSyncService` — фоновая синхронизация
- [x] Таблица `strava_activities`
- [x] Таблица `strava_activity_splits`
- [x] API `/strava/sync/{telegram_id}`

### 3.3 Профиль пользователя
- [x] `UserPerformanceProfile` модель
- [x] `UserProfileService.calculate_profile_with_splits()`
- [x] API `/profile/{telegram_id}`
- [x] API `/profile/{telegram_id}/calculate`

### 3.4 Персонализация прогнозов
- [x] `PersonalizationService` — расчёт по реальным сегментам
- [x] Интеграция в `ComparisonService`
- [x] `tobler_personalized` и `naismith_personalized` методы
- [x] Отображение в боте с иконкой 🎯

---

## Этап 4: Групповой режим в боте

### 4.1 Работа в группах
- [ ] Определение типа чата (личный/группа)
- [ ] Разный UX для группы

### 4.2 Сбор профилей
- [ ] Организатор загружает GPX
- [ ] Бот отправляет приватные сообщения участникам
- [ ] Сбор ответов, связь с походом

### 4.3 Групповой прогноз
- [ ] Вызов backend `/predict/group`
- [ ] Показ ролей (быстрый/средний/медленный)
- [ ] Рекомендации по разделению

---

## Этап 5: Деплой

### 5.1 Railway setup
- [ ] PostgreSQL database
- [ ] Backend service
- [ ] Bot service
- [ ] Environment variables

### 5.2 Тестирование
- [ ] Unit tests для калькуляторов
- [ ] Integration tests для API
- [ ] E2E тест бота

---

## Будущие этапы (не сейчас)

- **Peer Validation** — верификация опыта друзьями
- **Telegram Mini App** — после бота
- **База маршрутов Алматы** — нужно обсудить формат
- **Режим для бегунов** — Riegel, GAP
- **Crowdsourced покрытие**
- **Градации градиента** — 5 категорий вместо 3
- **Altitude correction** — замедление на высоте >2500м
- **Fatigue factor** — замедление после 4-6 часов

---

## Как работать с этим планом

1. Открываем новый чат
2. Говорим: "Продолжаем работу по плану в `docs/DEVELOPMENT_PLAN.md`"
3. Я читаю план, смотрю что не отмечено
4. Делаю следующий пункт
5. Отмечаем `[x]` когда готово

---

## Текущий прогресс

**Следующий шаг:** Этап 4 — Групповой режим в боте

**Завершено:**
- ✅ Этап 1: Backend БД интеграция
- ✅ Этап 2: Telegram бот MVP
- ✅ Этап 3: Strava интеграция + персонализация
