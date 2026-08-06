# Deployment

## Local development (what this project was actually built and tested against)

This dev sandbox has no Docker daemon, so local development used a directly-installed PostgreSQL
17 (via `winget`) rather than `docker compose`. All 142 tests, the live dashboard, the API, the
scheduler, and all 4 research notebooks were run and verified against this setup.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,notebooks]"
copy .env.example .env          # fill in DATABASE_URL / API_KEY / POSTGRES_PASSWORD
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python scripts\ingest_universe.py --start 2007-01-01
.venv\Scripts\python scripts\seed_scenarios.py
.venv\Scripts\python -m uvicorn risk_engine.api.main:app --reload --app-dir src
# -> http://127.0.0.1:8000/docs        (API docs)
# -> http://127.0.0.1:8000/dashboard/  (dashboard)
```

## Docker (the documented, intended production path)

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD, API_KEY
docker compose up --build
```

Services (`docker-compose.yml`): `db` (Postgres 17), `migrate` (runs Alembic once, exits),
`api` (FastAPI + dashboard, port 8000), `scheduler` (runs the daily pipeline on container start,
then every 24h).

**Honesty note:** this Docker setup has not been executed end-to-end in this development
environment (no Docker daemon available here -- see `docs/KNOWN_LIMITATIONS.md`). It is written to
the same standard as the rest of the codebase, and the GitHub Actions `docker-build` CI job does
build the image on every push (the actual verification point), but a local `docker compose up`
smoke test has not been performed by the author. Recommend running it once before relying on it in
a real deployment.

## Environment variables

See `.env.example` for the full list with descriptions. Required: `DATABASE_URL`, `API_KEY`.
Optional with sensible defaults: `MC_DEFAULT_SEED` (42), `DATA_SOURCE` (yfinance), `LOG_LEVEL`
(INFO).

## Database migrations

```powershell
.venv\Scripts\python -m alembic upgrade head              # apply
.venv\Scripts\python -m alembic revision --autogenerate -m "message"   # generate a new migration
```

Two databases are used in development: `portfolio_risk_engine` (dev data, real ingested market
history) and `portfolio_risk_engine_test` (truncated between test runs via `tests/conftest.py`).
Both need migrations applied independently.

## Observability in production

- `GET /health` -- DB connectivity + last successful risk-run timestamp.
- `GET /metrics` -- Prometheus text format (`http_requests_total`, `http_request_duration_seconds`,
  `risk_calculation_duration_seconds` by method, `pipeline_run_total` by outcome).
- Structured JSON logs to stdout (one JSON object per line, `risk_run_id`/`portfolio_id`/etc as
  top-level fields where relevant) -- see `observability/logging_config.py`.

## Scheduling the daily pipeline outside Docker

The `docker-compose.yml` scheduler service runs a simple `while true; sleep 86400` loop. For a real
host-cron deployment instead:

```cron
0 6 * * * cd /path/to/app && .venv/bin/python -m risk_engine.scheduler.run_daily_pipeline >> /var/log/risk_engine_pipeline.log 2>&1
```
