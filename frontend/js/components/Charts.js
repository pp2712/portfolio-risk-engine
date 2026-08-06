// Themed Plotly wrapper. Every chart in the dashboard goes through here so styling (colors, grid,
// typography, hover behaviour) stays consistent instead of each page hand-rolling Plotly configs.
//
// Design-system rules this module encodes (see the dataviz skill's mark-spec/anti-pattern refs):
//  - hairline, solid (never dashed) gridlines, one step off the surface color
//  - 2px lines, >=8px markers
//  - a legend whenever there are >=2 series, none for a single series
//  - never a dual-axis chart
//  - the categorical series order is fixed (series-1/2/3...), never reassigned by filter state
//  - financial hover templates (currency/percent), not raw floats

import { fmtDate } from "../format.js";

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** A date-series x-axis uses category type with pre-formatted labels ("3 Aug") rather than
 * Plotly's native date axis -- with a narrow or sparse date range (a handful of risk runs, say),
 * Plotly's date-axis autotick zooms into hour-level gridlines, which is meaningless for daily
 * portfolio risk data. Category type shows exactly the dates provided, nothing invented between. */
function dateAxisDefaults(dateCount) {
  return { type: "category", nticks: Math.min(10, dateCount) };
}

export function themeTokens() {
  return {
    surface: cssVar("--bg-surface"),
    textPrimary: cssVar("--text-primary"),
    textSecondary: cssVar("--text-secondary"),
    textMuted: cssVar("--text-muted"),
    grid: cssVar("--grid-line"),
    axis: cssVar("--axis-line"),
    series1: cssVar("--series-1"),
    series2: cssVar("--series-2"),
    series3: cssVar("--series-3"),
    series4: cssVar("--series-4"),
    series5: cssVar("--series-5"),
    good: cssVar("--status-good"),
    warning: cssVar("--status-warning"),
    serious: cssVar("--status-serious"),
    critical: cssVar("--status-critical"),
    positive: cssVar("--delta-positive"),
    negative: cssVar("--delta-negative"),
  };
}

export function seriesPalette() {
  const t = themeTokens();
  return [t.series1, t.series2, t.series3, t.series4, t.series5];
}

const FONT_FAMILY = "Inter, -apple-system, 'Segoe UI', sans-serif";

export function baseLayout(overrides = {}) {
  const t = themeTokens();
  return {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    height: 320,
    font: { family: FONT_FAMILY, size: 12, color: t.textSecondary },
    margin: { t: 40, r: 24, b: 44, l: 56 },
    hoverlabel: {
      bgcolor: t.surface,
      bordercolor: cssVar("--border-default"),
      font: { family: FONT_FAMILY, size: 12, color: t.textPrimary },
    },
    legend: {
      orientation: "h",
      y: 1.18,
      yanchor: "bottom",
      x: 0,
      font: { size: 11, color: t.textSecondary },
      bgcolor: "transparent",
    },
    xaxis: {
      gridcolor: t.grid,
      linecolor: t.axis,
      zerolinecolor: t.axis,
      tickfont: { size: 11, color: t.textMuted },
      showgrid: false,
      ticks: "",
    },
    yaxis: {
      gridcolor: t.grid,
      linecolor: t.axis,
      zerolinecolor: t.axis,
      tickfont: { size: 11, color: t.textMuted },
      showgrid: true,
      gridwidth: 1,
      ticks: "",
      zeroline: true,
    },
    colorway: seriesPalette(),
    ...overrides,
  };
}

export const baseConfig = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
};

/** Merge a partial layout with the theme base, deep enough for the one level (xaxis/yaxis) this
 * dashboard actually overrides. */
function mergeLayout(overrides) {
  const base = baseLayout();
  return {
    ...base,
    ...overrides,
    xaxis: { ...base.xaxis, ...(overrides.xaxis || {}) },
    yaxis: { ...base.yaxis, ...(overrides.yaxis || {}) },
    legend: { ...base.legend, ...(overrides.legend || {}) },
  };
}

export function plot(container, traces, layoutOverrides = {}, configOverrides = {}) {
  if (typeof container === "string") container = document.getElementById(container);
  const layout = mergeLayout(layoutOverrides);
  // Hard-constrain the container to the layout's own height so the card can never grow taller
  // than the chart it holds (min-height alone leaves room for the container to be stretched by
  // an unrelated ancestor layout rule -- an explicit height rules that out entirely).
  container.style.height = `${layout.height}px`;
  // Explicitly tear down whatever was in the container (typically a skeleton loader with an
  // infinite CSS animation) in its own synchronous DOM mutation before Plotly builds the chart.
  // Letting Plotly's own newPlot() implicitly replace an actively-animating child can leave its
  // compositor layer orphaned, which has been observed to paint stale content over unrelated
  // parts of the page.
  container.innerHTML = "";
  return Plotly.newPlot(container, traces, layout, { ...baseConfig, ...configOverrides });
}

/** Multi-line time series, e.g. VaR by method over time. `series` = [{ name, x, y, color }] where
 * `x` is a list of ISO date strings ("2026-08-03"). */
