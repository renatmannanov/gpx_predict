# R&D Фаза R2: Garmin и другие платформы — интеграция

## Цель

Подключить Garmin Connect API как второй источник данных. Garmin даёт более богатые данные (FIT файлы) и мягче ограничения на агрегацию — можно строить публичные лидерборды. Также подключить Polar (мгновенный доступ) и потенциально Suunto/COROS.

## Стратегическое значение

**Garmin = primary source для публичных агрегаций.**

Strava API Agreement запрещает агрегацию данных для показа третьим лицам. Garmin — нет. Поэтому:
- Лидерборды маршрутов ("цари горы") — из Garmin данных
- Агрегированная статистика маршрутов — из Garmin данных
- Персональные данные — из обоих источников

Поле `source` в таблице activities (`'strava' | 'garmin' | 'manual'`) позволяет различать источники и строить агрегации только из легальных данных.

**70%+ трейлраннеров Алматы** на Garmin — это основная аудитория.

---

## Рекомендуемый порядок подключения

| Приоритет | Платформа | Когда подавать | Почему |
|-----------|-----------|---------------|--------|
| 1 | **Polar** | Сейчас | Мгновенный доступ, self-service, можно начать интеграцию сразу |
| 2 | **Garmin** | После запуска дашборда (фаза 4) | Нужен сайт + privacy policy. Основная аудитория |
| 3 | **Suunto** | После Garmin | Те же требования, меньше аудитория |
| 4 | **COROS** | После всех | Закрытый, можно обойтись ручным FIT upload |

---

## 1. Garmin Connect Developer Program

### Общая информация

| Параметр | Значение |
|----------|----------|
| URL | developer.garmin.com/gc-developer-program/ |
| Доступ | **Только бизнес** (не для индивидуальных разработчиков) |
| Стоимость | Бесплатно (некоторые premium метрики — платно) |
| Ревью | ~2 рабочих дня (но могут проигнорировать без ответа) |
| Сайт обязателен | Да (поле формы) |
| Privacy Policy | Да (поле формы) |
| Webhooks | Да (push или ping/pull) |
| Формат данных | FIT, GPX, TCX |

### Что спрашивают в форме заявки

Форма: garmin.com/en-US/forms/GarminConnectDeveloperAccess/

Обязательные поля:
- **Company name**
- **Company website**
- **Link to Privacy Statement/Policy**
- **Primary Sales Region**
- **Full business address**
- **Contact name, email, phone number (с кодом страны), job title**
- **Technical Support Language Preference**
- Работаете ли **от имени клиента или третьей стороны** (если да — название и описание)
- Используете ли **субподрядчика** (если да — детали)
- **Количество устройств**, которые планируете поддерживать

### Доступные API (можно комбинировать)

| API | Что даёт | Нужно нам? |
|-----|----------|-----------|
| **Activity API** | FIT файлы тренировок | **Да — основной** |
| Health API | Дневные метрики (шаги, HR, сон, стресс, Body Battery, SpO2) | Нет (пока) |
| Training API | Push структурированных тренировок на устройства | Возможно позже |
| **Courses API** | Push маршрутов/курсов на устройства | **Да — можно отправлять маршруты из каталога на часы** |
| Women's Health API | Менструальный цикл | Нет |

**Courses API** — интересная возможность: маршруты из каталога (фаза 8) можно будет отправлять прямо на Garmin-часы юзера.

### Webhook / Push

Два варианта архитектуры:
- **Push Architecture:** Garmin POSTs данные на наш webhook URL когда появляются новые данные. Near-real-time (в течение минут после синхронизации часов).
- **Ping/Pull Architecture:** Мы периодически запрашиваем данные с серверов Garmin.

Можно выбрать per integration.

### Terms и ограничения

- Нужна **атрибуция "Garmin [model]"** при показе данных (social media, инфографики, дашборды, карточки активностей)
- Коммерческое использование данных за пределами приложения требует атрибуции
- Garmin может проверять compliance; нарушение = отключение API
- Нужно **согласие юзера** перед передачей данных
- Нельзя передавать данные юзера (включая геолокацию) без informed consent
- **Нет запрета на агрегацию** (в отличие от Strava) — ключевое отличие
- Полные условия: Garmin Connect Developer Program Agreement (PDF на developerportal.garmin.com)

