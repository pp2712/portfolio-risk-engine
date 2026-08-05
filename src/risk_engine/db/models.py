"""SQLAlchemy ORM models for the Portfolio Risk & Stress-Testing Engine schema.

Design notes (see CLAUDE.md and docs/architecture.md for the full rationale):

- `prices` and `returns` are append-only / immutable. A data correction inserts a new row with a
  later `ingested_at` rather than mutating the old one, so historical risk runs stay valid even
  after later corrections. The blueprint this schema was built from asked for a DB-level unique
  index on (asset_id, price_date) *and* append-only corrections in the same breath -- those two
  requirements are mutually exclusive (a unique constraint on (asset_id, price_date) would reject
  a corrected row for a date that already has one). Resolved in favour of immutability, which is
  the property that actually matters for auditability: ingestion idempotency (not re-inserting an
  unchanged row) is enforced in the ingestion pipeline instead of a DB constraint, and a non-unique
  index on (asset_id, price_date) keeps lookups fast. "Current" price/return for a date is defined
  as the row with the max `ingested_at` for that (asset_id, date) -- see db.queries.latest_prices.
- Every `risk_runs` row stores enough to reproduce its result byte-for-byte: `config_id` (model
  type, confidence levels, lookback, MC seed), `as_of_date`, `data_snapshot_hash`, and
  `calculated_at`. See docs/QUANTITATIVE_METHODOLOGY.md and tests/integration/test_reproducibility.py.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)  # EQUITY | ETF
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    first_available: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    prices: Mapped[list["Price"]] = relationship(back_populates="asset")
    returns: Mapped[list["Return"]] = relationship(back_populates="asset")


class Price(Base):
    """Immutable landing table for raw + adjusted OHLC-derived prices. Never updated in place."""

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "price_date", "ingested_at", name="uq_prices_asset_date_ingested"
        ),
    )

    price_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False, index=True)
    price_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    adj_close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    raw_close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped["Asset"] = relationship(back_populates="prices")


class Return(Base):
    """Immutable log/simple daily returns derived from `prices`. Risk models read only this table."""

    __tablename__ = "returns"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "return_date", "ingested_at", name="uq_returns_asset_date_ingested"
        ),
    )

    return_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False, index=True)
    return_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    log_return: Mapped[float] = mapped_column(Float, nullable=False)
    simple_return: Mapped[float] = mapped_column(Float, nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped["Asset"] = relationship(back_populates="returns")


class Portfolio(Base):
    __tablename__ = "portfolios"

    portfolio_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    positions: Mapped[list["Position"]] = relationship(back_populates="portfolio")


class Position(Base):
    """A portfolio's holding of one asset as of one date. Long-only (quantity >= 0) for MVP."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "asset_id", "as_of_date", name="uq_positions_portfolio_asset_date"
        ),
    )

    position_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.portfolio_id"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False, index=True)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="positions")
    asset: Mapped["Asset"] = relationship()


class ModelConfig(Base):
    """A named, versioned configuration for a risk calculation -- what makes results reproducible."""

    __tablename__ = "model_configs"

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0")
    lookback_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    mc_num_simulations: Mapped[int] = mapped_column(Integer, nullable=False, default=25_000)
    mc_random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    confidence_levels: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: [0.95, 0.99])
    extra_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Scenario(Base):
    """A stress scenario, represented as data. Versioned so old reports stay reproducible."""

    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_scenarios_name_version"),)

    scenario_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)  # HISTORICAL_REPLAY | FACTOR_SHOCK
    historical_start: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    historical_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    factor_shocks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RiskRun(Base):
    """One risk calculation for one portfolio as of one date. The audit-trail anchor row."""

    __tablename__ = "risk_runs"
    __table_args__ = (UniqueConstraint("portfolio_id", "as_of_date", "config_id", name="uq_risk_runs"),)

    risk_run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.portfolio_id"), nullable=False, index=True
    )
    config_id: Mapped[int] = mapped_column(ForeignKey("model_configs.config_id"), nullable=False)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    data_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    calculated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    var_results: Mapped[list["VarResult"]] = relationship(back_populates="risk_run")
    cvar_results: Mapped[list["CvarResult"]] = relationship(back_populates="risk_run")
    decompositions: Mapped[list["RiskDecomposition"]] = relationship(back_populates="risk_run")


