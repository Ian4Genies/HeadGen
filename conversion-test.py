import bpy
import bmesh
from mathutils import Vector, kdtree


# ── UV helpers ────────────────────────────────────────────────────────────────

def build_vert_uvs(mesh, uv_layer_name=None):
    """
    For each vertex index, collect the unique list of UV coords (as float tuples)
    assigned to it via face loops.

    Returns: list[list[tuple[float, float]]] indexed by vertex.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    uv_layer = (
        bm.loops.layers.uv.get(uv_layer_name)
        if uv_layer_name
        else bm.loops.layers.uv.active
    )
    if uv_layer is None:
        bm.free()
        raise ValueError(f"No UV layer found on mesh '{mesh.name}'")

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


def build_uv_to_verts(vert_uvs, precision=6):
    """Invert: rounded uv_key -> list of vert indices that own that UV."""
    uv_map = {}
    for vi, uvs in enumerate(vert_uvs):
        for u, v in uvs:
            key = (round(u, precision), round(v, precision))
            bucket = uv_map.setdefault(key, [])
            if vi not in bucket:
                bucket.append(vi)
    return uv_map


def build_uv_kdtree(uv_map):
    """KDTree over unique UV keys for nearest-UV fallback matching."""
    keys = list(uv_map.keys())
    tree = kdtree.KDTree(len(keys))
    for i, (u, v) in enumerate(keys):
        tree.insert(Vector((u, v, 0.0)), i)
    tree.balance()
    return tree, keys


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


# ── Core reorder ──────────────────────────────────────────────────────────────

def build_reordered_mesh(
    correct_obj,
    wrong_obj,
    new_obj_name=None,
    uv_layer_name=None,
    uv_fallback_tolerance=1e-4,
    use_depsgraph=True,
    use_world_space=True,
):
    """
    Create a NEW object whose:
      - topology (vertex/edge/face order, UVs, groups, etc.) matches `correct_obj`
      - vertex positions are sampled from `wrong_obj`'s visible shape via UV
        correspondence

    Neither `correct_obj` nor `wrong_obj` is modified.

    Args:
        correct_obj:  Mesh with the CORRECT index order. Its topology is cloned
                      and becomes the topology of the new mesh. The new object
                      inherits its matrix_world so it is a drop-in.
        wrong_obj:    Mesh with the WRONG index order but the desired SHAPE.
                      Its vertex positions are sampled for every vert in
                      `correct_obj` via matching UVs.
        new_obj_name: Name for the new object. Defaults to
                      correct_obj.name + "_FromWrong".
        uv_layer_name: UV layer to use. None = active UV layer on each mesh.
        uv_fallback_tolerance: If an exact rounded-UV key is missing, accept a
                      nearest-UV match within this Euclidean distance in UV
                      space. Set to 0 to disable the fallback.
        use_depsgraph: If True, sample positions from the depsgraph-evaluated
                      mesh so shape keys and modifiers are included. If False,
                      use the raw basis mesh data.
        use_world_space: If True, sample wrong positions in world space and
                      convert to correct_obj's local space. If False, sample
                      raw local .co from wrong_mesh (requires both objects to
                      share a transform for the result to align).

    Returns:
        The new bpy.types.Object.
    """
    if new_obj_name is None:
        new_obj_name = correct_obj.name + "_FromWrong"

    print(f"[UV Reorder] correct (topology source): '{correct_obj.name}' "
          f"({len(correct_obj.data.vertices)} verts)")
    print(f"[UV Reorder] wrong   (shape source):    '{wrong_obj.name}' "
          f"({len(wrong_obj.data.vertices)} verts)")
    print(f"[UV Reorder] use_depsgraph={use_depsgraph}  "
          f"use_world_space={use_world_space}")

    # The topology source is always taken from the basis (data) so the output
    # stays a clean copy of correct_obj's mesh. If correct has live modifiers
    # we still want the resting topology and UVs unchanged.
    correct_basis_mesh = correct_obj.data

    # UVs come from the basis of both meshes. Modifiers don't typically change
    # UVs, and using the basis here keeps the UV→vertex index map aligned with
    # the basis vertex indices (which is what we want to write into).
    correct_vert_uvs = build_vert_uvs(correct_basis_mesh, uv_layer_name)

    # Sample the wrong mesh through an evaluated-mesh context so shape keys
    # and modifiers are baked into the positions we read.
    with _EvaluatedMesh(wrong_obj, use_depsgraph=use_depsgraph) as wrong_mesh_eval:
        wrong_vert_uvs = build_vert_uvs(wrong_mesh_eval, uv_layer_name)

        if use_world_space:
            mw_wrong = wrong_obj.matrix_world
            wrong_positions = [mw_wrong @ v.co.copy() for v in wrong_mesh_eval.vertices]
        else:
            wrong_positions = [v.co.copy() for v in wrong_mesh_eval.vertices]

    wrong_uv_map = build_uv_to_verts(wrong_vert_uvs)
    wrong_tree = wrong_keys = None
    if uv_fallback_tolerance > 0 and wrong_uv_map:
        wrong_tree, wrong_keys = build_uv_kdtree(wrong_uv_map)

    # The correct positions we use as a fallback for unmatched verts.
    if use_world_space:
        mw_correct = correct_obj.matrix_world
        correct_world_positions = [mw_correct @ v.co.copy() for v in correct_basis_mesh.vertices]
        new_world_positions = [p.copy() for p in correct_world_positions]
    else:
        correct_world_positions = None
        new_world_positions = [v.co.copy() for v in correct_basis_mesh.vertices]

    matched = 0
    fallback_used = 0
    ambiguous = 0
    unmatched_verts = []

    for ci, uvs in enumerate(correct_vert_uvs):
        if not uvs:
            unmatched_verts.append(ci)
            continue

        candidate_verts = []
        for u, v in uvs:
            key = (round(u, 6), round(v, 6))
            bucket = wrong_uv_map.get(key)
            if bucket:
                candidate_verts.extend(bucket)
            elif wrong_tree is not None:
                _co, idx, dist = wrong_tree.find(Vector((u, v, 0.0)))
                if dist <= uv_fallback_tolerance:
                    candidate_verts.extend(wrong_uv_map[wrong_keys[idx]])
                    fallback_used += 1

        if not candidate_verts:
            unmatched_verts.append(ci)
            continue

        unique = list(set(candidate_verts))

        if len(unique) == 1:
            new_world_positions[ci] = wrong_positions[unique[0]].copy()
        else:
            # Multiple wrong verts share this UV. Pick the candidate that
            # appears most often across the correct vert's UVs; ties fall
            # back to the 3D centroid (seam-safe when they're co-located).
            counts = {u: candidate_verts.count(u) for u in unique}
            top = max(counts.values())
            winners = [u for u, c in counts.items() if c == top]
            if len(winners) == 1:
                new_world_positions[ci] = wrong_positions[winners[0]].copy()
            else:
                avg = Vector((0.0, 0.0, 0.0))
                for u in winners:
                    avg += wrong_positions[u]
                avg /= len(winners)
                new_world_positions[ci] = avg
                ambiguous += 1

        matched += 1

    # Duplicate correct_mesh so all topology & attributes are preserved.
    new_mesh = correct_basis_mesh.copy()
    new_mesh.name = new_obj_name + "_mesh"

    new_obj = bpy.data.objects.new(new_obj_name, new_mesh)
    bpy.context.collection.objects.link(new_obj)

    # Make the new object a drop-in for correct_obj: same transform, so local
    # positions in new_mesh map to world identically.
    new_obj.matrix_world = correct_obj.matrix_world.copy()

    # Convert the accumulated positions back into the new mesh's local space.
    if use_world_space:
        inv = correct_obj.matrix_world.inverted()
        for i, world_pos in enumerate(new_world_positions):
            new_mesh.vertices[i].co = inv @ world_pos
    else:
        for i, local_pos in enumerate(new_world_positions):
            new_mesh.vertices[i].co = local_pos

    new_mesh.update()

    # ── Report ────────────────────────────────────────────────────────────────
    total = len(correct_basis_mesh.vertices)
    print(f"[UV Reorder] Done. New object: '{new_obj.name}' ({total} verts)")
    print(f"  Matched:                 {matched} / {total}")
    if fallback_used:
        print(f"  UV KDTree fallback hits: {fallback_used}")
    if ambiguous:
        print(f"  Ambiguous (averaged):    {ambiguous}")
    if unmatched_verts:
        print(f"  Unmatched: {len(unmatched_verts)} verts kept correct-mesh positions")
        print(f"  First 20 unmatched indices: {unmatched_verts[:20]}")

    # Sanity diagnostic: how far did positions move relative to correct?
    # If this is ~0, nothing is actually being sampled from wrong (likely a
    # depsgraph / transform / shape-key issue on wrong_obj).
    if use_world_space and correct_world_positions is not None:
        ref_positions = correct_world_positions
    else:
        ref_positions = [v.co.copy() for v in correct_basis_mesh.vertices]

    deltas = [(new_world_positions[i] - ref_positions[i]).length for i in range(total)]
    if deltas:
        avg_delta = sum(deltas) / len(deltas)
        max_delta = max(deltas)
        nonzero = sum(1 for d in deltas if d > 1e-6)
        print(f"  Delta vs correct:        "
              f"avg={avg_delta:.6f}  max={max_delta:.6f}  "
              f"nonzero={nonzero}/{total}")
        if nonzero == 0:
            print("  WARNING: every vertex is identical to correct_obj. "
                  "Likely wrong_obj's visible shape lives in shape keys / "
                  "modifiers / object transform — check use_depsgraph and "
                  "use_world_space flags.")

    return new_obj


# ── Main runner by explicit object names ──────────────────────────────────────

# Fill in the exact object names from your scene:
CORRECT_OBJ_NAME = "MeshA_Correct"   # correct vertex / polygon order (topology)
WRONG_OBJ_NAME   = "MeshB_Wrong"     # wrong order but the shape we want
NEW_OBJ_NAME     = None              # None => "<CORRECT_OBJ_NAME>_FromWrong"
UV_LAYER_NAME    = None              # None => active UV layer on each mesh
USE_DEPSGRAPH    = True              # bake modifiers + shape keys on wrong side
USE_WORLD_SPACE  = True              # respect object transforms


def run_by_name(
    correct_obj_name=CORRECT_OBJ_NAME,
    wrong_obj_name=WRONG_OBJ_NAME,
    new_obj_name=NEW_OBJ_NAME,
    uv_layer_name=UV_LAYER_NAME,
    use_depsgraph=USE_DEPSGRAPH,
    use_world_space=USE_WORLD_SPACE,
):
    correct_obj = bpy.data.objects.get(correct_obj_name)
    wrong_obj   = bpy.data.objects.get(wrong_obj_name)

    if correct_obj is None:
        print(f"[UV Reorder] ERROR: correct-order object '{correct_obj_name}' not found.")
        return None
    if wrong_obj is None:
        print(f"[UV Reorder] ERROR: wrong-order object '{wrong_obj_name}' not found.")
        return None
    if correct_obj.type != 'MESH' or wrong_obj.type != 'MESH':
        print(f"[UV Reorder] ERROR: both objects must be meshes "
              f"(got {correct_obj.type}, {wrong_obj.type}).")
        return None
    if correct_obj is wrong_obj:
        print(f"[UV Reorder] ERROR: correct and wrong objects are the same.")
        return None

    new_obj = build_reordered_mesh(
        correct_obj=correct_obj,
        wrong_obj=wrong_obj,
        new_obj_name=new_obj_name,
        uv_layer_name=uv_layer_name,
        use_depsgraph=use_depsgraph,
        use_world_space=use_world_space,
    )

    if new_obj:
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.context.view_layer.objects.active = new_obj
        print(f"[UV Reorder] '{new_obj.name}' selected and ready")

    return new_obj


# ── Run ───────────────────────────────────────────────────────────────────────
run_by_name()
