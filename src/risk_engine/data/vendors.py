"""Market-data vendor adapters.

Both adapters return the same "raw prices" long-format DataFrame:
    columns = [ticker, price_date, open, high, low, close, adj_close, volume, source]

Primary vendor is Yahoo Finance (via `yfinance`). Stooq is a documented fallback for a ticker that
fails on the primary vendor (both are standard, widely-used free data sources for exactly this
purpose). Vendor selection/fallback is orchestrated in `ingest.py`, not here -- these functions are
single-vendor, single-responsibility, and easy to unit test with mocked network calls.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

RAW_COLUMNS = ["ticker", "price_date", "open", "high", "low", "close", "adj_close", "volume", "source"]


def fetch_from_yfinance(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Download daily OHLCV for one ticker. Returns an empty frame (not an exception) on failure."""
    try:
        raw = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end + dt.timedelta(days=1)).isoformat(),  # yfinance `end` is exclusive
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
        )
    except Exception:
        logger.exception("yfinance download failed for %s", ticker)
        return pd.DataFrame(columns=RAW_COLUMNS)

    if raw is None or raw.empty:
        logger.warning("yfinance returned no data for %s", ticker)
        return pd.DataFrame(columns=RAW_COLUMNS)

    # Newer yfinance returns MultiIndex columns (Price, Ticker) even for a single symbol.
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.xs(ticker, axis=1, level=-1)

    out = pd.DataFrame(
        {
            "ticker": ticker,
            "price_date": pd.to_datetime(raw.index).date,
            "open": raw["Open"].to_numpy(dtype=float),
            "high": raw["High"].to_numpy(dtype=float),
            "low": raw["Low"].to_numpy(dtype=float),
            "close": raw["Close"].to_numpy(dtype=float),
            "adj_close": raw["Adj Close"].to_numpy(dtype=float),
            "volume": raw["Volume"].to_numpy(dtype="int64"),
            "source": "yfinance",
        }
    )
    return out[RAW_COLUMNS]


def fetch_from_stooq(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Fallback vendor. Stooq has no adjusted-close field, so adj_close falls back to raw close
    (flagged downstream via the `source` column so this simplification is traceable, not silent).
    """
    url = f"https://stooq.com/q/d/l/?s={ticker}.US&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception:
        logger.exception("stooq download failed for %s", ticker)
        return pd.DataFrame(columns=RAW_COLUMNS)

    from io import StringIO

    text = resp.text.strip()
    if not text or text.startswith("No data") or "Date,Open" not in text:
        logger.warning("stooq returned no data for %s", ticker)
        return pd.DataFrame(columns=RAW_COLUMNS)

    raw = pd.read_csv(StringIO(text))
    if raw.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)

    out = pd.DataFrame(
        {
            "ticker": ticker,
            "price_date": pd.to_datetime(raw["Date"]).dt.date,
            "open": raw["Open"].astype(float),
            "high": raw["High"].astype(float),
            "low": raw["Low"].astype(float),
            "close": raw["Close"].astype(float),
            "adj_close": raw["Close"].astype(float),  # stooq has no split/div-adjusted series
            "volume": raw["Volume"].astype("int64"),
            "source": "stooq",
        }
    )
    return out[RAW_COLUMNS]
