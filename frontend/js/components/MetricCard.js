// MetricCard -- the primary stat-tile used on Overview and throughout the dashboard. Every value
// rendered here comes from a caller-supplied, already-formatted string; this component never
// invents or defaults a number.

import { icon } from "../icons.js";
import { escapeHtml } from "../dom.js";

/**
 * @param {object} opts
 * @param {string} opts.label
 * @param {string} opts.value - pre-formatted display value
 * @param {string} [opts.sub] - secondary line (e.g. "as of 3 Aug 2026")
 * @param {{ text: string, direction: "positive"|"negative"|"neutral" }} [opts.delta]
 * @param {string} [opts.infoTip] - tooltip text explaining the metric
 * @param {boolean} [opts.hero] - larger display size
 * @param {boolean} [opts.mono] - use tabular monospace figures for the value
 */
export function metricCard({ label, value, sub = "", delta = null, infoTip = "", hero = false, mono = true }) {
  const deltaHtml = delta
    ? `<span class="metric-delta ${delta.direction}">${delta.direction === "positive" ? icon("arrowUp") : delta.direction === "negative" ? icon("arrowDown") : ""}${escapeHtml(delta.text)}</span>`
    : "";
  return `
    <div class="metric-card${hero ? " metric-card--hero" : ""}">
      <div class="metric-label">
        <span>${escapeHtml(label)}</span>
        ${infoTip ? `<span class="info-tip" title="${escapeHtml(infoTip)}">${icon("info")}</span>` : ""}
      </div>
      <div class="metric-value${mono ? " mono" : ""}">${value}</div>
      ${sub || deltaHtml ? `<div class="metric-sub">${deltaHtml}${sub ? `<span>${escapeHtml(sub)}</span>` : ""}</div>` : ""}
    </div>`;
}
