"""Build & execute notebooks/02_backtesting_validation.ipynb -- the artifact that proves the
project's core claim: not just "here is a VaR number" but "here is the statistical proof it is
calibrated." Real leakage-safe rolling backtest against real market data.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notebook_builder import build_and_execute  # noqa: E402

CELLS: list[tuple[str, str]] = [
("md", """
# Experiment 2 & 4: Model Validation -- Which VaR Model Can Actually Be Trusted?

**Question:** Of the three VaR methodologies (Historical, Parametric, Monte Carlo), which one(s)
produce statistically calibrated forecasts for this portfolio, and do any exhibit dangerous
exception clustering (failing exactly during regime shifts, even if their overall exception rate
looks acceptable)?

**Method:** A leakage-safe rolling walk-forward backtest (`validation/backtest.py`) -- for each
date in the backtest window, each model's VaR forecast uses *only* data strictly before that date
(`validation/data_access.py` enforces this structurally, not by convention). The forecast is then
compared against the actual realised return. Kupiec (coverage) and Christoffersen (independence)
tests are applied to the resulting exception series. This notebook runs the real backtest engine
against real ingested market data -- nothing here is simulated or fabricated.
"""),

("code", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from risk_engine.db.session import SessionLocal
from risk_engine.db.queries import get_returns_matrix
from risk_engine.portfolio.calculations import compute_portfolio_returns
from risk_engine.risk_models.historical import historical_var
from risk_engine.risk_models.parametric import parametric_var
from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar
from risk_engine.validation.backtest import run_rolling_backtest, exception_summary
from risk_engine.validation.kupiec import kupiec_pof_test
from risk_engine.validation.christoffersen import christoffersen_independence_test, conditional_coverage_test
from risk_engine.validation.traffic_light import traffic_light_zone

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "JPM", "JNJ", "PG", "XOM", "XLK"]
LOOKBACK_DAYS = 250
CONFIDENCE = 0.95

db = SessionLocal()
as_of_date = db.execute(__import__("sqlalchemy").text("SELECT max(price_date) FROM prices")).scalar()

# Full available history so the backtest window can be long.
full_history_days = LOOKBACK_DAYS + 1000
returns_matrix = get_returns_matrix(db, TICKERS, as_of_date, full_history_days)
weights = {t: 1.0 / len(TICKERS) for t in TICKERS}
portfolio_returns = compute_portfolio_returns(weights, returns_matrix)
portfolio_returns.index = pd.to_datetime(returns_matrix.index)

window_start = portfolio_returns.index[LOOKBACK_DAYS].date()
window_end = portfolio_returns.index[-1].date()
print(f"Backtest window: {window_start} to {window_end} ({len(portfolio_returns) - LOOKBACK_DAYS} trading days)")
"""),

("code", """
def historical_var_fn(window):
    return historical_var(window, CONFIDENCE)

def parametric_var_fn(window):
    return parametric_var(float(np.mean(window)), float(np.std(window, ddof=1)), CONFIDENCE)

def monte_carlo_var_fn(window):
    mu = np.array([float(np.mean(window))])
    cov = np.array([[float(np.var(window, ddof=1))]])
    result = monte_carlo_var_cvar(np.array([1.0]), mu, cov, CONFIDENCE, n_simulations=5000, seed=42)
    return result.var

METHODS = {"historical": historical_var_fn, "parametric": parametric_var_fn, "monte_carlo": monte_carlo_var_fn}

backtest_results = {}
for name, var_fn in METHODS.items():
    records = run_rolling_backtest(portfolio_returns, var_fn, LOOKBACK_DAYS, window_start, window_end)
    backtest_results[name] = records
    print(f"{name}: {len(records)} observations computed")
"""),

("code", """
summary_rows = []
for name, records in backtest_results.items():
    n_obs, n_exc = exception_summary(records)
    kupiec = kupiec_pof_test(n_obs, n_exc, CONFIDENCE)
    exceptions_binary = [r.is_exception for r in records]
    christoffersen = christoffersen_independence_test(exceptions_binary)
    cc = conditional_coverage_test(kupiec, christoffersen)
    zone = traffic_light_zone(n_obs, n_exc, CONFIDENCE)
    summary_rows.append({
        "method": name, "n_obs": n_obs, "n_exceptions": n_exc,
        "exception_rate": n_exc / n_obs, "expected_rate": 1 - CONFIDENCE,
        "kupiec_pvalue": kupiec.p_value, "kupiec_pass": not kupiec.reject_h0,
        "christoffersen_pvalue": christoffersen.p_value, "christoffersen_pass": not christoffersen.reject_h0,
        "conditional_coverage_pass": not cc.reject_h0,
        "traffic_light": zone,
    })

summary_df = pd.DataFrame(summary_rows).set_index("method")
summary_df
"""),

