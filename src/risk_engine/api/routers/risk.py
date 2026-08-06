from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.api.schemas.risk import (
    DecompositionEntry,
    ModelConfigOut,
    RiskRunAccepted,
    RiskRunRequest,
    RiskRunResultOut,
)
from risk_engine.api.services.risk_run_service import RiskRunError, execute_risk_run
from risk_engine.db.models import (
    Asset,
    CvarResult,
    ModelConfig,
    RiskDecomposition,
    RiskRun,
    VarResult,
)
from risk_engine.db.queries import get_latest_positions, get_latest_prices, get_returns_matrix
from risk_engine.portfolio.calculations import (
    compute_portfolio_returns,
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
    max_drawdown,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/runs", response_model=RiskRunAccepted, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def trigger_risk_run(body: RiskRunRequest, db: Session = Depends(get_db)) -> RiskRunAccepted:
    try:
        risk_run = execute_risk_run(db, body.portfolio_id, body.config_id, body.as_of_date)
        db.commit()
    except RiskRunError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return RiskRunAccepted(risk_run_id=risk_run.risk_run_id, status=risk_run.status)


@router.get("/runs/{risk_run_id}", response_model=RiskRunResultOut)
def get_risk_run(risk_run_id: int, db: Session = Depends(get_db)) -> RiskRunResultOut:
    risk_run = db.get(RiskRun, risk_run_id)
    if risk_run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"risk run {risk_run_id} not found")

    var_rows = db.execute(select(VarResult).where(VarResult.risk_run_id == risk_run_id)).scalars().all()
    cvar_rows = db.execute(select(CvarResult).where(CvarResult.risk_run_id == risk_run_id)).scalars().all()
    decomp_rows = db.execute(
        select(RiskDecomposition, Asset.ticker)
        .join(Asset, Asset.asset_id == RiskDecomposition.asset_id)
        .where(RiskDecomposition.risk_run_id == risk_run_id)
    ).all()
    config = db.get(ModelConfig, risk_run.config_id)
    if config is None:
        # Should be structurally impossible (FK constraint), but keeps mypy honest and gives a
        # clear signal if it ever happens rather than an AttributeError.
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"model config {risk_run.config_id} referenced by risk run {risk_run_id} is missing")

    var: dict[str, dict[str, float]] = {}
    for v in var_rows:
        var.setdefault(v.method, {})[f"{v.confidence_level:.2f}"] = v.var_value
    cvar: dict[str, dict[str, float]] = {}
    for c in cvar_rows:
        cvar.setdefault(c.method, {})[f"{c.confidence_level:.2f}"] = c.cvar_value

    decomposition = [
        DecompositionEntry(ticker=ticker, component_var=d.component_var, marginal_var=d.marginal_var, pct_contribution=d.pct_contribution)
        for d, ticker in decomp_rows
    ]

    # Volatility / max drawdown over the same lookback window used for the risk run -- identical
    # logic to reporting/generator.py, computed here too so the API surfaces it (previously only
    # available inside the generated HTML report).
    volatility: float | None = None
    max_dd: float | None = None
    positions = get_latest_positions(db, risk_run.portfolio_id, risk_run.as_of_date)
    if positions:
        tickers = sorted(positions.keys())
        prices = get_latest_prices(db, tickers, risk_run.as_of_date)
        quantities = {t: positions[t] for t in tickers if t in prices}
        if quantities:
            market_values = compute_position_values(quantities, prices)
            portfolio_value = compute_portfolio_value(market_values)
            weights = compute_weights(market_values, portfolio_value)

            log_matrix = get_returns_matrix(db, tickers, risk_run.as_of_date, config.lookback_window_days, column="log_return")
            if not log_matrix.empty:
                aligned_weights = {t: weights[t] for t in log_matrix.columns if t in weights}
                port_log_returns = compute_portfolio_returns(aligned_weights, log_matrix)
                volatility = float(port_log_returns.std() * (252**0.5))

            simple_matrix = get_returns_matrix(db, tickers, risk_run.as_of_date, config.lookback_window_days, column="simple_return")
            if not simple_matrix.empty:
                aligned_weights = {t: weights[t] for t in simple_matrix.columns if t in weights}
                port_simple_returns = compute_portfolio_returns(aligned_weights, simple_matrix)
                max_dd = max_drawdown(port_simple_returns)

    return RiskRunResultOut(
        risk_run_id=risk_run.risk_run_id,
        portfolio_id=risk_run.portfolio_id,
        as_of_date=risk_run.as_of_date,
        var=var,
        cvar=cvar,
        decomposition=decomposition,
        config=ModelConfigOut(
            config_id=config.config_id,
            model_version=config.model_version,
            lookback_window_days=config.lookback_window_days,
            mc_num_simulations=config.mc_num_simulations,
            mc_random_seed=config.mc_random_seed,
            confidence_levels=config.confidence_levels,
        ),
        data_snapshot_hash=risk_run.data_snapshot_hash,
        calculated_at=risk_run.calculated_at,
        volatility=volatility,
        max_drawdown=max_dd,
    )
