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
from mathutils import Matrix, Vector


# ---------------------------------------------------------------------------
# Private helpers — all operate on a caller-owned open bmesh
# ---------------------------------------------------------------------------

def _ingest_mesh(
    bm: bmesh.types.BMesh,
    source_obj: bpy.types.Object,
    dest_matrix_inv: Matrix,
) -> list[bmesh.types.BMVert]:
    """Copy geometry and shape key data from *source_obj* into *bm*.

    Vertex coordinates are transformed from the source object's local space
    into the destination's local space via ``dest_matrix_inv @ src_matrix``.

    Only shape keys that **already exist** on *bm* (by name) receive data.
    Shape keys unique to the source are ignored (would otherwise zero out
    existing verts in that new layer).

    Bmesh shape layers store **absolute shaped positions** (not deltas).

    Returns the list of newly created BMVerts in source-index order.
    """
    src_mesh = source_obj.data
    src_matrix = source_obj.matrix_world
    transform = dest_matrix_inv @ src_matrix

    vcount_before = len(bm.verts)
    fcount_before = len(bm.faces)

    src_key = src_mesh.shape_keys
    shared_layers: list[tuple[bpy.types.ShapeKey, bmesh.types.BMLayerItem]] = []
    if src_key:
        for kb in src_key.key_blocks:
            existing = bm.verts.layers.shape.get(kb.name)
            if existing is not None:
                shared_layers.append((kb, existing))

    new_verts: list[bmesh.types.BMVert] = []
    for sv in src_mesh.vertices:
        co = transform @ sv.co
        nv = bm.verts.new(co)
        new_verts.append(nv)

    for kb, layer in shared_layers:
        for i, nv in enumerate(new_verts):
            nv[layer] = transform @ kb.data[i].co

    for poly in src_mesh.polygons:
        face_verts = [new_verts[vi] for vi in poly.vertices]
        try:
            bm.faces.new(face_verts)
        except ValueError:
            pass

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    print(
        f"[SynthHead][clean_mesh] Ingested '{source_obj.name}': "
        f"+{len(bm.verts) - vcount_before} verts, "
        f"+{len(bm.faces) - fcount_before} faces, "
        f"{len(shared_layers)} shared shape keys"
    )
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
               remove_doubles (which keeps the lower-indexed vert).
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
    cfg,
) -> None:
    """Perform all mesh surgery on *head_obj* in a single bmesh session.

    Operations in order:
      1. Stash shape key animation action so bm.to_mesh() can't orphan it.
      2. Open bmesh and resolve all BMVert references up front.
      3. Delete mouth bag verts (creates open lip boundary).
      4. Sew lips using pre-resolved BMVert refs (filtered to surviving verts).
      5. Ingest eye wedge R, eye wedge L, and body geo with shape key transfer.
      6. remove_doubles over all verts to weld overlapping seam borders.
      7. Write back to mesh once; restore animation action if needed.
      8. Delete the now-merged wedge and body objects from the scene.

    Args:
        head_obj:   The base head mesh Object (modified in-place).
        wedge_R_obj: Right eye wedge Object (deleted after merge).
        wedge_L_obj: Left eye wedge Object (deleted after merge).
        body_obj:   Body geo Object (deleted after merge).
        cfg:        CleanupConfig with mouth_bag_group, mouth_sew_indices.
    """
    head_mesh = head_obj.data
    head_matrix_inv = head_obj.matrix_world.inverted()

    # --- 1. Stash animation action -------------------------------------------
    stashed_action: Optional[bpy.types.Action] = None
    sk = head_mesh.shape_keys
    if sk and sk.animation_data and sk.animation_data.action:
        stashed_action = sk.animation_data.action

    # --- 2. Open bmesh and resolve refs up front -----------------------------
    bm = bmesh.new()
    bm.from_mesh(head_mesh)
    bm.verts.ensure_lookup_table()

    initial_vert_count = len(bm.verts)
    print(f"[SynthHead][clean_mesh] Head loaded: {initial_vert_count} verts, "
          f"{len(bm.faces)} faces, "
          f"{len(sk.key_blocks) if sk else 0} shape keys")

    # Resolve mouth sew pairs as BMVert refs (indices reference the original head mesh)
    mouth_pairs: list[tuple[bmesh.types.BMVert, bmesh.types.BMVert]] = []
    for str_a, idx_b in cfg.mouth_sew_indices.items():
        idx_a = int(str_a)
        if idx_a >= initial_vert_count or idx_b >= initial_vert_count:
            print(f"[SynthHead][clean_mesh] WARNING: skipping sew pair {idx_a}->{idx_b} "
                  f"(out of range for {initial_vert_count} verts)")
            continue
        va = bm.verts[idx_a]
        vb = bm.verts[idx_b]
        mouth_pairs.append((va, vb))

    # Resolve mouth bag verts
    bag_verts = _collect_vertex_group(bm, head_obj, cfg.mouth_bag_group)
    bag_vert_set = set(bag_verts)
    print(f"[SynthHead][clean_mesh] Mouth bag '{cfg.mouth_bag_group}': "
          f"{len(bag_verts)} verts")

    # Filter out sew pairs whose verts are in the bag (they'd be deleted)
    surviving_pairs = [
        (a, b) for a, b in mouth_pairs
        if a not in bag_vert_set and b not in bag_vert_set
    ]
    lost_pairs = len(mouth_pairs) - len(surviving_pairs)
    if lost_pairs:
        print(f"[SynthHead][clean_mesh] WARNING: {lost_pairs} sew pair(s) "
              f"reference bag verts and will be skipped")

    # --- 3. Delete mouth bag -------------------------------------------------
    if bag_verts:
        bmesh.ops.delete(bm, geom=bag_verts, context="VERTS")
        bm.verts.ensure_lookup_table()
        print(f"[SynthHead][clean_mesh] After bag delete: {len(bm.verts)} verts")

    # --- 4. Sew lips ---------------------------------------------------------
    if surviving_pairs:
        _merge_pairs(bm, surviving_pairs)
        bm.verts.ensure_lookup_table()
        print(f"[SynthHead][clean_mesh] Sewed {len(surviving_pairs)} lip pair(s); "
              f"after sew: {len(bm.verts)} verts")

    # --- 5. Ingest secondary meshes ------------------------------------------
    _ingest_mesh(bm, wedge_R_obj, head_matrix_inv)
    _ingest_mesh(bm, wedge_L_obj, head_matrix_inv)
    _ingest_mesh(bm, body_obj, head_matrix_inv)

    # --- 6. Weld all overlapping seam borders --------------------------------
    bm.verts.ensure_lookup_table()
    pre_weld = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    print(f"[SynthHead][clean_mesh] Global remove_doubles: "
          f"{pre_weld} -> {len(bm.verts)} verts (welded {pre_weld - len(bm.verts)})")

    # --- 7. Write back -------------------------------------------------------
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
                print("[SynthHead][clean_mesh] Restored shape key animation action")

    print(f"[SynthHead][clean_mesh] Final head mesh: "
          f"{len(head_mesh.vertices)} verts, {len(head_mesh.polygons)} faces, "
          f"{len(head_mesh.shape_keys.key_blocks) if head_mesh.shape_keys else 0} shape keys")

    # --- 8. Remove source objects from scene ---------------------------------
    for obj in (wedge_R_obj, wedge_L_obj, body_obj):
        bpy.data.objects.remove(obj, do_unlink=True)
