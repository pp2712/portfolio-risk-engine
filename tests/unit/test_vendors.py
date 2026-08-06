"""Unit tests for vendor adapters using mocked network calls -- no real HTTP/yfinance traffic.
Real end-to-end vendor behaviour is exercised by scripts/ingest_universe.py (manual/CI-excluded,
see docs/TESTING.md for why network calls aren't part of the automated suite).
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock, patch

import pandas as pd

from risk_engine.data.vendors import RAW_COLUMNS, fetch_from_stooq, fetch_from_yfinance


def _make_yf_frame(multiindex: bool) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=3)
    data = {
        "Open": [100.0, 101.0, 102.0], "High": [101.0, 102.0, 103.0], "Low": [99.0, 100.0, 101.0],
        "Close": [100.5, 101.5, 102.5], "Adj Close": [100.0, 101.0, 102.0], "Volume": [1000, 1100, 1200],
    }
    df = pd.DataFrame(data, index=dates)
    if multiindex:
        df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]])
    return df


@patch("risk_engine.data.vendors.yf.download")
def test_fetch_from_yfinance_flat_columns(mock_download):
    mock_download.return_value = _make_yf_frame(multiindex=False)
    result = fetch_from_yfinance("AAPL", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert list(result.columns) == RAW_COLUMNS
    assert len(result) == 3
    assert result["source"].iloc[0] == "yfinance"
    assert result["adj_close"].iloc[0] == 100.0


@patch("risk_engine.data.vendors.yf.download")
def test_fetch_from_yfinance_handles_multiindex_columns(mock_download):
    mock_download.return_value = _make_yf_frame(multiindex=True)
    result = fetch_from_yfinance("AAPL", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert len(result) == 3
    assert result["adj_close"].iloc[0] == 100.0


@patch("risk_engine.data.vendors.yf.download")
def test_fetch_from_yfinance_empty_response_returns_empty_frame(mock_download):
    mock_download.return_value = pd.DataFrame()
    result = fetch_from_yfinance("BOGUS", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert result.empty
    assert list(result.columns) == RAW_COLUMNS


@patch("risk_engine.data.vendors.yf.download")
def test_fetch_from_yfinance_exception_returns_empty_frame_not_raise(mock_download):
    mock_download.side_effect = RuntimeError("network down")
    result = fetch_from_yfinance("AAPL", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert result.empty


@patch("risk_engine.data.vendors.requests.get")
def test_fetch_from_stooq_parses_csv(mock_get):
    csv_text = "Date,Open,High,Low,Close,Volume\n2024-01-02,100,101,99,100.5,1000\n2024-01-03,100.5,102,100,101.5,1100\n"
    mock_response = Mock()
    mock_response.text = csv_text
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = fetch_from_stooq("AAPL", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert len(result) == 2
    assert result["source"].iloc[0] == "stooq"
    # Stooq has no adjusted series -- adj_close falls back to close, documented not silent.
    assert result["adj_close"].iloc[0] == result["close"].iloc[0]


@patch("risk_engine.data.vendors.requests.get")
def test_fetch_from_stooq_no_data_response(mock_get):
    mock_response = Mock()
    mock_response.text = "No data"
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = fetch_from_stooq("BOGUS", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert result.empty


@patch("risk_engine.data.vendors.requests.get")
def test_fetch_from_stooq_http_error_returns_empty_frame(mock_get):
    mock_get.side_effect = ConnectionError("network down")
    result = fetch_from_stooq("AAPL", dt.date(2024, 1, 2), dt.date(2024, 1, 4))
    assert result.empty
