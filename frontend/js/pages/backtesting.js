// Backtesting -- "Does our VaR model actually work?" The most important page in the application:
// given significantly more visual emphasis (hero exception rate stat, full-width breach chart,
// three statistical-test cards with real interpretation, never a bare PASS/FAIL label alone).

import { api } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { metricCard } from "../components/MetricCard.js";
import { trafficLightBadge } from "../components/RiskBadge.js";
import { testResultCard } from "../components/TestResultCard.js";
import { emptyState, skeletonMetricRow, skeletonChart } from "../components/States.js";
import { exceptionChart } from "../components/Charts.js";
import { fmtPct, fmtDate, methodLabel } from "../format.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Backtesting" }) + emptyState({ icon: "backtest", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Backtesting", subtitle: "Rolling walk-forward validation: does the VaR forecast actually hold up against realised outcomes?" })}
    <div id="bt-metrics">${skeletonMetricRow(4)}</div>
    <div class="card">
      <div class="card-header"><h3>VaR Forecast vs. Realised Return</h3><span class="card-hint">Breaches (exceptions) marked in red</span></div>
      <div class="card-body" id="bt-chart">${skeletonChart()}</div>
    </div>
    <div>
      <div class="section-title">Statistical Validation</div>
      <div class="section-hint">Each test's null hypothesis, statistic, p-value, and what the result actually means.</div>
      <div class="grid grid-cols-3" id="bt-tests"></div>
    </div>`;

  let backtests;
  try {
    backtests = await api.listBacktests(portfolioId);
  } catch (err) {
    document.getElementById("bt-metrics").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load backtests", desc: err.message });
    return;
  }
  if (backtests.length === 0) {
    document.getElementById("bt-metrics").innerHTML = emptyState({
      icon: "backtest", title: "No backtests yet for this portfolio",
      desc: "Trigger a rolling backtest via POST /risk/backtest to validate a VaR model against realised history.",
    });
    document.getElementById("bt-chart").innerHTML = "";
    document.getElementById("bt-tests").innerHTML = "";
    return;
  }

  const detail = await api.getBacktest(backtests[0].backtest_id);
  renderMetrics(detail);
  renderChart(detail);
  renderTests(detail);
}

function renderMetrics(bt) {
  const expectedRate = 1 - bt.confidence_level;
  const observedRate = bt.num_exceptions / bt.num_observations;
  const cards = [
    metricCard({ label: "Exception Rate", value: fmtPct(observedRate, { digits: 2 }), sub: `${bt.num_exceptions} of ${bt.num_observations} observations`, hero: true }),
    metricCard({ label: "Expected Rate", value: fmtPct(expectedRate, { digits: 2 }), sub: `at ${(bt.confidence_level * 100).toFixed(0)}% confidence` }),
    metricCard({ label: "Method", value: methodLabel(bt.method), mono: false, sub: `${fmtDate(bt.window_start)} – ${fmtDate(bt.window_end)}` }),
    metricCard({ label: "Traffic Light", value: "", sub: "Basel-style binomial classification" }),
  ];
  document.getElementById("bt-metrics").innerHTML = `<div class="grid grid-cols-4">${cards.join("")}</div>`;
  const zoneCard = document.querySelectorAll("#bt-metrics .metric-card")[3];
  zoneCard.querySelector(".metric-value").innerHTML = trafficLightBadge(bt.traffic_light_zone);
}

function renderChart(bt) {
  const el = document.getElementById("bt-chart");
  if (bt.exceptions.length === 0) {
    el.innerHTML = emptyState({ icon: "backtest", title: "No exception series recorded" });
    return;
  }
  el.innerHTML = "";
  exceptionChart(el, {
    dates: bt.exceptions.map((e) => e.as_of_date),
    varForecast: bt.exceptions.map((e) => e.var_forecast),
    realised: bt.exceptions.map((e) => e.realised_return),
    isException: bt.exceptions.map((e) => e.is_exception),
  }, { margin: { t: 16, r: 24, b: 40, l: 56 } });
}

function renderTests(bt) {
  const cards = [
    testResultCard({ key: "kupiec", name: "Kupiec POF Test", statistic: bt.kupiec_stat, pvalue: bt.kupiec_pvalue, pass: bt.kupiec_pass }),
  ];
  if (bt.christoffersen_stat !== null) {
    cards.push(testResultCard({ key: "christoffersen", name: "Christoffersen Independence", statistic: bt.christoffersen_stat, pvalue: bt.christoffersen_pvalue, pass: bt.christoffersen_pass }));
  }
  if (bt.conditional_coverage_stat !== null) {
    cards.push(testResultCard({ key: "conditional_coverage", name: "Conditional Coverage", statistic: bt.conditional_coverage_stat, pvalue: bt.conditional_coverage_pvalue, pass: bt.conditional_coverage_pass }));
  }
  // #bt-tests is a plain grid-cols-3 container -- each card already occupies one implicit column,
  // no col-span wrapper needed (col-span-* is scaled for the 12-col grid used elsewhere).
  document.getElementById("bt-tests").innerHTML = cards.join("");
}
