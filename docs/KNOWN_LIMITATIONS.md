# Known Limitations

An honest, explicit list of every scope simplification in this project. Each of these is a
conscious decision, not an oversight -- the reasoning is included so it can be evaluated on its
merits. See also `CLAUDE.md`'s "Important architectural decisions" table.

## Scope boundaries

- **Long-only, no leverage, no derivatives.** Positions are quantity >= 0 (enforced by the API's
  Pydantic schema). Short positions would need sign-consistent weight/VaR handling that changes
  interpretation, not just a sign flip. Derivatives have non-linear P&L (delta/gamma effects)
  requiring either full revaluation or a Taylor approximation -- a substantial separate project.
- **Single currency (USD).** No FX translation risk. All 20 universe assets plus the SPY market
  proxy are USD-denominated US-listed securities.
- **Equity + sector-ETF only, no fixed income.** No yield curve, no duration/convexity. The "Rate
  Shock" stress scenario is an explicitly documented equity-only proxy (shocking rate-sensitive
  financial-sector exposure), not a duration-based bond calculation.
- **No intraday data.** Daily frequency only.

## Data limitations

- **Survivorship bias.** The fixed 20-asset universe (`data/universe.py`) consists of large-cap
  names that are all still liquid and listed today. Properly correcting this requires point-in-time
  index-constituent history, which is not freely available. Accepted for this project's scope.
- **Vendor data conventions.** Yahoo Finance's `Close` field (with `auto_adjust=False`) is already
  split-adjusted but NOT dividend-adjusted; `Adj Close` is both. Neither is a truly "as traded on
  the day" raw price -- yfinance does not expose that. See `db/models.py::Price` docstring and
  `tests/data_quality/test_corporate_actions.py`.
- **META (Meta Platforms) has no data before its 2012-05-18 IPO.** The 2008 GFC historical-replay
  scenario excludes it from that specific replay (see `stress/engine.py`'s `excluded_assets`
  handling) rather than silently treating it as flat or dropping it from weight normalisation.
- **Stooq fallback has no adjusted-close field**; `adj_close` falls back to raw close for that
  vendor, flagged via the `source` column so it's traceable, not silently wrong.

## Modelling limitations

- **Historical VaR at 250 observations / 95% confidence rests on ~12 tail observations** --
  high estimator variance, a known and documented weakness of the methodology itself (see
  `risk_models/historical.py`).
- **Parametric VaR assumes normality**, which underestimates tail risk for real equity return
  distributions (excess kurtosis, negative skew) -- demonstrated, not just claimed, in
  `notebooks/01_var_model_comparison.ipynb`.
- **Monte Carlo defaults to a multivariate-normal draw** (same limitation as parametric, by
  construction, when used for the convergence check). A multivariate Student's-t mode exists
  (`risk_models/monte_carlo.py::simulate_asset_returns(distribution="student_t")`) but is not the
  default and is not wired into the risk-run orchestration by default.
- **Covariance estimated via equal-weighted sample covariance** over the lookback window, not
  EWMA. EWMA would react faster to volatility regime changes; documented as a reasonable
  alternative, not implemented.
- **Component VaR decomposition uses the parametric closed form** at a single "primary" confidence
  level per risk run (the `risk_decomposition` table has no confidence_level column). Incremental
  VaR (exact P&L from fully removing a position) is not implemented as a standing metric.
- **Factor-shock betas**: only the `equity_market` factor is regression-estimated (against SPY).
  Other named factors (e.g. `rate_sensitive_financials`) use direct sector-membership indicators
  (1.0/0.0), not a regression, because there is no in-scope tradeable return series to regress
  against for those factors.

## Engineering limitations

- **No Docker/container testing in this development environment.** This sandbox has no Docker
  daemon available. `Dockerfile` and `docker-compose.yml` are written to the same standard as the
  rest of the codebase and validated for YAML/Dockerfile syntax, but `docker compose up --build`
  has not been executed end-to-end locally. The GitHub Actions `docker-build` CI job does build the
  image on every push, which is the actual verification point.
- **No PDF report export.** WeasyPrint (the natural HTML-to-PDF choice) requires the GTK/Cairo/
  Pango native stack, which is not cleanly installable on Windows in this environment without a
  system package manager. The HTML report is the complete, real deliverable; PDF was evaluated and
  dropped rather than faked.
- **No multi-user auth/RBAC.** A single shared `X-API-Key` header gates all write endpoints. This
  is appropriate for a portfolio/demo project, explicitly not for an institution handling real
  client capital -- see `docs/SECURITY.md`.
- **Cron-based scheduling, not a task queue.** Appropriate at this project's scale (one portfolio
  universe, no need for horizontal worker scaling); documented as a scale-dependent choice in
  `CLAUDE.md`, not an oversight.
- **Dashboard has no automated browser/UI test suite.** It was manually verified in a real browser
  (headless Chromium screenshots of every tab, against real API data) during development, but there
  is no Playwright/Selenium regression suite guarding against future UI breakage.

## What would change first with more time

1. EWMA covariance as a documented alternative estimator.
2. Multivariate Student's-t as the default Monte Carlo distribution, with a fat-tail vs. normal
   comparison as a fifth research notebook.
3. A Playwright-based dashboard smoke-test suite.
4. Point-in-time index constituent data to remove survivorship bias from the universe.
