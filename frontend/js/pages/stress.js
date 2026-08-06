// Stress Testing -- "What happens to this portfolio under extreme market conditions?"

import { api } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { scenarioCard } from "../components/ScenarioCard.js";
import { emptyState, skeletonChart } from "../components/States.js";
import { horizontalBarChart, themeTokens } from "../components/Charts.js";
import { fmtDate } from "../format.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Stress Testing" }) + emptyState({ icon: "stress", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Stress Testing", subtitle: "Historical replay and factor-shock scenarios applied to current portfolio weights." })}
    <div class="card">
      <div class="card-header"><h3>Scenario Comparison</h3><span class="card-hint">Portfolio P&amp;L impact, %</span></div>
      <div class="card-body" id="st-chart">${skeletonChart()}</div>
    </div>
    <div>
      <div class="section-title">Scenario Detail</div>
      <div class="grid grid-cols-3" id="st-cards"></div>
    </div>`;

  let runs, portfolio;
  try {
    [runs, portfolio] = await Promise.all([api.listStressRuns(portfolioId), api.getPortfolio(portfolioId)]);
  } catch (err) {
    document.getElementById("st-chart").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load stress runs", desc: err.message });
    return;
  }
  if (runs.length === 0) {
    document.getElementById("st-chart").innerHTML = emptyState({
      icon: "stress", title: "No stress runs yet for this portfolio",
      desc: "Trigger a stress run via POST /stress/runs against an available scenario (see GET /scenarios).",
    });
    document.getElementById("st-cards").innerHTML = "";
    return;
  }

  // Only the latest run per scenario -- avoids the chart/cards duplicating history entries.
  const latestByScenario = new Map();
  for (const r of runs) {
    const existing = latestByScenario.get(r.scenario_id);
    if (!existing || r.as_of_date > existing.as_of_date) latestByScenario.set(r.scenario_id, r);
  }
  const latestRuns = [...latestByScenario.values()].sort((a, b) => a.portfolio_pnl_pct - b.portfolio_pnl_pct);

  let scenarios = [];
  try {
    scenarios = await api.listScenarios();
  } catch { /* scenario metadata is a nice-to-have; chart/cards still work without it */ }
  const scenarioById = Object.fromEntries(scenarios.map((s) => [s.scenario_id, s]));

  // Plotly.newPlot resolves asynchronously; wait for it before mutating later DOM siblings so a
  // late Plotly internal reflow (it attaches a ResizeObserver under responsive:true) can never
  // land after -- and interact with -- content added afterward.
  await renderChart(latestRuns);
  renderCards(latestRuns, scenarioById, portfolio.base_currency);
}

async function renderChart(runs) {
  const el = document.getElementById("st-chart");
  const t = themeTokens();
  await horizontalBarChart(
    el,
    runs.map((r) => ({ label: r.scenario_name, value: r.portfolio_pnl_pct * 100, color: r.portfolio_pnl_pct < 0 ? t.critical : t.good })),
    { valueFormat: (v) => `${v.toFixed(1)}%` }
  );
}

function renderCards(runs, scenarioById, currency) {
  const cards = runs.map((r) => {
    const scenario = scenarioById[r.scenario_id];
    const dateRange = scenario?.historical_start ? `${fmtDate(scenario.historical_start)} – ${fmtDate(scenario.historical_end)}` : "";
    return scenarioCard({
      name: r.scenario_name,
      description: scenario?.description || "",
      scenarioType: scenario?.scenario_type || "SCENARIO",
      dateRange,
      pnl: r.portfolio_pnl,
      pnlPct: r.portfolio_pnl_pct,
      currency,
    });
  });
  document.getElementById("st-cards").innerHTML = cards.join("");
}
