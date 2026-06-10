# Шаг 3: Юнит-тесты на матчинг — тёзки и изоляция источников

> Зависит от: step_1, step_2
> Статус: [x] done
> Файл: backend/tests/features/races/test_runner_matching.py (новый) + tests/conftest.py

## Задача

Написать тесты, фиксирующие новую логику матчинга. ДО пересборки реальных данных —
ловим регрессии на моках.

## Тестовая БД — отдельная, НЕ dev-БД (важно)
`backend/tests/conftest.py` **не существует** (проверено 2026-06-08) — фикстуры БД
нет, строим с нуля. Тесты НЕ зависят от применённой на dev-БД миграции (миграция
применяется только в step_4). Подход:
- Создать `conftest.py` с фикстурой отдельной тестовой PostgreSQL-БД
  (например `gpx_predictor_test`), схема поднимается через `Base.metadata.create_all`
  (включит новую колонку `source` и составной constraint из модели db_models.py —
  поэтому step_3 зависит от step_2, где модель обновлена).
- Каждый тест — в транзакции с rollback (изоляция).
- НЕ использовать dev-БД `gpx_predictor` для тестов.

**Зависимость:** step_3 требует, чтобы модель Runner в db_models.py уже имела `source`
и новый constraint (это делается в step_2). Сам `alembic upgrade` для тестов не нужен —
`create_all` строит схему из модели.

## Сценарии

### 1. Тёзки без birth_year → разные runners
```python
# Два результата "Юлия Ким" без birth_year, source=am
# → создаётся 2 разных Runner (не склеиваются)
```

### 2. Тёзки с разным birth_year → разные runners
```python
# "Pavlov Alexandr" 1984 и "Pavlov Alexandr" 2015 (отец/сын), source=athletex
# → 2 разных Runner
```

### 3. Один человек, одинаковый birth_year, один источник → один runner
```python
# "Renat Karimov" 1990 в двух гонках athletex
# → 1 Runner, races_count учитывает обе
```

### 4. Изоляция источников
```python
# "Sergey Ivanov" 1985 source=athletex И "Sergey Ivanov" 1985 source=am
# → 2 разных Runner (одинаковые имя+год, но разный source)
```

### 5. Fuzzy НЕ срабатывает при импорте
```python
# "Knyaz X" и "Kniaz X" с одинаковым birth_year, source=athletex
# → 2 разных Runner (fuzzy выключен, name_normalized различаются)
# (раньше fuzzy бы их склеил — теперь нет)
```

## Существующие тесты — проверить, что не сломались
```bash
# Найти тесты, которые могли зависеть от старого матчинга
grep -rl "_fuzzy_match_runner\|name_normalized\|save_to_db" backend/tests/ 2>/dev/null
```

## Команды для верификации
```bash
cd backend && pytest tests/test_runner_matching.py -v
# Ожидаем: все 5 сценариев PASS

cd backend && pytest tests/ -q
# Ожидаем: вся существующая сюита зелёная (нет регрессий)
```

## Критерии готовности
- [ ] Файл `tests/test_runner_matching.py` создан, 5 сценариев
- [ ] `pytest tests/test_runner_matching.py -v` — все зелёные
- [ ] `pytest tests/ -q` — вся сюита зелёная (нет регрессий)
