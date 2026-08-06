"""Chart generation for HTML reports: matplotlib (Agg backend, no display needed) -> base64 PNG
embedded directly in the HTML via a data: URI. No JS charting library needed -- keeps the report a
single self-contained HTML file.
"""

from __future__ import annotations

import base64
import datetime as dt
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def decomposition_bar_chart(tickers: list[str], component_vars: list[float]) -> str:
    """Horizontal bar chart, sorted descending by contribution (blueprint Section 17.6)."""
    pairs = sorted(zip(tickers, component_vars, strict=True), key=lambda p: p[1], reverse=True)
    sorted_tickers = [p[0] for p in pairs]
    sorted_values = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(tickers))))
    colors = ["#c0392b" if v >= 0 else "#2980b9" for v in sorted_values]
    ax.barh(sorted_tickers, sorted_values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Component VaR")
    ax.set_title("Risk Decomposition -- Component VaR by Position")
    ax.axvline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    return _fig_to_base64(fig)


def exception_series_chart(
    dates: list[dt.date], var_forecasts: list[float], realised_pnls: list[float], is_exception: list[bool]
) -> str:
    """VaR forecast band + realised P&L scatter, breaches highlighted (blueprint Section 17.7 --
    "probably the most important visual in the whole report")."""
    # mypy's matplotlib stubs don't accept a plain list[date] for x -- these plot fine at runtime
    # (matplotlib handles datetime.date natively); cast to satisfy the type checker.
    import numpy as np

    x = np.asarray(dates)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, [-v for v in var_forecasts], color="#c0392b", linewidth=1.2, label="-VaR forecast (loss threshold)")
    ax.plot(x, [v for v in var_forecasts], color="#c0392b", linewidth=0.6, linestyle="--", alpha=0.4)

    normal_x = np.asarray([d for d, e in zip(dates, is_exception, strict=True) if not e])
    normal_y = [p for p, e in zip(realised_pnls, is_exception, strict=True) if not e]
    breach_x = np.asarray([d for d, e in zip(dates, is_exception, strict=True) if e])
    breach_y = [p for p, e in zip(realised_pnls, is_exception, strict=True) if e]

    ax.scatter(normal_x, normal_y, s=10, color="#2c3e50", label="Realised return", zorder=3)
    ax.scatter(breach_x, breach_y, s=40, color="#e74c3c", marker="x", label="Exception (breach)", zorder=4)

    ax.axhline(0, color="grey", linewidth=0.5)
    ax.set_title("Backtest: VaR Forecast vs. Realised Return")
    ax.set_ylabel("Return")
    ax.legend(loc="lower left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_base64(fig)


def stress_comparison_chart(scenario_names: list[str], pnl_pcts: list[float]) -> str:
    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.5 * len(scenario_names))))
    colors = ["#c0392b" if v < 0 else "#27ae60" for v in pnl_pcts]
    ax.barh(scenario_names, [v * 100 for v in pnl_pcts], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Portfolio P&L (%)")
    ax.set_title("Stress Scenario Comparison")
    ax.axvline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    return _fig_to_base64(fig)


def model_comparison_chart(methods: list[str], var_values: list[float], confidence: float) -> str:
    fig, ax = plt.subplots(figsize=(5, 3.5))
    colors = ["#2980b9", "#8e44ad", "#16a085"]
    ax.bar(methods, var_values, color=colors[: len(methods)])
    ax.set_ylabel("VaR")
    ax.set_title(f"VaR by Methodology ({confidence:.0%} confidence)")
    fig.tight_layout()
    return _fig_to_base64(fig)
