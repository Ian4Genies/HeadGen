"""
Scene operations for the chaos animation pipeline.

Applies pre-generated transform data (from core.variation) to pose bones
and inserts keyframes. All functions here touch the live Blender scene.
"""

from __future__ import annotations

import bpy

from ..core.math import euler_degrees_to_quaternion
from ..core.variation import ChaosTransform


def collect_chaos_joints(
    armature: bpy.types.Object,
    joint_names: frozenset[str],
) -> list[bpy.types.PoseBone]:
    """Return the pose bones from *armature* whose names are in *joint_names*."""
    return [bone for bone in armature.pose.bones if bone.name in joint_names]


def _apply_transforms_to_bones(
    chaos_joints: list[bpy.types.PoseBone],
    joint_transforms: dict[str, ChaosTransform],
    frame: int,
) -> None:
    """Set bone transforms and insert keyframes for a single frame.

    Rotation values are expected in degrees and are converted to quaternions
    at this boundary.
    """
    for bone in chaos_joints:
        xform = joint_transforms.get(bone.name)
        if xform is None:
            continue

        bone.location.x, bone.location.y, bone.location.z = xform.location

        w, x, y, z = euler_degrees_to_quaternion(xform.rotation)
        bone.rotation_quaternion.w = w
        bone.rotation_quaternion.x = x
        bone.rotation_quaternion.y = y
        bone.rotation_quaternion.z = z

        bone.scale.x, bone.scale.y, bone.scale.z = xform.scale

        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def apply_chaos_keyframes(
    context: bpy.types.Context,
    armature: bpy.types.Object,
    chaos_joints: list[bpy.types.PoseBone],
    transforms: dict[int, dict[str, ChaosTransform]],
) -> None:
    """Apply pre-generated chaos transforms and insert keyframes for all frames.

    Args:
        context: The active Blender context.
        armature: The armature object to animate.
        chaos_joints: The pose bones to key (should match names in *transforms*).
        transforms: Output of core.variation.generate_chaos_transforms —
            {frame: {joint_name: ChaosTransform}}.
    """
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")

    for frame, joint_map in transforms.items():
        context.scene.frame_set(frame)
        _apply_transforms_to_bones(chaos_joints, joint_map, frame)

    bpy.ops.object.mode_set(mode="OBJECT")


def apply_chaos_single_frame(
    context: bpy.types.Context,
    armature: bpy.types.Object,
    chaos_joints: list[bpy.types.PoseBone],
    joint_transforms: dict[str, ChaosTransform],
) -> None:
    """Apply chaos transforms and insert keyframes on the current frame only.

    Args:
        context: The active Blender context.
        armature: The armature object to pose.
        chaos_joints: The pose bones to key.
        joint_transforms: Output of core.variation.generate_single_frame_transforms —
            {joint_name: ChaosTransform}.
    """
    frame = context.scene.frame_current
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")

    _apply_transforms_to_bones(chaos_joints, joint_transforms, frame)

    bpy.ops.object.mode_set(mode="OBJECT")
