"""FastAPI application entrypoint.

Run: uvicorn risk_engine.api.main:app --reload --app-dir src
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy import text

from risk_engine.api.routers import backtest, history, model_configs, portfolios, risk, stress
from risk_engine.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Portfolio Risk & Stress-Testing Engine",
    description=(
        "Produces VaR/CVaR estimates across three independent methodologies and continuously "
        "validates them against realised outcomes via a leakage-safe rolling backtest "
        "(Kupiec + Christoffersen)."
    ),
    version="0.1.0",
)

app.include_router(portfolios.router)
app.include_router(model_configs.router)
app.include_router(risk.router)
app.include_router(backtest.router)
app.include_router(stress.router)
app.include_router(history.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable"}