### Риски

- Заявку могут **проигнорировать без ответа** — тишина = вероятный отказ
- Workaround: писать на ENGPOBTDev@garmin.com
- Неофициальная альтернатива: python-garminconnect (GitHub) — симулирует веб-логин, может сломаться

### Процесс после одобрения

1. Получаете доступ к Developer Portal
2. Garmin приглашает на **integration call** — обсуждение деталей
3. Типичная интеграция занимает **1-4 недели**

---

## 2. Polar AccessLink API

### Общая информация

| Параметр | Значение |
|----------|----------|
| URL | polar.com/accesslink-api/ |
| Доступ | **Открытый для всех** (self-service) |
| Стоимость | Бесплатно (могут начать брать в будущем) |
| Ревью | **Мгновенно** — никакого ревью |
| Webhooks | Да (HMAC SHA-256) |
| Формат данных | **TCX/GPX/JSON** (НЕ FIT!) |

### Регистрация

1. Создать Polar Flow аккаунт
2. Зайти на admin.polaraccesslink.com
3. Создать API client с OAuth2 callback URL
4. Получить client_id и secret **сразу** — без ревью

### Доступные данные

- **Тренировки:** активности за 30 дней, HR зоны, HR samples, маршруты, Training Load Pro
- **Daily activity:** шаги, калории, дистанция (365 дней, запрос макс. 28 дней)
- **Continuous HR:** 5-минутные интервалы
- **Сон:** Sleep Plus Stages, Nightly Recharge
- **Биометрия:** температура, SpO2, ECG (если есть)
- **Физические данные:** вес, рост

### Webhooks

- Типы событий: EXERCISE, SLEEP, CONTINUOUS_HEART_RATE, ACTIVITY_SUMMARY и др.
- Безопасность: HMAC SHA-256 подпись
- Ограничение: **только 1 webhook на приложение**
- Автоотключение через 7 дней неудачных доставок (можно реактивировать через API)

### Rate Limits

Динамические, растут с количеством юзеров:
- 15-минутное окно: 500 + (users × 20) запросов
- 24-часовое окно: 5000 + (users × 100) запросов

### Ограничения (License Agreement)

- Атрибуция: **"Polar Ecosystem as the source of Data"** при показе данных
- Нужна **privacy policy** при выходе в продакшен
- Нельзя создавать сервисы **конкурирующие с Polar Ecosystem**
- Удалять токены и данные по запросу юзера
- "Gatekeepers" по EU Digital Markets Act не могут использовать

### Важно

**Нет FIT экспорта** — ни через API, ни через платформу. Для Polar юзеров — TCX fallback. TCX содержит GPS + HR + каденс, но теряет running dynamics и power.

---

## 3. Suunto API

### Общая информация

| Параметр | Значение |
|----------|----------|
| URL | apizone.suunto.com |
| Доступ | **Только бизнес/организации** |
| Стоимость | Бесплатно |
| Ревью | До 2 недель (еженедельный review) |
| Формат данных | FIT (новые устройства) |

### Критерии оценки заявки

Suunto оценивает:
- **Fit to their brand** — outdoor, endurance фокус
- **Interest from their customers** — есть ли запрос от пользователей Suunto
- **Innovation mindset** — что нового вы приносите

### Процесс

1. Подать заявку через Suunto Partner Program (suunto.com/partners/welcome-partners/)
2. Подписать API agreement
3. Перечислить всех разработчиков, которым нужен доступ
4. Если одобрены — получаете Development API (ограниченные лимиты)
5. Готовы к продакшену — подаёте заявку на Production API

Контакт при отсутствии ответа: partners@suunto.com

### Доступные данные

- Тренировки: GPS, HR, laps
- Daily activities: шаги, калории
- Route push: GPX формат
- Workout push: FIT формат
- **НЕ доступно:** сон, POI, персональные данные (вес, HR зоны)

---

## 4. COROS API

### Общая информация

