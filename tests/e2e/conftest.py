from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from risk_engine.api.deps import get_db
from risk_engine.api.main import app
from risk_engine.config import get_settings


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def api_key_headers():
    return {"X-API-Key": get_settings().api_key}
