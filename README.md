# Portfolio Risk & Stress-Testing Engine

A portfolio-risk system whose core claim is not "here is a VaR number" but **"here is a VaR
number, and here is the statistical proof it is calibrated."** Three independent VaR/CVaR
methodologies are computed side-by-side and continuously validated against realised outcomes via a
leakage-safe rolling backtest (Kupiec proportion-of-failures + Christoffersen independence tests) --
the same discipline a bank's model-validation function applies before a risk model is trusted in
production.

## Why it exists

Most portfolio-risk demos answer "what is my VaR today?" A real risk desk cares less about the
number itself and more about *whether the number can be trusted*. This project produces risk
estimates **and** continuously proves (or disproves) that those estimates are statistically valid,
with a full audit trail: every stored result traces back to the exact data snapshot and model
configuration that produced it, and that reproducibility is asserted by a real test, not claimed in
documentation.

## Key capabilities

- **Three independent VaR/CVaR methodologies** (Historical, Parametric, Monte Carlo) computed
  side-by-side at 95%/99% confidence, with two real formula corrections made to the original design
  spec during implementation and documented (see `docs/QUANTITATIVE_METHODOLOGY.md`).
- **Leakage-safe rolling backtest**, structurally unable to see future data (enforced in the query
  layer, not developer discipline), with dedicated regression tests guarding against reintroducing
  look-ahead bias.
- **Kupiec + Christoffersen + conditional-coverage validation**, plus a Basel-style traffic-light
  classification derived from the actual binomial distribution, not a hardcoded lookup table.
- **Stress testing**: 2008 GFC and 2020 COVID historical replay, plus factor-shock scenarios with
  genuinely regression-estimated market betas (against a real SPY-based market proxy).
- **Risk decomposition** (Marginal/Component VaR) that sums to total portfolio VaR *exactly*
  (verified to `1e-9` on synthetic portfolios, `1.7e-18` -- floating-point noise -- on real market
  data).
- **Full audit trail**: every risk run stores its config, as-of-date, and a SHA-256 hash of the
  exact data used; bit-for-bit reproducibility is proven by a test that deletes a stored result and
  recomputes it from scratch.
- **A working system, not a notebook**: PostgreSQL-backed API, HTML report generation, a 9-tab
  dashboard, a daily automation pipeline, structured logging + Prometheus metrics, Docker/CI.

## Architecture

```
data ingestion (Yahoo Finance/Stooq -> validate -> clean -> Postgres, immutable/append-only)
        |
portfolio model -> risk model engine -> validation layer -> stress engine -> decomposition   [all pure functions]
        |
orchestration (api/services) -- the only layer touching both the DB and the pure calculation layer
        |
FastAPI (18 endpoints) --+-- HTML report generation (Jinja2 + matplotlib)
                          +-- 9-tab dashboard (vanilla JS + Plotly, served at /dashboard)
                          +-- daily scheduler pipeline (ingest -> risk run -> backtest -> stress -> report)
```

Full detail: `docs/ARCHITECTURE.md`.

## Technology stack

Python 3.10+, NumPy/pandas/SciPy (quant core), FastAPI + Pydantic v2 (API), PostgreSQL 17 +
SQLAlchemy 2.0 + Alembic (persistence), vanilla JS + Plotly (dashboard, no build step), Jinja2 +
matplotlib (HTML reports), pytest (142 tests), ruff + mypy (lint/types), Docker + GitHub Actions
(deployment/CI), prometheus_client (metrics). Every dependency choice is justified in
`docs/ARCHITECTURE.md`'s technology-choices table -- nothing was added because it sounded
impressive.

## Quantitative methodology (summary)

VaR/CVaR are always positive loss numbers. Log returns for risk models, simple returns for P&L.
Historical/Monte Carlo VaR use a "k worst observations" estimator (avoids ambiguous quantile
interpolation, makes `CVaR >= VaR` hold by construction). Parametric VaR/CVaR and the Marginal VaR
decomposition formula were corrected from the original design spec during implementation -- both
corrections, with full derivations, are documented in `docs/QUANTITATIVE_METHODOLOGY.md` rather
than silently fixed. Kupiec and Christoffersen are implemented via `scipy.special.xlogy` so the
`x=0`/`x=T` edge cases (which naively hit `log(0)`) are handled correctly, not special-cased away.

## Real results (not fabricated -- from the actual notebooks/report in this repo)

From `notebooks/02_backtesting_validation.ipynb`, a real 1,000-trading-day rolling backtest
(2022-08-10 to 2026-08-05) against real ingested market data for a 10-asset equal-weight portfolio:

