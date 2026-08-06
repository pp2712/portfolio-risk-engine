# Quantitative Methodology

The complete mathematical specification for every risk model, validation test, and decomposition
in this project, including two formula corrections made to the original design spec during
implementation (documented here rather than silently fixed).

## Conventions

- **VaR and CVaR are always reported as positive loss numbers.** A 95% VaR of 0.03 means "a 3% loss
  is the threshold not expected to be exceeded 95% of the time."
- **Log returns for risk models** (`r_t = ln(P_t / P_{t-1})`) -- time-additive, approximately
  normal for daily equity data. **Simple returns for P&L / portfolio-value reporting**
  (`portfolio_value_t / portfolio_value_{t-1} - 1`) -- the economically correct, exactly-compounding
  quantity. Never conflate the two.
- **Portfolio log-return** is a linear approximation: `R_p,t ~= w^T r_t`. This is standard for
  daily horizons but is an approximation -- portfolio log-returns are not exactly linear in asset
  log-returns (simple returns are exactly linear; log-returns approximately so at daily horizons).

## 1. Historical VaR / CVaR (`risk_models/historical.py`)

Distribution-free empirical estimator. Given a lookback window of `T` portfolio returns and target
confidence `alpha`:

```
k = ceil((1 - alpha) * T), floored at 1
sorted_returns = ascending sort of the T returns
VaR_alpha  = -sorted_returns[k-1]          (the k-th worst observation)
CVaR_alpha = -mean(sorted_returns[:k])     (average of the k worst observations)
```

This "k worst observations" estimator was chosen over `numpy.quantile`'s interpolation to avoid an
ambiguous empirical quantile and to make `CVaR >= VaR` hold **by construction**, not by luck of the
interpolation scheme.

**Advantages:** captures actual fat tails/skew, no distributional assumption.
**Limitations:** entirely backward-looking; at 250 observations / 95% confidence, VaR rests on ~12
tail observations (high estimator variance).

## 2. Parametric (Variance-Covariance) VaR / CVaR (`risk_models/parametric.py`)

Assumes portfolio returns `R_p ~ N(mu_p, sigma_p^2)`, with `sigma_p^2 = w^T Sigma w` (portfolio
variance from the asset covariance matrix and weight vector).

```
z_alpha    = Phi^-1(alpha)                          (positive convention, e.g. z_0.95 = 1.645)
VaR_alpha  = z_alpha * sigma_p - mu_p
CVaR_alpha = sigma_p * phi(z_alpha) / (1 - alpha) - mu_p     (phi = standard normal PDF)
```

### Correction #1: VaR sign convention

The original spec described `z_alpha` as "the standard normal quantile, e.g. 1.645 for 95%"
(implying the positive convention) but wrote the formula as `VaR = -(mu + z_alpha * sigma)`, which
only produces a positive VaR if `z_alpha` is **negative** (`z_alpha = Phi^-1(1-alpha) = -1.645` at
95%). Taking the stated positive `z_alpha = 1.645` literally into that formula produces a negative
VaR for a typical near-zero-mean portfolio -- a real sign error if implemented as written. Both
forms are mathematically equivalent once the sign of `z_alpha` is fixed consistently; this project
standardises on the positive-`z` convention (`VaR = z_alpha * sigma_p - mu_p`) as the less
error-prone of the two to implement and read.

### Correction #2: CVaR formula

The original spec stated the parametric CVaR closed form as
`mu + sigma * phi(z_alpha) / (1 - alpha)` (mu **added**). Re-deriving from the definition
`CVaR_alpha = -E[R | R <= q_{1-alpha}]` for `R ~ N(mu, sigma^2)` gives
`CVaR_alpha = sigma * phi(z_alpha) / (1 - alpha) - mu` (mu **subtracted**). The `+mu` version is
only correct when `mu = 0`; for nonzero `mu` it is off by `2*mu` from the derived value and can
violate the `CVaR >= VaR` invariant for sufficiently negative `mu`. Implemented with the corrected
sign; `tests/unit/test_parametric_var.py::test_cvar_greater_equal_var_over_random_params` asserts
the invariant across randomised mu/sigma including negative mu.

**Advantages:** closed-form, fast, decomposes cleanly into Component/Marginal VaR.
**Limitations:** normality underestimates tail risk for real equity returns (excess kurtosis,
negative skew) -- demonstrated in `notebooks/01_var_model_comparison.ipynb`.

## 3. Monte Carlo VaR / CVaR (`risk_models/monte_carlo.py`)

Simulate `N` correlated asset-return draws (`numpy.random.default_rng(seed).multivariate_normal`),
map to portfolio returns via the weight vector (no per-instrument revaluation needed for a
long-only linear portfolio), then apply the same "k worst observations" estimator as Historical
VaR/CVaR to the simulated sample.

- **Reproducibility:** every simulation takes an explicit integer seed; never implicit global RNG
  state. The seed and N are stored per risk run.
- **Distribution:** defaults to multivariate normal (same `mu, Sigma` as parametric) so the
  MC-vs-parametric convergence check is a genuine "does the simulator implement the model
  correctly" test (`tests/statistical/test_monte_carlo_convergence.py`,
  `notebooks/01_var_model_comparison.ipynb` Experiment 3). A multivariate Student's-t mode is also
  implemented (`distribution="student_t"`), with the scale matrix corrected by `(df-2)/df` so the
  realised covariance matches the target `Sigma` despite the fat-tailed draw.

## 4. Risk Decomposition (`portfolio/decomposition.py`)

