"""
Scene operations for blendshape weights.

Sets shape key values on a mesh object and inserts keyframes.
All functions here touch the live Blender scene.
"""

from __future__ import annotations

import bpy


def _apply_weights_to_shape_keys(
    mesh_obj: bpy.types.Object,
    weights: dict[str, float],
    frame: int,
) -> None:
    """Set shape key values from *weights* and insert keyframes on *frame*.

    Shape names in *weights* that don't exist on the mesh are silently skipped.
    """
    key_blocks = mesh_obj.data.shape_keys.key_blocks

    for name, value in weights.items():
        sk = key_blocks.get(name)
        if sk is None:
            continue
        sk.value = value
        sk.keyframe_insert(data_path="value", frame=frame)


def apply_blendshape_keyframes(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    weights_by_frame: dict[int, dict[str, float]],
) -> None:
    """Apply blendshape weights and keyframe them across multiple frames.

    Args:
        context: The active Blender context.
        mesh_obj: The mesh object with shape keys.
        weights_by_frame: ``{frame: {shape_name: weight}}`` — output of
            ``core.blendshapes.generate_blendshape_weights``.
    """
    for frame, weights in weights_by_frame.items():
        context.scene.frame_set(frame)
        _apply_weights_to_shape_keys(mesh_obj, weights, frame)


def apply_blendshape_single_frame(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    weights: dict[str, float],
) -> None:
    """Apply blendshape weights and keyframe them on the current frame only.

    Args:
        context: The active Blender context.
        mesh_obj: The mesh object with shape keys.
        weights: ``{shape_name: weight}`` — output of
            ``core.blendshapes.generate_single_frame_blendshape_weights``.
    """
    frame = context.scene.frame_current
    _apply_weights_to_shape_keys(mesh_obj, weights, frame)
