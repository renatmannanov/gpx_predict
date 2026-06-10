# Шаг 1: Матчинг по (name, birth_year, source), убрать fuzzy из импорта

> Зависит от: нет
> Статус: [x] done
> Файл: backend/scripts/batch_parse.py

## Задача

Поменять логику резолва runner в `save_to_db()` (batch_parse.py:231-284):

### Было
```python
runner = db.execute(
    select(Runner).where(Runner.name_normalized == name_norm)
).scalar_one_or_none()
if not runner:
    runner, warnings = _fuzzy_match_runner(db, name_norm, r.birth_year)  # ← убрать
    ...
```

### Станет
```python
# source приходит параметром save_to_db: "clax" или "almaty-marathon"
# Нормализуем к значению колонки runners.source:
#   "almaty-marathon" → "am",  всё остальное → "athletex"
runner_source = "am" if source == "almaty-marathon" else "athletex"

runner = None
if name_norm and r.birth_year is not None:
    # Совпадение ТОЛЬКО при известном birth_year И внутри своего источника
    runner = db.execute(
        select(Runner).where(
            Runner.name_normalized == name_norm,
            Runner.birth_year == r.birth_year,
            Runner.source == runner_source,
        )
    ).scalar_one_or_none()
# birth_year IS NULL → runner остаётся None → создаётся новый (фрагмент)
```

При создании Runner — добавить `source=runner_source`.

### Что убрать
- Вызов `_fuzzy_match_runner` из `save_to_db()` (строки ~242-244)
- `suspect_warnings` от fuzzy (если больше нигде не используется — убрать накопление)
- **Саму функцию `_fuzzy_match_runner` НЕ удалять** — она переедет в логику
  merge-candidates позже. Просто перестать вызывать из импорта. Пометить docstring:
  `# NOTE: больше не вызывается при импорте, зарезервировано для merge-candidates API`

### Алиасы
Логика сохранения алиасов (batch_parse.py:286-301) — **не трогаем**, работает.

### repository.py::get_or_create_runner — мёртвый код со старой логикой
Функция `get_or_create_runner` (repository.py:219) содержит СТАРЫЙ матчинг
(exact по `name_normalized`, без source/birth_year) и сейчас **нигде не вызывается**
(проверено grep 2026-06-08). Это ловушка: если кто-то позже её вызовет — получит
склейки. Варианты (ВЫБРАН первый):
- **Удалить функцию** `get_or_create_runner` целиком (она мёртвая, дублирует логику
  `save_to_db`). Если grep покажет неожиданный вызов — тогда обновить под новый
  матчинг вместо удаления.
```bash
# Перед удалением подтвердить, что вызовов нет:
grep -rn "get_or_create_runner" backend/ --include="*.py" | grep -v "def get_or_create_runner"
# Ожидаем: пусто → удалять безопасно
```

## Тесты
- Покрывается в step_3 (юнит-тесты). Здесь — только правка кода.

## Команды для верификации
```bash
# fuzzy не вызывается при импорте (только определение функции остаётся)
grep -n "_fuzzy_match_runner" backend/scripts/batch_parse.py
# Ожидаем: только строка с "def _fuzzy_match_runner" (определение), без вызовов в save_to_db

# source используется в резолве
grep -n "Runner.source\|runner_source" backend/scripts/batch_parse.py
# Ожидаем: ≥2 совпадения (в where и в Runner(...))

# Python синтаксис ок
python -c "import ast; ast.parse(open('backend/scripts/batch_parse.py').read())"
```

## Критерии готовности
- [ ] `_fuzzy_match_runner` НЕ вызывается в `save_to_db` (определение остаётся)
- [ ] Резолв runner фильтрует по `name_normalized` + `birth_year` + `source`
- [ ] `birth_year IS NULL` → всегда новый runner
- [ ] При создании Runner проставляется `source`
- [ ] `python -c "import ast..."` без ошибок
- [ ] `--import-json` ветка работает: `import_json_to_db` уже передаёт `source` в
      `save_to_db` (batch_parse.py:505) — отдельно её менять НЕ нужно. Критерий
      закрыт тем, что сам `save_to_db` использует новый матчинг (основная задача шага),
      а не тем, что «source передаётся». Проверка — через тесты step_3, не на глаз.
- [ ] `get_or_create_runner` удалён (или обновлён, если есть вызовы)
