// Model Comparison -- where do Historical, Parametric, and Monte Carlo VaR disagree, and how has
// that disagreement evolved over time?

import { api, getLatestRiskRun } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { renderDataTable } from "../components/DataTable.js";
import { emptyState, skeletonChart, skeletonTable } from "../components/States.js";
import { lineChart, themeTokens } from "../components/Charts.js";
import { fmtPct, methodLabel } from "../format.js";

const METHODS = ["historical", "parametric", "monte_carlo"];

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Model Comparison" }) + emptyState({ icon: "compare", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Model Comparison", subtitle: "Historical vs. Parametric vs. Monte Carlo VaR, current values and over time." })}
    <div class="grid grid-cols-12">
      <div class="col-span-12 card">
        <div class="card-header"><h3>95% VaR by Method Over Time</h3><span class="card-hint">Where and when do the models diverge?</span></div>
        <div class="card-body" id="mc-chart">${skeletonChart()}</div>
      </div>
      <div class="col-span-12">
        <div class="section-title">Current Snapshot &amp; Divergence</div>
        <div class="section-hint">Spread = max method − min method, at the latest risk run.</div>
        <div id="mc-table">${skeletonTable(3)}</div>
      </div>
    </div>`;

  let riskRun, history;
  try {
    [riskRun, history] = await Promise.all([getLatestRiskRun(portfolioId), api.getRiskHistory(portfolioId)]);
  } catch (err) {
    document.getElementById("mc-chart").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load risk data", desc: err.message });
    return;
  }
  if (!riskRun) {
    document.getElementById("mc-chart").innerHTML = emptyState({ icon: "compare", title: "No risk runs yet" });
    document.getElementById("mc-table").innerHTML = "";
    return;
  }

  renderChart(history);
  renderTable(riskRun);
}

function renderChart(history) {
  const el = document.getElementById("mc-chart");
  if (history.points.length === 0) {
    el.innerHTML = emptyState({ icon: "compare", title: "No risk history yet" });
    return;
  }
  const t = themeTokens();
  const dates = history.points.map((p) => p.as_of_date);
  const colors = [t.series1, t.series2, t.series3];
  const series = METHODS.map((m, i) => ({
    name: methodLabel(m), x: dates, y: history.points.map((p) => p.var?.[m]?.["0.95"] ?? null), color: colors[i],
    hovertemplate: "%{y:.2%}<extra>" + methodLabel(m) + "</extra>",
  }));
  el.innerHTML = "";
  lineChart(el, series, { yaxis: { tickformat: ".1%" } });
}

function renderTable(riskRun) {
  const confidences = new Set();
  Object.values(riskRun.var).forEach((byConf) => Object.keys(byConf).forEach((c) => confidences.add(c)));
  const rows = [...confidences].sort().map((conf) => {
    const values = METHODS.map((m) => riskRun.var[m]?.[conf]).filter((v) => v != null);
    const spread = values.length > 1 ? Math.max(...values) - Math.min(...values) : null;
    return {
      confidence: conf,
      historical: riskRun.var.historical?.[conf] ?? null,
      parametric: riskRun.var.parametric?.[conf] ?? null,
      monte_carlo: riskRun.var.monte_carlo?.[conf] ?? null,
      spread,
    };
  });

  const columns = [
    { key: "confidence", label: "Confidence", align: "left", render: (r) => `${Math.round(parseFloat(r.confidence) * 100)}%` },
    { key: "historical", label: "Historical VaR", render: (r) => fmtPct(r.historical) },
    { key: "parametric", label: "Parametric VaR", render: (r) => fmtPct(r.parametric) },
    { key: "monte_carlo", label: "Monte Carlo VaR", render: (r) => fmtPct(r.monte_carlo) },
    { key: "spread", label: "Spread", render: (r) => (r.spread != null ? `<span class="${r.spread > 0.005 ? "cell-negative" : ""}">${fmtPct(r.spread)}</span>` : "–") },
  ];
  renderDataTable("mc-table", { columns, rows, rowKey: (r) => r.confidence });
}
