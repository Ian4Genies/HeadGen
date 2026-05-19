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


def read_bone_custom_props(
    armature: bpy.types.Object,
    bone_props_config: dict[str, dict],
) -> dict[str, float]:
    """Read current bone/object custom property values for all bone_properties entries.

    Routes each lookup to its target based on the config spec:
    - ``"target_bone": "<name>"`` → pose bone custom property on *armature*
    - ``"target_object": "<name>"`` → custom property on the named scene object

    Missing targets or absent properties are silently skipped.

    Args:
        armature: The armature object (used for target_bone lookups).
        bone_props_config: Config dict keyed by prop_name (from
            VariationConfig.bone_properties).

    Returns:
        ``{prop_name: float}`` for every property that was found.
    """
    result: dict[str, float] = {}
    for prop_name, spec in bone_props_config.items():
        if "target_bone" in spec:
            bone = armature.pose.bones.get(spec["target_bone"])
            if bone is not None and prop_name in bone:
                result[prop_name] = float(bone[prop_name])
        elif "target_object" in spec:
            obj = bpy.data.objects.get(spec["target_object"])
            if obj is not None and prop_name in obj:
                result[prop_name] = float(obj[prop_name])
    return result


def apply_bone_custom_prop_values(
    armature: bpy.types.Object,
    prop_values: dict[str, float],
    bone_props_config: dict[str, dict],
    frame: int,
) -> None:
    """Set bone/object custom property values from snapshot data and keyframe them.

    Routes each property to its target based on the config spec:
    - ``"target_bone": "<name>"`` → pose bone custom property on *armature*
    - ``"target_object": "<name>"`` → custom property on the named scene object

    Properties not found in *bone_props_config* or whose target doesn't exist
    are silently skipped.

    Args:
        armature: The armature object (used for target_bone lookups).
        prop_values: ``{prop_name: value}`` — values from the snapshot.
        bone_props_config: Config dict keyed by prop_name (from
            VariationConfig.bone_properties).
        frame: Blender frame number to insert keyframes on.
    """
    for prop_name, val in prop_values.items():
        spec = bone_props_config.get(prop_name)
        if spec is None:
            continue
        if "target_bone" in spec:
            bone = armature.pose.bones.get(spec["target_bone"])
            if bone is not None:
                bone[prop_name] = float(val)
                bone.keyframe_insert(f'["{prop_name}"]', frame=frame)
        elif "target_object" in spec:
            obj = bpy.data.objects.get(spec["target_object"])
            if obj is not None:
                obj[prop_name] = float(val)
                obj.keyframe_insert(f'["{prop_name}"]', frame=frame)


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
