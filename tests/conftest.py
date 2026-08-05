"""Shared pytest fixtures.

Integration/e2e tests get a real Postgres session against `portfolio_risk_engine_test`, with all
tables truncated between tests so each test starts from a clean slate.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from risk_engine.config import get_settings
from risk_engine.db.models import Base


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Session:
    SessionLocal = sessionmaker(bind=test_engine, future=True)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        # Truncate all tables (fast, keeps schema) so tests are isolated without full re-create.
        with test_engine.begin() as conn:
            table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
            conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        session.close()