class VarResult(Base):
    __tablename__ = "var_results"
    __table_args__ = (
        UniqueConstraint("risk_run_id", "method", "confidence_level", name="uq_var_results"),
    )

    var_result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_run_id: Mapped[int] = mapped_column(
        ForeignKey("risk_runs.risk_run_id"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # historical | parametric | monte_carlo
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    var_value: Mapped[float] = mapped_column(Float, nullable=False)  # positive loss number
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    risk_run: Mapped["RiskRun"] = relationship(back_populates="var_results")


class CvarResult(Base):
    __tablename__ = "cvar_results"
    __table_args__ = (
        UniqueConstraint("risk_run_id", "method", "confidence_level", name="uq_cvar_results"),
    )

    cvar_result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_run_id: Mapped[int] = mapped_column(
        ForeignKey("risk_runs.risk_run_id"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    cvar_value: Mapped[float] = mapped_column(Float, nullable=False)  # positive loss number

    risk_run: Mapped["RiskRun"] = relationship(back_populates="cvar_results")


class RiskDecomposition(Base):
    __tablename__ = "risk_decomposition"
    __table_args__ = (UniqueConstraint("risk_run_id", "asset_id", name="uq_risk_decomposition"),)

    decomp_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_run_id: Mapped[int] = mapped_column(
        ForeignKey("risk_runs.risk_run_id"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    component_var: Mapped[float] = mapped_column(Float, nullable=False)
    marginal_var: Mapped[float] = mapped_column(Float, nullable=False)
    pct_contribution: Mapped[float] = mapped_column(Float, nullable=False)

    risk_run: Mapped["RiskRun"] = relationship(back_populates="decompositions")


class BacktestResult(Base):
    """Summary statistics for one rolling backtest window."""

    __tablename__ = "backtest_results"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "config_id", "window_start", "window_end", "method",
            name="uq_backtest_results",
        ),
    )

    backtest_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.portfolio_id"), nullable=False, index=True
    )
    config_id: Mapped[int] = mapped_column(ForeignKey("model_configs.config_id"), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    window_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    window_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    num_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    num_exceptions: Mapped[int] = mapped_column(Integer, nullable=False)
    kupiec_stat: Mapped[float] = mapped_column(Float, nullable=False)
    kupiec_pvalue: Mapped[float] = mapped_column(Float, nullable=False)
    kupiec_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    christoffersen_stat: Mapped[float | None] = mapped_column(Float, nullable=True)
    christoffersen_pvalue: Mapped[float | None] = mapped_column(Float, nullable=True)
    christoffersen_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    conditional_coverage_stat: Mapped[float | None] = mapped_column(Float, nullable=True)
    conditional_coverage_pvalue: Mapped[float | None] = mapped_column(Float, nullable=True)
    conditional_coverage_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    traffic_light_zone: Mapped[str] = mapped_column(String(10), nullable=False)  # green|amber|red
    calculated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    exceptions: Mapped[list["BacktestException"]] = relationship(back_populates="backtest")


class BacktestException(Base):
    """Per-date rolling VaR forecast vs. realised P&L -- the exception series behind the chart.

    Not present in the blueprint's ER diagram directly, but required to render the exception-series
    chart (spec Section 17.7 / 19) and to make backtest results independently auditable per date
    rather than only as a summary statistic. A deliberate, documented schema addition.
    """

    __tablename__ = "backtest_exceptions"
    __table_args__ = (UniqueConstraint("backtest_id", "as_of_date", name="uq_backtest_exceptions"),)

    exception_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_results.backtest_id"), nullable=False, index=True
    )
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    var_forecast: Mapped[float] = mapped_column(Float, nullable=False)
    realised_return: Mapped[float] = mapped_column(Float, nullable=False)
    realised_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    is_exception: Mapped[bool] = mapped_column(Boolean, nullable=False)

    backtest: Mapped["BacktestResult"] = relationship(back_populates="exceptions")


class StressResult(Base):
    __tablename__ = "stress_results"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "scenario_id", "as_of_date", name="uq_stress_results"),
    )

    stress_result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.portfolio_id"), nullable=False, index=True
    )
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.scenario_id"), nullable=False)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    portfolio_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    portfolio_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    position_contributions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calculated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_run_id: Mapped[int] = mapped_column(
        ForeignKey("risk_runs.risk_run_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
