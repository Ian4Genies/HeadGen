"""Default config fragments for profile backfill — mirrors synth_head.core.config fallbacks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Top-level keys only; merged into existing profile JSON when missing.
DEFAULT_CONFIG_FILES: dict[str, dict[str, Any]] = {
    "featureFlags": {
        "wedgeProjection": True,
    },
    "cleanup": {
        "remove_mouth_bag": True,
        "sew_lips": True,
        "snap_lips": True,
        "join_merge_distance": 1e-7,
        "lip_sew_merge_distance": 1e-8,
        "seam_weld_distance": 1e-7,
    },
    "export": {
        "include_hd_eyes": False,
        "include_boolean_cutters": True,
        "bake_hd_eye_texture_direct": False,
        "hd_eye_material_name": "eye_mat",
        "hd_eye_bake_resolution": 512,
        "clean_head_on_export": False,
    },
    "eye_fit": {
        "enabled": True,
        "depth_axis": "y",
        "left_bone": "LeftEyeSocketBind",
        "right_bone": "RightEyeSocketBind",
        "target_inset": 0.002,
        "max_correction": 0.05,
        "max_iters": 4,
        "gain": 0.5,
        "tolerance": 0.0005,
        "weight_min": 0.1,
        "weight_max": 0.9,
        "sample_radius": 0.08,
        "eye_front_percentile": 0.9,
        "outward_sign": 1.0,
        "min_face_samples": 8,
        "min_eye_samples": 8,
    },
    "materials": {
        "heterochromia_probability": 0.0,
    },
    "auth_head_variations": {
        "enabled": False,
        "name_prefix": "auth_",
        "vary_materials": False,
        "vary_texture_swap": False,
    },
    "texture_swap": {
        "random_texture_color": True,
    },
}


def deep_merge_missing(base: dict[str, Any], defaults: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return *base* with any missing keys filled from *defaults* (recursive for dicts)."""
    out = dict(base)
    changed = False
    for key, default in defaults.items():
        if key not in out:
            out[key] = deepcopy(default)
            changed = True
        elif isinstance(default, dict) and isinstance(out.get(key), dict):
            merged, sub = deep_merge_missing(out[key], default)
            if sub:
                out[key] = merged
                changed = True
    return out, changed
