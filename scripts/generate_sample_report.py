"""Build a sample portfolio from the real ingested universe, run the full risk/backtest/stress
pipeline, and generate examples/sample_risk_report.html -- a real, generated report (not mocked)
that can be opened directly without running any code (blueprint standout artifact #5).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from risk_engine.api.services.backtest_service import execute_backtest  # noqa: E402
from risk_engine.api.services.risk_run_service import execute_risk_run  # noqa: E402
from risk_engine.api.services.stress_service import execute_stress_run  # noqa: E402
from risk_engine.db.models import Asset, ModelConfig, Portfolio, Position, Scenario  # noqa: E402
from risk_engine.db.session import SessionLocal  # noqa: E402
from risk_engine.reporting.generator import generate_report  # noqa: E402

# A diversified sample allocation across the real ingested universe.
SAMPLE_HOLDINGS = {
    "AAPL": 150, "MSFT": 120, "GOOGL": 80, "AMZN": 60, "NVDA": 100,
    "JPM": 90, "JNJ": 110, "PG": 100, "XOM": 130, "XLF": 200, "XLK": 150,
}


def main() -> None:
    db = SessionLocal()
    try:
        as_of_date = dt.date.today() - dt.timedelta(days=3)  # a few days back, ensures data exists

        portfolio = Portfolio(name="Sample Diversified Portfolio", base_currency="USD")
        db.add(portfolio)
        db.flush()

        for ticker, qty in SAMPLE_HOLDINGS.items():
            asset = db.execute(select(Asset).where(Asset.ticker == ticker)).scalar_one()
            db.add(Position(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, as_of_date=as_of_date, quantity=qty))
        db.flush()

        config = ModelConfig(
            model_version="v1.0", lookback_window_days=250, mc_num_simulations=25_000, mc_random_seed=42,
            confidence_levels=[0.95, 0.99],
        )
        db.add(config)
        db.flush()

        risk_run = execute_risk_run(db, portfolio.portfolio_id, config.config_id, as_of_date)
        db.flush()
        print(f"risk_run_id={risk_run.risk_run_id}")

        backtest = execute_backtest(
            db, portfolio.portfolio_id, config.config_id, "historical", 0.95,
            as_of_date - dt.timedelta(days=500), as_of_date,
        )
        db.flush()
        print(f"backtest_id={backtest.backtest_id}, exceptions={backtest.num_exceptions}/{backtest.num_observations}, zone={backtest.traffic_light_zone}")

        stress_ids = []
        for scenario_name in ("2008 Global Financial Crisis", "2020 COVID Crash", "Equity Market -20%"):
            scenario = db.execute(select(Scenario).where(Scenario.name == scenario_name)).scalar_one()
            stress = execute_stress_run(db, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
            db.flush()
            stress_ids.append(stress.stress_result_id)
            print(f"stress: {scenario_name} -> P&L {stress.portfolio_pnl_pct:.2%}")

        output_dir = Path(__file__).resolve().parents[1] / "examples"
        report = generate_report(db, risk_run.risk_run_id, backtest_id=backtest.backtest_id, stress_result_ids=stress_ids, output_dir=output_dir)
        db.commit()

        final_path = output_dir / "sample_risk_report.html"
        Path(report.storage_path).replace(final_path)
        print(f"\nReport written to: {final_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
