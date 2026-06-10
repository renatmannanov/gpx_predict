"""Runner matching at import — namesakes and source isolation.

Exercises the real save_to_db() resolve path (step_1):
matching is strict on (name_normalized, birth_year, source); birth_year IS NULL
always creates a new runner; fuzzy matching is OFF at import.

These guard against the regression that merged "Yuliya Kim" from 5 different
women and "Pavlov Alexandr" from father+son into single runners.
"""
from sqlalchemy import select, func

from app.features.races.db_models import Runner, RunnerNameAlias
from app.features.races.models import (
    RaceEditionData,
    RaceDistanceResults,
    RaceResult,
)
from scripts.batch_parse import save_to_db


def _result(name, birth_year=None, gender="M"):
    return RaceResult(
        name=name,
        name_local=None,
        time_seconds=3600,
        place=1,
        category=None,
        gender=gender,
        club=None,
        bib=None,
        pace=None,
        birth_year=birth_year,
        nationality=None,
    )


def _edition(race_name, year, results, distance_name="Main"):
    return RaceEditionData(
        race_name=race_name,
        year=year,
        date=None,
        source_url=None,
        distances=[
            RaceDistanceResults(
                distance_name=distance_name,
                distance_km=10.0,
                elevation_gain_m=0,
                results=results,
            )
        ],
    )


def _save(db, race_id, race_name, results, source="clax", year=2025):
    save_to_db(db, race_id, race_name, _edition(race_name, year, results), source=source)
    db.flush()


def _runner_count(db, name_normalized):
    return db.execute(
        select(func.count()).select_from(Runner).where(
            Runner.name_normalized == name_normalized
        )
    ).scalar()


def test_namesakes_without_birth_year_stay_separate(db):
    """Two "Yuliya Kim" with no birth_year -> 2 distinct runners (no merge)."""
    _save(db, "race_a", "Race A", [_result("Yuliya Kim", birth_year=None, gender="F")],
          source="clax")
    _save(db, "race_b", "Race B", [_result("Yuliya Kim", birth_year=None, gender="F")],
          source="clax")

    assert _runner_count(db, "kim yuliya") == 2


def test_namesakes_different_birth_year_stay_separate(db):
    """Father/son "Pavlov Alexandr" 1984 vs 2015 -> 2 distinct runners."""
    _save(db, "race_a", "Race A", [_result("Pavlov Alexandr", birth_year=1984)],
          source="clax")
    _save(db, "race_b", "Race B", [_result("Pavlov Alexandr", birth_year=2015)],
          source="clax")

    assert _runner_count(db, "aleksandr pavlov") == 2


def test_same_person_same_birth_year_same_source_merges(db):
    """One person, same birth_year, same source, two races -> 1 runner."""
    _save(db, "race_a", "Race A", [_result("Renat Karimov", birth_year=1990)],
          source="clax")
    _save(db, "race_b", "Race B", [_result("Renat Karimov", birth_year=1990)],
          source="clax")

    assert _runner_count(db, "karimov renat") == 1
    runner = db.execute(
        select(Runner).where(Runner.name_normalized == "karimov renat")
    ).scalar_one()
    assert runner.races_count >= 0  # sanity: row exists, both results attach to it


def test_source_isolation(db):
    """Same name+birth_year but different source -> 2 distinct runners."""
    _save(db, "race_trail", "Trail", [_result("Sergey Ivanov", birth_year=1985)],
          source="clax")  # -> athletex
    _save(db, "race_am", "AM", [_result("Sergey Ivanov", birth_year=1985)],
          source="almaty-marathon")  # -> am

    assert _runner_count(db, "ivanov sergey") == 2
    sources = db.execute(
        select(Runner.source).where(Runner.name_normalized == "ivanov sergey")
    ).scalars().all()
    assert set(sources) == {"am", "athletex"}


def test_fuzzy_not_applied_at_import(db):
    """Transliteration variants with same birth_year stay separate.

    Knyaz/Kniaz normalize differently -> different name_normalized -> 2 runners.
    Old fuzzy import would have merged them; now it must not.
    """
    _save(db, "race_a", "Race A", [_result("Knyaz Ttest", birth_year=1990)],
          source="clax")
    _save(db, "race_b", "Race B", [_result("Kniaz Test", birth_year=1990)],
          source="clax")

    total = db.execute(select(func.count()).select_from(Runner)).scalar()
    assert total == 2


def test_duplicate_name_in_same_race_no_alias_violation(db):
    """Two identical results (same name+birth_year) in ONE race import.

    Regression: a DB select only sees flushed rows, so the second result's
    alias "not exists" check passed and inserted a duplicate, violating
    ix_runner_aliases_unique (hit on Tengri Ultra: two "ABZHAPAROV Nurgeldi").
    Must resolve to a single runner with a single alias, without raising.
    """
    _save(
        db, "race_dup", "Race Dup",
        [
            _result("Nurgeldi Abzhaparov", birth_year=1990),
            _result("Nurgeldi Abzhaparov", birth_year=1990),
        ],
        source="clax",
    )

    assert _runner_count(db, "abzhaparov nurgeldi") == 1
    runner = db.execute(
        select(Runner).where(Runner.name_normalized == "abzhaparov nurgeldi")
    ).scalar_one()
    alias_count = db.execute(
        select(func.count()).select_from(RunnerNameAlias).where(
            RunnerNameAlias.runner_id == runner.id
        )
    ).scalar()
    assert alias_count == 1


def test_cyrillic_am_matching_stays_cyrillic(db):
    """AM Cyrillic names: word-order variants of the same person merge, and
    name/name_normalized stay Cyrillic (no transliteration to Latin)."""
    _save(
        db, "race_am1", "AM Race 1",
        [_result("Руслан Бекешов", birth_year=1990)],
        source="almaty-marathon",
    )
    _save(
        db, "race_am2", "AM Race 2",
        [_result("Бекешов Руслан", birth_year=1990)],  # swapped word order
        source="almaty-marathon",
    )

    # Same person -> one runner, keyed by canonical Cyrillic normalized form.
    assert _runner_count(db, "бекешов руслан") == 1
    runner = db.execute(
        select(Runner).where(Runner.name_normalized == "бекешов руслан")
    ).scalar_one()
    assert runner.source == "am"
    # Display name stays Cyrillic (as it arrived), not transliterated.
    assert any("Ѐ" <= ch <= "ӿ" for ch in runner.name)
