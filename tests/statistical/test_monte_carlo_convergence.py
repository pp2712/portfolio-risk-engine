"""Monte Carlo VaR, under a multivariate-normal assumption matching parametric VaR's (mu, Sigma),
must converge to the parametric closed-form answer as N grows. This is both a correctness check
(if the simulator were wrong, it would converge to the WRONG number, consistently) and a research
artifact reproduced in notebooks/01_var_model_comparison.ipynb (Experiment 3).
"""

from __future__ import annotations

import numpy as np
import pytest

from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar
from risk_engine.risk_models.parametric import parametric_var_cvar, portfolio_variance


@pytest.mark.slow
def test_monte_carlo_var_converges_to_parametric_as_n_grows():
    weights = np.array([0.4, 0.35, 0.25])
    mu = np.array([0.0004, 0.0002, -0.0001])
    cov = np.array(
        [
            [0.00030, 0.00008, 0.00005],
            [0.00008, 0.00025, 0.00004],
            [0.00005, 0.00004, 0.00040],
        ]
    )
    confidence = 0.95
    mu_p = float(weights @ mu)
    sigma_p = float(np.sqrt(portfolio_variance(weights, cov)))
    parametric_var, parametric_cvar = parametric_var_cvar(mu_p, sigma_p, confidence)

    sample_sizes = [200, 2_000, 20_000, 200_000]
    var_errors = []
    for n in sample_sizes:
        result = monte_carlo_var_cvar(weights, mu, cov, confidence, n_simulations=n, seed=2024)
        var_errors.append(abs(result.var - parametric_var))

    # Convergence, not monotonicity at every single step (MC has sampling noise) -- assert the
    # error at the largest N is materially smaller than at the smallest N.
    assert var_errors[-1] < var_errors[0] / 3, (
        f"MC VaR error did not shrink with N: errors={var_errors} "
        f"(parametric VaR={parametric_var:.6f})"
    )
    # And the largest-N estimate should be tight in absolute terms.
    assert var_errors[-1] < 0.001, f"MC VaR at N={sample_sizes[-1]} still {var_errors[-1]:.6f} away from parametric"


@pytest.mark.slow
def test_monte_carlo_estimator_variance_shrinks_with_n():
    """Run several independent seeds at each N and check the spread of VaR estimates narrows."""
    weights = np.array([0.6, 0.4])
    mu = np.array([0.0, 0.0])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0009]])
    confidence = 0.95

    def spread(n_simulations: int) -> float:
        vars_ = [
            monte_carlo_var_cvar(weights, mu, cov, confidence, n_simulations, seed=s).var
            for s in range(10)
        ]
        return float(np.std(vars_))

    spread_small_n = spread(200)
    spread_large_n = spread(20_000)
    assert spread_large_n < spread_small_n / 2
