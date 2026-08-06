// Reports -- generated HTML risk reports for the current portfolio.

import { api } from "../api.js";
import { state } from "../state.js";
import { pageHeader } from "../components/PageHeader.js";
import { renderDataTable } from "../components/DataTable.js";
import { emptyState, skeletonTable } from "../components/States.js";
import { neutralBadge } from "../components/RiskBadge.js";
import { fmtDate, fmtDateTime } from "../format.js";
import { API_BASE } from "../../config.js";

export async function render(container) {
  const portfolioId = state.currentPortfolioId;
  if (!portfolioId) {
    container.innerHTML = pageHeader({ title: "Reports" }) + emptyState({ icon: "reports", title: "No portfolio selected" });
    return;
  }

  container.innerHTML = `
    ${pageHeader({ title: "Reports", subtitle: "Generated HTML risk reports for this portfolio." })}
    <div id="rp-table">${skeletonTable(5)}</div>`;

  let reports;
  try {
    reports = await api.listReports(portfolioId);
  } catch (err) {
    document.getElementById("rp-table").innerHTML = emptyState({ icon: "alertCircle", title: "Failed to load reports", desc: err.message });
    return;
  }
  if (reports.length === 0) {
    document.getElementById("rp-table").innerHTML = emptyState({
      icon: "reports", title: "No reports generated yet",
      desc: "Reports are generated automatically by the daily pipeline, or on first view of a risk run's report.",
    });
    return;
  }

  renderDataTable("rp-table", {
    columns: [
      { key: "as_of_date", label: "As-Of Date", align: "left", render: (r) => fmtDate(r.as_of_date) },
      { key: "status", label: "Status", render: (r) => neutralBadge(r.status.toUpperCase()) },
      { key: "generated_at", label: "Generated At", render: (r) => fmtDateTime(r.generated_at) },
      { key: "link", label: "", sortable: false, render: (r) => `<a class="btn btn-sm" href="${API_BASE}/reports/${r.risk_run_id}" target="_blank" rel="noopener">View report</a>` },
    ],
    rows: reports,
    rowKey: (r) => r.report_id,
  });
}
