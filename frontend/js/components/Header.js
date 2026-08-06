import { icon } from "../icons.js";
import { escapeHtml } from "../dom.js";

export function renderHeader({ portfolios }) {
  const options = portfolios.length
    ? portfolios.map((p) => `<option value="${p.portfolio_id}">${escapeHtml(p.name)}</option>`).join("")
    : `<option value="">No portfolios</option>`;

  return `
    <header class="app-header">
      <div class="header-left">
        <div class="header-portfolio-select">
          ${icon("wallet")}
          <select class="select" id="portfolio-select" aria-label="Select portfolio">${options}</select>
        </div>
        <div class="divider-v"></div>
        <div class="header-meta" id="header-asof">
          <span>As of</span><strong id="header-asof-value">–</strong>
        </div>
        <div class="header-meta hide-mobile" id="header-calc">
          ${icon("clock")}
          <span>Last calculated</span><strong id="header-calc-value">–</strong>
        </div>
      </div>
      <div class="header-right">
        <span class="badge badge-neutral" id="api-status">
          <span class="dot"></span><span id="api-status-text">Connecting…</span>
        </span>
        <button class="btn btn-icon btn-ghost" id="theme-toggle" title="Toggle theme" aria-label="Toggle light/dark theme">
          ${icon("moon", "theme-icon-moon")}${icon("sun", "theme-icon-sun")}
        </button>
      </div>
    </header>`;
}

export function setApiStatus(status) {
  const badge = document.getElementById("api-status");
  const text = document.getElementById("api-status-text");
  if (!badge || !text) return;
  badge.classList.remove("badge-good", "badge-critical", "badge-neutral");
  if (status === "ok") {
    badge.classList.add("badge-good");
    text.textContent = "Live";
  } else if (status === "degraded") {
    badge.classList.add("badge-warning");
    text.textContent = "Degraded";
  } else {
    badge.classList.add("badge-critical");
    text.textContent = "Offline";
  }
}

export function setHeaderMeta({ asOf, lastCalculated }) {
  const asOfEl = document.getElementById("header-asof-value");
  const calcEl = document.getElementById("header-calc-value");
  if (asOfEl) asOfEl.textContent = asOf || "–";
  if (calcEl) calcEl.textContent = lastCalculated || "–";
}