export function lineChart(container, series, layoutOverrides = {}) {
  const dateCount = series[0]?.x?.length || 0;
  const traces = series.map((s) => ({
    x: s.x.map(fmtDate),
    y: s.y,
    type: "scatter",
    mode: dateCount <= 1 ? "markers" : "lines+markers",
    name: s.name,
    line: { width: 2, color: s.color, shape: "spline", smoothing: 0.3 },
    marker: { size: 6, color: s.color },
    hovertemplate: s.hovertemplate || `%{y}<extra>${s.name}</extra>`,
  }));
  return plot(container, traces, {
    showlegend: series.length > 1,
    ...layoutOverrides,
    xaxis: { ...dateAxisDefaults(dateCount), ...(layoutOverrides.xaxis || {}) },
  });
}

/** Horizontal bar, sorted by the caller -- used for decomposition/exposure/scenario comparisons.
 * `items` = [{ label, value, color? }]. Colors default to a severity ramp when `severity: true`. */
export function horizontalBarChart(container, items, { valueFormat = (v) => v, layoutOverrides = {} } = {}) {
  const t = themeTokens();
  const colors = items.map((it) => it.color || (it.value < 0 ? t.negative : t.positive));
  const traces = [
    {
      y: items.map((it) => it.label),
      x: items.map((it) => it.value),
      type: "bar",
      orientation: "h",
      marker: { color: colors },
      text: items.map((it) => valueFormat(it.value)),
      // "auto" (rather than a hardcoded "outside") lets Plotly fall back to placing the label
      // inside the bar when the outside margin is too narrow to fit it -- avoids the label
      // colliding with the y-axis category text on narrower (tablet-width) layouts.
      textposition: "auto",
      constraintext: "none",
      textfont: { size: 11, color: t.textSecondary },
      insidetextfont: { size: 11, color: "#f5f5f0" },
      hovertemplate: "%{y}: %{text}<extra></extra>",
    },
  ];
  return plot(container, traces, {
    showlegend: false,
    // automargin lets Plotly measure the ACTUAL rendered label widths (correct font metrics)
    // and reserve exactly enough space, rather than a hand-rolled character-count estimate that
    // clips long labels like "Rate Shock +150bps (Financials proxy)".
    yaxis: { autorange: "reversed", showgrid: false, automargin: true },
    xaxis: { zeroline: true, zerolinewidth: 1, zerolinecolor: t.axis, automargin: true },
    margin: { t: 16, r: 56, b: 40, l: 8 },
    ...layoutOverrides,
  });
}

/** Grouped bar -- model comparison (VaR vs CVaR per method). */
export function groupedBarChart(container, groups, layoutOverrides = {}) {
  const colors = seriesPalette();
  const traces = groups.map((g, i) => ({
    x: g.x,
    y: g.y,
    type: "bar",
    name: g.name,
    marker: { color: colors[i % colors.length] },
    hovertemplate: g.hovertemplate || `%{y}<extra>${g.name}</extra>`,
  }));
  return plot(container, traces, { barmode: "group", showlegend: groups.length > 1, bargap: 0.3, bargroupgap: 0.15, ...layoutOverrides });
}

/** VaR-forecast-vs-realised exception chart -- the backtesting page's signature chart. Breaches
 * rendered as a distinct, larger, status-critical marker; the VaR threshold as a filled band. */
export function exceptionChart(container, { dates, varForecast, realised, isException }, layoutOverrides = {}) {
  const t = themeTokens();
  const displayDates = dates.map(fmtDate);
  const upper = varForecast;
  const lower = varForecast.map((v) => -v);

  const normalX = [], normalY = [], breachX = [], breachY = [];
  displayDates.forEach((d, i) => {
    if (isException[i]) { breachX.push(d); breachY.push(realised[i]); }
    else { normalX.push(d); normalY.push(realised[i]); }
  });

  const traces = [
    {
      x: displayDates, y: upper, type: "scatter", mode: "lines", name: "VaR threshold",
      line: { width: 1, color: t.textMuted, dash: "solid" }, hoverinfo: "skip", showlegend: false,
    },
    {
      x: displayDates, y: lower, type: "scatter", mode: "lines", name: "VaR threshold (loss)",
      line: { width: 1.5, color: t.warning }, fill: "tonexty", fillcolor: "rgba(250,178,25,0.05)",
      hovertemplate: "VaR forecast: %{y:.2%}<extra></extra>",
    },
    {
      x: normalX, y: normalY, type: "scatter", mode: "markers", name: "Realised return",
      marker: { size: 6, color: t.textSecondary, line: { width: 1, color: t.surface } },
      hovertemplate: "%{x}<br>Realised: %{y:.2%}<extra></extra>",
    },
    {
      x: breachX, y: breachY, type: "scatter", mode: "markers", name: "Exception (breach)",
      marker: { size: 10, color: t.critical, symbol: "x", line: { width: 2, color: t.critical } },
      hovertemplate: "%{x}<br><b>Breach:</b> %{y:.2%}<extra></extra>",
    },
  ];
  return plot(container, traces, {
    showlegend: true,
    yaxis: { tickformat: ".1%", zeroline: true, zerolinewidth: 1, zerolinecolor: t.axis },
    ...layoutOverrides,
    xaxis: { ...dateAxisDefaults(dates.length), ...(layoutOverrides.xaxis || {}) },
  });
}
