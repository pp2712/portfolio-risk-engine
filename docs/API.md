# API

Full interactive documentation (auto-generated from the Pydantic schemas) is served at
`/docs` (Swagger UI) and `/redoc` when the app is running. This document is a narrative overview.

## Authentication

All write endpoints (`POST`, and the report-regenerate endpoint) require an `X-API-Key` header
matching the `API_KEY` environment variable. Read (`GET`) endpoints are open. See
`docs/SECURITY.md` for scope/rationale.

## Endpoints

| Method & Path | Purpose |
|---|---|
| `GET /portfolios` | List all portfolios |
| `POST /portfolios` | Create a portfolio |
| `GET /portfolios/{id}` | Portfolio metadata + current positions |
| `POST /portfolios/{id}/positions` | Set/replace positions as of a date |
| `POST /model-configs` | Create a model configuration (lookback, MC seed/sims, confidence levels) |
| `POST /risk/runs` | Trigger a risk calculation -> `202 Accepted`, returns `risk_run_id` |
| `GET /risk/runs/{id}` | VaR + CVaR + decomposition for a completed run |
| `GET /risk/backtest?portfolio_id=` | List backtests for a portfolio |
| `POST /risk/backtest` | Trigger a rolling backtest -> `202 Accepted`, returns `backtest_id` |
| `GET /risk/backtest/{id}` | Kupiec/Christoffersen results + full exception series |
| `GET /risk/history/{portfolio_id}` | Time series of VaR/CVaR across all risk runs for a portfolio |
| `GET /scenarios` | List available stress scenarios |
| `POST /scenarios` | Define a new scenario (historical replay or factor shock) |
| `GET /stress/runs?portfolio_id=` | List stress runs for a portfolio |
| `POST /stress/runs` | Trigger a stress-test run |
| `GET /stress/runs/{id}` | Scenario P&L result |
| `GET /reports?portfolio_id=` | List generated reports for a portfolio |
| `GET /reports/{risk_run_id}` | HTML risk report (generates on first request if missing) |
| `POST /reports/{risk_run_id}/regenerate` | Force report regeneration |
| `GET /health` | DB connectivity + last successful risk-run timestamp |
| `GET /metrics` | Prometheus metrics |

## Idempotency

`POST /risk/runs`, `POST /risk/backtest`, and `POST /stress/runs` are idempotent for a given
`(portfolio_id, config_id/scenario_id, as_of_date/window)` triple -- re-requesting an identical
computation returns the already-persisted result rather than recomputing or creating a duplicate
row (enforced by DB unique constraints, checked first in the orchestration layer). This is what
makes "the same config against the same data reproduces the same result" a cheap query rather than
something that has to be trusted.

## Example: full workflow

```
POST /portfolios                          {"name": "Demo", "base_currency": "USD"}
  -> {"portfolio_id": 1, ...}

POST /portfolios/1/positions               {"as_of_date": "2026-08-01", "positions": [{"ticker": "AAPL", "quantity": 100}, ...]}

POST /model-configs                        {"lookback_window_days": 250, "mc_num_simulations": 25000, "mc_random_seed": 42, "confidence_levels": [0.95, 0.99]}
  -> {"config_id": 1, ...}

POST /risk/runs                            {"portfolio_id": 1, "config_id": 1, "as_of_date": "2026-08-01"}
  -> 202 {"risk_run_id": 1, "status": "queued"}

GET /risk/runs/1
  -> {
       "var": {"historical": {"0.95": 0.0135, "0.99": 0.0180}, "parametric": {...}, "monte_carlo": {...}},
       "cvar": {...},
       "decomposition": [{"ticker": "AAPL", "component_var": 0.0018, "pct_contribution": 0.148}, ...],
       "data_snapshot_hash": "...",
       ...
     }
```

## Error handling

- `404` -- referenced entity (portfolio, config, risk run, scenario) not found.
- `422` -- request is well-formed but cannot be satisfied (unknown ticker, insufficient return
  history for the requested lookback, non-positive portfolio value).
- `401` -- missing/invalid `X-API-Key` on a write endpoint.
- Pydantic validation errors (malformed request body) are handled automatically by FastAPI and
  return `422` with a structured error body before reaching any route handler code.
