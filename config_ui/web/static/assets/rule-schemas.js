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

const P = {
  target: "Parameter overwritten when the rule fires. Joint: JawBind.scale.x · Shape: JAW_DROP",
  source: "Parameter read as input. Joint: JawBind.location.y · Shape: MOUTH_LOWERER",
  param: "Flat param key. Joint: NoseBind.scale.z · Shape: CHEEK_PUFF_L",
  factor: "Multiplier on source. 0.5 = half strength. Negative inverts direction.",
  minBound: "Optional floor applied to target when the condition fires.",
  maxBound: "Optional ceiling applied to target when the condition fires.",
  maxCombined: "Max allowed sum of |value| across all listed params.",
  maxRatio: "Numerator is scaled down if numerator ÷ denominator exceeds this.",
  maxProduct: "Param A is scaled down if param_a × param_b exceeds this.",
  tolerance: "Extra slack beyond floor/ceiling anchors (same units as params).",
};

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

/** @type {Record<string, object>} */
export const RULE_SCHEMAS = {
  scale_follow: {
    label: "Scale follow",
    formula: "target = source × factor",
    description: "Replaces the target with a scaled copy of the source every frame.",
    whenToUse: "One param should track another proportionally (mouth follows jaw, inverse shape pairs).",
    example: { source: "JawBind.location.y", target: "MouthBind.location.y", factor: 0.5 },
    caveats: "The target's independently generated value is discarded.",
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "", help: P.target },
      { key: "source", label: "Source param", widget: "param", required: true, default: "", help: P.source },
      { key: "factor", label: "Factor", widget: "number", required: true, default: 0.5, help: P.factor },
    ],
  },
  conditional_clamp: {
    label: "Conditional clamp",
    formula: "if condition → clamp(target)",
    description: "Clamps target only when a watched param crosses a threshold.",
    whenToUse: "Prevent bad combos without permanently restricting either param alone.",
    example: { target: "MOUTH_LOWERER", condition: { param: "JAW_DROP", above: 0.5 }, max: 0.2 },
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "", help: P.target },
      {
        key: "condition",
        label: "Condition",
        widget: "condition",
        required: true,
        default: cond(),
        help: "Fires when param is strictly above and/or below threshold. At least one bound required on condition.",
      },
      { key: "min", label: "Min bound", widget: "number_optional", required: false, default: undefined, help: P.minBound },
      { key: "max", label: "Max bound", widget: "number_optional", required: false, default: undefined, help: P.maxBound },
    ],
  },
  mutual_dampen: {
    label: "Mutual dampen",
    formula: "scale all down if Σ|params| > max_combined",
    description: "Scales listed params proportionally when their combined absolute total exceeds a budget.",
    whenToUse: "Stop competing shapes or jaws from stacking to implausible combined levels.",
    example: { params: ["JAW_DROP", "JAW_THRUST"], max_combined: 1 },
    caveats: "Ratios between params are preserved — nothing is zeroed unless it was already zero.",
    fields: [
      {
        key: "params",
        label: "Params",
        widget: "param_list",
        required: true,
        default: [""],
        minItems: 1,
        help: "Group monitored together. Missing params are skipped; rule still runs on present ones.",
      },
      { key: "max_combined", label: "Max combined", widget: "number", required: true, default: 1, help: P.maxCombined },
    ],
  },
  ratio_clamp: {
    label: "Ratio clamp",
    formula: "if num ÷ den > max_ratio → num = den × max_ratio",
    description: "Scales numerator down when its ratio to denominator exceeds a cap.",
    whenToUse: "Proportion limits — nose length vs width, mouth height vs width.",
    example: { numerator: "NoseBind.scale.z", denominator: "NoseBind.scale.x", max_ratio: 1.6 },
    caveats: "Skipped silently when denominator is zero.",
    fields: [
      { key: "numerator", label: "Numerator", widget: "param", required: true, default: "", help: "Param scaled down when ratio is too high." },
      { key: "denominator", label: "Denominator", widget: "param", required: true, default: "", help: "Reference param for the ratio." },
      { key: "max_ratio", label: "Max ratio", widget: "number", required: true, default: 1, help: P.maxRatio },
    ],
  },
  product_clamp: {
    label: "Product clamp",
    formula: "if a × b > max_product → a = max_product ÷ b",
    description: "Scales param_a down when its product with param_b exceeds a budget.",
    whenToUse: "Inverse-proportion guards — wide nose should cap tall Z, etc.",
    example: { param_a: "NoseBind.scale.z", param_b: "NoseBind.scale.x", max_product: 1.6 },
    caveats: "Use when two dimensions share a budget; differs from ratio_clamp which caps a fixed ratio at any scale.",
    fields: [
      { key: "param_a", label: "Param A", widget: "param", required: true, default: "", help: "Param scaled down when product is too high." },
      { key: "param_b", label: "Param B", widget: "param", required: true, default: "", help: "Partner in the product budget." },
      { key: "max_product", label: "Max product", widget: "number", required: true, default: 1, help: P.maxProduct },
    ],
  },
  cross_proportion_clamp: {
    label: "Cross proportion clamp",
    formula: "if (if) AND (and) → clamp(then_clamp)",
    description: "Clamps a target when two independent conditions are both true.",
    whenToUse: "Contextual caps — e.g. limit eye socket width only when the nose is narrow.",
    example: {
      if: { param: "LeftEyeSocketBind.scale.x", above: 1.05 },
      and: { param: "NoseBind.scale.x", below: 1 },
      then_clamp: { param: "LeftEyeSocketBind.scale.x", max: 1.05 },
    },
    help: "Left* joint targets auto-mirror to Right* at runtime.",
    fields: [
      { key: "if", label: "If", widget: "condition", required: true, default: cond(), help: "First condition — must pass." },
      { key: "and", label: "And", widget: "condition", required: true, default: cond(), help: "Second condition — both must pass." },
      {
        key: "then_clamp",
        label: "Then clamp",
        widget: "clamp_spec",
        required: true,
        default: clampSpec(),
        help: "Param and min/max applied when both conditions are true.",
      },
    ],
  },
  sandwich_clamp: {
    label: "Sandwich clamp",
    formula: "floor − tolerance ≤ target ≤ ceiling + tolerance",
    description: "Keeps target between two anchor params (sorted dynamically).",
    whenToUse: "Mouth Y between nose and jaw, or any param that must stay in a live band.",
    example: {
      target: "MouthBind.location.y",
      floor: "NoseBind.location.y",
      ceiling: "JawBind.location.y",
      target_sign: -1,
      tolerance: 0.05,
    },
    fields: [
      { key: "target", label: "Target param", widget: "param", required: true, default: "", help: P.target },
      { key: "floor", label: "Floor param", widget: "param", required: true, default: "", help: "Lower anchor (auto-sorted with ceiling)." },
      { key: "ceiling", label: "Ceiling param", widget: "param", required: true, default: "", help: "Upper anchor (auto-sorted with floor)." },
      { key: "tolerance", label: "Tolerance", widget: "number", required: false, default: 0, help: P.tolerance },
      {
        key: "target_sign",
        label: "Target sign",
        widget: "enum",
        required: false,
        default: 1,
        help: "Use −1 when target axis is inverted vs anchors (e.g. MouthBind Y positive-down).",
        options: [
          { value: 1, label: "1 (normal)" },
          { value: -1, label: "-1 (inverted axis)" },
        ],
      },
    ],
  },
  conditional_bias: {
    label: "Conditional bias",
    formula: "raise: max(target, signal×max_bias) · suppress: min(target, (1−signal)×max_bias)",
    description: "Biases a blendshape up or down based on remapped driver signals.",
    whenToUse: "Nostril shapes that should rise on upturned narrow noses, or suppress on wide noses.",
    example: {
      direction: "raise",
      target: "nose_male_varGp01G",
      drivers: [{ param: "NoseBind.rotation.x", range: [0, -8], map: [0, 1] }],
      combine: "min",
      max_bias: 1,
    },
    caveats: "Blendshapes only — never lowers below generated value in raise mode, or raises above it in suppress mode.",
    fields: [
      {
        key: "direction",
        label: "Direction",
        widget: "enum",
        required: true,
        default: "raise",
        help: "raise = floor the target up; suppress = shrink the ceiling down.",
        options: [
          { value: "raise", label: "raise" },
          { value: "suppress", label: "suppress" },
        ],
      },
      { key: "target", label: "Target shape", widget: "param", required: true, default: "", help: "Blendshape name to bias." },
      {
        key: "drivers",
        label: "Drivers",
        widget: "bias_drivers",
        required: true,
        default: [driver()],
        help: "Each driver remaps a param from range → map (0–1 signal). range [in_lo, in_hi], map [out_lo, out_hi].",
      },
      {
        key: "combine",
        label: "Combine",
        widget: "enum",
        required: false,
        default: "min",
        help: "How to merge driver signals: min = all must agree (AND), max = any (OR), average.",
        options: [
          { value: "min", label: "min (AND)" },
          { value: "max", label: "max (OR)" },
          { value: "average", label: "average" },
        ],
      },
      { key: "max_bias", label: "Max bias", widget: "number", required: false, default: 1, help: "Scales the combined signal (usually 0–1)." },
    ],
  },
  winner_take_all: {
    label: "Winner take all",
    formula: "keep argmax(|params|); zero the rest",
    description: "Zeroes all listed params except the one with the largest absolute value.",
    whenToUse: "Mutually exclusive pairs — iris grow vs shrink, pupil grow vs shrink.",
    example: { params: ["var_iris_grow", "var_iris_shrink"] },
    caveats: "Ties broken by list order — first param wins.",
    fields: [
      {
        key: "params",
        label: "Params",
        widget: "param_list",
        required: true,
        default: ["", ""],
        minItems: 2,
        help: "At least two params. Missing params are skipped; need two present to run.",
      },
    ],
  },
};

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

export function schemaFor(type) {
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

export function ruleTypeFormula(type) {
  return schemaFor(type).formula ?? "";
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
