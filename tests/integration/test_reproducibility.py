"""The reproducibility guarantee, tested for real rather than claimed in docs (CLAUDE.md /
blueprint Section 24): given a stored risk_run_id, re-fetching the exact input data (immutable
`returns` rows, filtered the same way) and re-running the calculation with the stored config
(including the Monte Carlo seed) must reproduce the stored result exactly -- same
data_snapshot_hash, same VaR/CVaR to the last bit.

This test forces a genuine from-scratch recomputation (not the `execute_risk_run` idempotency
shortcut that returns an already-persisted run unchanged -- that's tested separately in
test_risk_run_service.py) by deleting the risk run's own rows and calling execute_risk_run again,
which re-fetches from the database and recomputes from first principles.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from risk_engine.api.services.risk_run_service import execute_risk_run
from risk_engine.db.models import CvarResult, RiskDecomposition, RiskRun, VarResult
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def _delete_risk_run_and_children(db, risk_run_id: int) -> None:
    db.execute(delete(RiskDecomposition).where(RiskDecomposition.risk_run_id == risk_run_id))
    db.execute(delete(CvarResult).where(CvarResult.risk_run_id == risk_run_id))
    db.execute(delete(VarResult).where(VarResult.risk_run_id == risk_run_id))
    db.execute(delete(RiskRun).where(RiskRun.risk_run_id == risk_run_id))
    db.flush()


def test_recomputed_risk_run_reproduces_stored_result_exactly(db_session):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, seed=11)

    run1 = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.flush()

    original_hash = run1.data_snapshot_hash
    original_var = {
        (v.method, v.confidence_level): v.var_value
        for v in db_session.execute(select(VarResult).where(VarResult.risk_run_id == run1.risk_run_id)).scalars()
    }
    original_cvar = {
        (c.method, c.confidence_level): c.cvar_value
        for c in db_session.execute(select(CvarResult).where(CvarResult.risk_run_id == run1.risk_run_id)).scalars()
    }
    original_decomp = {
        d.asset_id: (d.component_var, d.marginal_var, d.pct_contribution)
        for d in db_session.execute(select(RiskDecomposition).where(RiskDecomposition.risk_run_id == run1.risk_run_id)).scalars()
    }

    # Force a genuine from-scratch recomputation.
    _delete_risk_run_and_children(db_session, run1.risk_run_id)

    run2 = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.flush()

    assert run2.risk_run_id != run1.risk_run_id  # confirms this really was a fresh row, not idempotency
    assert run2.data_snapshot_hash == original_hash

    new_var = {
        (v.method, v.confidence_level): v.var_value
        for v in db_session.execute(select(VarResult).where(VarResult.risk_run_id == run2.risk_run_id)).scalars()
    }
    new_cvar = {
        (c.method, c.confidence_level): c.cvar_value
        for c in db_session.execute(select(CvarResult).where(CvarResult.risk_run_id == run2.risk_run_id)).scalars()
    }
    new_decomp = {
        d.asset_id: (d.component_var, d.marginal_var, d.pct_contribution)
        for d in db_session.execute(select(RiskDecomposition).where(RiskDecomposition.risk_run_id == run2.risk_run_id)).scalars()
    }

    assert new_var.keys() == original_var.keys()
    for key, original_value in original_var.items():
        assert new_var[key] == pytest.approx(original_value, abs=0), f"VaR drifted for {key}"

    for key, original_value in original_cvar.items():
        assert new_cvar[key] == pytest.approx(original_value, abs=0), f"CVaR drifted for {key}"

    assert new_decomp.keys() == original_decomp.keys()
    for asset_id, (comp, marg, pct) in original_decomp.items():
        new_comp, new_marg, new_pct = new_decomp[asset_id]
        assert new_comp == pytest.approx(comp, abs=0)
        assert new_marg == pytest.approx(marg, abs=0)
        assert new_pct == pytest.approx(pct, abs=0)


def test_data_snapshot_hash_changes_if_underlying_data_would_differ(db_session):
    """Sanity check on the hash itself: two portfolios seeded with different random data must
    produce different snapshot hashes (the hash is actually sensitive to the data, not a constant
    or a hash of only the tickers/date)."""
    portfolio_a, config_a, as_of_date_a, _ = seed_synthetic_portfolio(db_session, seed=1, ticker_prefix="AAA")
    run_a = execute_risk_run(db_session, portfolio_a.portfolio_id, config_a.config_id, as_of_date_a)
    db_session.flush()

    portfolio_b, config_b, as_of_date_b, _ = seed_synthetic_portfolio(db_session, seed=2, ticker_prefix="BBB")
    run_b = execute_risk_run(db_session, portfolio_b.portfolio_id, config_b.config_id, as_of_date_b)

    assert run_a.data_snapshot_hash != run_b.data_snapshot_hash
