"""
Scene read/write for selective re-randomization.

Reads keyframed parameter state at a frame and applies patched values back
to bones, shape keys, and bone custom properties.
"""

from __future__ import annotations

import bpy

from ..core.config import PipelineConfig
from ..core.constraints import flatten_params
from ..core.math import quaternion_to_euler_degrees
from ..core.rerandomize import build_param_registry
from ..core.variation import ChaosTransform
from .blendshapes import _apply_weights_to_shape_keys
from .chaos_anim import (
    apply_bone_property_values,
    apply_partial_joint_keys,
    collect_chaos_joints,
)
from .refs import get_ref
from ..core.ref_keys import (
    MESH,
    ARMATURE,
    EYE_WEDGE_R,
    EYE_WEDGE_L,
    EYE_WEDGE_R_BAKE,
    EYE_WEDGE_L_BAKE,
    R_PROJECTOR,
    L_PROJECTOR,
    EYEBROWS,
    EYELASHES,
)
from .snapshot import (
    read_bone_custom_props,
    read_bone_transforms,
    read_shape_key_values,
)


def _joint_data_to_transforms(
    joint_data: dict[str, dict],
) -> dict[str, ChaosTransform]:
    transforms: dict[str, ChaosTransform] = {}
    for name, jdata in joint_data.items():
        loc = tuple(jdata.get("location", [0.0, 0.0, 0.0]))
        scale = tuple(jdata.get("scale", [1.0, 1.0, 1.0]))
        quat = jdata.get("rotation_quaternion", [1.0, 0.0, 0.0, 0.0])
        rot = quaternion_to_euler_degrees(tuple(quat))
        transforms[name] = ChaosTransform(
            location=loc,  # type: ignore[arg-type]
            rotation=rot,
            scale=scale,  # type: ignore[arg-type]
        )
    return transforms


def read_flat_params_at_frame(
    context: bpy.types.Context,
    cfg: PipelineConfig,
    frame: int,
) -> dict[str, float]:
    """Read the pipeline flat parameter dict from the scene at *frame*."""
    armature = get_ref(context, ARMATURE)
    head_mesh = get_ref(context, MESH)
    if armature is None or head_mesh is None:
        return {}

    scene = context.scene
    prev_frame = scene.frame_current
    scene.frame_set(frame)

    try:
        joint_data = read_bone_transforms(armature, cfg.chaos_joint_names)
        transforms = _joint_data_to_transforms(joint_data)

        variation_names = (
            cfg.blendshapes.variation_shapes
            + list(cfg.blendshapes.independent_shapes.keys())
        )
        var_shapes, expr_shapes = read_shape_key_values(
            head_mesh,
            variation_names,
            cfg.blendshapes.expression_shapes,
        )
        combined_bs: dict[str, float] = {**var_shapes, **expr_shapes}
        combined_bs.update(
            read_bone_custom_props(armature, cfg.variation.bone_properties)
        )

        return flatten_params(transforms, combined_bs)
    finally:
        scene.frame_set(prev_frame)


def _parity_meshes(context: bpy.types.Context) -> list[bpy.types.Object]:
    refs = [
        MESH,
        EYE_WEDGE_R,
        EYE_WEDGE_L,
        EYE_WEDGE_R_BAKE,
        EYE_WEDGE_L_BAKE,
        R_PROJECTOR,
        L_PROJECTOR,
        EYEBROWS,
        EYELASHES,
    ]
    meshes: list[bpy.types.Object] = []
    for key in refs:
        obj = get_ref(context, key)
        if obj is not None:
            meshes.append(obj)
    return meshes


def apply_rerandomized_frame(
    context: bpy.types.Context,
    cfg: PipelineConfig,
    frame: int,
    flat: dict[str, float],
    apply_keys: set[str],
) -> None:
    """Write selected keys from *flat* back to the scene on *frame*."""
    armature = get_ref(context, ARMATURE)
    if armature is None:
        return

    registry, _ = build_param_registry(cfg)

    joint_keys = {k for k in apply_keys if registry.get(k) == "joint"}
    blendshape_keys = {k for k in apply_keys if registry.get(k) == "blendshape"}
    property_keys = {k for k in apply_keys if registry.get(k) == "bone_property"}

    scene = context.scene
    prev_frame = scene.frame_current
    scene.frame_set(frame)

    try:
        context.view_layer.objects.active = armature

        if joint_keys:
            chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)
            if chaos_joints:
                if armature.mode != "POSE":
                    bpy.ops.object.mode_set(mode="POSE")
                apply_partial_joint_keys(chaos_joints, flat, joint_keys, frame)
                if armature.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")

        if blendshape_keys:
            weights = {k: flat[k] for k in blendshape_keys if k in flat}
            for mesh_obj in _parity_meshes(context):
                _apply_weights_to_shape_keys(mesh_obj, weights, frame)

        if property_keys:
            prop_values = {k: flat[k] for k in property_keys if k in flat}
            apply_bone_property_values(
                armature,
                prop_values,
                cfg.variation.bone_properties,
                frame,
            )
    finally:
        scene.frame_set(prev_frame)
