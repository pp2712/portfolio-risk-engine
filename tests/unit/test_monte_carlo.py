from __future__ import annotations

import numpy as np
import pytest

from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar, simulate_asset_returns


def test_simulate_asset_returns_shape():
    mu = np.array([0.001, 0.0005])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0009]])
    sims = simulate_asset_returns(mu, cov, n_simulations=1000, seed=1)
    assert sims.shape == (1000, 2)


def test_simulate_asset_returns_same_seed_is_reproducible():
    mu = np.array([0.0, 0.0])
    cov = np.eye(2) * 0.0004
    a = simulate_asset_returns(mu, cov, n_simulations=500, seed=123)
    b = simulate_asset_returns(mu, cov, n_simulations=500, seed=123)
    np.testing.assert_array_equal(a, b)


def test_simulate_asset_returns_different_seed_differs():
    mu = np.array([0.0, 0.0])
    cov = np.eye(2) * 0.0004
    a = simulate_asset_returns(mu, cov, n_simulations=500, seed=1)
    b = simulate_asset_returns(mu, cov, n_simulations=500, seed=2)
    assert not np.array_equal(a, b)


def test_simulate_asset_returns_sample_covariance_converges_to_target():
    mu = np.array([0.0, 0.0])
    cov = np.array([[0.0004, 0.0002], [0.0002, 0.0009]])
    sims = simulate_asset_returns(mu, cov, n_simulations=200_000, seed=42)
    sample_cov = np.cov(sims, rowvar=False)
    np.testing.assert_allclose(sample_cov, cov, atol=2e-5)


def test_simulate_asset_returns_student_t_covariance_matches_target():
    # The (df-2)/df scale correction should make the realised covariance match `cov` even though
    # the underlying draw is fat-tailed, not normal.
    mu = np.array([0.0, 0.0])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0009]])
    sims = simulate_asset_returns(mu, cov, n_simulations=300_000, seed=7, distribution="student_t", t_df=5)
    sample_cov = np.cov(sims, rowvar=False)
    np.testing.assert_allclose(sample_cov, cov, atol=5e-5)


def test_simulate_asset_returns_invalid_distribution_raises():
    with pytest.raises(ValueError):
        simulate_asset_returns(np.zeros(1), np.eye(1), 10, seed=1, distribution="bogus")


def test_monte_carlo_var_cvar_reproducible_with_same_seed():
    weights = np.array([0.5, 0.5])
    mu = np.array([0.0, 0.0])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0009]])
    r1 = monte_carlo_var_cvar(weights, mu, cov, confidence=0.95, n_simulations=5000, seed=99)
    r2 = monte_carlo_var_cvar(weights, mu, cov, confidence=0.95, n_simulations=5000, seed=99)
    assert r1.var == r2.var
    assert r1.cvar == r2.cvar
    assert r1.seed == 99
    assert r1.n_simulations == 5000


def test_monte_carlo_cvar_greater_equal_var():
    weights = np.array([0.3, 0.7])
    mu = np.array([0.0002, -0.0001])
    cov = np.array([[0.0006, 0.0002], [0.0002, 0.0012]])
    result = monte_carlo_var_cvar(weights, mu, cov, confidence=0.99, n_simulations=20_000, seed=5)
    assert result.cvar >= result.var