("code", """
fig, ax = plt.subplots(figsize=(10, 4))
records = backtest_results["historical"]
dates = [r.as_of_date for r in records]
var_forecast = [r.var_forecast for r in records]
realised = [r.realised_return for r in records]
is_exc = [r.is_exception for r in records]

ax.plot(dates, [-v for v in var_forecast], color="#c0392b", linewidth=1, label="-VaR (historical)")
ax.scatter([d for d, e in zip(dates, is_exc) if not e], [r for r, e in zip(realised, is_exc) if not e], s=8, color="#2c3e50", label="Realised return")
ax.scatter([d for d, e in zip(dates, is_exc) if e], [r for r, e in zip(realised, is_exc) if e], s=45, color="#e74c3c", marker="x", label="Exception")
ax.axhline(0, color="grey", linewidth=0.5)
ax.set_title("Historical VaR: Forecast vs Realised Return (95% confidence)")
ax.legend(loc="lower left", fontsize=8)
fig.autofmt_xdate()
fig.tight_layout()
plt.show()
"""),

("code", """
# Data-driven conclusion -- entirely derived from summary_df above, no hardcoded claims.
passing = summary_df[summary_df["kupiec_pass"] & summary_df["christoffersen_pass"]]
failing = summary_df[~(summary_df["kupiec_pass"] & summary_df["christoffersen_pass"])]

print(f"Backtest window: {window_start} to {window_end}, {summary_df['n_obs'].iloc[0]} observations, 95% confidence\\n")

for method, row in summary_df.iterrows():
    verdict = "PASSES both coverage and independence" if row["kupiec_pass"] and row["christoffersen_pass"] else "FAILS at least one test"
    print(f"{method:>12}: {row['n_exceptions']:.0f}/{row['n_obs']:.0f} exceptions "
          f"({row['exception_rate']:.2%} vs {row['expected_rate']:.2%} expected), "
          f"Kupiec p={row['kupiec_pvalue']:.4f}, Christoffersen p={row['christoffersen_pvalue']:.4f} -- {verdict}")

print()
if len(passing) == len(summary_df):
    print("All three models are statistically well-calibrated for this portfolio over this window.")
elif len(passing) == 0:
    print("NONE of the three models are statistically well-calibrated for this portfolio over this")
    print("window -- this would be a real signal to recalibrate lookback windows or confidence")
    print("assumptions before relying on any of them for capital/limit-setting decisions.")
else:
    print(f"Only {list(passing.index)} pass(es) both tests; {list(failing.index)} should not be")
    print("trusted without recalibration for this portfolio over this window.")
"""),

("md", """
## Experiment 4: Exception Clustering

Kupiec alone cannot distinguish "exceptions spread evenly through the window" from "exceptions
clustered in a single crisis period" -- Christoffersen's independence test (computed above) is
specifically designed to catch this. A model that clusters its failures is failing exactly when it
matters most (during a regime shift), even if its raw exception count looks acceptable.
"""),

("code", """
for method, row in summary_df.iterrows():
    if row["christoffersen_pass"]:
        print(f"{method}: no significant clustering detected (p={row['christoffersen_pvalue']:.4f}) -- "
              "exceptions appear independent over time.")
    else:
        print(f"{method}: SIGNIFICANT CLUSTERING detected (p={row['christoffersen_pvalue']:.4f}) -- "
              "exceptions are NOT independent; breaches tend to occur in runs.")
"""),

("md", """
## Limitations

- The backtest window length is capped by available ingested history (2007-present) and the
  250-day lookback requirement; a longer window would allow more powerful statistical tests.
- Monte Carlo VaR in this backtest uses 5,000 simulations per rolling window (vs. 25,000-50,000 in
  the model-comparison notebook) purely for notebook runtime -- see `test_monte_carlo_convergence.py`
  for the formal N-sensitivity analysis.
- This is a single equal-weighted 10-asset portfolio; conclusions about "which model to trust" are
  specific to this portfolio's composition and this backtest window, not a universal ranking.
"""),
]

if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "notebooks" / "02_backtesting_validation.ipynb"
    build_and_execute(CELLS, output)
