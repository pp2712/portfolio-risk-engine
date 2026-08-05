"""Integration test for the full risk-run orchestration: DB seed -> execute_risk_run -> assert
persisted results are internally consistent. Uses synthetic seeded data (not the real ingested
universe) so this test is self-contained and portable -- see tests/e2e for a test against the
real ingested dev data through the API.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from risk_engine.api.services.risk_run_service import RiskRunError, execute_risk_run
from risk_engine.db.models import CvarResult, ModelConfig, RiskDecomposition, VarResult
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def test_execute_risk_run_persists_consistent_results(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session)

    risk_run = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.commit()

    var_results = db_session.execute(select(VarResult).where(VarResult.risk_run_id == risk_run.risk_run_id)).scalars().all()
    cvar_results = db_session.execute(select(CvarResult).where(CvarResult.risk_run_id == risk_run.risk_run_id)).scalars().all()
    decomp = db_session.execute(select(RiskDecomposition).where(RiskDecomposition.risk_run_id == risk_run.risk_run_id)).scalars().all()

    # 3 methods x 2 confidence levels each for VaR and CVaR.
    assert len(var_results) == 6
    assert len(cvar_results) == 6
    # Decomposition computed once (primary confidence level only), one row per asset (3 assets).
    assert len(decomp) == 3

    # CVaR >= VaR invariant, for every method/confidence pair actually persisted.
    var_by_key = {(v.method, v.confidence_level): v.var_value for v in var_results}
    cvar_by_key = {(c.method, c.confidence_level): c.cvar_value for c in cvar_results}
    for key, var_val in var_by_key.items():
        assert cvar_by_key[key] >= var_val - 1e-9, f"CVaR < VaR for {key}"

    # Component VaR additivity (parametric, primary confidence level).
    parametric_var = var_by_key[("parametric", config.confidence_levels[0])]
    assert sum(d.component_var for d in decomp) == pytest.approx(parametric_var, abs=1e-6)

    assert risk_run.data_snapshot_hash  # non-empty, deterministic hash was stored
    assert risk_run.status == "completed"


def test_execute_risk_run_is_idempotent_for_same_triple(db_session):
    """(portfolio_id, config_id, as_of_date) uniquely identifies a risk run (`uq_risk_runs`).
    Re-requesting it must return the already-persisted run, not recompute/duplicate -- this is
    what makes reproducibility a cheap query rather than something that could silently drift if
    recomputed. The deeper "recompute from scratch and compare" reproducibility guarantee is
    tests/integration/test_reproducibility.py."""
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, seed=7)

    run1 = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.flush()
    run2 = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)

    assert run2.risk_run_id == run1.risk_run_id
    assert run2.data_snapshot_hash == run1.data_snapshot_hash


def test_execute_risk_run_raises_for_unknown_portfolio(db_session):
    config = ModelConfig(lookback_window_days=250, mc_num_simulations=1000, mc_random_seed=1, confidence_levels=[0.95])
    db_session.add(config)
    db_session.flush()
    with pytest.raises(RiskRunError, match="not found"):
        execute_risk_run(db_session, portfolio_id=999999, config_id=config.config_id, as_of_date=dt.date(2024, 1, 1))


def test_execute_risk_run_raises_for_insufficient_history(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=10)  # far fewer than lookback_window_days=250
    with pytest.raises(RiskRunError, match="insufficient return history"):
        execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
