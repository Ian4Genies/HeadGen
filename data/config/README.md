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
| `attractor.json` | Attractive-head attractor system (nudge toward curated references) |
| `materials.json` | Skin material source file and node configuration |
| `cleanup.json` | Mesh surgery settings: mouth bag group, lip sew indices, eye wedge and body object names |

---

## runner.json

Controls the top-level pipeline run.

```json
{
  "frame_count": 400,
  "seed": null,
  "paths": {
    "fbx":            "genericGenie-0013-unified_rig.fbx",
    "save_blend":     "gen13_genie_chaos.blend",
    "issues_dir":     "head-issues",
    "good_dir":       "head-good",
    "attractive_dir": "head-attractive"
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
| `paths.good_dir` | string | Directory for good-head qualitative/quantitative snapshots, relative to `data/` |
| `paths.attractive_dir` | string | Directory for attractive-head snapshots used by the attractor system, relative to `data/` |

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
    { "type": "sandwich_clamp", ... },
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

#### `sandwich_clamp`
Keeps a target parameter sandwiched between two live anchor parameters. The permitted band is derived dynamically from the anchor values (sorted, so the rule stays stable if the anchors cross each other), then widened by `tolerance` on each side to allow controlled overshoot.

```json
{
  "type":        "sandwich_clamp",
  "target":      "MouthBind.location.y",
  "target_sign": -1,
  "floor":       "NoseBind.location.y",
  "ceiling":     "JawBind.location.y",
  "tolerance":   0.05
}
```

| Field | Type | Description |
|---|---|---|
| `target` | string | Parameter to constrain |
| `floor` | string | Lower anchor parameter |
| `ceiling` | string | Upper anchor parameter |
| `tolerance` | float | Extra wiggle room added beyond each anchor value (default `0.0`) |
| `target_sign` | int | `1` (default) or `-1`. Set to `-1` when the target joint's axis is physically inverted relative to the anchor joints |

`floor` and `ceiling` are sorted at runtime so the label is semantic only — either can be the numerically larger value without breaking the rule. Missing params are silently skipped.

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

## attractor.json

Controls the attractor system that nudges randomly generated heads toward a curated pool of attractive-head reference snapshots. Runs after generation but before constraints, so the constraint engine acts as a safety net.

```json
{
  "enabled": true,
  "attractive_heads_dir": "head-attractive",
  "min_attractors": 2,
  "max_attractors": 5,
  "max_influence": 0.2,
  "distance_weights": {},
  "exclude_params": []
}
```

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Master on/off switch for the attractor system |
| `attractive_heads_dir` | string | Directory containing attractive-head snapshot JSONs, relative to `data/` |
| `min_attractors` | int | Minimum number of attractor heads to select per generated head |
| `max_attractors` | int | Maximum number of attractor heads to select per generated head |
| `max_influence` | float | Nudge strength (0.0–1.0). Fraction of the distance between current value and attractor target to move. `0.2` = move 20% of the way |
| `distance_weights` | dict[string, float] | Per-parameter weight overrides for the distance metric. Default weight is `1.0` for all params. Higher weight = that param contributes more to distance |
| `exclude_params` | list[string] | Parameters to skip during nudging. Supports fnmatch glob patterns (e.g. `"*.rotation.*"` to exclude all rotations) |

### How it works

1. The pool of attractive-head snapshots is loaded from `attractive_heads_dir` and flattened into the same parameter space used by constraints.
2. For each generated head, `N` closest attractive heads are found using normalized Euclidean distance, where `N` is randomized between `min_attractors` and `max_attractors` (clamped to pool size).
3. Random weights are assigned to the selected heads (summing to 1.0) and a weighted-average target is computed.
4. Each non-excluded parameter is moved toward the target: `new = current + max_influence * (target - current)`.
5. Constraints run afterward to enforce all hard limits and relational rules.

### Pool cache

The attractive-head pool is cached in memory for the duration of the Blender session. When a new attractive head is saved (via Save Head Attractive), a `_manifest.json` file in the pool directory is updated. On the next pipeline run, only new/removed files are processed incrementally.

### Disabling the attractor

Set `"enabled": false` to bypass the attractor entirely. The pipeline behaves exactly as it did before the attractor was added.

---

## materials.json

Configures the skin material source and the target color node used during generation.

```json
{
  "paths": {
    "skin_material_blend": "skin_material.blend"
  },
  "skin_material_name": "head_mat",
  "final_color_randomness": 0.1
}
```

| Field | Type | Description |
|---|---|---|
| `paths.skin_material_blend` | string | Source `.blend` file containing the skin material, relative to `data/` |
| `skin_material_name` | string | Name of the material to append from the source file |
| `final_color_randomness` | float | Blend fraction (0.0–1.0) between the attractive color and the RNG color. `0.0` = fully attractive, `1.0` = fully random. Only used when the attractor system is active. Default `0.1` |

The material is appended once per Blender session and cached by reference. On re-runs, if a material with the same name already exists in the scene, the append step is skipped automatically.

The pipeline targets a node labelled `"head_color"` inside the material's node tree to keyframe skin color variation. This must be an RGB node with that label set in the Blender node editor.

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

---

## cleanup.json

Controls the **Clean Mesh** operator, which performs all one-time mesh surgery after the Variation Pipeline runs. Operations happen in a single bmesh session so shape keys and animation data are preserved.

```json
{
  "paths": {
    "assets_blend_path": "assets.blend"
  },
  "eye_wedge_R_name": "eye_wedge_R",
  "eye_wedge_L_name": "eye_wedge_L",
  "mouth_bag_group": "MouthBag",
  "mouth_sew_indices": {
    "123": 456,
    "124": 457
  }
}
```

| Field | Type | Description |
|---|---|---|
| `paths.assets_blend_path` | string | Source `.blend` file for appended assets, relative to `data/` |
| `eye_wedge_R_name` | string | Scene name of the right eye wedge object to ingest into the head mesh |
| `eye_wedge_L_name` | string | Scene name of the left eye wedge object to ingest into the head mesh |
| `mouth_bag_group` | string | Vertex group name on the head mesh whose vertices are deleted (the interior mouth bag geometry) |
| `mouth_sew_indices` | object | Pairs of head-mesh vertex indices to snap and merge, closing the lip border after the mouth bag is removed. Keys and values are both indices into the **original untransformed head mesh**. |

### mouth_sew_indices format

```json
"mouth_sew_indices": {
  "<idx_A>": <idx_B>
}
```

Each entry merges vertex `idx_A` onto vertex `idx_B` (both are head-mesh vertex indices). These values must be recorded from the original FBX head mesh before any surgery is applied. Obtain them by entering Edit Mode in Blender, enabling Vertex Index overlay (Overlays → Statistics or the N-panel), and noting paired lip-border vertex indices.

### Mesh surgery order

1. Lip borders are snapped together using `mouth_sew_indices` and welded.
2. The `mouth_bag_group` vertex group is deleted.
3. Eye wedge R, eye wedge L, and the body mesh are ingested (geometry + shape keys transferred).
4. A `remove_doubles` pass welds all overlapping seam borders (eye sockets, neck).
5. The wedge and body objects are removed from the scene.

Shape keys with shared names across meshes are merged by name — each vert carries the delta from its source mesh. On welded seam verts the head's delta takes priority.
