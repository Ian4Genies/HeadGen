"""
Rule-based constraint engine — pure Python, no bpy.

Operates on a flat dict[str, float] parameter snapshot that unifies
joint transforms and blendshape weights under a single key space.
Fully testable with pytest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .variation import ChaosTransform

# ---------------------------------------------------------------------------
# Flat-key convention
# ---------------------------------------------------------------------------
_CHANNELS = ("location", "rotation", "scale")
_AXES = ("x", "y", "z")


def _joint_key(joint: str, channel: str, axis: str) -> str:
    return f"{joint}.{channel}.{axis}"


def expand_joint_keys(joint_name: str) -> list[str]:
    """Return all 9 flat keys (loc/rot/scale × xyz) for one joint."""
    return [
        _joint_key(joint_name, ch, ax)
        for ch in _CHANNELS
        for ax in _AXES
    ]


# ---------------------------------------------------------------------------
# Flatten / unflatten
# ---------------------------------------------------------------------------

def flatten_params(
    transforms: dict[str, ChaosTransform],
    blendshape_weights: dict[str, float],
) -> dict[str, float]:
    """Merge joint transforms and blendshape weights into a single flat dict."""
    flat: dict[str, float] = {}
    for name, xform in transforms.items():
        for ch, vals in (
            ("location", xform.location),
            ("rotation", xform.rotation),
            ("scale", xform.scale),
        ):
            for ax, v in zip(_AXES, vals):
                flat[_joint_key(name, ch, ax)] = v

    flat.update(blendshape_weights)
    return flat


def unflatten_params(
    flat: dict[str, float],
    joint_names: list[str],
) -> tuple[dict[str, ChaosTransform], dict[str, float]]:
    """Split a flat dict back into joint transforms and blendshape weights.

    Keys matching ``<joint_name>.<channel>.<axis>`` become ChaosTransforms;
    everything else is returned as blendshape weights.
    """
    joint_key_set: set[str] = set()
    transforms: dict[str, ChaosTransform] = {}

    for name in joint_names:
        loc = tuple(flat[_joint_key(name, "location", ax)] for ax in _AXES)
        rot = tuple(flat[_joint_key(name, "rotation", ax)] for ax in _AXES)
        sc = tuple(flat[_joint_key(name, "scale", ax)] for ax in _AXES)
        transforms[name] = ChaosTransform(
            location=loc,  # type: ignore[arg-type]
            rotation=rot,  # type: ignore[arg-type]
            scale=sc,  # type: ignore[arg-type]
        )
        for ch in _CHANNELS:
            for ax in _AXES:
                joint_key_set.add(_joint_key(name, ch, ax))

    bs_weights = {k: v for k, v in flat.items() if k not in joint_key_set}
    return transforms, bs_weights


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ClampRange:
    min: float | None = None
    max: float | None = None


@dataclass
class ValidationReport:
    stale_keys: list[str] = field(default_factory=list)
    unconstrained_params: list[str] = field(default_factory=list)


@dataclass
class ConstraintRules:
    hard_clamps: dict[str, ClampRange] = field(default_factory=dict)
    relational_rules: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "ConstraintRules":
        clamps: dict[str, ClampRange] = {}
        for key, bounds in raw.get("hard_clamps", {}).items():
            clamps[key] = ClampRange(
                min=bounds.get("min"),
                max=bounds.get("max"),
            )
        return cls(
            hard_clamps=clamps,
            relational_rules=raw.get("relational_rules", []),
        )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_rules(path: str | Path) -> ConstraintRules:
    """Read a constraint_rules.json file and return a ConstraintRules object."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return ConstraintRules.from_dict(raw)


# ---------------------------------------------------------------------------
# Hard clamps
# ---------------------------------------------------------------------------

def apply_hard_clamps(
    flat: dict[str, float],
    clamps: dict[str, ClampRange],
) -> dict[str, float]:
    """Apply per-parameter min/max clamps. Missing keys are silently skipped."""
    for key, cr in clamps.items():
        if key not in flat:
            continue
        v = flat[key]
        if cr.min is not None:
            v = v if v >= cr.min else cr.min
        if cr.max is not None:
            v = v if v <= cr.max else cr.max
        flat[key] = v
    return flat


