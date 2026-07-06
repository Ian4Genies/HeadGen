"""Chaos joints UI schema — mirrors synth_head.core.variation.VariationConfig."""

from __future__ import annotations

from synth_head.core.variation import (
    CHAOS_JOINT_NAMES,
    DEFAULT_JOINT_OVERRIDES,
    mirror_partner_joint,
    sync_mirror_joint_names,
)

# Joints that must never be added to joint_names (workspace rule).
BLOCKED_JOINT_NAMES = frozenset({"NeckBind"})

# Right* joints are mirrored from Left* at runtime — do not add separately.
MIRROR_PREFIX = "Right"


def left_partner(right_name: str) -> str | None:
    if not right_name.startswith(MIRROR_PREFIX):
        return None
    return mirror_partner_joint(right_name)


def is_mirror_joint(name: str) -> bool:
    return name.startswith(MIRROR_PREFIX)


def chaos_joints_schema() -> dict:
    sample_bone_prop = {
        "min": 0.0,
        "max": 1.0,
        "target_bone": "LeftEyeSocketBind",
    }
    return {
        "globals": {
            "transform_max": {"type": "float", "label": "Location max (m)", "default": 0.2},
            "rotate_max": {"type": "float", "label": "Rotation max (°)", "default": 10.0},
            "scale_max": {"type": "float", "label": "Scale max", "default": 0.2},
            "enable_scale": {"type": "bool", "label": "Enable scale channels", "default": True},
        },
        "joint_names": {
            "type": "string_list",
            "catalog": sorted(CHAOS_JOINT_NAMES),
            "blocked": sorted(BLOCKED_JOINT_NAMES),
            "mirror_prefix": MIRROR_PREFIX,
            "note": "Left* joints mirror to Right* automatically. Do not add Right* entries.",
        },
        "overrides": {
            "type": "override_map",
            "key_pattern": "JointName.channel[.axis]",
            "value_one_of": [
                {"type": "symmetric", "description": "float → sampled from [-v, +v]; 0 locks axis"},
                {"type": "asymmetric", "fields": {"min": "float", "max": "float"}},
            ],
            "channels": [
                {"id": "location", "axes": ["x", "y", "z"], "global": "transform_max"},
                {"id": "rotation", "axes": ["x", "y", "z"], "global": "rotate_max"},
                {"id": "scale", "axes": ["x", "y", "z"], "global": "scale_max"},
            ],
            "default_keys": sorted(DEFAULT_JOINT_OVERRIDES.keys()),
        },
        "bone_properties": {
            "type": "bone_property_map",
            "entry_fields": {
                "min": {"type": "float", "required": True},
                "max": {"type": "float", "required": True},
                "target_bone": {"type": "string", "mutually_exclusive_with": "target_object"},
                "target_object": {"type": "string", "mutually_exclusive_with": "target_bone"},
            },
            "target_modes": ["bone", "object"],
            "default_entry": sample_bone_prop,
        },
    }
