// Portfolio Risk & Stress-Testing Engine -- dashboard frontend.
// Vanilla JS + Plotly (CDN). No build step, no framework -- deliberately (blueprint Section 18:
// "the content/structure matters far more than the charting library choice").

const state = {
  portfolios: [],
  currentPortfolioId: null,
  currentRiskRunId: null,
  currentBacktestId: null,
};

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}

function fmtPct(x, digits = 2) {
  return x === null || x === undefined || Number.isNaN(x) ? "--" : `${(x * 100).toFixed(digits)}%`;
}
function fmtMoney(x) {
  return x === null || x === undefined ? "--" : `$${Math.round(x).toLocaleString()}`;
}
function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

// ---------- Tabs ----------
// Deep-linkable: the active tab is reflected in the URL hash (#backtesting, etc.) so a link to a
// specific view can be shared/bookmarked, and the back/forward buttons work.

function activateTab(tabName) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
  if (!btn) return;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(`tab-${tabName}`).classList.add("active");
  loadTab(tabName);
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.location.hash = btn.dataset.tab;
    });
  });
  window.addEventListener("hashchange", () => {
    const tab = window.location.hash.replace("#", "");
    if (tab) activateTab(tab);
  });
}

function activeTab() {
  return document.querySelector(".tab-btn.active")?.dataset.tab;
}

// ---------- Portfolio selector ----------

async function loadPortfolios() {
  state.portfolios = await api("/portfolios");
  const select = document.getElementById("portfolio-select");
  select.innerHTML = "";
  if (state.portfolios.length === 0) {
    select.appendChild(el(`<option value="">No portfolios yet</option>`));
    return;
  }
  for (const p of state.portfolios) {
    select.appendChild(el(`<option value="${p.portfolio_id}">${p.name} (#${p.portfolio_id})</option>`));
  }
  select.addEventListener("change", () => {
    state.currentPortfolioId = Number(select.value);
    loadTab(activeTab());
  });
  state.currentPortfolioId = Number(select.value);
}

// ---------- Overview ----------

async function loadOverview() {
  const container = document.getElementById("overview-content");
  if (state.portfolios.length === 0) {
    container.innerHTML = `<div class="empty-state">No portfolios yet. Create one via POST /portfolios.</div>`;
    return;
  }
  const rows = [];
  for (const p of state.portfolios) {
    let latestVar = "--", zone = "--";
    try {
      const history = await api(`/risk/history/${p.portfolio_id}`);
      if (history.points.length > 0) {
        const latest = history.points[history.points.length - 1];
        const hv = latest.var?.historical?.["0.95"];
        latestVar = hv !== undefined ? fmtPct(hv) : "--";
      }
    } catch (e) { /* no risk runs yet */ }
    try {
      const backtests = await api(`/risk/backtest?portfolio_id=${p.portfolio_id}`);
      if (backtests.length > 0) zone = backtests[0].traffic_light_zone;
    } catch (e) { /* no backtests yet */ }
    rows.push(`<tr><td>${p.name}</td><td>${p.base_currency}</td><td>${latestVar}</td><td class="zone-${zone}">${zone.toUpperCase()}</td></tr>`);
  }
  container.innerHTML = `
    <table><tr><th>Portfolio</th><th>Currency</th><th>Latest 95% Hist. VaR</th><th>Traffic Light</th></tr>${rows.join("")}</table>`;
}

// ---------- Portfolio ----------

async function loadPortfolioTab() {
  if (!state.currentPortfolioId) return;
  const detail = await api(`/portfolios/${state.currentPortfolioId}`);
  const tableDiv = document.getElementById("portfolio-table");
  const rows = detail.positions.map((p) => `<tr><td>${p.ticker}</td><td>${p.quantity}</td><td>${p.as_of_date}</td></tr>`).join("");
  tableDiv.innerHTML = `<table><tr><th>Ticker</th><th>Quantity</th><th>As-of</th></tr>${rows || '<tr><td colspan="3">No positions</td></tr>'}</table>`;

  if (detail.positions.length > 0) {
    Plotly.newPlot("portfolio-pie", [{
      type: "pie", labels: detail.positions.map((p) => p.ticker), values: detail.positions.map((p) => p.quantity),
    }], { title: "Position Weights (by quantity)", margin: { t: 40 } }, { responsive: true });
  }
}

