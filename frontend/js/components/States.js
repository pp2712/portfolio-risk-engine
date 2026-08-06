// EmptyState / ErrorState / loading skeletons -- shown by every page module while data loads,
// when there is genuinely nothing to show yet, or when a request fails.

import { ICONS, icon } from "../icons.js";
import { escapeHtml } from "../dom.js";

export function emptyState({ icon: iconName = "inbox", title, desc = "" } = {}) {
  return `
    <div class="state-block" role="status">
      <div class="state-icon">${ICONS[iconName] || ICONS.inbox}</div>
      <div class="state-title">${escapeHtml(title)}</div>
      ${desc ? `<div class="state-desc">${escapeHtml(desc)}</div>` : ""}
    </div>`;
}

export function errorState({ title = "Something went wrong", desc = "", onRetryId = "" } = {}) {
  return `
    <div class="state-block state-error" role="alert">
      <div class="state-icon">${ICONS.alertCircle}</div>
      <div class="state-title">${escapeHtml(title)}</div>
      ${desc ? `<div class="state-desc">${escapeHtml(desc)}</div>` : ""}
      ${onRetryId ? `<button class="btn btn-sm" id="${onRetryId}">${icon("refresh")}<span>Retry</span></button>` : ""}
    </div>`;
}

export function skeletonMetricCard() {
  return `
    <div class="metric-card">
      <div class="skeleton skeleton-text" style="width:56%"></div>
      <div class="skeleton skeleton-metric"></div>
      <div class="skeleton skeleton-text" style="width:40%"></div>
    </div>`;
}

export function skeletonMetricRow(n = 4) {
  return `<div class="grid grid-cols-4">${Array.from({ length: n }, skeletonMetricCard).join("")}</div>`;
}

export function skeletonChart() {
  return `<div class="skeleton skeleton-chart"></div>`;
}

export function skeletonTable(rows = 5) {
  return `<div class="card"><div class="card-body">${Array.from({ length: rows }, () => `<div class="skeleton skeleton-row"></div>`).join("")}</div></div>`;
}

/** Render a loading skeleton into a container, run an async loader, and swap in the real content
 * -- or an error state with a working retry button -- on completion/failure. This is the one
 * function every page module routes its data fetch through, so loading/error handling is
 * consistent everywhere instead of re-implemented per page. */
export async function withLoadingState(container, { skeleton, load, render, emptyCheck, empty }) {
  if (typeof container === "string") container = document.getElementById(container);
  container.innerHTML = skeleton();
  try {
    const data = await load();
    if (emptyCheck && emptyCheck(data)) {
      container.innerHTML = empty();
      return data;
    }
    container.innerHTML = render(data);
    return data;
  } catch (err) {
    console.error(err);
    const retryId = `retry-${Math.random().toString(36).slice(2, 9)}`;
    container.innerHTML = errorState({
      title: "Couldn't load this data",
      desc: err?.message || "The request failed unexpectedly.",
      onRetryId: retryId,
    });
    const btn = document.getElementById(retryId);
    if (btn) btn.addEventListener("click", () => withLoadingState(container, { skeleton, load, render, emptyCheck, empty }));
    throw err;
  }
}
