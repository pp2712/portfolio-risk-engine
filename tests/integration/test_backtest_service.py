from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from risk_engine.api.services.backtest_service import BacktestError, execute_backtest
from risk_engine.db.models import BacktestException
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def test_execute_backtest_persists_summary_and_exceptions(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=400)
    window_start = as_of_date - dt.timedelta(days=100)
    window_end = as_of_date

    result = execute_backtest(
        db_session, portfolio.portfolio_id, config.config_id, method="historical", confidence=0.95,
        window_start=window_start, window_end=window_end,
    )
    db_session.commit()

    assert result.num_observations > 0
    assert 0.0 <= result.kupiec_pvalue <= 1.0
    assert result.traffic_light_zone in {"green", "amber", "red"}

    exceptions = db_session.execute(
        select(BacktestException).where(BacktestException.backtest_id == result.backtest_id)
    ).scalars().all()
    assert len(exceptions) == result.num_observations
    assert sum(e.is_exception for e in exceptions) == result.num_exceptions


def test_execute_backtest_is_idempotent(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=400, seed=3)
    window_start = as_of_date - dt.timedelta(days=60)

    r1 = execute_backtest(db_session, portfolio.portfolio_id, config.config_id, "historical", 0.95, window_start, as_of_date)
    db_session.flush()
    r2 = execute_backtest(db_session, portfolio.portfolio_id, config.config_id, "historical", 0.95, window_start, as_of_date)
    assert r1.backtest_id == r2.backtest_id


def test_execute_backtest_all_three_methods_run(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=400, seed=9)
    window_start = as_of_date - dt.timedelta(days=40)

    for method in ("historical", "parametric", "monte_carlo"):
        result = execute_backtest(db_session, portfolio.portfolio_id, config.config_id, method, 0.95, window_start, as_of_date)
        assert result.num_observations > 0, f"{method} produced no observations"


def test_execute_backtest_unknown_method_raises(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300)
    with pytest.raises(BacktestError, match="unknown method"):
        execute_backtest(db_session, portfolio.portfolio_id, config.config_id, "bogus_method", 0.95, as_of_date - dt.timedelta(days=10), as_of_date)


def test_execute_backtest_unknown_portfolio_raises(db_session):
    config = seed_synthetic_portfolio(db_session, n_days=300)[1]
    with pytest.raises(BacktestError, match="not found"):
        execute_backtest(db_session, 999999, config.config_id, "historical", 0.95, dt.date(2023, 1, 1), dt.date(2023, 2, 1))