```
MarginalVaR_i  = z_alpha * (Sigma @ w)_i / sigma_p - mu_i
ComponentVaR_i = w_i * MarginalVaR_i
invariant: sum_i(ComponentVaR_i) == VaR_p            (exact, verified to 1e-9 in tests)
```

### Correction #3: Marginal VaR formula (additivity)

The original spec gave `MarginalVaR_i = z_alpha * (Sigma w)_i / sigma_p`, omitting the per-asset
mean term `mu_i`. Given this project's `VaR_p = z_alpha * sigma_p - mu_p`, differentiating the
**full** expression w.r.t. `w_i` requires the `-mu_i` term. Dropping it is fine only when
`mu_p ~ 0`; keeping it is what makes `sum_i(w_i * MarginalVaR_i) == VaR_p` hold **exactly** (proven
via Euler's theorem for the homogeneous-degree-1 `sigma_p` term, plus exact linearity of the mean
term) rather than approximately. Verified across randomised 2-20 asset portfolios in
`tests/unit/test_decomposition.py::test_component_var_sums_to_portfolio_var_exactly` (all pass to
`abs=1e-9`), and against real market data in `notebooks/04_risk_decomposition.ipynb` (difference
`1.73e-18`, i.e. floating-point noise).

Standalone VaR (each position priced in isolation, ignoring correlation) is intentionally **not**
implemented as a decomposition method -- it overstates total risk and is not additive. It is used
only for the diversification-benefit metric (Section 6).

## 5. Kupiec Proportion-of-Failures Test (`validation/kupiec.py`)

- **H0:** observed exception rate equals the model's stated exception probability
  `p = 1 - confidence`.
- **H1:** the true exception rate differs (two-sided).
- **Statistic:** `LR_POF = -2 ln[ (1-p)^(T-x) p^x / ((1-x/T)^(T-x) (x/T)^x) ]`, `T` = observations,
  `x` = exceptions. Under H0, `LR_POF ~ chi-squared(1)`.
- Implemented via `scipy.special.xlogy` (`x*log(y)`, defined as 0 when `x==0` regardless of `y`) so
  the `x=0` and `x=T` edge cases -- which naively hit `log(0)`/`0^0` -- are handled correctly.
- **Worked example** (matches the design spec exactly): 250 observations, 95% VaR, 20 exceptions ->
  `LR_POF ~= 4.04`, exceeds the chi-squared(1) 5% critical value of 3.84 -> reject H0, model
  under-covers risk. Reproduced in `tests/unit/test_kupiec.py`.

## 6. Christoffersen Independence Test (`validation/christoffersen.py`)

Kupiec alone cannot distinguish evenly-spread exceptions from clustered exceptions. Build a
first-order Markov transition matrix over the binary exception series:

```
n00, n01, n10, n11 = transition counts (no-exception->no-exception, no-exception->exception, ...)
pi01 = n01/(n00+n01), pi11 = n11/(n10+n11), pi = (n01+n11)/T
LR_ind = -2 ln[ (1-pi)^(n00+n10) pi^(n01+n11) / ((1-pi01)^n00 pi01^n01 (1-pi11)^n10 pi11^n11) ]
```

Under H0 (independence, `pi01 == pi11`), `LR_ind ~ chi-squared(1)`. Not applicable (returns
`applicable=False`) when fewer than 2 exceptions occurred.

**Combined conditional coverage:** `LR_cc = LR_POF + LR_ind ~ chi-squared(2)` -- tests coverage and
independence jointly, the criterion regulators actually use.

## 7. Traffic-Light Zone Classification (`validation/traffic_light.py`)

Rather than hardcoding the classic Basel table (built specifically for 99%/250-day: green 0-4,
amber 5-9, red 10+), this implements the underlying methodology directly so it generalises to any
confidence/window length: classify by where the observed exception count falls in the cumulative
`Binomial(n_observations, 1-confidence)` distribution under H0 (green: cumulative probability <
95th percentile; amber: 95th-99.99th; red: >= 99.99th). Verified to reproduce the canonical
99%/250-day boundaries exactly in `tests/unit/test_traffic_light.py`.

## 8. Stress Testing (`stress/engine.py`, `stress/scenarios.py`, `stress/factor_model.py`)

- **Historical replay:** apply realised simple returns from a historical window (e.g. 2008 GFC:
  Sep-Nov 2008; 2020 COVID: Feb-Mar 2020) directly to today's portfolio weights. Assets with no
  price history in the window are excluded and reported (`excluded_assets`), not silently assumed
  flat.
- **Factor shock:** `asset_return_i = sum_f(beta_i,f * shock_f)`. The `equity_market` factor's
  betas are genuinely regression-estimated (OLS against SPY, ingested purely as a market-factor
  proxy, never an investable holding). Other factors use direct sector-membership indicators, since
  no in-scope return series exists to regress against them (see `docs/KNOWN_LIMITATIONS.md`).

## 9. Reproducibility (`db/snapshot_hash.py`, `api/services/risk_run_service.py`)

Every `risk_runs` row stores `config_id` (model type, confidence levels, lookback, MC seed),
`as_of_date`, a `data_snapshot_hash` (SHA-256 of the sorted ticker list, as-of date, and the full
return-matrix values used), and `calculated_at`. Re-fetching the same immutable data and re-running
with the stored config reproduces the stored result bit-for-bit -- proven, not claimed, in
`tests/integration/test_reproducibility.py` by deleting a risk run's rows and recomputing from
scratch.
