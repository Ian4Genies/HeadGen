"""
Single-parameter pipeline trace — catalog, stage collection, simulation.

Pure Python, no bpy.  Source of truth for Value Trace UI stage order and simulate.
"""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .config import PipelineConfig

from .attractor import PoolCache, _build_exclude_set, attract
from .blendshapes import (
    classify_expression_shapes,
    classify_variation_shapes,
    generate_single_frame_blendshape_weights,
)
from .constraints import (
    constrain,
    flatten_params,
    relational_rule_write_keys,
    rule_is_muted,
)
from .rerandomize import (
    ParamKind,
    _sample_joint_targets_with_symmetry,
    build_param_registry,
    expand_constraint_peers,
    param_range,
    resolve_targets,
    sample_value,
    _canonical_left_joint_key,
    _mirror_partner_joint_name,
)
from .variation import generate_bone_property_values, generate_single_frame_transforms

TraceMode = Literal["randomize_face", "rerandomize"]

STAGE_GENERATION = "generation"
STAGE_ATTRACTOR = "attractor"
STAGE_CONSTRAINTS = "constraints"
STAGE_RERANDOMIZE = "rerandomize"
STAGE_READ = "read"
STAGE_RESAMPLE = "resample"


def rule_references_param(rule: dict, key: str) -> bool:
    """True if *key* appears anywhere in a relational rule."""
    if rule.get("target") == key:
        return True
    if rule.get("source") == key:
        return True
    if rule.get("numerator") == key or rule.get("denominator") == key:
        return True
    if rule.get("param_a") == key or rule.get("param_b") == key:
        return True
    if rule.get("floor") == key or rule.get("ceiling") == key:
        return True
    if key in rule.get("params", []):
        return True
    condition = rule.get("condition", {})
    if condition.get("param") == key:
        return True
    for cond_key in ("if", "and"):
        cond = rule.get(cond_key, {})
        if cond.get("param") == key:
            return True
    then_clamp = rule.get("then_clamp", {})
    if then_clamp.get("param") == key:
        return True
    for driver in rule.get("drivers", []):
        if driver.get("param") == key:
            return True
    return False


def rule_writes_param(rule: dict, key: str) -> bool:
    """True if a relational rule may write *key*."""
    return key in relational_rule_write_keys(rule)


def _blendshape_subtype(cfg: "PipelineConfig", key: str) -> str | None:
    if key in cfg.blendshapes.independent_shapes:
        return "independent"
    if key in cfg.blendshapes.variation_shapes:
        return "variation"
    if key in cfg.blendshapes.expression_shapes:
        return "expression"
    return None


def _feature_group(name: str) -> str | None:
    if "_" not in name:
        return None
    return name.split("_", 1)[0]


def _symmetry_partner_key(key: str, kind: ParamKind) -> str | None:
    if kind == "joint":
        parts = key.split(".")
        if len(parts) != 3:
            return None
        joint, ch, ax = parts
        partner = _mirror_partner_joint_name(joint)
        if partner is None:
            return None
        return f"{partner}.{ch}.{ax}"
    return None


def _param_metadata(cfg: "PipelineConfig", key: str) -> dict[str, Any]:
    registry, _ = build_param_registry(cfg)
    kind = registry.get(key)
    if kind is None:
        raise KeyError(f"Unknown trace parameter: {key!r}")

    lo, hi = param_range(key, cfg)
    meta: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "canonical_key": _canonical_left_joint_key(key) if kind == "joint" else key,
        "value_range": {"min": lo, "max": hi},
    }
    if kind == "joint":
        meta["symmetry_partner"] = _symmetry_partner_key(key, kind)
    elif kind == "blendshape":
        sub = _blendshape_subtype(cfg, key)
        meta["blendshape_subtype"] = sub
        if sub == "variation":
            meta["feature_group"] = _feature_group(key)
    return meta


