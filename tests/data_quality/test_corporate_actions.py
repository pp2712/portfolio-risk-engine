"""Spot-check that the vendor's price series correctly absorbs known stock splits.

Blueprint requirement: "explicitly verify (spot-check 2-3 known stock splits) that the vendor's
adjustment is applied correctly, rather than trusting it blindly."

Finding from building this check: Yahoo Finance's `Close` field (with auto_adjust=False) is
*already split-adjusted* -- historical splits are retroactively folded into the whole `Close`
series by the vendor, not just `Adj Close`. Only `Adj Close` additionally removes dividends.
yfinance does not expose a truly "as traded on the day" unadjusted price at all. The correct
verification is therefore NOT "does `close` jump by the split ratio on the split date" (it
shouldn't -- see docs/DATA.md) but "is the return series continuous (no artificial spike) across
the split date in both `close` and `adj_close`". An artificial spike there would mean the vendor's
adjustment was missing or mistimed and would directly corrupt VaR/CVaR and the backtest.

Queries the real ingested dev database (not the isolated test DB) because this is inherently a
check against real market data, not synthetic fixtures. Skips (does not fail) if the relevant
history hasn't been ingested locally -- run `scripts/ingest_universe.py` first.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from risk_engine.config import get_settings
from risk_engine.db.models import Asset, Price

pytestmark = pytest.mark.integration

# (ticker, split_date, split_ratio) -- ratio isn't asserted directly (see module docstring) but
# documents which known corporate action each date corresponds to.
KNOWN_SPLITS = [
    ("AAPL", dt.date(2020, 8, 31), 4.0),
    ("NVDA", dt.date(2021, 7, 20), 4.0),
    ("NVDA", dt.date(2024, 6, 10), 10.0),
]

# A genuine, undisputed large move for contrast: AAPL's 2000-style single-day moves are outside
# our ingestion window, so the bound below is simply "much larger than any split-adjustment
# artifact would be if the vendor forgot to adjust" (a forgotten 4x/10x split would show up as a
# >70% single-day move, not a few percent).
MAX_PLAUSIBLE_NON_SPLIT_MOVE = 0.25


@pytest.fixture(scope="module")
def dev_session():
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _prices_around(session, ticker: str, center: dt.date, days: int = 5):
    asset = session.execute(select(Asset).where(Asset.ticker == ticker)).scalar_one_or_none()
    if asset is None:
        return None
    rows = session.execute(
        select(Price.price_date, Price.close, Price.adj_close)
        .where(
            Price.asset_id == asset.asset_id,
            Price.price_date.between(center - dt.timedelta(days=days), center + dt.timedelta(days=days)),
        )
        .order_by(Price.price_date)
    ).all()
    return rows


@pytest.mark.parametrize("ticker,split_date,ratio", KNOWN_SPLITS)
def test_price_series_has_no_artificial_jump_across_split(dev_session, ticker, split_date, ratio):
    rows = _prices_around(dev_session, ticker, split_date)
    if not rows or len(rows) < 4:
        pytest.skip(f"no ingested price history around {ticker} split on {split_date} -- run scripts/ingest_universe.py")

    before = [r for r in rows if r.price_date < split_date]
    after = [r for r in rows if r.price_date >= split_date]
    if not before or not after:
        pytest.skip(f"insufficient rows straddling {ticker} split on {split_date}")

    close_before, close_after = float(before[-1].close), float(after[0].close)
    adj_before, adj_after = float(before[-1].adj_close), float(after[0].adj_close)

    close_move = abs(close_after / close_before - 1.0)
    adj_move = abs(adj_after / adj_before - 1.0)

    assert close_move < MAX_PLAUSIBLE_NON_SPLIT_MOVE, (
        f"{ticker}: `close` moved {close_move:.1%} across its {ratio}x split on {split_date} -- "
        "if the vendor's split-adjustment were missing this would show up as ~a {ratio}x jump; "
        "the series should be continuous"
    )
    assert adj_move < MAX_PLAUSIBLE_NON_SPLIT_MOVE, (
        f"{ticker}: `adj_close` moved {adj_move:.1%} across its {ratio}x split on {split_date} -- "
        "adjusted close must never show a split discontinuity"
    )