// ---------- VaR / CVaR ----------

async function getLatestRiskRunId(portfolioId) {
  const history = await api(`/risk/history/${portfolioId}`);
  if (history.points.length === 0) return null;
  return history.points[history.points.length - 1].risk_run_id;
}

async function loadVarCvarTab() {
  if (!state.currentPortfolioId) return;
  const riskRunId = await getLatestRiskRunId(state.currentPortfolioId);
  const tableDiv = document.getElementById("var-cvar-table");
  if (!riskRunId) {
    tableDiv.innerHTML = `<div class="empty-state">No risk runs yet for this portfolio.</div>`;
    return;
  }
  state.currentRiskRunId = riskRunId;
  const result = await api(`/risk/runs/${riskRunId}`);
  const conf = document.getElementById("confidence-select").value;

  const methods = Object.keys(result.var);
  const rows = methods.map((m) => {
    const v = result.var[m]?.[conf];
    const c = result.cvar[m]?.[conf];
    return `<tr><td>${m}</td><td>${fmtPct(v)}</td><td>${fmtPct(c)}</td></tr>`;
  }).join("");
  tableDiv.innerHTML = `
    <p class="hint">Risk run #${riskRunId} -- as of ${result.as_of_date} -- snapshot ${result.data_snapshot_hash.slice(0, 12)}...</p>
    <table><tr><th>Method</th><th>VaR</th><th>CVaR</th></tr>${rows}</table>`;

  Plotly.newPlot("var-cvar-chart", [
    { x: methods, y: methods.map((m) => result.var[m]?.[conf] ?? 0), type: "bar", name: "VaR" },
    { x: methods, y: methods.map((m) => result.cvar[m]?.[conf] ?? 0), type: "bar", name: "CVaR" },
  ], { title: `VaR vs CVaR @ ${(conf * 100).toFixed(0)}%`, barmode: "group", margin: { t: 40 } }, { responsive: true });
}

// ---------- Model Comparison ----------

async function loadModelComparisonTab() {
  if (!state.currentPortfolioId) return;
  const chartDiv = document.getElementById("model-comparison-chart");
  const history = await api(`/risk/history/${state.currentPortfolioId}`);
  if (history.points.length === 0) {
    chartDiv.innerHTML = `<div class="empty-state">No risk history yet.</div>`;
    return;
  }
  const dates = history.points.map((p) => p.as_of_date);
  const methods = ["historical", "parametric", "monte_carlo"];
  const traces = methods.map((m) => ({
    x: dates, y: history.points.map((p) => p.var[m]?.["0.95"] ?? null),
    type: "scatter", mode: "lines+markers", name: m,
  }));
  Plotly.newPlot(chartDiv, traces, { title: "95% VaR by Method Over Time", margin: { t: 40 } }, { responsive: true });
}

// ---------- Backtesting ----------

