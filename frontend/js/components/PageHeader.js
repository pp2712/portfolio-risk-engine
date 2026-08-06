import { escapeHtml } from "../dom.js";

export function pageHeader({ title, subtitle = "", actionsHtml = "" }) {
  return `
    <div class="page-header">
      <div>
        <div class="page-title">${escapeHtml(title)}</div>
        ${subtitle ? `<div class="page-subtitle">${escapeHtml(subtitle)}</div>` : ""}
      </div>
      ${actionsHtml ? `<div class="page-actions">${actionsHtml}</div>` : ""}
    </div>`;
}
