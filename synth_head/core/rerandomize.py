"""
Selective re-randomization — pure Python, no bpy.

Re-samples a configured subset of pipeline parameters (joint transforms,
bone custom properties, blendshape weights) on an existing variation,
reusing ranges from chaos_joints.json and blendshapes.json.
"""

from __future__ import annotations

import fnmatch
import random
from dataclasses import dataclass, field
from typing import Literal

from .attractor import build_range_vectors
from .constraints import constrain, expand_joint_keys

ParamKind = Literal["joint", "bone_property", "blendshape"]

_JOINT_CHANNELS = frozenset({"location", "rotation", "scale"})
_JOINT_AXES = frozenset({"x", "y", "z"})
_JOINT_CHANNEL_ALIASES = {
    "loc": "location",
    "rotate": "rotation",
    "rot": "rotation",
}


def _normalize_joint_target(pattern: str, joint_names: frozenset[str]) -> str | None:
    """Map a joint flat key to the pipeline convention (e.g. rotate → rotation)."""
    parts = pattern.split(".")
    if len(parts) != 3:
        return None
    joint, channel, axis = parts
    if joint not in joint_names:
        return None
    channel = _JOINT_CHANNEL_ALIASES.get(channel, channel)
    if channel not in _JOINT_CHANNELS or axis not in _JOINT_AXES:
        return None
    return f"{joint}.{channel}.{axis}"


@dataclass
class RerandomizeConfig:
    enabled: bool = True
    seed: int | None = None
    reapply_constraints: bool = True
    targets: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "RerandomizeConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            seed=data.get("seed"),
            reapply_constraints=bool(data.get("reapply_constraints", True)),
            targets=list(data.get("targets", [])),
        )


@dataclass(frozen=True)
class ResolvedTarget:
    key: str
    kind: ParamKind


def build_param_registry(cfg: "PipelineConfig") -> tuple[dict[str, ParamKind], list[str]]:
    """Build key → kind lookup and return collision warnings."""
    registry: dict[str, ParamKind] = {}
    warnings: list[str] = []

    prop_keys = set(cfg.variation.bone_properties.keys())
    shape_keys = set(cfg.blendshapes.variation_shapes)
    shape_keys.update(cfg.blendshapes.expression_shapes)
    shape_keys.update(cfg.blendshapes.independent_shapes.keys())

    for key in prop_keys & shape_keys:
        warnings.append(
            f"Parameter '{key}' exists in both bone_properties and blendshapes; "
            "plain targets default to blendshape — use property:{key} to force bone property"
        )

    for key in prop_keys:
        registry[key] = "bone_property"
    for key in shape_keys:
        registry[key] = "blendshape"
    for joint in cfg.chaos_joint_names:
        for key in expand_joint_keys(joint):
            registry[key] = "joint"
    for joint in cfg.chaos_joint_names:
        if not joint.startswith("Left"):
            continue
        partner = _mirror_partner_joint_name(joint)
        if partner is None or partner in cfg.chaos_joint_names:
            continue
        for key in expand_joint_keys(partner):
            registry[key] = "joint"

    return registry, warnings


def _parse_target_entry(entry: str) -> tuple[ParamKind | None, str]:
    if entry.startswith("property:"):
        return "bone_property", entry[len("property:"):]
    if entry.startswith("shape:"):
        return "blendshape", entry[len("shape:"):]
    return None, entry


