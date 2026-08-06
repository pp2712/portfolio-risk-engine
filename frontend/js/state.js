// Central app state -- portfolios list, current selection, current page, theme/sidebar UI prefs.
// Deliberately a plain mutable object (no framework/store library) -- this app has one consumer
// (the page modules reading state synchronously before/while rendering), so a reactive store
// would be ceremony without benefit. Persisted UI prefs (theme, sidebar) go to localStorage.

export const state = {
  portfolios: [],
  currentPortfolioId: null,
  currentPage: "overview",
  currentRiskRun: null, // full RiskRunResultOut of the latest risk run for the current portfolio
  currentBacktest: null,
  confidenceLevel: "0.95",
};

const THEME_KEY = "risk-engine-theme";
const SIDEBAR_KEY = "risk-engine-sidebar-collapsed";

export function getStoredTheme() {
  return localStorage.getItem(THEME_KEY) || "dark";
}
export function setStoredTheme(theme) {
  localStorage.setItem(THEME_KEY, theme);
}

export function getStoredSidebarCollapsed() {
  return localStorage.getItem(SIDEBAR_KEY) === "1";
}
export function setStoredSidebarCollapsed(collapsed) {
  localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
}

export function currentPortfolio() {
  return state.portfolios.find((p) => p.portfolio_id === state.currentPortfolioId) || null;
}
