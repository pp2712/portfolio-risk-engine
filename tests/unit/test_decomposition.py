from __future__ import annotations

import numpy as np
import pytest

from risk_engine.portfolio.decomposition import component_var, marginal_var, pct_contribution
from risk_engine.risk_models.parametric import parametric_var, portfolio_variance


def _random_portfolio(rng, n_assets):
    weights = rng.dirichlet(np.ones(n_assets))  # sums to 1, all positive -- long-only
    mu = rng.normal(0.0002, 0.0005, n_assets)
    a = rng.normal(0, 0.02, (n_assets, n_assets))
    cov = a @ a.T + np.eye(n_assets) * 1e-6  # guaranteed positive semi-definite
    return weights, mu, cov


@pytest.mark.parametrize("n_assets,seed", [(2, 1), (5, 2), (10, 3), (20, 4)])
def test_component_var_sums_to_portfolio_var_exactly(n_assets, seed):
    rng = np.random.default_rng(seed)
    weights, mu, cov = _random_portfolio(rng, n_assets)
    confidence = 0.95

    sigma_p = float(np.sqrt(portfolio_variance(weights, cov)))
    mu_p = float(weights @ mu)
    portfolio_var = parametric_var(mu_p, sigma_p, confidence)

    mvar = marginal_var(weights, mu, cov, confidence, sigma_p)
    cvar = component_var(weights, mvar)

    assert np.sum(cvar) == pytest.approx(portfolio_var, abs=1e-9)


def test_pct_contribution_sums_to_one():
    rng = np.random.default_rng(5)
    weights, mu, cov = _random_portfolio(rng, 8)
    confidence = 0.99
    sigma_p = float(np.sqrt(portfolio_variance(weights, cov)))
    mu_p = float(weights @ mu)
    portfolio_var = parametric_var(mu_p, sigma_p, confidence)

    mvar = marginal_var(weights, mu, cov, confidence, sigma_p)
    cvar = component_var(weights, mvar)
    pct = pct_contribution(cvar, portfolio_var)

    assert np.sum(pct) == pytest.approx(1.0, abs=1e-9)


def test_marginal_var_single_asset_equals_full_portfolio_var():
    # A single-asset "portfolio" -- marginal VaR must equal that asset's own parametric VaR.
    weights = np.array([1.0])
    mu = np.array([0.0003])
    cov = np.array([[0.0004]])
    confidence = 0.95
    sigma_p = float(np.sqrt(portfolio_variance(weights, cov)))

    mvar = marginal_var(weights, mu, cov, confidence, sigma_p)
    expected_var = parametric_var(mu[0], sigma_p, confidence)
    assert mvar[0] == pytest.approx(expected_var)


def test_marginal_var_zero_sigma_raises():
    with pytest.raises(ValueError):
        marginal_var(np.array([1.0]), np.array([0.0]), np.array([[0.0]]), 0.95, sigma_p=0.0)


def test_pct_contribution_zero_portfolio_var_returns_zeros():
    result = pct_contribution(np.array([1.0, 2.0]), portfolio_var=0.0)
    np.testing.assert_array_equal(result, np.array([0.0, 0.0]))