# ---------------------------------------------------------------------------
# Relational rules
# ---------------------------------------------------------------------------

def _apply_scale_follow(flat: dict[str, float], rule: dict) -> None:
    """target = source * factor"""
    source = rule.get("source", "")
    target = rule.get("target", "")
    factor = rule.get("factor", 1.0)
    if source not in flat or target not in flat:
        return
    flat[target] = flat[source] * factor


def _apply_conditional_clamp(flat: dict[str, float], rule: dict) -> None:
    """If condition.param crosses a threshold, clamp target."""
    target = rule.get("target", "")
    condition = rule.get("condition", {})
    cond_param = condition.get("param", "")

    if target not in flat or cond_param not in flat:
        return

    cond_val = flat[cond_param]
    triggered = False

    if "above" in condition and cond_val > condition["above"]:
        triggered = True
    if "below" in condition and cond_val < condition["below"]:
        triggered = True

    if not triggered:
        return

    v = flat[target]
    if "min" in rule:
        v = v if v >= rule["min"] else rule["min"]
    if "max" in rule:
        v = v if v <= rule["max"] else rule["max"]
    flat[target] = v


def _apply_mutual_dampen(flat: dict[str, float], rule: dict) -> None:
    """Scale listed params proportionally if their combined abs exceeds max."""
    params: list[str] = rule.get("params", [])
    max_combined: float = rule.get("max_combined", 1.0)

    present = [p for p in params if p in flat]
    if not present:
        return

    total = sum(abs(flat[p]) for p in present)
    if total <= max_combined or total == 0.0:
        return

    scale_factor = max_combined / total
    for p in present:
        flat[p] *= scale_factor


def _apply_ratio_clamp(flat: dict[str, float], rule: dict) -> None:
    """Clamp param_a when param_a / param_b exceeds a ratio threshold.

    JSON schema::

        {
          "type":      "ratio_clamp",
          "numerator": "NoseBind.scale.z",
          "denominator": "NoseBind.scale.x",
          "max_ratio": 1.4
        }

    When ``numerator / denominator > max_ratio`` (and denominator != 0),
    ``numerator`` is scaled down so the ratio equals ``max_ratio``.
    Missing params are silently skipped.
    """
    num_key: str = rule.get("numerator", "")
    den_key: str = rule.get("denominator", "")
    max_ratio: float = rule.get("max_ratio", 1.0)

    if num_key not in flat or den_key not in flat:
        return

    denominator = flat[den_key]
    if denominator == 0.0:
        return

    ratio = flat[num_key] / denominator
    if ratio <= max_ratio:
        return

    flat[num_key] = denominator * max_ratio


def _apply_product_clamp(flat: dict[str, float], rule: dict) -> None:
    """Clamp param_a when param_a * param_b exceeds a product budget.

    JSON schema::

        {
          "type":        "product_clamp",
          "param_a":     "NoseBind.scale.z",
          "param_b":     "NoseBind.scale.x",
          "max_product": 1.3
        }

    When ``param_a * param_b > max_product`` (and param_b != 0),
    ``param_a`` is scaled down so the product equals ``max_product``.
    Use this when two values should stay inversely proportional — e.g. a
    wide nose should get a shorter Z ceiling.
    Missing params are silently skipped.
    """
    a_key: str = rule.get("param_a", "")
    b_key: str = rule.get("param_b", "")
    max_product: float = rule.get("max_product", 1.0)

    if a_key not in flat or b_key not in flat:
        return

    b = flat[b_key]
    if b == 0.0:
        return

    product = flat[a_key] * b
    if product <= max_product:
        return

    flat[a_key] = max_product / b