async function loadBacktestingTab() {
  if (!state.currentPortfolioId) return;
  const summaryDiv = document.getElementById("backtest-summary");
  const chartDiv = document.getElementById("exception-chart");
  const backtests = await api(`/risk/backtest?portfolio_id=${state.currentPortfolioId}`);
  if (backtests.length === 0) {
    summaryDiv.innerHTML = `<div class="empty-state">No backtests yet for this portfolio.</div>`;
    chartDiv.innerHTML = "";
    return;
  }
  const summary = backtests[0];
  state.currentBacktestId = summary.backtest_id;
  const detail = await api(`/risk/backtest/${summary.backtest_id}`);

  summaryDiv.innerHTML = `
    <div class="stat-row">
      <div class="stat"><div class="label">Method / Confidence</div><div class="value">${detail.method} / ${(detail.confidence_level * 100).toFixed(0)}%</div></div>
      <div class="stat"><div class="label">Observations</div><div class="value">${detail.num_observations}</div></div>
      <div class="stat"><div class="label">Exceptions</div><div class="value">${detail.num_exceptions}</div></div>
      <div class="stat"><div class="label">Traffic Light</div><div class="value zone-${detail.traffic_light_zone}">${detail.traffic_light_zone.toUpperCase()}</div></div>
    </div>
    <table>
      <tr><th>Test</th><th>Statistic</th><th>p-value</th><th>Result</th></tr>
      <tr><td>Kupiec POF</td><td>${detail.kupiec_stat.toFixed(3)}</td><td>${detail.kupiec_pvalue.toFixed(4)}</td><td class="${detail.kupiec_pass ? 'pass' : 'fail'}">${detail.kupiec_pass ? 'PASS' : 'FAIL'}</td></tr>
      ${detail.christoffersen_stat !== null ? `<tr><td>Christoffersen</td><td>${detail.christoffersen_stat.toFixed(3)}</td><td>${detail.christoffersen_pvalue.toFixed(4)}</td><td class="${detail.christoffersen_pass ? 'pass' : 'fail'}">${detail.christoffersen_pass ? 'PASS' : 'FAIL'}</td></tr>` : ""}
    </table>`;

  const dates = detail.exceptions.map((e) => e.as_of_date);
  Plotly.newPlot(chartDiv, [
    { x: dates, y: detail.exceptions.map((e) => -e.var_forecast), type: "scatter", mode: "lines", name: "-VaR forecast", line: { color: "#c0392b" } },
    { x: dates, y: detail.exceptions.map((e) => e.var_forecast), type: "scatter", mode: "lines", name: "+VaR forecast", line: { color: "#c0392b", dash: "dot" } },
    { x: dates, y: detail.exceptions.map((e) => e.realised_return), type: "scatter", mode: "markers", name: "Realised return",
      marker: { color: detail.exceptions.map((e) => (e.is_exception ? "#e74c3c" : "#2c3e50")), size: detail.exceptions.map((e) => (e.is_exception ? 9 : 5)) } },
  ], { title: "VaR Forecast vs Realised Return (breaches in red)", margin: { t: 40 } }, { responsive: true });
}

// ---------- Stress Testing ----------

async function loadStressTab() {
  if (!state.currentPortfolioId) return;
  const tableDiv = document.getElementById("stress-table");
  const chartDiv = document.getElementById("stress-chart");
  const runs = await api(`/stress/runs?portfolio_id=${state.currentPortfolioId}`);
  if (runs.length === 0) {
    tableDiv.innerHTML = `<div class="empty-state">No stress runs yet for this portfolio.</div>`;
    chartDiv.innerHTML = "";
    return;
  }
  const rows = runs.map((r) => `<tr><td>${r.scenario_name}</td><td>${fmtMoney(r.portfolio_pnl)}</td><td>${fmtPct(r.portfolio_pnl_pct)}</td></tr>`).join("");
  tableDiv.innerHTML = `<table><tr><th>Scenario</th><th>P&amp;L</th><th>P&amp;L %</th></tr>${rows}</table>`;

  Plotly.newPlot(chartDiv, [{
    y: runs.map((r) => r.scenario_name), x: runs.map((r) => r.portfolio_pnl_pct * 100),
    type: "bar", orientation: "h", marker: { color: runs.map((r) => (r.portfolio_pnl_pct < 0 ? "#c0392b" : "#27ae60")) },
  }], { title: "Stress Scenario P&L (%)", margin: { t: 40, l: 180 } }, { responsive: true });
}

// ---------- Risk Decomposition ----------

