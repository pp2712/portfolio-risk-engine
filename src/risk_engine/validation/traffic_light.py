"""Basel-style traffic-light exception classification.

Rather than hardcoding the classic Basel table (built specifically for 99% 1-day VaR over a
250-day window: green 0-4, amber 5-9, red 10+ exceptions), this implements the actual underlying
methodology so it generalises to any confidence level / window length: classify by where the
observed exception count falls in the cumulative Binomial(n_observations, p) distribution under
H0, where p = 1 - confidence.

    green:  cumulative probability of <= n_exceptions < 95th percentile  (plausible under H0)
    amber:  95th percentile <= cumulative probability < 99.99th percentile
    red:    cumulative probability >= 99.99th percentile (essentially impossible under H0)

For the canonical 99%/250-day case this reproduces the standard Basel boundaries (green through 4,
amber 5-9, red 10+).
"""

from __future__ import annotations

from scipy import stats


def traffic_light_zone(n_observations: int, n_exceptions: int, confidence: float) -> str:
    if n_observations <= 0:
        raise ValueError("n_observations must be positive")
    if not 0 <= n_exceptions <= n_observations:
        raise ValueError("n_exceptions must be between 0 and n_observations")
    p = 1.0 - confidence
    cumulative_prob = float(stats.binom.cdf(n_exceptions, n_observations, p))

    if cumulative_prob < 0.95:
        return "green"
    if cumulative_prob < 0.9999:
        return "amber"
    return "red"
