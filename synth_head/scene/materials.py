import bpy
import random

# ---------------------------------------------------------------------------
# Per-shader-type color keying helpers
# Each entry: shader node.type → callable(node, node_tree, color, frame) → bool
# Add new shader types here as needed.
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
_SHADER_COLOR_HANDLERS: dict[str, callable] = {
    "BSDF_PRINCIPLED": _key_color_bsdf_principled,
    # "BSDF_DIFFUSE":  _key_color_bsdf_diffuse,   # example placeholder
    # "EMISSION":      _key_color_emission,         # example placeholder
}

# Label used to locate the skin color RGB node inside head_mat.
_HEAD_COLOR_NODE_LABEL = "head_color"


def _find_node_by_label(
    node_tree: bpy.types.NodeTree,
    label: str,
) -> bpy.types.Node | None:
    """Return the first node whose label matches *label* (case-sensitive)."""
    return next((n for n in node_tree.nodes if n.label == label), None)


def _key_color_rgb_node(
    node: bpy.types.Node,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe the color output of an RGB node. Returns True if applied."""
    # RGB nodes expose their color via the 'Color' output socket's default value,
    # but the editable property is node.color — for an RGB node it is node.outputs[0].default_value.
    output = node.outputs[0] if node.outputs else None
    if output is None or output.type != "RGBA":
        return False
    output.default_value = color
    node.outputs[0].keyframe_insert("default_value", frame=frame)
    return True


# ---------------------------------------------------------------------------
# Public material helpers
# ---------------------------------------------------------------------------

def assign_exclusive_material(
    mesh_obj: bpy.types.Object,
    mat: bpy.types.Material,
) -> None:
    """Clear all material slots on mesh_obj and assign mat as the sole material."""
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    mesh_obj.active_material_index = 0


def key_material_color(
    mat: bpy.types.Material,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe the skin color on mat.

    Targets the RGB node labelled _HEAD_COLOR_NODE_LABEL first.
    Falls back to the first supported shader type in _SHADER_COLOR_HANDLERS
    if no labelled node is found.
    Returns True if a color was applied.
    """
    if mat is None or not mat.use_nodes:
        return False

    node = _find_node_by_label(mat.node_tree, _HEAD_COLOR_NODE_LABEL)
    if node is not None:
        return _key_color_rgb_node(node, color, frame)

    # Fallback: dispatch by shader type
    for n in mat.node_tree.nodes:
        handler = _SHADER_COLOR_HANDLERS.get(n.type)
        if handler is not None:
            return handler(n, mat.node_tree, color, frame)

    return False


# ---------------------------------------------------------------------------
# Public operator-facing helpers
# ---------------------------------------------------------------------------

def randomize_head_material_color(
    mesh_obj: bpy.types.Object,
    rng: random.Random,
    frame: int,
) -> None:
    """Set and keyframe a random skin color on the first material slot of mesh_obj."""
    if not mesh_obj.material_slots:
        return

    mat = mesh_obj.material_slots[0].material
    color = (rng.random(), rng.random(), rng.random(), 1.0)
    key_material_color(mat, color, frame)


def read_material_color(
    mesh_obj: bpy.types.Object,
) -> list[float] | None:
    """Read the current skin color from the first material slot of mesh_obj.

    Targets the RGB node labelled _HEAD_COLOR_NODE_LABEL first.
    Falls back to the Base Color input of the first supported shader type.
    Returns [r, g, b, a] as a plain list, or None if no color could be read.
    """
    if not mesh_obj.material_slots:
        return None

    mat = mesh_obj.material_slots[0].material
    if mat is None or not mat.use_nodes:
        return None

    node = _find_node_by_label(mat.node_tree, _HEAD_COLOR_NODE_LABEL)
    if node is not None:
        output = node.outputs[0] if node.outputs else None
        if output is not None and output.type == "RGBA":
            return list(output.default_value)

    # Fallback: read Base Color from the first supported shader node
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            inp = n.inputs.get("Base Color")
            if inp is not None and inp.type == "RGBA":
                return list(inp.default_value)

    return None
