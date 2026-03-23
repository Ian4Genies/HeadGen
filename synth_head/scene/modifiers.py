"""
Modifier helpers — apply Blender modifiers to scene objects.

All functions here touch the live Blender scene.
"""

from __future__ import annotations

import bpy

from ..core.modifiers import SmoothCorrectiveConfig


def add_smooth_corrective(
    mesh_obj: bpy.types.Object,
    config: SmoothCorrectiveConfig,
) -> bpy.types.Modifier:
    """Add a Corrective Smooth modifier to *mesh_obj* and configure it.

    Returns the newly created modifier.
    """
    mod = mesh_obj.modifiers.new(name="CorrectiveSmooth", type='CORRECTIVE_SMOOTH')
    mod.factor = config.factor
    mod.iterations = config.iterations
    mod.scale = config.scale
    mod.smooth_type = config.smooth_type
    mod.use_only_smooth = config.use_only_smooth
    mod.use_pin_boundary = config.use_pin_boundary
    mod.rest_source = config.rest_source
    return mod
