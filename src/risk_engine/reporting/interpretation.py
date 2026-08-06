"""Plain-English interpretation paragraph, generated from actual calculated values only.

CLAUDE.md / blueprint Section 35 "No Fake Results": never invent a metric. Every sentence here is
built from a number that was actually computed and passed in -- this module contains no
hardcoded example numbers, only conditional English templates.
"""

from __future__ import annotations


def build_interpretation(
    portfolio_name: str,
    var_by_method: dict[str, float],
    cvar_by_method: dict[str, float],
    confidence: float,
    kupiec_pass: bool | None,
    kupiec_pvalue: float | None,
    christoffersen_pass: bool | None,
    christoffersen_pvalue: float | None,
    traffic_light_zone: str | None,
    diversification_benefit_pct: float | None,
) -> str:
    parts: list[str] = []

    if var_by_method:
        method_strs = ", ".join(f"{m} VaR = {v:.2%}" for m, v in sorted(var_by_method.items()))
        parts.append(f"At {confidence:.0%} confidence, {portfolio_name}'s {method_strs}.")

        methods = list(var_by_method)
        if len(methods) >= 2:
            spread = max(var_by_method.values()) - min(var_by_method.values())
            highest = max(var_by_method, key=lambda m: var_by_method[m])
            lowest = min(var_by_method, key=lambda m: var_by_method[m])
            if spread > 0.001:
                parts.append(
                    f"The three methodologies disagree by {spread:.2%} ({highest} highest, {lowest} lowest) "
                    "-- see the Model Comparison section for why (fat tails/skew the parametric model assumes away)."
                )

    if cvar_by_method and var_by_method:
        for method in var_by_method:
            if method in cvar_by_method:
                ratio = cvar_by_method[method] / var_by_method[method] if var_by_method[method] else float("nan")
                parts.append(f"{method.capitalize()} CVaR exceeds VaR by a factor of {ratio:.2f}x, reflecting the severity of losses beyond the VaR threshold.")
                break

    if kupiec_pass is not None and kupiec_pvalue is not None:
        if kupiec_pass:
            parts.append(f"The Kupiec test does not reject the model's coverage (p={kupiec_pvalue:.4f}) -- the exception rate is statistically consistent with the stated confidence level.")
        else:
            parts.append(f"The Kupiec test REJECTS the model's coverage (p={kupiec_pvalue:.4f}) -- the observed exception rate is not statistically consistent with the model's stated confidence level.")

    if christoffersen_pass is not None and christoffersen_pvalue is not None:
        if christoffersen_pass:
            parts.append(f"Exceptions show no significant clustering (Christoffersen p={christoffersen_pvalue:.4f}).")
        else:
            parts.append(f"Exceptions are significantly CLUSTERED (Christoffersen p={christoffersen_pvalue:.4f}) -- the model tends to fail in runs, e.g. during regime shifts.")

    if traffic_light_zone is not None:
        zone_text = {
            "green": "within the expected range (Basel green zone).",
            "amber": "elevated but not conclusively abnormal (Basel amber zone) -- worth monitoring.",
            "red": "well outside the expected range (Basel red zone) -- the model likely needs recalibration.",
        }.get(traffic_light_zone, f"classified {traffic_light_zone}.")
        parts.append(f"The exception count over the backtest window is {zone_text}")

    if diversification_benefit_pct is not None:
        parts.append(f"Diversification reduces portfolio VaR by {diversification_benefit_pct:.1%} relative to the sum of standalone position VaRs.")

    if not parts:
        return "Insufficient data to generate an interpretation for this report."

    return " ".join(parts)
