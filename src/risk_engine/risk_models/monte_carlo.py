"""Monte Carlo VaR / CVaR: simulate N correlated portfolio return paths, then apply the same
"k worst observations" empirical estimator used by historical.py to the simulated sample.

For a long-only, linear (non-derivative) portfolio, simulated asset returns map directly to a
simulated portfolio return via the weight vector -- no iterative per-instrument revaluation is
needed (that only becomes necessary with non-linear instruments, which are out of scope; see
docs/KNOWN_LIMITATIONS.md).

Reproducibility (required for CLAUDE.md's audit-trail guarantee): every simulation uses an
explicit, caller-supplied integer seed via `numpy.random.default_rng`, never implicit global RNG
state. The seed and simulation count are returned in `MonteCarloResult` so a stored risk_run can
be re-run byte-for-byte from its `model_configs` row.

Distribution: defaults to multivariate normal, matching the same (mu, Sigma) as parametric VaR --
this makes the MC-vs-parametric convergence check in
notebooks/01_var_model_comparison.ipynb / tests/statistical/test_monte_carlo_convergence.py a
genuine "does my simulator implement the model correctly" test. An optional multivariate
Student's-t mode (fat tails) is offered as the documented Advanced-tier extension demonstrating
Monte Carlo's real advantage: flexibility of the assumed distribution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from risk_engine.risk_models.common import empirical_var_cvar


@dataclass(frozen=True)
class MonteCarloResult:
    var: float
    cvar: float
    n_simulations: int
    seed: int
    distribution: str


def simulate_asset_returns(
    mu: np.ndarray,
    covariance: np.ndarray,
    n_simulations: int,
    seed: int,
    distribution: str = "normal",
    t_df: int = 5,
) -> np.ndarray:
    """Draw `n_simulations` correlated asset-return vectors. Shape (n_simulations, n_assets)."""
    if n_simulations <= 0:
        raise ValueError("n_simulations must be positive")
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    rng = np.random.default_rng(seed)

    if distribution == "normal":
        return rng.multivariate_normal(mu, cov, size=n_simulations)

    if distribution == "student_t":
        if t_df <= 2:
            raise ValueError("t_df must be > 2 for the covariance-matching scale correction")
        # Scale the covariance matrix so the resulting multivariate-t sample's covariance matches
        # `covariance`: for a standard multivariate-t with df, Cov(X) = scale * df/(df-2), so
        # scale = covariance * (df-2)/df.
        scale = cov * (t_df - 2) / t_df
        z = rng.multivariate_normal(np.zeros_like(mu), scale, size=n_simulations)
        chi2 = rng.chisquare(t_df, size=n_simulations)
        w = np.sqrt(t_df / chi2)
        return mu + z * w[:, None]

    raise ValueError(f"unknown distribution: {distribution!r}")


def monte_carlo_var_cvar(
    weights: np.ndarray,
    mu: np.ndarray,
    covariance: np.ndarray,
    confidence: float,
    n_simulations: int,
    seed: int,
    distribution: str = "normal",
    t_df: int = 5,
) -> MonteCarloResult:
    simulated_assets = simulate_asset_returns(mu, covariance, n_simulations, seed, distribution, t_df)
    simulated_portfolio_returns = simulated_assets @ np.asarray(weights, dtype=float)
    var, cvar = empirical_var_cvar(simulated_portfolio_returns, confidence)
    return MonteCarloResult(var=var, cvar=cvar, n_simulations=n_simulations, seed=seed, distribution=distribution)
