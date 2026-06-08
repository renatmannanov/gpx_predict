# Шаг 2: Миграция БД — колонка source + новый UNIQUE constraint

> Зависит от: нет (можно параллельно со step_1, но применять после)
> Статус: [ ] pending
> Файлы: backend/app/features/races/db_models.py, новая миграция 019

## Задача

### Модель (db_models.py)
В классе `Runner` (db_models.py:52-59):
```python
# Было:
name_normalized = Column(String(255), nullable=False, unique=True, index=True)

# Станет (убрать unique=True, добавить колонку source и составной constraint):
name_normalized = Column(String(255), nullable=False, index=True)
source = Column(String(20), nullable=False, default="athletex")  # "am" | "athletex"

__table_args__ = (
    # UNIQUE только когда birth_year известен. NULL в Postgres != NULL,
    # поэтому фрагменты без birth_year не конфликтуют автоматически.
    UniqueConstraint("name_normalized", "birth_year", "source", name="uq_runner_name_birth_source"),
    Index("ix_runner_source", "source"),
)
```

### Миграция (новый файл 019)
Revision ID: **`019_runner_source`** (≤32 символов — правило проекта).

**ВАЖНО — реальные имена объектов (проверено `\d runners` 2026-06-08):**
На колонке `name_normalized` сейчас ДВА объекта уникальности, снять ОБА:
- индекс `ix_runners_name_normalized` (UNIQUE)
- констрейнт `uq_runners_name_normalized` (UNIQUE CONSTRAINT)

(`unique=True, index=True` в модели создаёт оба. Имени `runners_name_normalized_key`
НЕ существует — не использовать.)

```python
def upgrade():
    # 1. Добавить колонку source с дефолтом
    op.add_column("runners", sa.Column("source", sa.String(20),
                  nullable=False, server_default="athletex"))
    # 2. Снять СТАРЫЕ объекты уникальности (оба!)
    op.drop_constraint("uq_runners_name_normalized", "runners", type_="unique")
    op.drop_index("ix_runners_name_normalized", table_name="runners")
    # 3. Новый составной UNIQUE + индекс по source
    op.create_unique_constraint("uq_runner_name_birth_source", "runners",
                                ["name_normalized", "birth_year", "source"])
    op.create_index("ix_runner_source", "runners", ["source"])
    # name_normalized остаётся индексированным (модель: index=True без unique)
    op.create_index("ix_runners_name_normalized", "runners", ["name_normalized"])

def downgrade():
    op.drop_index("ix_runners_name_normalized", table_name="runners")
    op.drop_index("ix_runner_source", table_name="runners")
    op.drop_constraint("uq_runner_name_birth_source", "runners", type_="unique")
    op.create_index("ix_runners_name_normalized", "runners",
                    ["name_normalized"], unique=True)
    op.create_unique_constraint("uq_runners_name_normalized", "runners",
                                ["name_normalized"])
    op.drop_column("runners", "source")
```

## ⚠️ Этот шаг НЕ применяет миграцию
step_2 ТОЛЬКО пишет код модели (db_models.py) и файл миграции 019.
**`alembic upgrade head` запускается ЕДИНСТВЕННЫЙ раз — в step_4, ПОСЛЕ TRUNCATE.**
Не запускать alembic здесь. Причина: на живых данных (20K runners, дубли
birth_year в результатах) применять незачем — step_4 всё равно пересоберёт с нуля.
Жёсткий порядок: TRUNCATE (step_4) → migrate (step_4) → reparse (step_4).

## Команды для верификации (этого шага — только код, без применения)
```bash
# Файл миграции создан, revision id ≤ 32 символов
ls backend/alembic/versions/ | grep 019_runner_source

# Python синтаксис миграции и модели ок
python -c "import ast; ast.parse(open('backend/alembic/versions/019_runner_source.py').read())"
python -c "import ast; ast.parse(open('backend/app/features/races/db_models.py').read())"

# Модель Runner: source есть, unique=True на name_normalized УБРАН
grep -n "source\|name_normalized\|uq_runner_name_birth_source" \
  backend/app/features/races/db_models.py
```
(Применение и проверка `\d runners` — в step_4 после TRUNCATE.)

## Критерии готовности
- [ ] Колонка `source` добавлена в модель Runner (`db_models.py`)
- [ ] `unique=True` снят с `name_normalized` в модели (остаётся `index=True`)
- [ ] Составной `UniqueConstraint(name_normalized, birth_year, source)` в `__table_args__`
- [ ] Файл миграции `019_runner_source.py` создан, дропает ОБА реальных объекта
- [ ] Revision id ≤ 32 символов
- [ ] Синтаксис миграции и модели валиден (`ast.parse`)
- [ ] alembic НЕ запускался в этом шаге (применение — в step_4)
- [ ] Revision id ≤ 32 символов
