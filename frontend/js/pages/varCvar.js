// VaR / CVaR -- the three methodologies side by side at a selectable confidence level.

import { getLatestRiskRun } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { renderDataTable } from "../components/DataTable.js";
import { emptyState, skeletonChart, skeletonTable } from "../components/States.js";
import { groupedBarChart } from "../components/Charts.js";
import { fmtPct, fmtDateTime, methodLabel } from "../format.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "VaR / CVaR" }) + emptyState({ icon: "risk", title: "No portfolio selected" });
    return;
  }

  const actionsHtml = `
    <div class="segmented" id="conf-toggle" role="group" aria-label="Confidence level">
      <button data-conf="0.95" class="${state.confidenceLevel === "0.95" ? "active" : ""}">95%</button>
      <button data-conf="0.99" class="${state.confidenceLevel === "0.99" ? "active" : ""}">99%</button>
    </div>`;

  container.innerHTML = `
    ${pageHeader({ title: "Value at Risk / CVaR", subtitle: "Three independent methodologies, computed side by side.", actionsHtml })}
    <div class="grid grid-cols-12">
      <div class="col-span-5">
        <div class="section-title">Method Comparison</div>
        <div id="vc-table">${skeletonTable(3)}</div>
      </div>
      <div class="col-span-7 card">
        <div class="card-header"><h3>VaR vs. CVaR by Method</h3></div>
        <div class="card-body" id="vc-chart">${skeletonChart()}</div>
      </div>
    </div>`;

  document.querySelectorAll("#conf-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.confidenceLevel = btn.dataset.conf;
      render(container);
    });
  });

  let riskRun;
  try {
    riskRun = await getLatestRiskRun(portfolioId);
  } catch (err) {
    document.getElementById("vc-table").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load risk data", desc: err.message });
    return;
  }
  if (!riskRun) {
    document.getElementById("vc-table").innerHTML = emptyState({ icon: "risk", title: "No risk runs yet", desc: "Trigger a risk run for this portfolio via POST /risk/runs." });
    document.getElementById("vc-chart").innerHTML = "";
    return;
  }

  renderTable(riskRun);
  renderChart(riskRun);
}

function renderTable(riskRun) {
  const conf = state.confidenceLevel;
  const methods = Object.keys(riskRun.var);
  const rows = methods.map((m) => ({
    method: m,
    var: riskRun.var[m]?.[conf] ?? null,
    cvar: riskRun.cvar[m]?.[conf] ?? null,
  }));

  const columns = [
    { key: "method", label: "Method", align: "left", render: (r) => methodLabel(r.method) },
    { key: "var", label: "VaR", render: (r) => fmtPct(r.var) },
    { key: "cvar", label: "CVaR", render: (r) => fmtPct(r.cvar) },
  ];
  renderDataTable("vc-table", { columns, rows, rowKey: (r) => r.method, emptyMessage: "No VaR results at this confidence level." });

  const el = document.getElementById("vc-table");
  el.insertAdjacentHTML(
    "afterend",
    `<div class="text-xs text-muted" style="margin-top:0.75rem">Risk run #${riskRun.risk_run_id} · calculated ${fmtDateTime(riskRun.calculated_at)} · lookback ${riskRun.config.lookback_window_days}d · MC sims ${riskRun.config.mc_num_simulations.toLocaleString()}, seed ${riskRun.config.mc_random_seed}</div>`
  );
}

function renderChart(riskRun) {
  const conf = state.confidenceLevel;
  const methods = Object.keys(riskRun.var);
  const el = document.getElementById("vc-chart");
  el.innerHTML = "";
  groupedBarChart(el, [
    { name: "VaR", x: methods.map(methodLabel), y: methods.map((m) => riskRun.var[m]?.[conf] ?? null), hovertemplate: "%{y:.2%}<extra>VaR</extra>" },
    { name: "CVaR", x: methods.map(methodLabel), y: methods.map((m) => riskRun.cvar[m]?.[conf] ?? null), hovertemplate: "%{y:.2%}<extra>CVaR</extra>" },
  ], { yaxis: { tickformat: ".1%" } });
}