def build_trace_catalog(cfg: "PipelineConfig") -> dict[str, Any]:
    """Grouped param list with metadata for the Value Trace picker."""
    registry, warnings = build_param_registry(cfg)
    var_groups = classify_variation_shapes(cfg.blendshapes.variation_shapes)

    entries: list[dict[str, Any]] = []
    for key, kind in sorted(registry.items()):
        entry: dict[str, Any] = {"key": key, "kind": kind}
        if kind == "blendshape":
            sub = _blendshape_subtype(cfg, key)
            entry["blendshape_subtype"] = sub
            if sub == "variation":
                entry["feature_group"] = _feature_group(key)
                entry["group_members"] = var_groups.get(_feature_group(key) or "", [])
        elif kind == "joint":
            entry["symmetry_partner"] = _symmetry_partner_key(key, kind)
        entries.append(entry)

    grouped = {
        "joint": [e for e in entries if e["kind"] == "joint"],
        "variation_shapes": [e for e in entries if e.get("blendshape_subtype") == "variation"],
        "expression_shapes": [e for e in entries if e.get("blendshape_subtype") == "expression"],
        "independent_shapes": [e for e in entries if e.get("blendshape_subtype") == "independent"],
        "bone_properties": [e for e in entries if e["kind"] == "bone_property"],
    }
    return {"groups": grouped, "all_keys": sorted(registry.keys()), "warnings": warnings}


def _filter_joint_overrides(overrides: dict, key: str) -> dict:
    parts = key.split(".")
    if len(parts) != 3:
        return {}
    joint, channel, axis = parts
    out = {}
    for k, v in overrides.items():
        if k == f"{joint}.{channel}.{axis}":
            out[k] = v
        elif k == f"{joint}.{channel}":
            out[k] = v
        elif k == joint:
            out[k] = v
    return out


def _is_attractor_excluded(key: str, exclude_patterns: list[str], all_keys: list[str]) -> bool:
    excluded = _build_exclude_set(exclude_patterns, all_keys)
    return key in excluded


def _is_rerandomize_target(cfg: "PipelineConfig", key: str) -> bool:
    if not cfg.rerandomize.enabled:
        return False
    for entry in cfg.rerandomize.targets:
        resolved, errors = resolve_targets([entry.strip()], cfg)
        if errors:
            continue
        if any(t.key == key or t.key == _canonical_left_joint_key(key) for t in resolved):
            return True
    return False


def _hard_clamp_dict(cr) -> dict:
    return {"min": cr.min, "max": cr.max, "muted": cr.muted}


def _generation_stage(cfg: "PipelineConfig", key: str, kind: ParamKind) -> dict[str, Any]:
    notes: list[str] = []
    slice_data: dict[str, Any] = {}
    has_config = True

    if kind == "joint":
        canon = _canonical_left_joint_key(key)
        parts = canon.split(".")
        channel = parts[1] if len(parts) == 3 else ""
        overrides = _filter_joint_overrides(cfg.variation.joint_overrides, canon)
        slice_data = {
            "transform_max": cfg.variation.transform_max,
            "rotate_max": cfg.variation.rotate_max,
            "scale_max": cfg.variation.scale_max,
            "enable_scale": cfg.variation.enable_scale,
            "overrides": overrides,
        }
        has_config = bool(overrides) or channel in ("location", "rotation", "scale")
        if key != canon:
            notes.append(f"Right-side key — ranges from canonical {canon}")
        partner = _symmetry_partner_key(canon, "joint")
        if partner:
            notes.append("L/R pairs mirror: Left X loc negated; Left Y/Z rot negated for Right")
    elif kind == "bone_property":
        spec = cfg.variation.bone_properties.get(key, {})
        slice_data = {"bone_properties": {key: spec}}
        has_config = bool(spec)
    elif kind == "blendshape":
        sub = _blendshape_subtype(cfg, key)
        if sub == "independent":
            spec = cfg.blendshapes.independent_shapes.get(key, {})
            slice_data = {"independent_shapes": {key: spec}}
            has_config = bool(spec)
        elif sub == "variation":
            fg = _feature_group(key) or ""
            groups = classify_variation_shapes(cfg.blendshapes.variation_shapes)
            slice_data = {
                "feature_group": fg,
                "group_shapes": groups.get(fg, []),
                "max_var_shapes": cfg.blendshapes.max_var_shapes,
                "max_variation": cfg.blendshapes.max_variation,
                "variation_overrides": {key: cfg.blendshapes.variation_overrides.get(key)},
            }
            cap = cfg.blendshapes.variation_overrides.get(key)
            if cap is not None:
                slice_data["variation_overrides"] = {key: cap}
            notes.append("Group lottery — shape may be 0 if not selected this frame")
            has_config = key in cfg.blendshapes.variation_shapes
        elif sub == "expression":
            pairs, center = classify_expression_shapes(cfg.blendshapes.expression_shapes)
            pair_info = None
            for left, right in pairs:
                if key in (left, right):
                    pair_info = {"left": left, "right": right, "role": "pair"}
                    break
            if pair_info is None and key in center:
                pair_info = {"center": key}
            slice_data = {
                "expression_max": cfg.blendshapes.expression_max,
                "expression_overrides": {key: cfg.blendshapes.expression_overrides.get(key)},
                "pair_info": pair_info,
            }
            has_config = key in cfg.blendshapes.expression_shapes
            if cfg.blendshapes.expression_max == 0:
                notes.append("expression_max is 0 — expressions disabled")
        else:
            has_config = False

    return {
        "stage_id": STAGE_GENERATION,
        "label": "Generation",
        "config_file": "chaos_joints" if kind in ("joint", "bone_property") else "blendshapes",
        "has_config": has_config,
        "slice": slice_data,
        "notes": notes,
    }


