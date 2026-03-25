"""
Per-frame reset for all animated channels.

Zeroes every pose bone and shape key that the pipeline touches, then
keyframes the neutral values.  This guarantees that any channel *not*
explicitly set by generation code sits safely at its rest pose on every
frame — no ghost values leak from prior frames.
"""

from __future__ import annotations

import bpy


def reset_bones(
    chaos_joints: list[bpy.types.PoseBone],
    frame: int,
) -> None:
    """Reset all chaos joints to rest pose and keyframe on *frame*."""
    for bone in chaos_joints:
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)

        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def reset_shape_keys(
    mesh_obj: bpy.types.Object,
    frame: int,
) -> None:
    """Reset every shape key (except Basis) to 0.0 and keyframe on *frame*."""
    shape_keys = mesh_obj.data.shape_keys
    if shape_keys is None:
        return

    for sk in shape_keys.key_blocks:
        if sk.name == "Basis":
            continue
        sk.value = 0.0
        sk.keyframe_insert(data_path="value", frame=frame)


def reset_frame(
    chaos_joints: list[bpy.types.PoseBone],
    mesh_obj: bpy.types.Object,
    frame: int,
) -> None:
    """Full per-frame reset: bones + shape keys at neutral, keyed."""
    reset_bones(chaos_joints, frame)
    reset_shape_keys(mesh_obj, frame)
