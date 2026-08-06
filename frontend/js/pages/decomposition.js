// Risk Decomposition -- Component VaR by position (sums exactly to total portfolio VaR),
// Marginal VaR, and % contribution -- making concentration of risk immediately visible.

import { getLatestRiskRun } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { metricCard } from "../components/MetricCard.js";
import { renderDataTable } from "../components/DataTable.js";
import { emptyState, skeletonChart, skeletonTable } from "../components/States.js";
import { horizontalBarChart } from "../components/Charts.js";
import { fmtPct } from "../format.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Risk Decomposition" }) + emptyState({ icon: "decomposition", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Risk Decomposition", subtitle: "Component VaR by position — additive by construction, sums exactly to total portfolio VaR." })}
    <div id="dc-metrics"></div>
    <div class="grid grid-cols-12">
      <div class="col-span-7 card">
        <div class="card-header"><h3>Component VaR by Position</h3></div>
        <div class="card-body" id="dc-chart">${skeletonChart()}</div>
      </div>
      <div class="col-span-5">
        <div class="section-title">Detail</div>
        <div id="dc-table">${skeletonTable(6)}</div>
      </div>
    </div>`;

  let riskRun;
  try {
    riskRun = await getLatestRiskRun(portfolioId);
  } catch (err) {
    document.getElementById("dc-chart").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load decomposition", desc: err.message });
    return;
  }
  if (!riskRun || riskRun.decomposition.length === 0) {
    document.getElementById("dc-chart").innerHTML = emptyState({ icon: "decomposition", title: "No decomposition available", desc: "Trigger a risk run for this portfolio to compute Component/Marginal VaR." });
    document.getElementById("dc-table").innerHTML = "";
    return;
  }

  const sorted = [...riskRun.decomposition].sort((a, b) => b.component_var - a.component_var);
  const total = sorted.reduce((sum, d) => sum + d.component_var, 0);

  document.getElementById("dc-metrics").innerHTML = `<div class="grid grid-cols-3">${[
    metricCard({ label: "Portfolio VaR (sum of components)", value: fmtPct(total), hero: true }),
    metricCard({ label: "Largest Contributor", value: sorted[0].ticker, mono: false, sub: fmtPct(sorted[0].pct_contribution) + " of total risk" }),
    metricCard({ label: "Positions", value: String(sorted.length), sub: "in decomposition" }),
  ].join("")}</div>`;

  const el = document.getElementById("dc-chart");
  el.innerHTML = "";
  horizontalBarChart(el, sorted.map((d) => ({ label: d.ticker, value: d.component_var })), { valueFormat: (v) => fmtPct(v) });

  renderDataTable("dc-table", {
    columns: [
      { key: "ticker", label: "Ticker", align: "left", render: (r) => r.ticker },
      { key: "component_var", label: "Component VaR", render: (r) => fmtPct(r.component_var) },
      { key: "marginal_var", label: "Marginal VaR", render: (r) => fmtPct(r.marginal_var) },
      { key: "pct_contribution", label: "% of Risk", render: (r) => fmtPct(r.pct_contribution) },
    ],
    rows: sorted,
    rowKey: (r) => r.ticker,
  });
}
