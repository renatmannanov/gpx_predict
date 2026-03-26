# Phonetic Normalization — схлопывание вариантов транслитерации

> Статус: pending
> Дата: 2026-03-19
> Ветка: step-1c-am-pilot

## Проблема

similarity() не различает варианты транслитерации (`andrey/andrei` = один человек) от разных имён (`aida/aidana` = разные люди). Оба дают sim ~0.79.

Анализ 498 вручную проверенных пар:
- 256 реальных дублей (approved=1)
- 78 ложных (approved=0)
- Precision: 77%

## Решение

Добавить `phonetic_normalize()` — детерминированные regex-замены, схлопывающие варианты транслитерации в одну каноническую форму. Применяется пословно, ПОСЛЕ transliterate + lowercase, ДО sort.

## Правила (консервативные)

Порядок важен — выполнять сверху вниз.

| # | Regex (per word) | Замена | Покрытие | Пример |
|---|------------------|--------|----------|--------|
| 1 | `([aeiou])j(?=[aeiou])` | `\1y` | 12 пар | ajgul → aygul |
| 2 | `j$` | `y` | 11 пар | sergej → sergey |
| 3 | `([aeiou])ev$` | `\1yev` | 40 пар | baev → bayev |
| 4 | `([aeiou])eva$` | `\1yeva` | 23 пары | baeva → bayeva |
| 5 | `ii$` | `iy` | ~12 пар | dmitrii → dmitriy |
| 6 | `ei$` | `ey` | ~12 пар | andrei → andrey |
| 7 | `x` → `ks` | replace all | 7 пар | alexandr → aleksandr |

### Пропущены (слишком рискованно)

- `h` → `kh` — 3 пары, но сломает sh/ch/zh
- `ia` → `ya` — 5 пар, но tatiana — легитимное написание

## Шаги реализации

### Шаг 1. Функция `phonetic_normalize()` в name_utils.py

- [x] Добавить `phonetic_normalize_word(word: str) -> str`
- [x] 7 regex-правил в указанном порядке
- [x] Работает пословно (не на всей строке)

### Шаг 2. Интеграция в `normalize_name()`

- [x] Вызвать после lowercase, до sort:
  ```python
  words = [phonetic_normalize_word(w) for w in name.split()]
  parts = sorted(words)
  ```
- [x] Обновить docstring и doctests

### Шаг 3. Тесты

- [x] Тесты `phonetic_normalize_word()`: каждое правило отдельно
- [x] Тесты identity: `sergey` → `sergey` (уже каноническая)
- [x] Тесты safety: `aida` != `aidana`, `arina` != `alina`
- [x] End-to-end: 10-20 пар из audit CSV

### Шаг 4. Миграция данных (скрипт `update_phonetic_norm.py`)

**UNIQUE constraint на `runners.name_normalized`** — при схлопывании двух разных
`name_normalized` в одну, нужно сначала мёрджить runners.

- [ ] **Phase A: Detect** (`--detect`)
  - Вычислить новый `name_normalized` для каждого runner
  - Найти коллизии (разные старые → одинаковый новый)
  - Вывести CSV: keep_id, merge_id, same_birth_year
  - ~222 пары ожидается

- [ ] **Phase B: Merge** (`--merge`)
  - Авто-мёрдж если birth_year совпадает или один NULL
  - Пропуск если birth_year разный (разные люди)
  - Использовать логику merge_runners.py

- [ ] **Phase C: Update** (`--update`)
  - Обновить `runners.name_normalized` (21k)
  - Обновить `runner_name_aliases.name_normalized`
  - Батчами по 1000
  - `--dry-run` флаг обязателен

### Шаг 5. Верификация

- [ ] Перезапустить анализ 498 пар:
  - approved=1: сколько теперь exact match? (было ~60%, должно стать ~85%+)
  - approved=0: все ли остались distinct? (должно быть 78/78)
- [ ] Вывести метрики before/after

## Порядок реализации

1. Шаг 1 → Шаг 2 → Шаг 3 (код, без изменений в БД)
2. Шаг 4 (миграция, backup сначала)
3. Шаг 5 (проверка)

## Риски

- **UNIQUE collision при update**: решается мёрджем в Phase B до update
- **Aliases table** (`runner_id, name_normalized` UNIQUE): при схлопывании ON CONFLICT DO NOTHING
- **`x` → `ks` для нерусских имён**: Xavier, Felix — редки, `ks` каноническая форма
- **Каскад**: `race_results.name_normalized` денормализован, обновить вместе с runners
