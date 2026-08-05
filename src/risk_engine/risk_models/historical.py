"""Historical (empirical) VaR / CVaR -- distribution-free, no normality assumption.

VaR_alpha = -Q_{1-alpha}(R_1, ..., R_T) via the "k worst observations" estimator (see common.py).

Advantages: captures actual fat tails/skew in the data, no distributional assumption.
Limitations: entirely backward-looking (a lookback window with no crisis in it will
systematically understate risk); discrete jumps as extreme historical observations enter/exit the
rolling window; at 250 observations and 95% confidence, VaR rests on ~12 tail observations --
high estimator variance, worth stating explicitly (see docs/QUANTITATIVE_METHODOLOGY.md).
"""

from __future__ import annotations

import numpy as np

from risk_engine.risk_models.common import empirical_var_cvar


def historical_var(returns: np.ndarray, confidence: float) -> float:
    var, _ = empirical_var_cvar(returns, confidence)
    return var


def historical_cvar(returns: np.ndarray, confidence: float) -> float:
    _, cvar = empirical_var_cvar(returns, confidence)
    return cvar


def historical_var_cvar(returns: np.ndarray, confidence: float) -> tuple[float, float]:
    """Convenience: both in one call (avoids sorting the array twice)."""
    return empirical_var_cvar(returns, confidence)
