# Constraint Rules Reference

Rules live in `data/constraint_rules.json`. The constraint engine runs
per-frame between generation and scene application — it cannot crash the
pipeline. If a rule references a parameter that doesn't exist (because a
joint or shape was pruned), the rule is silently skipped.

Run `pytest -k validate_live_rules -v` after any edit to the JSON or to the
joint/shape config lists to catch stale references.

---

## Parameter key format

Every parameter is addressed by a flat string key.

### Joint transforms

```
"<JointName>.<channel>.<axis>"
```

| Channel    | Axes       | Notes                                     |
|------------|------------|-------------------------------------------|
| `location` | `x` `y` `z` | In Blender units                         |
| `rotation` | `x` `y` `z` | In **degrees** (converted to quaternions internally) |
| `scale`    | `x` `y` `z` | Relative to 1.0 (identity = 1.0)         |

Examples:

```
"JawBind.location.y"
"LeftBrowBind.rotation.x"
"NoseBind.scale.z"
```

Available joints (from `CHAOS_JOINT_NAMES` in `core/variation.py`):

```
JawBind           MouthBind         MouthInnerBind    NoseBind
FaceBind          LeftBrowBind      RightBrowBind
LeftEyeSocketBind RightEyeSocketBind
```

### Blendshape weights

Use the shape name directly — no prefix or suffix needed.

```
"JAW_DROP"
"MOUTH_LOWERER"
"CHEEK_PUFF_L"
"eyes_female_varGp01A"
```

Weights are floats, typically `0.0` to `1.0`.

---

## Evaluation order

Rules always evaluate in this fixed order regardless of how they are written:

1. **Relational rules** — in list order, top to bottom
2. **Hard clamps** — unconditional, always last

This means: relational rules can push values around freely, but a hard clamp
on the same parameter will always win. Use hard clamps as safety nets, not as
the primary mechanism.

---

## Section: `hard_clamps`

### What it does

Unconditionally keeps a parameter within `[min, max]`. Runs after all
relational rules, so it is the final word on any value. Either `min` or `max`
may be omitted if you only need one bound.

### When to use it

- A blendshape that looks bad beyond a certain weight
- A joint translation that starts clipping geometry at extremes
- A rotation range that is physically implausible for a specific joint

### JSON format

```json
"hard_clamps": {
    "<param_key>": { "min": <float>, "max": <float> }
}
```

Both `min` and `max` are optional. Omit whichever bound you don't need.

### Examples

Limit jaw drop blendshape to 80% maximum:
```json
"JAW_DROP": { "min": 0.0, "max": 0.8 }
```

Prevent JawBind from translating too far on Y in either direction:
```json
"JawBind.location.y": { "min": -0.15, "max": 0.15 }
```

Restrict JawBind X rotation to a tighter range than the global config:
```json
"JawBind.rotation.x": { "min": -8.0, "max": 8.0 }
```

Cap cheek puff at 40% (blendshapes only ever go positive):
```json
"CHEEK_PUFF_L": { "max": 0.4 },
"CHEEK_PUFF_R": { "max": 0.4 }
```

### Boilerplate

```json
"hard_clamps": {
    "JawBind.location.y":  { "min": -0.15, "max":  0.15 },
    "JawBind.location.z":  { "min": -0.1,  "max":  0.1  },
    "JawBind.rotation.x":  { "min": -8.0,  "max":  8.0  },
    "NoseBind.rotation.x": { "min": -5.0,  "max":  5.0  },
    "JAW_DROP":            { "min":  0.0,  "max":  0.8  },
    "MOUTH_LOWERER":       { "min":  0.0,  "max":  0.5  },
    "CHEEK_PUFF_L":        {               "max":  0.4  },
    "CHEEK_PUFF_R":        {               "max":  0.4  }
}
```

---

## Section: `relational_rules`

All relational rules live in a JSON array. They execute in the order they
appear — top to bottom — before hard clamps run.

```json
"relational_rules": [
    { ... rule 1 ... },
    { ... rule 2 ... }
]
```

---

## Rule type: `scale_follow`

### What it does

Sets `target = source * factor` every frame. The target's independently
generated value is discarded and replaced by a scaled copy of the source.

Used to emulate a parent/child relationship, proportional linkage, or
any situation where one parameter should track another.

### When to use it

