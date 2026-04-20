"""
UV-Barycentric Shape Transfer (proof of concept)
================================================

Paste into Blender's Script Editor and run.

Produces a NEW object whose topology (vertex / edge / face order, UVs,
vertex groups, etc.) is identical to `CORRECT_OBJ_NAME`, but whose vertex
POSITIONS are sampled from the shape of `WRONG_OBJ_NAME` via UV
correspondence using barycentric transfer inside wrong-mesh UV triangles.

Robust against:
  - Different vertex ORDER between the two meshes
  - Extra / missing vertices on the wrong side
  - Different triangulation (wrong may be triangulated, correct may not)
  - Small UV differences near seams (nearest-triangle projection)

The CORRECT object is the TOPOLOGY source.
The WRONG   object is the SHAPE    source.
We always iterate CORRECT verts and sample from WRONG. Never the reverse.
"""

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


# ── User config ───────────────────────────────────────────────────────────────

CORRECT_OBJ_NAME = "MeshA_Correct"   # TOPOLOGY source (correct vertex order)
WRONG_OBJ_NAME   = "MeshB_Wrong"     # SHAPE source    (wrong vertex order)
NEW_OBJ_NAME     = None              # None => "<CORRECT_OBJ_NAME>_FromWrong"
UV_LAYER_NAME    = None              # None => active UV layer on each mesh
USE_DEPSGRAPH    = True              # bake modifiers + shape keys on wrong side
USE_WORLD_SPACE  = True              # respect object transforms
WARN_UV_GAP      = 1e-3              # log if a UV is farther than this from
                                     # any wrong-mesh UV triangle


# ── Evaluated-mesh helper ─────────────────────────────────────────────────────

class _EvaluatedMesh:
    """
    Context-manager that yields a temporary bpy.types.Mesh reflecting the
    object's fully evaluated shape (modifiers + shape keys), and cleans it
    up when done.

    If use_depsgraph is False, yields obj.data directly and does nothing on
    exit (the mesh is owned by the bpy data block, so don't free it).
    """
    def __init__(self, obj, use_depsgraph=True):
        self.obj = obj
        self.use_depsgraph = use_depsgraph
        self._obj_eval = None
        self._mesh = None

    def __enter__(self):
        if self.use_depsgraph:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            self._obj_eval = self.obj.evaluated_get(depsgraph)
            self._mesh = self._obj_eval.to_mesh()
        else:
            self._mesh = self.obj.data
        return self._mesh

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.use_depsgraph and self._obj_eval is not None:
            self._obj_eval.to_mesh_clear()
        return False


# ── Correct-side: per-vertex UV collection ────────────────────────────────────

