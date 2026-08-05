from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from risk_engine.risk_models.parametric import (
    parametric_cvar,
    parametric_var,
    portfolio_variance,
)


def test_parametric_var_matches_closed_form_known_case():
    # mu=0, sigma=0.02, 95% confidence -- the exact worked case from the testing strategy spec.
    mu, sigma, confidence = 0.0, 0.02, 0.95
    expected = stats.norm.ppf(confidence) * sigma - mu
    assert parametric_var(mu, sigma, confidence) == pytest.approx(expected, abs=1e-10)


def test_parametric_var_zero_sigma_is_pure_mean_reversal():
    # No volatility -- VaR degenerates to -mu exactly.
    assert parametric_var(mu_p=0.01, sigma_p=0.0, confidence=0.95) == pytest.approx(-0.01)


def test_parametric_var_negative_sigma_raises():
    with pytest.raises(ValueError):
        parametric_var(0.0, -0.01, 0.95)


def test_parametric_var_increases_with_confidence():
    mu, sigma = 0.0, 0.02
    var_95 = parametric_var(mu, sigma, 0.95)
    var_99 = parametric_var(mu, sigma, 0.99)
    assert var_99 > var_95


@pytest.mark.parametrize("mu,sigma", [(0.0, 0.02), (0.001, 0.015), (-0.002, 0.03), (0.0005, 0.05)])
def test_cvar_greater_equal_var_over_random_params(mu, sigma):
    # The invariant that must always hold, for a range of mu (including negative mu, which is
    # exactly where the blueprint's un-corrected "+mu" CVaR formula could break it).
    for confidence in (0.95, 0.99):
        var = parametric_var(mu, sigma, confidence)
        cvar = parametric_cvar(mu, sigma, confidence)
        assert cvar >= var - 1e-12, f"CVaR ({cvar}) < VaR ({var}) at mu={mu}, sigma={sigma}, conf={confidence}"


def test_parametric_cvar_matches_hand_derivation():
    mu, sigma, confidence = 0.001, 0.02, 0.95
    z = stats.norm.ppf(confidence)
    expected = sigma * stats.norm.pdf(z) / (1 - confidence) - mu
    assert parametric_cvar(mu, sigma, confidence) == pytest.approx(expected, abs=1e-10)


def test_portfolio_variance_known_two_asset_case():
    weights = np.array([0.6, 0.4])
    # Sigma = [[var_A, cov], [cov, var_B]] with var_A=0.04, var_B=0.09, cov=0.02
    cov = np.array([[0.04, 0.02], [0.02, 0.09]])
    # w^T Sigma w = 0.6^2*0.04 + 0.4^2*0.09 + 2*0.6*0.4*0.02
    expected = 0.36 * 0.04 + 0.16 * 0.09 + 2 * 0.6 * 0.4 * 0.02
    assert portfolio_variance(weights, cov) == pytest.approx(expected, abs=1e-12)


def test_portfolio_variance_single_asset_equals_its_own_variance():
    assert portfolio_variance(np.array([1.0]), np.array([[0.0025]])) == pytest.approx(0.0025)
