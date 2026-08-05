from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from risk_engine.data.returns import build_aligned_return_matrix, compute_returns_for_asset


def test_compute_returns_known_values():
    prices = pd.DataFrame(
        {
            "price_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2), dt.date(2024, 1, 3)],
            "adj_close": [100.0, 110.0, 99.0],
        }
    )
    out = compute_returns_for_asset(prices)

    assert len(out) == 2
    assert out["return_date"].tolist() == [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]

    expected_log = [np.log(110.0 / 100.0), np.log(99.0 / 110.0)]
    expected_simple = [110.0 / 100.0 - 1.0, 99.0 / 110.0 - 1.0]
    np.testing.assert_allclose(out["log_return"].to_numpy(), expected_log, atol=1e-12)
    np.testing.assert_allclose(out["simple_return"].to_numpy(), expected_simple, atol=1e-12)


def test_compute_returns_single_row_is_empty():
    prices = pd.DataFrame({"price_date": [dt.date(2024, 1, 1)], "adj_close": [100.0]})
    out = compute_returns_for_asset(prices)
    assert out.empty


def test_compute_returns_deduplicates_same_date():
    prices = pd.DataFrame(
        {
            "price_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
            "adj_close": [100.0, 100.0, 105.0],
        }
    )
    out = compute_returns_for_asset(prices)
    assert len(out) == 1


def test_aligned_return_matrix_inner_join_drops_partial_dates():
    a = pd.DataFrame(
        {
            "return_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 3), dt.date(2024, 1, 4)],
            "log_return": [0.01, 0.02, 0.03],
            "simple_return": [0.01, 0.02, 0.03],
        }
    )
    # asset b is missing 2024-01-03 (e.g. thinly traded) -- inner join must drop that date entirely
    b = pd.DataFrame(
        {
            "return_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 4)],
            "log_return": [-0.01, 0.04],
            "simple_return": [-0.01, 0.04],
        }
    )
    matrix = build_aligned_return_matrix({"A": a, "B": b})

    assert list(matrix.columns) == ["A", "B"]
    assert len(matrix) == 2
    assert pd.Timestamp("2024-01-03") not in matrix.index


def test_aligned_return_matrix_never_forward_fills():
    # If forward-fill were happening, a NaN gap would silently become a repeated value.
    # Inner join means the gap date simply isn't a row at all -- assert that directly.
    a = pd.DataFrame(
        {
            "return_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 3)],
            "log_return": [0.01, np.nan],
            "simple_return": [0.01, np.nan],
        }
    )
    b = pd.DataFrame(
        {
            "return_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 3)],
            "log_return": [0.02, 0.02],
            "simple_return": [0.02, 0.02],
        }
    )
    matrix = build_aligned_return_matrix({"A": a, "B": b})
    # NaN in A on 01-03 must cause that row to be dropped (dropna), not filled.
    assert len(matrix) == 1
    assert matrix.index[0] == pd.Timestamp("2024-01-02")
