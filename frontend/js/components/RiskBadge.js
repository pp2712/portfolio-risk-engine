// RiskBadge -- the one consistent status visual language used across Overview, Backtesting,
// Stress Testing, and Portfolio pages.
//
// Thresholds are never invented client-side. The only genuinely backend-defined status is the
// Kupiec backtest's traffic_light_zone (green/amber/red -- see validation/traffic_light.py, a
// real Basel-style binomial classification). That maps directly to 3 of these 4 labels:
//   green -> NORMAL, amber -> ELEVATED, red -> CRITICAL.
// "HIGH" exists in the visual language for completeness/consistency but is never assigned by this
// dashboard on its own authority -- there is no 4-tier backend signal to justify it. Pass/fail
// booleans (Kupiec/Christoffersen pass) map to a plain pass/fail badge, not a risk-severity one.
// Anywhere a status can't be derived from real backend data, `neutral()` is used instead of a
// fabricated tier.

const ZONE_MAP = {
  green: { cls: "badge-good", label: "NORMAL" },
  amber: { cls: "badge-warning", label: "ELEVATED" },
  red: { cls: "badge-critical", label: "CRITICAL" },
};

export function trafficLightBadge(zone) {
  const z = ZONE_MAP[zone] || { cls: "badge-neutral", label: String(zone || "UNKNOWN").toUpperCase() };
  return `<span class="badge ${z.cls}"><span class="dot"></span>${z.label}</span>`;
}

export function passFailBadge(pass, { passLabel = "PASS", failLabel = "FAIL" } = {}) {
  return pass
    ? `<span class="badge badge-pass"><span class="dot"></span>${passLabel}</span>`
    : `<span class="badge badge-fail"><span class="dot"></span>${failLabel}</span>`;
}

export function neutralBadge(label) {
  return `<span class="badge badge-neutral"><span class="dot"></span>${label}</span>`;
}

/** Small colored dot only (no text) -- used inline in tables where the badge pill would be too
 * wide, e.g. next to a ticker. Still never color-alone: always placed beside a text value. */
export function statusDot(zone) {
  const z = ZONE_MAP[zone];
  const color = z ? { green: "var(--status-good)", amber: "var(--status-warning)", red: "var(--status-critical)" }[zone] : "var(--text-muted)";
  return `<span class="dot" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${color};margin-right:6px;"></span>`;
}
