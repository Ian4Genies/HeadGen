import bpy
import random

# ---------------------------------------------------------------------------
# Per-shader-type color extraction helpers
# Each entry: shader node.type → callable(node, node_tree, color) that sets
# the color on that shader. Add new shader types here as needed.
# ---------------------------------------------------------------------------

def _key_color_bsdf_principled(
    node: bpy.types.Node,
    node_tree: bpy.types.NodeTree,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe Base Color on a Principled BSDF node. Returns True if applied."""
    inp = node.inputs.get("Base Color")
    if inp is None or inp.type != "RGBA":
        return False
    if inp.is_linked:
        for link in inp.links:
            node_tree.links.remove(link)
    inp.default_value = color
    inp.keyframe_insert("default_value", frame=frame)
    return True


# Map node.type → handler. Extend this dict to support additional shaders.
# Each handler signature: (node, node_tree, color, frame) -> bool
_SHADER_COLOR_HANDLERS: dict[str, callable] = {
    "BSDF_PRINCIPLED": _key_color_bsdf_principled,
    # "BSDF_DIFFUSE":  _key_color_bsdf_diffuse,   # example placeholder
    # "EMISSION":      _key_color_emission,         # example placeholder
}


def key_material_color(
    mat: bpy.types.Material,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Find the first supported shader node in mat, set its color, and insert a keyframe.

    Searches mat's node tree for any shader type listed in
    _SHADER_COLOR_HANDLERS and delegates to the matching handler.
    Returns True if a color was applied, False if no supported shader found.
    """
    if mat is None or not mat.use_nodes:
        return False

    for node in mat.node_tree.nodes:
        handler = _SHADER_COLOR_HANDLERS.get(node.type)
        if handler is not None:
            return handler(node, mat.node_tree, color, frame)

    return False


# ---------------------------------------------------------------------------
# Public operator-facing helpers
# ---------------------------------------------------------------------------

def randomize_head_material_color(
    mesh_obj: bpy.types.Object,
    rng: random.Random,
    frame: int,
) -> None:
    """Set and keyframe a random base color on the first material slot of mesh_obj."""
    if not mesh_obj.material_slots:
        return

    mat = mesh_obj.material_slots[0].material
    color = (rng.random(), rng.random(), rng.random(), 1.0)
    key_material_color(mat, color, frame)