def collect_param_stages(cfg: "PipelineConfig", key: str) -> dict[str, Any]:
    """Ordered stage list with filtered config slices for *key*."""
    meta = _param_metadata(cfg, key)
    kind = meta["kind"]
    registry, _ = build_param_registry(cfg)
    all_keys = sorted(registry.keys())

    stages: list[dict[str, Any]] = [_generation_stage(cfg, key, kind)]

    att = cfg.attractor
    excluded = _is_attractor_excluded(key, att.exclude_params, all_keys)
    att_slice = {
        "enabled": att.enabled,
        "max_influence": att.max_influence,
        "distance_weight": att.distance_weights.get(key),
        "excluded": excluded,
        "exclude_params": att.exclude_params,
    }
    att_notes: list[str] = []
    if not att.enabled:
        att_notes.append("Attractor disabled")
    elif excluded:
        att_notes.append("Parameter excluded from attractor")
    elif att.max_influence == 0:
        att_notes.append("max_influence is 0 — no nudge")

    stages.append({
        "stage_id": STAGE_ATTRACTOR,
        "label": "Attractor",
        "config_file": "attractor",
        "has_config": att.enabled and (att.distance_weights.get(key) is not None or not excluded),
        "slice": att_slice,
        "notes": att_notes,
    })

    write_rules: list[dict] = []
    read_rules: list[dict] = []
    for i, rule in enumerate(cfg.constraints.relational_rules):
        if not rule_references_param(rule, key):
            continue
        entry = {"index": i, "rule": deepcopy(rule), "muted": rule_is_muted(rule)}
        if rule_writes_param(rule, key):
            write_rules.append(entry)
        else:
            read_rules.append(entry)

    hard = cfg.constraints.hard_clamps.get(key)
    stages.append({
        "stage_id": STAGE_CONSTRAINTS,
        "label": "Constraints",
        "config_file": "constraints",
        "has_config": hard is not None or bool(write_rules) or bool(read_rules),
        "slice": {
            "hard_clamp": _hard_clamp_dict(hard) if hard else None,
            "write_rules": write_rules,
            "read_rules": read_rules,
        },
        "notes": [],
    })

    lo, hi = param_range(key, cfg) if key in registry else (0.0, 0.0)
    stages.append({
        "stage_id": STAGE_RERANDOMIZE,
        "label": "Rerandomize",
        "config_file": "rerandomize",
        "has_config": _is_rerandomize_target(cfg, key),
        "slice": {
            "enabled": cfg.rerandomize.enabled,
            "is_target": _is_rerandomize_target(cfg, key),
            "reapply_constraints": cfg.rerandomize.reapply_constraints,
            "sampling_range": {"min": lo, "max": hi},
        },
        "notes": ["Alternate path — no attractor"] if cfg.rerandomize.enabled else ["Rerandomize disabled"],
    })

    return {"metadata": meta, "stages": stages}


