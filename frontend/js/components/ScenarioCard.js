import { fmtMoney, fmtPct, fmtDate } from "../format.js";
import { escapeHtml } from "../dom.js";

export function scenarioCard({ name, description, scenarioType, dateRange = "", pnl, pnlPct, currency = "USD" }) {
  const negative = pnlPct < 0;
  return `
    <div class="scenario-card">
      <div class="scenario-card-head">
        <div>
          <div class="scenario-name">${escapeHtml(name)}</div>
          <div class="scenario-type">${escapeHtml(scenarioType.replace(/_/g, " "))}${dateRange ? ` &middot; ${escapeHtml(dateRange)}` : ""}</div>
        </div>
      </div>
      <div class="scenario-impact ${negative ? "negative" : "positive"}">${fmtPct(pnlPct, { signed: true })}</div>
      <div class="text-xs text-muted">${fmtMoney(pnl, currency)} portfolio impact</div>
      ${description ? `<div class="text-xs text-secondary">${escapeHtml(description)}</div>` : ""}
    </div>`;
}
