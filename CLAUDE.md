# CLAUDE.md — Portfolio Risk & Stress-Testing Engine

Persistent development rules for this repository. Read this before making changes.

## Project purpose

A portfolio-risk system whose core claim is not "here is a VaR number" but "here is a VaR
number, and here is the statistical proof it is calibrated." Three independent VaR/CVaR
methodologies (Historical, Parametric, Monte Carlo) are computed side-by-side and continuously
validated against realised outcomes via a leakage-safe rolling backtest (Kupiec + Christoffersen).
See `PROJECT_BLUEPRINT.md`'s extracted content in `docs/methodology.md` for the full spec this
was built from.

## Architecture principles

1. **Pure math, impure orchestration.** Everything in `risk_models/`, `validation/`,
   `portfolio/` (the calculation modules) must be pure functions: NumPy/pandas in, NumPy/pandas
   or dataclasses out, no DB calls, no network calls, no logging side effects. This is what makes
   "unit test against a known closed-form answer" tractable. The `api/` and `scheduler/` layers
   own orchestration (fetch data → call pure function → persist result).
2. **Scenarios are data, not code.** New stress scenarios (`stress/scenarios` table rows) must
   not require changes to `stress/engine.py`. It dispatches on `scenario.type`
   (`HISTORICAL_REPLAY` | `FACTOR_SHOCK`) — exactly two execution paths, no plugin framework.
3. **Every risk number must be reproducible.** A `risk_runs` row stores `config_id`,
   `as_of_date`, `data_snapshot_hash`, and `calculated_at`. Given a `risk_run_id`, re-running the
   stored config against data filtered to `< as_of_date` must reproduce the stored result exactly.
   This is asserted by a real test (`tests/integration/test_reproducibility.py`), not claimed in
   docs.
4. **Immutable data.** Rows in `prices` and `returns` are never updated in place. A correction is
   a new row with a later `ingested_at`; the old row stays. Historical risk runs reference data
   as of their calculation time and remain valid after later corrections.
5. **No look-ahead, structurally enforced.** The backtest/data-access layer takes an explicit
   `as_of_date` and the query layer must be physically incapable of returning rows with
   `return_date >= as_of_date`. This is not a convention to remember — it's enforced in the query
   function itself, and covered by `tests/anti_leakage/`.

## Technology stack (and why)

- **Python 3.10, NumPy/pandas/SciPy** — vectorised quant core.
- **FastAPI + Pydantic v2** — API layer; Pydantic schemas double as the OpenAPI spec source.
- **PostgreSQL + SQLAlchemy 2.0 + Alembic** — relational integrity between
  portfolios/positions/risk_runs/results matters (a VaR result must trace back to an exact
  portfolio composition and data snapshot); a document store would make that traceability a
  documentation promise instead of a schema constraint.
- **Local dev DB**: a real PostgreSQL 17 instance installed via winget (this sandbox has no
  Docker). Role `risk_engine`, databases `portfolio_risk_engine` (dev) and
  `portfolio_risk_engine_test` (test). Credentials in `.env` (gitignored); see `.env.example`.
- **cron, not Celery/Redis** — one daily batch job over ~20 assets and tens of portfolios does
  not need a task queue. Documented explicitly so it reads as a considered decision, not an
  omission. Revisit only if scaling to many portfolios needing parallel processing, or
  on-demand long-running jobs triggered from the API.
- **HTML-first reporting** (Jinja2 + matplotlib/embedded charts). PDF export via WeasyPrint was
  evaluated and **dropped**: WeasyPrint requires the GTK/Cairo/Pango native stack, which is not
  cleanly installable on Windows without a system package manager. Documented in
  `docs/KNOWN_LIMITATIONS.md` rather than faked.
- **ruff + mypy** for lint/type-check. **pytest** for everything else.

## Quantitative correctness requirements

- Every formula implemented must match the mathematical spec in `docs/QUANTITATIVE_METHODOLOGY.md`
  exactly — including sign convention (VaR/CVaR are reported as **positive loss numbers**),
  quantile convention, and log-return vs simple-return usage.
- **Log returns for risk models** (`r_t = ln(P_t / P_{t-1})`), **simple returns for P&L/portfolio
  value reporting**. Do not conflate these — it's a common, subtle bug. Portfolio log-return is
  computed as the linear approximation `R_p,t ≈ w^T r_t` (standard for daily horizons; note this
  is an approximation, not exact, since log-returns aren't exactly linear in weights — simple
  returns are exactly linear).
- Every VaR/CVaR function needs a unit test against a **known closed-form case** (e.g. a
  single-asset normal series with known μ, σ has an analytically known parametric VaR — assert
  the function reproduces it to numerical tolerance). This is the single highest-value test
  category in the project.
- Monte Carlo VaR under a multivariate-normal assumption must be shown to **converge to the
  parametric closed-form answer** as N grows — this is both a correctness test and a research
  artifact (`notebooks/01_var_model_comparison.ipynb`).