def build_correct_vert_uvs(correct_mesh, uv_layer_name=None):
    """
    For each vertex of the CORRECT mesh, collect the unique list of UV coords
    (as (u, v) tuples) assigned to it via face loops. UV seam vertices end up
    with multiple entries, which we later average across.

    Returns: list[list[tuple[float, float]]] indexed by vertex.
    """
    bm = bmesh.new()
    bm.from_mesh(correct_mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    if uv_layer_name:
        uv_layer = bm.loops.layers.uv.get(uv_layer_name)
    else:
        uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        raise RuntimeError(
            f"CORRECT mesh '{correct_mesh.name}' has no UV layer"
            + (f" named '{uv_layer_name}'" if uv_layer_name else "")
        )

    vert_uvs = [[] for _ in range(len(bm.verts))]
    for face in bm.faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            vi = loop.vert.index
            entry = (uv.x, uv.y)
            if entry not in vert_uvs[vi]:
                vert_uvs[vi].append(entry)

    bm.free()
    return vert_uvs


# ── Wrong-side: triangulated UV → 3D BVH ──────────────────────────────────────

def build_wrong_uv_bvh(wrong_obj, use_depsgraph, use_world_space,
                       uv_layer_name=None):
    """
    Build a BVHTree of the WRONG mesh's UV-space triangles (flattened onto
    Z=0), plus two parallel arrays mapping triangle index to:
        tris_uv[i] = (uvA, uvB, uvC) as Vector((u, v, 0.0))
        tris_p3[i] = (p3A, p3B, p3C) world-space (or local) 3D positions

    find_nearest((u, v, 0.0)) on the returned tree gives us:
      - the projected point `co` (inside the triangle if the UV is inside,
        on the nearest edge if it's outside),
      - the triangle's index, which we use to fetch tris_uv[i] and tris_p3[i]
        and hand off to mathutils.geometry.barycentric_transform.
    """
    with _EvaluatedMesh(wrong_obj, use_depsgraph=use_depsgraph) as wrong_eval_mesh:
        bm = bmesh.new()
        bm.from_mesh(wrong_eval_mesh)

        if uv_layer_name:
            uv_layer = bm.loops.layers.uv.get(uv_layer_name)
        else:
            uv_layer = bm.loops.layers.uv.active
        if uv_layer is None:
            bm.free()
            raise RuntimeError(
                f"WRONG mesh '{wrong_obj.name}' has no UV layer"
                + (f" named '{uv_layer_name}'" if uv_layer_name else "")
            )

        # No-op if already triangulated; otherwise splits quads/ngons.
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.faces.ensure_lookup_table()

        mw = wrong_obj.matrix_world if use_world_space else None

        tris_uv = []
        tris_p3 = []
        flat_verts = []
        flat_polys = []

        for face in bm.faces:
            loops = face.loops[:]
            if len(loops) != 3:
                # Defensive: should not happen post-triangulation
                continue

            uvA = Vector((loops[0][uv_layer].uv.x, loops[0][uv_layer].uv.y, 0.0))
            uvB = Vector((loops[1][uv_layer].uv.x, loops[1][uv_layer].uv.y, 0.0))
            uvC = Vector((loops[2][uv_layer].uv.x, loops[2][uv_layer].uv.y, 0.0))

            if use_world_space:
                p3A = mw @ loops[0].vert.co.copy()
                p3B = mw @ loops[1].vert.co.copy()
                p3C = mw @ loops[2].vert.co.copy()
            else:
                p3A = loops[0].vert.co.copy()
                p3B = loops[1].vert.co.copy()
                p3C = loops[2].vert.co.copy()

            tris_uv.append((uvA, uvB, uvC))
            tris_p3.append((p3A, p3B, p3C))

            base = len(flat_verts)
            flat_verts.extend([uvA, uvB, uvC])
            flat_polys.append([base, base + 1, base + 2])

        bm.free()

    if not tris_uv:
        raise RuntimeError(
            f"WRONG mesh '{wrong_obj.name}' produced zero triangles after "
            f"triangulation — cannot sample."
        )

    bvh = BVHTree.FromPolygons(flat_verts, flat_polys)
    return bvh, tris_uv, tris_p3


# ── Sample one correct-mesh vertex from the wrong-mesh UV BVH ─────────────────

def sample_shape(bvh, tris_uv, tris_p3, uvs):
    """
    Given one correct-mesh vertex's list of UV coordinates (one per UV loop
    it owns — usually 1, more than 1 at UV seams), return the averaged 3D
    position sampled from the WRONG mesh via barycentric transfer, plus the
    max UV-space gap distance observed across the samples (for diagnostics).
    """
    sampled_positions = []
    max_gap = 0.0

    for u, v in uvs:
        query = Vector((u, v, 0.0))
        co, _normal, tri_idx, dist = bvh.find_nearest(query)
        if tri_idx is None:
            # Shouldn't happen for a non-empty BVH, but guard anyway.
            continue

        uvA, uvB, uvC = tris_uv[tri_idx]
        p3A, p3B, p3C = tris_p3[tri_idx]

        # Map the (projected) UV-space point onto the source-triangle's 3D
        # positions using barycentric coordinates. This is the core of the
        # transfer.
        sampled = barycentric_transform(co, uvA, uvB, uvC, p3A, p3B, p3C)
        sampled_positions.append(sampled)

        if dist is not None and dist > max_gap:
            max_gap = dist

    if not sampled_positions:
        return None, max_gap

    if len(sampled_positions) == 1:
        return sampled_positions[0], max_gap

    avg = Vector((0.0, 0.0, 0.0))
    for p in sampled_positions:
        avg += p
    avg /= len(sampled_positions)
    return avg, max_gap


# ── Role-safety: banner + bbox helpers ────────────────────────────────────────

def _world_bbox_dims(obj):
    mw = obj.matrix_world
    corners = [mw @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def _bbox_from_positions(positions):
    if not positions:
        return (0.0, 0.0, 0.0)
    xs = [p.x for p in positions]
    ys = [p.y for p in positions]
    zs = [p.z for p in positions]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def _describe_obj(obj, role):
    dims = _world_bbox_dims(obj)
    n_shape_keys = (
        len(obj.data.shape_keys.key_blocks) - 1
        if obj.data.shape_keys else 0
    )
    n_modifiers = len(obj.modifiers)
    return (
        f" {role:<18}: '{obj.name}'\n"
        f"   verts={len(obj.data.vertices)}  "
        f"bbox=({dims[0]:.3f}, {dims[1]:.3f}, {dims[2]:.3f})  "
        f"shape_keys={n_shape_keys}  modifiers={n_modifiers}"
    )


def _print_role_banner(correct_obj, wrong_obj, new_obj_name):
    print("================= UV Shape Transfer =================")
    print(_describe_obj(correct_obj, "CORRECT (topology)"))
    print(_describe_obj(wrong_obj,   "WRONG   (shape)"))
    print(f" {'OUTPUT':<18}: '{new_obj_name}'")
    print("======================================================")


# ── Builder ───────────────────────────────────────────────────────────────────

def build_reordered_mesh(
    correct_obj,
    wrong_obj,
    new_obj_name=None,
    uv_layer_name=None,
    use_depsgraph=True,
    use_world_space=True,
    warn_uv_gap=1e-3,
):
    """
    INVARIANT
    ---------
    correct_obj = TOPOLOGY source (we iterate its verts, we write into a copy
                  of its mesh, and its matrix_world becomes the output's).
    wrong_obj   = SHAPE    source (we build a UV-space BVH from it and sample
                  3D positions out via barycentric transfer).
    The loop is ALWAYS `for correct_vert: sample from wrong`.
    Never the reverse.
    """
    if new_obj_name is None:
        new_obj_name = correct_obj.name + "_FromWrong"

    _print_role_banner(correct_obj, wrong_obj, new_obj_name)

    # Topology & UVs come from the basis of correct_obj so the output stays a
    # clean copy of the correct resting topology.
    correct_basis_mesh = correct_obj.data
    correct_vert_uvs = build_correct_vert_uvs(correct_basis_mesh, uv_layer_name)

    # Build the UV-space BVH of the WRONG mesh (evaluated, so shape keys /
    # modifiers are baked in).
    bvh, tris_uv, tris_p3 = build_wrong_uv_bvh(
        wrong_obj,
        use_depsgraph=use_depsgraph,
        use_world_space=use_world_space,
        uv_layer_name=uv_layer_name,
    )

    # Starting positions: current correct positions (in whichever space we're
    # sampling into). Verts with no UV loops fall back to these.
    if use_world_space:
        mw_correct = correct_obj.matrix_world
        correct_ref_positions = [mw_correct @ v.co.copy()
                                 for v in correct_basis_mesh.vertices]
    else:
        correct_ref_positions = [v.co.copy()
                                 for v in correct_basis_mesh.vertices]
    new_positions = [p.copy() for p in correct_ref_positions]

    # Per-vert sampling loop.
    sampled_count = 0
    gap_warn_count = 0
    max_gap_overall = 0.0
    gap_sum = 0.0
    gap_samples = 0
    unmatched_verts = []

    for ci, uvs in enumerate(correct_vert_uvs):
        if not uvs:
            unmatched_verts.append(ci)
            continue

        sampled, max_gap = sample_shape(bvh, tris_uv, tris_p3, uvs)
        if sampled is None:
            unmatched_verts.append(ci)
            continue

        new_positions[ci] = sampled
        sampled_count += 1

        gap_sum += max_gap
        gap_samples += 1
        if max_gap > max_gap_overall:
            max_gap_overall = max_gap
        if max_gap > warn_uv_gap:
            gap_warn_count += 1

    # ── Build the new object from a copy of correct_obj's mesh ───────────────
    new_mesh = correct_basis_mesh.copy()
    new_mesh.name = new_obj_name + "_mesh"

    new_obj = bpy.data.objects.new(new_obj_name, new_mesh)
    bpy.context.collection.objects.link(new_obj)

    # Same transform as correct_obj → output overlays it 1:1 in the viewport.
    new_obj.matrix_world = correct_obj.matrix_world.copy()

    # Strip shape keys from the output. Rationale:
    # Blender shape keys store ABSOLUTE per-vertex positions, not deltas. If we
    # leave them on the output, every non-basis key still holds the original
    # CORRECT positions, and any non-zero slider pulls the displayed shape
    # back toward correct's silhouette via:
    #   displayed = basis + Σ slider_i * (shape_key_i - basis)
    # That produces the classic "output visually looks like correct" failure
    # even though the basis (what we just wrote) is the WRONG shape.
    # The proof-of-concept output is plain geometry; shape-key wiring belongs
    # in the downstream runner layer.
    stripped_keys = 0
    if new_mesh.shape_keys is not None:
        stripped_keys = len(new_mesh.shape_keys.key_blocks)
        new_obj.shape_key_clear()

    # Convert sampled positions (world or local depending on flag) back to
    # the new mesh's local space.
    if use_world_space:
        inv = correct_obj.matrix_world.inverted()
        for i, pos in enumerate(new_positions):
            new_mesh.vertices[i].co = inv @ pos
    else:
        for i, pos in enumerate(new_positions):
            new_mesh.vertices[i].co = pos

    new_mesh.update()

    # Hard invariant: output topology must match correct topology exactly.
    assert len(new_mesh.vertices) == len(correct_basis_mesh.vertices), (
        "Output vert count does not match CORRECT — this is a bug"
    )

    # ── Reporting ────────────────────────────────────────────────────────────
    total = len(correct_basis_mesh.vertices)
    avg_gap = gap_sum / gap_samples if gap_samples else 0.0

    print(f"[UV Reorder] Sampled {sampled_count}/{total} correct verts from wrong.")
    if stripped_keys:
        print(f"  Stripped {stripped_keys} shape key(s) from output so the "
              f"transferred basis displays without interference.")
    if unmatched_verts:
        print(f"  Unmatched (no UV loops or empty sample): "
              f"{len(unmatched_verts)} verts kept correct-mesh positions")
        print(f"  First 20 unmatched indices: {unmatched_verts[:20]}")
    print(f"  UV gap (nearest-tri distance): "
          f"avg={avg_gap:.6f}  max={max_gap_overall:.6f}  "
          f"over_threshold({warn_uv_gap})={gap_warn_count}")

    # Deltas vs correct, to flag silent no-ops.
    deltas_vs_correct = [
        (new_positions[i] - correct_ref_positions[i]).length
        for i in range(total)
    ]
    avg_delta = sum(deltas_vs_correct) / total if total else 0.0
    max_delta = max(deltas_vs_correct) if deltas_vs_correct else 0.0
    nonzero = sum(1 for d in deltas_vs_correct if d > 1e-6)
    print(f"  Delta vs CORRECT:  avg={avg_delta:.6f}  max={max_delta:.6f}  "
          f"nonzero={nonzero}/{total}")

    # Bbox comparison between output, correct, and wrong.
    correct_bbox = _world_bbox_dims(correct_obj)
    wrong_bbox   = _world_bbox_dims(wrong_obj)
    # Output bbox in world space: new_positions are already world-space when
    # use_world_space=True; otherwise recompute.
    if use_world_space:
        output_bbox = _bbox_from_positions(new_positions)
    else:
        mw_out = new_obj.matrix_world
        output_bbox = _bbox_from_positions(
            [mw_out @ new_mesh.vertices[i].co for i in range(total)]
        )

    def _bbox_dist(a, b):
        return ((a[0] - b[0]) ** 2
                + (a[1] - b[1]) ** 2
                + (a[2] - b[2]) ** 2) ** 0.5

    d_out_correct = _bbox_dist(output_bbox, correct_bbox)
    d_out_wrong   = _bbox_dist(output_bbox, wrong_bbox)
    print(f"  BBox  correct={correct_bbox}")
    print(f"  BBox  wrong  ={wrong_bbox}")
    print(f"  BBox  output ={output_bbox}")
    print(f"  BBox  ||output-correct||={d_out_correct:.6f}  "
          f"||output-wrong||={d_out_wrong:.6f}")

    # ── Loud warnings that catch the classic failure modes ──────────────────
    if nonzero == 0:
        print("  WARNING: every vertex is identical to correct_obj. "
              "Nothing was actually sampled from wrong_obj. "
              "Check USE_DEPSGRAPH / USE_WORLD_SPACE / UV layer selection "
              "and that the two objects really are distinct shapes.")
    if d_out_correct < d_out_wrong * 0.5 and max_delta > 1e-6:
        print("  WARNING: output bbox resembles CORRECT more than WRONG. "
              "Possible role confusion or degenerate UV mapping — verify "
              "CORRECT_OBJ_NAME and WRONG_OBJ_NAME are not swapped.")
    if gap_warn_count > 0:
        print(f"  WARNING: {gap_warn_count} correct-vert UV samples were "
              f"farther than {warn_uv_gap} from any wrong-mesh UV triangle "
              f"(max gap={max_gap_overall:.6f}). These were snapped to the "
              f"nearest triangle boundary — expect small artifacts at the "
              f"corresponding verts.")

    print(f"[UV Reorder] New object: '{new_obj.name}' ({total} verts)")
    return new_obj


# ── Preconditions + runner ────────────────────────────────────────────────────

def _validate_inputs(correct_obj, wrong_obj, correct_name, wrong_name,
                     uv_layer_name):
    if correct_obj is None:
        raise RuntimeError(
            f"CORRECT object '{correct_name}' not found in bpy.data.objects"
        )
    if wrong_obj is None:
        raise RuntimeError(
            f"WRONG object '{wrong_name}' not found in bpy.data.objects"
        )
    if correct_obj.type != 'MESH':
        raise RuntimeError(
            f"CORRECT object '{correct_obj.name}' is type {correct_obj.type}, "
            f"expected MESH"
        )
    if wrong_obj.type != 'MESH':
        raise RuntimeError(
            f"WRONG object '{wrong_obj.name}' is type {wrong_obj.type}, "
            f"expected MESH"
        )
    if correct_obj is wrong_obj:
        raise RuntimeError(
            f"CORRECT and WRONG point to the same object '{correct_obj.name}'"
        )
    if len(correct_obj.data.vertices) < 3:
        raise RuntimeError(
            f"CORRECT object '{correct_obj.name}' has "
            f"{len(correct_obj.data.vertices)} verts (need >= 3)"
        )

    def _has_uv(mesh, name):
        if name:
            return mesh.uv_layers.get(name) is not None
        return mesh.uv_layers.active is not None

    if not _has_uv(correct_obj.data, uv_layer_name):
        raise RuntimeError(
            f"CORRECT object '{correct_obj.name}' is missing UV layer"
            + (f" '{uv_layer_name}'" if uv_layer_name else " (no active UV)")
        )
    if not _has_uv(wrong_obj.data, uv_layer_name):
        raise RuntimeError(
            f"WRONG object '{wrong_obj.name}' is missing UV layer"
            + (f" '{uv_layer_name}'" if uv_layer_name else " (no active UV)")
        )


def run(
    correct_obj_name=CORRECT_OBJ_NAME,
    wrong_obj_name=WRONG_OBJ_NAME,
    new_obj_name=NEW_OBJ_NAME,
    uv_layer_name=UV_LAYER_NAME,
    use_depsgraph=USE_DEPSGRAPH,
    use_world_space=USE_WORLD_SPACE,
    warn_uv_gap=WARN_UV_GAP,
):
    correct_obj = bpy.data.objects.get(correct_obj_name)
    wrong_obj   = bpy.data.objects.get(wrong_obj_name)

    _validate_inputs(correct_obj, wrong_obj,
                     correct_obj_name, wrong_obj_name,
                     uv_layer_name)

    new_obj = build_reordered_mesh(
        correct_obj=correct_obj,
        wrong_obj=wrong_obj,
        new_obj_name=new_obj_name,
        uv_layer_name=uv_layer_name,
        use_depsgraph=use_depsgraph,
        use_world_space=use_world_space,
        warn_uv_gap=warn_uv_gap,
    )

    if new_obj:
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.context.view_layer.objects.active = new_obj
        print(f"[UV Reorder] '{new_obj.name}' selected and active.")
    return new_obj


# ── Run on paste ──────────────────────────────────────────────────────────────
run()
