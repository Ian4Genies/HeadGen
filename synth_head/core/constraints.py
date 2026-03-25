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


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_rules(path: str | Path) -> ConstraintRules:
    """Read a constraint_rules.json file and return a ConstraintRules object."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    clamps: dict[str, ClampRange] = {}
    for key, bounds in raw.get("hard_clamps", {}).items():
        clamps[key] = ClampRange(
            min=bounds.get("min"),
            max=bounds.get("max"),
        )

    return ConstraintRules(
        hard_clamps=clamps,
        relational_rules=raw.get("relational_rules", []),
    )


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


_RULE_HANDLERS = {
    "scale_follow": _apply_scale_follow,
    "conditional_clamp": _apply_conditional_clamp,
    "mutual_dampen": _apply_mutual_dampen,
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
        if "target" in rule:
            keys.add(rule["target"])
        if "source" in rule:
            keys.add(rule["source"])
        condition = rule.get("condition", {})
        if "param" in condition:
            keys.add(condition["param"])
        for p in rule.get("params", []):
            keys.add(p)
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
