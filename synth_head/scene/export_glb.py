"""
Per-frame GLB staging + export for the Export pipeline.

Responsibilities:

- ``staging_scene`` — freeze every enabled source object (head_geo + optional
  eyes / brows / lashes) into a temp ``ExportStaging`` collection using
  ``bpy.data.meshes.new_from_object``.  The resulting meshes have all
  modifiers applied and shape keys collapsed into basis (only the evaluated
  vertex positions remain — no armature, no shape keys).  Guarantees full
  cleanup on exit.
- ``rewrite_head_material_slots`` — replace each baked material slot on the
  frozen head_geo with a simple Principled BSDF material referencing the
  corresponding baked PNG.  ``material_index`` on every face is preserved, so
  the left/right eye wedge polys still point at their own slots.
- ``export_glb`` — thin wrapper around ``bpy.ops.export_scene.gltf`` that
  selects the staging objects and writes a self-contained GLB with embedded
  textures.

The source scene is left byte-identical before and after these helpers run.
"""

from __future__ import annotations

import types
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import bpy

from .export_bake import BAKE_TARGETS

_STAGING_COLLECTION_NAME = "ExportStaging"


# ---------------------------------------------------------------------------
# Freeze + staging
# ---------------------------------------------------------------------------

def _ensure_staging_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(_STAGING_COLLECTION_NAME)
    if col is None:
        col = bpy.data.collections.new(_STAGING_COLLECTION_NAME)
    if col.name not in scene.collection.children:
        try:
            scene.collection.children.link(col)
        except Exception:
            pass
    return col


