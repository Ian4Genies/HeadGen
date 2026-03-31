# Synth Head — Pipeline Configuration

This directory contains the full configuration for the Synth Head generation pipeline.
To swap configurations, replace the entire `data/config/` directory and reload the addon in Blender.
All paths in `runner.json` are relative to the `data/` directory.

---

## Files

| File | Purpose |
|---|---|
| `runner.json` | Frame count, seed, and file paths |
| `chaos_joints.json` | Joint names, global transform ranges, and per-joint overrides |
| `blendshapes.json` | Variation and expression shape lists, weights, and per-shape overrides |
| `constraints.json` | Hard clamps and relational rules applied after generation |
| `modifiers.json` | Blender modifier settings (smooth corrective) |

---

## runner.json

Controls the top-level pipeline run.

```json
{
  "frame_count": 400,
  "seed": null,
  "paths": {
    "fbx":        "genericGenie-0013-unified_rig.fbx",
    "save_blend": "gen13_genie_chaos.blend",
    "issues_dir": "head-issues",
    "good_dir":   "head-good"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `frame_count` | int | Number of animation frames to generate |
| `seed` | int \| null | RNG seed for reproducibility. `null` = random each run |
| `paths.fbx` | string | Source FBX file, relative to `data/` |
| `paths.save_blend` | string | Output `.blend` file, relative to `data/` |
| `paths.issues_dir` | string | Directory for issue snapshots, relative to `data/` |
| `paths.good_dir` | string | Directory for good-head snapshots, relative to `data/` |

---

## chaos_joints.json

Controls how chaos joint transforms are generated.

```json
{
  "joint_names": ["JawBind", "NoseBind", ...],
  "transform_max": 0.2,
  "rotate_max": 10.0,
  "scale_max": 0.2,
  "enable_scale": true,
  "overrides": {
    "NoseBind.scale.x": 0.35,
    "NoseBind.rotation.x": { "min": -5.0, "max": 8.0 }
  }
}
```

### Top-level fields

| Field | Type | Description |
|---|---|---|
| `joint_names` | list[string] | Bones to include in generation |
| `transform_max` | float | Global fallback for location channels (meters) |
| `rotate_max` | float | Global fallback for rotation channels (degrees) |
| `scale_max` | float | Global fallback for scale channels (deviation from 1.0) |
| `enable_scale` | bool | If false, all scale channels stay at identity (1, 1, 1) |

### overrides

Per-joint generation ranges. Keys follow the pattern `JointName.channel` or `JointName.channel.axis`.

**Resolution order (most specific wins):**
1. `JointName.channel.axis` (e.g. `NoseBind.rotation.x`)
2. `JointName.channel` (e.g. `NoseBind.rotation`)
3. Global fallback (`rotate_max`, `transform_max`, or `scale_max`)

**Value formats:**

| Format | Example | Effect |
|---|---|---|
| `float` | `0.35` | Symmetric range: sampled from `[-0.35, +0.35]` |
| `{"min": float, "max": float}` | `{"min": -5.0, "max": 8.0}` | Asymmetric range: sampled from `[-5.0, +8.0]` |

**Special values:**
- `0.0` on any axis locks that axis to zero (no movement on that axis)

**Symmetry — Left/Right joint pairs:**
- Overrides are keyed to the `Left*` joint name; the matching `Right*` joint inherits the same range
- Location X is automatically mirrored (negated) for the right joint
- Rotation Y and Z are automatically negated for the right joint

---

## blendshapes.json

Controls variation (facial structure) and expression shape key generation.

```json
{
  "variation_shapes": ["eyes_female_varGp01A", ...],
  "max_var_shapes": 4,
  "max_variation": 1.0,
  "variation_overrides": {},

  "independent_shapes": {
    "nose_male_varGp01G": { "min": 0.0, "max": 1.0, "mirror_sides": false }
  },

  "expression_shapes": ["JAW_DROP", "BROW_LOWERER_L", ...],
  "expression_max": 0.0,
  "expression_overrides": {
    "CHEEK_PUFF_L": 0.3,
    "CHEEK_PUFF_R": 0.3
  }
}
```

### Variation shapes

| Field | Type | Description |
|---|---|---|
| `variation_shapes` | list[string] | Shape keys used for facial structure variation |
| `max_var_shapes` | int | Max number of variation shapes active per frame per feature group |
| `max_variation` | float | Total weight budget distributed across active shapes per group |
| `variation_overrides` | dict[string, float] | Per-shape weight cap (overrides `max_variation` for that shape) |

Shapes are grouped by feature prefix (`eyes_`, `jaw_`, `lips_`, `nose_`). Within each group, 1–`max_var_shapes` shapes are randomly selected and their weights sum to `max_variation`.

### Expression shapes

| Field | Type | Description |
|---|---|---|
| `expression_shapes` | list[string] | Shape keys used for facial expressions |
| `expression_max` | float | Global max weight for any expression shape. `0.0` disables expressions |
| `expression_overrides` | dict[string, float] | Per-shape max weight (overrides `expression_max` for that shape) |

`_L` / `_R` suffix pairs always receive the same random value (bilateral symmetry). `_LB`/`_RB` and `_LT`/`_RT` pairs follow the same rule.

### Independent shapes

Always-on shapes that bypass the variation group lottery entirely. Each shape gets its own random value sampled from `[min, max]` on every frame, independent of any other shape.

| Field | Type | Description |
|---|---|---|
| key | string | Shape key name |
| `min` | float | Minimum random value (usually `0.0`) |
| `max` | float | Maximum random value (usually `1.0`) |
| `mirror_sides` | bool | If `true`, the opposite-side sibling receives the same value |

**`mirror_sides` token lookup order** (first match wins):

| Token in name | Replaced with |
|---|---|
| `Left` | `Right` |
| `Right` | `Left` |
| `_LB` | `_RB` |
| `_RB` | `_LB` |
| `_LT` | `_RT` |
| `_RT` | `_LT` |
| `_L` | `_R` |
| `_R` | `_L` |

If no side token is found, `mirror_sides` has no effect.

> **Note:** shapes listed here should be removed from `variation_shapes` to avoid double-generation.

---

## constraints.json

Applied after generation to enforce hard limits and relational rules. Rules run in order — order matters for chained rules.

```json
{
  "hard_clamps": {
    "JAW_DROP": { "min": 0.0, "max": 0.8 }
  },
  "relational_rules": [
    { "type": "scale_follow", ... },
    { "type": "conditional_clamp", ... },
    { "type": "mutual_dampen", ... },
    { "type": "ratio_clamp", ... },
    { "type": "product_clamp", ... },
    { "type": "cross_proportion_clamp", ... },
    { "type": "conditional_bias", ... }
  ]
}
```

### hard_clamps

Absolute min/max applied to any parameter after all relational rules.

```json
"hard_clamps": {
  "NoseBind.rotation.x": { "min": -8.0, "max": 8.0 },
  "JAW_DROP":             { "min": 0.0,  "max": 0.8 }
}
```

Keys can be joint parameters (`JointName.channel.axis`) or blendshape names. Both `"min"` and `"max"` are optional. Hard clamp entries do not currently support a `title` field (the key name itself serves as the identifier).

---

### Relational rule types

All relational rule objects accept an optional `"title"` string field for documentation purposes. It is ignored by the constraint engine and has no effect on evaluation.

```json
{ "title": "Human-readable label", "type": "scale_follow", ... }
```

---

#### `scale_follow`
Forces `target = source × factor`. Runs before hard clamps.

```json
{
  "type":   "scale_follow",
  "source": "JawBind.location.y",
  "target": "MouthBind.location.y",
  "factor": 0.5
}
```

---

#### `conditional_clamp`
Clamps `target` only when a single condition param crosses a threshold.

```json
{
  "type":      "conditional_clamp",
  "target":    "MOUTH_LOWERER",
  "condition": { "param": "JAW_DROP", "above": 0.5 },
  "max":       0.2
}
```

`condition` supports `"above"` and/or `"below"` threshold keys.

---

#### `mutual_dampen`
Scales a group of params proportionally if their combined absolute values exceed `max_combined`.

```json
{
  "type":         "mutual_dampen",
  "params":       ["JAW_DROP", "JAW_THRUST"],
  "max_combined": 1.0
}
```

---

#### `ratio_clamp`
Scales `numerator` down when `numerator / denominator > max_ratio`. Use for proportion-based limits (e.g. nose length-to-width ratio cap).

```json
{
  "type":        "ratio_clamp",
  "numerator":   "NoseBind.scale.z",
  "denominator": "NoseBind.scale.x",
  "max_ratio":   1.1
}
```

If `denominator` is zero, the rule is silently skipped.

---

#### `product_clamp`
Scales `param_a` down when `param_a * param_b > max_product`. Use for inverse-proportion guards where two values share a total "budget" — e.g. a wide nose (`param_b` large) should have a shorter Z ceiling (`param_a` clamped down accordingly.

```json
{
  "type":        "product_clamp",
  "param_a":     "NoseBind.scale.z",
  "param_b":     "NoseBind.scale.x",
  "max_product": 1.25
}
```

**How it differs from `ratio_clamp`:**
- `ratio_clamp` prevents Z from being disproportionately large relative to X at *any* X value (fixed ceiling on the ratio).
- `product_clamp` enforces that as X grows, the allowed Z ceiling *shrinks proportionally* — a wide nose gets a tighter height limit.

Pair both rules together on the same params for full coverage: the ratio cap handles narrow/tall noses, the product cap handles wide/tall noses.

If `param_b` is zero, the rule is silently skipped.

---

#### `cross_proportion_clamp`
Clamps a target only when two independent conditions are simultaneously true. Use for cross-feature proportion guards (e.g. large eyes + small nose).

```json
{
  "type": "cross_proportion_clamp",
  "if":   { "param": "LeftEyeSocketBind.scale.x", "above": 1.05 },
  "and":  { "param": "NoseBind.scale.x",          "below": 0.80 },
  "then_clamp": { "param": "LeftEyeSocketBind.scale.x", "max": 1.05 }
}
```

Both `"if"` and `"and"` conditions support `"above"` and/or `"below"` threshold keys.
`"then_clamp"` supports `"min"` and/or `"max"`.

---

#### `conditional_bias`
Drives a target shape value up or down based on one or more parameter signals. Use `"raise"` to bias a shape higher when geometry indicates a type (e.g. upturned small nose favours a nostril shape). Use `"suppress"` to aggressively zero out a shape under the same conditions (e.g. a shape redundant with nose slimming should disappear when the nose is already narrow and upturned).

**`direction: "raise"`** — floor is raised. Target will never be set *below* its generated value.

```json
{
  "type":      "conditional_bias",
  "direction": "raise",
  "target":    "nose_male_varGp01G",
  "drivers": [
    { "param": "NoseBind.rotation.x", "range": [0.0, 8.0], "map": [0.0, 1.0] },
    { "param": "NoseBind.scale.x",    "range": [1.0, 0.7], "map": [0.0, 1.0] }
  ],
  "combine":  "min",
  "max_bias": 1.0
}
```

**`direction: "suppress"`** — ceiling is lowered. As signal grows toward 1.0, the ceiling shrinks toward 0. Target will never be set *above* its generated value.

```json
{
  "type":      "conditional_bias",
  "direction": "suppress",
  "target":    "nose_female_varGp01K",
  "drivers": [
    { "param": "NoseBind.rotation.x", "range": [0.0, 8.0], "map": [0.0, 1.0] },
    { "param": "NoseBind.scale.x",    "range": [1.0, 0.7], "map": [0.0, 1.0] }
  ],
  "combine":  "min",
  "max_bias": 1.0
}
```

| Field | Type | Description |
|---|---|---|
| `target` | string | Shape key to drive |
| `direction` | string | `"raise"` (default) or `"suppress"` |
| `drivers` | list | One or more signal sources |
| `drivers[].param` | string | Parameter to read (joint transform or shape key) |
| `drivers[].range` | [float, float] | Input value range `[in_lo, in_hi]` to remap from |
| `drivers[].map` | [float, float] | Output signal range `[out_lo, out_hi]` (usually `[0.0, 1.0]`) |
| `combine` | string | How to combine signals: `"min"` (default), `"max"`, or `"average"` |
| `max_bias` | float | Scale factor on the floor/ceiling (`raise` floor = `signal × max_bias`; `suppress` ceiling = `(1 − signal) × max_bias`) |

**How `combine` works:**
- `"min"` — *all* drivers must be active for full effect (strictest; AND-style)
- `"max"` — any single driver at peak produces full effect (OR-style)
- `"average"` — blends proportionally across all drivers

Values outside a driver's `range` are clamped to the mapped boundary. Missing params contribute `0` to the combined signal.

---

## modifiers.json

Settings for the Smooth Corrective modifier applied to the head mesh after generation.

```json
{
  "smooth_corrective": {
    "factor":           0.6,
    "iterations":       5,
    "scale":            1.0,
    "smooth_type":      "SIMPLE",
    "use_only_smooth":  false,
    "use_pin_boundary": false,
    "rest_source":      "ORCO"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `factor` | float | Smoothing strength per iteration |
| `iterations` | int | Number of smoothing passes |
| `scale` | float | Scale factor for correction vectors |
| `smooth_type` | string | `"SIMPLE"` or `"LENGTH_WEIGHTED"` |
| `use_only_smooth` | bool | If true, only smoothing is applied (no correction) |
| `use_pin_boundary` | bool | If true, boundary vertices are not moved |
| `rest_source` | string | `"ORCO"` (object rest coords) or `"BIND"` |

---

## Parameter key format

All constraint rules and hard clamps reference parameters using a flat key format:

| Parameter type | Key format | Example |
|---|---|---|
| Joint location | `JointName.location.x/y/z` | `JawBind.location.y` |
| Joint rotation | `JointName.rotation.x/y/z` | `NoseBind.rotation.x` |
| Joint scale | `JointName.scale.x/y/z` | `LeftEyeSocketBind.scale.x` |
| Blendshape weight | Shape key name | `JAW_DROP`, `CHEEK_PUFF_L` |

Rotation values are in **degrees**. Location values are in **meters** (Blender scene units). Scale values are deviations from `1.0` during generation but stored as absolute values (e.g. `1.1` = 10% larger) in constraints.
