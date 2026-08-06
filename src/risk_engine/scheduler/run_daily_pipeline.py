"""Daily pipeline entrypoint -- what cron calls once a day.

    Fetch latest prices (incremental, idempotent -- last ~10 days is cheap and self-healing)
        |
    Recompute returns for new dates (ingest_asset does this as part of ingestion)
        |
    For each portfolio: trigger a risk run (as_of_date = today)
        |
    Extend the rolling backtest by one day
        |
    Refresh stored stress scenarios against updated weights
        |
    Generate a report
        |
    Log completion

Cron, not Celery/Redis -- see CLAUDE.md "Technology stack" for why a task queue would be
over-engineering at this project's scale (one portfolio universe, no need for worker scaling).
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from risk_engine.api.services.backtest_service import BacktestError, execute_backtest  # noqa: E402
from risk_engine.api.services.risk_run_service import RiskRunError, execute_risk_run  # noqa: E402
from risk_engine.api.services.stress_service import StressRunError, execute_stress_run  # noqa: E402
from risk_engine.data.ingest import ingest_universe  # noqa: E402
from risk_engine.data.universe import MARKET_FACTOR_PROXY, UNIVERSE  # noqa: E402
from risk_engine.db.models import ModelConfig, Portfolio, Scenario  # noqa: E402
from risk_engine.db.session import SessionLocal  # noqa: E402
from risk_engine.reporting.generator import ReportGenerationError, generate_report  # noqa: E402

logger = logging.getLogger("risk_engine.scheduler")

INCREMENTAL_INGEST_LOOKBACK_DAYS = 10
BACKTEST_WINDOW_DAYS = 500


def _default_config(db: Session) -> ModelConfig | None:
    return db.execute(select(ModelConfig).order_by(ModelConfig.config_id.desc())).scalars().first()


def run_daily_pipeline(as_of_date: dt.date | None = None) -> dict:
    as_of_date = as_of_date or dt.date.today()
    summary: dict = {"as_of_date": str(as_of_date), "ingestion": None, "portfolios": []}

    db = SessionLocal()
    try:
        ingest_start = as_of_date - dt.timedelta(days=INCREMENTAL_INGEST_LOOKBACK_DAYS)
        ingest_summaries = ingest_universe(db, (*UNIVERSE, MARKET_FACTOR_PROXY), ingest_start, as_of_date)
        summary["ingestion"] = {"tickers": len(ingest_summaries), "rows_inserted": sum(s["rows_inserted"] for s in ingest_summaries)}
        logger.info("ingestion complete: %s", summary["ingestion"])

        config = _default_config(db)
        if config is None:
            logger.warning("no model_configs exist -- skipping risk/backtest/stress/report steps")
            return summary

        portfolios = db.execute(select(Portfolio)).scalars().all()
        scenarios = db.execute(select(Scenario)).scalars().all()

        for portfolio in portfolios:
            entry: dict = {"portfolio_id": portfolio.portfolio_id, "name": portfolio.name}
            try:
                risk_run = execute_risk_run(db, portfolio.portfolio_id, config.config_id, as_of_date)
                db.commit()
                entry["risk_run_id"] = risk_run.risk_run_id
            except RiskRunError as e:
                db.rollback()
                entry["risk_run_error"] = str(e)
                summary["portfolios"].append(entry)
                logger.warning("risk run failed for portfolio %s: %s", portfolio.portfolio_id, e)
                continue

            try:
                backtest = execute_backtest(
                    db, portfolio.portfolio_id, config.config_id, "historical", 0.95,
                    as_of_date - dt.timedelta(days=BACKTEST_WINDOW_DAYS), as_of_date,
                )
                db.commit()
                entry["backtest_id"] = backtest.backtest_id
                entry["traffic_light_zone"] = backtest.traffic_light_zone
            except BacktestError as e:
                db.rollback()
                entry["backtest_error"] = str(e)

            stress_ids = []
            for scenario in scenarios:
                try:
                    stress = execute_stress_run(db, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
                    db.commit()
                    stress_ids.append(stress.stress_result_id)
                except StressRunError as e:
                    db.rollback()
                    logger.warning("stress run failed for portfolio %s scenario %s: %s", portfolio.portfolio_id, scenario.name, e)
            entry["stress_result_ids"] = stress_ids

            try:
                report = generate_report(db, entry["risk_run_id"], backtest_id=entry.get("backtest_id"), stress_result_ids=stress_ids or None)
                db.commit()
                entry["report_path"] = report.storage_path
            except ReportGenerationError as e:
                db.rollback()
                entry["report_error"] = str(e)

            summary["portfolios"].append(entry)
            logger.info("pipeline complete for portfolio %s: %s", portfolio.portfolio_id, entry)

        return summary
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = run_daily_pipeline()
    logger.info("daily pipeline finished: %s", result)