| Параметр | Значение |
|----------|----------|
| URL | support.coros.com (через Help Center) |
| Доступ | **Private/invitation-based** |
| Стоимость | Неизвестно |
| Ревью | Неизвестно |
| Документация | Приватная (выдаётся после одобрения) |

### Процесс

- Подать заявку через COROS Help Center
- Документация приватная — выдаётся после одобрения
- OAuth-based аутентификация
- Раздельные sandbox и production среды

### Кто одобрен

Одобренные партнёры: Tredict, TrainingPeaks, Strava и другие training-платформы. Ориентация на **partner companies** с существующей пользовательской базой.

### Что доступно (через одобренных партнёров)

- Activity data с FIT файлами (GPS, HR, power, Stryd)
- Workout sync (push на часы)
- Daily activity summaries
- Сон
- **Нет real-time webhooks** (по данным от интеграторов)

### Альтернативы

- **Ручной экспорт:** юзеры могут экспортировать из COROS app в FIT/TCX/GPX/KML/CSV
- **Bulk export:** xballoy/coros-api (GitHub) — неофициальный bulk export в FIT
- **Aggregator APIs:** Terra API (tryterra.co), Spike API — middleware с COROS интеграцией (платно)

---

## Сводная таблица

| Критерий | Garmin | Polar | Suunto | COROS |
|----------|--------|-------|--------|-------|
| Индивидуальные разработчики | Нет | **Да** | Нет | Вероятно нет |
| Заявка нужна | Да | Нет (self-service) | Да | Да |
| Время ревью | ~2 дня | Мгновенно | До 2 недель | Неизвестно |
| Сайт обязателен | Да | Нет | Да | Неизвестно |
| Privacy policy | Да (поле формы) | Да (agreement) | Да (agreement) | Неизвестно |
| Стоимость | Бесплатно | Бесплатно | Бесплатно | Неизвестно |
| Webhooks/Push | Да | Да (HMAC) | Не упомянуто | Нет |
| Формат активностей | **FIT**, GPX, TCX | TCX, GPX, JSON | FIT | FIT |
| Push маршрутов | Да (Courses API) | Нет | Да (GPX) | Нет |
| Push тренировок | Да (Training API) | Нет | Нет | Да |
| Сон | Да | Да | Нет | Да (через партнёров) |
| Запрет на агрегацию | **Нет** | Нет | Нет | Неизвестно |

---

## Чеклист: подготовка к подаче Garmin

Нужно до подачи заявки:

- [ ] **Сайт** — race dashboard (фаза 4) или лендинг. Должен выглядеть как продукт, не как заглушка
- [ ] **Домен** — свой домен (ayda.run? ayda.kz?)
- [ ] **Privacy Policy** на сайте — какие данные собираем, как используем, как удалить, GDPR
- [ ] **Terms of Service** на сайте
- [ ] **Бизнес-email** (не gmail) — email@свой_домен
- [ ] **Описание продукта** для формы:

> "Ayda — local trail running and hiking platform for Almaty, Kazakhstan. Provides race time predictions based on GPS elevation profiles and personal activity history. Currently integrates with Strava (approved Community Application, 42 users). Seeking Garmin Activity API integration to provide automatic activity sync and FIT-based analysis for the majority of local trail runners using Garmin devices. Also interested in Courses API to push curated local trail routes to users' Garmin watches."

- [ ] **Упомянуть существующую Strava интеграцию** — сильный аргумент
- [ ] **Упомянуть user base** — ayda_run с 42 юзерами, SRG/RUNFINITY клубы
- [ ] **Упомянуть конкретные API**: Activity API (FIT download) + Courses API (route push)

## Чеклист: Polar (можно сделать сейчас)

- [ ] Создать Polar Flow аккаунт
- [ ] Зайти на admin.polaraccesslink.com
- [ ] Создать API client
- [ ] Получить client_id/secret
- [ ] Протестировать на одной активности

---

## Техническая справка (из backlog_strava_streams.md)

### FIT файл — что внутри

FIT (Flexible and Interoperable Data Transfer) — компактный бинарный формат от Garmin/ANT+, де-факто стандарт.

