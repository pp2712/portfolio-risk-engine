"""HTML risk report generation: gather everything about a risk run (+ optional backtest/stress
context) from the DB, render the Jinja2 template, write the file, persist a `reports` row.

HTML is the primary and only format (CLAUDE.md: WeasyPrint/PDF dropped -- see docs/KNOWN_LIMITATIONS.md).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.db.models import (
    Asset,
    BacktestException,
    BacktestResult,
    CvarResult,
    ModelConfig,
    Portfolio,
    Report,
    RiskDecomposition,
    RiskRun,
    Scenario,
    StressResult,
    VarResult,
)
from risk_engine.db.queries import get_latest_positions, get_latest_prices, get_returns_matrix
from risk_engine.portfolio.calculations import (
    compute_portfolio_returns,
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
    herfindahl_hirschman_index,
    max_drawdown,
)
from risk_engine.portfolio.calculations import diversification_benefit as div_benefit_fn
from risk_engine.reporting.charts import (
    decomposition_bar_chart,
    exception_series_chart,
    model_comparison_chart,
    stress_comparison_chart,
)
from risk_engine.reporting.interpretation import build_interpretation
from risk_engine.risk_models.historical import historical_var

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ReportGenerationError(ValueError):
    pass


def generate_report(
    db: Session,
    risk_run_id: int,
    backtest_id: int | None = None,
    stress_result_ids: list[int] | None = None,
    output_dir: Path = Path("reports/generated"),
) -> Report:
    risk_run = db.get(RiskRun, risk_run_id)
    if risk_run is None:
        raise ReportGenerationError(f"risk run {risk_run_id} not found")
    portfolio = db.get(Portfolio, risk_run.portfolio_id)
    config = db.get(ModelConfig, risk_run.config_id)
    if portfolio is None or config is None:
        raise ReportGenerationError("risk run references a missing portfolio or config")

    positions = get_latest_positions(db, portfolio.portfolio_id, risk_run.as_of_date)
    tickers = sorted(positions.keys())
    prices = get_latest_prices(db, tickers, risk_run.as_of_date)
    market_values = compute_position_values(positions, prices)
    portfolio_value = compute_portfolio_value(market_values)
    weights = compute_weights(market_values, portfolio_value)
    hhi = herfindahl_hirschman_index(weights)

    position_rows = [
        {"ticker": t, "weight": weights[t], "market_value": market_values[t]}
        for t in sorted(weights, key=lambda t: weights[t], reverse=True)
    ]

    # Volatility / max drawdown over the same lookback window used for the risk run.
    volatility = None
    max_dd = None
    log_matrix = get_returns_matrix(db, tickers, risk_run.as_of_date, config.lookback_window_days, column="log_return")
    simple_matrix = get_returns_matrix(db, tickers, risk_run.as_of_date, config.lookback_window_days, column="simple_return")
    if not log_matrix.empty:
        aligned = [t for t in tickers if t in log_matrix.columns]
        w = {t: weights[t] for t in aligned if t in weights}
        port_log_returns = compute_portfolio_returns(w, log_matrix)
        volatility = float(port_log_returns.std() * (252**0.5))
    if not simple_matrix.empty:
        aligned = [t for t in tickers if t in simple_matrix.columns]
        w = {t: weights[t] for t in aligned if t in weights}
        port_simple_returns = compute_portfolio_returns(w, simple_matrix)
        max_dd = max_drawdown(port_simple_returns)

    var_rows = db.execute(select(VarResult).where(VarResult.risk_run_id == risk_run_id)).scalars().all()
    cvar_rows = db.execute(select(CvarResult).where(CvarResult.risk_run_id == risk_run_id)).scalars().all()
    var: dict[str, dict[str, float]] = {}
    for v in var_rows:
        var.setdefault(v.method, {})[f"{v.confidence_level:.2f}"] = v.var_value
    cvar: dict[str, dict[str, float]] = {}
    for c in cvar_rows:
        cvar.setdefault(c.method, {})[f"{c.confidence_level:.2f}"] = c.cvar_value
    methods = sorted(var.keys())
    confidence_levels = sorted({v.confidence_level for v in var_rows})

    decomp_rows = db.execute(
        select(RiskDecomposition, Asset.ticker)
        .join(Asset, Asset.asset_id == RiskDecomposition.asset_id)
        .where(RiskDecomposition.risk_run_id == risk_run_id)
    ).all()
    decomposition = [
        {"ticker": ticker, "component_var": d.component_var, "marginal_var": d.marginal_var, "pct_contribution": d.pct_contribution}
        for d, ticker in decomp_rows
    ]

    decomposition_chart_b64 = None
    if decomposition:
        decomposition_chart_b64 = decomposition_bar_chart(
            [d["ticker"] for d in decomposition], [d["component_var"] for d in decomposition]
        )

    model_comparison_chart_b64 = None
    if confidence_levels:
        primary_conf = confidence_levels[0]
        conf_key = f"{primary_conf:.2f}"
        values = [var[m].get(conf_key, 0.0) for m in methods]
        if any(values):
            model_comparison_chart_b64 = model_comparison_chart(methods, values, primary_conf)

    # Diversification benefit: standalone historical VaR per position vs. parametric portfolio VaR.
    diversification_benefit_pct = None
    if not log_matrix.empty and confidence_levels:
        primary_conf = confidence_levels[0]
        standalone = {}
        for t in log_matrix.columns:
            if t in weights and weights[t] > 0:
                standalone[t] = weights[t] * historical_var(log_matrix[t].to_numpy(), primary_conf)
        portfolio_var_primary = var.get("historical", {}).get(f"{primary_conf:.2f}")
        if standalone and portfolio_var_primary:
            benefit = div_benefit_fn(standalone, portfolio_var_primary)
            total_standalone = sum(standalone.values())
            if total_standalone > 0:
                diversification_benefit_pct = benefit / total_standalone

    backtest_ctx = None
    exception_chart_b64 = None
    if backtest_id is not None:
        bt = db.get(BacktestResult, backtest_id)
        if bt is not None:
            backtest_ctx = bt
            exceptions = db.execute(
                select(BacktestException).where(BacktestException.backtest_id == backtest_id).order_by(BacktestException.as_of_date)
            ).scalars().all()
            if exceptions:
                exception_chart_b64 = exception_series_chart(
                    [e.as_of_date for e in exceptions],
                    [e.var_forecast for e in exceptions],
                    [e.realised_pnl for e in exceptions],
                    [e.is_exception for e in exceptions],
                )

    stress_results: list[dict[str, str | float]] = []
    stress_chart_b64 = None
    if stress_result_ids:
        for sid in stress_result_ids:
            sr = db.get(StressResult, sid)
            if sr is None:
                continue
            scenario = db.get(Scenario, sr.scenario_id)
            stress_results.append(
                {"scenario_name": scenario.name if scenario else f"scenario {sr.scenario_id}", "portfolio_pnl": sr.portfolio_pnl, "portfolio_pnl_pct": sr.portfolio_pnl_pct}
            )
        if stress_results:
            scenario_names = [str(s["scenario_name"]) for s in stress_results]
            pnl_pcts = [float(s["portfolio_pnl_pct"]) for s in stress_results]
            stress_chart_b64 = stress_comparison_chart(scenario_names, pnl_pcts)

    primary_conf = confidence_levels[0] if confidence_levels else 0.95
    conf_key = f"{primary_conf:.2f}"
    interpretation = build_interpretation(
        portfolio_name=portfolio.name,
        var_by_method={m: var[m][conf_key] for m in methods if conf_key in var[m]},
        cvar_by_method={m: cvar[m][conf_key] for m in methods if m in cvar and conf_key in cvar[m]},
        confidence=primary_conf,
        kupiec_pass=backtest_ctx.kupiec_pass if backtest_ctx else None,
        kupiec_pvalue=backtest_ctx.kupiec_pvalue if backtest_ctx else None,
        christoffersen_pass=backtest_ctx.christoffersen_pass if backtest_ctx else None,
        christoffersen_pvalue=backtest_ctx.christoffersen_pvalue if backtest_ctx else None,
        traffic_light_zone=backtest_ctx.traffic_light_zone if backtest_ctx else None,
        diversification_benefit_pct=diversification_benefit_pct,
    )

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html"]))
    template = env.get_template("report.html.jinja2")
    html = template.render(
        portfolio=portfolio, risk_run=risk_run, config=config,
        portfolio_value=portfolio_value, positions=position_rows, hhi=hhi,
        volatility=volatility, max_drawdown_pct=max_dd,
        var=var, cvar=cvar, methods=methods, confidence_levels=confidence_levels,
        decomposition=decomposition, decomposition_chart_b64=decomposition_chart_b64,
        model_comparison_chart_b64=model_comparison_chart_b64,
        backtest=backtest_ctx, exception_chart_b64=exception_chart_b64,
        stress_results=stress_results, stress_chart_b64=stress_chart_b64,
        interpretation=interpretation,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"risk_run_{risk_run_id}.html"
    output_path = output_dir / filename
    output_path.write_text(html, encoding="utf-8")

    report = Report(risk_run_id=risk_run_id, status="generated", storage_path=str(output_path))
    db.add(report)
    db.flush()
    return report