@dataclass
class SimStep:
    stage_id: str
    label: str
    value: float
    delta: float | None = None
    skipped: bool = False
    detail: str | None = None
    substeps: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "label": self.label,
            "value": self.value,
            "delta": self.delta,
            "skipped": self.skipped,
            "detail": self.detail,
            "substeps": self.substeps,
        }


def _step_value(flat: dict[str, float], key: str) -> float:
    return float(flat.get(key, 0.0))


def _append_step(
    steps: list[SimStep],
    stage_id: str,
    label: str,
    flat: dict[str, float],
    key: str,
    *,
    skipped: bool = False,
    detail: str | None = None,
) -> None:
    val = _step_value(flat, key)
    prev = steps[-1].value if steps else None
    delta = None if prev is None or skipped else val - prev
    steps.append(SimStep(stage_id, label, val, delta, skipped, detail))


def _resolve_sim_seed(seed: int | None) -> int:
    """Pick a concrete seed — random each call when *seed* is None."""
    return seed if seed is not None else random.randrange(0, 2**31)


def _clamp_starting_value(
    key: str,
    cfg: "PipelineConfig",
    starting_value: float | None,
) -> float | None:
    if starting_value is None:
        return None
    lo, hi = param_range(key, cfg)
    return max(lo, min(hi, float(starting_value)))


def _generate_flat(cfg: "PipelineConfig", seed: int) -> dict[str, float]:
    """Generate a complete flat param snapshot (all joints, shapes, bone props)."""
    joint_names = sorted(cfg.chaos_joint_names)
    v_cfg = deepcopy(cfg.variation)
    b_cfg = deepcopy(cfg.blendshapes)
    v_cfg.seed = seed
    b_cfg.seed = seed
    transforms = generate_single_frame_transforms(v_cfg, joint_names)
    bs = generate_single_frame_blendshape_weights(b_cfg)
    props = generate_bone_property_values(v_cfg)
    return flatten_params(transforms, {**bs, **props})


def run_full_randomize_face(
    cfg: "PipelineConfig",
    seed: int | None = None,
    *,
    trace_key: str | None = None,
    starting_value: float | None = None,
) -> dict[str, Any]:
    """Run the full Randomize Face math pipeline on every flat param.

    When *starting_value* is set, only *trace_key* is overridden after generation;
    all peer params stay from the random (or fixed-seed) draw.
    """
    seed_used = _resolve_sim_seed(seed)
    flat = _generate_flat(cfg, seed_used)
    clamped = (
        _clamp_starting_value(trace_key, cfg, starting_value)
        if trace_key is not None
        else starting_value
    )
    if clamped is not None and trace_key is not None:
        flat = dict(flat)
        flat[trace_key] = clamped

    out: dict[str, Any] = {
        "seed": seed_used,
        "starting_value": clamped,
        "param_count": len(flat),
        "flat_generate": flat,
        "flat_attract": flat,
        "flat_constrain": flat,
        "attract_skipped": False,
        "attract_detail": None,
    }

    att = cfg.attractor
    pool = PoolCache()
    joint_names = sorted(cfg.chaos_joint_names)

    if not att.enabled:
        out["attract_skipped"] = True
        out["attract_detail"] = "Attractor disabled"
    elif att.max_influence == 0:
        out["attract_skipped"] = True
        out["attract_detail"] = "max_influence is 0"
    else:
        pool.sync(att.attractive_heads_dir, joint_names)
        if pool.pool_size == 0:
            out["attract_skipped"] = True
            out["attract_detail"] = "Attractive pool empty"
        else:
            attractor_rng = random.Random(seed_used)
            flat, _, _ = attract(
                flat, pool, att, cfg.variation, cfg.blendshapes, attractor_rng,
            )
            out["flat_attract"] = flat

    out["flat_constrain"] = constrain(dict(flat), cfg.constraints)
    return out