async function loadDecompositionTab() {
  if (!state.currentPortfolioId) return;
  const chartDiv = document.getElementById("decomposition-chart");
  const riskRunId = state.currentRiskRunId || (await getLatestRiskRunId(state.currentPortfolioId));
  if (!riskRunId) {
    chartDiv.innerHTML = `<div class="empty-state">No risk runs yet.</div>`;
    return;
  }
  const result = await api(`/risk/runs/${riskRunId}`);
  const sorted = [...result.decomposition].sort((a, b) => b.component_var - a.component_var);
  Plotly.newPlot(chartDiv, [{
    y: sorted.map((d) => d.ticker), x: sorted.map((d) => d.component_var),
    type: "bar", orientation: "h", marker: { color: "#2980b9" },
  }], { title: "Component VaR by Position", margin: { t: 40 }, yaxis: { autorange: "reversed" } }, { responsive: true });
}

// ---------- Historical Risk ----------

async function loadHistoricalTab() {
  if (!state.currentPortfolioId) return;
  const chartDiv = document.getElementById("historical-chart");
  const history = await api(`/risk/history/${state.currentPortfolioId}`);
  if (history.points.length === 0) {
    chartDiv.innerHTML = `<div class="empty-state">No risk history yet.</div>`;
    return;
  }
  const dates = history.points.map((p) => p.as_of_date);
  const traces = ["historical", "parametric", "monte_carlo"].flatMap((m) => [
    { x: dates, y: history.points.map((p) => p.var[m]?.["0.95"] ?? null), type: "scatter", mode: "lines+markers", name: `${m} VaR` },
  ]);
  Plotly.newPlot(chartDiv, traces, { title: "VaR History (95%)", margin: { t: 40 } }, { responsive: true });
}

// ---------- Reports ----------

async function loadReportsTab() {
  if (!state.currentPortfolioId) return;
  const tableDiv = document.getElementById("reports-table");
  const reports = await api(`/reports?portfolio_id=${state.currentPortfolioId}`);
  if (reports.length === 0) {
    tableDiv.innerHTML = `<div class="empty-state">No reports generated yet. Reports are generated automatically by the daily pipeline, or on first view of GET /reports/{risk_run_id}.</div>`;
    return;
  }
  const rows = reports.map((r) => `<tr><td>${r.as_of_date}</td><td>${r.status}</td><td>${r.generated_at}</td><td><a class="report-link" href="${API_BASE}/reports/${r.risk_run_id}" target="_blank">View</a></td></tr>`).join("");
  tableDiv.innerHTML = `<table><tr><th>As-of Date</th><th>Status</th><th>Generated At</th><th>Link</th></tr>${rows}</table>`;
}

// ---------- Router ----------

const TAB_LOADERS = {
  overview: loadOverview,
  portfolio: loadPortfolioTab,
  "var-cvar": loadVarCvarTab,
  "model-comparison": loadModelComparisonTab,
  backtesting: loadBacktestingTab,
  stress: loadStressTab,
  decomposition: loadDecompositionTab,
  historical: loadHistoricalTab,
  reports: loadReportsTab,
};

async function loadTab(tab) {
  const loader = TAB_LOADERS[tab];
  if (!loader) return;
  try {
    await loader();
  } catch (e) {
    console.error(`failed to load tab ${tab}:`, e);
  }
}

async function checkHealth() {
  const statusEl = document.getElementById("api-status");
  try {
    const health = await api("/health");
    statusEl.textContent = health.status === "ok" ? "API connected" : "API degraded";
    statusEl.className = health.status === "ok" ? "api-status" : "api-status error";
  } catch (e) {
    statusEl.textContent = "API unreachable";
    statusEl.className = "api-status error";
  }
}

async function main() {
  setupTabs();
  await checkHealth();
  await loadPortfolios();
  document.getElementById("confidence-select").addEventListener("change", () => loadTab("var-cvar"));
  const initialTab = window.location.hash.replace("#", "") || "overview";
  activateTab(initialTab);
}

main();
