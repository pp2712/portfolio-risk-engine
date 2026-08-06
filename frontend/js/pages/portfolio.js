// Portfolio -- positions, weights, market values, and (where a risk run exists) each position's
// contribution to portfolio risk. Concentration (HHI) is shown as a plain number, not a
// fabricated severity tier -- the backend defines no thresholds for it.

import { api, getLatestRiskRun } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { metricCard } from "../components/MetricCard.js";
import { renderDataTable } from "../components/DataTable.js";
import { emptyState, skeletonMetricRow, skeletonTable } from "../components/States.js";
import { horizontalBarChart } from "../components/Charts.js";
import { fmtMoney, fmtPct, fmtDate, fmtNum } from "../format.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Portfolio" }) + emptyState({ icon: "wallet", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Portfolio", subtitle: "Positions, weights, and market exposure." })}
    <div id="pf-metrics">${skeletonMetricRow(3)}</div>
    <div class="grid grid-cols-12">
      <div class="col-span-7">
        <div class="section-title">Positions</div>
        <div class="section-hint">Sortable — click a column header to reorder.</div>
        <div id="pf-table">${skeletonTable(6)}</div>
      </div>
      <div class="col-span-5 card">
        <div class="card-header"><h3>Exposure by Position</h3><span class="card-hint">% of portfolio value</span></div>
        <div class="card-body" id="pf-chart" style="min-height:340px"></div>
      </div>
    </div>`;

  let portfolio, riskRun;
  try {
    portfolio = await api.getPortfolio(portfolioId);
    riskRun = await getLatestRiskRun(portfolioId).catch(() => null);
  } catch (err) {
    document.getElementById("pf-metrics").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load portfolio", desc: err.message });
    return;
  }

  const contributionByTicker = {};
  if (riskRun) {
    for (const d of riskRun.decomposition) contributionByTicker[d.ticker] = d.pct_contribution;
  }

  renderMetrics(portfolio);
  renderTable(portfolio, contributionByTicker);
  renderExposureChart(portfolio);
}

function renderMetrics(portfolio) {
  const cards = [
    metricCard({ label: "Portfolio Value", value: portfolio.portfolio_value != null ? fmtMoney(portfolio.portfolio_value, portfolio.base_currency) : "–", sub: `${portfolio.positions.length} positions`, hero: true }),
    metricCard({ label: "Concentration (HHI)", value: portfolio.concentration_hhi != null ? fmtNum(portfolio.concentration_hhi, 3) : "–", sub: "Herfindahl-Hirschman Index", infoTip: "Sum of squared weights. 1/n = equal-weight; 1.0 = single position. No backend-defined severity threshold, shown as a plain value." }),
    metricCard({ label: "Valuation Date", value: portfolio.valuation_date ? fmtDate(portfolio.valuation_date) : "–", mono: false, sub: portfolio.base_currency }),
  ];
  document.getElementById("pf-metrics").innerHTML = `<div class="grid grid-cols-3">${cards.join("")}</div>`;
}

function renderTable(portfolio, contributionByTicker) {
  const hasValuation = portfolio.positions.some((p) => p.market_value != null);
  const columns = [
    { key: "ticker", label: "Ticker", align: "left", render: (r) => `<span class="ticker-cell"><span class="ticker-swatch" style="background:var(--series-1)"></span>${r.ticker}</span>` },
    { key: "quantity", label: "Quantity", render: (r) => fmtNum(r.quantity, 0) },
    { key: "market_value", label: "Market Value", render: (r) => (r.market_value != null ? fmtMoney(r.market_value, portfolio.base_currency) : "–") },
    {
      key: "weight", label: "Weight",
      render: (r) => {
        if (r.weight == null) return "–";
        const pct = Math.max(0, Math.min(100, r.weight * 100));
        return `<span class="weight-bar-track"><span class="weight-bar-fill" style="width:${pct}%"></span></span>${fmtPct(r.weight)}`;
      },
    },
    {
      key: "contribution", label: "Risk Contribution", sortValue: (r) => contributionByTicker[r.ticker] ?? null,
      render: (r) => (contributionByTicker[r.ticker] != null ? fmtPct(contributionByTicker[r.ticker]) : "–"),
    },
    { key: "as_of_date", label: "As Of", render: (r) => fmtDate(r.as_of_date) },
  ];
  if (!hasValuation) {
    // No price data available -- drop the valuation-dependent columns rather than show a wall of dashes.
    columns.splice(2, 3);
  }
  renderDataTable("pf-table", { columns, rows: portfolio.positions, rowKey: (r) => r.ticker, emptyMessage: "No positions in this portfolio yet." });
}

function renderExposureChart(portfolio) {
  const el = document.getElementById("pf-chart");
  const withWeights = portfolio.positions.filter((p) => p.weight != null);
  if (withWeights.length === 0) {
    el.innerHTML = emptyState({ icon: "portfolio", title: "No valuation data", desc: "Market values aren't available for these positions yet." });
    return;
  }
  const sorted = [...withWeights].sort((a, b) => b.weight - a.weight);
  const seriesColor = getComputedStyle(document.documentElement).getPropertyValue("--series-1").trim();
  horizontalBarChart(
    el,
    sorted.map((p) => ({ label: p.ticker, value: p.weight * 100, color: seriesColor })),
    { valueFormat: (v) => `${v.toFixed(1)}%` }
  );
}
