# Data

## Universe

`src/risk_engine/data/universe.py` defines a fixed set of 20 investable assets (17 large-cap US
equities across Technology, Financials, Healthcare, Consumer Staples, Energy, and Communication
Services + 3 sector ETFs: XLF, XLK, XLE) plus `SPY`, ingested separately purely as the broad-market
factor proxy for regression-based stress betas (never an investable holding).

Single currency (USD), daily frequency, adjusted close for return construction. See
`docs/KNOWN_LIMITATIONS.md` for the survivorship-bias and single-currency scope decisions.

## Ingestion pipeline (`data/vendors.py`, `data/validation.py`, `data/returns.py`, `data/ingest.py`)

```
Vendor download (yfinance primary, stooq fallback per-ticker)
        |
Validation (schema check, no future dates, no null/non-positive prices, dedup, outlier FLAGGING)
        |
Idempotent insert into `prices` (skip if unchanged; insert a new row with later ingested_at if a
vendor value genuinely changed -- a "correction", never a mutation of the old row)
        |
Return calculation (log + simple) from the latest price series
        |
Idempotent insert into `returns` (same immutability principle)
```

Run via `scripts/ingest_universe.py --start 2007-01-01`. The scheduler
(`scheduler/run_daily_pipeline.py`) runs an incremental version (last 10 days) daily.

### Price fields -- read this before assuming "raw" means "as traded"

Yahoo Finance's `Close` field (with `auto_adjust=False`) is **already split-adjusted**, just not
dividend-adjusted -- historical splits are retroactively folded into the whole `Close` series by
the vendor. `Adj Close` is split **and** dividend adjusted. Neither is a truly "as traded on the
day" raw price; yfinance does not expose that. This project's `prices.close` column holds the
split-adjusted-only series and `prices.adj_close` holds the fully adjusted series used for all
return construction. Verified against three known stock splits (AAPL 2020, NVDA 2021 and 2024) in
`tests/data_quality/test_corporate_actions.py` -- both series are continuous (no artificial jump)
across each split date, confirming the vendor's adjustment is applied correctly.

### Validation rules

| Check | Action |
|---|---|
| Missing required column | Raise (fail loud, not silent) |
| Future `price_date` | Hard reject, logged |
| Null/non-positive `adj_close` or `close` | Hard reject, logged |
| Exact duplicate `(ticker, price_date)` row | Deduplicate (keep first), logged |
| Single-day \|adj_close move\| > 30% | **Flagged, kept** -- a real crash/melt-up day is exactly the tail-risk observation the models must not lose |

### Missing data / alignment

Assets are aligned to the **intersection** of valid trading days across the specific tickers being
used for a calculation (`data/returns.py::build_aligned_return_matrix`), never forward-filled.
Forward-filling would manufacture a zero-return day that never happened, corrupting both VaR and
the backtest. Alignment happens at query time (scoped to the assets actually being used), not at
ingestion time -- aligning the whole universe to intersection at ingestion would truncate every
asset's usable history to META's 2012 IPO date.

## Schema

15 tables (`db/models.py`), migrated via Alembic (`alembic/versions/`). Full column-level detail is
in the model docstrings; the key structural decisions:

- **`prices` / `returns` are append-only.** No unique constraint on `(asset_id, date)` alone --
  only on `(asset_id, date, ingested_at)` -- specifically so a data correction can insert a new row
  without violating a constraint or requiring a mutation. "Current" value for a date is defined as
  the row with the max `ingested_at` for that `(asset_id, date)`.
- **`risk_runs`** stores `config_id`, `as_of_date`, `data_snapshot_hash`, `calculated_at` -- see
  `docs/QUANTITATIVE_METHODOLOGY.md` Section 9.
- **`backtest_exceptions`** (a deliberate addition beyond the original design's ER diagram): the
  per-date rolling VaR-forecast-vs-realised-return series behind the exception chart. Without it,
  `backtest_results` would only hold summary statistics, not the auditable per-date detail.
- **Uniqueness on `(portfolio_id, config_id, as_of_date)` for `risk_runs`** (and the equivalent for
  `backtest_results` / `stress_results`) makes the orchestration layer idempotent: re-requesting an
  identical run returns the already-persisted one rather than recomputing/duplicating.
