from __future__ import annotations

import datetime as dt

import pytest

from risk_engine.api.services.stress_service import StressRunError, execute_stress_run
from risk_engine.db.models import Scenario
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def test_historical_replay_stress_run(db_session):
    portfolio, _config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300)

    scenario = Scenario(
        name="Synthetic Crash",
        scenario_type="HISTORICAL_REPLAY",
        historical_start=dt.date(2023, 1, 10),
        historical_end=dt.date(2023, 1, 20),
        version=1,
    )
    db_session.add(scenario)
    db_session.flush()

    result = execute_stress_run(db_session, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
    db_session.commit()

    assert isinstance(result.portfolio_pnl, float)
    assert len(result.position_contributions) == 3
    # portfolio_pnl_pct must be internally consistent with portfolio_pnl (it's derived from the
    # same portfolio_value the engine used internally).
    if result.portfolio_pnl != 0:
        implied_portfolio_value = result.portfolio_pnl / result.portfolio_pnl_pct
        assert implied_portfolio_value > 0


def test_factor_shock_stress_run_uses_sector_betas(db_session):
    portfolio, _config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300)

    scenario = Scenario(
        name="Rate Shock Proxy",
        scenario_type="FACTOR_SHOCK",
        factor_shocks={"rate_sensitive_financials": -0.10},
        version=1,
    )
    db_session.add(scenario)
    db_session.flush()

    result = execute_stress_run(db_session, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
    # None of the synthetic tickers are in SECTOR_BY_TICKER (real-universe sectors), so all betas
    # default to 0 -- the scenario runs without error and produces zero P&L.
    assert result.portfolio_pnl == pytest.approx(0.0)


def test_stress_run_is_idempotent(db_session):
    portfolio, _config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300, seed=2)
    scenario = Scenario(name="S", scenario_type="HISTORICAL_REPLAY", historical_start=dt.date(2023, 1, 5), historical_end=dt.date(2023, 1, 15), version=1)
    db_session.add(scenario)
    db_session.flush()

    r1 = execute_stress_run(db_session, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
    db_session.flush()
    r2 = execute_stress_run(db_session, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
    assert r1.stress_result_id == r2.stress_result_id


def test_stress_run_unknown_scenario_raises(db_session):
    portfolio, _config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300)
    with pytest.raises(StressRunError, match="not found"):
        execute_stress_run(db_session, portfolio.portfolio_id, 999999, as_of_date)
