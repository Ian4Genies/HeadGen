/** Per-type relational rule schemas for the constraints editor. */

export const RULE_TYPES = [
  "scale_follow",
  "conditional_clamp",
  "mutual_dampen",
  "ratio_clamp",
  "product_clamp",
  "cross_proportion_clamp",
  "sandwich_clamp",
  "conditional_bias",
  "winner_take_all",
];

const COMMON_KEYS = new Set(["title", "type", "muted"]);

function cond(p = "") {
  return { param: p };
}

function clampSpec(p = "", min = undefined, max = undefined) {
  const o = { param: p };
  if (min !== undefined) o.min = min;
  if (max !== undefined) o.max = max;
  return o;
}

function driver(p = "") {
  return { param: p, range: [0, 1], map: [0, 1] };
}

/** @type {Record<string, { label: string, description: string, help?: string, fields: object[] }>} */
export const RULE_SCHEMAS = {
  scale_follow: {
    label: "Scale follow",
    description: "Forces target = source × factor.",
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "" },
      { key: "source", label: "Source param", widget: "param", required: true, default: "" },
      { key: "factor", label: "Factor", widget: "number", required: true, default: 0.5 },
    ],
  },
  conditional_clamp: {
    label: "Conditional clamp",
    description: "Clamps target only when a condition param crosses a threshold.",
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "" },
      { key: "condition", label: "Condition", widget: "condition", required: true, default: cond() },
      { key: "min", label: "Min bound", widget: "number_optional", required: false, default: undefined },
      { key: "max", label: "Max bound", widget: "number_optional", required: false, default: undefined },
    ],
  },
  mutual_dampen: {
    label: "Mutual dampen",
    description: "Scales params proportionally when combined |values| exceed max_combined.",
    fields: [
      { key: "params", label: "Params", widget: "param_list", required: true, default: [""], minItems: 1 },
      { key: "max_combined", label: "Max combined", widget: "number", required: true, default: 1 },
    ],
  },
  ratio_clamp: {
    label: "Ratio clamp",
    description: "Scales numerator down when numerator / denominator > max_ratio.",
    fields: [
      { key: "numerator", label: "Numerator", widget: "param", required: true, default: "" },
      { key: "denominator", label: "Denominator", widget: "param", required: true, default: "" },
      { key: "max_ratio", label: "Max ratio", widget: "number", required: true, default: 1 },
    ],
  },
  product_clamp: {
    label: "Product clamp",
    description: "Scales param_a down when param_a × param_b > max_product.",
    fields: [
      { key: "param_a", label: "Param A", widget: "param", required: true, default: "" },
      { key: "param_b", label: "Param B", widget: "param", required: true, default: "" },
      { key: "max_product", label: "Max product", widget: "number", required: true, default: 1 },
    ],
  },
  cross_proportion_clamp: {
    label: "Cross proportion clamp",
    description: "Clamps a target when two independent conditions are both true.",
    help: "Left* joint targets auto-mirror to Right* at runtime.",
    fields: [
      { key: "if", label: "If", widget: "condition", required: true, default: cond() },
      { key: "and", label: "And", widget: "condition", required: true, default: cond() },
      { key: "then_clamp", label: "Then clamp", widget: "clamp_spec", required: true, default: clampSpec() },
    ],
  },
  sandwich_clamp: {
    label: "Sandwich clamp",
    description: "Keeps target sandwiched between floor and ceiling anchor params.",
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "" },
      { key: "floor", label: "Floor param", widget: "param", required: true, default: "" },
      { key: "ceiling", label: "Ceiling param", widget: "param", required: true, default: "" },
      { key: "tolerance", label: "Tolerance", widget: "number", required: false, default: 0 },
      { key: "target_sign", label: "Target sign", widget: "enum", required: false, default: 1, options: [
        { value: 1, label: "1 (normal)" },
        { value: -1, label: "-1 (inverted axis)" },
      ] },
    ],
  },
  conditional_bias: {
    label: "Conditional bias",
    description: "Raises or suppresses a shape target based on driver signals.",
    fields: [
      { key: "direction", label: "Direction", widget: "enum", required: true, default: "raise", options: [
        { value: "raise", label: "raise" },
        { value: "suppress", label: "suppress" },
      ] },
      { key: "target", label: "Target shape", widget: "param", required: true, default: "" },
      { key: "drivers", label: "Drivers", widget: "bias_drivers", required: true, default: [driver()] },
      { key: "combine", label: "Combine", widget: "enum", required: false, default: "min", options: [
        { value: "min", label: "min (AND)" },
        { value: "max", label: "max (OR)" },
        { value: "average", label: "average" },
      ] },
      { key: "max_bias", label: "Max bias", widget: "number", required: false, default: 1 },
    ],
  },
  winner_take_all: {
    label: "Winner take all",
    description: "Zeroes all params except the largest |value| in the group.",
    fields: [
      { key: "params", label: "Params", widget: "param_list", required: true, default: ["", ""], minItems: 2 },
    ],
  },
};

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function schemaFor(type) {
  return RULE_SCHEMAS[type] ?? RULE_SCHEMAS.scale_follow;
}

