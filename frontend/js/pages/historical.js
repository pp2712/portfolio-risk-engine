// Historical Risk -- how has VaR/CVaR evolved over time for this portfolio? Time filters are
// applied client-side to the real /risk/history series (no separate backend endpoint needed for
// this -- the full series is already returned and is small enough to filter in the browser).

import { api } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { emptyState, skeletonChart } from "../components/States.js";
import { lineChart, themeTokens } from "../components/Charts.js";

const RANGES = [
  { key: "1M", days: 30 },
  { key: "3M", days: 90 },
  { key: "6M", days: 180 },
  { key: "1Y", days: 365 },
  { key: "All", days: null },
];

let activeRange = "3M";
let cachedHistory = null;

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Historical Risk" }) + emptyState({ icon: "historical", title: "No portfolio selected" });
    return;
  }

  const actionsHtml = `
    <div class="segmented" id="range-toggle" role="group" aria-label="Time range">
      ${RANGES.map((r) => `<button data-range="${r.key}" class="${r.key === activeRange ? "active" : ""}">${r.key}</button>`).join("")}
    </div>`;

  container.innerHTML = `
    ${pageHeader({ title: "Historical Risk", subtitle: "VaR / CVaR across all methods over time.", actionsHtml })}
    <div class="card">
      <div class="card-header"><h3>VaR (95%) Over Time</h3></div>
      <div class="card-body" id="hist-var-chart">${skeletonChart()}</div>
    </div>
    <div class="card">
      <div class="card-header"><h3>CVaR (95%) Over Time</h3></div>
      <div class="card-body" id="hist-cvar-chart">${skeletonChart()}</div>
    </div>`;

  document.querySelectorAll("#range-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeRange = btn.dataset.range;
      document.querySelectorAll("#range-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
      renderCharts();
    });
  });

  try {
    cachedHistory = await api.getRiskHistory(portfolioId);
  } catch (err) {
    document.getElementById("hist-var-chart").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load history", desc: err.message });
    return;
  }
  renderCharts();
}

function filteredPoints() {
  if (!cachedHistory || cachedHistory.points.length === 0) return [];
  const range = RANGES.find((r) => r.key === activeRange);
  if (!range.days) return cachedHistory.points;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - range.days);
  return cachedHistory.points.filter((p) => new Date(p.as_of_date) >= cutoff);
}

function renderCharts() {
  const points = filteredPoints();
  const varEl = document.getElementById("hist-var-chart");
  const cvarEl = document.getElementById("hist-cvar-chart");

  if (points.length === 0) {
    const msg = emptyState({ icon: "historical", title: "No risk history in this range", desc: "Try a wider time range, or trigger more risk runs for this portfolio." });
    varEl.innerHTML = msg;
    cvarEl.innerHTML = msg;
    return;
  }

  const t = themeTokens();
  const dates = points.map((p) => p.as_of_date);
  const colors = [t.series1, t.series2, t.series3];
  const methods = [
    { key: "historical", name: "Historical" },
    { key: "parametric", name: "Parametric" },
    { key: "monte_carlo", name: "Monte Carlo" },
  ];

  varEl.innerHTML = "";
  lineChart(varEl, methods.map((m, i) => ({ name: m.name, x: dates, y: points.map((p) => p.var?.[m.key]?.["0.95"] ?? null), color: colors[i] })), { yaxis: { tickformat: ".1%" } });

  cvarEl.innerHTML = "";
  lineChart(cvarEl, methods.map((m, i) => ({ name: m.name, x: dates, y: points.map((p) => p.cvar?.[m.key]?.["0.95"] ?? null), color: colors[i] })), { yaxis: { tickformat: ".1%" } });
}
