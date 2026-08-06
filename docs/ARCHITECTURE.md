# Architecture

## Layered design

```
data ingestion (vendors -> validation -> returns -> Postgres)
        |
portfolio model (positions -> weights -> portfolio returns)   [pure functions]
        |
risk model engine (historical / parametric / monte_carlo VaR+CVaR)   [pure functions]
        |
validation layer (rolling backtest -> Kupiec/Christoffersen/traffic-light)   [pure functions]
        |
stress engine (historical replay / factor shock)   [pure functions]
        |
risk decomposition (marginal/component VaR)   [pure functions]
        |
orchestration (api/services/*.py) -- the ONLY layer that touches both the DB and the pure functions
        |
API (FastAPI routers -- thin, delegate everything to orchestration)
        |
reporting (Jinja2 HTML + matplotlib charts) & dashboard (static JS, same API)
        |
scheduler (daily pipeline: ingest -> risk run -> backtest -> stress -> report, all via the same
           orchestration services the API uses -- no separate code path)
```

## The one rule that matters most

**Pure math, impure orchestration.** Everything in `risk_models/`, `validation/`, `portfolio/`,
and `stress/` is pure: NumPy/pandas/dataclasses in and out, no DB calls, no network calls, no
logging side effects. This is what makes "unit test against a known closed-form answer" tractable,
and it's why the same rolling-backtest harness (`validation/backtest.py`) can drive Historical,
Parametric, and Monte Carlo VaR identically -- it just takes a different `var_fn` callable.

`api/services/*.py` is the only layer allowed to mix DB reads/writes with calls into the pure
layer. Route handlers (`api/routers/*.py`) never contain calculation logic -- they parse/validate
the request (Pydantic), call a service function, and map the result/exception to an HTTP response.

## Database

PostgreSQL, 15 tables (`db/models.py`), SQLAlchemy 2.0 declarative + Alembic migrations. See
`docs/DATA.md` for the schema diagram and immutability design. Every `risk_runs` /
`backtest_results` / `stress_results` row is self-describing enough to reproduce: config,
as-of-date, and (for risk runs) a data-snapshot hash. See `docs/QUANTITATIVE_METHODOLOGY.md`
Section 9.

## Two different "as of" semantics -- read this before touching data-access code

- `db/queries.py::get_returns_matrix` uses `<=` (data known **through and including** `as_of_date`)
  -- correct for "what is my risk right now, given everything I know through today."
- `validation/data_access.py::get_returns_before` uses `<` (data **strictly before** `as_of_date`)
  -- correct for the backtest loop, which is forecasting that specific date's own outcome and must
  not have seen it yet.

These are not the same function reused two ways; they're two different, intentionally-separate
functions with different correctness properties. Merging them would silently reintroduce
look-ahead bias into the backtest.

## Technology choices and why

| Choice | Reason |
|---|---|
| FastAPI + Pydantic v2 | OpenAPI spec generated from the same schemas that validate requests. |
| PostgreSQL + SQLAlchemy 2.0 + Alembic | Relational integrity between portfolios/positions/results is load-bearing for the audit trail; a document store would make traceability a documentation promise instead of a schema constraint. |
| Vanilla JS + Plotly (CDN) dashboard | Blueprint guidance: "the content/structure matters far more than the charting library choice." No build step, no framework overhead for an 9-tab internal dashboard. |
| cron-style scheduler loop (not Celery/Redis) | One portfolio universe, no need for worker-pool scaling at this project's scale. Revisit if scaling to many portfolios needing parallel processing. |
| HTML-only reporting (no PDF) | WeasyPrint needs the GTK/Cairo/Pango native stack, not cleanly installable in this dev environment. Documented, not faked. |
| prometheus_client for metrics | Lightweight, standard; a full Grafana dashboard is explicitly out of scope (nice-to-have per the design brief). |

## Repository layout

```
src/risk_engine/
  data/          ingestion: vendors, validation, returns, universe definition
  db/            SQLAlchemy models, session, queries, snapshot hashing
  portfolio/     position/weight/portfolio-return calculations, risk decomposition
  risk_models/   historical/parametric/monte_carlo VaR+CVaR (pure)
  validation/    rolling backtest, Kupiec, Christoffersen, traffic-light (pure)
  stress/        scenario definitions, replay/factor-shock engine, factor-beta regression
  reporting/     HTML report generation (Jinja2 templates, matplotlib charts, interpretation text)
  scheduler/     daily pipeline entrypoint
  observability/ structured JSON logging, Prometheus metrics
  api/
    routers/     thin FastAPI route handlers
    schemas/     Pydantic request/response models
    services/    orchestration -- DB + pure-function calls
    main.py      app assembly, health/metrics endpoints, dashboard static mount
tests/
  unit/          fast, no I/O -- the majority of the suite
  statistical/   convergence/distributional checks
  integration/   real Postgres, full pipeline through the DB
  e2e/           full HTTP workflow through the FastAPI TestClient
  anti_leakage/  dedicated look-ahead-bias regression tests
  data_quality/  malformed-data handling, corporate-action spot-checks
  golden/        DB-free regression reference for the core calculations
notebooks/       4 executed research notebooks (see docs root README for summaries)
frontend/        the dashboard (static HTML/CSS/JS, served by the API at /dashboard)
alembic/         DB migrations
scripts/         CLI entrypoints (ingestion, scenario seeding, notebook builders, sample report)
```
