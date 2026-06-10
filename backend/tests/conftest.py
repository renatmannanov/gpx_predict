"""Pytest fixtures — isolated PostgreSQL test database.

Builds the schema from the SQLAlchemy models (Base.metadata.create_all), so the
new `runners.source` column and the composite UNIQUE constraint added in step_2
are exercised without depending on alembic (the migration is applied to the dev
DB only in step_4). Each test runs in a transaction that is rolled back, so tests
never persist into the test DB and stay isolated from each other.

Test DB connection: env TEST_DATABASE_URL, else derives a `_test` DB from the
app's database_url. NEVER points at the dev DB (gpx_predictor).
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base

# Register every model on Base.metadata before create_all.
import app.features.races.db_models  # noqa: F401
import app.features.users.models  # noqa: F401
import app.features.gpx.models  # noqa: F401
import app.features.strava.models  # noqa: F401
from app.models import prediction, user_profile, user_run_profile  # noqa: F401


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        return url
    # Derive a sibling `_test` database from the configured app DB.
    base = settings.database_url
    db_name = base.rsplit("/", 1)[-1].split("?", 1)[0]
    if db_name == "gpx_predictor_test":
        return base
    safety = db_name + "_test"
    return base.rsplit("/", 1)[0] + "/" + safety


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(_test_database_url())
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """A session bound to a transaction that is rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
