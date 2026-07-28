"""Scene-side eye socket depth fit (measure rim vs eye, write bone location)."""

from __future__ import annotations

import bpy
from mathutils import Vector

from ..core.config import PipelineConfig
from ..core.constraints import constrain, flatten_params, unflatten_params
from ..core.eye_fit import (
    EyeFitConfig,
    compute_depth_correction,
    get_transform_location_axis,
    percentile_mean,
    set_transform_location_axis,
)
from ..core.variation import ChaosTransform
from .chaos_anim import _apply_transforms_to_bones

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _bone_world_matrix(
    armature: bpy.types.Object,
    bone_name: str,
):
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone is None:
        return None, None
    return armature.matrix_world @ pose_bone.matrix, pose_bone


def _outward_axis(bone_world_matrix, axis: str, outward_sign: float) -> Vector:
    idx = _AXIS_INDEX[axis]
    local = Vector([1.0 if i == idx else 0.0 for i in range(3)])
    direction = bone_world_matrix.to_3x3() @ local
    if direction.length_squared < 1e-12:
        return Vector((0.0, 0.0, 1.0))
    direction.normalize()
    return direction * (1.0 if outward_sign >= 0.0 else -1.0)


def _evaluated_world_positions(
    obj: bpy.types.Object,
    depsgraph: bpy.types.Depsgraph,
) -> list[Vector]:
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        mw = eval_obj.matrix_world
        return [mw @ v.co for v in mesh.vertices]
    finally:
        eval_obj.to_mesh_clear()


def _vertex_group_weights(
    obj: bpy.types.Object,
    group_name: str,
) -> dict[int, float]:
    vg = obj.vertex_groups.get(group_name)
    if vg is None or obj.type != "MESH" or obj.data is None:
        return {}
    weights: dict[int, float] = {}
    gi = vg.index
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi:
                weights[v.index] = g.weight
                break
    return weights


def measure_side_gap(
    *,
    armature: bpy.types.Object,
    head_mesh: bpy.types.Object,
    eye_mesh: bpy.types.Object | None,
    bone_name: str,
    cfg: EyeFitConfig,
    depsgraph: bpy.types.Depsgraph,
) -> float | None:
    """Return eye−rim gap along outward axis, or None if sampling fails."""
    if eye_mesh is None:
        return None

    bone_mw, _ = _bone_world_matrix(armature, bone_name)
    if bone_mw is None:
        return None

    origin = bone_mw.translation
    outward = _outward_axis(bone_mw, cfg.depth_axis, cfg.outward_sign)
    radius_sq = cfg.sample_radius * cfg.sample_radius

    weights = _vertex_group_weights(head_mesh, bone_name)
    head_positions = _evaluated_world_positions(head_mesh, depsgraph)
    face_projs: list[float] = []
    for idx, co in enumerate(head_positions):
        w = weights.get(idx, 0.0)
        if w < cfg.weight_min or w > cfg.weight_max:
            continue
        if (co - origin).length_squared > radius_sq:
            continue
        face_projs.append((co - origin).dot(outward))

    if len(face_projs) < cfg.min_face_samples:
        return None

    eye_positions = _evaluated_world_positions(eye_mesh, depsgraph)
    eye_projs = [
        (co - origin).dot(outward)
        for co in eye_positions
        if (co - origin).length_squared <= radius_sq * 4.0
    ]
    if len(eye_projs) < cfg.min_eye_samples:
        # Fall back to all eye verts if radius filter is too tight
        eye_projs = [(co - origin).dot(outward) for co in eye_positions]
    if len(eye_projs) < cfg.min_eye_samples:
        return None

    rim = sum(face_projs) / len(face_projs)
    eye_front = percentile_mean(eye_projs, cfg.eye_front_percentile)
    if eye_front is None:
        return None
    return eye_front - rim


def _apply_depth_to_transforms(
    transforms: dict[str, ChaosTransform],
    cfg: EyeFitConfig,
    depth_value: float,
) -> dict[str, ChaosTransform]:
    updated = dict(transforms)
    for bone in (cfg.left_bone, cfg.right_bone):
        xform = updated.get(bone)
        if xform is None:
            continue
        updated[bone] = set_transform_location_axis(xform, cfg.depth_axis, depth_value)
    return updated


