// TestResultCard -- statistical validation result (Kupiec / Christoffersen / conditional
// coverage), shown as statistic + p-value + result + a plain-English interpretation, never just
// a bare "PASS" label.

import { fmtPValue, fmtNum } from "../format.js";
import { passFailBadge } from "./RiskBadge.js";
import { escapeHtml } from "../dom.js";

const INTERPRETATIONS = {
  kupiec: (pass, pvalue) =>
    pass
      ? `The observed exception rate is statistically consistent with the model's stated confidence level (p = ${fmtPValue(pvalue)}). The model's coverage is not rejected.`
      : `The observed exception rate is NOT statistically consistent with the model's stated confidence level (p = ${fmtPValue(pvalue)}). The model's coverage is rejected -- it is producing more or fewer breaches than its confidence level implies.`,
  christoffersen: (pass, pvalue) =>
    pass
      ? `Exceptions show no statistically significant clustering (p = ${fmtPValue(pvalue)}) -- breaches appear independent over time rather than concentrated in runs.`
      : `Exceptions are significantly CLUSTERED (p = ${fmtPValue(pvalue)}) -- the model tends to fail in runs, which is more dangerous than an equivalent number of isolated breaches: it means the model fails exactly when a regime shift is underway.`,
  conditional_coverage: (pass, pvalue) =>
    pass
      ? `Combined test of coverage AND independence: both hold jointly (p = ${fmtPValue(pvalue)}).`
      : `Combined test of coverage AND independence: at least one is violated (p = ${fmtPValue(pvalue)}) -- see the individual Kupiec/Christoffersen results above for which.`,
};

export function testResultCard({ key, name, statistic, pvalue, pass, note = "" }) {
  const interpretation = INTERPRETATIONS[key] ? INTERPRETATIONS[key](pass, pvalue) : note;
  return `
    <div class="test-result-card">
      <div class="test-result-head">
        <span class="test-result-name">${escapeHtml(name)}</span>
        ${passFailBadge(pass)}
      </div>
      <div class="test-result-stats">
        <div>
          <div class="test-stat-label">Test statistic</div>
          <div class="test-stat-value">${fmtNum(statistic, 3)}</div>
        </div>
        <div>
          <div class="test-stat-label">p-value</div>
          <div class="test-stat-value">${fmtPValue(pvalue)}</div>
        </div>
      </div>
      <div class="test-result-interpretation">${escapeHtml(interpretation)}</div>
    </div>`;
}