def _is_wildcard(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _match_keys(pattern: str, candidates: list[str]) -> list[str]:
    if _is_wildcard(pattern):
        return sorted(k for k in candidates if fnmatch.fnmatch(k, pattern))
    if pattern in candidates:
        return [pattern]
    return []


def _infer_kind(key: str, registry: dict[str, ParamKind]) -> ParamKind | None:
    return registry.get(key)


def resolve_targets(
    targets: list[str],
    cfg: "PipelineConfig",
) -> tuple[list[ResolvedTarget], list[str]]:
    """Expand target strings (with optional prefixes and wildcards) to resolved entries.

    Returns ``(resolved, errors)``.  On any error the resolved list may be partial;
    callers should abort when errors is non-empty.
    """
    registry, collision_warnings = build_param_registry(cfg)
    errors: list[str] = []
    for msg in collision_warnings:
        print(f"[SynthHead][Rerandomize] WARNING: {msg}")
    resolved: list[ResolvedTarget] = []
    seen: set[str] = set()

    keys_by_kind: dict[ParamKind, list[str]] = {
        "joint": [k for k, v in registry.items() if v == "joint"],
        "bone_property": [k for k, v in registry.items() if v == "bone_property"],
        "blendshape": [k for k, v in registry.items() if v == "blendshape"],
    }

    for entry in targets:
        forced_kind, pattern = _parse_target_entry(entry.strip())
        if not pattern:
            errors.append(f"Empty target entry: {entry!r}")
            continue

        if forced_kind is not None:
            matched = _match_keys(pattern, keys_by_kind[forced_kind])
            if not matched:
                errors.append(
                    f"No {forced_kind} parameters match {pattern!r}"
                )
                continue
            for key in matched:
                if key not in seen:
                    resolved.append(ResolvedTarget(key=key, kind=forced_kind))
                    seen.add(key)
            continue

        if _is_wildcard(pattern):
            matched = _match_keys(pattern, list(registry.keys()))
            if not matched:
                errors.append(f"No parameters match wildcard {pattern!r}")
                continue
            for key in matched:
                kind = registry[key]
                if key not in seen:
                    resolved.append(ResolvedTarget(key=key, kind=kind))
                    seen.add(key)
            continue

        joint_key = _normalize_joint_target(pattern, cfg.chaos_joint_names)
        if joint_key is not None:
            if joint_key not in seen:
                if joint_key != pattern:
                    print(
                        f"[SynthHead][Rerandomize] NOTE: target '{pattern}' "
                        f"normalized to '{joint_key}'"
                    )
                resolved.append(ResolvedTarget(key=joint_key, kind="joint"))
                seen.add(joint_key)
            continue

        in_shape = pattern in cfg.blendshapes.variation_shapes or pattern in cfg.blendshapes.expression_shapes or pattern in cfg.blendshapes.independent_shapes
        in_prop = pattern in cfg.variation.bone_properties

        if in_shape and in_prop:
            print(f"[SynthHead][Rerandomize] WARNING: ambiguous target '{pattern}' — defaulting to blendshape")
            kind: ParamKind = "blendshape"
        elif in_shape:
            kind = "blendshape"
        elif in_prop:
            kind = "bone_property"
        elif pattern in registry:
            kind = registry[pattern]
        else:
            errors.append(f"Unknown target parameter: {pattern!r}")
            continue

        if pattern not in seen:
            resolved.append(ResolvedTarget(key=pattern, kind=kind))
            seen.add(pattern)

    if not resolved and not errors:
        errors.append("No targets resolved — check rerandomize.json targets list")

    return resolved, errors


def _mirror_partner_joint_name(joint: str) -> str | None:
    if joint.startswith("Left"):
        return "Right" + joint[4:]
    if joint.startswith("Right"):
        return "Left" + joint[5:]
    return None


def is_joint_flat_key(key: str) -> bool:
    return _joint_flat_key_parts(key) is not None


def _expand_mirror_joint_keys(keys: set[str]) -> set[str]:
    """Ensure L/R partner flat keys are included for apply."""
    expanded = set(keys)
    for key in keys:
        parts = _joint_flat_key_parts(key)
        if parts is None:
            continue
        joint, channel, axis = parts
        partner = _mirror_partner_joint_name(joint)
        if partner is not None:
            expanded.add(f"{partner}.{channel}.{axis}")
    return expanded


def _joint_flat_key_parts(key: str) -> tuple[str, str, str] | None:
    parts = key.split(".")
    if len(parts) != 3:
        return None
    joint, channel, axis = parts
    if channel not in _JOINT_CHANNELS or axis not in _JOINT_AXES:
        return None
    return joint, channel, axis


def _canonical_left_joint_key(key: str) -> str:
    """Paired joints sample from Left* ranges; Right* targets map to Left*."""
    parts = _joint_flat_key_parts(key)
    if parts is None:
        return key
    joint, channel, axis = parts
    if joint.startswith("Right"):
        joint = "Left" + joint[5:]
    return f"{joint}.{channel}.{axis}"


def _right_value_from_left_key(left_key: str, left_value: float) -> float:
    """Mirror a Left* flat value to its Right* partner (variation symmetry rules)."""
    parts = _joint_flat_key_parts(left_key)
    if parts is None:
        return left_value
    _, channel, axis = parts
    if channel == "location" and axis == "x":
        return -left_value
    if channel == "rotation" and axis in ("y", "z"):
        return -left_value
    return left_value


def _apply_paired_joint_sample(
    patched: dict[str, float],
    left_key: str,
    value: float,
) -> set[str]:
    """Write Left* sample and mirrored Right* partner; return keys touched."""
    parts = _joint_flat_key_parts(left_key)
    if parts is None:
        patched[left_key] = value
        return {left_key}
    joint, channel, axis = parts
    partner = _mirror_partner_joint_name(joint)
    if partner is None:
        patched[left_key] = value
        return {left_key}
    right_key = f"{partner}.{channel}.{axis}"
    patched[left_key] = value
    patched[right_key] = _right_value_from_left_key(left_key, value)
    return {left_key, right_key}


def _sample_joint_targets_with_symmetry(
    patched: dict[str, float],
    joint_target_keys: list[str],
    rng: random.Random,
    cfg: "PipelineConfig",
) -> set[str]:
    """Re-sample joint flat keys, mirroring L/R pairs like variation generation."""
    written: set[str] = set()
    canon_keys: set[str] = set()
    for key in joint_target_keys:
        canon_keys.add(_canonical_left_joint_key(key))

    for left_key in sorted(canon_keys):
        value = sample_value(left_key, rng, cfg)
        written |= _apply_paired_joint_sample(patched, left_key, value)
    return written


def param_range(key: str, cfg: "PipelineConfig") -> tuple[float, float]:
    """Return ``(min, max)`` sampling range for a single flat parameter key."""
    key = _canonical_left_joint_key(key)
    mins, maxs = build_range_vectors([key], cfg.variation, cfg.blendshapes)
    return float(mins[0]), float(maxs[0])


def sample_value(key: str, rng: random.Random, cfg: "PipelineConfig") -> float:
    lo, hi = param_range(key, cfg)
    if hi <= lo:
        return lo
    return rng.uniform(lo, hi)


def expand_constraint_peers(
    target_keys: set[str],
    rules,
) -> set[str]:
    """Include relational-rule peers (e.g. winner_take_all pairs) in the apply set."""
    peers = set(target_keys)
    for rule in rules.relational_rules:
        if rule.get("type") != "winner_take_all":
            continue
        params = rule.get("params", [])
        if any(p in target_keys for p in params):
            peers.update(params)
    return peers


def _keys_changed_by_constrain(
    before: dict[str, float],
    after: dict[str, float],
    epsilon: float = 1e-9,
) -> set[str]:
    """Return flat keys whose values differ after constrain."""
    keys = set(before) | set(after)
    return {
        key for key in keys
        if abs(after.get(key, 0.0) - before.get(key, 0.0)) > epsilon
    }


def rerandomize_flat(
    flat: dict[str, float],
    resolved_targets: list[ResolvedTarget],
    rng: random.Random,
    cfg: "PipelineConfig",
) -> tuple[dict[str, float], set[str]]:
    """Patch *flat* with new samples for *resolved_targets*, optionally constrain.

    Returns ``(result_flat, apply_keys)``.  When constraints are re-applied,
    apply_keys includes winner_take_all peers and any key whose value constrain
    adjusted (e.g. NoseBind.scale.y/z after NoseBind.scale.x is re-rolled).
    """
    patched = dict(flat)
    target_keys: set[str] = set()

    joint_targets = [t.key for t in resolved_targets if t.kind == "joint"]
    for target in resolved_targets:
        if target.kind == "joint":
            continue
        patched[target.key] = sample_value(target.key, rng, cfg)
        target_keys.add(target.key)

    if joint_targets:
        target_keys |= _sample_joint_targets_with_symmetry(
            patched, joint_targets, rng, cfg,
        )

    if cfg.rerandomize.reapply_constraints:
        result = constrain(patched, cfg.constraints)
        apply_keys = expand_constraint_peers(target_keys, cfg.constraints)
        apply_keys |= _keys_changed_by_constrain(patched, result)
    else:
        result = patched
        apply_keys = set(target_keys)

    apply_keys = _expand_mirror_joint_keys(apply_keys)
    return result, apply_keys
