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


def cut_and_sew(
    cut_group_name: str,
    mesh_obj: bpy.types.Object,
    sew_pairs,
) -> None:
    """Delete a vertex group and sew paired vertex indices in one bmesh session.

    Generalized version of the lip-cut-and-sew step that works well on any
    mesh with a vertex group to remove and paired boundary verts to weld.

    Operations (all in one bmesh session on *mesh_obj*):
      1. Stash shape key animation action so the bmesh round-trip can't orphan it.
      2. Resolve BMVert references for every sew pair and every cut vert.
      3. Drop any sew pair whose verts overlap the cut set.
      4. Delete the cut verts.
      5. Snap each surviving sew pair together and weld via remove_doubles.
      6. Write the mesh back and restore the animation action if needed.

    Args:
        cut_group_name: Vertex group name on *mesh_obj* whose members will be
                        deleted.  Pass an empty string to skip the cut.
        mesh_obj:       The mesh Object to edit in place.
        sew_pairs:      Index pairs to merge after the cut.  Accepts either
                        a ``{"<idx_a>": idx_b, ...}`` dict (as read from
                        cleanup.json) or an iterable of ``(idx_a, idx_b)``
                        tuples.  Both indices reference the ORIGINAL mesh
                        (pre-cut), since all refs are resolved before the
                        cut runs.
    """
    mesh = mesh_obj.data

    # --- 1. Stash animation action -------------------------------------------
    stashed_action: Optional[bpy.types.Action] = None
    sk = mesh.shape_keys
    if sk and sk.animation_data and sk.animation_data.action:
        stashed_action = sk.animation_data.action

    # --- Normalize sew_pairs to list of (int, int) ---------------------------
    pair_list: list[tuple[int, int]] = []
    if isinstance(sew_pairs, dict):
        for k, v in sew_pairs.items():
            pair_list.append((int(k), int(v)))
    else:
        for a, b in sew_pairs:
            pair_list.append((int(a), int(b)))

    # --- 2. Open bmesh and resolve refs up front -----------------------------
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    initial_vert_count = len(bm.verts)

    bm_pairs: list[tuple[bmesh.types.BMVert, bmesh.types.BMVert]] = []
    for idx_a, idx_b in pair_list:
        if idx_a >= initial_vert_count or idx_b >= initial_vert_count:
            print(f"[SynthHead][cut_and_sew] WARNING: skipping pair "
                  f"{idx_a}->{idx_b} (out of range for {initial_vert_count} verts)")
            continue
        bm_pairs.append((bm.verts[idx_a], bm.verts[idx_b]))

    cut_verts: list[bmesh.types.BMVert] = []
    if cut_group_name:
        vg = mesh_obj.vertex_groups.get(cut_group_name)
        if vg is None:
            print(f"[SynthHead][cut_and_sew] WARNING: vertex group "
                  f"'{cut_group_name}' not found on '{mesh_obj.name}'")
        else:
            vg_index = vg.index
            deform_layer = bm.verts.layers.deform.verify()
            cut_verts = [v for v in bm.verts if vg_index in v[deform_layer]]

    # --- 3. Drop sew pairs that overlap the cut ------------------------------
    cut_set = set(cut_verts)
    surviving_pairs = [
        (a, b) for a, b in bm_pairs
        if a not in cut_set and b not in cut_set
    ]
    lost_pairs = len(bm_pairs) - len(surviving_pairs)

    print(f"[SynthHead][cut_and_sew] mesh='{mesh_obj.name}' "
          f"start={initial_vert_count}v, "
          f"cut_group='{cut_group_name}' ({len(cut_verts)} verts), "
          f"sew_pairs={len(surviving_pairs)}"
          + (f" (dropped {lost_pairs} overlapping cut)" if lost_pairs else ""))

    # --- 4. Delete cut verts --------------------------------------------------
    if cut_verts:
        bmesh.ops.delete(bm, geom=cut_verts, context="VERTS")
        bm.verts.ensure_lookup_table()

    # --- 5. Sew surviving pairs ----------------------------------------------
    if surviving_pairs:
        touched: list[bmesh.types.BMVert] = []
        for mover, target in surviving_pairs:
            mover.co = target.co.copy()
            touched.extend((mover, target))
        bmesh.ops.remove_doubles(bm, verts=touched, dist=1e-5)
        bm.verts.ensure_lookup_table()

    # --- 6. Write back + restore animation ------------------------------------
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    if stashed_action is not None:
        sk_after = mesh.shape_keys
        if sk_after is not None:
            if sk_after.animation_data is None:
                sk_after.animation_data_create()
            if sk_after.animation_data.action is None:
                sk_after.animation_data.action = stashed_action

    print(f"[SynthHead][cut_and_sew] '{mesh_obj.name}' final: "
          f"{len(mesh.vertices)} verts, {len(mesh.polygons)} faces")


def clean_head_mesh(
    head_obj: bpy.types.Object,
    wedge_R_obj: bpy.types.Object,
    wedge_L_obj: bpy.types.Object,
    body_obj: bpy.types.Object,
    cfg,
) -> None:
    """Clean the head mesh: cut the mouth bag and sew the lips.

    Stripped-down replacement for ``clean_head_mesh_old``.  Only the
    lip-cut-and-sew step runs; eye wedges and body geo are left untouched
    and must be combined by some other mechanism (see ``clean_head_mesh_old``
    for the full bmesh-based merge if you need it).

    Args:
        head_obj:    The head mesh Object (edited in place).
        wedge_R_obj: Unused (kept for signature compatibility).
        wedge_L_obj: Unused (kept for signature compatibility).
        body_obj:    Unused (kept for signature compatibility).
        cfg:         CleanupConfig providing ``mouth_bag_group`` and
                     ``mouth_sew_indices``.
    """
    cut_and_sew(cfg.mouth_bag_group, head_obj, cfg.mouth_sew_indices)
    join_and_merge([wedge_R_obj, wedge_L_obj, body_obj], head_obj)

    #3. Simple combine operation to combine the eye wedges and body into the head

def clean_head_mesh_old(
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


def join_and_merge(mesh_objects: list, target_object: bpy.types.Object, merge_distance: float = 0.01):
    """
    Joins a list of mesh objects into a target object, then merges vertices by distance.
    
    Args:
        mesh_objects: List of mesh objects to join into the target
        target_object: The object to join everything into
        merge_distance: Distance threshold for merging vertices (default 0.0001)
    """
    
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')
    
    # Select all mesh objects to join
    for obj in mesh_objects:
        obj.select_set(True)
    
    # Select and set target as active
    target_object.select_set(True)
    bpy.context.view_layer.objects.active = target_object
    
    # Join all into target
    bpy.ops.object.join()
    
    # Go into edit mode and merge by distance
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=merge_distance)
    bpy.ops.object.mode_set(mode='OBJECT')