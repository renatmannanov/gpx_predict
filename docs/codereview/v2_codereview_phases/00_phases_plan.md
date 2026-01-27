# Code Review Documentation v2

> **Проект:** GPX Predictor
> **Дата начала:** 2026-01-24
> **Обновлено:** 2026-01-27
> **Цель:** Привести кодовую базу в AI-friendly состояние и подготовить к production

---

## Фазы рефакторинга

| Фаза | Файл | Статус | Зависимости | Строк | Ветка |
|------|------|--------|-------------|-------|-------|
| **Phase 0a** | [phase0a_structure.md](phase0a_structure.md) | ⏳ Не начато | Нет | ~50 | `refactor/phase-0a-structure` |
| **Phase 0b** | [phase0b_shared.md](phase0b_shared.md) | ⏳ Не начато | 0a | ~100 | `refactor/phase-0b-shared` |
| **Phase 0c** | [phase0c_hiking.md](phase0c_hiking.md) | ⏳ Не начато | 0b | ~200 | `refactor/phase-0c-hiking` |
| **Phase 0d** | [phase0d_trail_run.md](phase0d_trail_run.md) | ⏳ Не начато | 0b | ~150 | `refactor/phase-0d-trail-run` |
| **Phase 0e** | [phase0e_strava.md](phase0e_strava.md) | ⏳ Не начато | 0b | ~300 | `refactor/phase-0e-strava` |
| **Phase 0f** | [phase0f_gpx_users.md](phase0f_gpx_users.md) | ⏳ Не начато | 0b | ~150 | `refactor/phase-0f-gpx-users` |
| **Phase 1** | [phase1_database.md](phase1_database.md) | ⏳ Не начато | 0a | ~250 | `refactor/phase-1-database` |
| **Phase 2** | [phase2_naming.md](phase2_naming.md) | ⏳ Не начато | 0c, 0d | ~200 | `refactor/phase-2-naming` |
| **Phase 3** | [phase3_calculators.md](phase3_calculators.md) | ⏳ Не начато | 0c | ~150 | `refactor/phase-3-calculators` |
| **Phase 5** | [phase5_repositories.md](phase5_repositories.md) | ⏳ Не начато | 0f, 1 | ~300 | `refactor/phase-5-repositories` |
| **Phase 6** | [phase6_api.md](phase6_api.md) | ⏳ Не начато | 2, 5 | ~200 | `refactor/phase-6-api` |
| **Phase 4** | [phase4_bot.md](phase4_bot.md) | ✅ Завершено | 6 | ~300 | `refactor/phase-4-bot` |
| **Phase 7** | [phase7_tests.md](phase7_tests.md) | ⏳ Не начато | Все | ~150 | `refactor/phase-7-tests` |

**Общий объём:** ~2300 строк изменений

---

## Порядок выполнения

```
                    ┌─► Phase 1 (Database) ────────────────────┐
                    │                                          │
Phase 0a ─► Phase 0b ─┬─► Phase 0c (hiking) ─► Phase 2 ─► Phase 3 ─┬─► Phase 5 ─► Phase 6 ─► Phase 4
                      │                            │               │
                      ├─► Phase 0d (trail_run) ────┘               │
                      │                                            │
                      ├─► Phase 0e (strava) ───────────────────────┘
                      │
                      └─► Phase 0f (gpx, users) ───────────────────┘

После всех фаз: Phase 7 (Tests)
```

**Можно делать параллельно:**
- Phase 0c + 0d (hiking и trail_run независимы)
- Phase 0e + 0f (strava и gpx/users независимы)
- Phase 1 можно делать параллельно с Phase 0c-0f

---

## Git стратегия

### Именование веток
```
refactor/phase-{N}{letter?}-{short-description}
```

### Workflow для каждой фазы
```bash
# 1. Создать ветку от main
git checkout main
git pull
git checkout -b refactor/phase-0a-structure

# 2. Работать над фазой
# ... изменения ...

# 3. Commit с описанием
git add .
git commit -m "refactor: phase 0a - create features/ and shared/ structure"

# 4. Merge в main (после проверки)
git checkout main
git merge refactor/phase-0a-structure
git push

# 5. (Опционально) Удалить ветку
git branch -d refactor/phase-0a-structure
```

### Commit message format
```
refactor: phase {N} - {краткое описание}

- Что изменено
- Какие файлы затронуты

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## Принятые решения

| Дата | Решение |
|------|---------|
| 2026-01-24 | `UserPerformanceProfile` → `UserHikingProfile` |
| 2026-01-24 | Использовать `trail_run` везде (не `run`) |
| 2026-01-24 | Оставить 2 версии Naismith (нужны для 3 вариантов расчёта) |
| 2026-01-24 | Лимиты: Сервисы 500, Routes 400, Models 300, Utils 200 строк |
| 2026-01-26 | PostgreSQL с самого начала (не SQLite) |
| 2026-01-26 | Phase 0 разбит на подфазы 0a-0f |
| 2026-01-26 | Phase 6 (API) перед Phase 4 (Bot) |
| 2026-01-26 | Добавлена Phase 7 (Tests) |
| 2026-01-26 | Одна git ветка на фазу/подфазу |

---

## Как работать с фазами

### Перед началом фазы
1. `git status` — должен быть чистый
2. Прочитать файл фазы целиком
3. Проверить зависимости — предыдущие фазы завершены?
4. Создать ветку: `git checkout -b refactor/phase-{N}-{name}`

### Во время фазы
1. Следовать чеклисту в файле фазы
2. Проверять что приложение запускается после каждого крупного изменения
3. Коммитить логические блоки (не один гигантский коммит)

### После завершения фазы
1. Проверить что приложение работает:
   ```bash
   cd backend && uvicorn app.main:app --reload
   # В другом терминале:
   cd bot && python main.py
   ```
2. Отметить ✅ все чекбоксы в файле фазы
3. Обновить статус в этом README
4. Merge в main
5. Обновить CLAUDE.md если нужно

---

## Проверка после каждой фазы

```bash
# Backend
cd backend
pip install -r requirements.txt  # если были изменения
uvicorn app.main:app --reload

# Bot (в отдельном терминале)
cd bot
python main.py

# Tests (после Phase 7)
cd backend
pytest tests/ -v
```

---

*Last updated: 2026-01-26*
