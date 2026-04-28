"""
Projection scene utilities — bake-settings application.

All functions here touch the live Blender scene.
"""

from __future__ import annotations

import bpy

from ..core.config import BakeSettings


def apply_bake_settings(scene: bpy.types.Scene, settings: BakeSettings) -> None:
    """Apply every field of *settings* to *scene*'s render/bake properties.

    Generalised: any BakeSettings instance loaded from config works here,
    whether it came from ``eye-bake-settings`` or any future named struct
    of the same shape.
    """
    scene.render.engine = settings.render_engine

    # bake_type is stored on cycles — the Bake panel reads it from there.
    if hasattr(scene, "cycles"):
        scene.cycles.bake_type = settings.bake_type

    bake = scene.render.bake
    bake.use_pass_direct        = settings.use_pass_direct
    bake.use_pass_indirect      = settings.use_pass_indirect
    bake.use_pass_color         = settings.use_pass_color
    bake.use_selected_to_active = settings.use_selected_to_active
    bake.use_cage               = settings.use_cage
    bake.cage_extrusion         = settings.cage_extrusion
    bake.max_ray_distance       = settings.max_ray_distance
    bake.target                 = settings.target
    bake.margin_type            = settings.margin_type
    bake.margin                 = settings.margin
    bake.use_clear              = settings.use_clear
    bake.save_mode              = settings.save_mode
