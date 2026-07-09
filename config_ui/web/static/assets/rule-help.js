/** Rule-type and field help panels for the constraints editor. */

import { schemaFor } from "./rule-schemas.js";

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

export const WIDGET_INLINE_HELP = new Set([
  "condition",
  "clamp_spec",
  "bias_drivers",
  "param_list",
]);

export function ruleTypeOptionLabel(type) {
  const s = schemaFor(type);
  return s.label ? `${s.label} (${type})` : type;
}

export function formatRuleExample(example) {
  if (!example) return "";
  if (typeof example === "string") return example;
  const parts = [];
  for (const [k, v] of Object.entries(example)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${k}: ${JSON.stringify(v)}`);
  }
  return parts.join(" · ");
}

/** @param {string} type */
export function updateRuleTypeDetail(panel, type) {
  const s = schemaFor(type);
  panel.replaceChildren();
  panel.className = "rule-type-detail";

  if (s.formula) {
    const row = el("div", "rule-type-detail-row");
    row.append(el("span", "rule-type-detail-k", "Formula"), el("code", "rule-type-formula mono", s.formula));
    panel.appendChild(row);
  }

  const desc = s.description || s.whenToUse;
  if (desc) panel.appendChild(el("p", "rule-type-detail-desc", desc));

  if (s.whenToUse && s.description && s.whenToUse !== s.description) {
    panel.appendChild(el("p", "rule-type-detail-when muted small", s.whenToUse));
  }

  const ex = formatRuleExample(s.example);
  if (ex) {
    const row = el("div", "rule-type-detail-row");
    row.append(el("span", "rule-type-detail-k", "Example"), el("span", "rule-type-detail-ex mono small", ex));
    panel.appendChild(row);
  }

  const caveat = s.caveats || s.help;
  if (caveat) panel.appendChild(el("p", "rule-type-detail-caveat chip-hint", caveat));
}

/** @param {string} type */
export function mountRuleTypeDetail(type) {
  const panel = el("div", "rule-type-detail");
  updateRuleTypeDetail(panel, type);
  return panel;
}

/** Label row: text + optional (?) tooltip, or separate inline hint for complex widgets. */
export function mountFieldLabelWithTip(label, help, { forceInline = false } = {}) {
  const wrap = el("div", "field-label-row");
  wrap.appendChild(el("span", "field-label-text", label));
  if (!help) return { labelRow: wrap, inlineHelp: null };

  if (forceInline) {
    const hint = el("p", "field-inline-help muted small", help);
    return { labelRow: wrap, inlineHelp: hint };
  }

  const tip = el("button", "field-help-btn", "?");
  tip.type = "button";
  tip.title = help;
  tip.setAttribute("aria-label", help);
  wrap.appendChild(tip);
  return { labelRow: wrap, inlineHelp: null };
}
