# Бэклог-индекс: gpx_predictor (движок предсказаний)

> Обновлено: 2026-06-11
> Второй продукт: [INDEX_ayda_run.md](INDEX_ayda_run.md)
> Старый общий индекс: [README.md](README.md) (заменён этими двумя файлами)

Ядро продукта — точность предсказаний времени (hiking + trail run).
Текущие ошибки: персонализированный run-метод +35.8%, hiking −49.6%, MAPE 14.5%.

---

## P1 — точность (ядро)

| # | Задача | Файл | Заметка |
|---|--------|------|---------|
| 1 | Калибровка run-профилей (фильтрация пеших сегментов, медиана, тонкие градиентные категории) | [calibration_backlog.md](calibration_backlog.md) | Персонализация даёт +35.8% ошибку: один бакет смешивает асфальт и скрамблинг (12x разброс пейса) |
| 2 | Hiking-профили: IQR + effort levels | [backlog_hiking_profile.md](backlog_hiking_profile.md) | Применить к хайкингу то, что работает для trail run. Ошибка −49.6%. НЕ блокируется п.1 |

## P2 — данные и структура

| # | Задача | Файл | Заметка |
|---|--------|------|---------|
| 3 | Strava Streams API / FIT-файлы вместо 1km-сплитов | [backlog_strava_streams.md](backlog_strava_streams.md) | Ожидание: MAPE 14.5% → 10-12%. Можно параллельно с п.1 |
| 4 | HikingService рефакторинг (из монолитного PredictionService) | [backlog_hiking_service_refactor.md](backlog_hiking_service_refactor.md) | По образцу TrailRunService |
| 5 | Извлечение UserHikingProfile в отдельный файл | [backlog_hiking_profile_extraction.md](backlog_hiking_profile_extraction.md) | Техдолг, удобно вместе с п.4 |
| 6 | Разделение Road / Trail профилей | [calibration_backlog.md](calibration_backlog.md) | Рекомендация #6. Блокер: Strava API не различает тип → зависит от п.3 (Streams/FIT) |

## P3 — улучшения и техдолг

| # | Задача | Файл | Заметка |
|---|--------|------|---------|
| 7 | Персонализированные пороги аномалий пейса | [ANOMALY_DETECTION_PLAN.md](ANOMALY_DETECTION_PLAN.md) | Фиксированные 4–25 мин/км не учитывают уровень юзера; 17 размеченных аномалий |
| 8 | Profile history — JSONB-снапшоты профилей | [BACKLOG_2.md](BACKLOG_2.md) | Отладка «почему walk_threshold прыгнул», «было → стало» |
| 9 | Strava sync: начинать с новейших активностей | [backlog_1.md](backlog_1.md) | Сейчас первая синхронизация грузит годовалые активности первыми |
| 10 | Hiking: показывать статус Strava (как в trail run) + убрать debug-логирование | [backlog_1.md](backlog_1.md) | Мелкий UX + техдолг |

## R&D / долгосрочное

| # | Задача | Файл | Заметка |
|---|--------|------|---------|
| 11 | Garmin / Polar / Suunto интеграция | [phase_R2_garmin.md](phase_R2_garmin.md) | Polar — self-service, можно подать сейчас. Garmin — основная аудитория (70%+ трейлраннеров Алматы), нужен сайт + privacy policy — портал уже есть |
| 12 | User matching — подбор партнёров по профилю | [user_matching.md](user_matching.md) | Движок на стороне gpx_predictor. Блокер: мало пользователей с профилями. UI-сторона — [phase_R3_buddy_matching.md](phase_R3_buddy_matching.md) |
| 13 | Лавинный анализ маршрутов (Иле-Алатау, ATES) | [avalanche_risk_analysis.md](avalanche_risk_analysis.md) | План: зима 2026-2027 |
| 14 | Погода и тип поверхности | *(файла нет — создать при планировании)* | Связано с п.6 (Road/Trail — первый шаг к учёту поверхности) |
