// Tiny DOM helpers shared by every component/page module.

export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

export function mount(container, html) {
  if (typeof container === "string") container = document.getElementById(container);
  container.innerHTML = html;
  return container;
}

export function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