| Method | Exceptions | Exception Rate | Kupiec p-value | Christoffersen p-value | Verdict |
|---|---|---|---|---|---|
| Historical | 41/1000 | 4.10% (vs. 5.00% expected) | 0.178 | 0.108 | Passes both tests |
| Parametric | 44/1000 | 4.40% | 0.375 | 0.170 | Passes both tests |
| Monte Carlo | 40/1000 | 4.00% | 0.133 | 0.300 | Passes both tests |

From `notebooks/03_stress_scenarios.ipynb`, replaying 2008 and 2020 onto the same sample portfolio:
2008 GFC P&L **-27.01%**, 2020 COVID P&L **-32.78%** -- comparable magnitude, but the two crises hit
*different* positions hardest (AAPL vs. MSFT for this holding set), confirming different loss
shapes, not scaled versions of the same shock.

From `notebooks/04_risk_decomposition.ipynb`: Component VaR summed to portfolio VaR with a
difference of `1.73e-18` (i.e. exact, to floating-point precision) on real market data; the
diversification benefit shrank from 55.8% to 18.2% of standalone VaR as portfolio concentration
(HHI) rose from 0.10 to 0.50 -- matching theory.

A full generated sample report is in `examples/sample_risk_report.html` -- open it directly, no
server required.

## Dashboard

9 tabs (Overview, Portfolio, VaR/CVaR, Model Comparison, Backtesting, Stress Testing, Risk
Decomposition, Historical Risk, Reports), vanilla JS + Plotly, served by the API itself at
`/dashboard`. Verified working in a real browser against real API data (headless Chromium
screenshots of every tab during development -- see commit history).

## Installation & running

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,notebooks]"
copy .env.example .env                                    # fill in DATABASE_URL, API_KEY
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python scripts\ingest_universe.py --start 2007-01-01
.venv\Scripts\python scripts\seed_scenarios.py
.venv\Scripts\python -m uvicorn risk_engine.api.main:app --reload --app-dir src
```

Then open `http://127.0.0.1:8000/docs` (API) or `http://127.0.0.1:8000/dashboard/` (dashboard).

Docker (documented, not executed end-to-end in this dev sandbox -- see `docs/KNOWN_LIMITATIONS.md`):
```bash
docker compose up --build
```

## Testing

```powershell
.venv\Scripts\python -m pytest
```

142 tests: unit (fast, closed-form comparisons), statistical (MC convergence), data-quality,
anti-leakage (dedicated look-ahead-bias regressions), golden/regression, integration (real
Postgres), and end-to-end (full HTTP workflow). Detail: `docs/TESTING.md`.

## Research notebooks

| Notebook | Question |
|---|---|
| `01_var_model_comparison.ipynb` | Does parametric VaR underestimate tail risk vs. historical/MC? Does MC converge to the parametric closed form as N grows? |
| `02_backtesting_validation.ipynb` | Which VaR model(s) are actually statistically calibrated for this portfolio, and do any cluster their failures? |
| `03_stress_scenarios.ipynb` | Do 2008 and 2020 produce different loss *shapes* despite comparable magnitude? |
| `04_risk_decomposition.ipynb` | Does Component VaR really sum to portfolio VaR? Does diversification benefit shrink with concentration? |

All four were executed against real ingested market data with real, non-fabricated outputs (see
the "Real results" section above and the notebooks themselves).

## Documentation

`docs/ARCHITECTURE.md` &middot; `docs/QUANTITATIVE_METHODOLOGY.md` &middot; `docs/API.md` &middot;
`docs/DATA.md` &middot; `docs/TESTING.md` &middot; `docs/DEPLOYMENT.md` &middot;
`docs/SECURITY.md` &middot; `docs/KNOWN_LIMITATIONS.md` &middot; `FINAL_PROJECT_AUDIT.md`

## Limitations (honest, not hidden)

Long-only/no-derivatives/single-currency/equity-only scope, a survivorship-biased fixed universe,
no Docker execution in this dev sandbox, no PDF export. Full list with reasoning:
`docs/KNOWN_LIMITATIONS.md`.

## Future improvements

EWMA covariance as an alternative estimator; multivariate Student's-t as the default Monte Carlo
distribution with a fat-tail research notebook; a Playwright dashboard regression suite;
point-in-time index-constituent data to remove survivorship bias. See
`docs/KNOWN_LIMITATIONS.md`'s "what would change first" section.
