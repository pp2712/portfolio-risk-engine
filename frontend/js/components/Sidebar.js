import { icon } from "../icons.js";
import { escapeHtml } from "../dom.js";

export const NAV_SECTIONS = [
  {
    label: "Analysis",
    items: [
      { id: "overview", label: "Overview", icon: "overview" },
      { id: "portfolio", label: "Portfolio", icon: "portfolio" },
      { id: "var-cvar", label: "VaR / CVaR", icon: "risk" },
      { id: "model-comparison", label: "Model Comparison", icon: "compare" },
    ],
  },
  {
    label: "Validation",
    items: [
      { id: "backtesting", label: "Backtesting", icon: "backtest" },
      { id: "stress", label: "Stress Testing", icon: "stress" },
      { id: "decomposition", label: "Risk Decomposition", icon: "decomposition" },
      { id: "historical", label: "Historical Risk", icon: "historical" },
    ],
  },
  {
    label: "Output",
    items: [{ id: "reports", label: "Reports", icon: "reports" }],
  },
];

export function renderSidebar(activeId) {
  const sections = NAV_SECTIONS.map(
    (section) => `
      <div class="sidebar-section-label">${escapeHtml(section.label)}</div>
      ${section.items
        .map(
          (item) => `
        <button class="nav-item${item.id === activeId ? " active" : ""}" data-nav="${item.id}" aria-current="${item.id === activeId ? "page" : "false"}">
          ${icon(item.icon)}
          <span class="label">${escapeHtml(item.label)}</span>
        </button>`
        )
        .join("")}`
  ).join("");

  return `
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-brand">
        <div class="sidebar-brand-mark">PR</div>
        <div class="sidebar-brand-text">
          <span class="name">Portfolio Risk</span>
          <span class="tag">Engine</span>
        </div>
      </div>
      <nav class="sidebar-nav" aria-label="Primary">
        ${sections}
      </nav>
      <div class="sidebar-footer">
        <button class="sidebar-toggle" id="sidebar-toggle" title="Collapse sidebar" aria-label="Collapse sidebar">
          ${icon("chevronLeft", "sidebar-toggle-icon")}
          <span class="label">Collapse</span>
        </button>
      </div>
    </aside>`;
}

export function setActiveNavItem(activeId) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    const isActive = btn.dataset.nav === activeId;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-current", isActive ? "page" : "false");
  });
}