def fit_eye_sockets_on_frame(
    context: bpy.types.Context,
    pipeline_cfg: PipelineConfig,
    *,
    armature: bpy.types.Object,
    head_mesh: bpy.types.Object,
    eye_mesh_L: bpy.types.Object | None,
    eye_mesh_R: bpy.types.Object | None,
    transforms: dict[str, ChaosTransform],
    shape_weights: dict[str, float],
    chaos_joints: list[bpy.types.PoseBone],
    frame: int,
) -> tuple[dict[str, ChaosTransform], dict[str, float]]:
    """Measure side-view eye gap, correct socket depth, re-constrain, re-apply.

    Caller must already have applied *transforms* / *shape_weights* for *frame*.
    Returns updated transforms and shape/bone-prop weights after constrain.
    """
    fit_cfg = pipeline_cfg.eye_fit
    if not fit_cfg.enabled:
        return transforms, shape_weights

    left = transforms.get(fit_cfg.left_bone)
    if left is None:
        return transforms, shape_weights

    joint_names = [b.name for b in chaos_joints]
    current = dict(transforms)
    weights = dict(shape_weights)

    for _ in range(fit_cfg.max_iters):
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()

        gap_L = measure_side_gap(
            armature=armature,
            head_mesh=head_mesh,
            eye_mesh=eye_mesh_L,
            bone_name=fit_cfg.left_bone,
            cfg=fit_cfg,
            depsgraph=depsgraph,
        )
        gap_R = measure_side_gap(
            armature=armature,
            head_mesh=head_mesh,
            eye_mesh=eye_mesh_R,
            bone_name=fit_cfg.right_bone,
            cfg=fit_cfg,
            depsgraph=depsgraph,
        )

        gaps = [g for g in (gap_L, gap_R) if g is not None]
        if not gaps:
            break

        gap = sum(gaps) / len(gaps)
        if abs(gap + fit_cfg.target_inset) <= fit_cfg.tolerance:
            break

        delta = compute_depth_correction(
            gap,
            target_inset=fit_cfg.target_inset,
            max_correction=fit_cfg.max_correction,
            gain=fit_cfg.gain,
        )
        if abs(delta) < 1e-8:
            break

        depth = get_transform_location_axis(current[fit_cfg.left_bone], fit_cfg.depth_axis)
        current = _apply_depth_to_transforms(current, fit_cfg, depth + delta)
        _apply_transforms_to_bones(chaos_joints, current, frame)

    flat = flatten_params(current, weights)
    flat = constrain(flat, pipeline_cfg.constraints)
    current, weights = unflatten_params(flat, joint_names)
    _apply_transforms_to_bones(chaos_joints, current, frame)
    return current, weights


def fit_eye_sockets_from_scene(
    context: bpy.types.Context,
    pipeline_cfg: PipelineConfig,
    *,
    armature: bpy.types.Object,
    head_mesh: bpy.types.Object,
    eye_mesh_L: bpy.types.Object | None,
    eye_mesh_R: bpy.types.Object | None,
    chaos_joints: list[bpy.types.PoseBone],
    flat: dict[str, float],
    frame: int,
) -> None:
    """Fit sockets using current scene bone pose + non-joint keys from *flat*."""
    if not pipeline_cfg.eye_fit.enabled:
        return

    from ..core.math import quaternion_to_euler_degrees
    from .snapshot import read_bone_transforms

    joint_data = read_bone_transforms(armature, pipeline_cfg.chaos_joint_names)
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

    joint_names = set(pipeline_cfg.chaos_joint_names)
    shape_weights = {
        k: v for k, v in flat.items()
        if not (k.count(".") == 2 and k.split(".", 1)[0] in joint_names)
    }
    fit_eye_sockets_on_frame(
        context,
        pipeline_cfg,
        armature=armature,
        head_mesh=head_mesh,
        eye_mesh_L=eye_mesh_L,
        eye_mesh_R=eye_mesh_R,
        transforms=transforms,
        shape_weights=shape_weights,
        chaos_joints=chaos_joints,
        frame=frame,
    )
