"""Parametric (variance-covariance) VaR / CVaR under a normality assumption.

Portfolio returns ~ N(mu_p, sigma_p^2), sigma_p^2 = w^T Sigma w.

    VaR_alpha  = z_alpha * sigma_p - mu_p                       (z_alpha = Phi^-1(alpha), positive)
    CVaR_alpha = sigma_p * phi(z_alpha) / (1 - alpha) - mu_p     (phi = standard normal PDF)

Both are corrected/re-derived from the blueprint's Section 7.2/7.4 formulas -- see
common.py's module docstring for the VaR sign-convention fix, and the CVaR note below.

**CVaR formula correction:** the blueprint states the parametric CVaR closed form as
`mu + sigma * phi(z_alpha) / (1 - alpha)`. Re-deriving it from the definition
`CVaR_alpha = -E[R | R <= q_{1-alpha}]` for R ~ N(mu, sigma^2) gives
`CVaR_alpha = sigma * phi(z_alpha) / (1 - alpha) - mu` (mu SUBTRACTED, not added). The blueprint's
`+mu` version is consistent with its own VaR formula only when mu = 0; for nonzero mu it produces
a CVaR that is 2*mu off from the correct value and can violate the CVaR >= VaR invariant for
sufficiently negative mu. Implemented here with the derivation re-checked and a unit test
(`tests/unit/test_parametric_var.py::test_cvar_greater_equal_var_over_random_params`) asserting
the invariant holds for randomised mu/sigma.

Advantages: closed-form, fast, decomposes cleanly into Component/Marginal VaR (risk_models is not
where decomposition lives -- see portfolio/decomposition.py -- but this module supplies sigma_p).
Limitations: daily equity returns have excess kurtosis and negative skew, so this model
systematically UNDERESTIMATES tail risk relative to Historical/Monte-Carlo with fat-tailed
assumptions -- demonstrated, not just claimed, in notebooks/01_var_model_comparison.ipynb
(Experiment 1).
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from risk_engine.risk_models.common import z_score


def portfolio_variance(weights: np.ndarray, covariance: np.ndarray) -> float:
    """sigma_p^2 = w^T Sigma w."""
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(covariance, dtype=float)
    return float(w @ sigma @ w)


def parametric_var(mu_p: float, sigma_p: float, confidence: float) -> float:
    if sigma_p < 0:
        raise ValueError("sigma_p must be non-negative")
    z = z_score(confidence)
    return z * sigma_p - mu_p


def parametric_cvar(mu_p: float, sigma_p: float, confidence: float) -> float:
    if sigma_p < 0:
        raise ValueError("sigma_p must be non-negative")
    z = z_score(confidence)
    phi_z = float(stats.norm.pdf(z))
    return sigma_p * phi_z / (1.0 - confidence) - mu_p


def parametric_var_cvar(mu_p: float, sigma_p: float, confidence: float) -> tuple[float, float]:
    return parametric_var(mu_p, sigma_p, confidence), parametric_cvar(mu_p, sigma_p, confidence)