function fieldDefault(field) {
  if (field.default === undefined) return undefined;
  return deepClone(field.default);
}

/** Build default rule object for a type. */
export function emptyRule(type = "scale_follow") {
  const schema = schemaFor(type);
  const rule = { title: "New rule", type, muted: false };
  for (const field of schema.fields) {
    if (field.default !== undefined) rule[field.key] = fieldDefault(field);
  }
  return rule;
}

function isEmptyValue(field, value) {
  if (value === undefined || value === null) return true;
  if (field.widget === "param" || field.widget === "number") {
    return value === "" || (field.widget === "number" && Number.isNaN(value));
  }
  if (field.widget === "param_list") {
    const min = field.minItems ?? 1;
    const items = Array.isArray(value) ? value.filter((x) => String(x).trim()) : [];
    return items.length < min;
  }
  if (field.widget === "condition" || field.widget === "clamp_spec") {
    if (!value || typeof value !== "object") return true;
    if (!String(value.param ?? "").trim()) return true;
    if (field.widget === "condition") {
      return value.above === undefined && value.below === undefined;
    }
    return value.min === undefined && value.max === undefined;
  }
  if (field.widget === "bias_drivers") {
    const drivers = Array.isArray(value) ? value : [];
    return !drivers.length || drivers.some((d) => !String(d?.param ?? "").trim());
  }
  if (field.widget === "number_optional") return false;
  return false;
}

/** Keys that would be lost when migrating from oldType to newType with non-empty values. */
export function migrationDataLoss(rule, newType) {
  const oldType = rule.type;
  if (oldType === newType) return [];
  const newKeys = new Set(schemaFor(newType).fields.map((f) => f.key));
  const lost = [];
  for (const [k, v] of Object.entries(rule)) {
    if (COMMON_KEYS.has(k) || k === "type") continue;
    if (newKeys.has(k)) continue;
    if (v === undefined || v === null || v === "") continue;
    if (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length) continue;
    if (Array.isArray(v) && !v.some((x) => String(x).trim())) continue;
    lost.push(k);
  }
  return lost;
}

/** Replace rule body with new type template; preserve title/muted. */
export function migrateRuleType(rule, newType, { preserveTitle = true, preserveMuted = true } = {}) {
  const schema = schemaFor(newType);
  const next = { type: newType };
  if (preserveTitle) next.title = rule.title ?? "New rule";
  if (preserveMuted) next.muted = !!rule.muted;
  for (const field of schema.fields) {
    if (field.default !== undefined) next[field.key] = fieldDefault(field);
  }
  return next;
}

/** @returns {{ ok: boolean, missing: string[], warnings: string[] }} */
export function validateRule(rule) {
  const schema = schemaFor(rule.type);
  const missing = [];
  const warnings = [];
  for (const field of schema.fields) {
    if (!field.required) continue;
    const value = rule[field.key];
    if (isEmptyValue(field, value)) missing.push(field.label || field.key);
  }
  if (rule.type === "conditional_clamp") {
    const hasBound = rule.min !== undefined || rule.max !== undefined;
    if (!hasBound) missing.push("Min or max bound");
  }
  if (rule.type === "cross_proportion_clamp") {
    const tp = rule.then_clamp?.param ?? "";
    if (tp.startsWith("Left") && tp.includes("Bind")) {
      warnings.push("Left* targets auto-mirror to Right* partner at runtime");
    }
  }
  return { ok: missing.length === 0, missing, warnings };
}

export function ruleTypeDescription(type) {
  return schemaFor(type).description ?? "";
}

export function ruleTypeHelp(type) {
  return schemaFor(type).help ?? "";
}

export function schemaFields(type) {
  return schemaFor(type).fields;
}

/** Drop keys that do not belong to the rule's type schema. */
export function normalizeRule(rule) {
  const allowed = new Set(["title", "type", "muted", ...schemaFields(rule.type).map((f) => f.key)]);
  const out = { type: rule.type, title: rule.title ?? "New rule", muted: !!rule.muted };
  for (const k of allowed) {
    if (k in rule && k !== "type" && k !== "title" && k !== "muted") out[k] = rule[k];
  }
  return out;
}
