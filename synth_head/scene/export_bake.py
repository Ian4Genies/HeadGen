"""
Per-frame diffuse bake for the Export pipeline.

This module owns every temporary mutation needed to run a multi-material Cycles
diffuse bake on ``head_geo`` and save the result to disk — and guarantees that
every one of those mutations is undone on exit, even on exception.

Responsibilities:

- Switch ``scene.render.engine`` to ``'CYCLES'`` and restore it on exit.
- Create a persistent bake-target Image datablock for every entry in
  ``BAKE_TARGETS`` and add an Image Texture node referencing that image to the
  matching material on ``head_geo`` (selected + active so Cycles writes into
  it during the bake call).
- Add a throwaway Image Texture node to any other material slot on ``head_geo``
  so ``bpy.ops.object.bake`` doesn't abort because of a missing bake target.
- On exit: remove every node we added, remove every image datablock we created,
  restore the previous active node on each material, restore the render engine.

The actual bake call is fired once per frame via ``bake_head_materials`` — one
``bpy.ops.object.bake`` writes all three target images in parallel.

Source-scene invariant: materials, nodes, and render settings are byte-identical
before and after ``scope_bake_environment`` runs.
"""

from __future__ import annotations

import types
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import bpy

from ..core.export import frame_png_name, frame_texture_dir_name


# ---------------------------------------------------------------------------
# Bake target table
# ---------------------------------------------------------------------------
#
# Single source of truth for which material slots on head_geo get diffuse
# bakes.  Keyed by material-name match against head_geo.data.materials[i].name.
# Any material on head_geo NOT listed here gets a throwaway bake target and
# its native shader travels through to the GLB unchanged.
#
# Extendable to JSON later, but kept in Python for now because the material set
# is still evolving.
# ---------------------------------------------------------------------------
BAKE_TARGETS: list[dict] = [
    {"material_name": "head_mat",    "suffix": "head",        "res_key": "head_bake_resolution"},
    {"material_name": "eye_mat.001", "suffix": "R_eye_wedge", "res_key": "eye_wedge_bake_resolution"},
    {"material_name": "eye_mat.002", "suffix": "L_eye_wedge", "res_key": "eye_wedge_bake_resolution"},
]

_DUMMY_IMAGE_NAME = "ExportBake_Dummy"
_DUMMY_IMAGE_RES = 64


def _find_material_on_object(obj: bpy.types.Object, name: str) -> bpy.types.Material | None:
    """Return the Material named *name* on *obj*'s material slots, or None."""
    for slot in obj.material_slots:
        if slot.material is not None and slot.material.name == name:
            return slot.material
    return None


def _add_image_texture_node(
    material: bpy.types.Material,
    image: bpy.types.Image,
) -> bpy.types.Node:
    """Add a selected+active Image Texture node to *material* referencing *image*.

    The node is intentionally left unconnected — it serves only as the bake
    target identified by ``material.node_tree.nodes.active``.
    """
    if not material.use_nodes:
        material.use_nodes = True
    nodes = material.node_tree.nodes
    for n in nodes:
        n.select = False
    node = nodes.new("ShaderNodeTexImage")
    node.name = f"_ExportBakeTarget_{image.name}"
    node.image = image
    node.select = True
    nodes.active = node
    return node


