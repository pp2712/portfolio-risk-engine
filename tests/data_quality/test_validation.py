from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from risk_engine.data.validation import validate_raw_prices


def _row(ticker="AAPL", price_date=dt.date(2024, 1, 2), close=100.0, adj_close=100.0, volume=1000):
    return {
        "ticker": ticker,
        "price_date": price_date,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "adj_close": adj_close,
        "volume": volume,
        "source": "yfinance",
    }


def test_valid_rows_pass_through_unchanged():
    df = pd.DataFrame([_row(price_date=dt.date(2024, 1, 2)), _row(price_date=dt.date(2024, 1, 3))])
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    assert len(result.clean) == 2
    assert result.issues == []


def test_future_date_is_rejected():
    df = pd.DataFrame([_row(price_date=dt.date(2099, 1, 1))])
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    assert result.clean.empty
    assert result.issues[0].issue_type == "future_date"


def test_negative_price_is_rejected():
    df = pd.DataFrame([_row(close=-5.0, adj_close=-5.0)])
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    assert result.clean.empty
    assert result.issues[0].issue_type == "invalid_price"


def test_null_price_is_rejected():
    df = pd.DataFrame([_row(adj_close=None)])
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    assert result.clean.empty
    assert result.issues[0].issue_type == "invalid_price"


def test_exact_duplicate_row_is_deduplicated():
    df = pd.DataFrame([_row(), _row()])
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    assert len(result.clean) == 1
    assert result.issues[0].issue_type == "duplicate_row"


def test_large_move_is_flagged_but_not_removed():
    df = pd.DataFrame(
        [
            _row(price_date=dt.date(2024, 1, 2), close=100.0, adj_close=100.0),
            _row(price_date=dt.date(2024, 1, 3), close=135.0, adj_close=135.0),  # +35% -- crash/melt-up
        ]
    )
    result = validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
    # Both rows kept -- this is the core "flag don't discard" behaviour.
    assert len(result.clean) == 2
    assert any(i.issue_type == "large_move_flagged" for i in result.issues)


def test_missing_required_column_raises():
    df = pd.DataFrame([{"ticker": "AAPL", "price_date": dt.date(2024, 1, 2)}])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_raw_prices(df, as_of=dt.date(2024, 1, 4))
