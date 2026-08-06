// Financial number formatting -- consistent magnitude-aware formatting across the whole dashboard.
// No raw floats ever reach the DOM; every number passes through one of these.
//
// Locale is always explicitly "en-US" (Western thousands-grouping: 1,245,320), never `undefined`
// -- letting Intl fall back to the browser/OS locale means the same portfolio value renders with
// different digit grouping (e.g. the Indian 12,34,567 style) depending on who is viewing it, which
// is exactly the kind of inconsistency a risk-reporting surface can't have.
const LOCALE = "en-US";

const CURRENCY_SYMBOLS = { USD: "$", GBP: "£", EUR: "€" };

export function currencySymbol(code) {
  return CURRENCY_SYMBOLS[code] || `${code} `;
}

/** Compact magnitude-aware currency: $1,245,320 / $125.4K / $4.2M */
export function fmtMoney(value, currency = "USD", { compact = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const symbol = currencySymbol(currency);
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (compact && abs >= 1_000_000) return `${sign}${symbol}${(abs / 1_000_000).toFixed(1)}M`;
  if (compact && abs >= 100_000) return `${sign}${symbol}${(abs / 1_000).toFixed(0)}K`;
  return `${sign}${symbol}${abs.toLocaleString(LOCALE, { maximumFractionDigits: 0 })}`;
}

/** Full-precision currency for tables where every digit matters. */
export function fmtMoneyFull(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const symbol = currencySymbol(currency);
  const sign = value < 0 ? "-" : "";
  return `${sign}${symbol}${Math.abs(value).toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Percentage, signed optionally. digits defaults to 2. */
export function fmtPct(value, { digits = 2, signed = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const pct = value * 100;
  const sign = signed && pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

/** Plain number with thousands separators, fixed decimals. */
export function fmtNum(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Integer count, thousands-comma'd. */
export function fmtInt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return Math.round(value).toLocaleString(LOCALE);
}

/** p-value formatting -- always 4 dp, since risk decisions hinge on the third/fourth digit. */
export function fmtPValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  if (value < 0.0001) return "<0.0001";
  return value.toFixed(4);
}

/** ISO date -> "3 Aug 2026" */
export function fmtDate(isoDate) {
  if (!isoDate) return "–";
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" });
}

/** ISO datetime -> "3 Aug 2026, 14:32" */
export function fmtDateTime(isoDateTime) {
  if (!isoDateTime) return "–";
  const d = new Date(isoDateTime);
  if (Number.isNaN(d.getTime())) return isoDateTime;
  return `${d.toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" })}, ${d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })}`;
}

/** Relative recency, e.g. "2h ago", "just now" -- used for the header's last-calculation stamp. */
export function fmtRelativeTime(isoDateTime) {
  if (!isoDateTime) return "–";
  const d = new Date(isoDateTime);
  if (Number.isNaN(d.getTime())) return isoDateTime;
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return fmtDate(isoDateTime.slice(0, 10));
}

/** Format a confidence-level dict key ("0.95") as "95%". */
export function fmtConfidenceKey(key) {
  return `${Math.round(parseFloat(key) * 100)}%`;
}

export function methodLabel(method) {
  return { historical: "Historical", parametric: "Parametric", monte_carlo: "Monte Carlo" }[method] || method;
}

export function titleCase(s) {
  return String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
