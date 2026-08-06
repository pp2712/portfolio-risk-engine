from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_engine.api.services.backtest_service import execute_backtest
from risk_engine.api.services.risk_run_service import execute_risk_run
from risk_engine.api.services.stress_service import execute_stress_run
from risk_engine.db.models import Scenario
from risk_engine.reporting.generator import ReportGenerationError, generate_report
from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.integration


def test_generate_report_full_context(db_session, tmp_path):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=400)
    risk_run = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.flush()

    backtest = execute_backtest(
        db_session, portfolio.portfolio_id, config.config_id, "historical", 0.95,
        as_of_date - dt.timedelta(days=90), as_of_date,
    )
    db_session.flush()

    scenario = Scenario(name="Test Crash", scenario_type="HISTORICAL_REPLAY", historical_start=dt.date(2023, 1, 10), historical_end=dt.date(2023, 1, 20), version=1)
    db_session.add(scenario)
    db_session.flush()
    stress = execute_stress_run(db_session, portfolio.portfolio_id, scenario.scenario_id, as_of_date)
    db_session.flush()

    report = generate_report(
        db_session, risk_run.risk_run_id, backtest_id=backtest.backtest_id,
        stress_result_ids=[stress.stress_result_id], output_dir=tmp_path,
    )
    db_session.commit()

    assert Path(report.storage_path).exists()
    html = Path(report.storage_path).read_text(encoding="utf-8")

    # Real content, not a template with unfilled placeholders.
    assert portfolio.name in html
    assert "Kupiec" in html
    assert "Christoffersen" in html or "not applicable" in html.lower()
    assert "Test Crash" in html
    assert "{{" not in html and "}}" not in html  # no unrendered Jinja2 tags leaked through
    assert "data:image/png;base64," in html  # at least one chart embedded


def test_generate_report_without_backtest_or_stress(db_session, tmp_path):
    portfolio, config, as_of_date, _tickers = seed_synthetic_portfolio(db_session, n_days=300, seed=5)
    risk_run = execute_risk_run(db_session, portfolio.portfolio_id, config.config_id, as_of_date)
    db_session.flush()

    report = generate_report(db_session, risk_run.risk_run_id, output_dir=tmp_path)
    html = Path(report.storage_path).read_text(encoding="utf-8")

    assert portfolio.name in html
    assert "{{" not in html


def test_generate_report_unknown_risk_run_raises(db_session, tmp_path):
    with pytest.raises(ReportGenerationError, match="not found"):
        generate_report(db_session, 999999, output_dir=tmp_path)
