"""
Scene operations for mesh editing.

Direct geometry edits: vertex deletion and vertex sewing.
All functions here touch the live Blender scene via bmesh.
"""

from __future__ import annotations

import bpy
import bmesh


def delete_vertex_group(mesh_obj: bpy.types.Object, group_name: str) -> None:
    """Delete all vertices belonging to *group_name* from *mesh_obj*.

    Args:
        mesh_obj:   A mesh Object whose data will be edited in-place.
        group_name: Name of the vertex group whose members are removed.
                    If the group doesn't exist the function returns silently.
    """
    vg = mesh_obj.vertex_groups.get(group_name)
    if vg is None:
        return

    vg_index = vg.index
    mesh = mesh_obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    deform_layer = bm.verts.layers.deform.verify()
    verts_to_delete = [v for v in bm.verts if vg_index in v[deform_layer]]

    bmesh.ops.delete(bm, geom=verts_to_delete, context="VERTS")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def sew_vertices(
    mesh_obj: bpy.types.Object,
    wedge_obj: bpy.types.Object,
    paired_indices: dict[str, int],
) -> None:
    """Merge paired vertices from *wedge_obj* onto matching vertices in *mesh_obj*.

    Each entry in *paired_indices* maps a string key (the vertex index inside
    *wedge_obj*) to the target vertex index inside *mesh_obj*.  The function
    joins *wedge_obj* into *mesh_obj* and then merges each wedge vertex to its
    counterpart by position snap, leaving a single contiguous mesh.

    Args:
        mesh_obj:       The base mesh Object (e.g. the head).
        wedge_obj:      The secondary mesh Object to be joined and sewn in
                        (e.g. an eye-wedge patch).
        paired_indices: ``{"<wedge_vert_idx>": <base_vert_idx>, ...}`` as read
                        from ``CleanupConfig.eye_wedge_R_indices`` /
                        ``eye_wedge_L_indices``.
    """
    # Collect world-space target positions from the base mesh before joining.
    base_mesh = mesh_obj.data
    base_matrix = mesh_obj.matrix_world
    target_positions: dict[int, tuple[float, float, float]] = {}
    for wedge_key, base_idx in paired_indices.items():
        v = base_mesh.vertices[base_idx]
        world_pos = base_matrix @ v.co
        target_positions[int(wedge_key)] = (world_pos.x, world_pos.y, world_pos.z)

    # Record how many verts the base mesh currently has so we can offset
    # wedge vertex indices after the join.
    base_vert_count = len(base_mesh.vertices)

    # Join the wedge into the base mesh object.
    wedge_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.join()

    # After join the wedge verts sit at (base_vert_count + wedge_idx).
    combined_mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(combined_mesh)
    bm.verts.ensure_lookup_table()

    merge_map: dict[bmesh.types.BMVert, bmesh.types.BMVert] = {}
    for wedge_idx, world_pos in target_positions.items():
        joined_idx = base_vert_count + wedge_idx
        wedge_vert = bm.verts[joined_idx]
        # Find the base vert that currently sits closest to world_pos.
        # Because the join preserves order, the original base vert is still at
        # its original index — look it up directly.
        base_vert_idx = paired_indices[str(wedge_idx)]
        base_vert = bm.verts[base_vert_idx]
        merge_map[wedge_vert] = base_vert

    # Move each wedge seam-vert onto its base counterpart then merge by distance.
    for wedge_vert, base_vert in merge_map.items():
        wedge_vert.co = base_vert.co.copy()

    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    bm.to_mesh(combined_mesh)
    bm.free()
    combined_mesh.update()
