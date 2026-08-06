"""Integration test for the daily pipeline orchestration wiring. The ingestion step itself hits a
real network vendor (see data/vendors.py) and is exercised for real by
`scripts/generate_sample_report.py`/manual runs, not in the automated suite -- here we monkeypatch
it to a no-op so this test is fast, deterministic, and offline, while still exercising the real
risk-run -> backtest -> stress -> report wiring against seeded data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from risk_engine.db.models import Scenario
from risk_engine.scheduler import run_daily_pipeline as pipeline_module
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def test_daily_pipeline_runs_full_wiring_for_existing_portfolio(db_session, monkeypatch):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=400)
    db_session.add(Scenario(name="Test Scenario", scenario_type="HISTORICAL_REPLAY", historical_start=dt.date(2023, 1, 10), historical_end=dt.date(2023, 1, 20), version=1))
    db_session.commit()

    monkeypatch.setattr(pipeline_module, "ingest_universe", lambda *a, **k: [])
    monkeypatch.setattr(pipeline_module, "SessionLocal", lambda: db_session)
    # Prevent the fixture's session.close() from being called mid-test by the pipeline itself.
    monkeypatch.setattr(db_session, "close", lambda: None)

    summary = pipeline_module.run_daily_pipeline(as_of_date=as_of_date)

    assert summary["ingestion"] == {"tickers": 0, "rows_inserted": 0}
    assert len(summary["portfolios"]) == 1
    entry = summary["portfolios"][0]
    assert entry["portfolio_id"] == portfolio.portfolio_id
    assert "risk_run_id" in entry
    assert "backtest_id" in entry
    assert len(entry["stress_result_ids"]) == 1
    assert "report_path" in entry


def test_daily_pipeline_no_configs_returns_early(db_session, monkeypatch):
    monkeypatch.setattr(pipeline_module, "ingest_universe", lambda *a, **k: [])
    monkeypatch.setattr(pipeline_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    summary = pipeline_module.run_daily_pipeline(as_of_date=dt.date(2024, 1, 1))
    assert summary["portfolios"] == []