- Invariants to keep passing at all times: `CVaR_α ≥ VaR_α` (always, by definition), and
  `Σ ComponentVaR_i ≈ VaR_portfolio` (component VaR is additive by construction under the
  parametric closed form).
- Random seeds for Monte Carlo are always explicit and stored per run — never implicit global
  RNG state.

## Testing requirements

Test pyramid — keep it real, don't invert it:
- **Unit (math)**: fast, no I/O, closed-form comparisons. Majority of the suite.
- **Statistical**: convergence checks, synthetic-data distributional checks.
- **Anti-leakage**: dedicated tests asserting a forecast for date `t` is unchanged by mutating
  data at or after `t`. Required for any function touching the backtest data-access layer.
- **Integration**: real Postgres (`portfolio_risk_engine_test` DB), full pipeline through the DB.
- **E2E**: a handful of full API-workflow tests (create portfolio → positions → risk run → fetch).
- **Regression/golden**: fixed synthetic dataset with stored reference output; any output change
  needs an explicit, reviewed reason.

Run before considering any phase done:
```
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m mypy src
```

## Security rules

- No hardcoded credentials anywhere in source. Config via `pydantic-settings` reading `.env`.
  `.env` is gitignored; `.env.example` documents required keys with placeholder values.
- All API write endpoints require the `X-API-Key` header (checked via a FastAPI dependency).
  Full multi-user auth/RBAC is explicitly out of scope for this project (documented in
  `docs/SECURITY.md`), not half-implemented.
- All DB access goes through SQLAlchemy parameterised queries/ORM — never raw string-formatted
  SQL.
- Pydantic models validate all API input before it reaches business logic.

## Data handling rules

- Adjusted close only (dividend/split-adjusted). Never raw close for return construction.
- Missing observations are **dropped after alignment to the intersection of valid trading
  days**, never forward-filled (forward-fill manufactures a zero-return day that didn't happen).
- Outliers (large single-day moves) are **flagged, never silently removed** — a real 12% crash
  day is exactly the tail-risk observation the model must not lose.
- Every data-quality issue that gets flagged is logged (structured JSON log), not silently
  dropped.

## Git conventions

- Commit at the end of each completed phase (working tests, not mid-refactor).
- Commit messages: imperative mood, one line summary, scope prefix where useful
  (`data:`, `risk_models:`, `api:`, `docs:`, etc).
- No `--no-verify`, no force-push, no history rewriting on `main`.

## Documentation requirements

- Every mathematical component documented in `docs/QUANTITATIVE_METHODOLOGY.md` with: formula,
  assumptions, known limitations.
- `docs/KNOWN_LIMITATIONS.md` must stay honest and current — survivorship bias in the fixed
  15–20 asset universe, single-currency/long-only/no-derivatives scope, equity-only rate-shock
  proxy, no WeasyPrint/PDF export, no Docker/e2e-deploy verification in this dev sandbox, etc.
- Never invent a metric (Sharpe ratio, VaR, p-value, breach rate, stress loss...). If an
  experiment hasn't been run, the notebook/doc says so explicitly — it does not show a plausible
  fabricated number.

## Commands

```powershell
# Activate venv (or just call .venv\Scripts\python.exe / .venv\Scripts\pip.exe directly)
.venv\Scripts\Activate.ps1

# Run the API (dashboard is served at /dashboard/ by the same app -- see api/main.py)
.venv\Scripts\python -m uvicorn risk_engine.api.main:app --reload --app-dir src
# Then open http://127.0.0.1:8000/dashboard/ and http://127.0.0.1:8000/docs

# Run tests
.venv\Scripts\python -m pytest                     # full suite
.venv\Scripts\python -m pytest tests\unit -q        # fast loop
.venv\Scripts\python -m pytest -m "not integration"  # skip DB-dependent tests

# Lint / type-check
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m ruff format src tests
.venv\Scripts\python -m mypy src

# DB migrations
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic revision --autogenerate -m "message"

# Daily pipeline (manual trigger, same entrypoint cron calls)
.venv\Scripts\python -m risk_engine.scheduler.run_daily_pipeline
```

## Important architectural decisions (log)

| Decision | Reason |
|---|---|
| `src/risk_engine/` package instead of bare `src/data`, `src/risk_models` | Blueprint's diagram shows top-level modules directly under `src/`; nesting under one package avoids `data`/`api` etc. becoming ambiguous top-level import names. |
| Component VaR (parametric closed form) as primary decomposition; Incremental VaR as on-demand endpoint only | Component VaR is additive and cheap; Incremental VaR is O(n) re-computations and is a "what-if" query, not a standing metric. |
| Local PostgreSQL via winget instead of Docker | No Docker available in this dev sandbox. Docker Compose is still the documented/intended deployment path; it has not been executed end-to-end here. |
| SQLite dropped in favour of real local Postgres for dev+test | Keeps JSONB scenario storage, Postgres-specific types, and Alembic migrations tested against the real target engine rather than a divergent dialect. |
| No WeasyPrint/PDF export | GTK/Cairo/Pango native stack isn't cleanly installable on Windows in this environment. HTML report is the complete, real deliverable. |