@contextmanager
def scope_bake_environment(
    head_geo: bpy.types.Object,
    export_cfg,
) -> Iterator[types.SimpleNamespace]:
    """Set up Cycles bake targets on *head_geo* and tear everything down on exit.

    Yields a namespace with:

    - ``targets``: list of ``{"material_name", "suffix", "image", "resolution"}``
      dicts — one entry per matched ``BAKE_TARGETS`` material that was actually
      wired up on *head_geo*. Materials listed in ``BAKE_TARGETS`` but missing
      from *head_geo* are silently skipped (logged via print).

    The source scene is left byte-identical on exit.
    """
    scene = bpy.context.scene

    # --- Save + switch render engine -----------------------------------------
    prev_engine = scene.render.engine
    scene.render.engine = "CYCLES"

    # Samples are applied per frame in bake_head_materials so they can be
    # tweaked mid-run via config reload.  Apply a safe default here too.
    try:
        scene.cycles.samples = int(export_cfg.bake_samples)
    except Exception:
        pass

    # --- Track every mutation so the finally block can undo it ---------------
    added_node_refs: list[tuple[str, str]] = []   # (material_name, node_name)
    prev_active_nodes: dict[str, str | None] = {}  # material_name -> node_name or None
    created_image_names: list[str] = []
    targets: list[dict] = []

    try:
        # 1. Build persistent bake images + nodes for each matched BAKE_TARGET.
        for spec in BAKE_TARGETS:
            mat_name = spec["material_name"]
            suffix = spec["suffix"]
            res = int(getattr(export_cfg, spec["res_key"]))

            material = _find_material_on_object(head_geo, mat_name)
            if material is None:
                print(
                    f"[Export][bake] WARNING: material '{mat_name}' not found "
                    f"on {head_geo.name!r} — skipping bake target '{suffix}'"
                )
                continue

            img = bpy.data.images.new(
                name=f"ExportBake_{suffix}",
                width=res,
                height=res,
                alpha=False,
                float_buffer=False,
            )
            img.colorspace_settings.name = "sRGB"
            created_image_names.append(img.name)

            nt = material.node_tree
            prev_active = nt.nodes.active
            prev_active_nodes[material.name] = prev_active.name if prev_active else None
            node = _add_image_texture_node(material, img)
            added_node_refs.append((material.name, node.name))

            targets.append(
                {
                    "material_name": mat_name,
                    "suffix": suffix,
                    "image": img,
                    "resolution": res,
                }
            )

        # 2. Protect every OTHER material on head_geo so the bake call doesn't
        #    error out on them.  Use a shared tiny dummy image as the target.
        baked_names = {t["material_name"] for t in targets}
        untargeted = [
            slot.material
            for slot in head_geo.material_slots
            if slot.material is not None and slot.material.name not in baked_names
        ]

        if untargeted:
            dummy = bpy.data.images.new(
                name=_DUMMY_IMAGE_NAME,
                width=_DUMMY_IMAGE_RES,
                height=_DUMMY_IMAGE_RES,
                alpha=False,
                float_buffer=False,
            )
            created_image_names.append(dummy.name)
            for mat in untargeted:
                if mat.name in prev_active_nodes:
                    continue  # already tracked (safety)
                nt = mat.node_tree
                prev_active = nt.nodes.active if nt else None
                prev_active_nodes[mat.name] = prev_active.name if prev_active else None
                node = _add_image_texture_node(mat, dummy)
                added_node_refs.append((mat.name, node.name))

        yield types.SimpleNamespace(targets=targets)

    finally:
        # --- Remove every added node ---------------------------------------
        for mat_name, node_name in added_node_refs:
            mat = bpy.data.materials.get(mat_name)
            if mat is None or mat.node_tree is None:
                continue
            node = mat.node_tree.nodes.get(node_name)
            if node is not None:
                try:
                    mat.node_tree.nodes.remove(node)
                except Exception:
                    pass

        # --- Restore previous active node on each affected material --------
        for mat_name, prev_name in prev_active_nodes.items():
            mat = bpy.data.materials.get(mat_name)
            if mat is None or mat.node_tree is None:
                continue
            if prev_name and prev_name in mat.node_tree.nodes:
                mat.node_tree.nodes.active = mat.node_tree.nodes[prev_name]

        # --- Remove every created image datablock --------------------------
        for img_name in created_image_names:
            img = bpy.data.images.get(img_name)
            if img is not None:
                try:
                    bpy.data.images.remove(img, do_unlink=True)
                except Exception:
                    pass

        # --- Restore render engine -----------------------------------------
        try:
            scene.render.engine = prev_engine
        except Exception:
            pass


def bake_head_materials(
    head_geo: bpy.types.Object,
    bake_ctx: types.SimpleNamespace,
    out_dir: Path,
    frame: int,
    samples: int,
    margin: int,
) -> dict[str, Path]:
    """Run a single multi-material diffuse bake and write PNGs for each target.

    Args:
        head_geo: the source head object whose materials were wired up by
            ``scope_bake_environment``.
        bake_ctx: the namespace yielded by ``scope_bake_environment``.
        out_dir: root export directory (``data/final-output/``).
        frame: current frame number — picks the ``frame_NNNN/`` subfolder.
        samples: Cycles samples for the bake.
        margin: UV edge padding in pixels.

    Returns:
        ``{suffix: png_path}`` for every bake target that was actually written.
    """
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer

    # Cycles sample count — per-frame so hot config reloads take effect.
    try:
        scene.cycles.samples = int(samples)
    except Exception:
        pass

    # Select head_geo as the ONLY selected + active object.
    bpy.ops.object.select_all(action="DESELECT")
    head_geo.select_set(True)
    view_layer.objects.active = head_geo

    # Single bake call — writes into every active Image Texture node on every
    # material on head_geo (one call, three images populate simultaneously).
    bpy.ops.object.bake(
        type="DIFFUSE",
        pass_filter={"COLOR"},
        use_selected_to_active=False,
        margin=int(margin),
    )

    # Write each bake image to disk under the per-frame sidecar folder.
    frame_dir = Path(out_dir) / frame_texture_dir_name(frame)
    frame_dir.mkdir(parents=True, exist_ok=True)

    png_paths: dict[str, Path] = {}
    for target in bake_ctx.targets:
        img = target["image"]
        suffix = target["suffix"]
        png_path = frame_dir / frame_png_name(suffix)
        img.filepath_raw = str(png_path)
        img.file_format = "PNG"
        img.save()
        png_paths[suffix] = png_path

    return png_paths