def _rule_peer_keys(rule: dict) -> list[str]:
    keys: list[str] = []
    for k in (
        rule.get("target"),
        rule.get("source"),
        rule.get("floor"),
        rule.get("ceiling"),
        rule.get("numerator"),
        rule.get("denominator"),
        rule.get("param_a"),
        rule.get("param_b"),
    ):
        if k:
            keys.append(k)
    keys.extend(rule.get("params", []))
    if p := rule.get("condition", {}).get("param"):
        keys.append(p)
    for cond_key in ("if", "and"):
        if p := rule.get(cond_key, {}).get("param"):
            keys.append(p)
    if p := rule.get("then_clamp", {}).get("param"):
        keys.append(p)
    for driver in rule.get("drivers", []):
        if p := driver.get("param"):
            keys.append(p)
    return keys


def _peer_snapshot(flat: dict[str, float], rule: dict, trace_key: str) -> dict[str, float]:
    peers: dict[str, float] = {}
    for k in _rule_peer_keys(rule):
        if k != trace_key and k in flat:
            peers[k] = float(flat[k])
    return peers


def _constrain_with_substeps(
    flat: dict[str, float],
    cfg: "PipelineConfig",
    trace_key: str,
) -> tuple[dict[str, float], list[dict]]:
    """Apply full constraint pass rule-by-rule; record trace_key after each relevant rule."""
    from .constraints import _RULE_HANDLERS, apply_hard_clamps

    result = dict(flat)
    substeps: list[dict] = []
    rules = cfg.constraints

    for i, rule in enumerate(rules.relational_rules):
        if rule_is_muted(rule):
            continue
        handler = _RULE_HANDLERS.get(rule.get("type", ""))
        if handler is None:
            continue
        before = float(result.get(trace_key, 0.0))
        handler(result, rule)
        if rule_references_param(rule, trace_key):
            after = float(result.get(trace_key, 0.0))
            substeps.append({
                "index": i,
                "title": rule.get("title") or rule.get("type", "rule"),
                "type": rule.get("type"),
                "value": after,
                "delta": after - before,
                "writes_target": rule_writes_param(rule, trace_key),
                "peers": _peer_snapshot(result, rule, trace_key),
            })

    before_hc = float(result.get(trace_key, 0.0))
    apply_hard_clamps(result, rules.hard_clamps)
    hc = rules.hard_clamps.get(trace_key)
    if hc is not None and not hc.muted and trace_key in flat:
        after_hc = float(result.get(trace_key, 0.0))
        if abs(after_hc - before_hc) > 1e-9:
            substeps.append({
                "index": -1,
                "title": "Hard clamp",
                "type": "hard_clamp",
                "value": after_hc,
                "delta": after_hc - before_hc,
                "writes_target": True,
                "peers": {},
            })

    return result, substeps


def _constraint_peer_context(flat: dict[str, float], cfg: "PipelineConfig", trace_key: str) -> dict[str, float]:
    """Snapshot peer param values referenced by rules that touch *trace_key*."""
    ctx: dict[str, float] = {}
    for rule in cfg.constraints.relational_rules:
        if not rule_references_param(rule, trace_key):
            continue
        for k in _rule_peer_keys(rule):
            if k != trace_key and k in flat:
                ctx[k] = float(flat[k])
    return ctx


def _target_entry_for_key(cfg: "PipelineConfig", key: str, kind: ParamKind) -> str:
    if kind == "bone_property":
        return f"property:{key}"
    if kind == "blendshape":
        return f"shape:{key}"
    return key


