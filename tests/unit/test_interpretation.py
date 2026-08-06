from __future__ import annotations

from risk_engine.reporting.interpretation import build_interpretation


def test_interpretation_includes_all_var_methods():
    text = build_interpretation(
        portfolio_name="Test Portfolio",
        var_by_method={"historical": 0.034, "parametric": 0.021, "monte_carlo": 0.033},
        cvar_by_method={"historical": 0.048},
        confidence=0.95,
        kupiec_pass=True, kupiec_pvalue=0.34,
        christoffersen_pass=True, christoffersen_pvalue=0.5,
        traffic_light_zone="green",
        diversification_benefit_pct=0.15,
    )
    assert "historical VaR = 3.40%" in text
    assert "parametric VaR = 2.10%" in text
    assert "95%" in text


def test_interpretation_flags_model_disagreement():
    text = build_interpretation(
        portfolio_name="P", var_by_method={"historical": 0.05, "parametric": 0.02, "monte_carlo": 0.048},
        cvar_by_method={}, confidence=0.95, kupiec_pass=None, kupiec_pvalue=None,
        christoffersen_pass=None, christoffersen_pvalue=None, traffic_light_zone=None, diversification_benefit_pct=None,
    )
    assert "disagree" in text


def test_interpretation_reports_kupiec_failure_explicitly():
    text = build_interpretation(
        portfolio_name="P", var_by_method={}, cvar_by_method={}, confidence=0.95,
        kupiec_pass=False, kupiec_pvalue=0.001,
        christoffersen_pass=None, christoffersen_pvalue=None, traffic_light_zone=None, diversification_benefit_pct=None,
    )
    assert "REJECTS" in text
    assert "0.0010" in text


def test_interpretation_reports_clustering():
    text = build_interpretation(
        portfolio_name="P", var_by_method={}, cvar_by_method={}, confidence=0.95,
        kupiec_pass=None, kupiec_pvalue=None,
        christoffersen_pass=False, christoffersen_pvalue=0.002,
        traffic_light_zone=None, diversification_benefit_pct=None,
    )
    assert "CLUSTERED" in text


def test_interpretation_handles_all_none_gracefully():
    text = build_interpretation(
        portfolio_name="P", var_by_method={}, cvar_by_method={}, confidence=0.95,
        kupiec_pass=None, kupiec_pvalue=None, christoffersen_pass=None, christoffersen_pvalue=None,
        traffic_light_zone=None, diversification_benefit_pct=None,
    )
    assert text  # never empty/crash
    assert "Insufficient" in text


def test_interpretation_never_contains_hardcoded_placeholder_numbers():
    # A regression guard against accidentally reintroducing a fabricated example value.
    text = build_interpretation(
        portfolio_name="P", var_by_method={"historical": 0.0271}, cvar_by_method={},
        confidence=0.99, kupiec_pass=True, kupiec_pvalue=0.77,
        christoffersen_pass=True, christoffersen_pvalue=0.61, traffic_light_zone="green",
        diversification_benefit_pct=0.22,
    )
    assert "2.71%" in text  # the actual input value must appear
    assert "12345" not in text and "99999" not in text