- MouthBind Y should loosely follow JawBind Y as the jaw opens
- An eye socket should partially follow a brow joint
- MouthInner should move at half the rate of Mouth on a given axis

### Fields

| Field    | Required | Type   | Description                                   |
|----------|----------|--------|-----------------------------------------------|
| `type`   | yes      | string | Must be `"scale_follow"`                      |
| `source` | yes      | string | Parameter key to read from                    |
| `target` | yes      | string | Parameter key to overwrite                    |
| `factor` | yes      | float  | Multiplier. Use negative values to invert.    |

If either `source` or `target` is missing from the generated data (pruned
joint/shape), the rule is skipped entirely.

### Examples

MouthBind Y follows JawBind Y at half strength:
```json
{
    "type": "scale_follow",
    "source": "JawBind.location.y",
    "target": "MouthBind.location.y",
    "factor": 0.5
}
```

MouthInnerBind Y follows JawBind Y at a quarter strength:
```json
{
    "type": "scale_follow",
    "source": "JawBind.location.y",
    "target": "MouthInnerBind.location.y",
    "factor": 0.25
}
```

MOUTH_RAISER inversely tracks MOUTH_LOWERER (when one goes up, other goes down):
```json
{
    "type": "scale_follow",
    "source": "MOUTH_LOWERER",
    "target": "MOUTH_RAISER",
    "factor": -0.5
}
```

### Boilerplate

```json
{
    "type": "scale_follow",
    "source": "JawBind.location.y",
    "target": "MouthBind.location.y",
    "factor": 0.5
}
```

---

## Rule type: `conditional_clamp`

### What it does

Watches a condition parameter and, when it crosses a threshold, applies a
temporary `min` and/or `max` to a target parameter. If the condition is not
met, the target is unchanged.

Used to prevent two parameters from combining in a way that looks bad, without
permanently restricting either one individually.

### When to use it

- When JAW_DROP is high, MOUTH_LOWERER shouldn't be allowed to stack on top
- When JawBind Y is at an extreme, restrict MouthBind rotation to avoid tearing
- When a brow shape is fully raised, prevent simultaneous brow lowering

### Fields

| Field               | Required | Type   | Description                                              |
|---------------------|----------|--------|----------------------------------------------------------|
| `type`              | yes      | string | Must be `"conditional_clamp"`                            |
| `target`            | yes      | string | Parameter to clamp when condition fires                  |
| `condition.param`   | yes      | string | Parameter to watch                                       |
| `condition.above`   | no       | float  | Fires when `condition.param` is strictly above this value |
| `condition.below`   | no       | float  | Fires when `condition.param` is strictly below this value |
| `min`               | no       | float  | Minimum applied to target when condition fires           |
| `max`               | no       | float  | Maximum applied to target when condition fires           |

You can use both `above` and `below` in the same condition — either crossing
triggers the clamp. At least one of `min` / `max` on the clamp side is
required for the rule to do anything.

If either `target` or `condition.param` is missing from the generated data,
the rule is skipped entirely.

### Examples

When JAW_DROP exceeds 50%, cap MOUTH_LOWERER at 20%:
```json
{
    "type": "conditional_clamp",
    "target": "MOUTH_LOWERER",
    "condition": { "param": "JAW_DROP", "above": 0.5 },
    "max": 0.2
}
```

When JawBind Y goes positive (forward), prevent NoseBind from also going fully forward:
```json
{
    "type": "conditional_clamp",
    "target": "NoseBind.location.y",
    "condition": { "param": "JawBind.location.y", "above": 0.05 },
    "max": 0.05
}
```

When CHEEK_PUFF_L is active, reduce LIP_CORNER_PULLER_L (they fight each other):
```json
{
    "type": "conditional_clamp",
    "target": "LIP_CORNER_PULLER_L",
    "condition": { "param": "CHEEK_PUFF_L", "above": 0.3 },
    "max": 0.3
}
```

### Boilerplate

```json
{
    "type": "conditional_clamp",
    "target": "MOUTH_LOWERER",
    "condition": { "param": "JAW_DROP", "above": 0.5 },
    "max": 0.2
}
```

---

## Rule type: `mutual_dampen`

### What it does

Monitors a group of parameters and, if their combined absolute values exceed
`max_combined`, scales all of them down proportionally until the total is
exactly `max_combined`. Values stay in ratio to each other — no single one is
favoured.

Used to prevent multiple similar or competing shapes from stacking to an
implausible combined level.

