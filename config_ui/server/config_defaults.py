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
        "join_merge_distance": 0.001,
        "lip_sew_merge_distance": 1e-6,
        "seam_weld_distance": 1e-5,
    },
    "export": {
        "include_hd_eyes": False,
        "include_boolean_cutters": True,
        "bake_hd_eye_texture_direct": False,
        "hd_eye_material_name": "eye_mat",
        "hd_eye_bake_resolution": 512,
        "clean_head_on_export": False,
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
