"""
Projection scene utilities — bake-settings application and per-frame eye baking.

All functions here touch the live Blender scene.
"""

from __future__ import annotations

from pathlib import Path

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


def _build_pass_filter(settings: BakeSettings) -> set[str]:
    """Derive the ``pass_filter`` set that ``bpy.ops.object.bake`` expects."""
    pf: set[str] = set()
    if settings.use_pass_direct:
        pf.add("DIRECT")
    if settings.use_pass_indirect:
        pf.add("INDIRECT")
    if settings.use_pass_color:
        pf.add("COLOR")
    return pf


def bake_eye_side(
    context: bpy.types.Context,
    bake_obj: bpy.types.Object,
    target_obj: bpy.types.Object,
    diffuse_node_name: str,
    out_path: Path,
    resolution: int,
    settings: BakeSettings,
) -> None:
    """Bake one eye side for the current frame and write the result to *out_path*.

    Args:
        bake_obj: Source object (e.g. eye_wedge_R_bake) — selected.
        target_obj: Destination wedge (e.g. eye_wedge_R) — active.
        diffuse_node_name: Name of the Image Texture node on *target_obj*'s
            material that receives the bake (e.g. ``"bake-diffuse"``).
        out_path: Fully resolved PNG path for this frame.
        resolution: Bake image width/height in pixels.
        settings: BakeSettings controlling engine, passes, margins, etc.
    """
    view_layer = context.view_layer

    material = target_obj.active_material
    if material is None or material.node_tree is None:
        raise RuntimeError(
            f"No active material with a node tree on {target_obj.name!r}"
        )

    node = material.node_tree.nodes.get(diffuse_node_name)
    if node is None:
        raise RuntimeError(
            f"Node {diffuse_node_name!r} not found on material "
            f"{material.name!r} of {target_obj.name!r}"
        )

    prev_image = node.image
    prev_active = material.node_tree.nodes.active

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    image = bpy.data.images.new(
        name="_EyeBakeTemp",
        width=resolution,
        height=resolution,
        alpha=False,
        float_buffer=False,
    )
    image.file_format = "PNG"
    image.filepath_raw = str(out_path)

    try:
        node.image = image
        for n in material.node_tree.nodes:
            n.select = False
        node.select = True
        material.node_tree.nodes.active = node

        bpy.ops.object.select_all(action="DESELECT")
        bake_obj.select_set(True)
        target_obj.select_set(True)
        view_layer.objects.active = target_obj

        bpy.ops.object.bake(
            type=settings.bake_type,
            pass_filter=_build_pass_filter(settings),
            use_selected_to_active=settings.use_selected_to_active,
        )

        image.save_render(filepath=str(out_path))

    finally:
        node.image = prev_image
        material.node_tree.nodes.active = prev_active
        bpy.data.images.remove(image, do_unlink=True)


def point_image_sequence_node(
    target_obj: bpy.types.Object,
    sequence_node_name: str,
    first_frame_path: Path,
    frame_start: int,
    frame_count: int,
) -> None:
    """Wire a baked image sequence into *target_obj*'s material node.

    Blender detects the numeric portion of the filename and auto-increments
    it per frame, so the caller only needs to supply the first frame's path.

    Args:
        target_obj: The eye wedge whose material has the sequence node.
        sequence_node_name: Name of the Image Texture node to populate
            (e.g. ``"baked-sequence"``).
        first_frame_path: Full path to the first frame's PNG.
        frame_start: First frame number in the sequence.
        frame_count: Total number of frames.
    """
    material = target_obj.active_material
    if material is None or material.node_tree is None:
        raise RuntimeError(
            f"No active material with a node tree on {target_obj.name!r}"
        )

    node = material.node_tree.nodes.get(sequence_node_name)
    if node is None:
        raise RuntimeError(
            f"Node {sequence_node_name!r} not found on material "
            f"{material.name!r} of {target_obj.name!r}"
        )

    image = bpy.data.images.load(filepath=str(first_frame_path))
    image.source = "SEQUENCE"

    node.image = image
    node.image_user.frame_start = frame_start
    node.image_user.frame_duration = frame_count
    node.image_user.frame_offset = 0