### When to use it

- JAW_DROP + JAW_THRUST should not both be near maximum simultaneously
- JAW_SIDEWAYS_LEFT + JAW_SIDEWAYS_RIGHT are mutually exclusive — their
  combined value should stay at or below 1.0
- Multiple lip shapes that fight each other

### Fields

| Field          | Required | Type         | Description                                                   |
|----------------|----------|--------------|---------------------------------------------------------------|
| `type`         | yes      | string       | Must be `"mutual_dampen"`                                     |
| `params`       | yes      | list[string] | The parameters to monitor as a group                          |
| `max_combined` | yes      | float        | Maximum allowed sum of absolute values across all listed params |

Parameters in `params` that are missing from the generated data are skipped;
the rule still runs on whichever params are present.

### Examples

JAW_DROP and JAW_THRUST can't both be near maximum:
```json
{
    "type": "mutual_dampen",
    "params": ["JAW_DROP", "JAW_THRUST"],
    "max_combined": 1.0
}
```

Jaw sideways shapes are mutually exclusive (left vs. right):
```json
{
    "type": "mutual_dampen",
    "params": ["JAW_SIDEWAYS_LEFT", "JAW_SIDEWAYS_RIGHT"],
    "max_combined": 0.8
}
```

Limit the total combined influence of all lip sucker shapes:
```json
{
    "type": "mutual_dampen",
    "params": ["LIP_SUCK_LB", "LIP_SUCK_LT", "LIP_SUCK_RB", "LIP_SUCK_RT"],
    "max_combined": 1.0
}
```

### Boilerplate

```json
{
    "type": "mutual_dampen",
    "params": ["JAW_DROP", "JAW_THRUST"],
    "max_combined": 1.0
}
```

---

## Full file boilerplate

A complete `constraint_rules.json` skeleton with all three rule types and
representative entries. Delete or adjust anything that doesn't apply.

```json
{
    "hard_clamps": {
        "JawBind.location.y":      { "min": -0.15, "max":  0.15 },
        "JawBind.location.z":      { "min": -0.1,  "max":  0.1  },
        "JawBind.rotation.x":      { "min": -8.0,  "max":  8.0  },
        "MouthBind.location.y":    { "min": -0.1,  "max":  0.1  },
        "NoseBind.rotation.x":     { "min": -5.0,  "max":  5.0  },
        "LeftBrowBind.rotation.x": { "min": -6.0,  "max":  6.0  },
        "JAW_DROP":                { "min":  0.0,  "max":  0.8  },
        "MOUTH_LOWERER":           { "min":  0.0,  "max":  0.5  },
        "CHEEK_PUFF_L":            {               "max":  0.4  },
        "CHEEK_PUFF_R":            {               "max":  0.4  }
    },
    "relational_rules": [
        {
            "type": "scale_follow",
            "source": "JawBind.location.y",
            "target": "MouthBind.location.y",
            "factor": 0.5
        },
        {
            "type": "scale_follow",
            "source": "JawBind.location.y",
            "target": "MouthInnerBind.location.y",
            "factor": 0.25
        },
        {
            "type": "conditional_clamp",
            "target": "MOUTH_LOWERER",
            "condition": { "param": "JAW_DROP", "above": 0.5 },
            "max": 0.2
        },
        {
            "type": "conditional_clamp",
            "target": "LIP_CORNER_PULLER_L",
            "condition": { "param": "CHEEK_PUFF_L", "above": 0.3 },
            "max": 0.3
        },
        {
            "type": "conditional_clamp",
            "target": "LIP_CORNER_PULLER_R",
            "condition": { "param": "CHEEK_PUFF_R", "above": 0.3 },
            "max": 0.3
        },
        {
            "type": "mutual_dampen",
            "params": ["JAW_DROP", "JAW_THRUST"],
            "max_combined": 1.0
        },
        {
            "type": "mutual_dampen",
            "params": ["JAW_SIDEWAYS_LEFT", "JAW_SIDEWAYS_RIGHT"],
            "max_combined": 0.8
        }
    ]
}
```

---

## Sanity check

After any edit to `constraint_rules.json`, or after pruning/adding joints or
shapes from the config lists, run:

```
pytest -k validate_live_rules -v
```

A passing test means every key in the JSON matches a parameter that currently
exists in the pipeline. A failing test lists every stale key so you know
exactly what to remove or rename.
