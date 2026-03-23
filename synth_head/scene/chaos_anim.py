"""
Scene operations for the chaos animation pipeline.

Applies pre-generated transform data (from core.variation) to pose bones
and inserts keyframes. All functions here touch the live Blender scene.
"""

from __future__ import annotations

import bpy

from ..core.variation import ChaosTransform


def collect_chaos_joints(
    armature: bpy.types.Object,
    joint_names: frozenset[str],
) -> list[bpy.types.PoseBone]:
    """Return the pose bones from *armature* whose names are in *joint_names*."""
    return [bone for bone in armature.pose.bones if bone.name in joint_names]


def apply_chaos_keyframes(
    context: bpy.types.Context,
    armature: bpy.types.Object,
    chaos_joints: list[bpy.types.PoseBone],
    transforms: dict[int, dict[str, ChaosTransform]],
) -> None:
    """Apply pre-generated chaos transforms and insert keyframes.

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
        for bone in chaos_joints:
            xform = joint_map.get(bone.name)
            if xform is None:
                continue
            bone.location.x, bone.location.y, bone.location.z = xform.location
            bone.rotation_euler.x, bone.rotation_euler.y, bone.rotation_euler.z = xform.rotation
            bone.scale.x, bone.scale.y, bone.scale.z = xform.scale
            bone.keyframe_insert(data_path="location", frame=frame)
            bone.keyframe_insert(data_path="rotation_euler", frame=frame)
            bone.keyframe_insert(data_path="scale", frame=frame)

    bpy.ops.object.mode_set(mode="OBJECT")
