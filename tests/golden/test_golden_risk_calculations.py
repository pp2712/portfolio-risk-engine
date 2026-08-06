"""Golden/regression test: a fixed synthetic dataset's risk-calculation output is stored as a
reference (`reference_output.json`). Any future code change that alters the numeric output without
an explicit, reviewed reason (regenerate via `python -m tests.golden.generate_reference`, which
must be a deliberate action, not a reflexive "make the test pass") fails this test.

Deliberately DB-free and fast (pure risk_models/portfolio functions only) so it runs on every
commit as part of the unit-test-speed tier, not gated behind Postgres availability.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from risk_engine.portfolio.calculations import herfindahl_hirschman_index, max_drawdown
from risk_engine.portfolio.decomposition import component_var, marginal_var
from risk_engine.risk_models.historical import historical_var_cvar
from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar
from risk_engine.risk_models.parametric import parametric_var_cvar, portfolio_variance
from risk_engine.validation.christoffersen import christoffersen_independence_test
from risk_engine.validation.kupiec import kupiec_pof_test

REFERENCE_PATH = Path(__file__).parent / "reference_output.json"


def _build_fixed_scenario():
    """A fixed, deterministic synthetic 4-asset portfolio -- same construction every time this
    function is called, in this file or in generate_reference.py. Do not change this function
    without regenerating the reference output deliberately."""
    rng = np.random.default_rng(20240101)
    n_assets, n_obs = 4, 500
    weights = np.array([0.4, 0.3, 0.2, 0.1])

    a = rng.normal(0, 0.02, (n_assets, n_assets))
    cov = a @ a.T + np.eye(n_assets) * 1e-5
    mu = np.array([0.0003, 0.0002, 0.0001, -0.0001])

    returns = rng.multivariate_normal(mu, cov, size=n_obs)
    portfolio_returns = returns @ weights
    return weights, mu, cov, returns, portfolio_returns


def _compute_golden_output() -> dict:
    weights, mu, cov, returns, portfolio_returns = _build_fixed_scenario()
    confidence = 0.95

    sigma_p = float(np.sqrt(portfolio_variance(weights, cov)))
    mu_p = float(weights @ mu)

    h_var, h_cvar = historical_var_cvar(portfolio_returns, confidence)
    p_var, p_cvar = parametric_var_cvar(mu_p, sigma_p, confidence)
    mc = monte_carlo_var_cvar(weights, mu, cov, confidence, n_simulations=50_000, seed=777)

    mvar = marginal_var(weights, mu, cov, confidence, sigma_p)
    cvars = component_var(weights, mvar)

    hhi = herfindahl_hirschman_index({f"A{i}": w for i, w in enumerate(weights)})

    # Synthetic backtest exception series (deterministic from the same portfolio_returns).
    var_forecast = p_var
    exceptions = (portfolio_returns < -var_forecast).astype(int).tolist()
    n_obs, n_exc = len(exceptions), sum(exceptions)
    kupiec = kupiec_pof_test(n_obs, n_exc, confidence)
    christoffersen = christoffersen_independence_test(exceptions)

    simple_returns_series = portfolio_returns  # small values, log~=simple for this synthetic case
    import pandas as pd

    mdd = max_drawdown(pd.Series(simple_returns_series))

    return {
        "historical_var": h_var, "historical_cvar": h_cvar,
        "parametric_var": p_var, "parametric_cvar": p_cvar,
        "monte_carlo_var": mc.var, "monte_carlo_cvar": mc.cvar,
        "component_var": cvars.tolist(),
        "hhi": hhi,
        "kupiec_lr": kupiec.lr_statistic, "kupiec_pvalue": kupiec.p_value,
        "christoffersen_lr": christoffersen.lr_statistic,
        "n_exceptions": n_exc,
        "max_drawdown": mdd,
    }


def test_golden_risk_calculations_match_stored_reference():
    if not REFERENCE_PATH.exists():
        pytest.fail(
            f"no golden reference at {REFERENCE_PATH} -- generate it deliberately with "
            "`python -m tests.golden.generate_reference` and commit it, do not create it "
            "reflexively just to make this test pass"
        )

    reference = json.loads(REFERENCE_PATH.read_text())
    actual = _compute_golden_output()

    for key, expected_value in reference.items():
        actual_value = actual[key]
        if isinstance(expected_value, list):
            np.testing.assert_allclose(actual_value, expected_value, rtol=1e-9, atol=1e-12, err_msg=f"golden mismatch: {key}")
        else:
            assert actual_value == pytest.approx(expected_value, rel=1e-9, abs=1e-12), f"golden mismatch: {key} (expected {expected_value}, got {actual_value})"
