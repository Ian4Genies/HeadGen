"""
Scene read/write for head snapshots.

Reads live bone transforms and shape key values from the Blender scene,
and applies saved values back.  All functions here touch the live scene.
"""

from __future__ import annotations

import bpy

from .materials import key_material_color


def read_bone_transforms(
    armature: bpy.types.Object,
    joint_names: frozenset[str],
) -> dict[str, dict]:
    """Read current pose-bone transforms for every bone in *joint_names*.

    Returns ``{bone_name: {location: [...], rotation_quaternion: [...], scale: [...]}}``.
    Bones not found on the armature are silently skipped.
    """
    result: dict[str, dict] = {}
    for bone in armature.pose.bones:
        if bone.name not in joint_names:
            continue
        result[bone.name] = {
            "location": list(bone.location),
            "rotation_quaternion": list(bone.rotation_quaternion),
            "scale": list(bone.scale),
        }
    return result


def read_shape_key_values(
    mesh_obj: bpy.types.Object,
    variation_names: list[str],
    expression_names: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Read current shape key values, split into variation and expression dicts.

    Shape names not present on the mesh are silently skipped.
    """
    variation: dict[str, float] = {}
    expression: dict[str, float] = {}

    shape_keys = mesh_obj.data.shape_keys
    if shape_keys is None:
        return variation, expression

    key_blocks = shape_keys.key_blocks

    for name in variation_names:
        sk = key_blocks.get(name)
        if sk is not None:
            variation[name] = sk.value

    for name in expression_names:
        sk = key_blocks.get(name)
        if sk is not None:
            expression[name] = sk.value

    return variation, expression


def apply_bone_transforms(
    armature: bpy.types.Object,
    joint_data: dict[str, dict],
    frame: int,
) -> None:
    """Set pose-bone transforms from *joint_data* and keyframe on *frame*.

    *joint_data* uses the same format returned by :func:`read_bone_transforms`.
    """
    for bone in armature.pose.bones:
        data = joint_data.get(bone.name)
        if data is None:
            continue

        loc = data["location"]
        bone.location.x, bone.location.y, bone.location.z = loc

        quat = data["rotation_quaternion"]
        bone.rotation_quaternion.w = quat[0]
        bone.rotation_quaternion.x = quat[1]
        bone.rotation_quaternion.y = quat[2]
        bone.rotation_quaternion.z = quat[3]

        sc = data["scale"]
        bone.scale.x, bone.scale.y, bone.scale.z = sc

        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def apply_shape_key_values(
    mesh_obj: bpy.types.Object,
    shape_data: dict[str, float],
    frame: int,
) -> None:
    """Set shape key values from *shape_data* and keyframe on *frame*.

    Shape names not present on the mesh are silently skipped.
    """
    shape_keys = mesh_obj.data.shape_keys
    if shape_keys is None:
        return

    key_blocks = shape_keys.key_blocks
    for name, value in shape_data.items():
        sk = key_blocks.get(name)
        if sk is None:
            continue
        sk.value = value
        sk.keyframe_insert(data_path="value", frame=frame)


def apply_material_color(
    mesh_obj: bpy.types.Object,
    color: list[float],
    frame: int,
) -> None:
    """Apply and keyframe a skin color from snapshot data on the first material slot.

    *color* is a [r, g, b, a] list as stored in the snapshot.
    Silently does nothing if the mesh has no material slot or color cannot be applied.
    """
    if not mesh_obj.material_slots:
        return
    mat = mesh_obj.material_slots[0].material
    if mat is None:
        return
    key_material_color(mat, tuple(color), frame)
