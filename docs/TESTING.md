# Testing

142 tests, organized as a real pyramid (not inverted):

| Category | Count | Speed | What it covers |
|---|---|---|---|
| `tests/unit/` | ~90 | fast, no I/O | Every VaR/CVaR/decomposition/portfolio calculation, against hand-computed or closed-form known answers |
| `tests/statistical/` | 2 | fast | Monte Carlo -> parametric convergence, estimator-variance shrinkage with N |
| `tests/data_quality/` | ~13 | fast + 1 real-DB | Malformed data handling; corporate-action spot-checks against real ingested history |
| `tests/anti_leakage/` | 6 | fast | Dedicated look-ahead-bias regressions -- see below |
| `tests/golden/` | 1 | fast, DB-free | Fixed-seed reference output for the core calculation chain |
| `tests/integration/` | ~30 | real Postgres | Full risk-run/backtest/stress/report orchestration through the DB, reproducibility proof |
| `tests/e2e/` | 4 | real Postgres + HTTP | Full workflow through the actual FastAPI app (`TestClient`) |

Run:
```powershell
.venv\Scripts\python -m pytest                       # full suite
.venv\Scripts\python -m pytest tests\unit -q          # fast loop while iterating
.venv\Scripts\python -m pytest -m "not integration"   # skip DB-dependent tests
```

## The two highest-value test categories

**Anti-leakage (`tests/anti_leakage/`).** CLAUDE.md: "the test suite should fail if future
information becomes available to a forecast; do not rely merely on developer discipline." These
tests exist independently of the functional backtest tests -- they exist specifically to catch a
regression that reintroduces leakage even if every functional test still passes (a leaky
implementation can easily still produce plausible-looking numbers). Key assertions:
- Mutating a return value strictly after `as_of_date` never changes the forecast *for* `as_of_date`.
- A boundary-value off-by-one regression guard (`<` vs `<=` at the exact cutoff date).
- Requesting an absurdly large lookback window still can't reach past `as_of_date`.

**Closed-form / invariant tests.** Every VaR/CVaR function is tested against a known analytical
answer (e.g. parametric VaR on a synthetic `mu=0, sigma=0.02` series matches `z_alpha * sigma` to
`1e-10`). Two invariants are checked continuously:
- `CVaR >= VaR`, always, including under randomised negative-mu parameters (the exact condition
  under which the design spec's original, uncorrected CVaR formula would have failed).
- `sum(ComponentVaR_i) == VaR_portfolio`, exactly, verified to `1e-9` across randomised 2-20 asset
  portfolios and to `1.7e-18` (floating-point noise) against real market data.

## Reproducibility as a test, not a claim

`tests/integration/test_reproducibility.py` deletes a persisted risk run's rows and calls
`execute_risk_run` again -- forcing a genuine from-scratch recomputation (re-fetching from the DB,
not returning the cached idempotent result) -- and asserts every VaR/CVaR/decomposition value and
the `data_snapshot_hash` match the original exactly.

## Golden/regression testing

`tests/golden/test_golden_risk_calculations.py` computes a fixed-seed synthetic 4-asset scenario
and compares against a stored `reference_output.json`. Deliberately DB-free so it runs at
unit-test speed on every commit. Regenerating the reference
(`python -m tests.golden.generate_reference`) is a manual, reviewed action -- never done reflexively
just to make the test pass; a diff means either the fixed scenario changed (fine) or a calculation's
numeric output changed (needs a reason).

## Data-quality and integration tests

- `tests/data_quality/test_validation.py` -- synthetic malformed rows (negative price, future date,
  null price, duplicate row, large single-day move) exercised against `data/validation.py` directly.
- `tests/data_quality/test_corporate_actions.py` -- real ingested price history around three known
  stock splits (AAPL 2020, NVDA 2021/2024), skips gracefully if that history hasn't been ingested
  locally rather than failing the whole suite.
- `tests/integration/test_schema.py` -- the append-only immutability principle (a "correction" row
  for an existing date does not violate any constraint) and the position-uniqueness constraint.

## CI

`.github/workflows/ci.yml` runs on every push/PR: `ruff check`, `mypy`, the full `pytest` suite
against a real `postgres:17-alpine` service container (so integration/e2e tests run for real, not
skipped), `pip-audit`, and a Docker image build. See `docs/DEPLOYMENT.md`.