def _apply_cross_proportion_clamp(flat: dict[str, float], rule: dict) -> None:
    """Clamp a target when two independent conditions are simultaneously true.

    JSON schema::

        {
          "type":   "cross_proportion_clamp",
          "if":     {"param": "LeftEyeSocketBind.scale.x", "above": 1.05},
          "and":    {"param": "NoseBind.scale.x", "below": 0.80},
          "then_clamp": {"param": "LeftEyeSocketBind.scale.x", "max": 1.05}
        }

    Both conditions must be satisfied simultaneously for the clamp to fire.
    Each condition supports ``"above"`` and/or ``"below"`` threshold keys.
    Missing params are silently skipped.
    """
    def _check(condition: dict) -> bool:
        param = condition.get("param", "")
        if param not in flat:
            return False
        val = flat[param]
        if "above" in condition and val <= condition["above"]:
            return False
        if "below" in condition and val >= condition["below"]:
            return False
        return True

    if_cond = rule.get("if", {})
    and_cond = rule.get("and", {})

    if not (_check(if_cond) and _check(and_cond)):
        return

    then_clamp = rule.get("then_clamp", {})
    target = then_clamp.get("param", "")
    if target not in flat:
        return

    v = flat[target]
    if "min" in then_clamp:
        v = v if v >= then_clamp["min"] else then_clamp["min"]
    if "max" in then_clamp:
        v = v if v <= then_clamp["max"] else then_clamp["max"]
    flat[target] = v


def _apply_conditional_bias(flat: dict[str, float], rule: dict) -> None:
    """Drive a target up or down based on one or more param signals.

    Each driver remaps its param from an input ``range`` to a 0–1 signal via
    ``map``.  Signals are combined with ``combine`` (``"min"``, ``"max"``, or
    ``"average"``; default ``"min"``).

    ``direction`` controls the effect:

    * ``"raise"`` (default) — target is set to ``max(current, signal * max_bias)``.
      The target will never be *lowered* below its generated value.
    * ``"suppress"`` — target is set to ``min(current, (1 - signal) * max_bias)``.
      As the signal grows (conditions intensify), the ceiling shrinks toward 0.
      The target will never be *raised* above its generated value.

    JSON schema (raise — bias up)::

        {
          "type":      "conditional_bias",
          "target":    "nose_male_varGp01G",
          "direction": "raise",
          "drivers": [
            {"param": "NoseBind.rotation.x", "range": [0.0, 8.0], "map": [0.0, 1.0]},
            {"param": "NoseBind.scale.x",    "range": [1.0, 0.7], "map": [0.0, 1.0]}
          ],
          "combine":  "min",
          "max_bias": 1.0
        }

    JSON schema (suppress — push ceiling down aggressively)::

        {
          "type":      "conditional_bias",
          "target":    "nose_female_varGp01K",
          "direction": "suppress",
          "drivers": [
            {"param": "NoseBind.rotation.x", "range": [0.0, 8.0], "map": [0.0, 1.0]},
            {"param": "NoseBind.scale.x",    "range": [1.0, 0.7], "map": [0.0, 1.0]}
          ],
          "combine":  "min",
          "max_bias": 1.0
        }

    ``range`` is [in_lo, in_hi] — the param value range to remap.
    ``map``   is [out_lo, out_hi] — the output signal range (usually [0, 1]).
    Values outside ``range`` are clamped to the mapped boundary.
    Missing params skip that driver (it contributes 0 to the combined signal).
    """
    target = rule.get("target", "")
    if target not in flat:
        return

    drivers: list[dict] = rule.get("drivers", [])
    combine: str = rule.get("combine", "min")
    max_bias: float = float(rule.get("max_bias", 1.0))
    direction: str = rule.get("direction", "raise")

    signals: list[float] = []
    for driver in drivers:
        param = driver.get("param", "")
        if param not in flat:
            signals.append(0.0)
            continue
        in_lo, in_hi = driver["range"]
        out_lo, out_hi = driver["map"]
        val = flat[param]
        if in_hi == in_lo:
            t = 0.0
        else:
            t = (val - in_lo) / (in_hi - in_lo)
        t = max(0.0, min(1.0, t))
        signals.append(out_lo + t * (out_hi - out_lo))

    if not signals:
        return

    if combine == "max":
        combined = max(signals)
    elif combine == "average":
        combined = sum(signals) / len(signals)
    else:
        combined = min(signals)

    if direction == "suppress":
        ceiling = (1.0 - combined) * max_bias
        flat[target] = min(flat[target], ceiling)
    else:
        bias_floor = combined * max_bias
        flat[target] = max(flat[target], bias_floor)


