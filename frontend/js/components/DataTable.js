// DataTable -- a sortable, professionally-formatted financial table. Renders into a container and
// wires up its own header-click sort handlers; call `renderDataTable` again (e.g. from a sort
// click) to re-render with new order.
//
// columns: [{ key, label, align: "left"|"right", sortable, render(row), sortValue(row) }]

import { icon } from "../icons.js";
import { escapeHtml } from "../dom.js";

const sortState = new WeakMap(); // container element -> { key, dir }

export function renderDataTable(container, { columns, rows, rowKey = (r, i) => i, onRowClick = null, emptyMessage = "No data available." }) {
  if (typeof container === "string") container = document.getElementById(container);
  if (!rows || rows.length === 0) {
    container.innerHTML = `<div class="state-block"><div class="state-title">${escapeHtml(emptyMessage)}</div></div>`;
    return;
  }

  let state = sortState.get(container);
  if (!state) {
    state = { key: null, dir: 1 };
    sortState.set(container, state);
  }

  const sortedRows = [...rows];
  if (state.key) {
    const col = columns.find((c) => c.key === state.key);
    const getVal = col?.sortValue || ((r) => r[state.key]);
    sortedRows.sort((a, b) => {
      const va = getVal(a), vb = getVal(b);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      return va > vb ? state.dir : -state.dir;
    });
  }

  const headHtml = columns
    .map((c) => {
      const sortable = c.sortable !== false;
      const isSorted = state.key === c.key;
      const arrow = isSorted ? (state.dir === 1 ? icon("arrowUp") : icon("arrowDown")) : "";
      return `<th class="${sortable ? "sortable" : ""}${isSorted ? " sorted" : ""}" data-key="${c.key}" style="${c.align === "left" ? "text-align:left" : ""}">${escapeHtml(c.label)}<span class="sort-arrow">${arrow}</span></th>`;
    })
    .join("");

  const bodyHtml = sortedRows
    .map((row, i) => {
      const cells = columns.map((c) => `<td class="${c.align === "left" ? "" : "num"}">${c.render(row, i)}</td>`).join("");
      return `<tr data-row-key="${escapeHtml(String(rowKey(row, i)))}" class="${onRowClick ? "row-link" : ""}">${cells}</tr>`;
    })
    .join("");

  container.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>${headHtml}</tr></thead>
        <tbody>${bodyHtml}</tbody>
      </table>
    </div>`;

  container.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (state.key === key) {
        state.dir *= -1;
      } else {
        state.key = key;
        state.dir = 1;
      }
      renderDataTable(container, { columns, rows, rowKey, onRowClick, emptyMessage });
    });
  });

  if (onRowClick) {
    container.querySelectorAll("tbody tr").forEach((tr) => {
      tr.addEventListener("click", () => onRowClick(tr.dataset.rowKey));
    });
  }
}
