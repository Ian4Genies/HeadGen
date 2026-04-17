"""
Scene operations for mesh editing.

Single-session mesh surgery: lip sewing, mouth-bag deletion,
eye-wedge + body ingestion with shape key transfer, and border welding.
All operations share one bmesh so BMVert references stay stable across
mutations and the mesh is written back exactly once.
"""

from __future__ import annotations

from typing import Optional

import bpy
import bmesh

from ..core.config import CleanupConfig


# ---------------------------------------------------------------------------
# Private helpers — all operate on a caller-owned open bmesh
# ---------------------------------------------------------------------------

def _ingest_mesh(
    bm: bmesh.types.BMesh,
    source_obj: bpy.types.Object,
) -> list[bmesh.types.BMVert]:
    """Copy geometry and shape key deltas from *source_obj* into *bm*.

    For every shape key on *source_obj* a matching shape layer is found or
    created on *bm* by name.  New verts receive the correct delta for each
    layer.  Existing head verts are unaffected.

    Returns the list of newly created BMVerts in source-index order.
    """
    src_mesh = source_obj.data
    src_matrix = source_obj.matrix_world

    # Build shape layer map: layer_name -> bm shape layer
    src_key = src_mesh.shape_keys
    shape_layers: dict[str, bmesh.types.BMLayerItem] = {}
    if src_key:
        for kb in src_key.key_blocks:
            existing = bm.verts.layers.shape.get(kb.name)
            if existing is None:
                existing = bm.verts.layers.shape.new(kb.name)
            shape_layers[kb.name] = existing

    # Create verts in world space (source_obj may be offset relative to head)
    new_verts: list[bmesh.types.BMVert] = []
    for sv in src_mesh.vertices:
        world_co = src_matrix @ sv.co
        nv = bm.verts.new(world_co)
        new_verts.append(nv)

    # Write shape key deltas onto the new verts
    if src_key:
        for kb in src_key.key_blocks:
            layer = shape_layers[kb.name]
            for i, nv in enumerate(new_verts):
                nv[layer] = src_matrix @ kb.data[i].co - src_matrix @ src_mesh.vertices[i].co

    # Rebuild faces using the new vert list
    for poly in src_mesh.polygons:
        face_verts = [new_verts[vi] for vi in poly.vertices]
        try:
            bm.faces.new(face_verts)
        except ValueError:
            # Face already exists (shouldn't happen, but skip gracefully)
            pass

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return new_verts


def _merge_pairs(
    bm: bmesh.types.BMesh,
    pairs: list[tuple[bmesh.types.BMVert, bmesh.types.BMVert]],
) -> None:
    """Snap the first vert of each pair onto the second, then weld them.

    Args:
        bm:    The open bmesh to operate on.
        pairs: List of (mover, target) BMVert tuples.  The mover is snapped
               to the target's position then both are merged via
               remove_doubles.
    """
    touched: list[bmesh.types.BMVert] = []
    for mover, target in pairs:
        mover.co = target.co.copy()
        touched.extend((mover, target))

    bmesh.ops.remove_doubles(bm, verts=touched, dist=1e-5)


def _collect_vertex_group(
    bm: bmesh.types.BMesh,
    mesh_obj: bpy.types.Object,
    group_name: str,
) -> list[bmesh.types.BMVert]:
    """Return the BMVerts that belong to *group_name* on *mesh_obj*.

    The bmesh must have been opened from *mesh_obj*.  Returns an empty list
    if the vertex group doesn't exist.
    """
    vg = mesh_obj.vertex_groups.get(group_name)
    if vg is None:
        return []

    vg_index = vg.index
    deform_layer = bm.verts.layers.deform.verify()
    bm.verts.ensure_lookup_table()
    return [v for v in bm.verts if vg_index in v[deform_layer]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_head_mesh(
    head_obj: bpy.types.Object,
    wedge_R_obj: bpy.types.Object,
    wedge_L_obj: bpy.types.Object,
    body_obj: bpy.types.Object,
    cfg: CleanupConfig,
) -> None:
    """Perform all mesh surgery on *head_obj* in a single bmesh session.

    Operations in order:
      1. Stash shape key animation action so bm.to_mesh() can't orphan it.
      2. Sew mouth: snap config-paired lip border verts together.
      3. Delete mouth bag: remove the vertex group named cfg.mouth_bag_group.
      4. Ingest eye wedge R, eye wedge L, and body geo (with shape key transfer).
      5. remove_doubles over all verts to weld overlapping seam borders.
      6. Write back to mesh once; restore animation action if needed.
      7. Delete the now-merged wedge and body objects from the scene.

    Args:
        head_obj:   The base head mesh Object (modified in-place).
        wedge_R_obj: Right eye wedge Object (deleted after merge).
        wedge_L_obj: Left eye wedge Object (deleted after merge).
        body_obj:   Body geo Object (deleted after merge).
        cfg:        CleanupConfig with mouth_bag_group, mouth_sew_indices,
                    and object names.
    """
    head_mesh = head_obj.data

    # --- 1. Stash animation action -------------------------------------------
    stashed_action: Optional[bpy.types.Action] = None
    sk = head_mesh.shape_keys
    if sk and sk.animation_data and sk.animation_data.action:
        stashed_action = sk.animation_data.action

    # --- 2 & 3. Open bmesh, sew lips, delete mouth bag -----------------------
    bm = bmesh.new()
    bm.from_mesh(head_mesh)
    bm.verts.ensure_lookup_table()

    # Resolve mouth sew pairs — both indices reference the original head mesh
    mouth_pairs: list[tuple[bmesh.types.BMVert, bmesh.types.BMVert]] = []
    for str_a, idx_b in cfg.mouth_sew_indices.items():
        va = bm.verts[int(str_a)]
        vb = bm.verts[idx_b]
        mouth_pairs.append((va, vb))

    if mouth_pairs:
        _merge_pairs(bm, mouth_pairs)
        bm.verts.ensure_lookup_table()

    # Delete mouth bag vertex group
    bag_verts = _collect_vertex_group(bm, head_obj, cfg.mouth_bag_group)
    if bag_verts:
        bmesh.ops.delete(bm, geom=bag_verts, context="VERTS")
        bm.verts.ensure_lookup_table()

    # --- 4. Ingest secondary meshes ------------------------------------------
    _ingest_mesh(bm, wedge_R_obj)
    _ingest_mesh(bm, wedge_L_obj)
    _ingest_mesh(bm, body_obj)

    # --- 5. Weld all overlapping seam borders --------------------------------
    bm.verts.ensure_lookup_table()
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)

    # --- 6. Write back -------------------------------------------------------
    bm.to_mesh(head_mesh)
    bm.free()
    head_mesh.update()

    # Restore animation action if bm.to_mesh() rebuilt the Key data-block
    if stashed_action is not None:
        sk_after = head_mesh.shape_keys
        if sk_after is not None:
            if sk_after.animation_data is None:
                sk_after.animation_data_create()
            if sk_after.animation_data.action is None:
                sk_after.animation_data.action = stashed_action

    # --- 7. Remove source objects from scene ---------------------------------
    for obj in (wedge_R_obj, wedge_L_obj, body_obj):
        bpy.data.objects.remove(obj, do_unlink=True)