_RULE_HANDLERS = {
    "scale_follow": _apply_scale_follow,
    "conditional_clamp": _apply_conditional_clamp,
    "mutual_dampen": _apply_mutual_dampen,
    "ratio_clamp": _apply_ratio_clamp,
    "product_clamp": _apply_product_clamp,
    "cross_proportion_clamp": _apply_cross_proportion_clamp,
    "conditional_bias": _apply_conditional_bias,
}


def apply_relational_rules(
    flat: dict[str, float],
    rules: list[dict],
) -> dict[str, float]:
    """Evaluate relational rules in order. Unknown types are silently skipped."""
    for rule in rules:
        handler = _RULE_HANDLERS.get(rule.get("type", ""))
        if handler is not None:
            handler(flat, rule)
    return flat


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def constrain(
    flat: dict[str, float],
    rules: ConstraintRules,
) -> dict[str, float]:
    """Apply relational rules then hard clamps to a flat parameter snapshot."""
    flat = apply_relational_rules(flat, rules.relational_rules)
    flat = apply_hard_clamps(flat, rules.hard_clamps)
    return flat


# ---------------------------------------------------------------------------
# Validation (offline — never called in the pipeline)
# ---------------------------------------------------------------------------

def _collect_rule_keys(rules: ConstraintRules) -> set[str]:
    """Return every parameter key referenced by any rule."""
    keys: set[str] = set()
    keys.update(rules.hard_clamps.keys())
    for rule in rules.relational_rules:
        # scale_follow / conditional_clamp
        if "target" in rule:
            keys.add(rule["target"])
        if "source" in rule:
            keys.add(rule["source"])
        condition = rule.get("condition", {})
        if "param" in condition:
            keys.add(condition["param"])
        # mutual_dampen
        for p in rule.get("params", []):
            keys.add(p)
        # ratio_clamp
        if "numerator" in rule:
            keys.add(rule["numerator"])
        if "denominator" in rule:
            keys.add(rule["denominator"])
        # product_clamp
        if "param_a" in rule:
            keys.add(rule["param_a"])
        if "param_b" in rule:
            keys.add(rule["param_b"])
        # cross_proportion_clamp
        for cond_key in ("if", "and"):
            cond = rule.get(cond_key, {})
            if "param" in cond:
                keys.add(cond["param"])
        then_clamp = rule.get("then_clamp", {})
        if "param" in then_clamp:
            keys.add(then_clamp["param"])
        # conditional_bias
        if "target" in rule and rule.get("type") == "conditional_bias":
            keys.add(rule["target"])
        for driver in rule.get("drivers", []):
            if "param" in driver:
                keys.add(driver["param"])
    return keys


def _collect_constrained_keys(rules: ConstraintRules) -> set[str]:
    """Return every parameter key that is constrained (clamped or targeted)."""
    return _collect_rule_keys(rules)


def validate_rules(
    rules: ConstraintRules,
    known_params: set[str],
) -> ValidationReport:
    """Cross-reference rules against known params.

    Returns a ValidationReport with:
    - stale_keys: rule keys that don't exist in known_params
    - unconstrained_params: known params with zero rules (informational)
    """
    rule_keys = _collect_rule_keys(rules)
    constrained = _collect_constrained_keys(rules)

    stale = sorted(k for k in rule_keys if k not in known_params)
    unconstrained = sorted(k for k in known_params if k not in constrained)

    return ValidationReport(
        stale_keys=stale,
        unconstrained_params=unconstrained,
    )