**Record messages (каждую секунду или Smart):**
- `position_lat` / `position_long` — GPS (semicircles, точнее float32)
- `enhanced_altitude` — высота (м)
- `enhanced_speed` — скорость (м/с)
- `heart_rate` — ЧСС (bpm)
- `cadence` — каденс (spm)
- `power` — мощность (W)
- `temperature` — температура (°C)
- `distance` — кумулятивная дистанция (м)
- `vertical_oscillation`, `ground_contact_time`, `stride_length` — running dynamics

**Плотность данных:**

| Режим записи | Точек/час | На 2ч trail run | Размер FIT |
|-------------|-----------|-----------------|------------|
| Smart (~3-6с) | ~600-1,200 | ~1,200-2,400 | 100-300 KB |
| Every Second | ~3,600 | ~7,200 | 300 KB - 1 MB |
| Every Second + Dynamics | ~3,600+ | ~7,200+ | 1-3 MB |

### Python библиотеки

| Библиотека | Статус | Примечание |
|-----------|--------|-----------|
| `fitdecode` | Активная, рекомендуется | Thread-safe, MIT |
| `garmin-fit-sdk` | Официальный Garmin SDK | |
| `gpxpy` | **Уже в проекте** | Для GPX/TCX |

### Форматы по брендам

| Бренд | Нативный формат | Запись по умолчанию | FIT экспорт |
|-------|----------------|--------------------|----|
| Garmin | FIT | Smart (~3-6с) | Нативный |
| Suunto | FIT (новые) / SML (старые) | 1с | Нативный (новые) |
| COROS | FIT | 1с | Нативный |
| Polar | Проприетарный | 1с | **Нет** (TCX/GPX) |

---

## Unified Activity Storage

Все данные из любого источника попадают в единую таблицу activities с полем `source`:
- `'strava'` — данные через Strava API (ограничения на агрегацию)
- `'garmin'` — данные через Garmin API (без ограничений на агрегацию)
- `'polar'` — данные через Polar API
- `'manual'` — ручной upload FIT/GPX

gpx_predictor работает одинаково со всеми источниками.

**Критично:** Поле `source` позволяет строить агрегации только из данных без юридических ограничений (Garmin, Polar, manual).

---

## Зависимости

- **Polar** — подать можно сейчас, не блокирует ничего
- **Garmin** — подать после фазы 4 (нужен сайт + privacy policy)
- **Интеграция** — после портала (фаза 9) или параллельно
- Нужна Unified Activity Storage (схема из agent_brief.md секция 5)

## Ссылки

### Garmin
- [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/)
- [Garmin Developer Program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/)
- [Garmin Access Request Form](https://www.garmin.com/en-US/forms/GarminConnectDeveloperAccess/)
- [Garmin Activity API](https://developer.garmin.com/gc-developer-program/activity-api/)
- [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/)
- [Garmin API Brand Guidelines](https://developer.garmin.com/brand-guidelines/api-brand-guidelines/)
- [Garmin Developer Program Agreement (PDF)](https://developerportal.garmin.com/sites/default/files/Garmin%20Connect%20Developer%20Program%20Agreement.pdf)
- [python-garminconnect (unofficial)](https://github.com/cyberjunky/python-garminconnect)

### Polar
- [Polar AccessLink API](https://www.polar.com/accesslink-api/)
- [Polar API License Agreement](https://www.polar.com/en/legal/polar-api-agreement)
- [Polar Admin Portal](https://admin.polaraccesslink.com)

### Suunto
- [Suunto API Zone](https://apizone.suunto.com/)
- [Suunto Partner Program](https://www.suunto.com/partners/welcome-partners/)

### COROS
- [COROS API Application](https://support.coros.com/hc/en-us/articles/17085887816340-Submitting-an-API-Application)
- [coros-api bulk export (unofficial)](https://github.com/xballoy/coros-api)

### Python
- [fitdecode (PyPI)](https://pypi.org/project/fitdecode/)
- [gpxpy (PyPI)](https://pypi.org/project/gpxpy/)

### Aggregator APIs (альтернатива прямой интеграции)
- [Terra API (tryterra.co)](https://tryterra.co) — единый API для Garmin + COROS + Polar + Suunto + 500 других
- [Spike API (spikeapi.com)](https://www.spikeapi.com) — аналогичный middleware
