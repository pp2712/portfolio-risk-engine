"""Risk decomposition: Marginal VaR and Component VaR (parametric closed form).

    Marginal VaR_i  = d(VaR_p) / d(w_i)
    Component VaR_i = w_i * MarginalVaR_i
    invariant:  sum_i(ComponentVaR_i) == VaR_p   (exactly, by construction -- see below)

Standalone VaR (each position's VaR computed in isolation, ignoring correlation) is NOT
implemented here as a decomposition -- it overstates total risk (ignores diversification) and is
only useful for the diversification-benefit metric in portfolio/calculations.py, not as a
"risk contribution by position" breakdown. Component VaR is the right choice for that: additive by
construction, which Standalone VaR is not.

**Formula correction vs. the source blueprint:** Section 14-15 states
`MarginalVaR_i = z_alpha * (Sigma w)_i / sigma_p`, omitting the portfolio-mean term. Given this
project's parametric VaR is `VaR_p = z_alpha * sigma_p - mu_p` (see risk_models/parametric.py),
differentiating the FULL expression w.r.t. w_i gives
`MarginalVaR_i = z_alpha * (Sigma w)_i / sigma_p - mu_i` (mu_i = asset i's mean return). Dropping
the `-mu_i` term is fine only when mu_p ~ 0; keeping it is what makes
`sum_i(w_i * MarginalVaR_i) == VaR_p` hold EXACTLY rather than approximately (verified by
Euler's theorem for the homogeneous-degree-1 sigma_p term, plus exact linearity of the mean term).
See tests/unit/test_decomposition.py::test_component_var_sums_to_portfolio_var_exactly and
docs/QUANTITATIVE_METHODOLOGY.md.
"""

from __future__ import annotations

import numpy as np

from risk_engine.risk_models.common import z_score


def marginal_var(weights: np.ndarray, mu: np.ndarray, covariance: np.ndarray, confidence: float, sigma_p: float) -> np.ndarray:
    """MVaR_i = z_alpha * (Sigma w)_i / sigma_p - mu_i. Returns an array, one entry per asset."""
    if sigma_p <= 0:
        raise ValueError("sigma_p must be positive (zero-volatility portfolio has undefined marginal risk)")
    z = z_score(confidence)
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(covariance, dtype=float)
    sigma_w = sigma @ w
    return z * sigma_w / sigma_p - np.asarray(mu, dtype=float)


def component_var(weights: np.ndarray, marginal_var_values: np.ndarray) -> np.ndarray:
    """ComponentVaR_i = w_i * MarginalVaR_i."""
    return np.asarray(weights, dtype=float) * np.asarray(marginal_var_values, dtype=float)


def pct_contribution(component_var_values: np.ndarray, portfolio_var: float) -> np.ndarray:
    """Each position's share of total portfolio VaR. Sums to 1.0 (given the additivity invariant)."""
    if portfolio_var == 0:
        return np.zeros_like(component_var_values)
    return np.asarray(component_var_values, dtype=float) / portfolio_var
