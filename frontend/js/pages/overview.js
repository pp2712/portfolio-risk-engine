// Overview -- "What is the current risk position of this portfolio?" The landing page for the
// currently selected portfolio (header dropdown). Every metric here is only ever populated from
// real API responses; anything unavailable renders as an explicit empty/neutral state, never a
// guessed number.

import { api, getLatestRiskRun, getLatestBacktest } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { metricCard } from "../components/MetricCard.js";
import { trafficLightBadge, neutralBadge } from "../components/RiskBadge.js";
import { emptyState, skeletonMetricRow, skeletonChart } from "../components/States.js";
import { lineChart, plot, themeTokens } from "../components/Charts.js";
import { fmtMoney, fmtPct, fmtDate, fmtDateTime, fmtConfidenceKey } from "../format.js";
import { setHeaderMeta } from "../components/Header.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Overview" }) + emptyState({
      icon: "wallet",
      title: "No portfolio selected",
      desc: "Create a portfolio via the API to get started -- see docs/API.md.",
    });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Overview", subtitle: "Current risk position for the selected portfolio." })}
    <div id="ov-metrics">${skeletonMetricRow(4)}</div>
    <div class="grid grid-cols-12">
      <div class="col-span-7 card">
        <div class="card-header"><h3>Risk Trend — 90 Days</h3><span class="card-hint">95% VaR by methodology</span></div>
        <div class="card-body" id="ov-trend-chart">${skeletonChart()}</div>
      </div>
      <div class="col-span-5 card">
        <div class="card-header"><h3>Risk vs. Realised P&amp;L</h3><span class="card-hint">Latest backtest window</span></div>
        <div class="card-body" id="ov-pnl-chart">${skeletonChart()}</div>
      </div>
    </div>`;

  let portfolio, riskRun, history, backtest;
  try {
    [portfolio, history] = await Promise.all([api.getPortfolio(portfolioId), api.getRiskHistory(portfolioId)]);
    riskRun = history.points.length ? await api.getRiskRun(history.points[history.points.length - 1].risk_run_id) : null;
    backtest = await getLatestBacktest(portfolioId).catch(() => null);
  } catch (err) {
    console.error(err);
    document.getElementById("ov-metrics").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load portfolio data", desc: err.message });
    return;
  }

  setHeaderMeta({
    asOf: riskRun ? fmtDate(riskRun.as_of_date) : (portfolio.valuation_date ? fmtDate(portfolio.valuation_date) : "–"),
    lastCalculated: riskRun ? fmtDateTime(riskRun.calculated_at) : "–",
  });

  renderMetrics(portfolio, riskRun, backtest);
  renderTrendChart(history);
  renderPnlChart(backtest);
}

function renderMetrics(portfolio, riskRun, backtest) {
  const currency = portfolio.base_currency;
  const cards = [];

  cards.push(
    metricCard({
      label: "Portfolio Value",
      value: portfolio.portfolio_value != null ? fmtMoney(portfolio.portfolio_value, currency) : "–",
      sub: portfolio.valuation_date ? `as of ${fmtDate(portfolio.valuation_date)}` : "no valuation yet",
      hero: true,
    })
  );

  if (riskRun) {
    const var95 = riskRun.var?.historical?.["0.95"];
    const var99 = riskRun.var?.historical?.["0.99"];
    const cvar95 = riskRun.cvar?.historical?.["0.95"];
    cards.push(
      metricCard({ label: "Value at Risk (95%)", value: var95 != null ? fmtPct(var95) : "–", sub: "Historical method", infoTip: "1-day loss not expected to be exceeded 95% of the time." }),
      metricCard({ label: "Value at Risk (99%)", value: var99 != null ? fmtPct(var99) : "–", sub: "Historical method" }),
      metricCard({ label: "Expected Shortfall (95%)", value: cvar95 != null ? fmtPct(cvar95) : "–", sub: "CVaR, historical method", infoTip: "Average loss in the worst 5% of outcomes." }),
      metricCard({ label: "Annualised Volatility", value: riskRun.volatility != null ? fmtPct(riskRun.volatility, { digits: 1 }) : "–", sub: `${riskRun.config.lookback_window_days}-day lookback` }),
      metricCard({ label: "Maximum Drawdown", value: riskRun.max_drawdown != null ? fmtPct(riskRun.max_drawdown, { digits: 1 }) : "–", sub: "over lookback window" })
    );
  }

  cards.push(
    metricCard({
      label: "Risk Status",
      value: backtest ? "" : "–",
      mono: false,
      sub: backtest ? `Kupiec: ${backtest.kupiec_pass ? "pass" : "fail"}` : "no backtest yet",
    })
  );

  document.getElementById("ov-metrics").innerHTML = `<div class="grid grid-cols-4">${cards.join("")}</div>`;

  // Swap the risk-status metric's value slot for a real badge (needs DOM, not just a string).
  const statusCard = document.querySelectorAll("#ov-metrics .metric-card")[cards.length - 1];
  if (statusCard) {
    const valueEl = statusCard.querySelector(".metric-value");
    valueEl.innerHTML = backtest ? trafficLightBadge(backtest.traffic_light_zone) : neutralBadge("NOT YET VALIDATED");
  }
}

function renderTrendChart(history) {
  const el = document.getElementById("ov-trend-chart");
  const points = history.points.slice(-90);
  if (points.length === 0) {
    el.innerHTML = emptyState({ icon: "historical", title: "No risk history yet", desc: "Trigger a risk run for this portfolio to begin building history." });
    return;
  }
  const t = themeTokens();
  const dates = points.map((p) => p.as_of_date);
  const series = [
    { name: "Historical", x: dates, y: points.map((p) => p.var?.historical?.["0.95"] ?? null), color: t.series1 },
    { name: "Parametric", x: dates, y: points.map((p) => p.var?.parametric?.["0.95"] ?? null), color: t.series2 },
    { name: "Monte Carlo", x: dates, y: points.map((p) => p.var?.monte_carlo?.["0.95"] ?? null), color: t.series3 },
  ];
  el.innerHTML = "";
  lineChart(el, series, { yaxis: { tickformat: ".1%" } });
}

function renderPnlChart(backtest) {
  const el = document.getElementById("ov-pnl-chart");
  if (!backtest || backtest.exceptions.length === 0) {
    el.innerHTML = emptyState({ icon: "backtest", title: "No backtest yet", desc: "Run a backtest for this portfolio to see forecast VaR against realised P&L." });
    return;
  }
  const t = themeTokens();
  const recent = backtest.exceptions.slice(-90);
  const dates = recent.map((e) => e.as_of_date);
  el.innerHTML = "";
  plot(
    el,
    [
      { x: dates, y: recent.map((e) => -e.var_forecast), type: "scatter", mode: "lines", name: "VaR threshold", line: { width: 1.5, color: t.warning }, hovertemplate: "VaR: %{y:.2%}<extra></extra>" },
      {
        x: dates, y: recent.map((e) => e.realised_return), type: "scatter", mode: "markers", name: "Realised return",
        marker: {
          size: recent.map((e) => (e.is_exception ? 9 : 5)),
          color: recent.map((e) => (e.is_exception ? t.critical : t.textSecondary)),
          symbol: recent.map((e) => (e.is_exception ? "x" : "circle")),
        },
        hovertemplate: "%{x}<br>Realised: %{y:.2%}<extra></extra>",
      },
    ],
    { yaxis: { tickformat: ".1%" } }
  );
}