def _freeze_object(
    src_obj: bpy.types.Object,
    label: str,
    depsgraph: bpy.types.Depsgraph,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    """Freeze *src_obj* into a static mesh + wrapper object, linked into *collection*.

    Uses ``bpy.data.meshes.new_from_object`` on the evaluated object — modifiers
    are applied and shape keys are collapsed into the basis positions.  The
    source object is not touched.

    The source's ``matrix_world`` is then baked into the frozen mesh's vertex
    coordinates so the staging object can sit at world identity.  This is the
    Python equivalent of Blender's "Apply All Transforms" and is necessary
    because the armature above these meshes carries a non-identity transform:
    without this bake the exported GLB would place every part at the armature's
    offset instead of at the pose we actually see in the viewport.  A negative
    determinant means the transform inverts winding order (mirror / negative
    scale), so we flip normals to keep shading correct in the GLB.
    """
    obj_eval = src_obj.evaluated_get(depsgraph)
    frozen_mesh = bpy.data.meshes.new_from_object(
        obj_eval,
        preserve_all_data_layers=True,
        depsgraph=depsgraph,
    )
    frozen_mesh.name = f"{label}_frozen"

    world_matrix = src_obj.matrix_world.copy()
    frozen_mesh.transform(world_matrix)
    if world_matrix.determinant() < 0.0:
        frozen_mesh.flip_normals()

    obj = bpy.data.objects.new(f"{label}_frozen", frozen_mesh)
    collection.objects.link(obj)
    return obj


@contextmanager
def staging_scene(
    refs: types.SimpleNamespace,
    export_cfg,
) -> Iterator[types.SimpleNamespace]:
    """Freeze all enabled source objects into a temp collection; clean up on exit.

    Args:
        refs: namespace exposing ``head_geo``, ``L_eye``, ``R_eye``,
            ``eyebrows``, ``eyelashes`` (any of the optional ones may be
            ``None``).
        export_cfg: ExportConfig — drives include flags.

    Yields a namespace with:

    - ``head_geo``: frozen head object (always present).
    - ``eyes``: list of frozen eye objects (0-2 entries).
    - ``brows``: list of frozen eyebrow objects (0-1 entries).
    - ``lashes``: list of frozen eyelash objects (0-1 entries).
    - ``objects``: flat list of every staged object, suitable for GLB export.
    """
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    collection = _ensure_staging_collection(scene)

    # Track created datablocks by NAME so cleanup survives dangling references.
    created_object_names: list[str] = []
    created_mesh_names: list[str] = []

    def _freeze(src_obj: bpy.types.Object | None, label: str) -> bpy.types.Object | None:
        if src_obj is None:
            return None
        obj = _freeze_object(src_obj, label, depsgraph, collection)
        created_object_names.append(obj.name)
        created_mesh_names.append(obj.data.name)
        return obj

    try:
        if refs.head_geo is None:
            raise RuntimeError("staging_scene: head_geo ref is None — cannot export")

        head_geo = _freeze(refs.head_geo, "head_geo")

        eyes: list[bpy.types.Object] = []
        if export_cfg.include_eyes:
            for src, lbl in ((refs.R_eye, "R_eye"), (refs.L_eye, "L_eye")):
                frozen = _freeze(src, lbl)
                if frozen is not None:
                    eyes.append(frozen)
                elif src is None:
                    print(f"[Export][stage] WARNING: include_eyes=True but {lbl} ref is unset — skipping")

        brows: list[bpy.types.Object] = []
        if export_cfg.include_brows:
            frozen = _freeze(refs.eyebrows, "eyebrows")
            if frozen is not None:
                brows.append(frozen)
            else:
                print("[Export][stage] WARNING: include_brows=True but eyebrows ref is unset — skipping")

        lashes: list[bpy.types.Object] = []
        if export_cfg.include_lashes:
            frozen = _freeze(refs.eyelashes, "eyelashes")
            if frozen is not None:
                lashes.append(frozen)
            else:
                print("[Export][stage] WARNING: include_lashes=True but eyelashes ref is unset — skipping")

        objects = [head_geo, *eyes, *brows, *lashes]

        yield types.SimpleNamespace(
            head_geo=head_geo,
            eyes=eyes,
            brows=brows,
            lashes=lashes,
            objects=objects,
            collection=collection,
        )

    finally:
        # Remove objects first; that drops the only user of each frozen mesh.
        for name in created_object_names:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass

        for name in created_mesh_names:
            mesh = bpy.data.meshes.get(name)
            if mesh is not None:
                try:
                    bpy.data.meshes.remove(mesh, do_unlink=True)
                except Exception:
                    pass

        # Remove the staging collection if we left it empty.
        col = bpy.data.collections.get(_STAGING_COLLECTION_NAME)
        if col is not None and len(col.objects) == 0 and len(col.children) == 0:
            try:
                bpy.data.collections.remove(col)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Export material builder + slot rewrite
# ---------------------------------------------------------------------------

def _build_export_material(suffix: str, png_path: Path) -> bpy.types.Material:
    """Build a throwaway Principled-BSDF material that references *png_path*.

    Name is ``Export_{suffix}``.  Any pre-existing material with that name is
    removed first, so back-to-back frames don't accumulate orphan datablocks.
    """
    mat_name = f"Export_{suffix}"
    existing = bpy.data.materials.get(mat_name)
    if existing is not None:
        try:
            bpy.data.materials.remove(existing, do_unlink=True)
        except Exception:
            pass

    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree

    for n in list(nt.nodes):
        nt.nodes.remove(n)

    out_node = nt.nodes.new("ShaderNodeOutputMaterial")
    out_node.location = (300, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-350, 0)
    img = bpy.data.images.load(str(png_path), check_existing=False)
    img.colorspace_settings.name = "sRGB"
    tex.image = img

    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    return mat


def rewrite_head_material_slots(
    frozen_head_geo: bpy.types.Object,
    png_paths: dict[str, Path],
) -> None:
    """Replace each baked material slot on *frozen_head_geo* with an Export material.

    For every entry in ``BAKE_TARGETS`` whose source material name matches a slot
    on *frozen_head_geo* (and whose PNG was successfully written), swap that slot
    for an ``Export_{suffix}`` Principled-BSDF material referencing the PNG.

    Slot indices and per-face ``material_index`` values are preserved — the
    left / right eye wedge polys continue pointing at the correct slot after
    the swap.
    """
    mesh = frozen_head_geo.data
    for spec in BAKE_TARGETS:
        src_name = spec["material_name"]
        suffix = spec["suffix"]
        png = png_paths.get(suffix)
        if png is None:
            continue

        for slot_idx, mat in enumerate(mesh.materials):
            if mat is not None and mat.name == src_name:
                export_mat = _build_export_material(suffix, png)
                mesh.materials[slot_idx] = export_mat
                break


# ---------------------------------------------------------------------------
# GLB export wrapper
# ---------------------------------------------------------------------------

def export_glb(
    objects: list[bpy.types.Object],
    filepath: Path,
    format: str = "GLB",
) -> None:
    """Write *objects* to *filepath* as a self-contained GLB with embedded textures.

    Thin wrapper around ``bpy.ops.export_scene.gltf`` with settings appropriate
    for the frozen static output:

    - ``use_selection=True`` — only the staged objects go into the file.
    - ``export_apply=False`` — modifiers were already applied via
      ``new_from_object``; re-applying would do nothing but is also unsafe for
      linked data.
    - ``export_skins=False``, ``export_animations=False`` — static handoff.
    - ``export_format='GLB'`` — textures embedded inside the glb binary.
    """
    if not objects:
        raise RuntimeError("export_glb: no objects to export")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format=format,
        use_selection=True,
        export_apply=False,
        export_skins=False,
        export_animations=False,
        export_materials="EXPORT",
    )
