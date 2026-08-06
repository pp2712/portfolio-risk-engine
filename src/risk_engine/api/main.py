"""FastAPI application entrypoint.

Run: uvicorn risk_engine.api.main:app --reload --app-dir src
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from risk_engine.api.routers import (
    backtest,
    history,
    model_configs,
    portfolios,
    reports,
    risk,
    stress,
)
from risk_engine.db.models import RiskRun
from risk_engine.db.session import SessionLocal, engine
from risk_engine.observability.logging_config import setup_json_logging
from risk_engine.observability.metrics import request_metrics_middleware

setup_json_logging()

app = FastAPI(
    title="Portfolio Risk & Stress-Testing Engine",
    description=(
        "Produces VaR/CVaR estimates across three independent methodologies and continuously "
        "validates them against realised outcomes via a leakage-safe rolling backtest "
        "(Kupiec + Christoffersen)."
    ),
    version="0.1.0",
)

app.middleware("http")(request_metrics_middleware)

app.include_router(portfolios.router)
app.include_router(model_configs.router)
app.include_router(risk.router)
app.include_router(backtest.router)
app.include_router(stress.router)
app.include_router(history.router)
app.include_router(reports.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    last_pipeline_run = None
    if db_ok:
        db: Session = SessionLocal()
        try:
            last_pipeline_run = db.execute(select(RiskRun.calculated_at).order_by(RiskRun.calculated_at.desc()).limit(1)).scalar_one_or_none()
        except Exception:
            pass
        finally:
            db.close()

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "last_risk_run_at": last_pipeline_run.isoformat() if last_pipeline_run else None,
    }


@app.get("/metrics", tags=["health"])
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Dashboard: served by the API itself (docker-compose.yml note: "if built as a separate frontend
# service; otherwise served by `api`" -- we chose the latter, no separate frontend container).
_frontend_dir = Path(__file__).resolve().parents[3] / "frontend"
if _frontend_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_frontend_dir), html=True), name="dashboard")
