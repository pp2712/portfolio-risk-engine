// Entry point: app shell assembly, theme/sidebar prefs, routing, portfolio selection.

import { api } from "./api.js";
import { state, getStoredTheme, setStoredTheme, getStoredSidebarCollapsed, setStoredSidebarCollapsed } from "./state.js";
import { renderSidebar, setActiveNavItem } from "./components/Sidebar.js";
import { renderHeader, setApiStatus } from "./components/Header.js";
import { icon } from "./icons.js";

import * as overviewPage from "./pages/overview.js";
import * as portfolioPage from "./pages/portfolio.js";
import * as varCvarPage from "./pages/varCvar.js";
import * as modelComparisonPage from "./pages/modelComparison.js";
import * as backtestingPage from "./pages/backtesting.js";
import * as stressPage from "./pages/stress.js";
import * as decompositionPage from "./pages/decomposition.js";
import * as historicalPage from "./pages/historical.js";
import * as reportsPage from "./pages/reports.js";

const PAGES = {
  overview: overviewPage,
  portfolio: portfolioPage,
  "var-cvar": varCvarPage,
  "model-comparison": modelComparisonPage,
  backtesting: backtestingPage,
  stress: stressPage,
  decomposition: decompositionPage,
  historical: historicalPage,
  reports: reportsPage,
};

// ---------- Theme ----------

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  setStoredTheme(theme);
}

function setupThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  btn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
    // Chart colors are read from CSS variables at render time -- re-render the active page so
    // Plotly picks up the new theme's palette instead of staying on the previous mode's colors.
    routeTo(state.currentPage, { skipHashUpdate: true });
  });
}

// ---------- Sidebar ----------

function setupSidebar() {
  const shell = document.getElementById("app-shell");
  const toggleBtn = document.getElementById("sidebar-toggle");
  const collapsed = getStoredSidebarCollapsed();
  if (collapsed) shell.classList.add("sidebar-collapsed");
  updateSidebarToggleIcon(collapsed);

  toggleBtn.addEventListener("click", () => {
    const isCollapsed = shell.classList.toggle("sidebar-collapsed");
    setStoredSidebarCollapsed(isCollapsed);
    updateSidebarToggleIcon(isCollapsed);
  });

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.location.hash = btn.dataset.nav;
    });
  });
}

function updateSidebarToggleIcon(collapsed) {
  const iconSpan = document.querySelector("#sidebar-toggle .icon");
  if (iconSpan) iconSpan.outerHTML = icon(collapsed ? "chevronRight" : "chevronLeft", "sidebar-toggle-icon");
  const label = document.querySelector("#sidebar-toggle .label");
  if (label) label.textContent = collapsed ? "Expand" : "Collapse";
}

// ---------- Portfolio selection ----------

async function loadPortfolios() {
  try {
    state.portfolios = await api.listPortfolios();
  } catch (err) {
    console.error("failed to load portfolios", err);
    state.portfolios = [];
  }
  if (state.portfolios.length > 0) {
    state.currentPortfolioId = state.portfolios[0].portfolio_id;
  }
}

function setupPortfolioSelect() {
  const select = document.getElementById("portfolio-select");
  if (state.currentPortfolioId) select.value = String(state.currentPortfolioId);
  select.addEventListener("change", () => {
    state.currentPortfolioId = Number(select.value) || null;
    routeTo(state.currentPage, { skipHashUpdate: true });
  });
}

// ---------- Routing ----------

async function routeTo(pageId, { skipHashUpdate = false } = {}) {
  const page = PAGES[pageId] ? pageId : "overview";
  state.currentPage = page;
  setActiveNavItem(page);
  if (!skipHashUpdate && window.location.hash.replace("#", "") !== page) {
    window.location.hash = page;
    return; // hashchange listener will call routeTo again
  }
  const container = document.getElementById("app-main");
  await PAGES[page].render(container);
}

function setupRouter() {
  window.addEventListener("hashchange", () => {
    const page = window.location.hash.replace("#", "") || "overview";
    routeTo(page, { skipHashUpdate: true });
  });
}

// ---------- Health ----------

async function checkHealth() {
  try {
    const health = await api.health();
    setApiStatus(health.status);
  } catch {
    setApiStatus("offline");
  }
}

// ---------- Boot ----------

async function main() {
  applyTheme(getStoredTheme());

  await loadPortfolios();

  const shell = document.getElementById("app-shell");
  shell.innerHTML = `
    ${renderSidebar("overview")}
    ${renderHeader({ portfolios: state.portfolios })}
    <main class="app-main" id="app-main"></main>`;

  setupSidebar();
  setupThemeToggle();
  setupPortfolioSelect();
  setupRouter();
  checkHealth();
  setInterval(checkHealth, 60_000);

  const initialPage = window.location.hash.replace("#", "") || "overview";
  await routeTo(initialPage, { skipHashUpdate: true });
}

main();
