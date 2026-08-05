from __future__ import annotations

import pytest

from risk_engine.validation.traffic_light import traffic_light_zone


def test_zero_exceptions_is_green():
    assert traffic_light_zone(250, 0, 0.99) == "green"


def test_basel_canonical_boundaries_99pct_250days():
    # Canonical Basel table for 99%/250-day: green through 4, amber 5-9, red 10+.
    for n in range(0, 5):
        assert traffic_light_zone(250, n, 0.99) == "green", f"n={n} should be green"
    for n in range(5, 10):
        assert traffic_light_zone(250, n, 0.99) == "amber", f"n={n} should be amber"
    for n in (10, 15, 20):
        assert traffic_light_zone(250, n, 0.99) == "red", f"n={n} should be red"


def test_more_exceptions_than_expected_moves_toward_red():
    green = traffic_light_zone(250, 2, 0.99)
    red = traffic_light_zone(250, 25, 0.99)
    assert green == "green"
    assert red == "red"


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        traffic_light_zone(0, 0, 0.99)
    with pytest.raises(ValueError):
        traffic_light_zone(100, 101, 0.99)
