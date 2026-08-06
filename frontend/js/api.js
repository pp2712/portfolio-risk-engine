// API client -- thin wrappers around the existing FastAPI endpoints. No new endpoints invented
// here beyond what the backend genuinely exposes (see docs/API.md). Every function name maps
// 1:1 to a real route.

import { API_BASE } from "../config.js";

class ApiError extends Error {
  constructor(status, path, body) {
    super(`${status} ${path}`);
    this.status = status;
    this.path = path;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, path, body);
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}

export const api = {
  health: () => request("/health"),

  listPortfolios: () => request("/portfolios"),
  getPortfolio: (id) => request(`/portfolios/${id}`),

  getRiskRun: (id) => request(`/risk/runs/${id}`),
  getRiskHistory: (portfolioId) => request(`/risk/history/${portfolioId}`),

  listBacktests: (portfolioId) => request(`/risk/backtest?portfolio_id=${portfolioId}`),
  getBacktest: (id) => request(`/risk/backtest/${id}`),

  listScenarios: () => request("/scenarios"),
  listStressRuns: (portfolioId) => request(`/stress/runs?portfolio_id=${portfolioId}`),
  getStressRun: (id) => request(`/stress/runs/${id}`),

  listReports: (portfolioId) => request(`/reports?portfolio_id=${portfolioId}`),
};

export { ApiError };

/** Convenience: the most recent risk run for a portfolio, derived from the history endpoint
 * (there is no dedicated "latest risk run" endpoint -- history is already ordered by date). */
export async function getLatestRiskRun(portfolioId) {
  const history = await api.getRiskHistory(portfolioId);
  if (history.points.length === 0) return null;
  const latestPoint = history.points[history.points.length - 1];
  return api.getRiskRun(latestPoint.risk_run_id);
}

/** Convenience: the most recently computed backtest for a portfolio (list is already ordered by
 * calculated_at desc server-side). */
export async function getLatestBacktest(portfolioId) {
  const backtests = await api.listBacktests(portfolioId);
  if (backtests.length === 0) return null;
  return api.getBacktest(backtests[0].backtest_id);
}