def simulate_pipeline(
    cfg: "PipelineConfig",
    key: str,
    mode: TraceMode = "randomize_face",
    seed: int | None = None,
    starting_value: float | None = None,
    input_flat: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run pipeline math; return per-step values for *key*.

    *seed* None → fresh random seed each call.  *starting_value* overrides the
    traced param after generation while peers stay from the full random draw.
    """
    registry, _ = build_param_registry(cfg)
    if key not in registry:
        raise KeyError(f"Unknown trace parameter: {key!r}")
    kind = registry[key]

    steps: list[SimStep] = []

    lo, hi = param_range(key, cfg)
    starting_value = _clamp_starting_value(key, cfg, starting_value)

    if mode == "randomize_face":
        pipeline = run_full_randomize_face(
            cfg,
            seed,
            trace_key=key,
            starting_value=starting_value,
        )
        seed_used = pipeline["seed"]
        starting_value = pipeline["starting_value"]
        flat_gen = pipeline["flat_generate"]
        flat_att = pipeline["flat_attract"]
        gen_detail = f"starting value {starting_value}" if starting_value is not None else None
        _append_step(steps, STAGE_GENERATION, "Generate", flat_gen, key, detail=gen_detail)

        _append_step(
            steps,
            STAGE_ATTRACTOR,
            "Attract",
            flat_att,
            key,
            skipped=pipeline["attract_skipped"],
            detail=pipeline["attract_detail"],
        )

        flat_pre = dict(flat_att)
        flat, substeps = _constrain_with_substeps(flat_pre, cfg, key)
        constrain_step = SimStep(
            STAGE_CONSTRAINTS,
            "Constrain",
            _step_value(flat, key),
            _step_value(flat, key) - _step_value(flat_pre, key),
            False,
            None,
            substeps,
        )
        steps.append(constrain_step)

        final = _step_value(flat, key)
        return {
            "param_key": key,
            "mode": mode,
            "seed": seed_used,
            "starting_value": starting_value,
            "final": final,
            "value_range": {"min": lo, "max": hi},
            "full_pipeline": True,
            "param_count": pipeline["param_count"],
            "peer_context": _constraint_peer_context(flat_pre, cfg, key),
            "steps": [s.to_dict() for s in steps],
        }

    # rerandomize mode — start from a full generated frame, then resample targets
    seed_used = _resolve_sim_seed(seed)
    base = dict(input_flat) if input_flat else _generate_flat(cfg, seed_used)
    if starting_value is not None:
        base = dict(base)
        base[key] = starting_value
    _append_step(steps, STAGE_READ, "Read", base, key, detail="Full generated flat frame")

    entry = _target_entry_for_key(cfg, key, kind)
    resolved, errors = resolve_targets([entry], cfg)
    if errors:
        return {
            "param_key": key,
            "mode": mode,
            "seed": seed_used,
            "final": _step_value(base, key),
            "steps": [s.to_dict() for s in steps],
            "errors": errors,
        }

    target_keys = {t.key for t in resolved}
    target_keys |= expand_constraint_peers(target_keys, cfg.constraints)

    patched = dict(base)
    rng = random.Random(seed_used)
    for t in resolved:
        if t.kind == "joint":
            continue
        patched[t.key] = sample_value(t.key, rng, cfg)

    joint_targets = [t.key for t in resolved if t.kind == "joint"]
    if joint_targets:
        _sample_joint_targets_with_symmetry(patched, joint_targets, rng, cfg)

    _append_step(steps, STAGE_RESAMPLE, "Resample", patched, key)

    if cfg.rerandomize.reapply_constraints:
        flat_pre = dict(patched)
        result, substeps = _constrain_with_substeps(flat_pre, cfg, key)
        steps.append(SimStep(
            STAGE_CONSTRAINTS, "Constrain", _step_value(result, key),
            _step_value(result, key) - _step_value(flat_pre, key),
            False, None, substeps,
        ))
        final = _step_value(result, key)
    else:
        _append_step(
            steps, STAGE_CONSTRAINTS, "Constrain", patched, key,
            skipped=True, detail="reapply_constraints is false",
        )
        final = _step_value(patched, key)

    return {
        "param_key": key,
        "mode": mode,
        "seed": seed_used,
        "starting_value": starting_value,
        "final": final,
        "value_range": {"min": lo, "max": hi},
        "full_pipeline": True,
        "param_count": len(base),
        "peer_context": _constraint_peer_context(patched, cfg, key) if cfg.rerandomize.reapply_constraints else {},
        "steps": [s.to_dict() for s in steps],
    }
